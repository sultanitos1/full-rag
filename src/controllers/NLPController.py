from .BaseController import BaseController
from stores.llm.LLMEnums import DocumentTypeEnum


MAX_HISTORY_TURNS = 5

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client,
                embedding_client, template_parser):
        super().__init__()

        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.collection_name = self.app_settings.VECTOR_DB_COLLECTION_NAME
        self.score_threshold = self.app_settings.SCORE_THRESHOLD

    def rewrite_query(self, query: str, history: list) -> str:
        if not history:
            return query

        context_lines = []
        for msg in history[-MAX_HISTORY_TURNS*2:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_lines.append(f"{role}: {content}")
        context = "\n".join(context_lines)

        rewrite_prompt = (
            "You are a search query rewriter. Given the conversation history "
            "and the latest user query, rewrite the latest query as a standalone, "
            "detailed search query. Return ONLY the rewritten query, nothing else.\n\n"
            f"Conversation:\n{context}\n\n"
            f"Latest query: {query}\n\n"
            f"Standalone query:"
        )

        rewritten = self.generation_client.generate_text(
            prompt=rewrite_prompt,
            max_output_tokens=100,
            temperature=0.0,
        )

        return (rewritten or query).strip().strip('"')

    def is_greeting_query(self, query: str) -> bool:
        query_clean = query.strip().lower().rstrip("?!.,;:")
        greetings = {
            "hi", "hello", "hey", "howdy", "greetings",
            "good morning", "good afternoon", "good evening", "good day",
            "what's up", "sup", "yo",
            "مرحبا", "اهلا", "اهلاً", "السلام عليكم", "سلام",
            "bonjour", "salut", "bonsoir",
            "hola", "buenos días", "buenas tardes",
        }
        return query_clean in greetings

    def chat(self, query: str, limit: int = 5, prior_history: list = None):

        if not query or not query.strip():
            return None

        search_query = self.rewrite_query(query, prior_history)
        vector = self.embedding_client.embed_text(text=search_query,
                                                document_type=DocumentTypeEnum.QUERY.value)

        if not vector or len(vector) == 0:
            return None

        results = self.vectordb_client.search_by_vector(
            collection_name=self.collection_name,
            vector=vector,
            limit=limit,
        )

        if not results:
            return None

        results = [doc for doc in results if doc.score >= self.score_threshold]

        if not results:
            return None

        return results

    def generate_chat_answer(self, query: str, retrieved_documents: list, prior_history: list = None, system_prompt: str = None):

        if system_prompt is None:
            system_prompt = self.template_parser.get("rag", "system_prompt")

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {
            "query": query
        })

        # prevent prompt truncation by limiting document budget
        max_input_chars = self.app_settings.INPUT_DEFAULT_MAX_CHARACTERS
        footer_len = len(footer_prompt) if footer_prompt else 0
        doc_budget = max_input_chars - footer_len

        documents_prompts = ""
        for idx, doc in enumerate(retrieved_documents):
            doc_prompt = self.template_parser.get("rag", "document_prompt", {
                "doc_num": idx + 1,
                "chunk_text": doc.text,
                "score": round(doc.score, 3),
            })
            if not doc_prompt:
                continue
            separator = "\n\n" if documents_prompts else ""
            if len(documents_prompts) + len(separator) + len(doc_prompt) > doc_budget:
                break
            documents_prompts += separator + doc_prompt

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        if prior_history:
            for msg in prior_history[-MAX_HISTORY_TURNS*2:]:
                role_value = msg.get("role", "user")
                if role_value == "assistant":
                    mapped_role = self.generation_client.enums.ASSISTANT.value
                else:
                    mapped_role = self.generation_client.enums.USER.value
                chat_history.append(
                    self.generation_client.construct_prompt(
                        prompt=msg.get("content", ""),
                        role=mapped_role,
                    )
                )

        full_prompt = (
            "\n\n".join([documents_prompts, footer_prompt])
            if documents_prompts
            else footer_prompt
        )

        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history

    def index_chunks(self, chunks: list):
        texts = [c.chunk_text for c in chunks]
        metadata = [dict(c.chunk_metadata) if c.chunk_metadata else {} for c in chunks]

        # get current point count and start IDs after it
        try:
            collection_info = self.vectordb_client.get_collection_info(
                collection_name=self.collection_name
            )
            base_id = collection_info.points_count if hasattr(collection_info, 'points_count') else 0
        except Exception:
            base_id = 0

        vectors = [
            self.embedding_client.embed_text(text=text,
                                            document_type=DocumentTypeEnum.DOCUMENT.value)
            for text in texts
        ]

        _ = self.vectordb_client.create_collection(
            collection_name=self.collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=False,
        )

        _ = self.vectordb_client.insert_many(
            collection_name=self.collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=list(range(base_id, base_id + len(chunks))),
        )

        return True

    def delete_file_vectors(self, asset_id: str):
        return self.vectordb_client.delete_by_filter(
            collection_name=self.collection_name,
            filter={"asset_id": asset_id}
        )
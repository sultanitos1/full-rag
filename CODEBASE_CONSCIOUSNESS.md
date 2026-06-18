# Mini-RAG Codebase Self-Consciousness

> **Purpose:** Single-collection tourism RAG chatbot. Users chat about Egypt destinations. Admin uploads PDFs/docs which are chunked, embedded, and indexed into Qdrant. Chat queries embed → retrieve → LLM generate.

---

## 1. Architecture Overview

```
FastAPI (uvicorn, port 5000, EC2, systemd service)
├── main.py — Startup: init OpenAI, Qdrant, MongoDB, TemplateParser
├── routes/
│   ├── base.py       GET  /api/v1/                    → {app_name, app_version}
│   ├── data.py       POST /api/v1/data/multi-upload   → batch upload files
│                    GET  /api/v1/data/files           → list all assets
│                    PUT  /api/v1/data/file/{file_id}  → replace file + re-index
│                    DELETE /api/v1/data/file/{file_id} → delete file + chunks + vectors
│   └── nlp.py        POST /api/v1/nlp/conversation   → create new chat session
│                    POST /api/v1/nlp/chat           → chat with RAG (requires conversation_id)
├── controllers/
│   ├── BaseController.py      — files_dir path, random string generator
│   ├── DataController.py      — validate file type/size, generate unique path
│   ├── ProcessController.py   — load file (txt/pdf/csv/docx), chunk with RecursiveCharacterTextSplitter
│   └── NLPController.py       — rewrite queries, embed, retrieve, generate answer, index chunks, delete vectors
├── models/
│   ├── AssetModel.py          — MongoDB: create, get, delete asset
│   ├── ChunkModel.py          — MongoDB: create, insert_many, delete by asset_id
│   ├── BaseDataModel.py       — db_client + settings
│   ├── db_schemes/asset.py    — Asset pydantic model
│   ├── db_schemes/data_chunk.py — DataChunk + RetrievedDocument pydantic models
│   └── enums/                 — ResponseSignal, DataBaseEnum, ProcessingEnum, AssetTypeEnum
├── stores/
│   ├── llm/                   — LLMInterface → OpenAIProvider, TemplateParser
│   ├── vectordb/              — VectorDBInterface → QdrantDBProvider
│   └── (rerank deleted)
  └── (CoHere deleted)
├── helpers/config.py          — Settings via pydantic-settings from .env
└── .env                       — all config (API keys, model IDs, thresholds)
```

---

## 2. Active Routes

| Method | Path | Purpose | Body/Params |
|--------|------|---------|-------------|
| GET | `/api/v1/` | Health check | — |
| POST | `/api/v1/nlp/conversation` | Create chat session | — |
| POST | `/api/v1/nlp/chat` | Chat | `{text, limit=5, conversation_id}` |
| POST | `/api/v1/data/multi-upload` | Batch upload | `files: UploadFile[], chunk_size=500, overlap_size=20` |
| GET | `/api/v1/data/files` | List assets | — |
| PUT | `/api/v1/data/file/{file_id}` | Replace file | `file: UploadFile, chunk_size=500, overlap_size=20` |
| DELETE | `/api/v1/data/file/{file_id}` | Delete file | — |

---

## 3. Data Flow — Chat

```
Angular → .NET → RAG

1. POST /api/v1/nlp/conversation
   → {"conversation_id": "a1b2c3..."}

2. POST /api/v1/nlp/chat({text: "what about hotels?", conversation_id: "a1b2c3..."})
   → load history from MongoDB `conversations` collection by conversation_id
   → NLPController.chat(query, history)
     → rewrite_query() — gpt-4o-mini rewrites "what about hotels?" → "hotels in Cairo"
     → embedding_client.embed_text(rewritten_query, QUERY)  # OpenAI 1536-dim
     → vectordb_client.search_by_vector(top_k=5)             # Qdrant cosine similarity
     → filter by score >= SCORE_THRESHOLD (0.2)
     → return RetrievedDocument[] with score, text, metadata
   → NLPController.generate_chat_answer(query, docs, history)
     → template_parser.get("rag", "system_prompt")           # en/rag.py
     → template_parser.get("rag", "document_prompt")         # format each doc
     → template_parser.get("rag", "footer_prompt")           # format query
     → generation_client.generate_text(prompt, history)      # OpenAI gpt-4o-mini
     → return answer
   → append Q&A turn to MongoDB `conversations` collection
   → response: {signal, message, answer, sources[{doc, city, score, excerpt}]}
```

## 4. Data Flow — Upload

```
POST /multi-upload(files[], chunk_size, overlap_size)
  for each file:
    validate_uploaded_file (content_type, extension, size)
    generate_unique_filepath (random_12chars_cleanedName.ext)
    save to disk (assets/files/)
    create Asset in MongoDB {type, name, size, config: {city, doc_type}}
    create ChunkModel via LangChain loader (PyMuPDF/TextLoader/CSVLoader/Docx2txtLoader)
    process_file_content (RecursiveCharacterTextSplitter, chunk_size=500, overlap=20)
    insert DataChunks to MongoDB (bulk_write, batch=100)
    index_chunks → embed each chunk → create Qdrant collection if needed → insert vectors
  → response: {signal, total, succeeded, failed, results[{file_id, inserted_chunks}]}
```

---

## 5. Key Configuration (.env)

| Variable | Value | Notes |
|----------|-------|-------|
| GENERATION_BACKEND | OPENAI | Only active provider |
| EMBEDDING_BACKEND | OPENAI | Only active provider |
| GENERATION_MODEL_ID | gpt-4o-mini | Cost-effective (low temp 0.1) |
| EMBEDDING_MODEL_ID | text-embedding-3-small | 1536 dim |
| VECTOR_DB_BACKEND | QDRANT | Cloud SaaS |
| SCORE_THRESHOLD | 0.2 | Relatively low |
| INPUT_DEFAULT_MAX_CHARACTERS | 4096 | Document budget |
| GENERATION_DEFAULT_MAX_TOKENS | 500 | Output limit |
| VECTOR_DB_COLLECTION_NAME | tourism_knowledge_base | Single collection |
| PRIMARY_LANG | en | English |
| DEFAULT_CITY | unknown | All uploads |
| DEFAULT_DOC_TYPE | general | All uploads |
| MONGODB_DATABASE | mini-rag | Atlas |

---

## 6. Dependencies (requirements.txt)

| Package | Purpose | Status |
|---------|---------|--------|
| fastapi | Framework | ✅ |
| uvicorn[standard] | Server | ✅ |
| python-multipart | Form parsing | ✅ |
| pydantic-settings | .env loading | ✅ |
| aiofiles | Async file writes | ✅ |
| openai | LLM + Embeddings | ✅ |
| motor | Async MongoDB | ✅ |
| pymongo | MongoDB driver | ✅ |
| qdrant-client | Vector DB | ✅ |
| PyMuPDF | PDF loader | ✅ |
| python-docx | DOCX support | ✅ |
| docx2txt | DOCX text | ✅ |
| langchain | Document loaders/splitters | ⚠️ Only langchain_community + langchain_text_splitters used |
| pydantic-mongo | — | ❌ Not imported anywhere |

---

## 7. Stores Structure

### LLM (`stores/llm/`)
```
LLMInterface.py              — Abstract: set_generation_model, set_embedding_model, generate_text, embed_text, construct_prompt
LLMEnums.py                  — LLMEnums(OPENAI), OpenAIEnums(SYSTEM/USER/ASSISTANT), DocumentTypeEnum
LLMProviderFactory.py        — create(provider) → OpenAIProvider
providers/
  └── OpenAIProvider.py      — OpenAI client, generate_text, embed_text
templates/
  ├── template_parser.py     — get(group, key, vars) → dynamic import from locales/{lang}/{group}.py
  └── locales/
      ├── en/rag.py          — system_prompt, document_prompt, footer_prompt
      └── ar/rag.py          — same prompts in Arabic
```

### VectorDB (`stores/vectordb/`)
```
VectorDBInterface.py         — Abstract: connect, disconnect, CRUD operations
VectorDBEnums.py             — VectorDBEnums(QDRANT), DistanceMethodEnums(COSINE, DOT)
VectorDBProviderFactory.py   — create(provider) → QdrantDBProvider
providers/
  └── QdrantDBProvider.py   — QdrantClient, full CRUD, payload indexing, filter building
```

---

## 8. Data Models

### Asset (MongoDB collection: `assets`)
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| _id | ObjectId | auto | |
| asset_type | str | required | `"file"` always |
| asset_name | str | required | `randomKey_cleanedName.ext` |
| asset_size | int | None | bytes |
| asset_config | dict | None | `{city: "unknown", doc_type: "general"}` |
| asset_pushed_at | datetime | `default_factory=datetime.utcnow` | Saves correctly now |

### DataChunk (MongoDB collection: `chunks`)
| Field | Type | Notes |
|-------|------|-------|
| _id | ObjectId | auto |
| chunk_text | str | Page content from loader |
| chunk_metadata | dict | `{city, doc_type, asset_id, source}` |
| chunk_order | int | 1-based index |

### Qdrant Point
| Field | Notes |
|-------|-------|
| id | Integer, sequential from `points_count` |
| vector | 1536-dim float array from OpenAI |
| payload.text | chunk_text |
| payload.metadata | `{city, doc_type, asset_id}` |
| payload indexes | metadata.city, metadata.doc_type, metadata.asset_id |

---

## 9. Known Bugs

### B1 — Chunk deletion filter field mismatch (CRITICAL)
`ChunkModel.py:52` queries `"chunk_asset_id"` but chunks store `asset_id` inside `chunk_metadata`. File DELETE doesn't remove chunks from MongoDB. Orphans accumulate.

### B2 — PUT endpoint data loss risk (HIGH)
`data.py` deletes old file + chunks + vectors **before** processing the new file. If new file is corrupt, old data is gone.

### B3 — No retry/timeout on OpenAI calls (MEDIUM)
`OpenAIProvider.py` has no retry logic, no timeout configuration.

### B4 — Sequential embedding (MEDIUM)
`NLPController.py` embeds each chunk one by one. OpenAI supports up to 2048 inputs per call.

---

## 10. Dead / Unused Code

| File | Lines | Dead Code | Reason |
|------|-------|-----------|--------|
| `ChunkModel.py` | 31-34 | `create_chunk()` | Never called — only `insert_many_chunks` used |
| `ProcessController.py` | 57 | `file_id` param | Accepted but never used in function body |
| `CoHereProvider.py` | 97 lines | Full CoHere provider | **Deleted** |
| `routes/base.py` | 1-2 | `import os`, `from fastapi import FastAPI` | Unused imports |
| `routes/nlp.py` | 1,8,10 | `from fastapi import FastAPI`, `import logging`, `logger` | Unused |
| `routes/data.py` | 1 | `from fastapi import FastAPI` | Unused (only APIRouter) |

---

## 11. RAG Parameters

| Parameter | Value | Assessment |
|-----------|-------|------------|
| Chunk size | 500 chars | Small (~75 words). Consider 1000-2000. |
| Chunk overlap | 20 chars | Too low (4%). Standard: 10-20%. |
| Score threshold | 0.2 | Permissive. Accepts near-random matches. |
| Top-K default | 5 | Reasonable. |
| Temperature | 0.1 | Good for factual consistency. |
| Max tokens | 500 | Reasonable for concise answers. |
| Document budget | 4096 chars | Character-based (not token-based). |
| History window | last 6 messages | Reasonable. |
| Embedding model | text-embedding-3-small | 1536 dim, $0.13/M tokens. Good. |
| Generation model | gpt-4o-mini | $0.15/M in, $0.60/M out. Good. |

---

## 12. Prompts (English)

### System Prompt
> You are a travel assistant. Your knowledge comes ONLY from the provided sources below.
> RULES:
> 1. Answer ONLY using information EXPLICITLY stated in the provided sources.
> 2. If the sources only partially answer, state what is confirmed and note what is missing.
> 3. Respond in the same language as the user.
> 4. Keep answers clear, direct, and concise.

### Document Prompt
```
## Source $doc_num [Relevance: $score]
$chunk_text
```

### Footer Prompt
> REMEMBER: Answer ONLY from the provided sources above.
> ## Question:
> $query
> ## Answer:

---

## 13. Git History (last 5 commits)

| Commit | Message |
|--------|---------|
| `cec0e27` | cleanup: remove reranking and CoHere unused providers |
| `ee6ef99` | fix: use default_factory for asset_pushed_at to prevent bson encoding error |
| `f6c53b3` | fix: asset_pushed_at timestamp on upload, add GET /files + PUT /file/{file_id}, rename to /multi-upload |
| `0fa7167` | cleanup: remove dead code (schemas, methods, enums, related questions) + add Postman collection |
| `c6042b5` | stable: production-ready single-collection RAG chatbot |
| `111b5e6` | feat: cross-encoder reranker, multi-upload, city detection, prompt rewrite |

---

## 14. Deployment (EC2)

| Service | Details |
|---------|---------|
| Server | Ubuntu EC2, port 5000 |
| Process manager | systemd — `rag.service` |
| Restart policy | `Restart=always` |
| Python | conda env `mini-rag` (Python 3.11) |
| Deploy script | `~/deploy.sh` — git pull, cd src, restart |
| Remote | SSH via deploy key |

---

## 15. File Map (src/)

```
src/
├── .env                          # Config: API keys, model IDs, thresholds
├── .gitignore                    # __pycache__, .env, assets/files, assets/database
├── main.py                       # FastAPI app, startup/shutdown hooks, middleware
├── requirements.txt              # Python deps (fixed versions)
├── drop_collections.py           # Utility: drops MongoDB chunks + assets collections
├── assets/files/                 # Uploaded files on disk
├── helpers/
│   └── config.py                 # Settings(BaseSettings) + get_settings()
├── controllers/
│   ├── __init__.py               # Exports: DataController, ProcessController, NLPController
│   ├── BaseController.py         # Base: files_dir, generate_random_string
│   ├── DataController.py         # validate_uploaded_file, generate_unique_filepath, get_clean_file_name
│   ├── ProcessController.py      # get_file_loader, get_file_content, process_file_content
│   └── NLPController.py          # chat, rewrite_query, generate_chat_answer, index_chunks, delete_file_vectors, is_greeting_query
├── models/
│   ├── __init__.py               # Exports: ResponseSignal, ProcessingEnum
│   ├── BaseDataModel.py          # Base: db_client, app_settings
│   ├── AssetModel.py             # create, get_by_id, delete asset
│   ├── ChunkModel.py             # create, insert_many, delete_by_asset_id
│   ├── ConversationModel.py      # create, get, append_turn conversation in MongoDB
│   ├── db_schemes/
│   │   ├── asset.py              # Asset pydantic model
│   │   ├── conversation.py       # Conversation pydantic model (history, timestamps)
│   │   └── data_chunk.py         # DataChunk + RetrievedDocument pydantic models
│   └── enums/
│       ├── AssetTypeEnum.py      # FILE = "file"
│       ├── DataBaseEnum.py       # COLLECTION_CHUNK_NAME, COLLECTION_ASSET_NAME, COLLECTION_CONVERSATION_NAME
│       ├── ProcessingEnum.py     # TXT, PDF, CSV, DOCX
│       └── ResponseEnums.py      # FILE_*, CHAT_*, DELETE_*, MULTI_*, INVALID_QUERY
├── routes/
│   ├── base.py                   # GET /api/v1/
│   ├── data.py                   # POST /multi-upload, GET /files, PUT /file/{id}, DELETE /file/{id}
│   ├── nlp.py                    # POST /conversation, POST /chat
│   └── schemes/
│       └── nlp.py                # ChatRequest pydantic model (text, limit, conversation_id)
├── stores/
│   ├── llm/
│   │   ├── LLMInterface.py       # Abstract base
│   │   ├── LLMEnums.py           # Enums: OPENAI, role enums, DocumentTypeEnum
│   │   ├── LLMProviderFactory.py # Factory → OpenAIProvider
│   │   ├── providers/
│   │   │   └── OpenAIProvider.py # generate_text, embed_text via openai lib
│   │   └── templates/
│   │       ├── template_parser.py # Dynamic locale template loader with fallback
│   │       └── locales/
│   │           ├── en/rag.py     # English prompts
│   │           └── ar/rag.py     # Arabic prompts
│   └── vectordb/
│       ├── VectorDBInterface.py  # Abstract base
│       ├── VectorDBEnums.py      # QDRANT, COSINE/DOT
│       ├── VectorDBProviderFactory.py # Factory → QdrantDBProvider
│       └── providers/
│           └── QdrantDBProvider.py # Full Qdrant CRUD, filter builder
└── tests/                        # Manual test payloads (JSON) + ad-hoc scripts
    ├── test_cairo.json
    ├── test_arabic.json
    ├── test_france.json
    ├── test_greeting.json
    ├── test_empty.json
    ├── test_fallback.json
    ├── test_multi.json
    ├── check_chunks.py
    ├── check_qdrant.py
    └── check_qdrant2.py
```

---

## 16. Recent Changes

### CoHere provider removed (June 2026)
Deleted `CoHereProvider.py` (97 lines) + all references.
- `providers/__init__.py` — export removed
- `LLMProviderFactory.py` — import + COHERE branch removed
- `LLMEnums.py` — `LLMEnums.COHERE` + entire `CoHereEnums` class removed
- `config.py` — `COHERE_API_KEY` field removed
- `.env` — `COHERE_API_KEY=""` removed
- `requirements.txt` — `cohere==5.5.8` removed

### Conversation history in MongoDB (June 2026)
Added persistent conversation history via MongoDB `conversations` collection.
- New file `models/db_schemes/conversation.py` — `Conversation` schema with `history`, `created_at`, `updated_at`
- New file `models/ConversationModel.py` — `create_conversation()`, `get_conversation()`, `append_turn()`
- New endpoint `POST /api/v1/nlp/conversation` — creates a new conversation, returns `conversation_id`
- Modified `POST /api/v1/nlp/chat` — `ChatRequest` replaces `history` with `conversation_id`. Loads history from MongoDB, appends Q&A turn after each response.
- `DataBaseEnum` — added `COLLECTION_CONVERSATION_NAME = "conversations"`
- `.NET/Angular` calls `/conversation` once per new chat, stores the id, then passes it with every `/chat` request.

### Query rewriting for conversation-aware retrieval (June 2026)
Added conversation-aware retrieval via `rewrite_query()` in `NLPController.py`.
- `NLPController.py` — added `rewrite_query()` method: uses gpt-4o-mini to rewrite
  the latest user query into a standalone search query using conversation history
- `NLPController.chat()` — now accepts `prior_history` param, calls rewrite before embed
- `routes/nlp.py` — passes `prior_history` to `chat()`
- Cost: ~80 tokens per rewrite (~$0.000015), +~200ms latency per turn
- Prompt: "Given the conversation, rewrite the latest query as a standalone search..."

### Reranking removed (June 2026)
Deleted entire `src/stores/rerank/` directory (7 files) and all references:
- `RerankInterface.py`, `RerankEnums.py`, `RerankProviderFactory.py`
- `CrossEncoderRerankProvider.py`, `OllamaRerankProvider.py`
- `main.py` — import + init block removed
- `NLPController.py` — `rerank_client`/`rerank_model_id` params removed, `chat()` simplified to always use `limit` and `SCORE_THRESHOLD`
- `routes/nlp.py` + `routes/data.py` (3x) — rerank args removed from NLPController construction
- `helpers/config.py` — `RERANK_BACKEND` + `RERANK_MODEL_ID` fields removed
- `.env` — `RERANK_BACKEND=` + `RERANK_MODEL_ID=BAAI/bge-reranker-v2-m3` removed
- `requirements.txt` — `sentence-transformers==3.4.1` removed

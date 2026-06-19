from qdrant_client import models, QdrantClient
from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums
import logging
from typing import List, Optional
from models.db_schemes import RetrievedDocument


class QdrantDBProvider(VectorDBInterface):

    def __init__(self, qdrant_db_url: str, qdrant_db_api_key: str, distance_method: str):

        self.client = None
        self.qdrant_db_url = qdrant_db_url
        self.qdrant_db_api_key = qdrant_db_api_key
        self.qdrant_db_distance_method = distance_method

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT

        self.logger = logging.getLogger(__name__)

    def connect(self):
        self.client = QdrantClient(url=self.qdrant_db_url, api_key=self.qdrant_db_api_key)

    def disconnect(self):
        self.client = None

    def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)

    def list_all_collections(self) -> List:
        return self.client.get_collections()

    def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name=collection_name)

    def delete_collection(self, collection_name: str):
        if self.is_collection_existed(collection_name):
            return self.client.delete_collection(collection_name=collection_name)

    def create_collection(self, collection_name: str,
                                embedding_size: int,
                                do_reset: bool = False):
        if do_reset:
            _ = self.delete_collection(collection_name=collection_name)

        if not self.is_collection_existed(collection_name):
            _ = self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )

            for field in ["project_id", "city", "doc_type", "asset_id"]:
                try:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=f"metadata.{field}",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                except Exception as e:
                    self.logger.warning(f"Could not create index on metadata.{field}: {e}")

            return True

        return False

    def _build_filter(self, filter: dict) -> Optional[models.Filter]:
        if not filter:
            return None

        conditions = []
        for key, value in filter.items():
            conditions.append(
                models.FieldCondition(
                    key=f"metadata.{key}",
                    match=models.MatchValue(value=value)
                )
            )

        return models.Filter(must=conditions)

    def insert_one(self, collection_name: str, text: str, vector: list,
                        metadata: dict = None,
                        record_id: str = None):

        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Can not insert new record to non-existed collection: {collection_name}")
            return False

        try:
            _ = self.client.upload_records(
                collection_name=collection_name,
                records=[
                    models.Record(
                        id=[record_id],
                        vector=vector,
                        payload={
                            "text": text, "metadata": metadata
                        }
                    )
                ]
            )
        except Exception as e:
            self.logger.error(f"Error while inserting batch: {e}")
            return False

        return True

    def insert_many(self, collection_name: str, texts: list,
                        vectors: list, metadata: list = None,
                        record_ids: list = None, batch_size: int = 50):

        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = list(range(0, len(texts)))

        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size

            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            batch_record_ids = record_ids[i:batch_end]

            batch_records = [
                models.Record(
                    id=batch_record_ids[x],
                    vector=batch_vectors[x],
                    payload={
                        "text": batch_texts[x], "metadata": batch_metadata[x]
                    }
                )

                for x in range(len(batch_texts))
            ]

            try:
                _ = self.client.upload_records(
                    collection_name=collection_name,
                    records=batch_records,
                )
            except Exception as e:
                self.logger.error(f"Error while inserting batch: {e}")
                return False

        return True

    def search_by_vector(self, collection_name: str, vector: list, limit: int = 5, filter: Optional[dict] = None):

        query_filter = self._build_filter(filter) if filter else None

        results = self.client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=query_filter
        )

        if not results or len(results) == 0:
            return None

        return [
            RetrievedDocument(**{
                "score": result.score,
                "text": result.payload.get("text", ""),
                "metadata": result.payload.get("metadata", {}),
            })
            for result in results
        ]

    def delete_by_filter(self, collection_name: str, filter: dict):
        if not self.is_collection_existed(collection_name):
            return False

        query_filter = self._build_filter(filter)
        if not query_filter:
            return False

        self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=query_filter
            )
        )

        return True
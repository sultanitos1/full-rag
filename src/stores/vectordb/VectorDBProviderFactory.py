from .providers import QdrantDBProvider
from .VectorDBEnums import VectorDBEnums
from controllers.BaseController import BaseController

class VectorDBProviderFactory:
    def __init__(self, config):
        self.config = config
        self.base_controller = BaseController()

    def create(self, provider: str):
        if provider == VectorDBEnums.QDRANT.value:
            return QdrantDBProvider(
            qdrant_db_url=self.config.QDRANT_DB_URL,
            qdrant_db_api_key=self.config.QDRANT_DB_API_KEY,
            distance_method=self.config.DISTANCE_METHOD,
        )
        return None

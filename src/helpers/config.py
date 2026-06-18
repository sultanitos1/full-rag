from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    APP_NAME: str
    APP_VERSION: str

    FILE_ALLOWED_TYPES: list
    FILE_ALLOWED_EXTENSIONS: list = [".txt", ".pdf", ".csv", ".docx"]
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int
    VECTOR_DB_COLLECTION_NAME: str = "tourism_knowledge_base"
    DEFAULT_CITY: str = "unknown"
    DEFAULT_DOC_TYPE: str = "general"

    MONGODB_URL: str
    MONGODB_DATABASE: str

    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: str = None
    OPENAI_API_URL: str = None
    GENERATION_MODEL_ID: str = None
    EMBEDDING_MODEL_ID: str = None
    EMBEDDING_MODEL_SIZE: int = None
    INPUT_DEFAULT_MAX_CHARACTERS: int = None
    GENERATION_DEFAULT_MAX_TOKENS: int = None
    GENERATION_DEFAULT_TEMPERATURE: float = None

    VECTOR_DB_BACKEND : str
    QDRANT_DB_URL : str
    DISTANCE_METHOD: str = None
    QDRANT_DB_API_KEY : str 

    PRIMARY_LANG: str = "en"
    DEFAULT_LANG: str = "en"

    SCORE_THRESHOLD: float = 0.4

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()

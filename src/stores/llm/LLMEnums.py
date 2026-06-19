from enum import Enum

class LLMEnums(Enum):
    OPENAI = "OPENAI"

class OpenAIEnums(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class DocumentTypeEnum(Enum):
    DOCUMENT = "document"
    QUERY = "query"
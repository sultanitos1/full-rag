from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    text: str
    limit: Optional[int] = 5
    conversation_id: Optional[str] = None

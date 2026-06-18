from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

class Conversation(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    title: str = ""
    history: List[dict] = Field(default=[])
    created_at: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("Africa/Cairo")))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("Africa/Cairo")))

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_indexes(cls):
        return []

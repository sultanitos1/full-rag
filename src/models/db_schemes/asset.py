from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid import ObjectId
from datetime import datetime
from zoneinfo import ZoneInfo

class Asset(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    asset_type: str = Field(..., min_length=1)
    asset_name: str = Field(..., min_length=1)
    asset_size: int = Field(ge=0, default=None)
    asset_config: dict = Field(default=None)
    asset_pushed_at: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("Africa/Cairo")))

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [
                    ("asset_name", 1)
                ],
                "name": "asset_name_index_1",
                "unique": True
            },
        ]
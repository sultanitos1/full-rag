from .BaseDataModel import BaseDataModel
from .db_schemes import Conversation
from .enums.DataBaseEnum import DataBaseEnum
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

class ConversationModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.collection = self.db_client[DataBaseEnum.COLLECTION_CONVERSATION_NAME.value]

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        await instance.init_collection()
        return instance

    async def init_collection(self):
        all_collections = await self.db_client.list_collection_names()
        if DataBaseEnum.COLLECTION_CONVERSATION_NAME.value not in all_collections:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_CONVERSATION_NAME.value]
            indexes = Conversation.get_indexes()
            for index in indexes:
                await self.collection.create_index(
                    index["key"],
                    name=index["name"],
                    unique=index["unique"]
                )

    async def create_conversation(self):
        conv_id = uuid.uuid4().hex
        record = Conversation(**{"_id": conv_id})
        await self.collection.insert_one(record.dict(by_alias=True))
        return record

    async def get_conversation(self, conversation_id: str):
        record = await self.collection.find_one({"_id": conversation_id})
        return Conversation(**record) if record else None

    async def append_turn(self, conversation_id: str, user_msg: str, assistant_msg: str):
        now = datetime.now(ZoneInfo("Africa/Cairo"))

        await self.collection.update_one(
            {"_id": conversation_id, "title": {"$in": ["", None]}},
            {"$set": {"title": user_msg[:100]}},
        )

        await self.collection.update_one(
            {"_id": conversation_id},
            {
                "$push": {
                    "history": {
                        "$each": [
                            {"role": "user", "content": user_msg},
                            {"role": "assistant", "content": assistant_msg},
                        ]
                    }
                },
                "$set": {"updated_at": now},
            }
        )

    async def list_conversations(self, ids: list[str]):
        cursor = self.collection.find(
            {"_id": {"$in": ids}},
            {"_id": 1, "title": 1, "updated_at": 1},
        ).sort("updated_at", -1)
        results = await cursor.to_list(length=None)
        return [
            {
                "conversation_id": r["_id"],
                "title": r.get("title", ""),
                "updated_at": r.get("updated_at").replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Africa/Cairo")).isoformat() if r.get("updated_at") else None,
            }
            for r in results
        ]

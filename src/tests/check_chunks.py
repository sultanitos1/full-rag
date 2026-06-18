from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings
import asyncio

async def run():
    s = get_settings()
    c = AsyncIOMotorClient(s.MONGODB_URL)
    db = c[s.MONGODB_DATABASE]
    cursor = db.chunks.find().sort("chunk_order", 1)
    docs = await cursor.to_list(length=None)
    for d in docs:
        meta = d.get("chunk_metadata", {})
        text = str(d.get("chunk_text", ""))[:80]
        print(str(d.get("chunk_order")) + " " + text)
    print("Total: " + str(len(docs)))
    c.close()

asyncio.run(run())

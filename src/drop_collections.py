from motor.motor_asyncio import AsyncIOMotorClient
from helpers.config import get_settings
import asyncio

async def run():
    s = get_settings()
    c = AsyncIOMotorClient(s.MONGODB_URL)
    db = c[s.MONGODB_DATABASE]
    for name in ["chunks", "assets"]:
        if name in await db.list_collection_names():
            await db[name].drop()
            print(f"Dropped {name}")
    c.close()
    print("Done.")

asyncio.run(run())

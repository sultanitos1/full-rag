"""Check Qdrant collection contents."""
import sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

from helpers.config import get_settings
from qdrant_client import QdrantClient

settings = get_settings()
client = QdrantClient(url=settings.QDRANT_DB_URL, api_key=settings.QDRANT_DB_API_KEY)
name = settings.VECTOR_DB_COLLECTION_NAME
cols = [c.name for c in client.get_collections().collections]
print("Collections:", cols)

if name in cols:
    info = client.get_collection(name)
    print(f"Points: {info.points_count}, Vector size: {info.config.params.vectors.size}")
    points, _ = client.scroll(collection_name=name, limit=3, with_payload=True)
    for p in points:
        text = str(p.payload.get("text", ""))[:120]
        print(f"ID={p.id} text={text}")

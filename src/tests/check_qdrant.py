"""Check Qdrant collection contents."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from helpers.config import get_settings
from qdrant_client import QdrantClient

settings = get_settings()
client = QdrantClient(
    url=settings.QDRANT_DB_URL,
    api_key=settings.QDRANT_DB_API_KEY,
)

name = settings.VECTOR_DB_COLLECTION_NAME
collections = [c.name for c in client.get_collections().collections]
print("Collections:", collections)

if name in collections:
    info = client.get_collection(name)
    print(f"Points: {info.points_count}")
    print(f"Vector size: {info.config.params.vectors.size}")

    # scroll through first 5 points
    points, _ = client.scroll(collection_name=name, limit=5, with_payload=True)
    for p in points:
        print(f"\nID={p.id} score={p.score}")
        print(f"  Payload: {p.payload}")
        print(f"  Text: {str(p.payload.get('text', ''))[:100]}")

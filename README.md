# Mini RAG — Multi-City Tourism Chatbot

A multi-provider RAG (Retrieval-Augmented Generation) chatbot for tourism insights. Users ask questions about cities, attractions, restaurants, hotels, and shopping — the system retrieves relevant document chunks and generates answers grounded in uploaded content.

---

## Architecture

```
┌─ Frontend (Angular + .NET) ──────────────────────────┐
│  POST /api/v1/nlp/chat   { text, limit, doc_type, history }  │
└──────────────────────────┬──────────────────────────┘
                           │
┌─ Backend (FastAPI) ──────▼──────────────────────────┐
│                                                      │
│  LLM Provider  ◄── Factory ──── OpenAI / CoHere     │
│  Embedding     ◄── Factory ──── OpenAI / CoHere     │
│  Vector DB     ◄── Factory ──── Qdrant (extensible) │
│  Reranker      ◄── Factory ──── CrossEncoder / Ollama │
│                                                      │
│  ┌─ MongoDB Atlas ──────────────────────────────┐   │
│  │  Projects | Assets | Chunks (metadata)       │   │
│  └──────────────────────────────────────────────┘   │
│  ┌─ Qdrant Cloud ───────────────────────────────┐   │
│  │  tourism_knowledge_base (single collection)   │   │
│  │  metadata fields: city, doc_type, asset_id    │   │
│  └──────────────────────────────────────────────┘   │
│  ┌─ city_mappings.json ─────────────────────────┐   │
│  │  Country→city mapping + known_cities[]        │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

- **LLM**: Swappable via `.env` — Ollama (dev, OpenAI-compatible), OpenAI (production), CoHere
- **Vector DB**: Qdrant Cloud (single collection, `tourism_knowledge_base`)
- **Reranker**: Cross-Encoder (`BAAI/bge-reranker-v2-m3`) on CPU; falls back to Qdrant score threshold if unavailable
- **MongoDB Atlas**: Stores project/asset/chunk records
- **City Detection**: Filename parsing (`cairo_restaurants.pdf`), content-based fallback on upload, query-time detection from user text

---

## API Reference

### Global Chat (Primary)

**`POST /api/v1/nlp/chat`**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | yes | User question |
| `limit` | int | no | Max sources (default 5) |
| `doc_type` | string | no | Filter by document type (e.g. `restaurants`, `hotels`) |
| `history` | array | no | Previous messages `[{"role":"user"/"assistant", "content":"..."}]` |

**Response:**
```json
{
  "signal": "chat_success",
  "message": "Here's what I found based on the available documents.",
  "answer": "Cairo has several highly-rated restaurants...",
  "sources": [
    {
      "document_name": "cairo_restaurants_guide.pdf",
      "city": "cairo",
      "doc_type": "restaurants",
      "score": 0.8921,
      "excerpt": "The best restaurants in Cairo include..."
    }
  ],
  "related_questions": [
    "What are the best hotels in Cairo?",
    "Which restaurants serve local Egyptian food?"
  ]
}
```

**Error signals:** `no_relevant_documents`, `chat_error`, `invalid_query`

---

### Data Endpoints (Admin — Upload & Manage)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/data/upload/{project_id}` | Upload single file + auto-chunk |
| `POST` | `/api/v1/data/upload-multi` | Upload multiple files + auto-detect city |
| `PUT` | `/api/v1/data/asset/{asset_id}` | Change city/type on an asset |
| `GET` | `/api/v1/data/assets/uncategorized` | List assets with unknown city |
| `GET` | `/api/v1/data/cities` | List distinct cities in DB |
| `POST` | `/api/v1/data/process/{project_id}` | Re-process files into chunks |
| `DELETE` | `/api/v1/data/project/{project_id}` | Delete project + assets + chunks + vectors |
| `DELETE` | `/api/v1/data/file/{file_id}` | Delete single file + chunks + vectors |
| `DELETE` | `/api/v1/data/chunks/{project_id}` | Delete chunks + vectors only |

#### Upload Single File

```
POST /api/v1/data/upload/{project_id}
```
**Form data:**
- `file` — the file (PDF, DOCX, CSV, TXT)
- `city` — (optional, overrides filename detection)
- `doc_type` — (optional, e.g. `attractions`, `hotels`, `food`)
- `chunk_size` — (optional, default 500)
- `overlap_size` — (optional, default 20)

#### Upload Multiple Files

```
POST /api/v1/data/upload-multi
```
Automatically detects city from filename (`cairo_restaurants.pdf` → city=`cairo`, type=`restaurants`). Falls back to content detection for files named `unknown_*.pdf`. Each file goes to its own city project.

---

### Legacy Endpoints (Project-scoped)

Kept for backward compatibility — prefer `/chat` for new integrations.

| Method | Path |
|--------|------|
| `POST` | `/api/v1/nlp/index/push/{project_id}` |
| `GET` | `/api/v1/nlp/index/info/{project_id}` |
| `POST` | `/api/v1/nlp/index/search/{project_id}` |
| `POST` | `/api/v1/nlp/index/answer/{project_id}` |

---

## File Naming Convention

Files are expected to follow: **`{city}_{type}.{ext}`**

Examples:
- `cairo_restaurants.pdf` → city=`cairo`, type=`restaurants`
- `alexandria_hotels.docx` → city=`alexandria`, type=`hotels`
- `unknown_attractions.pdf` → city detected from content, type=`attractions`

Supported extensions: `.pdf`, `.docx`, `.csv`, `.txt`

---

## Environment Variables

| Variable | Dev Value | Production | Notes |
|----------|-----------|------------|-------|
| `GENERATION_BACKEND` | `OPENAI` | `OPENAI` or `COHERE` | LLM provider |
| `EMBEDDING_BACKEND` | `OPENAI` | `OPENAI` or `COHERE` | Embedding provider |
| `OPENAI_API_KEY` | `ollama` | `<your-key>` | Empty string for Ollama |
| `OPENAI_API_URL` | `http://192.168.1.8:11434/v1` | `https://api.openai.com/v1` | Switch for production |
| `GENERATION_MODEL_ID` | `qwen2.5:latest` | `gpt-4o` or `gpt-4o-mini` | |
| `EMBEDDING_MODEL_ID` | `nomic-embed-text` | `text-embedding-3-small` | Must match embedding size |
| `EMBEDDING_MODEL_SIZE` | `768` | `1536` | Must match model |
| `RERANK_BACKEND` | `CROSS_ENCODER` | `CROSS_ENCODER` | Or `OLLAMA` |
| `VECTOR_DB_BACKEND` | `QDRANT` | `QDRANT` | |
| `QDRANT_DB_URL` | `<cloud-url>` | `<cloud-url>` | |
| `QDRANT_DB_API_KEY` | `<your-key>` | `<your-key>` | |
| `MONGODB_URL` | `<atlas-url>` | `<atlas-url>` | |
| `MONGODB_DATABASE` | `mini-rag` | `mini-rag` | |
| `SCORE_THRESHOLD` | `0.2` | `0.4` | Only used when reranker unavailable |
| `PRIMARY_LANG` | `en` | `en` | Prompt language |
| `INPUT_DEFAULT_MAX_CHARACTERS` | `2048` | `2048` | Max input chars for LLM |

---

## Quick Start (Server Deployment)

```bash
# Clone
git clone <repo>
cd mini-rag/src

# Install dependencies
pip install -r requirements.txt

# Configure .env
# Set OPENAI_API_KEY, QDRANT_DB_URL, QDRANT_DB_API_KEY, MONGODB_URL for production

# Run
python -m uvicorn main:app --host 0.0.0.0 --port 5000
```

---

## Greeting Detection

Pure greetings (`"hi"`, `"hello"`, `"مرحبا"`, `"bonjour"`) skip vector search and return a warm welcome. Queries like `"hi what restaurants are in cairo"` do NOT trigger this — they hit the full RAG pipeline.

---

## How Reranking Works

1. Qdrant retrieves top 20 results by cosine similarity
2. Cross-encoder re-scores all 20 with relevance logits
3. Results with logit >= 0.0 pass (filters clearly irrelevant)
4. Top `limit` (default 5) returned to LLM
5. If cross-encoder is unavailable, falls back to Qdrant score >= `SCORE_THRESHOLD`

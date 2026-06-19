# 🏛️ Full RAG — Multi-City Tourism Chatbot

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/OpenAI-gpt--4o--mini-412991?style=for-the-badge&logo=openai" alt="OpenAI">
  <img src="https://img.shields.io/badge/Qdrant-Cloud-FF6F00?style=for-the-badge&logo=qdrant" alt="Qdrant">
  <img src="https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb" alt="MongoDB">
  <img src="https://img.shields.io/badge/Angular-17-DD0031?style=for-the-badge&logo=angular" alt="Angular">
  <img src="https://img.shields.io/badge/.NET-8-512BD4?style=for-the-badge&logo=dotnet" alt=".NET">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
</p>

<p align="center">
  <b>A production-ready Retrieval-Augmented Generation chatbot for tourism insights.</b><br>
  Users ask about cities, attractions, restaurants, hotels, and shopping —<br>
  the system retrieves relevant document chunks and generates grounded answers via OpenAI.
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **Stateful Conversations** | History persisted in MongoDB — resume any chat, anywhere |
| 🔄 **Query Rewriting** | Follow-ups like "what about hotels there?" → standalone search query |
| 🏷️ **Auto-Titling** | First user message becomes the conversation title — sidebar ready |
| 📄 **Multi-File Upload** | Batch upload PDF/DOCX/CSV/TXT — auto-chunked at 500 chars |
| 🏙️ **Single Collection** | All cities share one Qdrant collection — metadata-based filtering |
| 🌐 **Cairo Timezone** | All timestamps in `Africa/Cairo` — Egypt tourism focus |
| 👋 **Greeting Detection** | "Hi", "Hello", "مرحبا" → warm welcome, no vector search |
| 📎 **Source Citations** | Every answer includes document name, city, score, and excerpt |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Angular Frontend                           │
│          Chat UI + Conversation Sidebar + File Manager           │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼────────────────────────────────────┐
│                         .NET API                                 │
│          Authentication · User → Conversation Mapping            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼────────────────────────────────────┐
│                      FastAPI RAG Server                          │
│                                                                  │
│  ┌──────────────────────┐   ┌────────────────────────────────┐  │
│  │      Routes          │   │         Controllers             │  │
│  │  · Health (/)        │   │  · DataController — validation  │  │
│  │  · Data (/data)      │   │  · ProcessController — chunking │  │
│  │  · Chat (/nlp)       │   │  · NLPController — RAG engine   │  │
│  └──────────────────────┘   └────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────┐   ┌────────────────────────────────┐  │
│  │       Models         │   │          Stores                 │  │
│  │  · AssetModel        │   │  · OpenAIProvider (gpt-4o-mini)│  │
│  │  · ChunkModel        │   │  · OpenAIProvider (embeddings) │  │
│  │  · ConversationModel │   │  · QdrantDBProvider            │  │
│  └──────────────────────┘   └────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │   MongoDB    │  │   Qdrant Cloud │  │   OpenAI API       │  │
│  │   Atlas      │  │   vectors      │  │   generation + emb │  │
│  └──────────────┘  └────────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow**: `Angular UI ↔ .NET Auth ↔ FastAPI RAG ↔ OpenAI + Qdrant + MongoDB`

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [MongoDB Atlas](https://www.mongodb.com/atlas) (free tier works)
- [Qdrant Cloud](https://cloud.qdrant.io/) (free 1GB cluster)
- [OpenAI API key](https://platform.openai.com/api-keys)

### Installation

```bash
# Clone
git clone https://github.com/sultanitos1/full-rag
cd full-rag/src

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Edit `.env` with your keys:

```ini
OPENAI_API_KEY="sk-..."                    # Your OpenAI API key
MONGODB_URL="mongodb+srv://..."            # Your MongoDB Atlas URI
QDRANT_DB_URL="https://..."                # Your Qdrant cloud URL
QDRANT_DB_API_KEY="eyJ..."                 # Your Qdrant API key
```

### Run

```bash
uvicorn main:app --host 0.0.0.0 --port 5000
```

### Deploy on EC2

```bash
# ~/deploy.sh
git pull && pip install -r requirements.txt -q && sudo systemctl restart rag
```

---

## 📡 API Reference

### Health Check

```
GET /api/v1/
```

```json
{ "app_name": "Mini RAG", "app_version": "0.1.0" }
```

---

### 💬 Conversations

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/nlp/conversation` | Create new chat session |
| `GET`  | `/api/v1/nlp/conversation/{id}` | Get full history |
| `GET`  | `/api/v1/nlp/conversations?ids=a,b,c` | List titles for sidebar |

**POST /api/v1/nlp/conversation**
```json
// Response
{ "conversation_id": "a1b2c3d4e5f6a7b8c9d0e1f2" }
```

**GET /api/v1/nlp/conversation/a1b2c3d4e5f6a7b8c9d0e1f2**
```json
{
  "conversation_id": "a1b2c3d4e5f6a7b8c9d0e1f2",
  "history": [
    { "role": "user", "content": "What hotels are in Cairo?" },
    { "role": "assistant", "content": "Cairo has many hotels..." }
  ],
  "created_at": "2026-06-16T03:09:55+02:00",
  "updated_at": "2026-06-16T03:09:55+02:00"
}
```

---

### 🤖 Chat

```
POST /api/v1/nlp/chat
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | `string` | ✅ | — | User's question |
| `conversation_id` | `string` | ❌ | `null` | Existing conversation to continue |
| `limit` | `int` | ❌ | `5` | Max sources to retrieve |

```json
{
  "text": "What hotels are in Luxor?",
  "conversation_id": "a1b2c3d4e5f6a7b8c9d0e1f2",
  "limit": 5
}
```

**Response:**
```json
{
  "signal": "chat_success",
  "message": "Here's what I found based on the available documents.",
  "answer": "Luxor has several highly-rated hotels including the Sofitel Winter Palace Luxor, a historic hotel on the Nile celebrating its 100th anniversary.",
  "sources": [
    {
      "document_name": "luxor_hotels_guide.pdf",
      "city": "unknown",
      "doc_type": "general",
      "score": 0.8921,
      "excerpt": "Sofitel Winter Palace Luxor is a 5-star hotel..."
    }
  ]
}
```

---

### 📁 File Management

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/data/multi-upload` | Upload multiple files (batch) |
| `GET`  | `/api/v1/data/files` | List all uploaded files |
| `PUT`  | `/api/v1/data/file/{file_id}` | Replace a file + re-index |
| `DELETE` | `/api/v1/data/file/{file_id}` | Delete file, chunks, and vectors |

**POST /api/v1/data/multi-upload**

Multipart form:
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `files` | `UploadFile[]` | ✅ | — | PDF, DOCX, CSV, or TXT files |
| `chunk_size` | `int` | ❌ | `500` | Characters per chunk |
| `overlap_size` | `int` | ❌ | `20` | Chunk overlap characters |

```json
// Response
{
  "signal": "multi_upload_success",
  "total": 3,
  "succeeded": 3,
  "failed": 0,
  "results": [
    { "file_name": "luxor_hotels.pdf", "status": "success", "file_id": "abc...", "inserted_chunks": 12 }
  ]
}
```

---

## ⚙️ Configuration

All configuration is via `.env`. See [`.env.example`](src/.env.example) for a template.

### Required Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `MONGODB_URL` | MongoDB Atlas connection string |
| `QDRANT_DB_URL` | Qdrant cloud URL |
| `QDRANT_DB_API_KEY` | Qdrant API key |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GENERATION_MODEL_ID` | `gpt-4o-mini` | Model for answer generation |
| `EMBEDDING_MODEL_ID` | `text-embedding-3-small` | Model for embeddings |
| `EMBEDDING_MODEL_SIZE` | `1536` | Embedding dimension |
| `SCORE_THRESHOLD` | `0.4` | Minimum vector search score |
| `INPUT_DEFAULT_MAX_CHARACTERS` | `4096` | Max input chars to LLM |
| `GENERATION_DEFAULT_MAX_TOKENS` | `500` | Max output tokens |
| `GENERATION_DEFAULT_TEMPERATURE` | `0.1` | LLM temperature |
| `VECTOR_DB_COLLECTION_NAME` | `tourism_knowledge_base` | Qdrant collection name |
| `DISTANCE_METHOD` | `cosine` | Vector distance metric |
| `FILE_MAX_SIZE` | `10` | Max file size in MB |
| `PRIMARY_LANG` | `en` | Prompt language |
| `DEFAULT_CITY` | `unknown` | Default city for uploads |
| `DEFAULT_DOC_TYPE` | `general` | Default doc type for uploads |

---

## 📂 Project Structure

```
src/
├── main.py                       # FastAPI entry point
├── .env.example                  # Configuration template
│
├── routes/                       # HTTP layer
│   ├── base.py                   # GET /api/v1/ — health check
│   ├── data.py                   # File upload/list/update/delete
│   └── nlp.py                    # Conversation CRUD + chat
│
├── controllers/                  # Business logic
│   ├── BaseController.py         # Shared base
│   ├── DataController.py         # File validation
│   ├── ProcessController.py      # Document loading & chunking
│   └── NLPController.py          # RAG engine (chat, search, index)
│
├── models/                       # MongoDB data access
│   ├── AssetModel.py             # File metadata CRUD
│   ├── ChunkModel.py             # Text chunk CRUD
│   ├── ConversationModel.py      # Chat history CRUD
│   └── db_schemes/               # Pydantic schemas
│
├── stores/                       # External service abstractions
│   ├── llm/                      # OpenAI provider + prompt templates
│   └── vectordb/                 # Qdrant provider
│
├── helpers/config.py             # Settings loader from .env
└── assets/files/                 # Uploaded files on disk
```

For a complete deep-dive into every file, function, and endpoint, see [**ARCHITECTURE.md**](ARCHITECTURE.md).

---

## 🔄 Chat Flow

```
User: "What hotels are in Luxor?"
        │
        ▼
  1. Load conversation history from MongoDB
        │
        ▼
  2. Is it a greeting? ─── Yes → Warm welcome (skip search)
        │ No
        ▼
  3. Rewrite query with last 5 turns of context
     "What hotels are in Luxor?" → "What hotels are in Luxor?"
        │
        ▼
  4. Embed → Qdrant search → filter by score ≥ 0.4
        │
        ▼
  5. Send docs + last 5 turns to GPT-4o-mini
        │
        ▼
  6. Save Q&A to MongoDB
        │
        ▼
  7. Return { answer, sources }
```

**Why this works better than a naive RAG:**
- 🔄 **Query rewriting** handles follow-ups naturally ("what about there?" → "hotels in Luxor")
- 🧹 **History truncation** keeps latency predictable as conversations grow
- 📏 **Budget trimming** prevents silent prompt truncation by the LLM
- 🗄️ **Persistent MongoDB history** survives server restarts

---

## 🛠️ Tech Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Framework** | FastAPI (Python) | Async API server |
| **LLM** | OpenAI gpt-4o-mini | Answer generation |
| **Embeddings** | OpenAI text-embedding-3-small | Vector embeddings (1536d) |
| **Vector DB** | Qdrant Cloud | Similarity search |
| **Database** | MongoDB Atlas | Conversation history, assets, chunks |
| **Frontend** | Angular 17 | Chat UI |
| **Middleware** | .NET 8 | Authentication, user mapping |
| **Deployment** | Ubuntu EC2 + systemd | Production server |
| **File parsing** | LangChain (PyMuPDF, etc.) | PDF/DOCX/CSV/TXT loading |

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [`README.md`](README.md) | This file — quick start + overview |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Complete architecture — every file, endpoint, function explained |
| [`CODEBASE_CONSCIOUSNESS.md`](CODEBASE_CONSCIOUSNESS.md) | Internal dev reference — bugs, dead code, recent changes |

---

## 🤝 Contributing

This is a graduation project. Contributions, issues, and feature requests are welcome!

---

## 📄 License

[MIT](LICENSE)

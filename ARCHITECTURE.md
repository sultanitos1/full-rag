# Full RAG — Architecture Documentation

> Complete reference: every file, directory, endpoint, and function — what they do and why they exist.

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Directory Tree](#2-directory-tree)
3. [Entry Point — `main.py`](#3-entry-point---mainpy)
4. [Configuration — `config.py` + `.env`](#4-configuration)
5. [Routes — API Layer](#5-routes)
   - 5.1 [`base.py`](#51-basepy) — Health Check
   - 5.2 [`data.py`](#52-datapy) — File Management
   - 5.3 [`nlp.py`](#53-nlppy) — Chat & Conversations
   - 5.4 [`schemes/nlp.py`](#54-schemesnlppy) — Request Schemas
6. [Controllers — Business Logic](#6-controllers)
   - 6.1 [`BaseController.py`](#61-basecontrollerpy)
   - 6.2 [`DataController.py`](#62-datacontrollerpy)
   - 6.3 [`ProcessController.py`](#63-processcontrollerpy)
   - 6.4 [`NLPController.py`](#64-nlpcontrollerpy)
7. [Models — Data Access Layer](#7-models)
   - 7.1 [`BaseDataModel.py`](#71-basedatamodelpy)
   - 7.2 [`AssetModel.py`](#72-assetmodelpy)
   - 7.3 [`ChunkModel.py`](#73-chunkmodelpy)
   - 7.4 [`ConversationModel.py`](#74-conversationmodelpy)
   - 7.5 [`db_schemes/`](#75-db_schemes)
   - 7.6 [`enums/`](#76-enums)
8. [Stores — External Services](#8-stores)
   - 8.1 [LLM Store](#81-llm-store)
   - 8.2 [Vector DB Store](#82-vector-db-store)
   - 8.3 [Template Parser](#83-template-parser)
9. [Deployment](#9-deployment)
10. [Known Issues](#10-known-issues)

---

## 1. System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Angular Frontend                          │
│  (Chat UI — renders bubbles, manages conversation sidebar)       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────────┐
│                         .NET API                                 │
│  (Authentication, User → Conversation mapping, Session mgmt)     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────────┐
│                      FastAPI RAG Server                          │
│                      (port 5000, systemd)                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Routes (HTTP Layer)                                      │   │
│  │  base.py  |  data.py  |  nlp.py                           │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │  Controllers (Business Logic)                             │   │
│  │  DataController | ProcessController | NLPController      │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                         │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │  Models (MongoDB Access)     │  Stores (External APIs)    │   │
│  │  AssetModel                  │  OpenAIProvider            │   │
│  │  ChunkModel                  │  QdrantDBProvider          │   │
│  │  ConversationModel           │  TemplateParser            │   │
│  └──────────────────────────────┴───────────────────────────┘   │
│                                                                  │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│  │   MongoDB     │  │   Qdrant Cloud │  │   OpenAI API     │   │
│  │   Atlas       │  │   Vector Store │  │   gpt-4o-mini    │   │
│  │               │  │                │  │   embeddings     │   │
│  └───────────────┘  └────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

| Layer | Why It Exists |
|-------|---------------|
| **Angular → .NET** | .NET handles user authentication, session management, and maps users to `conversation_id`s. RAG doesn't need to know about users. |
| **RAG is stateless between conversations** | Each chat request is self-contained via `conversation_id`. The server can be horizontally scaled behind a load balancer. |
| **MongoDB for history** | Persists conversation history across server restarts. Works with .NET's multi-user architecture. |
| **Qdrant Cloud** | Managed vector database — no infrastructure to maintain. Single collection with metadata filtering. |
| **Factory Pattern for stores** | External services (LLM, Vector DB) use abstract interfaces + factories. Swapping providers requires zero changes to controllers or routes. |

---

## 2. Directory Tree

```
mini-rag/
│
├── ARCHITECTURE.md              ← This file — full architecture reference
├── README.md                    ← GitHub front page — quick start + badges
├── CHANGELOG.md                 ← Release history
├── CODEBASE_CONSCIOUSNESS.md    ← Internal dev reference (known bugs, dead code)
├── DOCUMENTATION.md             ← Legacy documentation (outdated)
├── LICENSE                      ← MIT license
├── mini-rag.postman_collection.json ← Postman collection for API testing
│
└── src/
    ├── main.py                  ← FastAPI entry point — app startup/shutdown
    ├── .env                     ← ALL configuration (gitignored — API keys here)
    ├── .env.example             ← Template with placeholder values
    ├── .gitignore               ← Ignores __pycache__, .env, assets/files/, logs
    ├── drop_collections.py      ← Dev utility: drops MongoDB chunks + assets collections
    ├── requirements.txt         ← Python dependencies with versions
    │
    ├── helpers/
    │   ├── __init__.py          ← Empty
    │   └── config.py            ← pydantic-settings Settings class — reads .env
    │
    ├── controllers/             ← Business logic (no HTTP knowledge)
    │   ├── __init__.py          ← Exports: DataController, ProcessController, NLPController
    │   ├── BaseController.py    ← Shared base: file paths, random strings
    │   ├── DataController.py    ← File validation, unique naming
    │   ├── ProcessController.py ← Document loading, text chunking
    │   └── NLPController.py     ← Chat, search, embedding, indexing, deletion
    │
    ├── models/                  ← MongoDB data access (CRUD)
    │   ├── __init__.py          ← Exports: ResponseSignal, ProcessingEnum, ConversationModel
    │   ├── BaseDataModel.py     ← Shared base: db_client + settings
    │   ├── AssetModel.py        ← CRUD for "assets" collection
    │   ├── ChunkModel.py        ← CRUD for "chunks" collection
    │   ├── ConversationModel.py ← CRUD for "conversations" collection
    │   ├── db_schemes/          ← Pydantic schemas (data validation)
    │   │   ├── __init__.py      ← Exports: Asset, Conversation, DataChunk, RetrievedDocument
    │   │   ├── asset.py         ← Asset schema — file metadata
    │   │   ├── conversation.py  ← Conversation schema — chat history
    │   │   └── data_chunk.py    ← DataChunk + RetrievedDocument schemas
    │   └── enums/               ← Shared constants
    │       ├── __init__.py      ← Empty
    │       ├── AssetTypeEnum.py ← FILE = "file"
    │       ├── DataBaseEnum.py  ← MongoDB collection names
    │       ├── ProcessingEnum.py← File extensions (.txt, .pdf, .csv, .docx)
    │       └── ResponseEnums.py ← API response signal strings
    │
    ├── routes/                  ← HTTP endpoints (no business logic)
    │   ├── __init__.py          ← Empty
    │   ├── base.py              ← GET /api/v1/ — health check
    │   ├── data.py              ← File upload/list/update/delete endpoints
    │   ├── nlp.py               ← Conversation CRUD + chat endpoint
    │   └── schemes/
    │       ├── __init__.py      ← Empty
    │       └── nlp.py           ← ChatRequest Pydantic schema
    │
    ├── stores/                  ← External service abstractions
    │   ├── llm/                 ← LLM (OpenAI) — generation + embedding
    │   │   ├── __init__.py      ← Empty
    │   │   ├── LLMEnums.py      ← Enums: OPENAI, OpenAIEnums, DocumentTypeEnum
    │   │   ├── LLMInterface.py  ← Abstract base class for LLM providers
    │   │   ├── LLMProviderFactory.py ← Factory → returns OpenAIProvider
    │   │   ├── providers/
    │   │   │   ├── __init__.py  ← Exports: OpenAIProvider
    │   │   │   └── OpenAIProvider.py ← OpenAI client — generate_text, embed_text
    │   │   └── templates/
    │   │       ├── __init__.py      ← Empty
    │   │       ├── template_parser.py ← Dynamic prompt template loader
    │   │       └── locales/
    │   │           ├── __init__.py  ← Empty
    │   │           ├── en/rag.py    ← English prompt templates
    │   │           ├── en/__init__.py ← Empty
    │   │           ├── ar/rag.py    ← Arabic prompt templates
    │   │           └── ar/__init__.py ← Empty
    │   │
    │   └── vectordb/            ← Vector DB (Qdrant)
    │       ├── __init__.py      ← Empty
    │       ├── VectorDBEnums.py ← QDRANT, DistanceMethodEnums (COSINE, DOT)
    │       ├── VectorDBInterface.py ← Abstract base class
    │       ├── VectorDBProviderFactory.py ← Factory → returns QdrantDBProvider
    │       └── providers/
    │           ├── __init__.py  ← Exports: QdrantDBProvider
    │           └── QdrantDBProvider.py  ← Qdrant client — search, insert, delete
    │
    ├── assets/files/            ← Uploaded files on disk (gitignored)
    └── tests/                   ← Manual test payloads + scripts
        ├── test_cairo.json      ← Chat request: "What hotels in Cairo?"
        ├── test_arabic.json     ← Chat request in Arabic
        ├── test_france.json     ← Chat request: France query
        ├── test_greeting.json   ← Greeting test
        ├── test_empty.json      ← Empty query test
        ├── test_fallback.json   ← Fallback test (no results)
        ├── test_multi.json      ← Multi-file test
        ├── check_chunks.py      ← Script: inspect MongoDB chunks
        ├── check_qdrant.py      ← Script: inspect Qdrant vectors
        └── check_qdrant2.py     ← Script: alternative Qdrant inspection
```

---

## 3. Entry Point — `main.py`

**File**: `src/main.py`

**Purpose**: Creates and configures the FastAPI application. All global dependencies are initialized here.

**Why this exists**: Centralizes all startup/sutdown logic in one place. Routes don't create their own clients — they access them via `request.app`.

### Startup Sequence

| Step | Code | What Happens | Why |
|------|------|-------------|-----|
| 1 | `settings = get_settings()` | Reads `.env` into a `Settings` object | All config in one place, validated at startup |
| 2 | `AsyncIOMotorClient(settings.MONGODB_URL)` | Connects to MongoDB Atlas | Async driver — non-blocking DB operations |
| 3 | `LLMProviderFactory(settings).create("OPENAI")` | Creates `OpenAIProvider` for **generation** | `gpt-4o-mini` for answer generation |
| 4 | Same factory, same provider | Creates `OpenAIProvider` for **embedding** | `text-embedding-3-small` for vector embeddings |
| 5 | `VectorDBProviderFactory(settings).create("QDRANT")` | Creates + connects `QdrantDBProvider` | Vector similarity search |
| 6 | `TemplateParser(language="en")` | Loads prompt templates from `locales/en/` | Multilingual prompts with fallback |

### Global State Attached to `app`

These are accessed by routes via `request.app`:

```python
app.mongo_conn          # AsyncIOMotorClient — MongoDB connection
app.db_client           # Database — MongoDB database handle
app.generation_client   # OpenAIProvider — text generation (gpt-4o-mini)
app.embedding_client    # OpenAIProvider — text embedding (text-embedding-3-small, 1536d)
app.vectordb_client     # QdrantDBProvider — vector search/insert/delete
app.template_parser     # TemplateParser — loads prompt files by language
```

### CORS

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

All origins allowed — the Angular frontend and .NET intermediary can be on any domain.

### Shutdown

```python
app.mongo_conn.close()      # Close MongoDB connection
app.vectordb_client.disconnect()  # Disconnect Qdrant
```

---

## 4. Configuration

### `helpers/config.py`

**File**: `src/helpers/config.py`

**Purpose**: Defines the `Settings` class using `pydantic-settings`. Reads all values from `.env`.

**Why it exists**:
- Single source of truth for all configuration
- Type validation at startup (a missing API key fails fast, not at runtime)
- Default values for optional settings
- Environment variable override support

### `.env` Reference

| Variable | Required | Default | Used By | Description |
|----------|----------|---------|---------|-------------|
| `APP_NAME` | Yes | — | `base.py` | API health response |
| `APP_VERSION` | Yes | — | `base.py` | API version string |
| `FILE_ALLOWED_TYPES` | Yes | — | `DataController` | Allowed MIME types for upload |
| `FILE_ALLOWED_EXTENSIONS` | No | `[".txt",".pdf",".csv",".docx"]` | `DataController` | Allowed file extensions |
| `FILE_MAX_SIZE` | Yes | — | `DataController` | Max file size in MB |
| `FILE_DEFAULT_CHUNK_SIZE` | Yes | — | `main.py` (unused directly) | Chunk size for reading uploads |
| `VECTOR_DB_COLLECTION_NAME` | No | `"tourism_knowledge_base"` | `NLPController` | Qdrant collection name |
| `DEFAULT_CITY` | No | `"unknown"` | `data.py` | Default city for new uploads |
| `DEFAULT_DOC_TYPE` | No | `"general"` | `data.py` | Default doc type for new uploads |
| `MONGODB_URL` | Yes | — | `main.py` | MongoDB Atlas connection string |
| `MONGODB_DATABASE` | Yes | — | `main.py` | MongoDB database name |
| `GENERATION_BACKEND` | Yes | — | `main.py` | LLM provider for generation (`OPENAI`) |
| `EMBEDDING_BACKEND` | Yes | — | `main.py` | LLM provider for embeddings (`OPENAI`) |
| `OPENAI_API_KEY` | Yes | — | `OpenAIProvider` | OpenAI API key |
| `OPENAI_API_URL` | No | `https://api.openai.com/v1` | `OpenAIProvider` | OpenAI-compatible endpoint |
| `GENERATION_MODEL_ID` | No | `gpt-4o-mini` | `OpenAIProvider` | Model for text generation |
| `EMBEDDING_MODEL_ID` | No | `text-embedding-3-small` | `OpenAIProvider` | Model for embeddings |
| `EMBEDDING_MODEL_SIZE` | No | `1536` | `QdrantDBProvider` | Embedding vector dimension |
| `INPUT_DEFAULT_MAX_CHARACTERS` | No | `4096` | `OpenAIProvider` | Max input characters to LLM |
| `GENERATION_DEFAULT_MAX_TOKENS` | No | `500` | `OpenAIProvider` | Max output tokens |
| `GENERATION_DEFAULT_TEMPERATURE` | No | `0.1` | `OpenAIProvider` | LLM temperature |
| `SCORE_THRESHOLD` | No | `0.4` | `NLPController` | Minimum vector search score |
| `VECTOR_DB_BACKEND` | Yes | — | `main.py` | Vector DB provider (`QDRANT`) |
| `QDRANT_DB_URL` | Yes | — | `QdrantDBProvider` | Qdrant cloud URL |
| `QDRANT_DB_API_KEY` | Yes | — | `QdrantDBProvider` | Qdrant API key |
| `DISTANCE_METHOD` | No | `cosine` | `QdrantDBProvider` | Vector distance metric |
| `PRIMARY_LANG` | No | `"en"` | `TemplateParser` | Prompt language |
| `DEFAULT_LANG` | No | `"en"` | `TemplateParser` | Fallback language |

---

## 5. Routes

### 5.1 `base.py`

**File**: `src/routes/base.py`

**Purpose**: Health check endpoint. Returns app name and version.

**Why it exists**: .NET and monitoring tools need a lightweight endpoint to verify the RAG server is alive and responding.

| Endpoint | Method | Function | Returns |
|----------|--------|----------|---------|
| `/api/v1/` | GET | `welcome()` | `{app_name, app_version}` |

**Code**:
```python
@base_router.get("/")
async def welcome(app_settings: Settings = Depends(get_settings)):
    return {"app_name": app_settings.APP_NAME, "app_version": app_settings.APP_VERSION}
```

---

### 5.2 `data.py`

**File**: `src/routes/data.py`

**Purpose**: File management — upload, list, update, delete files and their chunks/vectors.

**Why it exists**: Admins need to upload tourism documents. The system needs to ingest files → chunk → embed → index. These endpoints expose that pipeline.

#### Endpoints

| Method | Path | Function | Purpose | Request | Response |
|--------|------|----------|---------|---------|----------|
| **POST** | `/api/v1/data/multi-upload` | `upload_multiple_files()` | Batch upload files | `files: UploadFile[]`, `chunk_size`, `overlap_size` | `{signal, total, succeeded, failed, results[]}` |
| **GET** | `/api/v1/data/files` | `list_files()` | List all uploaded files | — | `{assets: [{file_id, asset_name, file_size, uploaded_at}]}` |
| **PUT** | `/api/v1/data/file/{file_id}` | `update_file()` | Replace a file + re-index | `file: UploadFile`, `chunk_size`, `overlap_size` | `{signal, file_id, inserted_chunks}` |
| **DELETE** | `/api/v1/data/file/{file_id}` | `delete_file()` | Delete file + chunks + vectors | — | `{signal}` |

#### `POST /api/v1/data/multi-upload` — Detailed Flow

```
For each file:
  1. validate MIME type, extension, size → fail with signal if invalid
  2. generate unique filename (12 random chars + cleaned original name)
  3. save file to disk (assets/files/{unique_name})
  4. create Asset record in MongoDB {type, name, size, config: {city: "unknown", doc_type: "general"}}
  5. load file content via ProcessController (LangChain loader)
  6. chunk text via RecursiveCharacterTextSplitter (500 chars, 20 overlap)
  7. attach metadata {city, doc_type, asset_id} to each chunk
  8. insert all chunks into MongoDB "chunks" collection (bulk_write, batch=100)
  9. index all chunks into Qdrant (embed each → insert vectors)
  10. return per-file success/fail
```

**Why batch upload?** Admins upload many files at once. Processing them in parallel would overwhelm the embedding API — sequential per-file with batch feedback is safer.

#### `GET /api/v1/data/files` — Detailed Flow

```
  1. query MongoDB "assets" collection (projection: _id, asset_name, asset_size, asset_pushed_at)
  2. sort by asset_pushed_at descending
  3. convert timestamps from UTC to Africa/Cairo timezone
  4. return list
```

**Why Cairo timezone?** All tourism data is Egypt-focused. Upload timestamps should reflect the admin's local time.

#### `PUT /api/v1/data/file/{file_id}` — Detailed Flow

```
  1. look up existing asset by file_id → 404 if not found
  2. save new file to disk (overwrites old — same filename)
  3. update asset record (size, timestamp)
  4. delete old chunks from MongoDB (queries chunk_metadata.asset_id)
  5. delete old vectors from Qdrant (queries metadata.asset_id)
  6. load + chunk new file
  7. insert new chunks to MongoDB
  8. index new chunks to Qdrant
  9. return success with chunk count
```

**Why this exists:** Admins need to update tourism documents (e.g., correcting prices or hours). Rather than delete + re-upload, PUT handles the full cycle.

#### `DELETE /api/v1/data/file/{file_id}` — Detailed Flow

```
  1. delete asset from MongoDB
  2. delete chunks from MongoDB (by asset_id)
  3. delete vectors from Qdrant (by asset_id)
  4. return success
```

---

### 5.3 `nlp.py`

**File**: `src/routes/nlp.py`

**Purpose**: Conversation management and chat.

**Why it exists**: The core user-facing API. Separating chat from data management keeps concerns clean — data routes are admin-only, nlp routes are user-facing.

#### Endpoints

| Method | Path | Function | Purpose | Request | Response |
|--------|------|----------|---------|---------|----------|
| **POST** | `/api/v1/nlp/conversation` | `create_conversation()` | Create new chat session | — | `{conversation_id}` |
| **GET** | `/api/v1/nlp/conversation/{id}` | `get_conversation()` | Load full history | — | `{conversation_id, history[], created_at, updated_at}` |
| **GET** | `/api/v1/nlp/conversations` | `list_conversations()` | List sidebar titles | `?ids=a,b,c` | `{conversations: [{conversation_id, title, updated_at}]}` |
| **POST** | `/api/v1/nlp/chat` | `chat_endpoint()` | Send message, get answer | `{text, conversation_id?, limit?}` | `{signal, answer, sources[]}` |

#### `POST /api/v1/nlp/conversation` — Detailed Flow

```
  1. generate UUID hex (32 chars) as conversation ID
  2. create MongoDB document:
     {_id: "abc...", title: "", history: [], created_at: now(Cairo), updated_at: now(Cairo)}
  3. return {conversation_id: "abc..."}
```

**Why a separate endpoint?** The frontend creates a conversation once per chat session. The ID is reused for all subsequent messages. This separates "starting a chat" from "sending a message."

#### `GET /api/v1/nlp/conversation/{id}` — Detailed Flow

```
  1. query MongoDB by _id → 404 if not found
  2. convert timestamps from UTC to Africa/Cairo
  3. return full conversation (history, timestamps)
```

**Why the frontend needs this**: When a user taps a chat in the sidebar, the frontend needs to load all past messages to render the conversation UI.

#### `GET /api/v1/nlp/conversations?ids=a,b,c` — Detailed Flow

```
  1. parse comma-separated IDs
  2. query MongoDB: find all matching _ids
  3. project only _id, title, updated_at (no history — too large)
  4. sort by updated_at descending
  5. convert timestamps to Cairo
  6. return list
```

**Why light projection?** The sidebar only needs titles and timestamps. Loading full histories would be wasteful and slow.

#### `POST /api/v1/nlp/chat` — Detailed Flow

```
  1. validate text is non-empty → 400 INVALID_QUERY if empty
  2. load prior_history from MongoDB by conversation_id (if provided)
  3. if greeting → skip retrieval, generate answer directly, save turn, return
  4. call NLPController.chat(query, limit, history):
     a. rewrite_query() → GPT rewrites "what about hotels?" → "hotels in Cairo"
     b. embed rewritten query → vector[1536]
     c. search Qdrant (cosine, top_k=limit)
     d. filter by score >= SCORE_THRESHOLD (0.2)
     e. return RetrievedDocument[] or None
  5. if no results → fallback answer, save turn, return
  6. build sources array from results (doc name, city, score, excerpt)
  7. call generate_chat_answer(query, docs, history):
     a. build document prompts from templates
     b. budget-trim documents to fit INPUT_DEFAULT_MAX_CHARACTERS
     c. construct chat history (system + last 5 turns + docs + footer)
     d. call gpt-4o-mini → get answer
     e. return answer
  8. append user + assistant turn to MongoDB conversation
  9. return {signal, answer, sources}
```

**Why this flow?**
- **Query rewriting** resolves follow-up questions into standalone search queries (e.g., "what about there?" → "hotels in Luxor")
- **Greeting detection** avoids unnecessary vector search overhead for simple greetings
- **History truncation** (5 turns) keeps latency predictable as conversations grow
- **Budget trimming** prevents prompt truncation by the LLM — we control document length before sending

---

### 5.4 `schemes/nlp.py`

**File**: `src/routes/schemes/nlp.py`

**Purpose**: Pydantic request schemas for request validation.

**Why it exists**: FastAPI automatically validates request bodies against these schemas, returning clear 422 errors for invalid input.

```python
class ChatRequest(BaseModel):
    text: str                                           # User's question (required, non-empty)
    limit: Optional[int] = 5                            # Max sources to retrieve
    conversation_id: Optional[str] = None               # Existing conversation to continue
```

---

## 6. Controllers

### 6.1 `BaseController.py`

**File**: `src/controllers/BaseController.py`

**Purpose**: Base class for all controllers. Provides shared utilities.

**Why it exists**: DRY — every controller needs `app_settings` and `files_dir`. Extracting these to a base avoids duplication.

```python
class BaseController:
    def __init__(self):
        self.app_settings = get_settings()           # All .env config
        self.base_dir = os.path.dirname(src/)        # Project root
        self.files_dir = os.path.join(self.base_dir, "assets/files")  # Upload path

    def generate_random_string(self, length=12) -> str:
        # Random alphanumeric string — used for unique filenames
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
```

---

### 6.2 `DataController.py`

**File**: `src/controllers/DataController.py`

**Purpose**: File validation and unique filename generation.

**Why it exists**: Separates file-handling logic from route handlers. Routes stay thin — validation logic is testable in isolation.

```python
class DataController(BaseController):
    def validate_uploaded_file(self, file: UploadFile) -> (bool, str):
        # Check: content type in allowed list → extension in allowed list → size < max
        # Returns (True, FILE_VALIDATED_SUCCESS) or (False, error_signal)
```

**Why validation**: Prevents malicious uploads (e.g., .exe files), enforces size limits (prevents OOM), gives clear error messages.

```python
    def generate_unique_filepath(self, orig_file_name: str) -> (str, str):
        # Creates: assets/files/{random_12chars}_{cleaned_name}
        # Handles collisions (rare, but loop checks)
```

**Why unique names**: Two users could upload `cairo_hotels.pdf` — unique prefix prevents collisions without confusing the user (original name is preserved in the filename).

```python
    def get_clean_file_name(self, orig_file_name: str) -> str:
        # Remove special characters, replace spaces with underscore
```

**Why cleanup**: Prevents path traversal attacks (e.g., `../../../etc/passwd`) and filesystem issues with special characters.

---

### 6.3 `ProcessController.py`

**File**: `src/controllers/ProcessController.py`

**Purpose**: Loads files from disk, extracts text, splits into chunks.

**Why it exists**: File processing is complex — different loaders for different formats, configurable chunk sizes. Encapsulating this keeps routes clean.

```python
class ProcessController(BaseController):
    def get_file_loader(self, file_id: str):
        # Returns: TextLoader(.txt), PyMuPDFLoader(.pdf), CSVLoader(.csv), Docx2txtLoader(.docx)
```

**Why LangChain loaders**: LangChain provides battle-tested document loaders for all common formats. No need to write PDF parsing from scratch.

```python
    def get_file_content(self, file_id: str) -> list[Document] or None:
        # Loads file using the correct loader, returns list of Document(page_content, metadata)

    def process_file_content(self, file_content, file_id, chunk_size=500, overlap_size=20, metadata=None) -> list[Document]:
        # Uses RecursiveCharacterTextSplitter: chunk_size=500, overlap=20
        # Attaches metadata {city, doc_type, asset_id} to each chunk
```

**Why 500 characters with 20 overlap**:
- Designed to match the user's PDF structure (each chunk fits one tourism item)
- 20 chars overlap ensures no sentences are cut off at boundaries
- RecursiveCharacterTextSplitter tries to split on paragraph → sentence → word boundaries, maintaining readability

---

### 6.4 `NLPController.py`

**File**: `src/controllers/NLPController.py`

**Purpose**: The core RAG engine — chat, search, embedding, indexing, deletion.

**Why it exists**: This is the brain of the application. All LLM interaction, vector search logic, and prompt construction lives here.

```python
MAX_HISTORY_TURNS = 5  # Keep last 5 user+assistant pairs for context
```

**Why 5 turns**: Balances context awareness (enough to resolve follow-up questions) with latency (10 messages × ~200 tokens each = ~2000 tokens, processed in < 1s by gpt-4o-mini).

#### Methods

| Method | Purpose | Why It Exists |
|--------|---------|---------------|
| `rewrite_query(query, history)` | Rewrites follow-up into standalone query using GPT | Resolves "what about there?" → "hotels in Luxor" |
| `is_greeting_query(query)` | Checks if query is a pure greeting | Skips expensive vector search for "hello" |
| `chat(query, limit, history)` | Full search pipeline: rewrite → embed → search → filter | Main search method used by the chat endpoint |
| `generate_chat_answer(query, docs, history, system_prompt)` | Generates LLM answer from retrieved docs | Constructs prompt, calls GPT, handles fallback |
| `index_chunks(chunks)` | Embeds + indexes chunks into Qdrant | Converts text → vectors → Qdrant points |
| `delete_file_vectors(asset_id)` | Deletes Qdrant points by asset_id | Cleanup when files are deleted or updated |

#### `rewrite_query()` — Detailed

```python
def rewrite_query(self, query: str, history: list) -> str:
    if not history:
        return query  # No history = no rewriting needed

    # Take last 5 turns (10 messages) for context
    context = format_history(history[-MAX_HISTORY_TURNS*2:])

    prompt = f"""
    You are a search query rewriter. Given the conversation history
    and the latest user query, rewrite the latest query as a standalone,
    detailed search query. Return ONLY the rewritten query, nothing else.

    Conversation:
    {context}

    Latest query: {query}

    Standalone query:
    """

    rewritten = self.generation_client.generate_text(prompt=prompt, ...)
    return (rewritten or query).strip()
```

**Why GPT-based rewriting instead of regex?** Natural language follow-ups are too varied for rules. "What about there?" needs to understand "there" refers to "Luxor" from 3 turns ago. Only an LLM can do this reliably.

#### `chat()` — Detailed

```python
def chat(self, query: str, limit: int = 5, prior_history: list = None):
    search_query = self.rewrite_query(query, prior_history)
    vector = self.embedding_client.embed_text(text=search_query, document_type=DocumentTypeEnum.QUERY)
    results = self.vectordb_client.search_by_vector(
        collection_name=self.collection_name,
        vector=vector,
        limit=limit,
    )
    results = [doc for doc in results if doc.score >= self.score_threshold]
    return results or None
```

**Why separate from `generate_chat_answer()`?** Separation of concerns — search and generation are independent steps. The search step can be cached, and the generation step can be tested with mock documents.

#### `generate_chat_answer()` — Detailed

```python
def generate_chat_answer(self, query, retrieved_documents, prior_history=None, system_prompt=None):
    # 1. Build chat history with system prompt
    chat_history = [construct_prompt(system_prompt, SYSTEM)]

    # 2. Add last 5 turns of conversation history
    if prior_history:
        for msg in prior_history[-MAX_HISTORY_TURNS*2:]:
            chat_history.append(construct_prompt(msg.content, role))

    # 3. Build document prompts with budget trimming
    doc_budget = max_input_chars - len(footer)
    documents_prompts = ""
    for doc in retrieved_documents:
        doc_prompt = template_parser.get("rag", "document_prompt", {...})
        if len(documents_prompts) + len(doc_prompt) > doc_budget:
            break  # Trim to fit budget
        documents_prompts += doc_prompt

    # 4. Assemble full prompt and send to GPT
    full_prompt = documents_prompts + footer_prompt
    answer = self.generation_client.generate_text(prompt=full_prompt, chat_history=chat_history)
    return answer, full_prompt, chat_history
```

**Why budget trimming?** GPT has a max context window. If documents + history + footer exceed that, GPT silently truncates from the beginning. By trimming documents first, we ensure the footer (with the actual question) is always included.

#### `index_chunks()` — Detailed

```python
def index_chunks(self, chunks: list):
    texts = [c.chunk_text for c in chunks]
    metadata = [dict(c.chunk_metadata) for c in chunks]

    # Get starting ID from existing collection
    collection_info = self.vectordb_client.get_collection_info(...)
    base_id = collection_info.points_count

    # Embed each chunk (sequential)
    vectors = [self.embedding_client.embed_text(text=text, document_type=DOCUMENT)
               for text in texts]

    # Ensure collection exists, then insert
    self.vectordb_client.create_collection(...)
    self.vectordb_client.insert_many(texts=texts, vectors=vectors, metadata=metadata, record_ids=...)
```

**Why sequential embedding instead of batch?** Known limitation — each chunk is embedded individually. OpenAI supports batch embedding (up to 2048 inputs per call) but this was deferred for the graduation project.

---

## 7. Models

### 7.1 `BaseDataModel.py`

**File**: `src/models/BaseDataModel.py`

**Purpose**: Base class for all MongoDB models.

**Why it exists**: Provides `db_client` and `app_settings` to all data models without code duplication.

```python
class BaseDataModel:
    def __init__(self, db_client: object):
        self.db_client = db_client
        self.app_settings = get_settings()
```

---

### 7.2 `AssetModel.py`

**File**: `src/models/AssetModel.py`

**Collection**: `"assets"` (in MongoDB)

**Purpose**: CRUD for file asset records — metadata about uploaded files.

**Why it exists**: The system needs to track which files exist, their sizes, upload times, and configuration (city, doc_type). This is the source of truth for file management.

| Method | Purpose |
|--------|---------|
| `create_asset(asset)` | Insert new asset → returns with `_id` |
| `get_asset_by_id(asset_id)` | Find by MongoDB `_id` → `Asset` or `None` |
| `delete_asset_by_id(asset_id)` | Delete by MongoDB `_id` → deleted count |

```python
# Schema stored in MongoDB:
{
  "_id": ObjectId("..."),
  "asset_type": "file",
  "asset_name": "a1b2c3d4e5f6_luxor_hotels.pdf",
  "asset_size": 245760,
  "asset_config": {"city": "luxor", "doc_type": "hotels"},
  "asset_pushed_at": ISODate("2026-06-16T01:09:55Z")
}
```

---

### 7.3 `ChunkModel.py`

**File**: `src/models/ChunkModel.py`

**Collection**: `"chunks"` (in MongoDB)

**Purpose**: CRUD for text chunks — the raw text extracted from documents.

**Why it exists**: Chunks are stored in MongoDB for:
- Debugging / inspecting what was extracted from a file
- Re-indexing into Qdrant (delete + re-insert without re-parsing the file)
- Deleting chunks when a file is removed

| Method | Purpose |
|--------|---------|
| `create_chunk(chunk)` | Insert single chunk (unused — kept for API completeness) |
| `insert_many_chunks(chunks, batch_size=100)` | Batch insert chunks into MongoDB |
| `delete_chunks_by_asset_id(asset_id)` | Delete all chunks for an asset (used on file delete/update) |

```python
# Schema stored in MongoDB:
{
  "_id": ObjectId("..."),
  "chunk_text": "The Luxor Temple is an ancient Egyptian temple...",
  "chunk_metadata": {"city": "luxor", "doc_type": "attractions", "asset_id": "abc123..."},
  "chunk_order": 1
}
```

---

### 7.4 `ConversationModel.py`

**File**: `src/models/ConversationModel.py`

**Collection**: `"conversations"` (in MongoDB)

**Purpose**: CRUD for chat conversations — history persistence.

**Why it exists**: Conversations need to persist across server restarts. The .NET layer maps users to conversation IDs using its own DB, and RAG stores the actual chat history.

| Method | Purpose |
|--------|---------|
| `create_conversation()` | Insert empty conversation → returns `Conversation` with `_id` |
| `get_conversation(id)` | Find by `_id` → full conversation with history |
| `append_turn(id, user_msg, assistant_msg)` | Set title (if empty) + push Q&A pair + update timestamp |
| `list_conversations(ids)` | Project `_id, title, updated_at` for multiple IDs → sorted by latest |

```python
# Schema stored in MongoDB:
{
  "_id": "a1b2c3d4e5f6a7b8c9d0e1f2",
  "title": "What hotels are in Cairo?",
  "history": [
    {"role": "user", "content": "What hotels are in Cairo?"},
    {"role": "assistant", "content": "Cairo has many hotels including..."}
  ],
  "created_at": ISODate("2026-06-16T01:09:55Z"),
  "updated_at": ISODate("2026-06-16T01:09:55Z")
}
```

**Why auto-title?** The first user message automatically becomes the conversation title. This gives the sidebar meaningful labels without any frontend work.

---

### 7.5 `db_schemes/`

**Directory**: `src/models/db_schemes/`

**Purpose**: Pydantic data validation schemas for MongoDB documents.

**Why it exists**: Pydantic validates data at the boundary between the application and MongoDB. Ensures malformed data doesn't enter the database.

#### `asset.py`

```python
class Asset(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    asset_type: str = Field(..., min_length=1)       # "file"
    asset_name: str = Field(..., min_length=1)       # Unique filename
    asset_size: int = Field(ge=0, default=None)      # Bytes
    asset_config: dict = Field(default=None)          # {city, doc_type}
    asset_pushed_at: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("Africa/Cairo")))
```

**Why `asset_config` is a dict instead of separate fields?** Flexible — if we want to add more metadata later (e.g., `language`, `author`), no schema migration needed.

#### `conversation.py`

```python
class Conversation(BaseModel):
    id: Optional[str] = Field(None, alias="_id")          # UUID hex string
    title: str = ""                                        # Auto-set from first message
    history: List[dict] = Field(default=[])                # [{role, content}, ...]
    created_at: datetime = Field(default_factory=...Cairo)
    updated_at: datetime = Field(default_factory=...Cairo)
```

**Why `_id` is a string, not ObjectId?** Conversations use UUIDs (hex strings) as IDs. This is more portable across systems (no bson dependency for .NET).

#### `data_chunk.py`

```python
class DataChunk(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    chunk_text: str = Field(..., min_length=1)        # The actual text
    chunk_metadata: dict                               # {city, doc_type, asset_id}
    chunk_order: int = Field(..., gt=0)                # Position in document

class RetrievedDocument(BaseModel):
    text: str                                          # Document text from Qdrant
    score: float                                       # Cosine similarity score
    metadata: Optional[dict] = None                    # Qdrant payload metadata
```

**Why `RetrievedDocument` is separate from `DataChunk`?** They serve different purposes — `DataChunk` is stored in MongoDB, `RetrievedDocument` is returned from Qdrant search (has a `score`, no MongoDB `_id`).

---

### 7.6 `enums/`

**Directory**: `src/models/enums/`

**Purpose**: Shared constants used across the codebase.

**Why enums instead of string literals?** Prevents typos, enables IDE autocomplete, centralizes changes.

#### `AssetTypeEnum.py`

```python
class AssetTypeEnum(Enum):
    FILE = "file"        # Only asset type currently supported
```

#### `DataBaseEnum.py`

```python
class DataBaseEnum(Enum):
    COLLECTION_CHUNK_NAME = "chunks"            # Text chunks
    COLLECTION_ASSET_NAME = "assets"            # File metadata
    COLLECTION_CONVERSATION_NAME = "conversations"  # Chat history
```

#### `ProcessingEnum.py`

```python
class ProcessingEnum(Enum):
    TXT = ".txt"     # TextLoader
    PDF = ".pdf"     # PyMuPDFLoader
    CSV = ".csv"     # CSVLoader
    DOCX = ".docx"   # Docx2txtLoader
```

#### `ResponseEnums.py`

```python
class ResponseSignal(Enum):
    FILE_VALIDATED_SUCCESS    = "file_validate_successfully"
    FILE_TYPE_NOT_SUPPORTED   = "file_type_not_supported"
    FILE_SIZE_EXCEEDED        = "file_size_exceeded"
    FILE_UPLOAD_SUCCESS       = "file_upload_success"
    FILE_UPLOAD_FAILED        = "file_upload_failed"
    CHAT_SUCCESS              = "chat_success"
    CHAT_ERROR                = "chat_error"
    DELETE_SUCCESS            = "delete_success"
    MULTI_UPLOAD_SUCCESS      = "multi_upload_success"
    MULTI_UPLOAD_PARTIAL      = "multi_upload_partial"
    MULTI_UPLOAD_FAILED       = "multi_upload_failed"
    INVALID_QUERY             = "invalid_query"
```

**Why signals over HTTP status codes alone?** The frontend needs a specific string to branch on, not just 200/400/500. For example, `CHAT_ERROR` and `NO_RELEVANT_DOCUMENTS` are both HTTP 200 but need different UI handling.

---

## 8. Stores

### 8.1 LLM Store

**Directory**: `src/stores/llm/`

**Purpose**: Abstractions for Large Language Model providers.

**Why it exists**: The Factory + Interface pattern means we could swap OpenAI for another provider without touching any controller code.

#### `LLMInterface.py`

Abstract base class defining the contract:

| Method | Purpose |
|--------|---------|
| `set_generation_model(model_id)` | Choose which model generates answers |
| `set_embedding_model(model_id, embedding_size)` | Choose which model creates vectors |
| `generate_text(prompt, chat_history, max_output_tokens, temperature)` | Generate text response |
| `embed_text(text, document_type)` | Generate embedding vector |
| `construct_prompt(prompt, role)` | Format a message for the provider's API |

#### `LLMProviderFactory.py`

```python
class LLMProviderFactory:
    def create(self, provider: str):
        if provider == "OPENAI":
            return OpenAIProvider(api_key, api_url, ...)
        return None  # Unknown provider
```

**Why a factory?** The provider is determined by `.env` config (`GENERATION_BACKEND` / `EMBEDDING_BACKEND`). The factory centralizes creation logic.

#### `OpenAIProvider.py`

Concrete implementation using the OpenAI Python library.

**Generated text**: Uses `client.chat.completions.create()` with `gpt-4o-mini`.

```python
def generate_text(self, prompt, chat_history=[], max_output_tokens=None, temperature=None):
    chat_history.append({"role": "user", "content": self.process_text(prompt)})
    response = self.client.chat.completions.create(
        model=self.generation_model_id,
        messages=chat_history,
        max_tokens=max_output_tokens or default,
        temperature=temperature or default,
    )
    return response.choices[0].message.content
```

**Embedding**: Uses `client.embeddings.create()` with `text-embedding-3-small` (1536 dimensions).

```python
def embed_text(self, text, document_type=None):
    response = self.client.embeddings.create(
        model=self.embedding_model_id, input=text
    )
    return response.data[0].embedding  # List[float] of 1536 values
```

**Why two separate OpenAI clients for generation vs embedding?** They use different models with different APIs (chat completions vs embeddings). The factory creates two provider instances with different model configurations.

#### `LLMEnums.py`

```python
class LLMEnums(Enum):
    OPENAI = "OPENAI"           # Only active provider

class OpenAIEnums(Enum):
    SYSTEM = "system"           # OpenAI role strings
    USER = "user"
    ASSISTANT = "assistant"

class DocumentTypeEnum(Enum):
    DOCUMENT = "document"       # Used for embedding: search_document vs search_query
    QUERY = "query"
```

---

### 8.2 Vector DB Store

**Directory**: `src/stores/vectordb/`

**Purpose**: Abstractions for vector database providers.

**Why it exists**: Same Factory pattern as LLM — allows swapping Qdrant for another vector DB.

#### `VectorDBInterface.py`

Abstract base class defining the contract:

| Method | Purpose |
|--------|---------|
| `connect()` | Initialize connection |
| `disconnect()` | Close connection |
| `create_collection(name, size, do_reset)` | Create collection with vector config |
| `insert_one(name, text, vector, metadata, id)` | Insert single point |
| `insert_many(name, texts, vectors, metadata, ids, batch_size)` | Batch insert |
| `search_by_vector(name, vector, limit, filter)` | Vector search with optional filter |
| `delete_by_filter(name, filter)` | Delete points by filter |

#### `VectorDBProviderFactory.py`

```python
class VectorDBProviderFactory:
    def create(self, provider: str):
        if provider == "QDRANT":
            return QdrantDBProvider(qdrant_db_url, qdrant_db_api_key, distance_method)
        return None
```

#### `QdrantDBProvider.py`

Concrete implementation for Qdrant Cloud.

**Connection**: `QdrantClient(url=..., api_key=...)` — connects to Qdrant Cloud SaaS.

**Collection creation**:
```python
def create_collection(self, collection_name, embedding_size, do_reset=False):
    # Creates collection with cosine/dot distance
    # Auto-creates payload indexes on metadata fields for fast filtering
    for field in ["city", "doc_type", "asset_id"]:
        client.create_payload_index(field_name=f"metadata.{field}", schema=KEYWORD)
```

**Search**:
```python
def search_by_vector(self, collection_name, vector, limit=5, filter=None):
    query_filter = self._build_filter(filter) if filter else None
    results = self.client.search(
        collection_name=collection_name,
        query_vector=vector,
        limit=limit,
        query_filter=query_filter
    )
    return [RetrievedDocument(score=r.score, text=r.payload["text"], metadata=r.payload["metadata"])
            for r in results]
```

**Filter building**: Converts `{"city": "cairo"}` to Qdrant `Filter(must=[FieldCondition(key="metadata.city", match="cairo")])`.

**Why payload indexes?** Without indexes, Qdrant does a full scan of all points for filtered queries. Indexing `city`, `doc_type`, and `asset_id` makes filtered search instant.

#### `VectorDBEnums.py`

```python
class VectorDBEnums(Enum):
    QDRANT = "QDRANT"

class DistanceMethodEnums(Enum):
    COSINE = "cosine"    # Current — good for normalized embeddings
    DOT = "dot"          # Alternative for unnormalized vectors
```

---

### 8.3 Template Parser

**File**: `src/stores/llm/templates/template_parser.py`

**Purpose**: Loads prompt templates by language, group, and key.

**Why it exists**: Prompt engineering is iterative. Separating prompts from code means changing prompts doesn't require code changes.

```python
class TemplateParser:
    def get(self, group: str, key: str, vars: dict = {}) -> str:
        # 1. Look for locales/{language}/{group}.py
        # 2. Fall back to locales/{default_language}/{group}.py
        # 3. Fall back to None
        # 4. Import module dynamically
        # 5. Access key attribute (e.g., system_prompt)
        # 6. Call Template.substitute(vars)
```

**Locale structure**:
```
locales/
  en/rag.py     → system_prompt, document_prompt, footer_prompt
  ar/rag.py     → Same prompts in Arabic
```

**English prompts** (`locales/en/rag.py`):

```python
system_prompt = """
You are a travel assistant. Your knowledge comes ONLY from the provided sources below.
RULES:
1. Answer ONLY using information EXPLICITLY stated in the provided sources.
2. If the sources only partially answer, state what is confirmed and note what is missing.
3. Respond in the same language as the user.
4. Keep answers clear, direct, and concise.
"""

document_prompt = "## Source $doc_num [Relevance: $score]\n$chunk_text"

footer_prompt = """
REMEMBER: Answer ONLY from the provided sources above.
## Question:
$query

## Answer:
"""
```

**Why string.Template instead of f-strings?** `Template.substitute()` safely handles variables with default values, and files are plain text (not executable code).

---

## 9. Deployment

### EC2 Production Setup

| Component | Detail |
|-----------|--------|
| **Server** | Ubuntu EC2 instance |
| **Port** | 5000 |
| **Process manager** | systemd (`rag.service`) |
| **Python** | conda env `mini-rag` (Python 3.11) |
| **Deploy script** | `~/deploy.sh` — `git pull && pip install -r requirements.txt -q && sudo systemctl restart rag` |
| **Restart policy** | `Restart=always` — auto-restarts on crash or reboot |

### Systemd Service (`/etc/systemd/system/rag.service`)

```ini
[Unit]
Description=RAG Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mini-rag/src
ExecStart=/home/ubuntu/miniconda3/envs/mini-rag/bin/uvicorn main:app --host 0.0.0.0 --port 5000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Why systemd instead of Docker?** User preference — simpler to manage, debug, and update for a single-server deployment.

---

## 10. Known Issues

### Critical

| # | Issue | File | Description | Impact |
|---|-------|------|-------------|--------|
| 1 | Chunk deletion field mismatch | `ChunkModel.py:52` | Queries `"chunk_asset_id"` but chunks store `asset_id` inside `chunk_metadata` | File DELETE/PUT never removes chunks from MongoDB — orphans accumulate |

### High

| # | Issue | File | Description | Impact |
|---|-------|------|-------------|--------|
| 2 | PUT data loss ordering | `data.py:214-216` | Redundant `os.remove` before save (open("wb") overwrites anyway) | No data loss in practice, but dead code |

### Medium

| # | Issue | File | Description | Impact |
|---|-------|------|-------------|--------|
| 3 | No OpenAI retry/timeout | `OpenAIProvider.py` | No retry on rate limits, no timeout config | Random 429 errors in production |
| 4 | Sequential embedding | `NLPController.py:162` | Embeds chunks one by one instead of batch | Slower indexing for large files |

### Minor

| # | Issue | File | Description |
|---|-------|------|-------------|
| 5 | Dead code | `ChunkModel.py:31-34` | `create_chunk()` never called |
| 6 | Dead imports | `routes/nlp.py:1` | `from fastapi import FastAPI` unused |
| 7 | Dead import | `routes/base.py:1` | `import os` unused |

---

## Appendix: Chat Flow — Complete End-to-End

```
USER: "What hotels are in Luxor?"
        │
        ▼
  ┌─ POST /chat {text: "What hotels in Luxor?", conversation_id: "abc"}
  │
  ├─ 1. Validate non-empty query
  ├─ 2. Load conversation "abc" from MongoDB
  │      └─ history: [] (first message)
  │
  ├─ 3. is_greeting_query("What hotels in Luxor?")
  │      └─ false (too long, has content)
  │
  ├─ 4. rewrite_query("What hotels in Luxor?", [])
  │      └─ No history → return as-is: "What hotels in Luxor?"
  │
  ├─ 5. embed("What hotels in Luxor?") → vector[1536]
  │      └─ OpenAI text-embedding-3-small
  │
  ├─ 6. Qdrant.search(tourism_knowledge_base, vector, limit=5)
  │      └─ Returns 3 results (score: 0.89, 0.76, 0.45)
  │
  ├─ 7. Filter by score >= 0.2
  │      └─ All 3 pass → return
  │
  ├─ 8. Build sources:
  │      [{doc: "luxor_hotels.pdf", city: "luxor", score: 0.89, excerpt: "..."}]
  │
  ├─ 9. generate_chat_answer():
  │      ├─ Build chat_history: [system_prompt]
  │      ├─ No prior history (first message)
  │      ├─ 3 document prompts (trimmed to fit 4096 chars)
  │      ├─ Append footer: "## Question: What hotels are in Luxor?"
  │      └─ GPT-4o-mini → "Luxor has several top hotels including..."
  │
  ├─ 10. append_turn("abc", "What hotels in Luxor?", "Luxor has several...")
  │       └─ MongoDB: set title, push 2 history entries, update timestamp
  │
  └─ 11. Return {answer: "Luxor has several...", sources: [...]}


USER: "What about restaurants there?"
        │
        ▼
  ┌─ POST /chat {text: "What about restaurants there?", conversation_id: "abc"}
  │
  ├─ 1. Load conversation "abc" from MongoDB
  │      └─ history: [{user: "What hotels...", assistant: "Luxor has several..."}]
  │
  ├─ 2. rewrite_query("What about restaurants there?", history)
  │      └─ GPT: "What restaurants are in Luxor?"
  │
  ├─ 3. embed("What restaurants are in Luxor?") → vector[1536]
  ├─ 4. Qdrant.search() → 2 results
  ├─ 5. generate_chat_answer(docs, history) → "Luxor has great dining at..."
  ├─ 6. append_turn() → push to MongoDB
  └─ 7. Return answer with sources
```

This is the **key advantage** of query rewriting — without it, step 2 would search "What about restaurants there?" which would return nothing useful.

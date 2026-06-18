# Mini RAG — Full Documentation

> Multi-provider, multi-city RAG chatbot for tourism. Users ask questions about cities, attractions, restaurants, hotels, and shopping — the system retrieves relevant document chunks and generates answers grounded in uploaded content.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Directory Tree](#2-directory-tree)
3. [Entry Point (`main.py`)](#3-entry-point-mainpy)
4. [Configuration (`config.py` + `.env`)](#4-configuration)
5. [Controllers](#5-controllers)
   - 5.1 BaseController
   - 5.2 ProjectController
   - 5.3 DataController
   - 5.4 ProcessController
   - 5.5 NLPController
6. [Models](#6-models)
   - 6.1 DB Schemes (Pydantic)
   - 6.2 Data Models (MongoDB CRUD)
   - 6.3 Enums
7. [Routes — API Endpoints](#7-routes)
   - 7.1 base.py
   - 7.2 data.py
   - 7.3 nlp.py
   - 7.4 Schemes (Request/Response)
8. [Stores (Providers)](#8-stores)
   - 8.1 LLM Store
   - 8.2 Rerank Store
   - 8.3 Vector DB Store
   - 8.4 TemplateParser
9. [City Detection System](#9-city-detection-system)
10. [Data Flows (Step by Step)](#10-data-flows)
11. [Prompt Templates](#11-prompt-templates)
12. [Enums Reference](#12-enums-reference)
13. [Environment Variables Reference](#13-environment-variables-reference)

---

## 1. Architecture Overview

```
┌─ Frontend (Angular + .NET) ───────────────────────────────┐
│  POST /api/v1/nlp/chat   { text, limit, doc_type, history }      │
└────────────────────────────┬──────────────────────────────┘
                             │
┌─ Backend (FastAPI) ────────▼──────────────────────────────┐
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│  │  LLM Provider │   │  Embedding   │   │  Vector DB   │   │
│  │  ◄── Factory  │   │  ◄── Factory │   │  ◄── Factory │   │
│  │               │   │              │   │              │   │
│  │  OpenAI       │   │  OpenAI      │   │  Qdrant      │   │
│  │  CoHere       │   │  CoHere      │   │  (extensible)│   │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   │
│         │                  │                  │           │
│  ┌──────▼──────────────────▼──────────────────▼───────┐   │
│  │              Rerank Provider  ◄── Factory          │   │
│  │              CrossEncoder / Ollama                 │   │
│  └─────────────────────┬─────────────────────────────┘   │
│                        │                                  │
│  ┌─ MongoDB Atlas ─────┼─────────────────────────────┐   │
│  │  projects, assets, chunks (metadata)              │   │
│  └─────────────────────┼─────────────────────────────┘   │
│  ┌─ Qdrant Cloud ──────┼─────────────────────────────┐   │
│  │  tourism_knowledge_base (single collection)        │   │
│  │  payload: text, metadata.{city, doc_type, asset_id}│   │
│  └─────────────────────┼─────────────────────────────┘   │
│  ┌─ city_mappings.json ┘                              ┐   │
│  │  Country→city mapping + known_cities[]              │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Factory Pattern for Providers**
Every external service (LLM, embedding, vector DB, reranker) follows the same pattern:
- **Interface** (abstract base class) — defines the contract
- **Factory** — creates the correct provider based on `.env` config
- **Provider(s)** — concrete implementations

This means you can swap OpenAI ↔ CoHere or Qdrant ↔ any other vector DB without changing any controller or route code.

**Single Qdrant Collection**
All cities share one collection (`tourism_knowledge_base`). City scoping is done via Qdrant payload filters on `metadata.city`. This enables global search (no city filter = all cities) and multi-city queries.

**Stateless Backend**
No session management. Conversation history is sent by the frontend in every `ChatRequest.history` field. The backend is fully stateless — horizontally scalable.

---

## 2. Directory Tree

```
mini-rag/
│
├── DOCUMENTATION.md              ← This file
├── README.md                     ← Quick-start guide for frontend team
├── CHANGELOG.md                  ← Release history
├── LICENSE                       ← Project license
├── check_compile.py              ← CI script: compiles key Python files
├── check_deps.py                 ← Debug script: checks torch/transformers install
├── start_server.sh               ← WSL server launcher (uvicorn)
├── test_chat_api.py              ← Python test script (needs server running)
├── test_greeting.py              ← Greeting detection test
├── test_chat_error.py            ← FastAPI TestClient test
│
├── docker/
│   ├── docker-compose.yml        ← MongoDB 7 + Qdrant (for local dev)
│   └── .gitignore                ← Ignores mongodb/, .env
│
└── src/
    ├── main.py                   ← FastAPI app, startup/shutdown, DI setup
    ├── .env                      ← All configuration (secrets redacted in repo)
    ├── .gitignore                ← Ignores __pycache__, .env, assets/files/, assets/database/
    ├── city_mappings.json        ← Country→city + known_cities[]
    ├── requirements.txt          ← Python dependencies
    │
    ├── controllers/
    │   ├── __init__.py           ← Exports: DataController, ProjectController, ProcessController, NLPController
    │   ├── BaseController.py     ← File paths, random string generator
    │   ├── DataController.py     ← File validation, upload, city detection (filename + content)
    │   ├── NLPController.py      ← Core RAG logic (chat, search, rerank, generate, detect, delete)
    │   ├── ProcessController.py  ← Document loaders (PDF/DOCX/CSV/TXT), text splitting
    │   └── ProjectController.py  ← Project directory management
    │
    ├── helpers/
    │   ├── __init__.py           ← Empty
    │   └── config.py             ← Pydantic Settings class (loads from .env)
    │
    ├── models/
    │   ├── __init__.py           ← Exports: ResponseSignal, ProcessingEnum
    │   ├── BaseDataModel.py      ← Base class for all MongoDB models
    │   ├── ProjectModel.py       ← CRUD for MongoDB "projects" collection
    │   ├── AssetModel.py         ← CRUD for MongoDB "assets" collection
    │   ├── ChunkModel.py         ← CRUD for MongoDB "chunks" collection
    │   ├── db_schemes/
    │   │   ├── __init__.py       ← Exports: Project, Asset, DataChunk, RetrievedDocument
    │   │   ├── project.py        ← Project Pydantic model (project_id)
    │   │   ├── asset.py          ← Asset Pydantic model (project_id, type, name, size, config)
    │   │   └── data_chunk.py     ← DataChunk + RetrievedDocument Pydantic models
    │   └── enums/
    │       ├── __init__.py       ← Empty
    │       ├── ResponseEnums.py  ← All API signals (success/error codes)
    │       ├── AssetTypeEnum.py  ← Asset types (FILE)
    │       ├── DataBaseEnum.py   ← MongoDB collection names
    │       └── ProcessingEnum.py ← File extensions (.txt, .pdf, .csv, .docx)
    │
    ├── routes/
    │   ├── __init__.py           ← Empty
    │   ├── base.py               ← GET /api/v1/ (welcome + version)
    │   ├── data.py               ← Upload, process, delete, city management endpoints
    │   ├── nlp.py                ← Chat + legacy index/search/answer endpoints
    │   └── schemes/
    │       ├── __init__.py       ← Empty
    │       ├── data.py           ← ProcessRequest, UpdateAssetRequest
    │       └── nlp.py            ← PushRequest, SearchRequest, ChatRequest, ChatResponse
    │
    ├── stores/
    │   ├── llm/
    │   │   ├── __init__.py       ← Empty
    │   │   ├── LLMEnums.py       ← Enums: LLMEnums (OPENAI, COHERE), OpenAIEnums, CoHereEnums, DocumentTypeEnum
    │   │   ├── LLMInterface.py   ← Abstract base: set_generation_model, set_embedding_model, generate_text, embed_text, construct_prompt
    │   │   ├── LLMProviderFactory.py ← Creates OpenAIProvider or CoHereProvider
    │   │   ├── providers/
    │   │   │   ├── __init__.py   ← Exports: CoHereProvider, OpenAIProvider
    │   │   │   ├── OpenAIProvider.py  ← OpenAI-compatible (OpenAI API, Ollama, any OpenAI-proxy)
    │   │   │   └── CoHereProvider.py  ← CoHere API provider
    │   │   └── templates/
    │   │       ├── __init__.py       ← Empty
    │   │       ├── template_parser.py ← Loads prompt templates by language + group + key
    │   │       └── locales/
    │   │           ├── __init__.py   ← Empty
    │   │           ├── en/rag.py     ← English prompt templates
    │   │           └── ar/rag.py     ← Arabic prompt templates
    │   │
    │   ├── rerank/
    │   │   ├── __init__.py       ← Empty
    │   │   ├── RerankEnums.py    ← Enums: OLLAMA, CROSS_ENCODER
    │   │   ├── RerankInterface.py← Abstract base: rerank(query, documents, top_k, model)
    │   │   ├── RerankProviderFactory.py ← Creates OllamaRerankProvider or CrossEncoderRerankProvider
    │   │   └── providers/
    │   │       ├── __init__.py   ← Exports: OllamaRerankProvider, CrossEncoderRerankProvider
    │   │       ├── OllamaRerankProvider.py      ← Calls Ollama /api/rerank (deprecated, model-dependent)
    │   │       └── CrossEncoderRerankProvider.py ← Local cross-encoder via sentence-transformers
    │   │
    │   └── vectordb/
    │       ├── __init__.py       ← Empty
    │       ├── VectorDBEnums.py  ← Enums: QDRANT, DistanceMethodEnums (COSINE, DOT)
    │       ├── VectorDBInterface.py ← Abstract base: connect, disconnect, search, insert, delete, etc.
    │       ├── VectorDBProviderFactory.py ← Creates QdrantDBProvider
    │       └── providers/
    │           ├── __init__.py   ← Exports: QdrantDBProvider
    │           └── QdrantDBProvider.py ← Qdrant Cloud client implementation
    │
    └── assets/
        └── mini-rag-app.postman_collection.json  ← Postman API collection for testing
```

---

## 3. Entry Point (`main.py`)

**File:** `src/main.py`

The FastAPI application entry point. Sets up all global dependencies on startup and tears them down on shutdown.

### Startup Sequence (`startup_span()`)

| Step | What happens |
|------|-------------|
| 1 | Reads `.env` via `get_settings()` |
| 2 | Connects to MongoDB Atlas via `AsyncIOMotorClient` |
| 3 | Creates `LLMProviderFactory` + creates **generation** client (OpenAI/CoHere) |
| 4 | Creates `LLMProviderFactory` + creates **embedding** client |
| 5 | Creates `VectorDBProviderFactory` + creates + connects **Qdrant** client |
| 6 | Creates `TemplateParser` with configured language |
| 7 | Creates `RerankProviderFactory` + creates reranker client |

### Global App State

These are attached to `app` and accessed by routes via `request.app`:

| Attribute | Type | Purpose |
|-----------|------|---------|
| `app.mongo_conn` | `AsyncIOMotorClient` | MongoDB connection |
| `app.db_client` | Database | MongoDB database handle |
| `app.generation_client` | LLM Provider | Text generation (qwen2.5 / gpt-4o) |
| `app.embedding_client` | LLM Provider | Text embedding (nomic-embed-text / text-embedding-3-small) |
| `app.vectordb_client` | Vector DB Provider | Qdrant client |
| `app.template_parser` | TemplateParser | Loads locale-aware prompt templates |
| `app.rerank_client` | Rerank Provider | Cross-encoder / Ollama reranker |
| `app.rerank_model_id` | str | Model ID for reranker |

### CORS

All origins allowed (`*`) — the frontend team can configure this.

### Shutdown

Closes MongoDB connection and disconnects Qdrant client.

---

## 4. Configuration

### `src/helpers/config.py`

A `pydantic-settings` `BaseSettings` class that reads from `.env`. All fields are typed with defaults where appropriate.

| Field | Type | Default | .env Key |
|-------|------|---------|----------|
| `APP_NAME` | str | — | `APP_NAME` |
| `APP_VERSION` | str | — | `APP_VERSION` |
| `FILE_ALLOWED_TYPES` | list | — | `FILE_ALLOWED_TYPES` |
| `FILE_ALLOWED_EXTENSIONS` | list | `[".txt",".pdf",".csv",".docx"]` | — |
| `FILE_MAX_SIZE` | int | — | `FILE_MAX_SIZE` (MB) |
| `FILE_DEFAULT_CHUNK_SIZE` | int | — | `FILE_DEFAULT_CHUNK_SIZE` (bytes) |
| `VECTOR_DB_COLLECTION_NAME` | str | `"tourism_knowledge_base"` | — |
| `DEFAULT_CITY` | str | `"unknown"` | — |
| `DEFAULT_DOC_TYPE` | str | `"general"` | — |
| `MONGODB_URL` | str | — | `MONGODB_URL` |
| `MONGODB_DATABASE` | str | — | `MONGODB_DATABASE` |
| `GENERATION_BACKEND` | str | — | `GENERATION_BACKEND` |
| `EMBEDDING_BACKEND` | str | — | `EMBEDDING_BACKEND` |
| `OPENAI_API_KEY` | str | `None` | `OPENAI_API_KEY` |
| `OPENAI_API_URL` | str | `None` | `OPENAI_API_URL` |
| `COHERE_API_KEY` | str | `None` | `COHERE_API_KEY` |
| `GENERATION_MODEL_ID` | str | `None` | `GENERATION_MODEL_ID` |
| `EMBEDDING_MODEL_ID` | str | `None` | `EMBEDDING_MODEL_ID` |
| `EMBEDDING_MODEL_SIZE` | int | `None` | `EMBEDDING_MODEL_SIZE` |
| `INPUT_DEFAULT_MAX_CHARACTERS` | int | `None` | `INPUT_DEFAULT_MAX_CHARACTERS` |
| `GENERATION_DEFAULT_MAX_TOKENS` | int | `None` | `GENERATION_DEFAULT_MAX_TOKENS` |
| `GENERATION_DEFAULT_TEMPERATURE` | float | `None` | `GENERATION_DEFAULT_TEMPERATURE` |
| `VECTOR_DB_BACKEND` | str | — | `VECTOR_DB_BACKEND` |
| `QDRANT_DB_URL` | str | — | `QDRANT_DB_URL` |
| `DISTANCE_METHOD` | str | `None` | `DISTANCE_METHOD` |
| `QDRANT_DB_API_KEY` | str | — | `QDRANT_DB_API_KEY` |
| `PRIMARY_LANG` | str | `"en"` | `PRIMARY_LANG` |
| `DEFAULT_LANG` | str | `"en"` | — |
| `SCORE_THRESHOLD` | float | `0.4` | `SCORE_THRESHOLD` |
| `RERANK_BACKEND` | str | `None` | `RERANK_BACKEND` |
| `RERANK_MODEL_ID` | str | `None` | `RERANK_MODEL_ID` |
| `CITY_MAPPINGS_PATH` | str | `"city_mappings.json"` | — |

---

## 5. Controllers

### 5.1 BaseController (`src/controllers/BaseController.py`)

Base class for all controllers. Provides common utilities.

**Attributes:**

| Attribute | Value | Description |
|-----------|-------|-------------|
| `app_settings` | `Settings` | Loaded config object |
| `base_dir` | `os.path.dirname(src/)` | Project root |
| `files_dir` | `src/assets/files` | Uploaded file storage |

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate_random_string` | `(length=12) → str` | Generates a random alphanumeric string (used for unique file IDs) |

### 5.2 ProjectController (`src/controllers/ProjectController.py`)

Manages project directories on disk.

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_project_path` | `(project_id: str) → str` | Returns `assets/files/{project_id}` path, creates directory if it doesn't exist |

Note: Despite the name, this does NOT interact with MongoDB. It only manages the filesystem directory for file storage.

### 5.3 DataController (`src/controllers/DataController.py`)

Handles file validation, upload preparation, and city detection.

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `validate_uploaded_file` | `(file: UploadFile) → (bool, str)` | Checks content-type, extension, and size against config. Returns `(is_valid, signal)` |
| `generate_unique_filepath` | `(orig_file_name, project_id) → (file_path, file_id)` | Creates a unique file path with random prefix to prevent collisions. Returns `(full_path, relative_name)` |
| `get_clean_file_name` | `(orig_file_name) → str` | Strips special characters, replaces spaces with underscores |
| `extract_city_type` | `(filename) → dict` | Parses `{city}_{type}.ext` naming convention. Returns `{"city": ..., "doc_type": ...}` |
| `detect_city_from_content` | `(file_content: list) → str or None` | Scans document text against `known_cities` (exact single match) then country→city mapping. Used when filename doesn't specify a city |

**City Detection Logic (`detect_city_from_content`):**
1. Load `city_mappings.json` to get `known_cities` array and country mappings
2. Concatenate all page content from loaded documents
3. Check if exactly one known city appears in the text → return it
4. If no city match, check if exactly one known country appears → return its mapped city
5. Return `None` if ambiguous or no match

### 5.4 ProcessController (`src/controllers/ProcessController.py`)

Loads files from disk and splits them into chunks.

**Attributes:**

| Attribute | Description |
|-----------|-------------|
| `project_id` | The project this controller works with |
| `project_path` | Absolute path to `assets/files/{project_id}` |

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_file_extension` | `(file_id) → str` | Extracts extension from file name |
| `get_file_loader` | `(file_id) → loader or None` | Returns the appropriate LangChain document loader based on file extension |
| `get_file_content` | `(file_id) → list[Document] or None` | Loads file content using the correct loader |
| `process_file_content` | `(file_content, file_id, chunk_size, overlap_size, metadata) → list[Document]` | Splits documents into overlapping chunks using `RecursiveCharacterTextSplitter`, attaches metadata to each chunk |

**Supported file types and their loaders:**

| Extension | Loader |
|-----------|--------|
| `.txt` | `TextLoader` (UTF-8) |
| `.pdf` | `PyMuPDFLoader` |
| `.csv` | `CSVLoader` |
| `.docx` | `Docx2txtLoader` |

### 5.5 NLPController (`src/controllers/NLPController.py`)

The core of the RAG system. Handles search, reranking, LLM interaction, city detection, and data deletion.

**Module-level function:**

| Function | Signature | Description |
|----------|-----------|-------------|
| `load_city_mappings` | `(path="city_mappings.json") → dict` | LRU-cached loader for `city_mappings.json`. Returns parsed JSON dict |

**Constructor Parameters:**

| Param | Source | Description |
|-------|--------|-------------|
| `vectordb_client` | `app.vectordb_client` | Qdrant client |
| `generation_client` | `app.generation_client` | LLM for text generation |
| `embedding_client` | `app.embedding_client` | LLM for embeddings |
| `template_parser` | `app.template_parser` | Prompt template loader |
| `rerank_client` | `app.rerank_client` | Reranker (optional) |
| `rerank_model_id` | `app.rerank_model_id` | Reranker model ID |

**Methods:**

#### `is_greeting_query(query: str) → bool`

Checks if the query is a pure greeting (exact match against a multilingual set). Used to skip vector search and return a warm welcome.

**Greeting set:** `hi`, `hello`, `hey`, `howdy`, `greetings`, `good morning`, `good afternoon`, `good evening`, `good day`, `what's up`, `sup`, `yo`, `مرحبا`, `اهلا`, `اهلاً`, `السلام عليكم`, `سلام`, `bonjour`, `salut`, `bonsoir`, `hola`, `buenos días`, `buenas tardes`

Note: `"hi what is the best restaurants"` would NOT match (not pure greeting).

#### `detect_city_from_query(query: str, known_cities: list) → str or None`

Detects city from user's query text.

**Logic:**
1. Check if exactly one known city name appears in the query → return it
2. If no city match, check country mappings → if exactly one country matches, return its mapped city
3. Return `None` for no match or multiple matches (falls to global search)

#### `reset_vector_db_collection(project: Project) → bool`

Deletes all vectors for a given project from Qdrant.

#### `get_vector_db_collection_info(project: Project) → dict`

Returns Qdrant collection info (used by legacy `/index/info` endpoint).

#### `index_into_vector_db(project, chunks, chunks_ids, do_reset) → bool`

Embeds and indexes document chunks into Qdrant.

**Flow:**
1. Optionally reset existing vectors for this project
2. Extract text and metadata from each chunk
3. Embed each text via `embedding_client.embed_text()`
4. Create collection if not exists (idempotent)
5. Batch insert into Qdrant with vectors, texts, metadata, and record IDs

#### `chat(query, limit=5, city=None, doc_type=None) → list[RetrievedDocument] or None`

The primary search method. Searches Qdrant, reranks, filters, returns top results.

**Flow:**
1. Validate non-empty query → return `None` if invalid
2. Embed query
3. Build filter dict from `city` and `doc_type` params
4. Retrieve 20 results (or `limit` if reranker unavailable)
5. If reranker available: rerank all 20 → filter by cross-encoder score `>= 0.0` → return top `limit`
6. If reranker unavailable/unavailable: filter by Qdrant score `>= SCORE_THRESHOLD` → return top `limit`
7. Return `None` if no results pass threshold

#### `search_vector_db_collection(project: Project, text: str, limit: int = 10) → list[RetrievedDocument]`

Legacy project-scoped search (used by `/index/search/{project_id}`). Same reranking + threshold logic as `chat()` but filtered by `project_id`.

#### `generate_chat_answer(query, retrieved_documents, prior_history=None, system_prompt=None) → (answer, full_prompt, chat_history)`

Generates an LLM answer from retrieved documents.

**Flow:**
1. Build document prompts with source numbers and relevance scores
2. Budget-aware trimming: ensure documents + footer fit within `INPUT_DEFAULT_MAX_CHARACTERS`
3. Construct chat history: system prompt → prior history (up to 6 turns) → document prompts → footer
4. Call `generation_client.generate_text()` with the full prompt
5. Return answer, full prompt, and chat history

**Key details:**
- Prior history is injected as proper `user`/`assistant` messages (not a single system blob)
- Documents are trimmed before reaching the LLM, preventing silent truncation of footer/query
- Custom `system_prompt` can be passed (used for greeting responses)

#### `generate_related_questions(query: str, answer: str) → list[str]`

Generates 3-5 follow-up questions based on the query and answer.

**Flow:**
1. Build related-questions prompt from template
2. Call LLM
3. Parse numbered/bulleted list from response
4. Return up to 5 clean questions

#### `delete_project_vectors(project_id: str) → bool`

Deletes all Qdrant points matching `project_id`.

#### `delete_file_vectors(asset_id: str) → bool`

Deletes all Qdrant points matching `asset_id`.

---

## 6. Models

### 6.1 DB Schemes (Pydantic Models) — `src/models/db_schemes/`

#### `Project` (`project.py`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `ObjectId` | MongoDB `_id` |
| `project_id` | `str` | Unique project identifier (must be alphanumeric) |

Index: `project_id` (unique)

#### `Asset` (`asset.py`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `ObjectId` | MongoDB `_id` |
| `asset_project_id` | `ObjectId` | Reference to parent project |
| `asset_type` | `str` | `"file"` (from AssetTypeEnum) |
| `asset_name` | `str` | Unique file name on disk |
| `asset_size` | `int` | File size in bytes |
| `asset_config` | `dict` | `{"city": "...", "doc_type": "..."}` |
| `asset_pushed_at` | `datetime` | Upload timestamp |

Indexes: `asset_project_id`, compound `(asset_project_id + asset_name)` (unique)

#### `DataChunk` (`data_chunk.py`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `ObjectId` | MongoDB `_id` |
| `chunk_text` | `str` | Text content of the chunk |
| `chunk_metadata` | `dict` | `{"city": "...", "doc_type": "...", "asset_id": "..."}` |
| `chunk_order` | `int` | Position within the original document |
| `chunk_project_id` | `ObjectId` | Reference to parent project |
| `chunk_asset_id` | `ObjectId` | Reference to parent asset |

Index: `chunk_project_id`

#### `RetrievedDocument` (`data_chunk.py`)

Non-MongoDB model — used for Qdrant search results.

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Document text |
| `score` | `float` | Relevance score (Qdrant cosine or cross-encoder logit) |
| `metadata` | `dict` or `None` | Payload metadata |

### 6.2 Data Models (MongoDB CRUD)

All data models inherit from `BaseDataModel` which provides `db_client` and `app_settings`. They use a `create_instance` async factory pattern for async initialization.

#### `ProjectModel` (`ProjectModel.py`)

Collection: `"projects"`

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_project` | `(project) → Project` | Insert new project document |
| `get_project_or_create_one` | `(project_id) → Project` | Find by project_id or create new |
| `get_all_projects` | `(page, page_size) → (list[Project], total_pages)` | Paginated list |
| `delete_project` | `(project_id) → int` | Delete by project_id |

#### `AssetModel` (`AssetModel.py`)

Collection: `"assets"`

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_asset` | `(asset) → Asset` | Insert new asset document |
| `get_all_project_assets` | `(project_id, type) → list[Asset]` | All assets for a project |
| `get_asset_record` | `(project_id, asset_name) → Asset or None` | Find specific asset |
| `get_uncategorized_assets` | `() → list[Asset]` | Assets with city `None` or `"unknown"` |
| `update_asset_city` | `(asset_id, city, doc_type=None) → Asset or None` | Update city/type in asset_config |
| `delete_asset_by_id` | `(asset_id) → int` | Delete single asset |
| `delete_assets_by_project_id` | `(project_id) → int` | Delete all assets for a project |

#### `ChunkModel` (`ChunkModel.py`)

Collection: `"chunks"`

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_chunk` | `(chunk) → DataChunk` | Insert single chunk |
| `get_chunk` | `(chunk_id) → DataChunk or None` | Find by _id |
| `insert_many_chunks` | `(chunks, batch_size=100) → int` | Bulk insert with batched writes |
| `delete_chunks_by_project_id` | `(project_id) → int` | Delete all chunks for a project |
| `delete_chunks_by_asset_id` | `(asset_id) → int` | Delete all chunks for an asset |
| `get_project_chunks` | `(project_id, page, page_size) → list[DataChunk]` | Paginated chunks (used by index/push) |

### 6.3 Enums

#### `ResponseSignal` (`ResponseEnums.py`)

The entire API signaling system. Every endpoint response includes a `signal` field with one of these values.

| Enum Member | String Value | When Returned | HTTP Status |
|-------------|--------------|---------------|-------------|
| `FILE_VALIDATED_SUCCESS` | `"file_validate_successfully"` | Internal — file passes validation | 200 |
| `FILE_TYPE_NOT_SUPPORTED` | `"file_type_not_supported"` | Upload with unsupported extension/MIME | 400 |
| `FILE_SIZE_EXCEEDED` | `"file_size_exceeded"` | File too large | 400 |
| `FILE_UPLOAD_SUCCESS` | `"file_upload_success"` | Single file uploaded + chunked | 200 |
| `FILE_UPLOAD_FAILED` | `"file_upload_failed"` | Disk write error | 400 |
| `PROCESSING_SUCCESS` | `"processing_success"` | Re-processing complete | 200 |
| `PROCESSING_FAILED` | `"processing_failed"` | Chunking produced no chunks | 400 |
| `NO_FILES_ERROR` | `"not_found_files"` | No files found for processing | 400 |
| `FILE_ID_ERROR` | `"no_file_found_with_this_id"` | Asset not found | 400 |
| `PROJECT_NOT_FOUND_ERROR` | `"project_not_found"` | Project not found (delete/list) | 400 |
| `INSERT_INTO_VECTORDB_ERROR` | `"insert_into_vectordb_error"` | Vector DB insert failed | 400 |
| `INSERT_INTO_VECTORDB_SUCCESS` | `"insert_into_vectordb_success"` | Index push complete | 200 |
| `VECTORDB_COLLECTION_RETRIEVED` | `"vectordb_collection_retrieved"` | Collection info retrieved | 200 |
| `VECTORDB_SEARCH_ERROR` | `"vectordb_search_error"` | Legacy search found nothing | 400 |
| `VECTORDB_SEARCH_SUCCESS` | `"vectordb_search_success"` | Legacy search returned results | 200 |
| `RAG_ANSWER_ERROR` | `"rag_answer_error"` | Legacy RAG returned no answer | 400 |
| `RAG_ANSWER_SUCCESS` | `"rag_answer_success"` | Legacy RAG returned answer | 200 |
| `CHAT_SUCCESS` | `"chat_success"` | Chat returned answer | 200 |
| `CHAT_ERROR` | `"chat_error"` | LLM generation failed | 200 |
| `NO_RELEVANT_DOCUMENTS` | `"no_relevant_documents"` | No docs passed threshold | 200 |
| `DELETE_SUCCESS` | `"delete_success"` | Deletion complete | 200 |
| `DELETE_ERROR` | `"delete_error"` | Deletion failed | 400 |
| `CITY_UPDATE_SUCCESS` | `"city_update_success"` | Asset city/type updated | 200 |
| `MULTI_UPLOAD_SUCCESS` | `"multi_upload_success"` | All files uploaded | 200 |
| `MULTI_UPLOAD_PARTIAL` | `"multi_upload_partial"` | Some files failed | 200 |
| `MULTI_UPLOAD_FAILED` | `"multi_upload_failed"` | All files failed | 200 |
| `INVALID_QUERY` | `"invalid_query"` | Empty/spaces-only query | 400 |

#### `AssetTypeEnum` (`AssetTypeEnum.py`)

| Member | Value |
|--------|-------|
| `FILE` | `"file"` |

#### `DataBaseEnum` (`DataBaseEnum.py`)

| Member | Value | Collection |
|--------|-------|------------|
| `COLLECTION_PROJECT_NAME` | `"projects"` | MongoDB projects |
| `COLLECTION_CHUNK_NAME` | `"chunks"` | MongoDB chunks |
| `COLLECTION_ASSET_NAME` | `"assets"` | MongoDB assets |

#### `ProcessingEnum` (`ProcessingEnum.py`)

| Member | Value |
|--------|-------|
| `TXT` | `".txt"` |
| `PDF` | `".pdf"` |
| `CSV` | `".csv"` |
| `DOCX` | `".docx"` |

---

## 7. Routes (API Endpoints)

### 7.1 `base.py` — `GET /api/v1/`

Returns the app name and version.

**Response:**
```json
{
  "app_name": "Mini RAG",
  "app_version": "0.1.0"
}
```

### 7.2 `data.py` — Upload & Management Endpoints

All routes are under `/api/v1/data/`.

---

#### `POST /upload/{project_id}` — Single File Upload

**Purpose:** Upload a file, extract city/type from filename (or use provided values), detect city from content if filename was generic, chunk the document, store chunks in MongoDB.

**Form Data:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | UploadFile | yes | — | The file (PDF, DOCX, CSV, TXT) |
| `city` | string | no | from filename or "unknown" | Override city |
| `doc_type` | string | no | from filename or "general" | Override doc type |
| `chunk_size` | int | no | 500 | Chunk character size |
| `overlap_size` | int | no | 20 | Chunk overlap |

**Flow:**
1. Validate file type and size
2. Save file to `assets/files/{project_id}/` with unique name
3. Extract city/type from filename (fallback to form values)
4. Create Asset record in MongoDB
5. Load file content, detect city from content if city is still "unknown", update asset config
6. Split into chunks with metadata
7. Insert chunks into MongoDB
8. Return `FILE_UPLOAD_SUCCESS` with `file_id`, `city`, `doc_type`, `inserted_chunks`

---

#### `POST /upload-multi` — Multiple File Upload

**Purpose:** Upload multiple files at once, auto-detect city for each, create separate projects per city.

**Form Data:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `files` | List[UploadFile] | yes | — | Multiple files |
| `chunk_size` | int | no | 500 | Chunk size |
| `overlap_size` | int | no | 20 | Chunk overlap |

**Flow (per file):**
1. Validate file
2. Extract city/type from filename
3. Save file to `assets/files/{city}/`
4. If city is "unknown", load content and detect city from text
5. Get or create MongoDB project for the (possibly detected) city
6. Create Asset record
7. Chunk and insert into MongoDB
8. Return per-file result in array

**Response:**
```json
{
  "signal": "multi_upload_success",
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    {"file_name": "cairo_food.pdf", "status": "success", "project_id": "cairo", "city": "cairo", "doc_type": "food", "inserted_chunks": 12},
    {"file_name": "unknown_guide.pdf", "status": "success", "project_id": "luxor", "city": "luxor", "doc_type": "guide", "inserted_chunks": 8},
    {"file_name": "bad.xyz", "status": "error", "error": "file_type_not_supported"}
  ]
}
```

---

#### `PUT /asset/{asset_id}` — Update Asset City/Type

**Purpose:** Change the city and/or doc_type of an existing asset.

**Request Body:**
```json
{
  "city": "cairo",
  "doc_type": "restaurants"
}
```

Returns `CITY_UPDATE_SUCCESS` or `FILE_ID_ERROR`.

---

#### `GET /assets/uncategorized` — List Unknown Assets

Returns assets where city is `null` or `"unknown"`.

---

#### `GET /cities` — List Cities

Returns distinct city values from MongoDB assets (excluding `null` and `"unknown"`).

---

#### `POST /cities` — Add City (No-op)

Placeholder endpoint. Accepts `{"city_name": "..."}` and echoes it back. No actual database operation.

---

#### `POST /process/{project_id}` — Re-process Files

**Purpose:** Re-process all (or specific) files for a project into chunks. Can optionally reset existing chunks first.

**Request Body:**
```json
{
  "file_id": null,
  "chunk_size": 500,
  "overlap_size": 20,
  "do_reset": 0
}
```

If `file_id` is provided, only that file is processed. If `null`, all project files are processed. If `do_reset=1`, existing chunks are deleted first.

---

#### `DELETE /project/{project_id}` — Delete Project

Deletes all chunks, assets, Qdrant vectors, and the project record for the given project_id.

---

#### `DELETE /file/{file_id}` — Delete File

Deletes a single asset, its chunks, and its Qdrant vectors.

---

#### `DELETE /chunks/{project_id}` — Delete Chunks Only

Deletes chunks and Qdrant vectors only (keeps assets and project).

---

### 7.3 `nlp.py` — Chat & Legacy Endpoints

All routes are under `/api/v1/nlp/`.

---

#### `POST /chat` — Global Chat (Primary Endpoint)

**Purpose:** The main endpoint used by the frontend. Accepts a user question, detects city from text, searches Qdrant, reranks, generates an answer with sources.

**Request Body:**
```json
{
  "text": "What are the best restaurants in Cairo?",
  "limit": 5,
  "doc_type": null,
  "history": [
    {"role": "user", "content": "Tell me about Cairo"},
    {"role": "assistant", "content": "Cairo has..."}
  ]
}
```

**Flow:**
1. Validate non-empty query → return 400 `INVALID_QUERY` if empty
2. Check greeting → if pure greeting, skip search and return warm welcome
3. Fetch distinct cities from MongoDB, merge with `known_cities` from config
4. Detect city from query text
5. Call `NLPController.chat()` with detected city filter
6. If no results → return `NO_RELEVANT_DOCUMENTS` with friendly message
7. Build sources array (doc name, city, type, score, 300-char excerpt)
8. Call `generate_chat_answer()` with retrieved docs + history
9. Generate related questions
10. Return `CHAT_SUCCESS` with answer, sources, and related questions

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

**Error responses:**
- 400 `INVALID_QUERY` — empty query
- 200 `NO_RELEVANT_DOCUMENTS` — no matching content
- 200 `CHAT_ERROR` — LLM generation failed

---

#### `POST /index/push/{project_id}` — Push to Vector DB (Legacy)

Pulls all chunks from MongoDB for a project, embeds them, and indexes into Qdrant. Supports `do_reset` to clear existing vectors first.

---

#### `GET /index/info/{project_id}` — Collection Info (Legacy)

Returns Qdrant collection info for debugging.

---

#### `POST /index/search/{project_id}` — Project Search (Legacy)

Project-scoped search. Returns raw documents with scores.

---

#### `POST /index/answer/{project_id}` — Project RAG Answer (Legacy)

Project-scoped RAG generation. Uses `answer_rag_question()` which has simpler flow (no reranking, no budget trim, no history).

### 7.4 Schemes (Pydantic Request/Response)

#### `PushRequest` (`nlp.py`)
```python
class PushRequest(BaseModel):
    do_reset: Optional[int] = 0
```

#### `SearchRequest` (`nlp.py`)
```python
class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 5
```

#### `ChatRequest` (`nlp.py`)
```python
class ChatRequest(BaseModel):
    text: str
    limit: Optional[int] = 5
    doc_type: Optional[str] = None
    history: Optional[List[dict]] = None
```

#### `ChatResponse` (`nlp.py`) — unused (responses are manual dicts)
```python
class ChatResponse(BaseModel):
    signal: str
    answer: str
    sources: List[SourceInfo]
    related_questions: List[str]
```

#### `ProcessRequest` (`data.py`)
```python
class ProcessRequest(BaseModel):
    file_id: str = None
    chunk_size: Optional[int] = 500
    overlap_size: Optional[int] = 20
    do_reset: Optional[int] = 0
```

#### `UpdateAssetRequest` (`data.py`)
```python
class UpdateAssetRequest(BaseModel):
    city: str
    doc_type: Optional[str] = None
```

---

## 8. Stores (Providers)

### 8.1 LLM Store (`stores/llm/`)

#### `LLMInterface` (Abstract Base)

Defines the contract for all LLM providers:

| Method | Purpose |
|--------|---------|
| `set_generation_model(model_id)` | Select generation model |
| `set_embedding_model(model_id, embedding_size)` | Select embedding model |
| `generate_text(prompt, chat_history, max_output_tokens, temperature) → str` | Generate text |
| `embed_text(text, document_type) → list[float]` | Generate embedding vector |
| `construct_prompt(prompt, role) → dict` | Format message for the provider's API format |

#### `LLMProviderFactory`

Creates the correct provider based on config:

| Config Value | Provider Created |
|--------------|-----------------|
| `OPENAI` | `OpenAIProvider` |
| `COHERE` | `CoHereProvider` |

#### `OpenAIProvider`

Uses the OpenAI Python client. Compatible with:
- OpenAI API (`https://api.openai.com/v1`)
- Ollama (via OpenAI-compatible proxy at `http://<host>:11434/v1`)
- Any OpenAI-compatible API

Key behavior:
- `process_text(text)`: Truncates to `INPUT_DEFAULT_MAX_CHARACTERS`
- `construct_prompt(prompt, role)`: Returns `{"role": role, "content": text}` format
- `generate_text()`: Appends user message to chat history → calls chat completions
- `embed_text()`: Calls embeddings API → returns vector

#### `CoHereProvider`

Uses the CoHere Python client.

Key differences from OpenAI:
- CoHere uses `"text"` key instead of `"content"` in messages
- Chat uses CoHere's own chat API format
- Embedding supports `input_type` distinction (search_document vs search_query)
- `construct_prompt()` returns `{"role": role, "text": text}`

### 8.2 Rerank Store (`stores/rerank/`)

#### `RerankInterface` (Abstract Base)

| Method | Purpose |
|--------|---------|
| `rerank(query, documents, top_k, model) → list[(index, score)]` | Re-rank documents by relevance to query |

Returns list of `(original_index, relevance_score)` tuples, sorted by score descending, limited to `top_k`.

#### `RerankProviderFactory`

| Config Value | Provider Created |
|--------------|-----------------|
| `OLLAMA` | `OllamaRerankProvider` |
| `CROSS_ENCODER` | `CrossEncoderRerankProvider` |

#### `CrossEncoderRerankProvider` (Default)

Uses `sentence-transformers` `CrossEncoder` model running locally on CPU.

**Behavior:**
- Lazy-loads model on first call (cached in `~/.cache/huggingface/`)
- Default model: `BAAI/bge-reranker-v2-m3`
- Creates `[query, doc]` pairs for each document
- `predict()` returns scores (raw logits, not probabilities)
- Sorts by score descending, returns top_k
- Returns empty list on any exception (graceful fallback)

#### `OllamaRerankProvider` (Alternative)

Calls Ollama's `/api/rerank` endpoint. Requires Ollama server with a rerank-capable model. Returns empty list on 404 or any exception.

### 8.3 Vector DB Store (`stores/vectordb/`)

#### `VectorDBInterface` (Abstract Base)

| Method | Purpose |
|--------|---------|
| `connect()` | Initialize connection |
| `disconnect()` | Close connection |
| `is_collection_existed(name) → bool` | Check collection |
| `list_all_collections() → list` | List collections |
| `get_collection_info(name) → dict` | Collection metadata |
| `delete_collection(name)` | Delete collection |
| `create_collection(name, embedding_size, do_reset)` | Create with indexes |
| `insert_one(name, text, vector, metadata, record_id)` | Insert single |
| `insert_many(name, texts, vectors, metadata, record_ids, batch_size)` | Batch insert |
| `search_by_vector(name, vector, limit, filter) → list[RetrievedDocument]` | Vector search with optional filter |
| `delete_by_filter(name, filter)` | Delete points matching filter |

#### `VectorDBProviderFactory`

| Config Value | Provider Created |
|--------------|-----------------|
| `QDRANT` | `QdrantDBProvider` |

#### `QdrantDBProvider`

**Connection:** `QdrantClient(url, api_key)` — connects to Qdrant Cloud.

**Collection creation:** Creates collection with specified vector size and distance method (cosine/dot). Auto-creates payload indexes on `metadata.project_id`, `metadata.city`, `metadata.doc_type`, `metadata.asset_id` for efficient filtered search.

**Filter syntax:** Converts `{"city": "cairo"}` to Qdrant `Filter(must=[FieldCondition(key="metadata.city", match=MatchValue(value="cairo"))])`.

**Search:** Returns `RetrievedDocument(text, score, metadata)` objects.

### 8.4 TemplateParser (`stores/llm/templates/template_parser.py`)

Loads prompt templates by language, group, and key.

**Behavior:**
1. Look for `locales/{language}/{group}.py` (e.g., `locales/en/rag.py`)
2. If not found, fall back to `default_language`
3. If still not found, return `None`
4. Import the module dynamically using `__import__`
5. Access the requested key attribute
6. Call `Template.substitute(vars)` with provided variables

**Supported groups:** `"rag"` (the only group)

**Supported keys per group:**
- `system_prompt` — System instructions for the LLM
- `document_prompt` — Template for each source document
- `footer_prompt` — Footer with the user's question
- `related_prompt` — Template for generating follow-up questions

---

## 9. City Detection System

The project has three layers of city detection.

### 9.1 `city_mappings.json`

```json
{
  "egypt": ["cairo", "alexandria", "luxor", "aswan", "hurghada", ...],
  "france": ["paris"],
  "japan": ["tokyo"],
  "united arab emirates": ["dubai"],
  "uae": ["dubai"]
}
```

**Note:** The `known_cities` array (24 Egyptian cities) is merged at runtime in the chat route from MongoDB distinct cities + config file.

### 9.2 Detection Layer 1: From Filename (`extract_city_type`)

Parses `{city}_{type}.ext` convention:
- `cairo_restaurants.pdf` → `{"city": "cairo", "doc_type": "restaurants"}`
- `paris_hotels.pdf` → `{"city": "paris", "doc_type": "hotels"}`
- `myfile.pdf` → `{"city": None, "doc_type": None}`

Applied during upload. The form-provided `city`/`doc_type` takes priority over filename parsing.

### 9.3 Detection Layer 2: From Content (`detect_city_from_content`)

Triggered when city is still `"unknown"` after filename parsing.

Logic:
1. Load known_cities from `city_mappings.json`
2. Scan all document text for city names
3. If exactly one city found → use it
4. If no city found, scan for country names and use mapping
5. If multiple cities found or nothing → stay as "unknown"

Applied in both single and multi upload endpoints.

### 9.4 Detection Layer 3: From Query (`detect_city_from_query`)

Triggered on every chat request.

Logic:
1. Merge MongoDB distinct cities from assets + `known_cities` from config into a combined list
2. Check if exactly one known city appears in query text → use as filter
3. If no city matched, check country→city mappings
4. Return `None` for multi-city or no-match → global (unfiltered) search

---

## 10. Data Flows

### 10.1 Upload Flow

```
User uploads file
       │
       ▼
Validate file type, extension, size
       │
       ▼
Save file to disk: assets/files/{project_id}/{unique_id}_{filename}
       │
       ▼
Extract city/type from filename (or use form values)
       │
       ▼
Create Asset record in MongoDB (with city, doc_type in asset_config)
       │
       ▼
Load file content via ProcessController.get_file_content()
       │
       ▼
If city is still "unknown" ──► detect_city_from_content()
  │                               │
  │         city detected?        │
  │            ├── yes ───────────► Update asset_config.city in MongoDB
  │            └── no ────────────► Keep "unknown"
  │
  ▼
Chunk document with metadata {city, doc_type, asset_id}
       │
       ▼
Insert chunks into MongoDB "chunks" collection
       │
       ▼
Return success with file_id, city, doc_type, chunk count
```

Note: The upload flow does NOT automatically push to Qdrant. An admin must use `/index/push/{project_id}` to embed and index the chunks into the vector database.

### 10.2 Chat Flow

```
User sends: { "text": "What restaurants in Cairo?", "history": [...] }
       │
       ▼
Validate non-empty query ──► empty? → 400 INVALID_QUERY
       │
       ▼
Check pure greeting ──► greeting? → Skip search, return welcome
       │
       ▼
Fetch distinct cities from MongoDB + known_cities from config
       │
       ▼
Detect city from query text ──► "cairo" found → filter: {city: "cairo"}
       │
       ▼
NLPController.chat():
   │
   ├─► Embed query via embedding_client
   │
   ├─► Search Qdrant (retrieve 20 with optional city filter)
   │
   ├─► Rerank available? ──► Yes → CrossEncoder rerank → filter >= 0.0
   │                      └── No  → filter by SCORE_THRESHOLD
   │
   └─► Return top 5 documents or None
       │
       ▼
No results? ──► Return NO_RELEVANT_DOCUMENTS
       │
       ▼
Build sources array (doc name, city, score, 300-char excerpt)
       │
       ▼
generate_chat_answer():
   │
   ├─► Build document prompts with source numbers + scores
   ├─► Budget-trim documents to fit INPUT_DEFAULT_MAX_CHARACTERS
   ├─► Construct chat history (system + prior history + docs + footer)
   └─► Call LLM → get answer
       │
       ▼
LLM failed? ──► Return CHAT_ERROR
       │
       ▼
Generate related questions from query + answer
       │
       ▼
Return CHAT_SUCCESS with answer, sources, related questions
```

### 10.3 Reranking Flow

```
Qdrant returns 20 results (sorted by cosine similarity)
       │
       ▼
CrossEncoder takes query + all 20 doc texts
       │
       ▼
Creates 20 [query, doc] pairs
       │
       ▼
Model.predict() → raw logit scores for each pair
       │
       ▼
Sort by score descending
       │
       ▼
Filter: keep only scores >= 0.0 (removes clearly irrelevant)
       │
       ▼
Return top 5 (or configured limit)
       │
       ▼
Each doc.score is overwritten from cosine similarity → cross-encoder logit
```

**Fallback:** If cross-encoder is unavailable or returns empty list, the system falls back to Qdrant's cosine similarity filtered by `SCORE_THRESHOLD`.

### 10.4 Delete/Cleanup Flow

```
DELETE /project/{project_id}
   │
   ├─► Delete chunks from MongoDB (by project_id)
   ├─► Delete assets from MongoDB (by project_id)
   ├─► Delete vectors from Qdrant (by metadata.project_id)
   └─► Delete project from MongoDB

DELETE /file/{file_id}
   │
   ├─► Delete asset from MongoDB
   ├─► Delete chunks from MongoDB (by asset_id)
   └─► Delete vectors from Qdrant (by metadata.asset_id)

DELETE /chunks/{project_id}
   │
   ├─► Delete chunks from MongoDB (by project_id)
   └─► Delete vectors from Qdrant (by metadata.project_id)
   (Keeps assets and project record)
```

---

## 11. Prompt Templates

### English (`locales/en/rag.py`)

#### System Prompt (Rules-based, strict grounding)

```
You are a travel assistant. Your knowledge comes ONLY from the provided sources below.

RULES:
1. Answer ONLY using information EXPLICITLY stated in the provided sources.
2. If the sources do not contain the answer, say: 'I don't have information about that.' Do NOT guess or make up information.
3. Cite the source number when presenting specific facts (prices, locations, hours).
4. If sources only partially answer, state only what is confirmed.
5. Respond in the same language as the user.
6. Keep answers clear, direct, and concise.
```

#### Document Prompt (per source)

```
## Source $doc_num [Relevance: $score]
$chunk_text
```

Variables: `doc_num` (1-based index), `score` (rounded to 3 decimals), `chunk_text`

#### Footer Prompt

```
REMEMBER: Answer ONLY from the provided sources above. If they do not answer the question, say so.
## Question:
$query

## Answer:
```

Variable: `query`

#### Related Questions Prompt

```
Based ONLY on the provided sources, suggest 3-5 follow-up questions the user might ask.
Only suggest questions the sources can actually answer. Return a simple numbered list — nothing else.
## Question:
$query
## Answer:
$answer

## Suggested Questions:
```

Variables: `query`, `answer`

### Arabic (`locales/ar/rag.py`)

Same structure, translated to Arabic. System prompt uses `أنت مساعد سفر` persona with the same 6 rules.

---

## 12. Enums Reference

See [Section 6.3](#63-enums) for complete enum documentation.

---

## 13. Environment Variables Reference

See [Section 4](#4-configuration) for the complete settings table.

**Quick reference for typical configurations:**

| Variable | Dev (Ollama) | Production (OpenAI) |
|----------|--------------|-------------------|
| `GENERATION_BACKEND` | `OPENAI` | `OPENAI` |
| `EMBEDDING_BACKEND` | `OPENAI` | `OPENAI` |
| `OPENAI_API_KEY` | `ollama` | `<your-openai-key>` |
| `OPENAI_API_URL` | `http://192.168.1.8:11434/v1` | `https://api.openai.com/v1` |
| `GENERATION_MODEL_ID` | `qwen2.5:latest` | `gpt-4o` or `gpt-4o-mini` |
| `EMBEDDING_MODEL_ID` | `nomic-embed-text` | `text-embedding-3-small` |
| `EMBEDDING_MODEL_SIZE` | `768` | `1536` |
| `RERANK_BACKEND` | `CROSS_ENCODER` | `CROSS_ENCODER` |
| `VECTOR_DB_BACKEND` | `QDRANT` | `QDRANT` |
| `QDRANT_DB_URL` | `<qdrant-cloud-url>` | `<qdrant-cloud-url>` |
| `QDRANT_DB_API_KEY` | `<qdrant-api-key>` | `<qdrant-api-key>` |
| `MONGODB_URL` | `<atlas-connection-string>` | `<atlas-connection-string>` |
| `MONGODB_DATABASE` | `mini-rag` | `mini-rag` |
| `SCORE_THRESHOLD` | `0.2` | `0.4` |
| `PRIMARY_LANG` | `en` | `en` |
| `INPUT_DEFAULT_MAX_CHARACTERS` | `2048` | `2048` |

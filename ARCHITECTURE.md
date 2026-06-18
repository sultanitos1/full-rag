## mini-rag Architecture & Documentation

This document explains the architecture of `mini-rag`, covering **routes**, **controllers**, **models**, **background tasks**, **LLM/vector DB providers**, **configuration**, and **external services**. It is meant as a companion to the tutorial branches in the README.

---

## 1. High-level overview

**mini-rag** is a minimal but production-style **Retrieval-Augmented Generation (RAG)** backend built with:

- **FastAPI** for the HTTP API.
- **PostgreSQL + SQLAlchemy + Alembic** as the main database.
- **pgvector or Qdrant** as the vector database.
- **OpenAI or Cohere** as LLM backends (generation + embeddings).
- **Celery + Redis/RabbitMQ** for background processing.
- **Prometheus + Grafana + Flower** for monitoring and observability.

### 1.1 Core data flow (end-to-end)

1. **Upload documents**  
   - Client calls `POST /api/v1/data/upload/{project_id}` with a file.  
   - The file is validated and stored on disk as an asset, and metadata is recorded in Postgres.

2. **Process documents into chunks**  
   - Client calls `POST /api/v1/data/process/{project_id}` or `POST /api/v1/data/process-and-push/{project_id}`.  
   - A **Celery worker** reads files from disk, splits them into text chunks, and stores those chunks in Postgres.

3. **Index chunks into vector DB**  
   - Client calls `POST /api/v1/nlp/index/push/{project_id}` or triggers a workflow.  
   - A **Celery task** loads chunks from Postgres, embeds them using the configured LLM embedding model, and inserts them into **pgvector** (Postgres) or **Qdrant**.

4. **Query / RAG answering**  
   - Client calls `POST /api/v1/nlp/index/search/{project_id}` to do pure semantic search, or  
   - `POST /api/v1/nlp/index/answer/{project_id}` to get a RAG-style answer.  
   - The app embeds the query, retrieves similar chunks from the vector DB, formats them into a prompt using templates, and asks the LLM for an answer.

---

## 2. Application entrypoints

### 2.1 `src/main.py` – FastAPI application

```13:61:src/main.py
app = FastAPI()
setup_metrics(app)

async def startup_span():
    settings = get_settings()
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.db_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(app.db_engine, class_=AsyncSession, expire_on_commit=False)
    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=app.db_client)
    app.generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)
    app.embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_MODEL_SIZE)
    app.vectordb_client = vectordb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await app.vectordb_client.connect()
    app.template_parser = TemplateParser(language=settings.PRIMARY_LANG, default_language=settings.DEFAULT_LANG)

async def shutdown_span():
    app.db_engine.dispose()
    await app.vectordb_client.disconnect()

app.on_event("startup")(startup_span)
app.on_event("shutdown")(shutdown_span)

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
```

- **Responsibilities**:
  - Load **configuration** via `get_settings()`.
  - Create the **async SQLAlchemy engine** and `sessionmaker` (`app.db_client`).
  - Initialize:
    - `LLMProviderFactory` → `app.generation_client`, `app.embedding_client`.
    - `VectorDBProviderFactory` → `app.vectordb_client`.
    - `TemplateParser` → `app.template_parser`.
  - Register startup/shutdown handlers.
  - Mount routers for base, data, and NLP routes.

### 2.2 `src/celery_app.py` – Celery application

```10:59:src/celery_app.py
settings = get_settings()

async def get_setup_utils():
    settings = get_settings()
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    db_engine = create_async_engine(postgres_conn)
    db_client = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(config=settings, db_client=db_client)
    generation_client = llm_provider_factory.create(provider=settings.GENERATION_BACKEND)
    generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)
    embedding_client = llm_provider_factory.create(provider=settings.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_MODEL_SIZE)
    vectordb_client = vectordb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
    await vectordb_client.connect()
    template_parser = TemplateParser(language=settings.PRIMARY_LANG, default_language=settings.DEFAULT_LANG)
    return (db_engine, db_client, llm_provider_factory, vectordb_provider_factory,
            generation_client, embedding_client, vectordb_client, template_parser)

celery_app = Celery(
    "minirag",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "tasks.file_processing",
        "tasks.data_indexing",
        "tasks.process_workflow",
        "tasks.maintenance",
    ]
)
```

- **Responsibilities**:
  - Create a **Celery app** configured from env (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, etc.).
  - Provide a shared `get_setup_utils()` used by tasks to:
    - Open a DB engine + session factory.
    - Create LLM + vector DB clients.
    - Init the template parser.
  - Configure:
    - Task routing (`file_processing`, `data_indexing`, `process_workflow`, `maintenance`).
    - Beat schedule (periodic cleanup of old Celery execution records).

---

## 3. Configuration & settings

### 3.1 `src/helpers/config.py` – Settings

```4:57:src/helpers/config.py
class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    FILE_ALLOWED_TYPES: list
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int
    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str
    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str
    OPENAI_API_KEY: str = None
    OPENAI_API_URL: str = None
    COHERE_API_KEY: str = None
    GENERATION_MODEL_ID_LITERAL: List[str] = None
    GENERATION_MODEL_ID: str = None
    EMBEDDING_MODEL_ID: str = None
    EMBEDDING_MODEL_SIZE: int = None
    INPUT_DAFAULT_MAX_CHARACTERS: int = None
    GENERATION_DAFAULT_MAX_TOKENS: int = None
    GENERATION_DAFAULT_TEMPERATURE: float = None
    VECTOR_DB_BACKEND_LITERAL: List[str] = None
    VECTOR_DB_BACKEND : str
    VECTOR_DB_PATH : str
    VECTOR_DB_DISTANCE_METHOD: str = None
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int = 100
    PRIMARY_LANG: str = "en"
    DEFAULT_LANG: str = "en"
    CELERY_BROKER_URL: str = None
    CELERY_RESULT_BACKEND: str = None
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_TASK_TIME_LIMIT: int = 600
    CELERY_TASK_ACKS_LATE: bool = True
    CELERY_WORKER_CONCURRENCY: int = 2
    CELERY_FLOWER_PASSWORD: str = None

    class Config:
        env_file = ".env"

def get_settings():
    return Settings()
```

- **Used by**:
  - `main.py` (app setup).
  - `celery_app.py` (worker setup).
  - Controllers via `BaseController`.
- **Why it exists**:
  - Centralizes app, DB, LLM, vector DB, and Celery configs, so you can switch providers/backends via env without code changes.

---

## 4. HTTP routes (API surface)

### 4.1 Base routes – `src/routes/base.py`

- `APIRouter` with prefix `/api/v1`, tag `api_v1`.
- **Endpoint**:
  - `GET /api/v1/` → returns app name and version from `Settings`.

### 4.2 Data routes – `src/routes/data.py`

**Router**: prefix `/api/v1/data`, tags `["api_v1", "data"]`.

- **`POST /upload/{project_id}`**
  - **Uses**:
    - `ProjectModel` to get or create a project.
    - `DataController.validate_uploaded_file()` to check content type and size.
    - `DataController.generate_unique_filepath()` + `ProjectController.get_project_path()` to decide where to store file.
    - `aiofiles` for async file writing.
    - `AssetModel` + DB `Asset` schema to persist file metadata.
  - **Returns**:
    - A `ResponseSignal` (success/failure) + generated `file_id` stored as an asset name.

- **`POST /process/{project_id}`**
  - Accepts `ProcessRequest` body (chunk size, overlap, `do_reset`, `file_id`).
  - Enqueues **Celery task** `tasks.file_processing.process_project_files`.
  - **Purpose**: read files, chunk them, persist text chunks to Postgres.

- **`POST /process-and-push/{project_id}`**
  - Similar to `/process`, but enqueues a **Celery workflow** (`tasks.process_workflow.process_and_push_workflow`) which:
    1. Runs `process_project_files`.
    2. Then automatically runs `index_data_content` (push to vector DB).

### 4.3 NLP routes – `src/routes/nlp.py`

**Router**: prefix `/api/v1/nlp`, tags `["api_v1", "nlp"]`.

- **`POST /index/push/{project_id}`**
  - Enqueues `tasks.data_indexing.index_data_content`.
  - **Purpose**: read existing chunks from DB, embed them, and index them into vector DB.

- **`GET /index/info/{project_id}`**
  - Uses `ProjectModel` to get project.
  - Instantiates `NLPController` with:
    - `request.app.vectordb_client`
    - `request.app.generation_client`
    - `request.app.embedding_client`
    - `request.app.template_parser`
  - Calls `NLPController.get_vector_db_collection_info()` to fetch collection stats from vector DB.

- **`POST /index/search/{project_id}`**
  - Gets/creates project, then uses `NLPController.search_vector_db_collection()` to:
    - Embed query text.
    - Search vector DB (pgvector or Qdrant).
  - Returns ranked results or an error `ResponseSignal`.

- **`POST /index/answer/{project_id}`**
  - Full RAG pipeline:
    - Get project.
    - Use `NLPController.answer_rag_question()`:
      - Search the vector DB for relevant chunks.
      - Build a prompt using `TemplateParser` templates for `rag` (system/doc/footer prompts).
      - Call `generation_client.generate_text()` (OpenAI/Cohere).
  - Returns:
    - `answer` (LLM output).
    - `full_prompt` (built RAG prompt).
    - `chat_history` (for debugging / inspection).

---

## 5. Controllers (domain/business logic)

All controllers inherit from `BaseController` (not shown here), which provides shared utilities like loading settings and managing filesystem paths.

### 5.1 `DataController` – `src/controllers/DataController.py`

- **Key methods**:
  - `validate_uploaded_file(file: UploadFile)`  
    - Checks MIME type against `FILE_ALLOWED_TYPES`.
    - Checks size against `FILE_MAX_SIZE`.
    - Returns `(bool, ResponseSignal)` to routes.
  - `generate_unique_filepath(orig_file_name, project_id)`  
    - Uses `ProjectController.get_project_path()` to find directory.
    - Sanitizes filename, adds random prefix to avoid collisions.
  - `get_clean_file_name(orig_file_name)`  
    - Normalizes filename (remove special chars, replace spaces).

- **Used by**:
  - `POST /api/v1/data/upload/{project_id}`.

### 5.2 `ProjectController` – `src/controllers/ProjectController.py`

- **Key method**:
  - `get_project_path(project_id)`  
    - Ensures the project directory exists under the configured `files_dir`.
    - Returns path used to store project files.

- **Used by**:
  - `DataController.generate_unique_filepath()`.
  - `ProcessController` for loading files.

### 5.3 `ProcessController` – `src/controllers/ProcessController.py`

- **Responsibilities**:
  - Load project files from disk and split them into **chunks** ready for indexing.

- **Key methods**:
  - `get_file_loader(file_id)`  
    - Picks appropriate loader based on file extension:
      - `.txt` → `TextLoader`.
      - `.pdf` → `PyMuPDFLoader`.
  - `get_file_content(file_id)`  
    - Uses loader to return a list of LangChain document objects.
  - `process_file_content(file_content, file_id, chunk_size, overlap_size)`  
    - Runs `process_simpler_splitter()` to split raw text into custom `Document` chunks (`@dataclass`).
  - `process_simpler_splitter(texts, metadatas, chunk_size, splitter_tag="\n")`  
    - Simple, line-based splitter to create chunk-sized pieces of text.

- **Used by**:
  - Celery task `_process_project_files()` in `tasks/file_processing.py`.

### 5.4 `NLPController` – `src/controllers/NLPController.py`

- **Constructor dependencies**:
  - `vectordb_client` (pgvector or Qdrant).
  - `generation_client` (OpenAI/Cohere wrapper).
  - `embedding_client` (OpenAI/Cohere wrapper).
  - `template_parser` (RAG prompt templates).

- **Key responsibilities**:
  - **Vector DB collection management**:
    - `create_collection_name(project_id)` → base naming scheme.
    - `reset_vector_db_collection(project)` → drop collection.
    - `get_vector_db_collection_info(project)` → introspect vector DB.
  - **Indexing**:
    - `index_into_vector_db(project, chunks, chunks_ids, do_reset)`  
      - Embeds chunk texts using `embedding_client.embed_text()`.
      - Ensures collection exists via `vectordb_client.create_collection()`.
      - Bulk inserts via `vectordb_client.insert_many()`.
  - **Semantic search**:
    - `search_vector_db_collection(project, text, limit)`  
      - Embeds query as a vector.
      - Uses `vectordb_client.search_by_vector()` to retrieve results.
  - **RAG answering**:
    - `answer_rag_question(project, query, limit)`  
      - Uses semantic search to fetch chunks.
      - Builds prompts using `TemplateParser` (`rag.system_prompt`, `rag.document_prompt`, `rag.footer_prompt`).
      - Calls `generation_client.generate_text()` with chat history and full prompt.

- **Used by**:
  - NLP routes (`/index/info`, `/index/search`, `/index/answer`).
  - Celery tasks (`data_indexing`, `file_processing` indirectly).

---

## 6. Data models & database layer

### 6.1 High-level structure

- `src/models/BaseDataModel.py` – common base for data models, primarily to hold `db_client`.
- `src/models/db_schemes/minirag/schemes/*.py` – SQLAlchemy models for:
  - `Project`, `Asset`, `DataChunk`, `CeleryTaskExecution`, etc.
- `src/models/*.py` – high-level data-access models (repositories):
  - `ProjectModel`, `ChunkModel`, `AssetModel`.

### 6.2 `ProjectModel` – `src/models/ProjectModel.py`

- **Key methods**:
  - `create_project(project: Project)` – INSERT project row.
  - `get_project_or_create_one(project_id)` – idempotent fetch-or-create pattern.
  - `get_all_projects(page, page_size)` – simple pagination.

- **Used by**:
  - Routes and tasks whenever a project context is required.

### 6.3 `ChunkModel` – `src/models/ChunkModel.py`

- **Key methods**:
  - `create_chunk(chunk: DataChunk)` – insert single chunk.
  - `insert_many_chunks(chunks, batch_size)` – batch insert; used by file processing.
  - `delete_chunks_by_project_id(project_id)` – cleanup before re-indexing.
  - `get_poject_chunks(project_id, page_no, page_size)` – paginated retrieval for indexing.
  - `get_total_chunks_count(project_id)` – used to initialize progress bar.

- **Used by**:
  - `tasks.file_processing._process_project_files()` (insert chunks).
  - `tasks.data_indexing._index_data_content()` (load chunks for indexing).

### 6.4 `AssetModel` – `src/models/AssetModel.py`

- **Key methods**:
  - `create_asset(asset: Asset)` – insert new file asset record.
  - `get_all_project_assets(asset_project_id, asset_type)` – list files for a project.
  - `get_asset_record(asset_project_id, asset_name)` – find specific file by name.

- **Used by**:
  - `routes.data` during upload and processing.
  - `tasks.file_processing` to know which files belong to a project.

### 6.5 Enums – `src/models/enums/*.py`

- `ResponseEnums.py` – `ResponseSignal` values used across routes/tasks as standardized response codes.
- `AssetTypeEnum.py` – identifies type of asset (file, etc.).
- `ProcessingEnum.py` – supported file extensions for processing.
- `DataBaseEnum.py` – (legacy) DB type enums.

---

## 7. Background tasks (Celery)

### 7.1 File processing – `src/tasks/file_processing.py`

- **Task**: `process_project_files` (Celery task wrapper).
- **Core coroutine**: `_process_project_files(...)`

**Responsibilities**:

- Use `get_setup_utils()` to obtain:
  - DB engine + db_client.
  - LLM provider + generation and embedding clients.
  - Vector DB client.
  - Template parser.
- Use `IdempotencyManager` to:
  - Avoid re-processing identical tasks within a time limit.
  - Track task status and results in `CeleryTaskExecution` table.
- Resolve **project** (`ProjectModel`) and **assets** (`AssetModel`).
- Load file content via `ProcessController`.
- Convert content into `DataChunk` records and insert via `ChunkModel`.
- Optionally reset:
  - Vector DB collection for the project.
  - Existing chunks in DB.
- Clean up DB engine and vector DB client at the end.

### 7.2 Data indexing – `src/tasks/data_indexing.py`

- **Task**: `index_data_content` (Celery task).
- **Core coroutine**: `_index_data_content(project_id, do_reset)`.

**Responsibilities**:

- Resolve project, ensure it exists.
- Use `ChunkModel` to:
  - Page through chunks with `get_poject_chunks`.
  - Track total chunk count for a progress bar (`tqdm`).
- Use `NLPController.index_into_vector_db()` to:
  - Create or reset the collection.
  - Embed and insert chunk batches into vector DB via `vectordb_client`.

### 7.3 Workflow – `src/tasks/process_workflow.py`

- **Task**: `process_and_push_workflow`
  - Uses `celery.chain` to:
    1. Run `process_project_files`.
    2. Then run `push_after_process_task`, which calls `_index_data_content()` directly.
  - Returns a workflow ID and list of tasks for tracking.

- **Task**: `push_after_process_task`
  - Takes the result of file processing and immediately starts indexing.

### 7.4 Maintenance – `src/tasks/maintenance.py`

- **Task**: `clean_celery_executions_table`
  - Uses `IdempotencyManager.cleanup_old_tasks()` to delete stale execution records (controlled by retention period).

---

## 8. LLM providers & template system

### 8.1 LLM provider factory – `src/stores/llm/LLMProviderFactory.py`

- Reads `GENERATION_BACKEND` and `EMBEDDING_BACKEND` from `Settings`.
- Provides `create(provider: str)`:
  - If `OPENAI`, returns `OpenAIProvider`.
  - If `COHERE`, returns `CoHereProvider`.

### 8.2 `OpenAIProvider` – `src/stores/llm/providers/OpenAIProvider.py`

- Wraps the official `openai` SDK (Chat Completions + embeddings).
- **Key methods**:
  - `set_generation_model(model_id)` – sets chat model.
  - `set_embedding_model(model_id, embedding_size)` – sets embedding model and dimension.
  - `process_text(text)` – truncates text to max chars.
  - `generate_text(prompt, chat_history, ...)` – calls `client.chat.completions.create`.
  - `embed_text(text, document_type)` – calls `client.embeddings.create` and returns vectors.
  - `construct_prompt(prompt, role)` – convenience for chat history.

### 8.3 `CoHereProvider` – `src/stores/llm/providers/CoHereProvider.py`

- Wraps the `cohere` SDK.
- Mirrors `OpenAIProvider`’s interface:
  - `generate_text()` via `client.chat`.
  - `embed_text()` via `client.embed` with `input_type` (document vs query).
  - `construct_prompt()` to build chat history items.

### 8.4 Template parser – `src/stores/llm/templates/template_parser.py`

- Resolves language-specific template modules, e.g.:
  - `stores.llm.templates.locales.en.rag`.
  - `stores.llm.templates.locales.ar.rag`.
- `get(group, key, vars={})`:
  - Imports the module for the group (e.g. `"rag"`).
  - Returns the `Template` string (Python `string.Template`) filled with `vars`.
- **Used by**:
  - `NLPController.answer_rag_question()` to build:
    - System prompt.
    - Document prompt per retrieved chunk.
    - Footer/user prompt.

---

## 9. Vector DB providers

### 9.1 VectorDB factory – `src/stores/vectordb/VectorDBProviderFactory.py`

- Reads `VECTOR_DB_BACKEND`, `VECTOR_DB_PATH`, `VECTOR_DB_DISTANCE_METHOD`, `EMBEDDING_MODEL_SIZE`, etc.
- `create(provider)`:
  - If `QDRANT`, returns `QdrantDBProvider` configured for local disk path.
  - If `PGVECTOR`, returns `PGVectorProvider` configured with SQLAlchemy `db_client`.

### 9.2 Qdrant provider – `src/stores/vectordb/providers/QdrantDBProvider.py`

- Wraps `qdrant-client`.
- **Key capabilities**:
  - `connect() / disconnect()` – manage `QdrantClient`.
  - `create_collection(collection_name, embedding_size, do_reset)` – create or reset a Qdrant collection.
  - `insert_many(...)` – batch insert text + vector + metadata records.
  - `search_by_vector(...)` – returns `RetrievedDocument` objects with `text` and `score`.

### 9.3 PGVector provider – `src/stores/vectordb/providers/PGVectorProvider.py`

- Stores embeddings in **Postgres** using the `vector` extension and custom tables.
- **Key responsibilities**:
  - `connect()` – ensures the `vector` extension exists.
  - `create_collection(collection_name, embedding_size, do_reset)` – creates a new table for the collection if needed.
  - `insert_many(...)` – bulk-INSERT rows with text, vector (as vector type), metadata JSON, and `chunk_id`.
  - `create_vector_index()` – creates an index when data volume exceeds threshold.
  - `search_by_vector(...)` – uses vector similarity SQL (`<=>`) to rank results.

---

## 10. Utilities & observability

### 10.1 Idempotency manager – `src/utils/idempotency_manager.py`

- Tracks **Celery task executions** in the DB to avoid duplicate work.
- **Key methods**:
  - `create_task_record(...)` – insert new execution row with hashed args.
  - `should_execute_task(...)` – decides whether a task should actually run:
    - Skip if an identical successful execution already exists.
    - Allow re-run if the previous one is stuck or failed.
  - `update_task_status(...)` – update status + result JSON.
  - `cleanup_old_tasks(...)` – delete old entries.

### 10.2 Metrics – `src/utils/metrics.py`

- Adds **Prometheus middleware** to FastAPI:
  - `REQUEST_COUNT` – per method/endpoint/status.
  - `REQUEST_LATENCY` – request duration per method/endpoint.
- Exposes `/TrhBVe_m5gg2002_E5VVqS` as the metrics endpoint (hidden from OpenAPI).

---

## 11. External services and why they’re used

- **PostgreSQL + pgvector**:
  - Stores **projects**, **assets**, **chunks**, and **celery task executions**.
  - pgvector tables store dense embedding vectors efficiently in the same DB.
- **Qdrant** (optional alternative to pgvector):
  - Dedicated high-performance vector DB when you don’t want to couple vectors to Postgres.
- **OpenAI / Cohere**:
  - Provide:
    - **Text embeddings** for semantic search.
    - **LLM completions/chat** for generating final RAG answers.
- **Celery + Redis/RabbitMQ**:
  - Offload heavy work (file reading, chunking, embedding, indexing) from HTTP requests.
  - Support retries, scheduling, and workflows.
- **Prometheus + Grafana**:
  - Monitor request rate, latency, and errors.
  - Used together with `starlette-exporter` and `prometheus-client`.
- **Flower**:
  - Web UI for monitoring **Celery workers**, queues, and tasks.

---

## 12. How to extend or customize

- **Change LLM provider or models**:
  - Update env: `GENERATION_BACKEND`, `EMBEDDING_BACKEND`, `GENERATION_MODEL_ID`, `EMBEDDING_MODEL_ID`, etc.
- **Change vector DB backend**:
  - Switch `VECTOR_DB_BACKEND` between `PGVECTOR` and `QDRANT`.
- **Add new routes**:
  - Create a new router in `src/routes/`, a matching controller in `src/controllers/`, and wire it into `main.py`.
- **Add new file types**:
  - Extend `ProcessingEnum` and update `ProcessController.get_file_loader()` to support new loaders.

This architecture is intentionally modular: **routes** are thin, **controllers** hold business logic, **models** isolate DB access, **providers** abstract LLM/vector services, and **Celery tasks** own long-running workflows. This separation makes the project easier to understand, test, and extend.


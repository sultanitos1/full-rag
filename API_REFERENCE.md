## mini-rag API Reference Cheat Sheet

This file summarizes the main HTTP routes and flows of the `mini-rag` service.

---

## 1. End-to-end flow

### 1.1 Upload file

- **Endpoint**: `POST /api/v1/data/upload/{project_id}`
- **Body**: `multipart/form-data` with field `file`
- **What happens**:
  - Validates size/type.
  - Saves file under `files/{project_id}/...`.
  - Creates an `Asset` row in Postgres.
  - **Returns**: `file_id` (used in later steps).

### 1.2 Split file into chunks (store in DB)

- **Endpoint**: `POST /api/v1/data/process/{project_id}`
- **Body (JSON)** `ProcessRequest`:
  - `file_id: string | null` (if null, process all files of project)
  - `chunk_size: int`
  - `overlap_size: int`
  - `do_reset: int` (1 = clear old chunks/vectors first)
- **What happens**:
  - Celery task `tasks.file_processing.process_project_files`:
    - Loads file(s) from disk.
    - Splits content into chunks.
    - Stores chunks as `DataChunk` rows in Postgres.
  - **Returns**: Celery `task_id` for tracking.

### 1.3 Index chunks into vector DB

#### Option A – Separate step

- **Endpoint**: `POST /api/v1/nlp/index/push/{project_id}`
- **Body (JSON)** `PushRequest`:
  - `do_reset: int` (1 = recreate collection)
- **Task**: `tasks.data_indexing.index_data_content`
  - Reads chunks from Postgres.
  - Embeds them (OpenAI/Cohere).
  - Inserts embeddings into **pgvector** or **Qdrant**.

#### Option B – Combined workflow

- **Endpoint**: `POST /api/v1/data/process-and-push/{project_id}`
- **Body**: same as `/process`
- **Workflow**: `tasks.process_workflow.process_and_push_workflow`
  - Runs file processing then indexing automatically.
- **Returns**: `workflow_id` and list of tasks.

### 1.4 Check index status

- **Endpoint**: `GET /api/v1/nlp/index/info/{project_id}`
- **What happens**:
  - Asks vector DB for collection info (record count, etc.).
  - **Returns**: basic stats about that project’s collection.

### 1.5 Semantic search only

- **Endpoint**: `POST /api/v1/nlp/index/search/{project_id}`
- **Body (JSON)** `SearchRequest`:
  - `text: string` (query)
  - `limit: int` (top-k)
- **What happens**:
  - Embeds query.
  - Searches vector DB.
  - **Returns**: list of `{ text, score }` from `RetrievedDocument`.

### 1.6 Full RAG answer

- **Endpoint**: `POST /api/v1/nlp/index/answer/{project_id}`
- **Body (JSON)** `SearchRequest`:
  - `text: string` (question)
  - `limit: int` (how many chunks to use)
- **What happens**:
  - Does semantic search as above.
  - Builds RAG prompt from templates (`rag.system_prompt`, per-doc prompt, footer with query).
  - Calls LLM (OpenAI/Cohere) to generate final answer.
  - **Returns**:
    - `answer` (LLM response),
    - `full_prompt` (built RAG prompt),
    - `chat_history`.

---

## 2. Route reference by base path

### 2.1 `GET /api/v1/`

- **Purpose**: Basic health/info.
- **Returns**: `{ "app_name", "app_version" }` from settings.

### 2.2 `/api/v1/data/*`

#### `POST /api/v1/data/upload/{project_id}`

- **Input**: file upload as `multipart/form-data`.
- **Uses**:
  - `DataController` (validation + filename).
  - `ProjectModel`, `AssetModel`.
- **Output**: upload signal + `file_id`.

#### `POST /api/v1/data/process/{project_id}`

- **Input**: `ProcessRequest` JSON.
- **Uses**:
  - Celery task `process_project_files`.
- **Output**: processing signal + `task_id`.

#### `POST /api/v1/data/process-and-push/{project_id}`

- **Input**: `ProcessRequest` JSON.
- **Uses**:
  - Celery workflow `process_and_push_workflow`.
- **Output**: workflow started + `workflow_task_id`.

### 2.3 `/api/v1/nlp/*`

#### `POST /api/v1/nlp/index/push/{project_id}`

- **Input**: `PushRequest` (`do_reset`).
- **Uses**:
  - Celery task `index_data_content`.
- **Output**: push signal + `task_id`.

#### `GET /api/v1/nlp/index/info/{project_id}`

- **Uses**:
  - `ProjectModel`, `NLPController.get_vector_db_collection_info`.
- **Output**: collection info + signal.

#### `POST /api/v1/nlp/index/search/{project_id}`

- **Input**: `SearchRequest` (`text`, `limit`).
- **Uses**:
  - `NLPController.search_vector_db_collection` → embedding client → vector DB.
- **Output**: search signal + `results`.

#### `POST /api/v1/nlp/index/answer/{project_id}`

- **Input**: `SearchRequest` (`text`, `limit`).
- **Uses**:
  - `NLPController.answer_rag_question` → embedding + vector DB + templates + generation client.
- **Output**: RAG answer signal + `answer`, `full_prompt`, `chat_history`.


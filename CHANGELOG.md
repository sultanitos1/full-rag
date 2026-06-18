# Changelog

## [0.1.0] - 2026-06-07

### Added
- **Global RAG chat** — `POST /api/v1/nlp/chat` searches a single Qdrant collection, no `project_id` required
- **City/doc_type filtering** — chat accepts optional `city` and `doc_type` params to narrow results
- **Auto-detection of city/type** on upload — parses `{city}_{type}.pdf` filenames; admin can override
- **Auto city detection from query** — `detect_city_from_query()` matches known cities first, then country→city mapping; returns `None` for multi-city queries (falls to global search)
- **Admin endpoints:**
  - `PUT /api/v1/data/asset/{asset_id}` — edit city/type on an asset
  - `GET /api/v1/data/assets/uncategorized` — list assets with unknown city
  - `GET /api/v1/data/cities` — list distinct city values
  - `POST /api/v1/data/cities` — add a city placeholder
  - `DELETE /api/v1/data/project/{project_id}` — full project cleanup
  - `DELETE /api/v1/data/file/{file_id}` — single file/asset cleanup
  - `DELETE /api/v1/data/chunks/{project_id}` — chunks + vectors only
- **Multi-file upload** — `POST /api/v1/data/upload-multi`; auto-detects project from `{city}_{type}.pdf`, distributes to city projects, returns per-file results
- **CSV/DOCX file support** — new extensions alongside PDFs
- **Reranking module** — `stores/rerank/` with interface, factory, `OllamaRerankProvider`; retrieves 20, reranks (when available), threshold → top 5
- **Score threshold** — `SCORE_THRESHOLD=0.4` filters low-relevance chunks; configurable in `.env`
- **Conversation history** — `history` field in ChatRequest; frontend sends last N turns; backend is stateless
- **Related questions** — `generate_related_questions()` returns up to 5 follow-ups
- **Friendlier responses** — human-readable `message` field alongside `signal`; sources show filename, 300-char excerpt, rounded score
- **Qdrant payload indexes** — auto-created on `metadata.*` fields during collection init
- **city_mappings.json** — config file mapping countries to cities (egypt→cairo, japan→tokyo, france→paris, uae→dubai)
- **Postman collection** — `src/assets/mini-rag-app.postman_collection.json`
- **CrossEncoderRerankProvider** — new Python cross-encoder reranker using `sentence-transformers`; replaces broken Ollama `/api/rerank`; loads `BAAI/bge-reranker-v2-m3` on first use; CPU inference, no server dependency

### Changed
- **NLPController** — rewritten for global single-collection approach; added `chat()`, `detect_city_from_query()`, `generate_chat_answer()`, `generate_related_questions()`, delete/payload methods
- **QdrantDBProvider** — filter-based search and delete; metadata in `RetrievedDocument`; payload indexes on collection init
- **VectorDBInterface** — extended `search_by_vector` with optional `filter`; added `delete_by_filter`
- **DataController** — added `extract_city_type()`; `validate_uploaded_file()` now checks both extension and MIME type
- **ProcessController** — CSV/DOCX loaders added; metadata passed through to chunk creation
- **AssetModel** — added `update_asset_city()`, `get_uncategorized_assets()`, `delete_asset_by_id()`, `delete_assets_by_project_id()`
- **ChunkModel** — added `delete_chunks_by_asset_id()`; fixed typo `get_poject_chunks` → `get_project_chunks`
- **ProjectModel** — added `delete_project()`
- **Config** — `chunk_size` default 100 → 500; added `SCORE_THRESHOLD`, `RERANK_BACKEND`, `RERANK_MODEL_ID`, `CITY_MAPPINGS_PATH`; `GENERATION_DEFAULT_MAX_TOKENS` 200 → 500; `INPUT_DEFAULT_MAX_CHARACTERS` 1024 → 2048
- **Upload endpoint** — auto-chunks after saving; accepts `chunk_size`/`overlap_size` Form params; returns `inserted_chunks`
- **Schemas** — `ChatRequest` now has `history` instead of `session_id`; `ChatResponse` has `message`, `related_questions`; `UpdateAssetRequest` added
- **Templates** — EN/AR rewritten as local tour guide persona; all prompts simplified for model-agnostic use
- **ResponseSignals** — added `CHAT_SUCCESS`, `CHAT_ERROR`, `NO_RELEVANT_DOCUMENTS`, `DELETE_SUCCESS`, `DELETE_ERROR`, `CITY_UPDATE_SUCCESS`, `MULTI_UPLOAD_*`
- **ProcessingEnums** — added `CSV`, `DOCX`
- **Ollama** — upgraded 0.18.2 → 0.30.6
- **Requirements** — added `python-docx`, `docx2txt`

### Removed
- **Greeting detection** — `is_greeting_query()`, `is_greeting_query_llm()`, `greeting_classifier_prompt`, `greeting_prompt` templates, and all associated code
- **Session management** — `_sessions` dict and `session_id` removed from both endpoint and schema
- **`city` field from ChatRequest** — city is now auto-detected from query text
- **Location mention guard** — `query_mentions_location()` and route-level guard removed (was causing false positives)

### Fixed
- **Missing import** — added `NLPController` import to `routes/data.py` (caused 500 on all delete endpoints)
- **POST /cities** — changed from query param to JSON body (`{"city_name": "paris"}`)
- **Typo** — `get_poject_chunks` → `get_project_chunks` in ChunkModel and routes
- **Upload + process flow** — upload returns MongoDB `_id`; process endpoint now accepts it correctly
- **DOCX upload** — added `docx2txt` dependency (was `ModuleNotFoundError`)

### Legacy (kept for backward compatibility)
- `POST /api/v1/nlp/index/push/{project_id}`
- `POST /api/v1/nlp/index/search/{project_id}`
- `POST /api/v1/nlp/index/answer/{project_id}`
- `GET /api/v1/nlp/index/info/{project_id}`
- `POST /api/v1/data/upload/{project_id}`
- `POST /api/v1/data/process/{project_id}`

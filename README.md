# AWS ACU Chatbot

AWS ACU Chatbot is a container-first university assistant backend built with Django, Ollama, and RAG patterns. It is designed to answer student and applicant questions using institution content with source-aware responses and citation-ready metadata.

## What this project does

- Serves a Django backend API for chatbot features
- Uses Ollama for LLM inference and embedding generation
- Uses a vector store flow for retrieval-augmented generation (RAG)
- Stores application data and chat history in PostgreSQL
- Supports container networking and runtime via Docker Compose

## Architecture (current)

- `django-web`: Main backend service
- `ollama`: LLM + embedding model runtime
- `db`: PostgreSQL for relational data/chat history
- `backend/chromadb-data`: Local persisted vector store directory mounted into the backend container

## Installation & setup

### Prerequisites

- Docker Desktop (with Docker Compose)
- GPU support for Ollama models (recommended)

### 1) Clone the repository

```bash
git clone https://github.com/Erenimo3442/aws_acu_chatbot
cd aws_acu_chatbot
```

### 2) Configure environment

- Create/update `.env` at repo root.
- Confirm important values:
  - `OLLAMA_BASE_URL=http://ollama:11434`
  - `ACADEMIC_AGENT_MODEL_ID=<chat-model-tag>`
  - `OLLAMA_EMBEDDING_MODEL_ID=<embedding-model-tag>`
  - `VECTOR_STORE_PERSIST_DIR=chromadb-data`
  - `API_RATE_LIMIT_CHAT_LIMIT=10`
  - `API_RATE_LIMIT_CHAT_WINDOW_SECONDS=60`
  - `API_RATE_LIMIT_FEEDBACK_LIMIT=30`
  - `API_RATE_LIMIT_FEEDBACK_WINDOW_SECONDS=60`
  - `API_RATE_LIMIT_INGEST_LIMIT=5`
  - `API_RATE_LIMIT_INGEST_WINDOW_SECONDS=60`

### 3) Build and start services

```bash
docker compose up -d --build
```

### 4) Pull required Ollama models

```bash
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama pull nomic-embed-text-v2-moe
```

## Development notes

- This repo is container-first; run ingestion/query flows in containers.
- Host execution may fail for service hostnames such as `ollama`.
- Keep environment variables aligned with Docker networking.

## API contract quick reference (v1)

- Auth/access matrix: `backend/README.md`.
- Full endpoint contract: `backend/README_API_CONTRACT_V1.md`.
- OpenAPI spec: `backend/openapi.v1.yaml`.
- Standard error envelope for all errors:

```json
{
  "ok": false,
  "error": {"code": "...", "message": "...", "details": [], "retryable": false},
  "meta": {"request_id": "req_...", "timestamp": "2026-03-24T12:00:00Z"}
}
```

## Future objectives

### RAG quality and reliability

- Improve chunking strategy and retrieval ranking quality
- Add evaluation datasets and automated retrieval/answer quality checks
- Improve citation consistency and source drill-down coverage

### Data ingestion and web scraping

- Build robust web scraping/connector pipelines for university sources
- Add content versioning, change detection, and idempotent re-ingestion
- Add quality checks for stale, duplicate, or malformed content

### Product API and security

- Finalize v1 chatbot API contracts (`/chat`, `/sessions`, `/feedback`, `/sources`, `/ingest`)
- Implement role-based access (anonymous/student/admin/internal)
- Add request tracing, rate limiting, and operational observability

### Platform and scalability

- Strengthen backup/restore for PostgreSQL and vector data
- Introduce async ingestion jobs and retries
- Prepare production deployment profile and CI/CD hardening

# Movie Finder — Backend

AI-powered movie discovery and Q&A. Describe a film you half-remember — the system searches a vector-embedded movie dataset, enriches candidates with live IMDb data, and answers follow-up questions once you've confirmed your pick.

---

## How it works

```
User describes a movie
        │
        ▼
  [RAG Search] ──── Qdrant Cloud (vector store)
        │
        ▼
  [IMDb Enrichment] ── live ratings, credits, metadata via imdbapi.dev
        │
        ▼
  [Validation] ── deduplicate, filter low-confidence
        │
        ▼
  [Presentation] ── ranked candidate list → user
        │
   ┌────┴─────────────────┐
   │ user confirms        │ user says "none match"
   ▼                      ▼
[Q&A Agent]         [Refinement] ── rebuild query → RAG Search
(answers anything          │
 about the film)     max 3 cycles → dead end
```

---

## Repository structure

This is a **multi-repo monorepo** — the backend root integrates three independent submodule repos, each owned by a separate team.

| Repo | Path | Team | Description |
|------|------|------|-------------|
| [movie-finder-backend](.) | `/` | App / Backend | Integration root + FastAPI app |
| [movie-finder-chain](chain/) | `chain/` | AI Engineering | LangGraph multi-agent pipeline |
| [imdbapi-client](imdbapi/) | `imdbapi/` | IMDb API | Async IMDb REST API client |
| [movie-finder-rag](rag_ingestion/) | `rag_ingestion/` | AI / Data Engineering | Dataset ingestion → Qdrant |

```
backend/
├── app/                  ← FastAPI application (auth, chat, sessions)
│   ├── pyproject.toml
│   └── src/app/
│       ├── main.py           FastAPI + lifespan + /health
│       ├── config.py         AppConfig (Pydantic Settings)
│       ├── dependencies.py   Shared FastAPI dependencies
│       ├── routers/
│       │   ├── auth.py       POST /auth/register, /login, /refresh, /logout
│       │   └── chat.py       POST/GET /chat — streaming AI conversation
│       ├── auth/             JWT middleware + models
│       └── session/
│           └── store.py      PostgreSQL session store (asyncpg)
├── chain/                ← git submodule: movie-finder-chain
├── imdbapi/              ← git submodule: imdbapi-client
├── rag_ingestion/        ← git submodule: movie-finder-rag
├── scripts/
│   └── migrate_sqlite_to_postgres.py  ← one-time SQLite → PostgreSQL migration
├── Dockerfile            ← production container (multi-stage, uv + python:3.13-slim)
├── Jenkinsfile           ← CI/CD pipeline (lint → test → build → deploy to Azure)
├── Makefile              ← developer shortcuts (see make help)
├── INTEGRATION.md        ← team workflow & secret sharing guide
└── CONTRIBUTING.md       ← branching, PRs, release process
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.13+ | [python.org](https://www.python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| git | 2.20+ | system package manager |

---

## Quick start (backend standalone)

The backend runs independently — you only need a local PostgreSQL container and the API keys from your `.env`.

```bash
# 1. Clone with all submodules
git clone --recurse-submodules https://github.com/aharbii/movie-finder-backend.git
cd movie-finder-backend

# 2. Automated setup (installs deps, pre-commit hooks, copies .env)
make setup

# 3. Fill in your API keys in .env
#    Required: APP_SECRET_KEY, DATABASE_URL, ANTHROPIC_API_KEY, OPENAI_API_KEY,
#              QDRANT_ENDPOINT, QDRANT_API_KEY (from RAG team)
$EDITOR .env

# 4. Start local PostgreSQL (standalone — no full-stack compose needed)
make db-start
#    → sets DATABASE_URL=postgresql://movie_finder:devpassword@localhost:5432/movie_finder # pragma: allowlist secret

# 5. Migrate existing dev data (if you have movie_finder.db from a previous SQLite run)
make db-migrate

# 6. Start the dev server
make run-dev
#    → http://localhost:8000  (hot-reload, reads .env automatically)

# 7. Verify everything works
make check
```

---

## Common development commands

```bash
make setup          # first-time setup: deps + pre-commit + .env
make db-start       # start local PostgreSQL container (port 5432)
make db-stop        # stop and remove the container
make db-reset       # wipe data and restart (fresh empty database)
make db-migrate     # migrate SQLite dev data → PostgreSQL
make run-dev        # start FastAPI dev server with hot-reload
make lint           # ruff check/format + mypy
make lint-fix       # auto-fix ruff violations
make test           # pytest (all projects)
make test-app       # pytest (app only — requires make db-start)
make submodules     # pull latest from all submodule remotes
make clean          # remove __pycache__, .pytest_cache, etc.
```

See `make help` for the full list.

---

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_SECRET_KEY` | ✅ | JWT signing secret (`openssl rand -hex 32`) |
| `DATABASE_URL` | ✅ | PostgreSQL connection URL |
| `ANTHROPIC_API_KEY` | ✅ | Claude models for chain |
| `OPENAI_API_KEY` | ✅ | OpenAI embeddings |
| `QDRANT_ENDPOINT` | ✅ | Qdrant Cloud cluster URL (from RAG team) |
| `QDRANT_API_KEY` | ✅ | Qdrant Cloud API key (from RAG team) |
| `QDRANT_COLLECTION` | ✅ | Collection name (from RAG team) |
| `LANGSMITH_API_KEY` | ✗ | Optional — LangSmith tracing |

> **Note:** The IMDb API (`imdbapi.dev`) requires no authentication.
> `IMDBAPIClient` calls it directly with no API key.

---

## Databases

The project uses **two separate data stores** for distinct purposes:

| Store | Technology | Purpose |
|-------|-----------|---------|
| Vector store | **Qdrant Cloud** | RAG semantic search over movie plots |
| Relational DB | **PostgreSQL** | Users, sessions, chat messages |

Qdrant is always the production cluster — there is no local Qdrant container. The PostgreSQL database runs locally via `make db-start` for development, and as Azure Database for PostgreSQL Flexible Server in production.

---

## Working on a specific subproject

Each project can run fully independently. Jump to its README:

- **[chain/README.md](chain/README.md)** — AI pipeline: how nodes work, how to run examples, testing strategy
- **[imdbapi/README.md](imdbapi/README.md)** — IMDb client: endpoint coverage, pagination, error handling
- **[rag_ingestion/README.md](rag_ingestion/README.md)** — ingestion pipeline: dataset download, embedding, Qdrant load
- **[app/README.md](app/README.md)** — FastAPI layer: auth, chat, session management

---

## Team onboarding by role

| I am… | Start here |
|-------|-----------|
| New to the whole project | This README → [INTEGRATION.md](INTEGRATION.md) → your team's README |
| AI Engineering (chain) | [chain/README.md](chain/README.md) → [chain/CONTRIBUTING.md](chain/CONTRIBUTING.md) |
| IMDb API team | [imdbapi/README.md](imdbapi/README.md) → [imdbapi/CONTRIBUTING.md](imdbapi/CONTRIBUTING.md) |
| AI / Data Engineering (RAG) | [rag_ingestion/README.md](rag_ingestion/README.md) → [rag_ingestion/CONTRIBUTING.md](rag_ingestion/CONTRIBUTING.md) |
| App / Backend | [app/README.md](app/README.md) → [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## CI/CD

Pipelines run on Jenkins. Every repo has its own `Jenkinsfile`:

| Pipeline | Triggers | Key stages |
|----------|----------|------------|
| backend (this repo) | PR, push to main, v* tag | lint → test (with PG sidecar) → build → deploy to Azure |
| chain | PR, tag | lint → test → build |
| imdbapi | PR, tag | lint → test → build |
| rag_ingestion | PR, tag, **manual ingest** | lint → test → build → [ingest] |

See the [DevOps setup guide](../docs/devops-setup.md) for Jenkins credentials and Azure provisioning.

---

## Further reading

- [INTEGRATION.md](INTEGRATION.md) — submodule workflow, secret sharing, release process, FAQ
- [CONTRIBUTING.md](CONTRIBUTING.md) — git branching, commit conventions, PR checklist, code standards
- [docs/devops-setup.md](../docs/devops-setup.md) — Jenkins + Azure infrastructure guide (for DevOps team)

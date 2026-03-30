# Movie Finder — Backend

AI-powered movie discovery and Q&A. Describe a film you half-remember, the
system searches a Qdrant-backed movie corpus, enriches candidates with live IMDb
data, and answers follow-up questions once you confirm the right match.

This repo is the **backend integration root** for that flow. In the current
iteration, it standardizes a **Docker-only local development workflow for the
backend app stack**. The child repos keep their own repo-local rollout issues:

- `movie-finder-chain#9`
- `imdbapi-client#3`
- `movie-finder-rag#13`

---

## How it works

```text
User describes a movie
        │
        ▼
  [RAG Search] ───── Qdrant Cloud (external vector store)
        │
        ▼
  [IMDb Enrichment] ── live ratings, credits, metadata via imdbapi.dev
        │
        ▼
  [Validation] ── deduplicate, filter low-confidence candidates
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

This is a **multi-repo monorepo**. The backend root integrates three
independent child repos, but this iteration only standardizes the backend app
workflow from the root.

| Repo | Path | Team | Description |
|------|------|------|-------------|
| [movie-finder-backend](.) | `/` | App / Backend | FastAPI app, backend Docker contract, Jenkins pipeline |
| [movie-finder-chain](chain/) | `chain/` | AI Engineering | LangGraph multi-agent pipeline imported by the app |
| [imdbapi-client](imdbapi/) | `imdbapi/` | IMDb API | Async IMDb REST client imported by chain |
| [movie-finder-rag](rag_ingestion/) | `rag_ingestion/` | AI / Data Engineering | Offline ingestion pipeline that writes to Qdrant |

```text
backend/
├── app/                  FastAPI application (auth, chat, sessions)
│   ├── pyproject.toml
│   └── src/app/
│       ├── main.py           FastAPI lifespan + health endpoints
│       ├── config.py         Pydantic settings
│       ├── dependencies.py   Shared FastAPI dependencies
│       ├── routers/          HTTP API surface
│       ├── auth/             JWT middleware + models
│       └── session/          PostgreSQL session store
├── chain/                git submodule: movie-finder-chain
├── imdbapi/              git submodule: imdbapi-client
├── rag_ingestion/        git submodule: movie-finder-rag
├── docker/
│   └── postgres/init/    bootstrap SQL for the local test database
├── scripts/
│   ├── setup.sh          Docker-only backend bootstrap helper
│   └── migrate_sqlite_to_postgres.py
├── Dockerfile            dev + runtime images
├── docker-compose.yml    backend app local stack (postgres + backend)
├── Makefile              Docker-only developer entrypoint
├── Jenkinsfile           backend CI/CD pipeline
├── INTEGRATION.md        cross-repo workflow, secret sharing, FAQ
└── CONTRIBUTING.md       branching, PRs, code standards
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| git | 2.20+ | system package manager |
| make | recent | build tools / Xcode CLT / GNU Make package |

You do **not** need a host `.venv`, host `uv sync`, or host `fastapi dev` for
the backend-root workflow in this iteration.

---

## Quick start (backend app stack)

```bash
# 1. Clone with all child repos
git clone --recurse-submodules https://github.com/aharbii/movie-finder-backend.git
cd movie-finder-backend

# 2. Create your local env file
cp .env.example .env
$EDITOR .env

# 3. Build the dev image and start the local stack
make init
make up

# 4. Inspect the running stack
make logs
```

The backend is available at:

- API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`

If the parent `movie-finder/` stack is already using the default ports, change
`POSTGRES_HOST_PORT` and `BACKEND_HOST_PORT` in `.env` before `make up`.

Minimum values you must fill in before startup:

- `APP_SECRET_KEY`
- `QDRANT_URL`
- `QDRANT_API_KEY_RO`
- `QDRANT_COLLECTION_NAME`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

Use `make down` when you are done.

---

## Common development commands

```bash
make init           # pull postgres + build the backend dev image
make up             # start postgres + backend in the background
make down           # stop and remove local stack
make ci-down        # full cleanup for CI (volumes + images)
make logs           # follow backend + postgres logs
make shell          # shell into the running backend container

make editor-up      # start only backend for editing/linting
make editor-down    # stop the editor container

make lint           # ruff check for app/
make format         # ruff format for app/
make typecheck      # mypy --strict for app/
make test           # pytest app/tests/
make test-coverage  # pytest + coverage XML/HTML for app/
make pre-commit     # repo hooks inside Docker
make check          # lint + typecheck + test
```

All supported root-level developer workflows go through Docker. The child repos
will adopt the same target naming in their own repos as their issues land; this
root repo does not proxy their standalone lint/test/build surfaces yet.

---

## VS Code

The committed `.vscode/` config is split intentionally:

- `tasks.json` runs `make ...` targets from the **host workspace**
- `settings.json` assumes an **attached backend container** interpreter at
  `/opt/venv/bin/python`
- `launch.json` provides backend app and app-test debug profiles
- `extensions.json` recommends Remote Containers, Pylance, Ruff, and Coverage
  Gutters

Recommended workflow:

1. Run `make editor-up` (or `make up`) from the host workspace.
2. In VS Code, use `Dev Containers: Attach to Running Container...`.
3. Attach to the `backend` service container (it will be running after `make editor-up` or `make up`).
4. Use the committed tasks for lifecycle and quality commands.
5. Use the Python Test Explorer for `app/tests/` only in this iteration.

Editor intelligence is configured to resolve:

- `app/src`
- `chain/src`
- `imdbapi/src`

That gives backend developers navigation across the imported libraries without
taking over the child repos' own debug/task surfaces prematurely.

For coverage visualization:

- run `make test-coverage` or the `backend: test with coverage` VS Code task
- open the generated `app-coverage.xml` with Coverage Gutters

---

## Environment variables

The authoritative secret contract lives in
[`../infrastructure/docs/qdrant-secret-model.md`](../infrastructure/docs/qdrant-secret-model.md).

| Variable | Used by | Secret source / notes |
|----------|---------|-----------------------|
| `APP_SECRET_KEY` | backend app | Azure Key Vault: `app-secret-key` |
| `DATABASE_URL` | backend app | Azure Key Vault: `postgres-url` |
| `QDRANT_URL` | app, chain, rag_ingestion | Azure Key Vault / Jenkins: `qdrant-url` |
| `QDRANT_API_KEY_RO` | app, chain | Azure Key Vault / Jenkins: `qdrant-api-key-ro` |
| `QDRANT_COLLECTION_NAME` | app, chain, rag_ingestion | Azure Key Vault / Jenkins: `qdrant-collection-name` |
| `QDRANT_API_KEY_RW` | rag_ingestion only | documented here for cross-repo alignment; not injected into the backend app container |
| `KAGGLE_API_TOKEN` | rag_ingestion only | documented here for cross-repo alignment; not used by the backend app stack |
| `ANTHROPIC_API_KEY` | app via chain | Azure Key Vault: `anthropic-api-key` |
| `OPENAI_API_KEY` | app via chain | Azure Key Vault: `openai-api-key` |
| `LANGSMITH_API_KEY` | optional tracing | Azure Key Vault: `langsmith-api-key` |

Do **not** reintroduce the legacy names `QDRANT_ENDPOINT`, `QDRANT_API_KEY`, or
`QDRANT_COLLECTION` to `.env.example`. The backend compose file exports them
internally only as a temporary compatibility bridge until `movie-finder-chain#9`.

---

## Databases and health

The backend uses two distinct data systems:

| Store | Technology | Purpose |
|-------|------------|---------|
| Vector store | **Qdrant Cloud** | semantic movie search |
| Relational DB | **PostgreSQL 16** | users, sessions, chat history |

Qdrant is always external. There is no supported local Qdrant container in this
repo anymore.

The backend app exposes:

| Path | Purpose |
|------|---------|
| `/health` | backwards-compatible liveness alias |
| `/health/live` | container liveness probe |
| `/health/ready` | database readiness probe |

Local tests use a dedicated `movie_finder_test` database created by
`docker/postgres/init/01-create-test-database.sql`.

---

## Working on a specific subproject

- **App / backend integration work**
  Start here: [app/README.md](app/README.md), [CONTRIBUTING.md](CONTRIBUTING.md)
- **Chain repo-local work**
  Use `movie-finder-chain` docs and issue `movie-finder-chain#9`
- **IMDb client repo-local work**
  Use `imdbapi-client` docs and issue `imdbapi-client#3`
- **RAG repo-local work**
  Use `movie-finder-rag` docs and issue `movie-finder-rag#13`

This distinction is important for the current iteration: the backend root now
owns the app Docker contract, but it does not yet replace each child repo's own
developer surface.

---

## CI/CD

The backend pipeline lives in [Jenkinsfile](Jenkinsfile). In this iteration it
aligns with the backend-owned Docker contract and the new Qdrant secret names,
while the child repos continue landing their own repo-local Docker updates.

Build / deploy flow:

1. Check out the backend workspace with submodules
2. Lint and type-check the backend app slice
3. Run backend app tests against a local PostgreSQL sidecar
4. Build the runtime image
5. Deploy the image to Azure Container Apps

See [deploy/provision.sh](deploy/provision.sh) for the backend Azure bootstrap
script and [INTEGRATION.md](INTEGRATION.md) for the cross-repo secret model.

---

## Further reading

- [CONTRIBUTING.md](CONTRIBUTING.md) — branching, PRs, code standards
- [INTEGRATION.md](INTEGRATION.md) — cross-repo workflow and secret sharing
- [app/README.md](app/README.md) — FastAPI layer details
- [../infrastructure/docs/qdrant-secret-model.md](../infrastructure/docs/qdrant-secret-model.md) — canonical secret contract

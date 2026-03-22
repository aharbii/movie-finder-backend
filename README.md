# Movie Finder

AI-powered movie discovery and Q&A. Describe a film you half-remember — the system searches a vector-embedded movie dataset, enriches candidates with live IMDb data, and answers follow-up questions once you've confirmed your pick.

---

## How it works

```
User describes a movie
        │
        ▼
  [RAG Search] ──── Qdrant vector store (Wikipedia plots)
        │
        ▼
  [IMDb Enrichment] ── live ratings, credits, metadata
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
| [movie-finder-backend](.) | `/` | App / Backend | Integration root + future FastAPI app |
| [movie-finder-chain](chain/) | `chain/` | AI Engineering | LangGraph multi-agent pipeline |
| [imdbapi-client](imdbapi/) | `imdbapi/` | IMDb API | Async IMDb REST API client |
| [movie-finder-rag](rag_ingestion/) | `rag_ingestion/` | AI / Data Engineering | Dataset ingestion → Qdrant |

```
backend/
├── app/             ← future FastAPI app (placeholder)
├── chain/           ← git submodule: movie-finder-chain
├── imdbapi/         ← git submodule: imdbapi-client
├── rag_ingestion/   ← git submodule: movie-finder-rag
├── Dockerfile       ← future app container
├── docker-compose.yml
├── Jenkinsfile      ← integration CI
├── Makefile         ← developer shortcuts
├── INTEGRATION.md   ← team workflow & secret sharing guide
└── CONTRIBUTING.md  ← branching, PRs, release process
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

## Quick start

```bash
# 1. Clone with all submodules
git clone --recurse-submodules https://github.com/aharbii/movie-finder-backend.git
cd movie-finder-backend

# 2. Run the automated setup (installs deps, pre-commit hooks, copies .env)
make setup

# 3. Fill in your API keys
$EDITOR .env

# 4. Start the full local stack (Qdrant + app)
make docker-up

# 5. Verify everything imports correctly
make check
```

---

## Common development commands

```bash
make setup        # first-time setup: deps + pre-commit + .env
make lint         # ruff check/format + mypy (chain + imdbapi)
make lint-fix     # auto-fix ruff violations
make test         # pytest (chain + imdbapi)
make test-all     # pytest (all three projects including rag_ingestion)
make docker-up    # start Qdrant + app
make docker-down  # stop stack
make submodules   # pull latest from all submodule remotes
make clean        # remove __pycache__, .pytest_cache, etc.
```

See `make help` for the full list.

---

## Working on a specific subproject

Each project can run fully independently. Jump to its README:

- **[chain/README.md](chain/README.md)** — AI pipeline: how nodes work, how to run examples, testing strategy
- **[imdbapi/README.md](imdbapi/README.md)** — IMDb client: endpoint coverage, pagination, error handling
- **[rag_ingestion/README.md](rag_ingestion/README.md)** — ingestion pipeline: dataset download, embedding, Qdrant load
- **[app/README.md](app/README.md)** — FastAPI layer: planned structure (not yet implemented)

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
| backend (this repo) | PR, tag, manual deploy | lint all → test all → build app image |
| chain | PR, tag | lint → test → build image |
| imdbapi | PR, tag | lint → test → build image |
| rag_ingestion | PR, tag, **manual ingest** | lint → test → build → [ingest] |

See [INTEGRATION.md](INTEGRATION.md) for Jenkins credentials setup and the Qdrant secret-sharing workflow between teams.

---

## Further reading

- [INTEGRATION.md](INTEGRATION.md) — submodule workflow, secret sharing, release process, FAQ
- [CONTRIBUTING.md](CONTRIBUTING.md) — git branching, commit conventions, PR checklist, code standards

# Movie Finder — Integration Guide

This document describes how the four repositories are organized, how teams work independently, and how they integrate for a full-stack deployment.

---

## Repository Map

| Repo | GitHub | Team | Status | Consumed by |
|------|--------|------|--------|-------------|
| `movie-finder-backend` | `aharbii/movie-finder-backend` | App / Backend | Active | End users |
| `movie-finder-chain` | `aharbii/movie-finder-chain` | AI Engineering | Active | backend app |
| `imdbapi-client` | `aharbii/imdbapi-client` | IMDb API | Active | chain |
| `movie-finder-rag` | `aharbii/movie-finder-rag` | AI / Data Engineering | Active | chain (via Qdrant) |

### Dependency flow

```
movie-finder-rag ──[Qdrant endpoint]──► movie-finder-chain ◄──[pip]── imdbapi-client
                                               │
                                               ▼
                                    movie-finder-backend (FastAPI)
                                               │
                                               ▼
                                          End users
```

---

## Getting Started — First Clone

```bash
# Clone the backend repo WITH all submodules in one command
git clone --recurse-submodules https://github.com/aharbii/movie-finder-backend.git
cd movie-finder-backend

# Or if you already cloned without --recurse-submodules:
git submodule update --init --recursive
```

### Set up the Python environment (workspace)

```bash
cp .env.example .env
$EDITOR .env   # fill in all API keys

# Install workspace packages (chain + imdbapi) with dev tools
uv sync --group dev

# Verify
uv run python -c "from chain import compile_graph; print('chain OK')"
uv run python -c "from imdbapi import IMDBAPIClient; print('imdbapi OK')"
```

### Start the full local stack

```bash
docker compose up
# App: http://localhost:8000
# Qdrant: http://localhost:6333
```

---

## Working on a Specific Project (standalone)

Each project can run completely independently.

### chain

```bash
cd chain/
cp .env.example .env && $EDITOR .env
uv sync --group dev
uv run pytest tests/ -v
docker compose up   # starts local Qdrant + smoke-tests chain
```

### imdbapi

```bash
cd imdbapi/
cp .env.example .env && $EDITOR .env
uv sync --group dev
uv run pytest tests/ -v
```

### rag_ingestion

```bash
cd rag_ingestion/
cp .env.example .env && $EDITOR .env
uv sync --group dev
docker compose up qdrant -d
python -m src.main   # runs full ingestion
```

---

## Qdrant Secret Sharing (RAG team → Chain team)

The RAG team outputs a Qdrant collection after each ingestion run. The chain team consumes it.

### Process

1. RAG team runs the `Ingest` Jenkins stage (manual, parameterized)
2. Jenkins archives `ingestion-outputs.env` as a build artifact
3. RAG team downloads the artifact and updates these Jenkins credentials in the **chain repo pipeline**:
   - `qdrant-collection` → value of `QDRANT_COLLECTION`
   - The `qdrant-endpoint` and `qdrant-api-key` credentials are shared once and rarely change
4. Chain team's next build automatically picks up the new collection

### What to share (never via chat or email — use Jenkins credentials store)

```
QDRANT_ENDPOINT=<cloud-endpoint>
QDRANT_API_KEY=<api-key>
QDRANT_COLLECTION=<new-collection-name>
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSION=3072
```

---

## Submodule Workflow

### Updating a submodule to the latest commit

```bash
cd imdbapi/      # or chain/ or rag_ingestion/
git fetch && git checkout main && git pull
cd ..
git add imdbapi/
git commit -m "chore: bump imdbapi to latest main"
```

### Pinning to a specific release tag

```bash
cd chain/
git fetch --tags
git checkout v1.2.0
cd ..
git add chain/
git commit -m "chore: pin chain to v1.2.0"
```

### After pulling backend changes that update a submodule

```bash
git pull
git submodule update --init --recursive
```

---

## Extracting chain/ as a Git Submodule

> **One-time operation** — execute when `chain/` is ready to be its own repo.
> The team member performing this should have write access to GitHub org.

```bash
# Step 1: Create a new repo on GitHub: aharbii/movie-finder-chain

# Step 2: Initialize chain/ as its own git repo and push
cp -r chain/ /tmp/movie-finder-chain && cd /tmp/movie-finder-chain
git init
git add .
git commit -m "chore: init movie-finder-chain (extracted from backend monorepo)"
git remote add origin https://github.com/aharbii/movie-finder-chain.git
git push -u origin main
cd -

# Step 3: Remove chain/ from backend tracking
git rm -r chain/
git commit -m "chore: remove chain/ as tracked directory (converting to submodule)"

# Step 4: Add as submodule
git submodule add https://github.com/aharbii/movie-finder-chain.git chain
git submodule update --init --recursive
git commit -m "chore: add chain as git submodule"
git push origin main

# Step 5: Update .gitmodules — uncomment the chain entry
```

---

## Release Process (per repo)

Each repo follows semantic versioning (`vMAJOR.MINOR.PATCH`).

```bash
# 1. Bump version in pyproject.toml [project].version
# 2. Commit the version bump
git add pyproject.toml && git commit -m "chore: bump version to v1.2.0"

# 3. Tag and push — Jenkins release pipeline triggers automatically
git tag v1.2.0
git push origin main --tags
```

Jenkins picks up the tag and runs the full pipeline including Docker image build and push.

---

## CI/CD Overview

| Pipeline | Repo | Triggers | Key stages |
|----------|------|----------|------------|
| `imdbapi-client` | imdbapi | PR, tag | lint → test → build+push |
| `movie-finder-rag` | rag_ingestion | PR, tag, manual | lint → test → build → [ingest] |
| `movie-finder-chain` | chain | PR, tag | lint → test → build+push |
| `movie-finder-backend` | backend | PR, tag, manual | submodule checkout → lint (all) → test (all) → build → [deploy staging] |

### Jenkins credentials required (org-level or per-pipeline)

| Credential ID | Type | Used by |
|---|---|---|
| `docker-registry-url` | Secret text | all pipelines |
| `qdrant-endpoint` | Secret text | rag_ingestion Ingest stage |
| `qdrant-api-key` | Secret text | rag_ingestion Ingest stage |
| `openai-api-key` | Secret text | rag_ingestion Ingest stage |
| `kaggle-username` | Secret text | rag_ingestion Ingest stage |
| `kaggle-key` | Secret text | rag_ingestion Ingest stage |

---

## Environment Variable Reference

See `.env.example` for the complete list with descriptions. Quick reference:

| Variable | Owner | Required by |
|---|---|---|
| `QDRANT_ENDPOINT` | RAG team | rag_ingestion, chain |
| `QDRANT_API_KEY` | RAG team | rag_ingestion, chain |
| `QDRANT_COLLECTION` | RAG team | chain |
| `EMBEDDING_MODEL` | RAG team | chain |
| `OPENAI_API_KEY` | Shared | rag_ingestion, chain |
| `ANTHROPIC_API_KEY` | AI team | chain |
| `IMDB_API_KEY` | IMDb team | chain |
| `KAGGLE_USERNAME` / `KAGGLE_KEY` | Data team | rag_ingestion |

---

## Pre-commit Hooks

Each project has `.pre-commit-config.yaml`. Install hooks after cloning:

```bash
# From any project root
uv sync --group dev
uv run pre-commit install

# Run manually against all files
uv run pre-commit run --all-files
```

Hooks run: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `detect-secrets`, `mypy`, `ruff`.

---

## FAQ

**Q: A team wants to test chain changes without pushing to GitHub — how?**

In the backend workspace, `chain/` is a local path dependency. Make changes in `chain/src/`, run `uv run pytest chain/tests/` from the backend root. No push needed until ready for review.

**Q: The chain depends on imdbapi — how do standalone chain tests work?**

The chain's Dockerfile and docker-compose use the workspace root as the build context, so both `chain/` and `imdbapi/` are available. For local `pytest` runs, install from the workspace root (`uv sync --group test`) which installs imdbapi as a workspace member.

**Q: How do I add a new dependency to chain?**

```bash
cd backend/   # workspace root
uv add --package movie-finder-chain <package-name>
# uv updates chain/pyproject.toml and the root uv.lock
```

**Q: How do I add a dependency to rag_ingestion (not in workspace)?**

```bash
cd rag_ingestion/
uv add <package-name>
# uv updates rag_ingestion/pyproject.toml and rag_ingestion/uv.lock
```

# Movie Finder — Integration Guide

This document explains how the backend integration repo fits into the wider
Movie Finder project, and what is intentionally scoped into or out of the
current **backend-only Docker iteration**.

---

## Repository map

| Repo                   | GitHub                         | Team                  | Consumed by      |
| ---------------------- | ------------------------------ | --------------------- | ---------------- |
| `movie-finder-backend` | `aharbii/movie-finder-backend` | App / Backend         | end users        |
| `movie-finder-chain`   | `aharbii/movie-finder-chain`   | AI Engineering        | backend app      |
| `imdbapi-client`       | `aharbii/imdbapi-client`       | IMDb API              | chain            |
| `movie-finder-rag`     | `aharbii/movie-finder-rag`     | AI / Data Engineering | chain via Qdrant |

### Dependency flow

```text
movie-finder-rag ── writes vectors ──► Qdrant Cloud ◄── reads ── movie-finder-chain
                                                                      ▲
                                                                      │
                                                            imdbapi-client
                                                                      │
                                                                      ▼
                                                         movie-finder-backend
                                                                      │
                                                                      ▼
                                                                 End users
```

Qdrant is always external. There is no supported local Qdrant container in the
backend root anymore.

---

## Current iteration boundary

This backend repo now owns the **Docker-only local development contract for the
backend app stack**:

```bash
make init
make up
make down
make logs
make shell
make lint
make format
make typecheck
make test
make test-coverage
make pre-commit
```

What this iteration does **not** do yet:

- provide parent-owned standalone task surfaces for `chain/`
- provide parent-owned standalone task surfaces for `imdbapi/`
- provide parent-owned standalone task surfaces for `rag_ingestion/`
- replace each child repo's own docs, CI, or Docker contract

Those follow-up rollouts are tracked in:

- `movie-finder-chain#9`
- `imdbapi-client#3`
- `movie-finder-rag#13`

When those land, the backend root can take a later integration pass to expose
broader parent-level capabilities again without corrupting the child repo work.

---

## Getting started from this repo

```bash
git clone --recurse-submodules https://github.com/aharbii/movie-finder-backend.git
cd movie-finder-backend

cp .env.example .env
$EDITOR .env

make init
make up
```

The backend app is then available at `http://localhost:8000`.

If the parent `movie-finder/` stack is already running on the default ports,
override `POSTGRES_HOST_PORT` and `BACKEND_HOST_PORT` in `.env`.

---

## Working on a specific project

### Backend app integration work

Use this repo and its root Docker contract.

Recommended entry points:

- [README.md](README.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [app/README.md](app/README.md)

### Child repo work

Use the child repo's own docs and issue thread for repo-local development:

- `movie-finder-chain#9`
- `imdbapi-client#3`
- `movie-finder-rag#13`

The backend root should only record alignment and handoff notes for those repos
in this iteration, not absorb their implementation tasks.

---

## Provider and Vector Store Contract

The authoritative contract lives in
[`../infrastructure/docs/provider-runtime-contract.md`](../infrastructure/docs/provider-runtime-contract.md).

Canonical environment variables:

| Variable                 | Owner / usage                                 |
| ------------------------ | --------------------------------------------- |
| `VECTOR_COLLECTION_PREFIX` | target prefix shared by app, chain, and rag |
| `QDRANT_URL`               | Qdrant endpoint for app, chain, and rag     |
| `QDRANT_API_KEY_RO`        | read-only key for app + chain               |
| `QDRANT_API_KEY_RW`        | write-capable key for rag only              |
| `KAGGLE_API_TOKEN`         | rag only                                    |

Backend-specific implications:

- `.env.example` exposes canonical names only.
- `docker-compose.yml` injects only the backend runtime contract.
- The backend app container must not receive `QDRANT_API_KEY_RW`.

Current Jenkins credentials used by the backend-owned slice:

| Jenkins credential ID       | Canonical env var          |
| --------------------------- | -------------------------- |
| `qdrant-url`                | `QDRANT_URL`               |
| `qdrant-api-key-ro`         | `QDRANT_API_KEY_RO`        |
| `vector-collection-prefix`  | `VECTOR_COLLECTION_PREFIX` |

---

## Submodule workflow

### Updating a submodule to the latest commit

```bash
cd imdbapi/      # or chain/ or rag_ingestion/
git fetch && git checkout main && git pull
cd ..
git add imdbapi/
git commit -m "chore(imdbapi): bump to latest main"
```

### After pulling backend changes that update a submodule pointer

```bash
git pull
git submodule update --init --recursive
```

Pointer bumps should stay explicit so the parent repo never silently absorbs
unreviewed child repo work.

---

## CI/CD overview

| Pipeline               | Repo          | Current responsibility                                 |
| ---------------------- | ------------- | ------------------------------------------------------ |
| `movie-finder-backend` | backend       | backend app lint/typecheck/test, image build, deploy   |
| `movie-finder-chain`   | chain         | chain library rollout and its Docker-first update      |
| `imdbapi-client`       | imdbapi       | client library rollout and its Docker-first update     |
| `movie-finder-rag`     | rag_ingestion | ingestion pipeline rollout and its Docker-first update |

The backend pipeline in this iteration validates the backend app slice only. The
child repos continue landing their own repo-local changes independently.

---

## Environment variable reference

See [.env.example](.env.example) for the full current template. Quick reference:

| Variable                 | Required by                  |
| ------------------------ | ---------------------------- |
| `APP_SECRET_KEY`         | backend app                  |
| `DATABASE_URL`           | backend app                  |
| `QDRANT_URL`             | app, chain, rag_ingestion    |
| `QDRANT_API_KEY_RO`      | app, chain                   |
| `QDRANT_API_KEY_RW`      | rag_ingestion only           |
| `VECTOR_COLLECTION_PREFIX` | app, chain, rag_ingestion  |
| `OPENAI_API_KEY`         | app via chain, rag_ingestion |
| `ANTHROPIC_API_KEY`      | app via chain                |
| `KAGGLE_API_TOKEN`       | rag_ingestion only           |

---

## FAQ

**Q: Why doesn’t the backend root expose standalone child-repo tasks anymore?**

Because this iteration is intentionally limited to the backend-owned Docker app
stack. The child repos already have open issues for their repo-local Docker and
VS Code surfaces, and folding that work back into the root early would create
duplicate ownership.

**Q: Can backend developers still navigate into `chain/` and `imdbapi/` code?**

Yes. The attached-container VS Code settings expose `app/src`, `chain/src`, and
`imdbapi/src` for editor intelligence because the backend app imports those
libraries directly.

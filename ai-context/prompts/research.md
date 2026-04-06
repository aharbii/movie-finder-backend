# Research Prompt — movie-finder-backend

Use this for exploration and technology research before implementation.
This phase has ZERO codebase access — it's pure knowledge retrieval.

---

## When to use this

- Exploring a library or pattern before adopting it in the backend
- Comparing FastAPI patterns, asyncpg approaches, or auth strategies
- Understanding how a known issue is typically solved (e.g., rate limiting, CORS, token revocation)
- Getting up to speed on LangGraph, LangChain, or Pydantic v2 before implementing

**Do NOT open Claude Code for research.** Use:

- `gemini` — web search + long-context reading (Google AI Pro)
- `ollama run qwen2.5-coder:14b` — local, zero quota, good for code discussion
- `claude.ai` web — separate quota pool from Claude Code CLI/extension

---

## Backend context to paste at the start of a research session

```
I'm working on the backend of Movie Finder — a FastAPI app that serves as the HTTP/SSE
layer for an AI film-finding assistant.

Backend stack:
- Language: Python 3.13
- API: FastAPI 0.115+, StreamingResponse (SSE proxy)
- Auth: JWT (python-jose, bcrypt) — 30-min access token, 7-day refresh token
- Database: PostgreSQL 16, asyncpg connection pool
- AI pipeline: LangGraph 0.2+ (imported as `chain/` submodule)
- Vector store: Qdrant Cloud (external only — no local container)
- Package manager: uv workspace (app + chain as members)
- Linting: ruff (line-length 100)
- Type checking: mypy --strict
- Tests: pytest --asyncio-mode=auto
- Local dev: Docker-only via Makefile targets (make up, make test, make pre-commit)
- CI: Jenkins → Azure Container Registry → Azure Container Apps

Known open issues: rate limiting (#4), refresh token revocation (#5), DB indexes (#3),
MemorySaver non-persistence (#2), no CORS (#9), hashed_password exposure (#12).

I want to explore: [YOUR TOPIC HERE]

Please search for current best practices, relevant libraries, and notable tradeoffs.
I'm not implementing anything yet — just building understanding.
```

---

## How to use with Gemini CLI

```bash
gemini "$(cat ai-context/prompts/research.md)"
# Or start a session and paste the context block above
```

## How to use with Ollama

```bash
ollama run qwen2.5-coder:14b
# Then paste the context block above
```

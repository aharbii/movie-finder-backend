# AI Context — movie-finder-backend

Shared reference for AI agents working in this repo standalone.

## Available slash commands (Claude Code)

Open `backend/` as your workspace, then type `/`:

| Command | Usage |
|---|---|
| `/implement [issue-number]` | Implement a child issue from this repo |
| `/review-pr [pr-number]` | Review a PR in this repo |
| `/create-issue [description]` | Create sub-issues for chain/imdbapi/rag |

## Prompts (Codex CLI / Gemini CLI / Ollama)

- `ai-context/prompts/implement.md` — implementation workflow for this repo
- `ai-context/prompts/review-pr.md` — review workflow

Usage:
```bash
cat ai-context/prompts/implement.md   # read the prompt
gh pr diff N --repo aharbii/movie-finder-backend > /tmp/pr.txt
cat /tmp/pr.txt | codex "$(cat ai-context/prompts/review-pr.md)"
```

## Issue hierarchy

This repo's direct submodules: `movie-finder-chain`, `imdbapi-client`, `movie-finder-rag`.
Parent tracker: `aharbii/movie-finder` (creates issues in this repo, not in sub-submodules).
Use `/create-issue` in this workspace to create sub-issues for chain/imdbapi/rag.

## Agent Briefing

Every issue must have an `## Agent Briefing` section before implementation.
Template: `ai-context/issue-agent-briefing-template.md`

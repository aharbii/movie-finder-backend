# Session Start — movie-finder-backend

Run these checks in parallel, then give a prioritised summary. Do not read any source files.

```bash
gh issue list --repo aharbii/movie-finder-backend --state open --limit 20 \
  --json number,title,labels,assignees
```

```bash
gh pr list --repo aharbii/movie-finder-backend --state open \
  --json number,title,state,labels,headRefName
```

```bash
gh issue list --repo aharbii/movie-finder --state open --limit 10 \
  --json number,title,labels
```

```bash
git status && git log --oneline -5
```

```bash
cd chain && git log --oneline -3 && cd ../rag_ingestion && git log --oneline -3
```

Then summarise:

- **Open issues in this repo** — number, title, severity label
- **Open PRs** — which are ready to review, which are blocked
- **Parent issues in movie-finder** — any that affect this backend repo
- **Current branch and uncommitted changes** — in backend, chain, rag_ingestion
- **Recommended next action** — one specific thing

Keep the summary under 25 lines. Do not propose solutions yet.

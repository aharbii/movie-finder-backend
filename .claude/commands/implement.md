# Implement Issue — movie-finder-backend

**Repo:** `aharbii/movie-finder-backend`
**Parent tracker:** `aharbii/movie-finder`
**Pre-commit:** `uv run pre-commit run --all-files`

Implement GitHub issue #$ARGUMENTS from `aharbii/movie-finder-backend`.

---

## Step 1 — Read the child issue

```bash
gh issue view $ARGUMENTS --repo aharbii/movie-finder-backend
```

Find the **Agent Briefing** section. If absent, ask the user to add it before proceeding.

---

## Step 2 — Read the parent issue for full context

The child issue body contains a "Parent issue" link. Read it:

```bash
gh issue view [PARENT_NUMBER] --repo aharbii/movie-finder
```

Implement only what the **child issue** requires.

---

## Step 3 — Read only the files listed in the Agent Briefing

Do not explore the codebase. Read only what the issue specifies.

---

## Step 4 — Create the branch

```bash
git checkout main && git pull
git checkout -b [type]/[kebab-case-title]
```

---

## Step 5 — Implement

Follow the acceptance criteria. Backend standards:

- Type annotations required on all public functions and methods
- `mypy --strict` must pass
- Line length ≤ 100 chars
- No bare `except:` — specific exception types only
- No `print()` — use proper logging
- Async all the way — no blocking I/O in async context
- No mutable default arguments
- Docstrings on all public classes and functions (Google style)
- Design patterns: Repository for DB, Depends() for DI, Strategy for providers

---

## Step 6 — Run quality checks

```bash
uv run pre-commit run --all-files
```

Fix all findings before committing.

---

## Step 7 — Commit

```bash
git add [only changed files — never git add -A]
git commit -m "$(cat <<'EOF'
type(scope): short summary

[why]

Closes #$ARGUMENTS
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Step 8 — Open PR

```bash
cat .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null
```

```bash
gh pr create \
  --repo aharbii/movie-finder-backend \
  --title "type(scope): short summary" \
  --body "$(cat <<'EOF'
[PR body]

Closes #$ARGUMENTS
Parent: [PARENT_ISSUE_URL]

---
> AI-assisted implementation: Claude Code (claude-sonnet-4-6)
EOF
)"
```

---

## Step 9 — Cross-cutting comments

For each issue in the Agent Briefing's "Related issues" list:

```bash
gh issue comment [NUMBER] --repo [REPO] \
  --body "PR aharbii/movie-finder-backend#[PR] may affect this issue: [PR_URL]"
```

Comment on the child issue:

```bash
gh issue comment $ARGUMENTS --repo aharbii/movie-finder-backend \
  --body "Implemented in PR #[PR]: [PR_URL]"
```

Comment on the parent issue:

```bash
gh issue comment [PARENT] --repo aharbii/movie-finder \
  --body "Child work completed in aharbii/movie-finder-backend#[PR]: [PR_URL]"
```

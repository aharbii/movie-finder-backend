# Review PR — movie-finder-backend

**Repo:** `aharbii/movie-finder-backend`

Post findings as a comment only. Do not submit a GitHub review status.
The human decides whether to merge.

---

## Step 1 — Read PR, issue, and diff

```bash
gh pr view $ARGUMENTS --repo aharbii/movie-finder-backend
gh issue view [LINKED_ISSUE] --repo aharbii/movie-finder-backend
gh pr diff $ARGUMENTS --repo aharbii/movie-finder-backend
```

If a parent issue is referenced, read it too:

```bash
gh issue view [PARENT] --repo aharbii/movie-finder
```

If the PR is a partial iteration ("Part of #N"), evaluate only what it claims to implement.

---

## Blocking findings (must fix before merge)

**Backend patterns:**

- Repository pattern not used for DB access (raw SQL in route handlers)
- `Depends()` not used for shared resources (instantiation inside route handlers)
- Strategy pattern violated (if/else branching on provider type in core logic)
- `os.getenv()` scattered in code instead of Pydantic BaseSettings

**Python standards:**

- Missing type annotations on public functions/methods (mypy --strict equivalent)
- Bare `except:` — specific exception types required
- `print()` or debug output in production code
- `type: ignore` without inline comment
- Line > 100 chars
- Blocking I/O in async context
- No tests for new logic
- Missing docstrings on public classes/functions (Google style)

**PR hygiene:**

- AI disclosure missing
- Issue not linked (`Closes #N` or `Part of #N`)
- Conventional Commits format not followed

**Non-blocking:** minor style, CHANGELOG.md not updated, cross-cutting items
noted in PR body for other repos.

---

## Post as a comment

```bash
gh pr comment $ARGUMENTS --repo aharbii/movie-finder-backend \
  --body "[review comment body]"
```

Comment structure:

```
## Review — [date]
Reviewed by: [tool and model]

### Verdict
PASS — no blocking findings. Human call to merge.
— or —
BLOCKING FINDINGS — must fix before merge.

### Blocking findings
[file:line] — [issue and fix]

### Non-blocking observations
[file:line] — [observation]

### Cross-cutting gaps
[any cross-cutting item not handled and not noted in PR body]
```

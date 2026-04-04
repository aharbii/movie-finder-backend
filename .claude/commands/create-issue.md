# Create Sub-Issues — movie-finder-backend

This command is used when working in the backend workspace to create child issues for
backend's own sub-submodules: chain, imdbapi, rag_ingestion.

Use this AFTER a parent issue already exists in `aharbii/movie-finder-backend`.

Task: $ARGUMENTS (format: "parent issue #N — [brief description of sub-work needed]")

---

## Step 1 — Read the backend parent issue

```bash
gh issue view [PARENT_NUMBER] --repo aharbii/movie-finder-backend
```

Understand what the backend issue requires from its sub-submodules.

---

## Step 2 — Identify which sub-submodules need issues

| Area                  | Repo                         |
| --------------------- | ---------------------------- |
| LangGraph AI pipeline | `aharbii/movie-finder-chain` |
| IMDb REST client      | `aharbii/imdbapi-client`     |
| RAG ingestion         | `aharbii/movie-finder-rag`   |

Create child issues only in repos whose files will change.

---

## Step 3 — Read the linked_task template in the target repo

```bash
gh api repos/[TARGET_REPO]/contents/.github/ISSUE_TEMPLATE/linked_task.yml \
  --jq '.content' | base64 -d
```

---

## Step 4 — Create child issues

```bash
gh issue create \
  --repo [TARGET_REPO] \
  --title "[TASK]: [specific title]" \
  --label "task" \
  --body "[child body: link to backend parent, scoped Agent Briefing]"
```

The Agent Briefing must be scoped to that sub-submodule only.
Note the returned issue number as CHILD_NUMBER.

---

## Step 5 — Link child to backend parent using Sub-Issues API

```bash
gh api --method POST \
  /repos/aharbii/movie-finder-backend/issues/[PARENT_NUMBER]/sub_issues \
  -f sub_issue_id=CHILD_NUMBER
```

If the API returns an error, fall back to a comment:

```bash
gh issue comment [PARENT_NUMBER] --repo aharbii/movie-finder-backend \
  --body "Sub-issue created: [CHILD_URL]"
```

---

## Step 6 — Add child issues to GitHub Project

```bash
gh project list --owner aharbii
gh project item-add [PROJECT_NUMBER] --owner aharbii --url [CHILD_ISSUE_URL]
```

---

## Step 7 — Summary

Report: child issue URLs, link status, project items added.

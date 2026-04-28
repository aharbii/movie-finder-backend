# Contributing to Movie Finder Backend

This guide covers the shared conventions for the **backend-owned** slice of the
repo in the current Docker-only iteration. The child repos still keep their own
repo-local rollout issues and should not be folded into this root workflow
without updating those issue threads first.

---

## Table of contents

1. [Development setup](#development-setup)
2. [VS Code workflow](#vs-code-workflow)
3. [Branching strategy](#branching-strategy)
4. [Commit messages](#commit-messages)
5. [Pull requests](#pull-requests)
6. [Code standards](#code-standards)
7. [Testing requirements](#testing-requirements)
8. [Working with submodules](#working-with-submodules)
9. [Release process](#release-process)
10. [Jenkins CI](#jenkins-ci)

---

## Development setup

Run the backend setup flow after cloning:

```bash
git clone --recurse-submodules https://github.com/aharbii/movie-finder-backend.git
cd movie-finder-backend

cp .env.example .env
$EDITOR .env

make init
make editor-up    # start only backend for editing/linting
make up           # start full stack (app + postgres)
```

You can also use the helper script:

```bash
./scripts/setup.sh
```

Supported root-level quality commands:

```bash
make lint
make format
make typecheck
make test
make test-coverage
make pre-commit
```

Supported root-level database commands:

```bash
make db-upgrade                     # apply migrations inside Docker
make db-downgrade DB_REVISION=-1    # roll back inside Docker
make db-current                     # show current revision
make db-history                     # show migration history
make db-revision MESSAGE=add_index  # create a new empty revision
make lock                           # refresh uv.lock inside Docker
```

Backend startup runs `alembic upgrade head` automatically. If you introduce a
new schema change, create and apply it through the Docker-backed `make` targets
instead of running Alembic directly on the host.

Use `make editor-down` or `make down` to stop the local containers.

### What is intentionally not part of this root setup yet

- Standalone `chain/` lint/test/debug tasks
- Standalone `imdbapi/` lint/test/debug tasks
- Standalone `rag_ingestion/` lint/test/debug tasks
- Parent-level orchestration of all child repo pipelines from this root

Those capabilities are still owned by the child repo issues and will come back
to the backend root in a later integration iteration.

---

## VS Code workflow

The committed `.vscode/` config is designed around the Docker-only backend app
contract:

- **Host tasks** call `make ...`
- **Python interpreter** lives at `/opt/venv/bin/python` inside the attached
  `backend` container
- **Code navigation** resolves `app/src`, `chain/src`, and `chain/imdbapi/src`
- **Test Explorer** is configured for `app/tests/` only in this iteration

Recommended workflow:

1. Run `make up           # start full stack (app + postgres)`
2. Attach VS Code to the running `backend` container started from the root
3. Use the committed tasks and launch configurations from inside that session

Coverage workflow:

```bash
make test-coverage
```

This writes `app-coverage.xml` and `htmlcov/app/` for local inspection or VS Code
coverage extensions.

---

## Branching strategy

We follow **trunk-based development** with short-lived feature branches.

```text
main            always deployable; protected; requires PR + review
  feature/<short-description>
  fix/<short-description>
  chore/<short-description>
  docs/<short-description>
  hotfix/<short-description>
```

Rules:

- Never push directly to `main`
- Branch names use lowercase kebab-case
- Delete the branch after the PR is merged
- Keep branches short-lived
- If the work spans multiple repos, align the issue comments first before
  broadening scope

---

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <short summary>
```

Examples:

- `feat(app): add readiness probe`
- `chore(backend): standardize docker-only tooling`
- `docs(backend): clarify backend-only iteration boundaries`

Summary rules:

- Lowercase, no period at the end
- Imperative mood
- Prefer 72 characters or fewer

---

## Pull requests

### Before opening a PR

```bash
make lint
make typecheck
make test
make pre-commit
```

Use the pull request template in `.github/PULL_REQUEST_TEMPLATE.md`.

Before creating or editing an issue or PR:

- inspect the matching issue template
- inspect the PR template
- inspect one recent example of the same type

If AI tools are used:

- disclose the authoring tool and model in the PR description
- disclose any AI-assisted review tool and model in review comments or approvals

### Review requirements

- Minimum **1 approval** from a non-author reviewer
- All CI checks must be green before merge
- Resolve reviewer comments before merge
- Use **squash and merge** for normal feature/fix/chore branches

If the change intentionally stops short of child repo work, say that explicitly
in the PR description and on the linked issue thread.

---

## Code standards

All code is enforced by pre-commit hooks and CI.

### Python standards

- Python 3.13
- `ruff`
- `mypy --strict`
- line length: **100**
- Google-style docstrings on public functions and classes
- async all the way for app code

### Supported root targets

```bash
make lint
make format
make typecheck
make test
make test-coverage
make pre-commit
```

### Secrets detection

If `detect-secrets` flags a false positive, add an inline allowlist comment:

```python
value = "not-a-secret"  # pragma: allowlist secret
```

---

## Testing requirements

- New logic needs unit tests
- No real network calls in tests
- Coverage should not regress
- Tests should mirror the `src/` structure

The backend root currently guarantees the backend app test flow only:

```bash
make test
make test-coverage
```

`make test` runs inside Docker and points pytest at the dedicated
`movie_finder_test` database in the local postgres service.

If a change affects a child repo too, leave the parent/backend issue comment trail
clear about which verification belongs to which repo.

---

## Working with submodules

This repo is the backend integration root. The child repos keep their own release
cadence and their own issue-owned rollout work.

### Updating a submodule pointer

```bash
cd chain/   # or chain/imdbapi/ or rag_ingestion/
git fetch && git checkout main && git pull
cd ..
git add chain/
git commit -m "chore(chain): bump to latest main"
```

Note: `imdbapi-client` is a submodule nested inside `chain/` (path `chain/imdbapi/`).
To update its pointer, `cd chain/imdbapi/` and commit from `chain/`:

### After pulling backend changes that moved a submodule pointer

```bash
git pull
git submodule update --init --recursive
```

### Scope rule for this iteration

Do not expand the backend root into child-repo-only tooling as a side effect of
an app-stack change. Document the handoff in the relevant issue comment instead.

---

## Release process

Each repo is versioned independently with semantic versioning.

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v1.2.0"
git tag v1.2.0
git push origin main --tags
```

Jenkins handles the release pipeline after the tag is pushed.

After releasing a child repo, update the pointer here in a dedicated follow-up
commit or PR.

---

## Jenkins CI

The backend Jenkins pipeline now validates the backend-owned app slice from this
repo while the child repos continue landing their own Docker-first updates.

Current backend pipeline responsibilities:

- check out the workspace with submodules
- lint and type-check the backend app slice
- run backend app tests against PostgreSQL
- publish coverage reports

Image builds, Azure provisioning, and Container App rollout are owned by the
parent `movie-finder` pipeline and the `infrastructure/` Terraform module. For
runtime contract details, see:

- [Jenkinsfile](Jenkinsfile)
- [INTEGRATION.md](INTEGRATION.md)

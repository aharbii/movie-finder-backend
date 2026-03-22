# Contributing to Movie Finder Backend

This guide covers the shared conventions for all teams working in this monorepo. Each subproject also has its own `CONTRIBUTING.md` with team-specific details.

---

## Table of contents

1. [Development setup](#development-setup)
2. [Branching strategy](#branching-strategy)
3. [Commit messages](#commit-messages)
4. [Pull requests](#pull-requests)
5. [Code standards](#code-standards)
6. [Testing requirements](#testing-requirements)
7. [Working with submodules](#working-with-submodules)
8. [Release process](#release-process)
9. [Jenkins CI](#jenkins-ci)

---

## Development setup

Run the one-time setup script after cloning:

```bash
git clone --recurse-submodules https://github.com/aharbii/movie-finder-backend.git
cd movie-finder-backend
make setup
$EDITOR .env   # fill in your API keys
```

`make setup` does the following:
1. Initializes all git submodules
2. Installs workspace packages with dev tools (`uv sync --group dev`)
3. Installs pre-commit hooks (`pre-commit install`)
4. Copies `.env.example` → `.env` if `.env` does not exist

### Working on a submodule independently

```bash
cd chain/          # or imdbapi/, rag_ingestion/
uv sync --group dev
uv run pre-commit install
cp .env.example .env && $EDITOR .env
```

---

## Branching strategy

We follow **trunk-based development** with short-lived feature branches.

```
main            ← always deployable; protected; requires PR + review
  └── feature/<short-description>    ← new feature
  └── fix/<short-description>        ← bug fix
  └── chore/<short-description>      ← tooling, deps, CI changes
  └── docs/<short-description>       ← documentation only
  └── hotfix/<short-description>     ← urgent production fix
```

**Rules:**
- Never push directly to `main`
- Branch names use kebab-case: `feature/add-gemini-embedding`
- Delete the branch after the PR is merged
- Keep branches short-lived (ideally merged within a sprint)

---

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

**Types:**

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `chore` | Tooling, dependencies, CI, scripts |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `refactor` | Code change that is not a feature or fix |
| `perf` | Performance improvement |
| `ci` | CI pipeline changes |

**Scope** is optional but recommended — use the package name or area:
`feat(chain): add gemini embedding provider`
`fix(imdbapi): handle 429 rate-limit retry correctly`
`chore(rag): bump qdrant-client to v1.14`

**Summary rules:**
- Lowercase, no period at the end
- Imperative mood ("add", not "added" or "adds")
- ≤ 72 characters

---

## Pull requests

### Before opening a PR

```bash
make lint        # must pass with zero errors
make test        # must pass with zero failures
```

All pre-commit hooks run automatically on `git commit`. If they fail, fix the reported issues before retrying.

### PR title

Same format as commit messages:
`feat(chain): add streaming node for real-time output`

### PR description

Use the pull request template (`.github/PULL_REQUEST_TEMPLATE.md`). At minimum, fill in:
- **What** — what changed and why
- **How to test** — steps a reviewer can follow to verify
- **Checklist** — lint, tests, docs, env vars

### Review requirements

- Minimum **1 approval** from a team member who didn't author the PR
- All CI stages must be green before merge
- Resolve all reviewer comments before merging

### Merge strategy

Use **Squash and merge** for feature branches to keep `main` history clean.
Use **Merge commit** only for submodule version bumps so the pointer commit is preserved.

---

## Code standards

All code is enforced by pre-commit hooks and CI. There is no manual style negotiation.

### Linting & formatting — ruff

```bash
make lint-fix    # auto-fix safe violations + format
make lint        # check only (what CI runs)
```

Configuration is in each project's `pyproject.toml` under `[tool.ruff]`.
Line length: **100 characters**. Target version: **py313**.

### Type checking — mypy

```bash
uv run mypy chain/src/ imdbapi/src/
```

Strict mode is enabled. All public functions must have type annotations. Use `# type: ignore[<code>]` only as a last resort, always with a comment explaining why.

### Secrets detection — detect-secrets

`detect-secrets` runs on every commit. If it flags a false positive, add an inline comment:

```python
some_variable = "not-actually-a-secret"  # pragma: allowlist secret
```

To update the secrets baseline after adding a legitimate false-positive allowlist:
```bash
detect-secrets scan > .secrets.baseline
```

---

## Testing requirements

- **Unit tests required** for all new logic
- **No real API calls** in tests — mock at the HTTP boundary (`respx` for httpx, `pytest-mock` for LLM clients)
- Coverage should not decrease on any PR (CI enforces this via Cobertura reports)
- Tests go in `tests/` mirroring the `src/` structure

```bash
make test         # runs chain + imdbapi tests
make test-all     # also runs rag_ingestion tests
make test-chain   # only chain
make test-imdbapi # only imdbapi
make test-rag     # only rag_ingestion
```

---

## Working with submodules

### Updating a submodule to the latest commit on its main branch

```bash
cd chain/   # or imdbapi/ or rag_ingestion/
git fetch && git checkout main && git pull
cd ..
git add chain/
git commit -m "chore(chain): bump to latest main"
```

### Pinning a submodule to a specific release

```bash
cd chain/
git fetch --tags && git checkout v1.2.0
cd ..
git add chain/
git commit -m "chore(chain): pin to v1.2.0"
```

### After pulling backend changes that moved a submodule pointer

```bash
git pull
git submodule update --init --recursive
```

### After someone else adds a new submodule

```bash
git pull
git submodule update --init --recursive   # picks up the new submodule
```

---

## Release process

Each repo is released independently with semantic versioning (`vMAJOR.MINOR.PATCH`).

```
MAJOR — breaking API or behavior change
MINOR — new feature, backwards compatible
PATCH — bug fix, backwards compatible
```

**Steps:**

1. Update `version` in `pyproject.toml`
2. Update `CHANGELOG.md` — move items from `[Unreleased]` to the new version section
3. Commit: `git commit -m "chore: release v1.2.0"`
4. Tag: `git tag v1.2.0`
5. Push: `git push origin main --tags`

Jenkins detects the tag and automatically runs the release pipeline (lint → test → build Docker image → push to registry).

After releasing a submodule, update the pointer in the backend repo:
```bash
cd chain/ && git checkout v1.2.0 && cd ..
git add chain/
git commit -m "chore(chain): release v1.2.0"
git push
```

---

## Jenkins CI

### Adding Jenkins credentials

All credentials are stored in Jenkins (never in code). Required credentials per repo are documented at the top of each `Jenkinsfile`.

Add a credential: **Jenkins → Manage Jenkins → Credentials → System → Global → Add Credentials**

### Triggering a manual job

**rag_ingestion — manual dataset ingestion:**
1. Open the `movie-finder-rag` pipeline in Jenkins
2. Click **Build with Parameters**
3. Set `RUN_INGESTION=true`, `COLLECTION_NAME`, `VECTOR_STORE`
4. Click **Build**
5. After success: download `ingestion-outputs.env` artifact, update chain credentials

**backend — manual staging deploy:**
1. Open the `movie-finder-backend` pipeline
2. Click **Build with Parameters**
3. Set `DEPLOY_STAGING=true`
4. Click **Build**

### PR validation

Jenkins runs automatically on every PR. The pipeline must be green before a PR can be merged. Check the Jenkins build link in the PR status checks.

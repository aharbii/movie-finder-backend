## What and why

<!-- What does this PR change? Why is it needed? Link any related issues or tickets. -->

## How to test

<!-- Steps a reviewer can follow to verify the changes work correctly. -->

1.
2.
3.

## Checklist

<!-- Check all that apply. -->

### Code quality

- [ ] `make lint` passes with zero errors
- [ ] `make test` passes with zero failures
- [ ] New logic has unit tests
- [ ] No real API calls in tests (mocked at HTTP boundary)
- [ ] No secrets or credentials added to code or test fixtures

### Documentation

- [ ] Public functions/classes have type annotations
- [ ] New environment variables added to the relevant `.env.example`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] README updated if the public interface or setup steps changed

### Review

- [ ] PR description links the issue and discloses the AI authoring tool + model
- [ ] Any AI-assisted review comment or approval discloses the review tool + model

### Submodule changes _(if applicable)_

- [ ] Submodule pointer updated to a tagged release, not a raw commit
- [ ] Backend `pyproject.toml` / workspace config updated if dependencies changed

### Release _(for release PRs only)_

- [ ] `version` bumped in `pyproject.toml`
- [ ] `[Unreleased]` section moved to the new version in `CHANGELOG.md`
- [ ] Git tag created after merge: `git tag vX.Y.Z && git push origin --tags`

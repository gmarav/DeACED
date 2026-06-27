# Contributing to DeACED

Thanks for your interest!

## Setup

```bash
pip install -e ".[dev]"
pre-commit install
```

## Before opening a PR

```bash
ruff check .
ruff format --check .
mypy
pytest -q
```

## Guidelines

- Keep the core dependency-free (standard library only).
- All code, comments and commit messages in English.
- Add a test for every fix or new feature. Fixtures must be small and synthetic
  (no third-party data) — the repo is public.
- Preserve the text dump format unless intentionally changing it (it is covered by
  a golden test); discuss format changes in an issue first.
- Golden fixtures live in `tests/data`; regenerate them with `tools/regen_goldens.sh`
  (needs a JDK and the patched jar -- see `tools/README.md`).
- Update `CHANGELOG.md` and, when behaviour diverges from upstream, `NOTICE`.

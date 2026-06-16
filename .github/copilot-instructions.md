# GitHub Copilot Instructions for Vultron

## Project Overview

Vultron is a research prototype for a federated, decentralized protocol for
Coordinated Vulnerability Disclosure (CVD), developed at CERT/CC. It is
**not production-ready**.

Core domain concepts: **CVD** (single-party), **MPCVD** (multi-party), three
interacting state machines — Report Management (RM), Embargo Management (EM),
Case State (CS) — modeled as Behavior Trees.

## Authoritative Reference

**`AGENTS.md`** is the authoritative guide for all Vultron coding agents.
It covers: naming conventions, validation rules, architecture, key files map,
common pitfalls reference index, GitHub label conventions, commit workflow,
skill interaction rules, and the full technology stack. **Read it first.**

This file provides a quick-start orientation and a few pitfalls that benefit
from early visibility in the context window.

## Commands

```bash
# Setup
uv sync --dev

# Format Python sources (run before every commit)
uv run black vultron/ test/ && uv run flake8 vultron/ test/

# Full test suite — run exactly once, read the last 5 lines
uv run pytest --tb=short 2>&1 | tail -5

# Single test file (faster feedback)
uv run pytest test/test_semantic_activity_patterns.py -v

# All linters
uv run flake8 vultron/ test/
uv run mypy
./mdlint.sh                     # markdown only

# Docs
uv run mkdocs serve
```

Do not run Black on markdown files — use `markdownlint-cli2` for those.

---

## Common Pitfalls & Type Checking

### mypy/pyright: dict Variance and Protocol Types

mypy and pyright are strict about type variance. If you encounter an error like
"`dict[K, V]` is not assignable to `dict[K, V] | None`", the issue is likely
that `V` involves a callable with a `Protocol` type parameter. **Fix this by
switching to `Mapping[K, V]` (covariant in value type) instead of `dict`.**
Both `mypy` and `pyright` must pass before committing.

### Spec File Format & References

All Vultron specifications are **YAML files** (`.yaml`, not `.md`). When you
need to reference a spec, use `uv run spec-dump` or invoke the `load-specs`
skill to get the authoritative, inheritance-resolved JSON view. **Never
construct spec file paths manually** — the load-specs output is the source of
truth.

### History File Immutability Exceptions

`plan/history/` files are normally immutable (enforced by pre-commit), but you
**SHOULD override immutability in two cases**:

1. **Corrupt or impossible dates** — fix entries with future dates or other data
   errors using git blame to determine correct timestamps
2. **Explicit user override** — when the user explicitly asks you to override
   immutability rules

Use `uv run append-history` to add new history entries (never append directly).
Reference: `specs/history-management.yaml` § HM-03.

**`append-history` timestamp rule:** When migrating or backfilling historical
entries (not recording current work), **always** pass `--timestamp <ISO8601>`
derived from `git log`/`git blame`. Never let it default to today's date — this
produces corrupt history that requires an immutability override to fix.

### Test Suite Runtime Expectations

The full pytest suite can take **60–120+ seconds** to complete. Use
`initial_wait: 180` when running `pytest` in sync mode. Long-running tests are
normal. For faster feedback during development, run a single test file:
`uv run pytest test/test_semantic_activity_patterns.py -v`.

For the single-run rule and full test suite guidance, see **`AGENTS.md`**
§ Agent Quickstart and § Commit Workflow.

**CRITICAL — Demo/integration test requirement:** The default `pytest` run
**omits** `@pytest.mark.integration` tests. CI always runs all tests. If **any**
file under `vultron/demo/` or `test/demo/` was touched, you **must** run the
full suite before committing:

```bash
uv run pytest -m "" --tb=short 2>&1 | tail -5
```

Skipping this is how PRs end up blocked by 17-minute CI runs.

---

## Further Reference

- **`AGENTS.md`** — Authoritative agent guide (naming, architecture, pitfalls,
  commit workflow, skill interaction rules)
- `specs/` — Formal requirements with unique IDs (e.g., `HP-01-001`)
- `notes/` — Durable design insights (architecture, BT integration, AS2 semantics)
- `docs/adr/` — Architecture decision records
- `.agents/skills/format-code/SKILL.md`, `.agents/skills/run-linters/SKILL.md`,
  `.agents/skills/run-tests/SKILL.md` — Canonical format, lint, and test commands

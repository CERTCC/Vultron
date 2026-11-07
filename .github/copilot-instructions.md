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

# Format and lint Python sources (run before every commit)
uv run ruff check --fix && uv run ruff format

# The test gate — always targeted, run exactly once, read the `exit:` line
logs="/tmp/vultron-$(basename "$(git rev-parse --show-toplevel)")"
git fetch -q origin main || { echo "fetch failed — stop and report"; exit 1; }; gate=$(PYTHONPATH= uv run targeted-tests --base origin/main --pytest); rc=$?
[ "$rc" -eq 0 ] && { eval "$gate" > "$logs-gate.log" 2>&1; rc=$?; tail -20 "$logs-gate.log"; }; echo "exit: $rc"; (exit $rc)

# Single test file (faster feedback)
uv run pytest test/test_semantic_activity_patterns.py -v

# All linters (ruff reads its scope from pyproject.toml)
uv run ruff check && uv run ruff format --check
uv run mypy
./mdlint.sh                     # markdown only

# Docs
uv run mkdocs serve
```

`ruff format` skips markdown by config — use `markdownlint-cli2` for those.

---

## Common Pitfalls & Type Checking

### mypy/pyright: dict Variance and Protocol Types

mypy and pyright are strict about type variance. If you encounter an error like
"`dict[K, V]` is not assignable to `dict[K, V] | None`", the issue is likely
that `V` involves a callable with a `Protocol` type parameter. **Fix this by
switching to `Mapping[K, V]` (covariant in value type) instead of `dict`.**
`mypy` must pass before committing. `pyright` runs in CI only (PAD-18-027), so
read its findings off the `Lint (pyright)` job.

### Spec File Format & References

All Vultron specifications are **YAML files** (`.yaml`, not `.md`). When you
need to reference a spec, start from the map (`PYTHONPATH= uv run spec-dump
--index`), then load only what you need with `--topic`, `--group`, or `--ids`
(add `--slim` for statements only), or invoke the `load-specs` skill, to get
the authoritative, inheritance-resolved JSON view. Do not print the unfiltered
dump; it is far too large to read. **Never
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

### Test Gate Runtime Expectations

The targeted gate usually finishes in a couple of minutes. Use
`initial_wait: 180` when running it in sync mode. For faster feedback while
writing a test, run that one file: `uv run pytest <path> -n 0`.

For the single-run rule and the gate's shape, see **`AGENTS.md`**
§ Agent Quickstart and § Commit Workflow.

**No local gate runs the whole suite** (PAD-18-003, PAD-18-008, PAD-18-015).
The default `pytest` run omits `@pytest.mark.integration` tests, but the gate
command carries `-m ""`, so an integration-marked test among the selected
files still runs (PAD-18-011). The reach beyond the selected files is CI's:
it runs both suites on every push, and GitHub's required `CI gate` refuses
the merge until that run passes.

A change under `vultron/demo/` or `test/demo/` is no exception. That standing
requirement for a full local run is retired: CI runs those tests and the
required `CI gate` judges the run (PAD-18-008). `demo-integration.yml` covers
a `vultron/demo/` change; a `test/demo/` one is covered by `python-app.yml`'s
`rest` part, since `demo-integration.yml`'s `paths` list `vultron/**` but not
`test/demo/**`.

---

## Further Reference

- **`AGENTS.md`** — Authoritative agent guide (naming, architecture, pitfalls,
  commit workflow, skill interaction rules)
- `specs/` — Formal requirements with unique IDs (e.g., `HP-01-001`)
- `notes/` — Durable design insights (architecture, BT integration, AS2 semantics)
- `docs/adr/` — Architecture decision records
- `.agents/skills/format-code/SKILL.md`, `.agents/skills/run-linters/SKILL.md`,
  `.agents/skills/run-tests/SKILL.md` — Canonical format, lint, and test commands

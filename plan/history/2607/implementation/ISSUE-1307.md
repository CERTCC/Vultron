---
source: ISSUE-1307
timestamp: '2026-07-22T17:34:24.758091+00:00'
title: Demo scenario report tool
type: implementation
---

## Issue #1307 — Demo scenario report tool: parse JSONL case-ledger logs into readable reports

PR: <https://github.com/CERTCC/Vultron/pull/1604>

Implemented a standalone, read-only report tool at `vultron/demo/report.py`
(invokable as `python -m vultron.demo.report`) that parses the per-actor
case-ledger JSONL replica files written by demo scenario runs and renders a
selective, human-readable timeline. Fulfils `specs/demo-report.yaml`
(DRPT-01 through DRPT-05). No ADR (read-only utility over an existing artifact
format, per IDEA-1286).

Highlights:

- Discovery: recursive glob of `**/*-case-ledger.jsonl` under `$DEVLOGS_DIR`
  (default `devlogs/`), actor name derived from the parent directory.
- Distilled `CaseTimelineEvent` pydantic v2 model — camel/snake tolerant,
  handles ADR-0036 dimension-object and legacy flat state spellings; merge +
  dedup by `entry_hash`, order by `log_index`, per-actor replica presence.
- Friendly non-URI naming; active-voice summaries from a MessageSemantics
  phrase table; full ids only as secondary detail / HTML tooltips.
- Markdown table and self-contained static HTML renderers, both with the
  per-actor presence matrix; `--format`, `--output`, `--no-open`; exit codes
  0 / non-zero on missing dir / no files / parse error.
- Tests: parse→model, both renderers, CLI smoke (incl. `--no-open`) in
  `test/demo/test_report.py`.

Verification: black/flake8/mypy/pyright clean; full suite `uv run pytest -m ""`
6061 passed, 0 failures.

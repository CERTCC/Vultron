---
source: LEDGER-INVARIANTS-950
timestamp: '2026-06-15T20:16:37.077324+00:00'
title: Single-DataLayer demo case-ledger endpoint semantics
type: learning
---

`demo_triggers.demo_get_case_ledger` ignores the `actor_id` path parameter (`# noqa: ARG001`) and returns all `CaseLedgerEntry` objects for the case from the shared DataLayer. In the single-DataLayer test environment the "case-actor log" is therefore the union of all actors' entries. Test helpers should be named `_fetch_case_log` (not `_fetch_case_actor_log`) and docstrings must say "combined case log" to avoid implying per-replica isolation. The event types currently recorded in this unified log are `add_participant_status` and `submit_report` — not the full CI invariant 5 set (pending #789).

**Promoted**: 2026-06-15 — captured in `notes/demo-ci-diagnostics.md` and `AGENTS.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/978>.

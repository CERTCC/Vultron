---
source: CONCERN-3430
timestamp: '2026-11-16T18:44:42.341389+00:00'
title: In-memory stores stay shared per actor; a named helper opens a fresh one
type: learning
---

Theme: theme:test-and-ci — decides whether in-memory SQLite stores isolate per instance or fail on reuse.

## Scope (narrowed)

Option 1 below (documenting the trap) moved to #5366. This Concern now tracks only the open design question:

- Should in-memory stores be isolated per instance by default (option 2), or should constructing a second in-memory store for an `actor_id` that already has a live engine fail or warn loudly (option 3)?
- Deciding needs an audit first: which tests and harnesses rely on two in-memory stores for one `actor_id` sharing an engine (`get_actor_engine` caches by resolved store URL in `vultron/adapters/driven/datalayer_sqlite/engine.py`).

---

## Summary

Two `SqliteDataLayer("sqlite:///:memory:", actor_id=...)` instances constructed with the same `actor_id` in one process **share state**. A "fresh" store sees the previous one's rows — outbox entries, cases, activities. Nothing raises; the reads simply return another scenario's data.

`test/adapters/driven/trigger_activity_adapter/conftest.py` already works around it (`clear_all()` on setup teardown), but the workaround is undocumented and unenforced, so a test or script that omits it gets silent contamination rather than an error.

## Why this is worth tracking

It produced **two wrong conclusions by two independent agents** inside a single session on #3428:

1. A verification script reported that a declining admission policy emitted `Accept`+`Create` — the outbox rows were leaked from the previous scenario. The real behaviour was correct. I nearly "fixed" a non-bug.
2. An adversarial review agent hit the same trap and had to be explicitly warned about it in its instructions before its measurements were trustworthy.

The failure mode is the worst kind: results that look plausible, are internally consistent, and are wrong. An agent writing a throwaway harness to check protocol behaviour has no reason to suspect the store, and the leaked rows are exactly the type the scenario under test would have produced.

## Suggested remediation

Options, roughly increasing in cost:

1. **Document it** where an agent will hit it — `notes/testing-pitfalls.md` and/or `test/AGENTS.md`. Cheapest, and matches how the repo records other test traps.
2. **Make isolation the default.** `get_actor_engine` derives a per-actor engine; for `:memory:` it could additionally key on a per-instance nonce so each construction is genuinely fresh, with sharing opt-in for the cases that want it.
3. **Fail loudly on reuse** — warn when a second in-memory store is constructed for an `actor_id` that already has a live engine in this process.

Option 1 should happen regardless. Whether 2 is safe depends on which tests rely on the current sharing, and that inventory is part of the work.

## Discovery

Found twice while verifying the CaseProposal admission gate in #3428 (#1315 / #3399).


**Resolved**: 2026-11-16. Implementation is tracked in #6525.

**Decision:** every handle for one actor keeps opening that actor's one in-memory store. Store identity lives in the URL (DL-07-004), and `clone_for_actor` and `get_datalayer` open many handles for one actor, which must reach the same rows. Per-instance isolation (option 2) would split an actor's store across its clones. A warn-on-reuse check (option 3) would fire on every legitimate clone. Neither is adopted.

Between tests, the trap is already closed by the autouse `_dispose_actor_stores_between_tests` fixture in `test/conftest.py`. The remaining gap is a standalone script, or a test with several scenarios, that wants a store that starts empty. #6525 adds a named helper that returns a uniquely named in-memory URL, extracted from the inline idiom in `vultron/demo/helpers/participant_suggestion.py`. The documentation task #5366 names that helper.

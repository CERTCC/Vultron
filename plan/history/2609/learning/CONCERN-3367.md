---
source: CONCERN-3367
timestamp: '2026-09-18T13:56:14.726216+00:00'
title: docs/ arm of the ADR-0088 CaseActor->CASE_MANAGER prose sweep
type: learning
---

## Summary

Apply ADR-0088's prose half to `docs/`: rename prose that uses "CaseActor" as a synonym for the case **authority** to name **the CASE_MANAGER**. This is the last untracked arm of the ADR-0088 terminology sweep — `notes/` (#3306 / PR #3290), `AGENTS.md` (#3291), and `specs/` (#3342 / PR #3361) are done.

## Surface symptom vs. underlying problem

- **Surface symptom**: ~63 files under `docs/` still contain "CaseActor" / "Case Actor"; a naive reader might mass-rename them all.
- **Underlying problem**: only prose that means the *authority* is wrong. Most occurrences are correct and MUST stay:
  - `docs/adr/*` are historical decision records (several titled with CaseActor — 0021, 0041, 0051); immutable by ADR policy.
  - `docs/topics/scenarios/*` and `docs/topics/case_lifecycle/*` describe the concrete demo/prototype actor (containers, inboxes, seeding steps).

  This is a per-occurrence judgment sweep, not a find-and-replace.

## Category

Documentation consistency / terminology (ADR-0088 completion).

## Evidence

- Discriminator + worked examples: `plan/incoming/learnings/20260917-3342-caseactor-rename-keeps-infrastructure-concrete.md` — rewrite authority *actions* (commit/author ledger, maintain shared state, single-writer, route/authorize); keep *infrastructure/identity* (URI, inbox/outbox, DataLayer/store, container, code identifiers, the `CaseActor` domain type, the `case-actor` URL anti-pattern).
- Rule: `notes/spec-authoring-rules.md` and glossary ambiguity #13. ADR: `docs/adr/0088-consolidate-case-authority-determination.md`.

**Resolved**: 2026-09-18 — swept `docs/` directly in Docs PR #3381 (<https://github.com/CERTCC/Vultron/pull/3381>), which `Closes #3367`. No separate implementation issue was created (the sweep was bounded and executed in-session to save a review cycle). 25 authority-meaning occurrences were rewritten to `CASE_MANAGER` across 11 files; 163 concrete-actor occurrences were verified as deliberate keeps; `docs/adr/*`, `docs/adr/index.md`, the already-correct glossary, and generated scan artifacts were skipped. One inverse error was also fixed (a DataLayer wrongly attributed to the `CASE_MANAGER` role in `draft-vultron-replication-spec.md`). No spec/notes files were written — the discriminator already lives in `notes/spec-authoring-rules.md` and the glossary.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3381>.

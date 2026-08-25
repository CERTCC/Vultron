---
title: CSB-18-001..004 referenced in code but absent from spec registry
type: learning
timestamp: '2026-08-19T00:00:00+00:00'
source: ISSUE-2236
signal: spec-gap
---

The implementation of #2236 references CSB-18-001 (RM↔VFD cross-machine
entailment) in docstrings, module-level comments, and `Closes` lines, and
mentions CSB-18-002..004 (PXA→EM entailments) in `cross_machine_invariants.py`.
None of these entries exist in `specs/cs-behavior.yaml` or any other spec file.

`PYTHONPATH= uv run spec-dump | grep CSB-18` returns empty.

A follow-up task should add CSB-18-001 (the RM↔VFD rule now enforced) and
CSB-18-002..004 (PXA→EM rules reserved for the receive path) to
`specs/cs-behavior.yaml`.

**Promoted**: 2026-08-24 — captured in specs/cs-behavior.yaml (CSB-18-001..004).
Docs PR: [PR URL TBD].

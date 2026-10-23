---
source: CONCERN-1445
timestamp: '2026-07-15T17:05:52.819064+00:00'
title: No spec-level mapping from EM/CS/RM protocol shorthands to AS2 wire types
type: learning
---

## Summary

The behavioral conformance specs produced by #1423, #1424, and #1425 (RMB, EMB, CSB)
reference EM/CS/RM message shorthands (EP, EA, EV, CP, CX, RS, RV, etc.) throughout
their preconditions, triggers, and steps. The wire mapping spec
(`specs/vultron-as2-mapping.yaml`, VAM) maps `MessageSemantics` enum values to AS2
wire patterns. Neither spec layer bridges the two: there is no normative document that
maps EP → `MessageSemantics.INVITE_TO_EMBARGO_ON_CASE` → `Invite(Event)[context=VulnerabilityCase]`.

## Category

Specification completeness / traceability

## Severity

Medium — the gap does not break the implementation (the mapping exists in code), but it
makes the spec layer non-self-contained for an independent implementor.

## Evidence

- `specs/rm-behavior.yaml` (RMB), `specs/em-behavior.yaml` (EMB), `specs/cs-behavior.yaml`
  (CSB) all use protocol shorthand labels (RS, RV, EP, EA, CP, CX…) as trigger `value`
  fields and in prose.
- `specs/vultron-as2-mapping.yaml` (VAM) maps `MessageSemantics` enum values to AS2
  patterns — with no reference to the shorthand labels.
- The only authoritative shorthand→MessageSemantics mapping lives in
  `vultron/wire/as2/extractor.py` (`SEMANTICS_ACTIVITY_PATTERNS`) and implicitly in
  `vultron/core/case_states/patterns/potential_actions.py`.
- An independent implementor reading EMB-01-001 ("receiving EP MUST...") and
  VAM-05-005 ("INVITE_TO_EMBARGO_ON_CASE MUST be Invite(Event)...") cannot connect them
  without reading the code.

## Impact if Ignored

- Independent implementors cannot achieve full L3 behavioral conformance from specs alone —
  they must reverse-engineer the shorthand mapping from code.
- Adds friction for any future transport (non-AS2) that needs to produce its own mapping:
  the intermediate `MessageSemantics` layer is not spec-documented.
- RMB/EMB/CSB `satisfies` relationships cannot reference VAM items, leaving a gap in the
  cross-reference graph.

**Resolved**: 2026-07-15 — implementation tracked in #1449, follow-up in #1450.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1448>.
Notes: `notes/behavioral-conformance-specs.md` § "Protocol Shorthand → MessageSemantics → VAM Traceability".

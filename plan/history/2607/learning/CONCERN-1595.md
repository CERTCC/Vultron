---
source: CONCERN-1595
timestamp: '2026-07-22T17:37:16.270270+00:00'
title: DEMOMA scenario workflow specs use prose process descriptions instead of ECA-style
  preconditions/steps/postconditions
type: learning
---

## Summary

The DEMOMA spec groups describing demo scenario workflows (DEMOMA-06 through DEMOMA-11 in `specs/multi-actor-demo.yaml`) used flat ordered MUST statements — prose process descriptions — rather than the Event-Condition-Action (ECA) format (`trigger` / `preconditions` / `steps` / `postconditions`) used elsewhere in the spec corpus (e.g., `specs/cs-behavior.yaml`). Other spec files may have the same gap, but DEMOMA was the known instance. Demo scenario workflows are sequential, stateful processes with well-defined start states, ordered actions, and terminal conditions — exactly the shape that ECA-style requirements are designed to capture.

## Category

- Technical debt

## Severity

medium

## Evidence

- `specs/multi-actor-demo.yaml` groups DEMOMA-06 through DEMOMA-11: scenario workflows expressed as flat MUST statements with no `trigger`, `preconditions`, or `postconditions` fields.
- `specs/cs-behavior.yaml`: reference implementation of the intended ECA format — each group carries a `trigger`, typed `preconditions`, ordered `steps[]` with `actor`/`action`/`expected`, and `postconditions`.

## Impact if Ignored

Scenario workflow specs remained ambiguous about start state, sequencing preconditions, and terminal conditions. Implementers must infer context from adjacent prose rather than reading a structured contract. Coverage gaps are invisible because the spec provides no machine-readable trigger/postcondition structure to check against. The inconsistency also makes it harder to extend or review scenario specs uniformly.

## Resolution

**Resolved**: 2026-07-22 — implementation tracked in #1606.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1605>.
Spec: `specs/multi-actor-demo.yaml`.
Notes: `notes/behavioral-conformance-specs.md`.

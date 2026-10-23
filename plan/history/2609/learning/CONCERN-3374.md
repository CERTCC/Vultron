---
source: CONCERN-3374
timestamp: '2026-09-28T18:23:48.094638+00:00'
title: HP-04 describes a handler payload-access contract no handler uses
type: learning
---

## Summary

`specs/handler-protocol.yaml` HP-04 constrains how handlers read activity data
using a vocabulary that does not exist in the codebase. Found while planning
issue #1769, which fixed the neighbouring HP-01-002 contradiction; this one is

unrelated to that work and is filed rather than folded in.

## Category

- [x] Technical debt

## Severity

low — the requirements are inert. Nothing enforces them and no code is wrong
because of them. The harm is that an agent reading HP-04 will look for an API
that is not there, or worse, build one.

## Evidence

- **HP-04-001** (MUST): "Handlers MUST access activity data via
  `dispatchable.payload`". `grep -rn "dispatchable" vultron/` finds nothing.
  There is no `dispatchable` object and no `.payload` attribute on the handler
  input.
- **What handlers actually do**: each received use case takes a typed
  per-semantic `VultronEvent` subclass in `__init__` and reads named domain
  fields off it (`request.log_entry`, `request.actor_id`, `request.fault_id`).
  Semantic extraction happens in the wire layer before dispatch, so by the time a
  handler runs the payload has already been promoted to typed core fields — the
  validate-at-edge pattern of ADR-0032.
- **HP-04-002** (MUST): "Handlers MUST use schema validation for type-safe
  payload access" — arguably satisfied in spirit (the events are Pydantic
  models), but it reads as an instruction to validate *inside* the handler, which
  is the opposite of validate-at-edge.
- Neither requirement carries a `verification:` field, so nothing detects the
  drift.

## Why this is the same species as #1769

HP-01-002 said handlers MAY return `None` or `HandlerResult` while UCORG-05-002
said MUST — resolved in this planning cycle. HP-04 looks like the same kind of
residue: a requirement written against an earlier handler shape that the codebase
moved past without anyone amending the spec. `specs/handler-protocol.yaml` is
worth a read-through as a whole rather than requirement-by-requirement, since a
third instance is plausible.

## Suggested Action

Establish what HP-04 was meant to guarantee, then either restate it in current
terms (typed `VultronEvent` field access; no re-reading the wire activity, per
ADR-0035) or retire it. Add `verification:` to whatever survives. Audit the rest
of HP for the same class of drift while the context is loaded.

## Out of Scope

- HP-01-002/003/004 — amended by the #1769 docs PR
- The `UseCaseResult` envelope work — #3371, #3372, #3373

## References

Source: #1769 (found during planning)
Docs PR: <https://github.com/CERTCC/Vultron/pull/3370>
Spec: `specs/handler-protocol.yaml` HP-04-001, HP-04-002
Related: ADR-0032 (validate at the edge), ADR-0035 (core does not re-read wire
activities for semantics)

**Resolved**: 2026-09-28 — implementation tracked in #3827. HP-04-001 restated as one typed-access rule with a verification clause; HP-04-002 removed as folded in (MS-09-001); HP-01-001, HP-01-002, HP-08-001, HP-08-002 amended in the same read-through (retired `DataLayer.update()` path, narrow persistence ports, verification clauses).
Docs PR: <https://github.com/CERTCC/Vultron/pull/3826>.
Spec: `specs/handler-protocol.yaml`.

---
source: CONCERN-1506
timestamp: '2026-07-17T22:45:04.805141+00:00'
title: Core reads wire AS2 activities back from the DataLayer
type: learning
---

## Original concern

Separate from the entity read path (#1496 / #1503), core BT nodes and use cases
read persisted **wire AS2 Activities** back from the DataLayer via
`dl.read(activity_id)` — e.g. `report/nodes/emit.py` and
`report/nodes/case_creation.py` read a stored `as_Offer`;
`report/nodes/storage.py` even documents "`dl.read()` does not work for
`VultronActivity`". AS2 Activities are wire-only (no core counterpart), so this
is a genuine boundary violation, not something the DL-05 entity work fixes.

This is a **Concern** whose deliverable is to generate implementation issues:
audit every site, classify each, and spin off the migration work.

- **ARCH-01-002**: core functions MUST accept and return domain types only.
- **ARCH-03-001**: AS2↔domain mapping MUST happen in exactly one location.
- **ARCH-09-001**: core models are as rich as/richer than wire.

## Resolution

**Resolved**: 2026-07-17 — planned via `plan-issue`.

Diagnosis: `dl.read(activity_id)` in core is a **symptom**; the root cause is
that the 29 AS2 protocol Activities were built wire-first and never given a core
counterpart, inverting "wire is a projection of core" (ADR-0017) and violating
ARCH-09-001. Vultron is a set of communicating **core** state machines; wire is
only the transport between isolated cores (Actor Knowledge Model), and an AS2
Activity is an envelope carrying a core fact — not a domain object.

Decision (ADR-0035) splits two needs `dl.read(activity_id)` conflates:

- **Semantic content** — MUST come from core state, captured by the extractor at
  interpretation time; core MUST NOT re-read the activity. Correlation between
  messages (Accept→Invite) flows through a core-entity relationship, not a wire
  re-read. This is NOT a license to clone each AS2 Activity into a 1:1 core class.
- **Envelope reconstitution** — reconstituting the verbatim original activity for
  a reply's inline `object_` MAY read a stored activity back (activity ids are
  non-regenerable `urn:uuid:` values; the Actor Knowledge Model requires the full
  inline original), but only via a wire/adapter-owned opaque seam — never core
  interpreting it.

Audited sites classified A (plumbing re-reads) / B (semantic-content reads,
split by domain) / C (envelope reconstitution) / D (not activities; covered by
DL-05 / #1503).

Docs PR: <https://github.com/CERTCC/Vultron/pull/1516>
Spec: `specs/datalayer.yaml` DL-06-001 through DL-06-005 (new DL-06 group).
Notes: `notes/datalayer-design.md` § "Activity Read-Back: Semantic Content vs.
Envelope Reconstitution" (includes the audited site inventory).
ADR: `docs/adr/0035-core-activity-representation-and-envelope-reconstitution.md`.

Implementation tracked in issues #1517 (A — plumbing), #1518 (B —
report/offer), #1519 (B — embargo), #1520 (B — actor/participant), and #1521
(C — envelope seam). All blocked by #1506, children of Epic #1394, added to
Project #24.

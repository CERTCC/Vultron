---
status: accepted
date: 2026-07-22
deciders: [adh]
---

# Publication-Intent Subtree Collapse: Bypass Leaves → Intent-Record-Driven Arms

*Implemented by issue #1310 (`task/1310-publication-intent-arms`).*

## Context and Problem Statement

The simulator `Publication` BT encodes publication intent as a combination of
a `PublicationIntentsSet` flag check, a `PrioritizePublicationIntents` Evaluator,
and per-artifact bypass leaves (`NoPublishExploit`, `NoPublishFix`, `NoPublishReport`)
that allow the BT to short-circuit each artifact arm. In production, these bypass
leaves and the flag check are structural artifacts of the simulator representation
and do not represent real call-out points.

How should the publication-intent subtree be structured in production?

## Decision Drivers

- Eliminate structural artifacts (bypass leaves, flag checks) that add BT
  complexity without adding real call-out point seams
- Preserve `PrioritizePublicationIntents` as the primary Evaluator — it is already
  the correct shape and should survive
- Keep per-artifact arms independently executable (exploit, fix, report)

## Considered Options

1. Intent-record-driven arms — Evaluator output gates which arms execute;
   bypass leaves disappear; three named arms (exploit, fix, report) remain
2. Unified loop over artifact list — Evaluator returns an ordered list; BT
   iterates it; no named arms
3. Keep all simulator nodes (no collapse)

## Decision Outcome

Chosen option: **Option 1 (lean)** — intent-record-driven named arms.
`PrioritizePublicationIntents` returns a `PublicationIntentDecision` record
`{publish_exploit, publish_fix, publish_report, rationale}`; the BT uses these
booleans to gate which of the three named arms execute. The
`PublicationIntentsSet` flag check and `NoPublish*` bypass leaves disappear.

The choice between Options 1 and 2 is **finalized as Option 1** at
implementation time (issue #1310). Option 1 preserves a readable BT structure
with three named arms, which is easier to audit and debug than a generic loop
over an artifact list; the added arm count is small (exactly three) and fixed
by the CVD domain (exploit, fix, report), so the generality of Option 2 buys
nothing here.

Each named arm is a `Selector(Sequence(ShouldPublishX, PrepareX, Publish),
Inverter(ShouldPublishX))`: the intent-record boolean gates the Prepare→Publish
Sequence, and the `Inverter` makes a "not intended" arm a graceful SUCCESS
no-op (rather than failing the whole `PublicationBT`). This mirrors the
routing-no-op idiom already used in `vultron/core/behaviors/sync/announce_tree.py`
and honours the positive-condition-naming rule (BTND-08-001): `ShouldPublishX`
is named positively, not `NoPublishX`.

### Consequences

- Good, because `NoPublish*` bypass leaves and `PublicationIntentsSet` flag check
  are eliminated — they were ProtocolInternal no-ops masquerading as structural nodes
- Good, because three named per-artifact arms are easier to understand and debug
  than a generic loop
- Good, because the `ShouldPublishX` gate nodes are named positively (BTND-08-001)
  and read the intent record directly, so the removed `NoPublish*` leaves leave no
  behavioural gap
- Neutral, because the intent record must be designed as a typed Pydantic BaseModel
  (`PublicationIntentDecision`) to support the boolean-gate pattern

## More Information

- Planning issue: #1200; implementation issue: #1310
- Simulator nodes: `PublicationIntentsSet`, `PrioritizePublicationIntents`,
  `NoPublishExploit`, `NoPublishFix`, `NoPublishReport` and the Reprioritize*
  nodes (see `notes/bt-fuzzer-nodes-report-management.md` § "Publication" and
  "Production Collapse 2")
- Output schema: `PublicationIntentDecision(publish_exploit, publish_fix,
  publish_report, rationale)` (Pydantic BaseModel) in
  `vultron/core/behaviors/report/publication_tree.py`
- Fuzzer backend: `PrioritizePublicationIntents` (Evaluator) and the
  `ShouldPublishExploit` / `ShouldPublishFix` / `ShouldPublishReport` gate
  nodes in `vultron/demo/fuzzer/report_management/publication.py`
- Precedent: ADR-0027 (Production Collapse 1) uses the same
  Evaluator-writes-typed-record pattern
- The `Publish` leaf expands into a draft-review-submit pipeline separately in
  ADR-0030 (Production Collapse 4); this ADR keeps `Publish` as a single
  Actuator per arm

Generated spec requirements: `behavior-tree-integration.yaml` BT-20-002

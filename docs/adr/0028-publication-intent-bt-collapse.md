---
status: proposed
date: 2026-07-09
deciders: [adh]
---

# Publication-Intent Subtree Collapse: Bypass Leaves → Intent-Record-Driven Arms

> **PROVISIONAL** — formed at planning time (issue #1200). Subject to revision
> when the implementation issue for this collapse candidate is worked.
> Implementation tracked by the issue blocked by #1200.

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
`PrioritizePublicationIntents` returns `{publish_exploit, publish_fix,
publish_report}`; the BT uses these booleans to gate which of the three named
arms execute. The `PublicationIntentsSet` flag check and `NoPublish*` bypass
leaves disappear.

> **Note**: The choice between options 1 and 2 is **deferred** to the
> implementation issue. The lean is Option 1 because it preserves readable
> BT structure with named arms.

### Consequences

- Good, because `NoPublish*` bypass leaves and `PublicationIntentsSet` flag check
  are eliminated — they were ProtocolInternal no-ops masquerading as structural nodes
- Good, because three named per-artifact arms are easier to understand and debug
  than a generic loop
- Neutral, because the intent record must be designed as a typed Pydantic BaseModel
  to support the boolean-gate pattern

## More Information

- Planning issue: #1200
- Simulator nodes: `PublicationIntentsSet`, `PrioritizePublicationIntents`,
  `NoPublishExploit`, `NoPublishFix`, `NoPublishReport` and the Reprioritize*
  nodes (see `notes/bt-fuzzer-nodes-report-management.md` § "Publication" and
  "Production Collapse 2")
- Implementation blocked by: #1200; also see issue #1251 (target factory function)
- Per-artifact Publish leaf is handled separately in ADR-0029

Generated spec requirements: `behavior-tree-integration.yaml` BT-20-002 (provisional)

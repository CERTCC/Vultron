---
status: accepted
date: 2026-07-30
deciders: [adh]
---

# Report-to-Others Party Discovery: Sentinel Over Inline BT Loop

## Context and Problem Statement

The `MaybeReportToOthers` simulator BT models party identification and
notification as an inline tick-driven loop: identify vendors/coordinators/others
→ iterate → send RS to each. Production Collapse 3 (ADR-0029, issue #1311)
replaced the `InjectParticipant` family with calls to the `suggest-actor-to-case`
trigger, but retained the outer loop structure with typed blackboard queues
(`identified_vendors`, `identified_coordinators`, `identified_others`).

Planning of issue #1252 surfaced a fundamental gap: those queues have no
production mechanism to populate them. The identification step
(`IdentifyVendors`, `IdentifyCoordinators`, `IdentifyOthers`) remained as
stub call-out factories with no real implementation path. The `SuggestXTrigger`
factories require a specific actor ID on the blackboard — something only the
STOCHASTIC fuzzer stub provides.

The design question is: **should party discovery and invitation be an inline
tick-driven BT subtree, or should it be driven by an external Sentinel
capability?**

## Decision Drivers

- The downstream suggest-actor-to-case protocol cascade (ADR-0026, ADR-0029)
  already handles the Offer → CaseActor → CaseOwner → Invite → Accept → Record
  flow correctly; no new BT leaf is needed for the invitation itself
- Populating typed queues (vendor IDs, coordinator IDs) from CPE/NVD/SBOM
  lookups or LLM evaluation is an inherently external, latency-variable
  operation — poorly suited to a tick-driven inline BT that must return
  quickly
- The Sentinel capability shape pattern (ADR-0024, issue #1143) explicitly
  covers "monitors a condition; when met, calls a trigger endpoint"; this is
  exactly the party-discovery model
- The existing `create_report_to_others_tree` module (from #1311) has no
  production callers — it exists only in tests — confirming it was never wired
  into the real protocol cascade

## Considered Options

1. **Inline BT loop** — retain the three-typed-sub-loop tree; fill in real
   Retriever implementations (CPE/NVD lookups) for `IdentifyX` factories so
   the loop executes against real data on every tick
2. **External Sentinel** — replace the inline loop entirely; a Sentinel
   capability that runs periodically or event-triggered, inspects
   the case, and calls `suggest-actor-to-case` for each uninvited candidate
3. **Hybrid** — inline BT provides a single-pass Retriever seam (one
   call-out that returns all candidates at once); Sentinel calls this subtree;
   no tick loop

## Decision Outcome

Chosen option: **Option 2 — External Sentinel**, because it matches the
capability shape taxonomy (ADR-0024), avoids coupling external I/O latency
into the BT tick loop, and the downstream trigger cascade already handles the
rest. No inline BT loop is needed.

The `create_report_to_others_tree` module from #1311 was an implementation
artifact of the intermediate Production Collapse 3 design and has been removed
by issue #1848 (see `notes/bt-fuzzer-rm-reporting.md` § "Sentinel supersession
note").

### Consequences

- Good, because party discovery becomes a proper Sentinel capability — observable,
  auditable, and independently replaceable without changing the BT tree structure
- Good, because the downstream suggest-actor-to-case cascade already works; no
  new BT machinery is required
- Good, because the Sentinel can use arbitrarily slow external queries (CPE
  lookups, LLM evaluation) without blocking the BT tick loop
- Bad, because the Sentinel architecture (#1143) has open design questions
  (invocation model, authentication, per-case vs global) that must be resolved
  before a concrete implementation can be built
- Neutral, because the tick-driven `create_report_to_others_tree` module has
  been removed (issue #1848); tests and bundles were removed with it

## More Information

- ADR-0024: Capability Shape Taxonomy (Sentinel pattern)
- ADR-0026: CaseActor-Routed Actor Suggestion and Invitation Flow
- ADR-0029: Notification Loop Collapse (Production Collapse 3)
- Issue #1143: Sentinel capability shape design (open)
- Issue #1147: Capability Shapes epic
- Issue #1252: Idea planning session that surfaced this decision (closed)
- `notes/bt-fuzzer-rm-reporting.md` § "Sentinel supersession note"

Generated spec requirements: `specs/behavior-tree-integration.yaml` BT-20-003
  (amended to record sentinel direction).

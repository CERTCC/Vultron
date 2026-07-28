---
status: accepted
date: 2026-07-22
deciders: [adh]
---

# Publish Leaf Expansion: Single Actuator → Draft-Review-Submit Pipeline

> Implemented by issue #1312 (`task/1607-signal-taxonomy` branch).  The
> four-step pipeline (Option 2) was adopted as specified.  The open design
> question about participant-comment broadcast in the review phase (AC-4) was
> **deferred** to a follow-on issue — the pipeline functions without it using
> the default auto-approve `ReviewAdvisoryDraft` Evaluator.

## Context and Problem Statement

The simulator `Publish` node is a single Actuator leaf that stands in for the
entire advisory publication workflow. In production, publishing a vulnerability
advisory involves at minimum: drafting the artifact, reviewing/approving it,
and submitting it to the external advisory platform. These are distinct operations
with distinct external seams that should be separately swappable.

How should the single `Publish` simulator leaf expand in the production BT?

## Decision Drivers

- Draft, review, and submit are distinct operations with distinct call-out point
  shapes (Composer, Evaluator, Actuator)
- The Actuator shape for external platform submission is confirmed by ADR-0024
  (Actuator amendment, 2026-07-07)
- The review phase may involve a broadcast-for-participant-comment step — this is
  an open design question
- The pipeline is invoked per-artifact (once each for exploit, fix, and report
  artifacts as decided by `PrioritizePublicationIntents`)

## Considered Options

1. Three-step pipeline: Composer → Evaluator → Actuator
2. Four-step pipeline: Composer → Evaluator → optional Composer (revision) → Actuator
3. Extended pipeline with participant-comment broadcast: Composer → Evaluator
   (parallel with broadcast-for-comment) → optional Composer → Actuator
4. Keep single `Publish` Actuator (defer expansion)

## Decision Outcome

Chosen option: **Option 2 (lean)** — four-step pipeline with an optional revision
Composer. The core shape is Composer (draft) → Evaluator (review/approve) →
optional Composer (revise based on feedback) → Actuator (submit to advisory
platform).

> **Note**: Whether the review phase should include a broadcast-for-participant-comment
> step (Option 3) is an **open design question** deferred to the implementation issue.
> The broadcast step would involve emitting an outbound Activity (a protocol-visible
> action that may trigger an `Accept/Reject` response pattern). The implementation
> issue MUST design the review-phase protocol before wiring the BT.

### Consequences

- Good, because draft and submit become independently swappable call-out points
- Good, because the Evaluator review step has a default implementation (auto-approve)
  that allows the pipeline to function before a real review agent is available
- Neutral, because the optional revision Composer adds complexity; implementations
  may start with the three-step variant and add revision later
- Uncertain, because the participant-comment broadcast question may expand scope
  significantly — this must be resolved at implementation time

## More Information

- Planning issue: #1200
- Simulator node: `Publish` (see `notes/bt-fuzzer-nodes-report-management.md`
  § "Publication" and "Production Collapse 4")
- Blocked by: #1200 (this planning issue) and the implementation issue for
  ADR-0028 (publication intents — the intent record must be in place before the
  pipeline is wired)
- Related: ADR-0024 (Actuator shape), ADR-0028 (publication-intent arm structure),
  issue #1251 (publication tree factory function)
- Each per-artifact arm in `create_publication_tree` (exploit arm, fix arm, report arm)
  uses this pipeline for its Publish step

Generated spec requirements: `behavior-tree-integration.yaml` BT-20-004 (provisional)

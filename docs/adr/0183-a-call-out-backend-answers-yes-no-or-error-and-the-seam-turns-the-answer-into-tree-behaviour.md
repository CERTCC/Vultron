---
status: proposed
date: 2026-11-06
created: 2026-11-06
updated: 2026-11-06
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Concern #3446, Concern #3427; ADR-0025, ADR-0095, ADR-0097,
  ADR-0110; specs/behavior-tree-integration.yaml BT-18; specs/case-proposal.yaml
  CP-05, CP-06-004
informed: []
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0025-call-out-point-abstraction-layer.md
  - 0097-capability-layer-four-shapes-and-core-declared-contracts.md
---

# A Call-Out Backend Answers Yes, No or Error, and the Seam Turns the Answer Into Tree Behaviour

## Context and Problem Statement

[ADR-0097](0097-capability-layer-four-shapes-and-core-declared-contracts.md) settled that every call-out point answers within one tick with SUCCESS or FAILURE, and BT-18 defines blackboard outputs only for SUCCESS.
Two gaps follow from that binary answer (Concern #3446):

1. **A "no" cannot carry a reason.**
   CP-06-004 requires the proposer of a declined case proposal to learn the reason where one is given, but the admission backend has no channel for one, so `CaseProposalDeclineRecord.reason` is never written on that path.
2. **"No" and "I could not tell" look the same.**
   An admission backend that cannot reach its policy service must return FAILURE, and the tree records a permanent decline of that proposal.
   The rest of the admission gate raises rather than returning FAILURE when it cannot tell, but the call-out seam cannot.

Concern #3427 asks two questions with the same root.
Nothing says what a tree does when an Actuator fails, or how an Actuator reports partial success, some targets done and others not.
And a rejected credential looks the same as a refused side effect.

The question: **what does a call-out backend answer, so that a refusal can carry its reason, an undecidable question never becomes a decision, and trees still branch only on fixed outcomes?**

## Decision Drivers

- A tree never parses text or data to recover a fixed-option decision.
- "I could not decide or act" must never be recorded as a decision.
- One answer shape for every capability, so a new kind of data needs no new verdict.
- The pattern already exists one layer up: a use-case result is a fixed-vocabulary verdict plus data (ADR-0095, ADR-0110).
- A re-run from holding must not repeat an outside side effect.

## Considered Options

- An answer with a fixed verdict (yes, no, error) and typed data; the seam turns it into tree behaviour.
- The same answer, read from the blackboard by each tree.
- Keep SUCCESS and FAILURE, and let FAILURE carry a cause code that each tree checks.

## Decision Outcome

Chosen option: "An answer with a fixed verdict (yes, no, error) and typed data; the seam turns it into tree behaviour", because it is the only option in which an undecidable question cannot become a decision by a tree's omission, while trees keep branching on success and failure alone.

1. **Every backend gives one answer: a fixed verdict and typed data.**
   The verdict is exactly one of *yes*, *no* or *error*.
   Each capability declares the data for each verdict: its outputs for *yes*, a refusal payload for *no* (a human-readable reason at minimum, with room for structured fields), and diagnostics for *error*.
   A new kind of data extends a declaration, never the verdict vocabulary.
2. **The seam turns the answer into tree behaviour.**
   *Yes* writes the declared outputs and the node succeeds.
   *No* writes the refusal payload to its declared keys and the node fails.
   *Error* raises an error that names the node, so the message is not judged and stays in holding to be tried again, as BT-18-027 already requires of a backend that exceeds its time budget.
   The diagnostics go into the raised error and the logs, never onto the blackboard.
   No tree reads the answer itself.
3. **A refusal is a decision; an error is not.**
   A backend answers *no* only for a decision it made.
   An unreachable service, a rejected credential, or a side effect it cannot confirm is *error*.
   So a decline that is recorded is always a decision about that request, and needs no expiry.
4. **An Actuator acts on one target per call and is safe to repeat.**
   A tree that acts on several targets makes one call per target and sees one verdict per call, so partial success never arises inside an answer.
   Each Actuator is keyed on an id the tree derives from the act, so a re-run from holding repeats no side effect.
   What a tree does after a *no* stays the tree's own logic.
5. **An Actuator's credentials are a deployment matter.**
   Where they live and which systems an Actuator may reach are outside the protocol.
   A rejected credential is *error*, never *no*.

This partially supersedes [ADR-0097](0097-capability-layer-four-shapes-and-core-declared-contracts.md) § 2, where every call-out answers with SUCCESS or FAILURE, and [ADR-0025](0025-call-out-point-abstraction-layer.md)'s contract of outputs written only on SUCCESS.
How a backend hands its answer to the seam (a returned value, or a declared slot the seam reads) is an implementation choice.

### Consequences

- Good, because an unreachable policy service leaves a proposal in holding instead of declining it for good.
- Good, because a declined proposer can learn why, as CP-06-004 requires.
- Good, because trees keep their success-and-failure shape, so no tree changes its branching to adopt the answer.
- Good, because a re-run from holding is safe for outside systems.
- Bad, because every existing call-out point and fuzzer shape migrates to the new answer, and the BT-18 statements that pin the binary answer change.
- Bad, because a backend author must tell *no* from *error* correctly; one that answers *no* for an outage brings back the permanent decline.
- Neutral, because a tree that wants partial results must ask per target, which costs one call per target.

## Validation

The decision is confirmed when the seam guard rejects an answer outside the three verdicts, a *no* writes its refusal payload to declared keys, an *error* raises and leaves the message in holding, and the case-proposal gate records the admission backend's reason and records no decline when its policy service is unreachable.

## Pros and Cons of the Options

### An answer with a fixed verdict and typed data; the seam turns it into tree behaviour

- Good, because the one place that interprets the answer is the seam, which already guards call-outs.
- Bad, because every backend migrates.

### The same answer, read from the blackboard by each tree

- Good, because trees could branch on future verdicts.
- Bad, because every tree that contains a call-out point changes, and a tree that ignores *error* reintroduces the permanent decline.

### FAILURE carries a cause code that each tree checks

- Good, because the change to backends is smallest.
- Bad, because every call-out point's tree must check the code, and a tree that forgets turns "unavailable" back into a permanent "no".

## More Information

Concern #3427's other questions stay open there: whether a capability's output is recorded in the case ledger, Retriever caching and staleness, and where a Composer sits relative to the Note and advisory behaviours.

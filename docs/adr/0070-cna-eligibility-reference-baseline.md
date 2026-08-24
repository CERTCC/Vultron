---
status: accepted
date: 2026-08-24
deciders: Allen D. Householder
consulted: plan-issue workflow (CONCERN-2108)
informed: Vultron contributors
---

# CVE Eligibility: Reference Baseline over Normative Citation or Implementation-Defined

## Context and Problem Statement

The CVE ID assignment behavior tree (`assign_cve_id_tree.py`) implements the
`IdAssignable` eligibility check as 9 individual call-out point nodes, each
grounded in a specific section of CNA Operational Rules v4.1.0. The draft
protocol spec (§7.4.3) has 2 sentences pointing back to the code as its
source, with no position on whether those criteria carry normative weight.

Open Question 9 of the draft spec asks: should the RFC cite CNA Operational
Rules eligibility criteria as normative external requirements, or treat the
checks as implementation-defined?

A secondary architectural question emerged during review: should the 9
individual `IdAssignable` child nodes be consolidated into a single
`EvaluateCveEligibility` Evaluator call-out point?

## Decision Drivers

- The RFC should not require implementers to track an independently-versioned
  external document's revision history to maintain conformance.
- Treating eligibility as entirely implementation-defined would allow a
  "conforming" implementation to skip eligibility checks entirely, weakening
  the meaning of CNA role conformance.
- CVE eligibility checking is a single logical capability (a set of criteria
  applied as a unit), not 9 independent capabilities.
- The current implementation is already grounded in v4.1.0 and should continue
  to be. Future rules revisions require a deliberate spec update.

## Considered Options

- **Normative external citation**: The RFC requires conforming CNA
  implementations to apply CNA Operational Rules (versioned edition pinned in
  the spec).
- **Implementation-defined**: The RFC says eligibility checks are
  implementation-defined; the code's v4.1.0 grounding is an internal
  implementation detail with no normative force.
- **Reference baseline**: The spec endorses v4.1.0 as the conformance baseline
  for this implementation while acknowledging the capability requirement
  (CNA role → ability to apply eligibility criteria). Future rules revisions
  require a spec update to re-endorse the new edition.

## Decision Outcome

Chosen option: **Reference baseline**, because it avoids the maintenance
coupling of a hard normative citation while preserving the CNA conformance
requirement and being transparent about which edition the reference
implementation follows.

On the architectural question: `IdAssignable` SHOULD be consolidated into a
single `EvaluateCveEligibility` Evaluator call-out point (BTND-05-007). The
current 9-node structure treats one logical capability as 9 independent
pluggable checks, which misrepresents the substitution unit. The correct
abstraction is one call-out that evaluates all criteria and returns a verdict.
A separate Task issue tracks this refactoring.

### Consequences

- Good, because the spec clearly states CNA role requires the assignment
  capability without versioning the RFC to a specific external document
  edition.
- Good, because implementers can see exactly which edition this reference
  implementation follows (v4.1.0) and what a future update requires.
- Good, because the single-Evaluator design correctly models the substitution
  unit: replace the entire eligibility evaluator (e.g. for v4.2.0) without
  touching the surrounding BT structure.
- Bad, because the current code (9 individual nodes) does not yet conform to
  BTND-05-007. Conformance is deferred to the refactoring Task.
- Neutral, because the protocol spec need not cite a specific rules version;
  the version pin lives in the implementation, not the RFC text.

## Pros and Cons of the Options

### Normative external citation

- Good, because conformance is precisely defined: check against the named
  edition.
- Bad, because rules revisions make any pinned conformance claim stale or
  wrong without a spec update, creating an ongoing maintenance burden.
- Bad, because the RFC becomes coupled to an independently-governed document
  with its own release cycle.

### Implementation-defined

- Good, because implementers are free to substitute their own eligibility
  criteria without a conformance violation.
- Bad, because "conforming CNA implementation" then has no minimum eligibility
  bar, weakening what the CNA role means in the protocol.

### Reference baseline (chosen)

- Good, because the RFC anchors CNA conformance to a real-world standard
  without hard-versioning the RFC itself.
- Good, because the implementation is transparent about its grounding (v4.1.0)
  and future migration path (update spec + code when new edition is adopted).
- Neutral, because it accepts that a rules revision requires both a code
  update and a spec update — this is the right tradeoff given that eligibility
  criteria are not something the protocol can or should define independently.

## More Information

Generated spec requirements: `specs/behavior-tree-node-design.yaml`
BTND-05-007, BTND-05-008.

Resolves CONCERN-2108 (Open Question 9 from
`docs/reference/draft-vultron-spec.md`).

Refactoring Task: see impl issue created alongside this ADR.

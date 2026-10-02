---
status: accepted
date: 2026-10-02
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Issue #4067; PR #4087; specs/case-ledger-processing.yaml CLP-08;
  specs/case-proposal.yaml CP-09-001; specs/case-management.yaml CM-02-008
informed: []
stakeholder_type: [project-contributor]
---

# The Per-Case Genesis Hash Is Anchored to the Case Owner, Not the CaseActor

## Context and Problem Statement

Every case ledger starts from a per-case genesis hash, `SHA-256(case_id | created_at | <actor id>)` (CLP-08).
CLP-08-002 named the actor input `case_actor_id`, the URI of the CaseActor created for the case.
The `VulnerabilityCase` construction validator has always computed the hash from `attributed_to` instead, and `attributed_to` names the case owner on every creation path (CP-09-001, CM-02-008).

So the two creation paths disagreed.
A case the owner created itself was hashed on the owner.
PR #4087 made the proposal path, where the CaseActor creates the case from the owner's `CaseProposal`, pass a hash computed from the executing CaseActor.
That kept the proposal path compliant with the spec as worded, but the same case would hash differently depending on who created it, and two formulas now lived in the code.

The question: **which actor id anchors a case's genesis hash?**

## Decision Drivers

- One case, one genesis hash, whichever actor runs the creation code.
- One formula in the code, so a new creation path cannot pick the wrong anchor without anyone noticing.
- A replica carries the sender's hash; it never recomputes it (ADR-0103).

## Considered Options

1. **Anchor to the CaseActor.** Every creation path passes the CaseActor id or an explicit hash, and the validator stops defaulting from `attributed_to`.
2. **Anchor to the case owner.** CLP-08-002 names the owner (`VulnerabilityCase.attributed_to`), and the validator's owner-based default is the single definition.

## Decision Outcome

Chosen option: **Option 2, anchor to the case owner.**
The CaseActor acts on the case as the owner's delegated proxy, so the owner is the identity the case starts from.
A case the owner creates and a case the CaseActor creates from the owner's `CaseProposal` then hash the same for the same `(case_id, created_at, owner)`.

The formula lives in `compute_genesis_hash`, and the `VulnerabilityCase` validator is its only caller on a creation path.
A creator sets `attributed_to` and lets construction compute the hash.
`CreateCaseFromProposalNode` passes no hash of its own.
A received case keeps the `genesisHash` it arrived with.

### Consequences

- Good, because a case's genesis no longer depends on which actor ran the creation code.
- Good, because a new creation path that sets `attributed_to` gets the right hash with no further work, and nothing has to remember to pass one.
- Neutral, because ownership transfer rewrites `attributed_to` (CM-21-002) but not the stored hash. The anchor is the owner *at creation*, which is what CLP-08-002 says.
- Bad, because a ledger started under the old proposal-path anchor no longer matches what a verifier recomputes from the case. The project has no backwards-compatibility requirement, so such stores are reset rather than migrated.

## Validation

- `test/core/models/test_case_ledger.py` pins the digest as the SHA-256 of the pipe-joined, owner-anchored inputs.
- `test/core/behaviors/case/test_case_proposal_received_tree.py` (`TestCLP08002GenesisHashAnchoredToTheOwner`) asserts that the proposal path hashes on the owner, that it agrees with a self-created case, and that the owner's replica keeps the sender's hash unchanged.

## More Information

- Amends the reading of PR #4087's proposal path; ADR-0041 (CASE_MANAGER-authoritative initialization) is otherwise unchanged.
- Generated spec requirements: `specs/case-ledger-processing.yaml` CLP-08-002 (reworded; id unchanged).
- `notes/case-ledger-authority.md` § "Per-Case Genesis Hash" records the threat model and future improvements.

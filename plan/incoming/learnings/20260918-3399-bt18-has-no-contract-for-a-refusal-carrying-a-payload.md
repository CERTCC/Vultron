---
title: "BT-18 defines blackboard outputs only for SUCCESS, so a call-out refusal cannot carry a payload — which makes CP-06-004 unsatisfiable"
type: learning
timestamp: "2026-09-18T21:30:00Z"
source: ISSUE-3399
signal: spec-gap
---

Two BT-18 requirements are individually sound and jointly leave a hole:

- **BT-18-007** — an Evaluator that needs to block downstream execution MUST
  return `Status.FAILURE`. Setting a structured output field to a "rejected"
  value while returning SUCCESS does not block a Sequence and MUST NOT be used.
- **BT-18-002** — a backend MUST write to all declared output keys **when it
  returns SUCCESS**. BT-18-003 likewise scopes synthetic fuzzer data to the
  SUCCESS case, and BT-18-010 has a binary Retriever declare an *empty* output
  set because "the structured fact is expressed as the BT return value".

So the only sanctioned channel for a call-out point's answer is the return
status, and the only sanctioned way to refuse is a bare FAILURE. **There is no
declared way for a refusal to say anything about itself.**

That is fine for every call-out point where the refusal is self-explanatory. It
is not fine where a spec obliges the protocol to relay the reason. CP-06-004
requires the proposing actor to record a `Reject(as_CaseProposal)`'s reason, and
`RejectCaseProposalReceivedUseCase` duly reads `request.activity.summary` — but
nothing can set it, because the decision that produced the refusal had no way to
emit anything alongside its FAILURE. The requirement is unsatisfiable end to end,
and was unsatisfiable before any of the implementation existed.

The same shape should be expected wherever a refusal is protocol-visible rather
than local. `EMB-15-004`'s rejection delegation and the ADR-0076 status gates are
the nearby candidates: each one's refusal currently reaches the wire as a
transition, carrying no account of itself.

**How to apply.** When a spec requires a *reason*, a *diagnosis*, or any payload
attached to a refusal, check whether the refusing component has a channel for it
before assuming the plumbing is the missing part. If the refusal is a BT call-out
point, it does not — and adding one is a BT-18 amendment, not an implementation
detail. Three shapes were considered on #3399, and which one is right is a real
design question rather than a coin-flip:

- Declare an optional output key an Evaluator MAY write *before* returning
  FAILURE, extending BT-18-002's scope to cover the refusal case. Cheapest, but
  it weakens the clean "status is the answer" rule that BT-18-010 leans on.
- Give the bundle a reason-supplying callable separate from the verdict factory,
  keeping the node contract untouched at the cost of a second injection point.
- Narrow the requiring spec instead — decide that reasons are out of scope for
  machine-to-machine refusals, and amend CP-06-004.

Until one is chosen, a durable decline record can hold a `reason` field and the
emit path can read it (this is what #3428 built), so the gap is isolated to the
*writer*. That is worth doing at the time, because it keeps the missing piece
small and named instead of spread across the path.

Corroboration needed: one instance so far. A second witness would be any other
spec that requires a refusal to carry information — a fault class, a retry-after,
a policy citation — routed through a call-out point. The nearest negative witness
would be a call-out refusal that *does* carry a payload today, which would mean
the channel exists and this entry is wrong about BT-18's scope.

Related: [[20260918-3399-a-structural-fix-leaves-the-hazard-one-node-upstream]]
is the other half of the same session and concerns the tree structure rather
than the spec. Neither of the other queued entries covers this.

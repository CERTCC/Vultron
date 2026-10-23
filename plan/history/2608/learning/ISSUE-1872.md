---
title: BT-10-002 did not fail to prevent the bug — it specified it
type: learning
timestamp: "2026-08-24T00:00:00Z"
source: ISSUE-1872
signal: design-question
---

`BT-10-002` read:

> Case creation MUST create corresponding CaseActor (Service)

Implementations complied. They created a per-case `Service` object at a per-case
URI, `{case_actor_service_url}/actors/case-actor-{_derive_case_slug(report_id)}`,
and addressed `Create(as_CaseProposal)` there. That identity is **unhostable by
construction**: the *sender* computes it, so no container has registered it, and
`POST /actors/case-actor-<slug>/inbox/` answers a permanent 404. The CaseProposal
round-trip never began, which blocked the FV demo for long enough that a
hand-built fallback was written to stand in for it — and that fallback then hid a
second, unrelated defect (#2482) for months.

The requirement was not silent, vague, or aspirational. It was **wrong**, in a
MUST, and the code was correct with respect to it.

**Two compounding details, both worth generalising:**

1. `notes/case-proposal.md` had the buggy form as its **"CORRECT"** example. Its
   "Pitfall" section warned against deriving the base URL from `server_base_url`
   — a real pitfall — and its fix block still ended in
   `case-actor-{case_slug}`. A reader following the note to avoid one bug walked
   into a worse one. Prose that is right about its stated subject can still be
   load-bearing for something it does not mention.
2. The requirement was latent for as long as the sender and receiver were the same
   process. Co-location made the derived id resolvable — the sender's own store
   held it — so the spec looked satisfied. It only failed when the topology it was
   written for (a *dedicated* case-actor container) was actually used.

**How to apply.**

- When a bug's mechanism is "the code does exactly what the spec says", the fix
  is the spec, and the code change is downstream of it. Fixing only the code
  leaves a requirement that will re-specify the bug for the next implementer.
  Recorded here as BT-10-002/003/004 rewritten plus CP-04-003/004 added.
- **Entity-vs-role is a recurring specification error in this corpus.** All three
  of BT-10-002/003/004 said "CaseActor MUST …" as though it named a component.
  It names a *role*: whichever participant holds `CVDRole.CASE_MANAGER`. An actor
  participates in many cases, so anything per-case in its *identity* is a
  category error. Worth grepping the corpus for other "X MUST …" requirements
  where X is a role, especially where an implementation might mint an object to
  satisfy it.
- A requirement that can only fail in a topology nobody exercises is untested by
  construction. `specs/` `scope:` and `verification:` fields are where that
  should be visible; BT-10-002 had neither.
- Suggested for `decision-audit`: a requirement whose statement names an entity
  that the codebase models as a role is a high-yield stale-premise signal. So is
  a `notes/` code block containing the exact string a spec's rationale warns
  about. Related: [[store-fidelity-vs-annotation-that-admits-a-uri]], where the
  invariant existed only in prose and the type system quietly permitted its
  violation.

**Promoted**: 2026-08-27 — captured in AGENTS.md. Docs PR: <pending>.

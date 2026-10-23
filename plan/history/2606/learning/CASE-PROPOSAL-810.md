---
source: CASE-PROPOSAL-810
timestamp: '2026-06-22T19:36:45.625403+00:00'
title: 'CaseProposal convergence: case-actor always sends Create(CaseProposal)'
type: learning
---

`ProposeCaseToActorNode` (not `CreateCaseActorNode`) is responsible for
sending `Create(as_CaseProposal)`. The two nodes have distinct
responsibilities: `CreateCaseActorNode` registers the actor resource;
`ProposeCaseToActorNode` sends the proposal after the actor is ready. The
`as_CaseProposal.reporters` field diverged across two PRs (#809, #810); the
canonical convergence point is that reporters is a `list[as_CaseParticipant]`
matching the reporters kwarg of the factory function.

**Promoted**: 2026-06-22 — captured in `notes/case-proposal.md` (PR
convergence table).
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.

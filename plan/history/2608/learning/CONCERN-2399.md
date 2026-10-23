---
source: CONCERN-2399
timestamp: '2026-08-25T15:38:56.112654+00:00'
title: 10+ user stories have no or partial spec coverage — prioritization decisions
  needed
type: learning
---

Ten or more user stories have no spec coverage or only partial coverage,
representing whole stakeholder sub-processes that are either out-of-scope by
explicit decision or awaiting prioritization. The gap analysis exists in
`docs/reference/user_stories/traceability.md` but no GitHub issues tracked the
prioritization decisions needed to resolve it.

## Surface Symptom

`traceability.md` §"Gap Analysis" lists stories with no mapped requirements or
partial coverage. No GitHub issues existed for the prioritization decisions
required to close these gaps.

## Underlying Problem

The gaps fall into two categories needing different responses:

1. Stories explicitly marked out-of-scope (bug bounty, some privacy stories)
   need a recorded decision confirming that scope boundary.
2. Stories with partial coverage (privacy/anonymity, TLP, trust/reputation)
   need either new spec requirements or an explicit deferral to a future
   milestone. Without GitHub issues, neither decision gets made or tracked.

## Decision (2026-08-25)

All four gap clusters deferred as PROD_ONLY/long-term concerns. Four new Idea
issues created, each parented to an appropriate epic:

- **#2562** — privacy/anonymity spec (parent: #1156 Actor Cryptography)
- **#2563** — bug bounty protocol support (parent: #2088 Protocol vocabulary
  extension)
- **#2564** — TLP field support (parent: #2088)
- **#2565** — trust and reputation (parent: #2088)

`traceability.md` gap analysis section updated: each cluster now reads
"Deferred — tracked in #NNNN" with rationale.

**Resolved**: 2026-08-25 — implementation tracked in #2562, #2563, #2564, #2565.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2566>.

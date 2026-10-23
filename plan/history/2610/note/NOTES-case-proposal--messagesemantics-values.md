---
source: NOTES-case-proposal--messagesemantics-values
timestamp: '2026-10-12T19:33:09.589840+00:00'
title: MessageSemantics Values
type: note
---

**Archived:** 2026-10-12
**Reason:** inventory of live enum values; the ordering rule is kept in notes/case-proposal.md
**Superseded by:** vultron/core/models/events/base.py; SE-03-002

---

## MessageSemantics Values

Three new values added to the `MessageSemantics` enum:

| Value | Pattern |
|-------|---------|
| `CREATE_CASE_PROPOSAL` | `Create(as_CaseProposal)` |
| `ACCEPT_CASE_PROPOSAL` | `Accept(as_CaseProposal)` |
| `REJECT_CASE_PROPOSAL` | `Reject(as_CaseProposal)` |

All three patterns MUST appear in `SEMANTIC_REGISTRY` before any
more-general patterns that share the same outer Activity type (SE-03-002).

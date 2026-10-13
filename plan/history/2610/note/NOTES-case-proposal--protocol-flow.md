---
source: NOTES-case-proposal--protocol-flow
timestamp: '2026-10-12T19:33:09.123212+00:00'
title: Protocol Flow
type: note
---

**Archived:** 2026-10-12
**Reason:** reference material; the flow is documented in docs/
**Superseded by:** docs/reference/messages/case_proposal.md; docs/topics/behavior_logic/use-cases/propose-case.md

---

## Protocol Flow

**Note**: The flow below reflects the corrected CASE_MANAGER-authoritative model
(ADR-0041). The report receiver does NOT create a `VulnerabilityCase` locally before
the CASE_MANAGER responds. The report receiver stores the report, writes a pending
`VultronReportCaseLink`, and waits.

```text
Report receiver                     CaseActor Service
  |                                       |
  | --- Create(CaseProposal) -----------> |
  |         actor: receiver URI           |
  |         object_: as_CaseProposal      |
  |                                       |
  |   [creates case, adds participants,   |
  |    initializes embargo, commits       |
  |    canonical ledger entries natively] |
  |                                       |
  | <-- Accept(CaseProposal) ----------- |  (happy path)
  |         actor: case-actor URI         |
  |         object_: as_CaseProposal      |
  |         result: case URI              |
  |                                       |
  | <-- Create(VulnerabilityCase) ------- |
  |         actor: case-actor URI         |
  |         context: case URI             |
  |         in_reply_to: Accept URI       |
  |         [inline participants]         |
  |                                       |
  |    -- OR --                           |
  |                                       |
  | <-- Reject(CaseProposal) ----------- |  (rejection path)
  |         actor: case-actor URI         |
  |         object_: as_CaseProposal      |
```

### Step 1: Report receiver sends `Create(as_CaseProposal)`

The report receiver creates an `as_CaseProposal` object containing:

- `id_`: auto-generated URI for the proposal
- `attributed_to`: the report receiver's actor URI (the future CASE_OWNER)
- `object_`: inline or URI-referenced `as_VulnerabilityReport`
- `target`: the case-actor service URI
- `summary` (optional): human-readable description

The report receiver then sends `Create(as_CaseProposal)` to the case-actor service's
inbox, with `actor=owner_uri`.

### Step 2a: Case-actor accepts (happy path)

When the case-actor service decides to create the case, it sends **two**
activities back to the report receiver:

1. **`Accept(as_CaseProposal)`** — acknowledgment that the proposal was
   accepted. `object_` embeds the `as_CaseProposal` inline.

2. **`Create(VulnerabilityCase)`** — the actual case creation announcement.
   - `actor` = case-actor URI (preserving AS2 "I created this" semantics)
   - `context` = URI of the new `VulnerabilityCase` (consistent with all
     other case-scoped activities; required for inbox deferral routing)
   - `in_reply_to` = URI of the `Accept(CaseProposal)` activity (causal
     antecedent, in the AS2-correct field for responses)

`in_reply_to` carries the Accept URI rather than putting it in `context`.
AS2 defines `context` as a **scoping/grouping key** and `inReplyTo` as the
field for **causal antecedents** (what this activity is responding to).
The full causal chain is recoverable: `in_reply_to` → Accept → `object_`
(inline `as_CaseProposal`). See ADR-0045.

### Step 2b: Case-actor rejects

When the case-actor service declines, it sends:

**`Reject(as_CaseProposal)`** — `object_` embeds the `as_CaseProposal`
inline (consistent with the Accept pattern; inline is preferred over URI-only
for rejection so the receiver has the full proposal context without a round-trip).

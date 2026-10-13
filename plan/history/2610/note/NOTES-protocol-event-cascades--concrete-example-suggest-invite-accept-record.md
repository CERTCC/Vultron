---
source: NOTES-protocol-event-cascades--concrete-example-suggest-invite-accept-record
timestamp: '2026-10-12T19:36:53.793812+00:00'
title: 'Concrete Example: The Suggest–Invite–Accept–Record Cascade'
type: note
---

**Archived:** 2026-10-12
**Reason:** reference walkthrough, now stale — joining moved to the stub Invite plus full-case Invite model, so Step 4 no longer sends Announce(VulnerabilityCase)
**Superseded by:** `specs/case-management.yaml` CM-11; `notes/case-joining.md`

---

## Concrete Example: The Suggest–Invite–Accept–Record Cascade

The **suggest-actor-to-case** workflow is a concrete, 4-step cascade that
illustrates all the principles described above. Each step is triggered
automatically by the previous one; only the first step requires a primary
trigger from a human or agentic client.

### Step 1 — Actor A triggers `suggest-actor-to-case`

Actor A (e.g., a Finder or Coordinator) calls the trigger endpoint:

```http
POST /actors/{actor_a_id}/trigger/suggest-actor-to-case
{ "case_id": "urn:uuid:...", "suggested_actor_id": "https://vendor.example.org/actors/vendor-b" }
```

Actor A emits a `RecommendActor` activity addressed to the CASE_MANAGER. This
is the **only primary trigger**; everything that follows is automated.

### Step 2 — the CASE_MANAGER auto-invites the suggested actor

The CASE_MANAGER's `SuggestActorReceived` handler processes the incoming
`RecommendActor` activity. Its BT subtree automatically emits an
`RmInviteToCaseActivity` to the suggested actor (Vendor B). This step is a
BT subtree of the CASE_MANAGER's `RecommendActorReceivedBT`; it is NOT a
separate manual trigger.

### Step 3 — Vendor B accepts the case invite

Vendor B's inbox receives the `RmInviteToCaseActivity`. Its BT processes
the invite and, if all preconditions are met (policy allows acceptance,
embargo status is compatible), automatically emits an
`RmAcceptInviteToCaseActivity` back to the CASE_MANAGER. This step is also a
BT subtree — NOT a manual `POST /actors/vendor-b/trigger/accept-case-invite`.

If Vendor B requires human or policy input before accepting, it MAY instead
expose the `accept-case-invite` trigger endpoint for an operator to call
explicitly. But the fully-automated path handles it without that step.

### Step 4 — the CASE_MANAGER records Vendor B as a case participant

The CASE_MANAGER's `AcceptInviteToCaseReceived` handler processes Vendor B's
`RmAcceptInviteToCaseActivity`. Its BT subtree:

1. Creates or updates Vendor B's `CaseParticipant` record (rm_state = ACCEPTED)
2. Appends a `CaseLedgerEntry` recording the acceptance
3. If `rm_state = ACCEPTED` AND embargo adherence is satisfied (or no active
   embargo), sends the full `VulnerabilityCase` details to Vendor B via
   `Announce(VulnerabilityCase)`

All four steps flow automatically from the single `suggest-actor-to-case`
trigger. The demo-runner calls only Step 1.

### Implementation Requirements

- Each step's behavior MUST be a BT subtree (BT-06-001, BT-06-005)
- No step may be implemented as a post-BT procedural call (anti-pattern)
- The `invite-actor-to-case` trigger endpoint MUST exist but is used only
  when the CASE_MANAGER wants to initiate an invite without a prior suggestion
- The `accept-case-invite` trigger endpoint MUST exist but is used only
  when Vendor B requires an explicit human decision

---

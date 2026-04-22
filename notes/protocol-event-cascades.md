# Protocol Event Cascades

## Overview

The Vultron Protocol is designed to be event-driven with clear causal
relationships between primary events and their consequences. When a
primary event occurs (e.g., submitting a report, validating a report,
accepting an invitation), cascading effects SHOULD be automated rather
than requiring separate manual triggers.

This design principle is fundamental to demonstrating protocol
correctness: demos and real deployments alike should show that the
protocol drives the right behaviors automatically from minimal primary
inputs.

## Design Principle

**Automate cascading consequences via behavior trees wherever possible.**

The demo-runner (or a human operator, or an agentic client) should only
need to trigger *primary events*. Everything else should be a
consequence of those events, cascading through the system via the
defined behaviors of the actors according to the protocol.

**Primary events** (actor-initiated, require explicit trigger):

- submit-report (finder creates and offers a report)
- validate-report (vendor validates a received report)
- add-note (any participant adds a note to a case)
- propose-embargo (coordinator proposes embargo terms)
- terminate-embargo (actor announces embargo end)

**Cascading consequences** (should be automated):

- submit-report → case creation → participant setup → embargo
  initialization → notification to finder (`Create(Case)`)
- validate-report → validation logic only (case already exists)
- accept-invitation → engagement (RM→ACCEPTED)
- add-note-to-case → broadcast note to all case participants
- case state change → broadcast update to all participants (CM-06-001)

## Relationship to Demo Correctness

The purpose of the D5 demos is to demonstrate that the protocol
*actually works*, not merely to exercise the API. When a demo-runner
manually triggers intermediate steps that should be automated
consequences of primary events, the demo is misleading — it shows
puppeteered behavior rather than genuine protocol-driven automation.

Every manual trigger in a demo that should be a cascade represents
either:

- A gap in BT automation that needs to be filled
- A missing outbox delivery path that needs to be connected
- A missing `to` field on an outgoing activity

These gaps should be systematically identified and resolved before
demo sign-off (D5-7).

## Cascades MUST Be BT Subtrees (Not Post-BT Procedural Calls)

When identifying and fixing cascade gaps, the correct fix is always to
implement the cascade as a **BT subtree**, not as a procedural call after
`bt.run()` returns.

### Why This Matters

Cascades that appear as parent→child relationships in the canonical CVD
protocol BT (in `vultron-bt.txt`) MUST be expressed as BT subtrees in the
corresponding use-case BT. If a cascade is implemented as a procedural call
after the BT finishes, it:

1. Is invisible at the BT level — cannot be audited from the tree structure
2. Creates a gap between the canonical protocol model and the implementation
3. Breaks explainability — an observer reading the BT does not see the full
   causal chain
4. Violates BT-06-005 and BT-06-006 in `specs/behavior-tree-integration.md`

### Correct Approach for Each Gap

**For each cascade gap listed above**:

1. Identify where the parent→child relationship appears in the canonical BT
   (`vultron-bt.txt` or `docs/topics/behavior_logic/`). See
   `notes/canonical-bt-reference.md` for a subtree map.
2. Implement the child behavior as a BT subtree.
3. Add the child subtree as a child node of the parent BT.
4. Do NOT implement the cascade as a procedural function called after
   `bridge.execute_with_setup()` returns.

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

Actor A emits a `RecommendActor` activity addressed to the CaseActor. This
is the **only primary trigger**; everything that follows is automated.

### Step 2 — CaseActor auto-invites the suggested actor

The CaseActor's `SuggestActorReceived` handler processes the incoming
`RecommendActor` activity. Its BT subtree automatically emits an
`RmInviteToCaseActivity` to the suggested actor (Vendor B). This step is a
BT subtree of the CaseActor's `RecommendActorReceivedBT`; it is NOT a
separate manual trigger.

### Step 3 — Vendor B accepts the case invite

Vendor B's inbox receives the `RmInviteToCaseActivity`. Its BT processes
the invite and, if all preconditions are met (policy allows acceptance,
embargo status is compatible), automatically emits an
`RmAcceptInviteToCaseActivity` back to the CaseActor. This step is also a
BT subtree — NOT a manual `POST /actors/vendor-b/trigger/accept-case-invite`.

If Vendor B requires human or policy input before accepting, it MAY instead
expose the `accept-case-invite` trigger endpoint for an operator to call
explicitly. But the fully-automated path handles it without that step.

### Step 4 — CaseActor records Vendor B as a case participant

The CaseActor's `AcceptInviteToCaseReceived` handler processes Vendor B's
`RmAcceptInviteToCaseActivity`. Its BT subtree:

1. Creates or updates Vendor B's `CaseParticipant` record (rm_state = ACCEPTED)
2. Appends a `CaseLogEntry` recording the acceptance
3. If `rm_state = ACCEPTED` AND embargo adherence is satisfied (or no active
   embargo), sends the full `VulnerabilityCase` details to Vendor B via
   `Announce(VulnerabilityCase)`

All four steps flow automatically from the single `suggest-actor-to-case`
trigger. The demo-runner calls only Step 1.

### Implementation Requirements

- Each step's behavior MUST be a BT subtree (BT-06-001, BT-06-005)
- No step may be implemented as a post-BT procedural call (anti-pattern)
- The `invite-actor-to-case` trigger endpoint MUST exist but is used only
  when the CaseActor wants to initiate an invite without a prior suggestion
- The `accept-case-invite` trigger endpoint MUST exist but is used only
  when Vendor B requires an explicit human decision

---

## Related

- `notes/canonical-bt-reference.md` (subtree map, trunk-removed branches
  model, anti-pattern examples)
- `specs/behavior-tree-integration.md` BT-06-001, BT-06-005, BT-06-006
  (cascade-as-subtree requirement)
- `specs/case-management.md` CM-06 (case update broadcast), CM-11
  (invitation acceptance lifecycle)
- `specs/triggerable-behaviors.md` TRIG-02-005, TRIG-07-001
- `specs/multi-actor-demo.md` DEMO-MA-05-001 (demos MUST use triggers)
- `notes/activitystreams-semantics.md` (state-change notification model)
- `notes/bt-integration.md` (BT design decisions)

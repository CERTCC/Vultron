## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

### 2026-04-17 BUG-26041701 design scope expansion

**Context**: BUG-26041701 started as a narrow bug (bare-string `object_` in
`CreateFinderParticipantNode`'s Add activity) but investigation revealed a
deeper design gap: the demos are "spoofing" actors rather than "puppeteering"
them. The fix requires a systematic rethink of how the demos and the trigger
layer work together.

#### Root cause (the original bug)

`CreateFinderParticipantNode.update()` in
`vultron/core/behaviors/case/nodes.py` (lines 944–952) creates:

```python
VultronActivity(type_="Add", actor=self.actor_id,
                object_=participant.id_,   # ← bare string, not inline CaseParticipant
                target=case_id, to=[finder_actor_id])
```

The `_dehydrate_data` mechanism in `db_record.py` intentionally collapses
`object_` dict-values to ID strings during storage. A bare string is stored
as-is. The outbox handler's expansion bridge only covers `("Create",
"Announce")`. Any other type with a bare-string `object_` fails MV-09-001
(`VultronOutboxObjectIntegrityError`). This is confirmed by
`multi-vendor-demo-log.txt` line 607.

**Immediate fix** (still needed):

- Replace `VultronActivity(type_="Add", object_=participant.id_, ...)` with
  `AddParticipantToCaseActivity(object_=participant, ...)`.
- Extend the outbox expansion bridge (line 158 of `outbox_handler.py`) from
  `("Create", "Announce")` to `("Create", "Announce", "Add", "Invite",
  "Accept")` — because `_dehydrate_data` collapses **all** transitive
  activity `object_` fields, and these types are now also emitted via
  outbox.

#### The deeper issue: demo spoofing vs. puppeteering

The three-actor and multi-vendor demos currently **spoof** several protocol
exchanges: they construct AS2 activities manually and POST them directly to
another actor's inbox, bypassing the sending actor's own outbox. This
violates the principle that all inter-actor communication should go through
the AS2 outbox/inbox pipeline.

Affected functions in `three_actor_demo.py` (and `multi_vendor_demo.py`):

| Function | Spoofing action |
|---|---|
| `coordinator_creates_case_on_case_actor` | coordinator constructs `CreateCaseActivity` → POSTs to case_actor's inbox directly |
| `coordinator_adds_report_to_case` | coordinator constructs `AddReportToCaseActivity` → POSTs to case_actor's inbox directly |
| `coordinator_invites_actor` | coordinator constructs `RmInviteToCaseActivity` → POSTs to case_actor's inbox AND recipient's inbox directly |
| `actor_accepts_case_invite` | invitee constructs `RmAcceptInviteToCaseActivity` → POSTs to case_actor's inbox directly |
| `actor_accepts_embargo` | actor constructs `EmAcceptEmbargoActivity` → POSTs to case_actor's inbox directly |

The correct pattern — "puppeteering" — is: the demo calls a trigger
endpoint on the actor's **own** container. The actor's BT/use-case logic
produces the activity, adds it to the actor's outbox, and the outbox handler
delivers it to the recipient's inbox via HTTP.

#### Recommended design for participant invitation workflow

The correct protocol sequence for adding a new participant is:

```text
1. Coordinator → trigger suggest-actor-to-case
       ↓ creates RecommendActorActivity(actor=coordinator, object=invitee, target=case)
       ↓ added to coordinator outbox → delivered to case_actor inbox

2. Case-actor receives RecommendActorActivity
       ↓ BT: verify case_actor IS the case owner (attributed_to check)
       ↓ BT: emit AcceptActorRecommendationActivity(to=[coordinator])
       ↓ BT: emit RmInviteToCaseActivity(actor=case_actor, object=invitee, target=case, to=[invitee])
       ↓ both activities added to case_actor outbox
       ↓ outbox handler delivers Accept to coordinator inbox, Invite to invitee inbox

3. Invitee → trigger accept-case-invite (after polling for invite to arrive)
       ↓ creates RmAcceptInviteToCaseActivity(actor=invitee, object=invite, to=[case_actor])
       ↓ added to invitee outbox → delivered to case_actor inbox

4. Case-actor receives RmAcceptInviteToCaseActivity
       ↓ existing AcceptInviteActorToCaseReceivedUseCase handles this correctly:
         creates CaseParticipant, appends RM states, runs prioritize BT
```

The key point: the case_actor acts autonomously — it doesn't need to be
told "now send an invite". It always accepts case-owner suggestions and
invites the recommended actor. This is modeled as a BT triggered by the
`SuggestActorToCaseReceivedUseCase.execute()` method.

#### New triggers needed

| Trigger | Actor | HTTP body | Emits |
|---|---|---|---|
| `suggest-actor-to-case` | coordinator | `{case_id, suggested_actor_id}` | `RecommendActorActivity` to case_actor outbox |
| `accept-case-invite` | invitee | `{invite_id, case_owner_id}` | `RmAcceptInviteToCaseActivity` to invitee outbox |
| `create-case` | coordinator | `{report_id, name, content}` | `CreateCaseActivity` to coordinator outbox |
| `add-report-to-case` | coordinator | `{case_id, report_id}` | `AddReportToCaseActivity` to coordinator outbox |
| `accept-embargo` | actor | `{case_id, proposal_id?}` | `EmAcceptEmbargoActivity` to actor outbox |

Note: `evaluate-embargo` already exists but needs to be verified as
correctly using the outbox delivery path.

#### Behavior tree for SuggestActorToCase (new)

The `SuggestActorToCaseReceivedUseCase.execute()` should run a BT with:

- **Precondition**: the receiving actor is the case owner
  (`case.attributed_to == self.actor_id`)
- **Accept recommendation**: emit `AcceptActorRecommendationActivity`
  (to [recommending actor]) and queue in outbox
- **Invite recommended actor**: emit `RmInviteToCaseActivity`
  (to [recommended actor]) and queue in outbox

The BT should be idempotent: if an invite for this actor+case already
exists in the DataLayer, skip and log.

#### Outbox expansion bridge (transitive activities)

The expansion bridge in `outbox_handler.py` must be extended for all
transitive activity types that go through the dehydrate/rehydrate cycle.
The current set to add: `"Add"`, `"Invite"`, `"Accept"`. Additional types
(`"Join"`, `"Remove"`) may need the same treatment as they are implemented.

Note: `_dehydrate_data` collapsing `object_` to ID strings is **intentional
design** — it avoids redundant inline storage. The expansion bridge is the
correct compensating mechanism for delivery.

#### DataLayer lookup for expansion bridge

For the bridge to expand a bare-string `object_` to its full object, the
referenced object must be present in the **actor's own** DataLayer at
delivery time. This is generally true for:

- `Add`: the `CaseParticipant` is created in the same BT run
- `Invite`: the invitee actor is seeded on all containers at demo start
- `Accept`: the invite activity is stored in the actor's DataLayer when
  they receive it

If `dl.read(activity_object)` returns `None`, the expansion bridge should
log a warning and skip delivery (matching current `Create`/`Announce`
behavior).

#### Impact on test suite

Tests for `SuggestActorToCaseReceivedUseCase` currently only verify that
the activity is stored. After this change, they must also verify:

- `AcceptActorRecommendationActivity` is emitted and queued in outbox
- `RmInviteToCaseActivity` is emitted and queued in outbox
- Both are idempotent if the invite already exists

Integration tests in `test/demo/` will need to be updated once the demo
scripts switch from direct inbox injection to trigger-based puppeteering.

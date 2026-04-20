## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

### 2026-04-20 REVIEW-26042001 — Multi-Actor Demo Review: Architectural Decisions

Source: `notes/demo-review-26042001.md`. Decisions captured via structured
design interview. Tasks tracked in `plan/IMPLEMENTATION_PLAN.md`
PRIORITY-348.

#### DR-01 — Outbox reference-field dehydration (arch principle)

**Decision**: The outbound adapter (outbox_handler.py) is solely responsible
for producing wire-clean ActivityStreams JSON. Core and BT nodes may construct
activities using full domain model instances in any field. The outbox handler
MUST dehydrate the following fields to URI strings before wire delivery:
`actor`, `target`, `to`, `cc`, `origin`, `result`, `instrument`.

`object_` is explicitly **exempt** from dehydration — it must always carry the
full inline typed object on the wire so recipients can determine semantic type.

**Implementation**: Add `_dehydrate_references(activity_dict: dict) -> dict` in
`vultron/adapters/driving/fastapi/outbox_handler.py`. Apply it to the raw
`model_dump(by_alias=True)` output before calling
`VultronActivity.model_validate()` in `handle_outbox_item()`. For each field
in the dehydration set: if the value is a dict with an `id` key, replace with
the `id` value string; if it's a list, apply element-wise.

**Rationale**: Core must not be responsible for knowing what is appropriate to
send on the wire. That is entirely an outbound port concern (hexagonal
architecture: adapters translate between domain and wire formats).

#### DR-02 — Activity `name` construction (BT node responsibility)

**Decision**: The `name` field of outbound activities is semantic content
(human-readable label), not a wire-format concern. BT nodes that set `name`
when constructing activities MUST use `object_.name or object_.id_` — never
`repr(object_)` or `str(object_)`. The outbound adapter does not sanitize
semantic content.

**Files to audit**: any BT node in `vultron/core/behaviors/` that constructs
`Add`, `Invite`, or `Accept` activities with a computed `name` string.

#### DR-03 — Semantic extraction: bare-string object_ guard

**Decision**: `find_matching_semantics()` in `vultron/wire/as2/extractor.py`
MUST return `MessageSemantics.UNKNOWN` immediately when `object_` is a bare
string after rehydration. It MUST NOT continue matching typed-object patterns
against a string reference.

**General rule** (formal requirement to add to `specs/semantic-extraction.md`):
Every `ActivityPattern` MUST discriminate on at minimum `(Activity type, Object
type)`. No pattern may match on Activity type alone. For nested activities (e.g.
`Accept(Invite(...))`), the pattern MUST also check the nested object type where
needed to disambiguate semantically distinct activities with the same outer
shape.

#### DR-04 — Fail-fast for required event fields (ARCH-10-001)

**Decision**: Required fields in `*ReceivedEvent` classes (e.g. `report_id`,
`offer_id` in `ValidateReportReceivedEvent`) MUST be typed as non-optional
(`str`, not `str | None`). Pydantic validation MUST raise at construction time.
A use case MUST NOT raise `ValueError` inside `execute()` for missing required
fields.

**Audit**: Check all `*ReceivedEvent` classes for fields that are required by
their subtype but typed as optional in the parent.

#### DR-05 — Accept.object_ must carry the original Invite

**Decision**: `InviteReceivedUseCase` (both RM and EM variants) MUST stash
the received invite activity on the BT blackboard when the invite is processed.
The `AcceptInvite` BT node reads the invite from the blackboard and uses it
as `object_` when constructing the `Accept` activity.

**Wrong pattern**: passing the case object or embargo event as `object_` when
constructing Accept — this produces coercion failures on the receiving end.

**Correct pattern**:

```python
# In InviteReceivedUseCase.execute() — store invite on blackboard
bb.set("invite_activity", invite)

# In AcceptInviteNode.update() — read invite from blackboard
invite = bb.get("invite_activity")
accept = RmAcceptInviteToCaseActivity(actor=actor_id, object_=invite)
```

See AGENTS.md "Accept/Reject `object` Field Must Use an Inline Typed Activity
Object" pitfall entry.

#### DR-06 — Multi-party embargo: per-participant EM state

**Decision**: Each `CaseParticipant` carries its own EM state field (not just
the shared `VulnerabilityCase` EM state). Case EM state transitions to `ACTIVE`
when the **case owner** accepts, not on the first participant accept.

**Case owner determination**: `case.attributed_to == actor_id` identifies
the case owner (CaseActor / Coordinator role).

**Subsequent participant accepts**: When a non-owner participant calls
`accept-embargo` and the case EM state is already `ACTIVE`, the call MUST
succeed (200/204) and update only that participant's own EM state in
`CaseParticipant`. No 409.

**Rationale**: The EM model in the protocol is per-participant (`q^em` is
per-actor). The shared EM state is an aggregate derived from participant states.
The case owner's acceptance is the authoritative signal for `ACTIVE`. Inactive
participants do not hold a pocket veto because their lack of response does not
block the case owner from acting.

**Reference**: `docs/topics/process_models/em/` — the EM model is consent-based
with the case owner as the resolution authority when consensus fails.

#### DR-07 — ActivityPattern discrimination requirement

**Decision**: All entries in `SEMANTICS_ACTIVITY_PATTERNS` MUST match on at
minimum `(Activity type, Object type)`. No bare Activity-type matches.

**Immediate fix**: `AnnounceLogEntryActivity` pattern — add
`object_type = CaseLogEntry` discriminator.

**Audit required**: Review all patterns for bare-type matches. Pay particular
attention to `Accept` patterns which must distinguish:

- `Accept(Offer(VulnerabilityReport))` → `validate_report`
- `Accept(Invite(VulnerabilityCase))` → `accept_invite_to_case`
- `Accept(Invite(EmbargoEvent))` → `accept_embargo`

#### DR-08 — create_note: AttachNoteToCaseNode BT node

**Decision**: Implement `AttachNoteToCaseNode` BT node (in
`vultron/core/behaviors/case/nodes.py` or similar). The node:

1. Reads the `VulnerabilityCase` from the DataLayer.
2. Checks `case.notes` for the note's `id_` — if already present, returns
   `SUCCESS` (idempotent).
3. Appends `note.id_` to `case.notes`.
4. Calls `dl.save(case)`.

Wire this into the `create_note` BT subtree. The use case `execute()` remains
infrastructure glue only.

**Idempotency fix**: The Note object already existing in the DataLayer does NOT
mean it is attached to the case. The idempotency check MUST be `note.id_ in
case.notes`, not `dl.read(note_id) is not None`.

#### DR-09 — Actor ID normalization

**Decision**: Actor IDs MUST be full URIs everywhere in the system. Normalize
to full URI at the point the actor ID is first established (actor creation,
seed load, session context). No function downstream of that point should ever
receive or handle a short UUID.

**Audit**: Search for short-UUID actor ID assignment in
`vultron/demo/`, `vultron/adapters/`, and `vultron/core/` seeding code.

#### DR-10 — Stub objects for selective disclosure

**Decision**: Implement stub-object support (as designed in
`notes/stub-objects.md`) as part of the Invite/embargo flow:

- When constructing an `Invite` to a case, the `target` field MUST be a stub
  object `{id: case_id, type: "VulnerabilityCase"}` — not the full case.
  The invitee has not yet accepted the embargo and must not receive case details.
- Stub objects carry `id` + `type` (+ optional `summary`) only.
- Stubs MUST carry `type` so semantic routing works correctly.
- Recipient-side: stubs MUST NOT overwrite a full object already in the
  DataLayer. If the DataLayer already has a full `VulnerabilityCase` for that
  id, the stub is discarded.
- A new `specs/stub-objects.md` (or section in `specs/message-validation.md`)
  MUST formally define when stubs are permitted.

**Connection to MV-09-001**: Stub objects are a controlled exception to the
"full inline typed object" requirement. The spec must be updated to define
this exception explicitly.

#### DR-11 — PersistCase: upsert semantics

**Decision**: `PersistCase` BT node calls `dl.save()` with upsert / idempotent
semantics. Duplicate-key conditions MUST be silently handled. No WARNING log
for a pre-existing case with the same `id_`.

#### DR-12 — BT failure reason propagation

**Decision**: Add `get_failure_reason(tree) -> str` utility in
`vultron/core/behaviors/bridge.py`. Implementation: walk the behaviour tree
depth-first; return the first node with `status == Status.FAILURE` and its
`feedback_message`. If no node has a feedback message, return the failing
node's class name.

Apply to all BT-failure log messages (e.g., `EngageCaseBT`,
`ValidateReportBT`, etc.).

#### DR-13 — SubmitReportReceivedUseCase: remove vendor/target assumptions

**Decision**: Remove the `vendor_actor_id` / `Offer.target` lookup from
`SubmitReportReceivedUseCase`. The "vendor" label is a demo convenience; at the
protocol level all actors are generic. `Offer.target` has no defined semantic
meaning for `Offer(Report)` — it is misuse of the AS2 `target` field.

**Correct `to`/`cc` semantics**:

- Receiving actor in `Offer.to` → create a case (primary recipient).
- Receiving actor in `Offer.cc` → informational; log DEBUG; do NOT create a
  case.
- Receiving actor not in `to` or `cc` → log WARNING (why did this arrive?).

**Add to `specs/handler-protocol.md`**: document the `to`-only case-creation
rule as a formal requirement.

---

### 2026-04-17 BUG-26041701 design scope expansion

**Scope decision**: BUG-26041701 absorbs IDEA-26041702 (generalize
`CreateFinderParticipantNode`) but NOT IDEA-26041703 (broad BT composability
audit). The immediate fix plus node generalization form a single coherent
change; IDEA-26041703 is tracked as a separate future task in
`plan/PRIORITIES.md`.

This analysis has been folded into **PRIORITY-347** in `IMPLEMENTATION_PLAN.md`
(after P-345 DL-REHYDRATE). IDEA-26041703 becomes a subsequent priority block
with `notes/bt-reusability.md` and `specs/behavior-tree-node-design.md` as
deliverables.

**Context**: BUG-26041701 started as a narrow bug (bare-string `object_` in
`CreateFinderParticipantNode`'s Add activity) but investigation revealed a
deeper design gap: the demos are "spoofing" actors rather than "puppeteering"
them, and the BT node is overfitted to the demo rather than being a general
reusable behavior. The fix requires a systematic rethink of how the demos and
the trigger layer work together, including a generalization of the BT node.

**Two categories of demos** (clarified during analysis):

- **Exchange demos** (`vultron/demo/exchange/`): Demonstrate individual
  protocol message exchanges in isolation. These intentionally use direct
  inbox injection ("spoofing") because they are showing protocol fragments,
  not end-to-end behavior. Examples: `receive_report_demo.py`,
  `suggest_actor_demo.py`.
- **Scenario demos** (`vultron/demo/scenario/`): Demonstrate full multi-actor
  workflows. These MUST use trigger endpoints ("puppeteering") so that the
  system's own BT and outbox logic is exercised. Examples:
  `two_actor_demo.py`, `three_actor_demo.py`, `multi_vendor_demo.py`.

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

---

### 2026-04-20 REVIEW-26042001 (Supplement) — Second-Pass Spec Implications

Source: Architectural review of spec changes from REVIEW-26042001.

#### DR-06 Update — Per-Participant Embargo Consent State Machine

The existing `ParticipantStatus.embargo_adherence: bool` field is correct as a
derived value, but it needs a formal 5-state machine behind it. The states are:
`NO_EMBARGO` → `INVITED` → `SIGNATORY` (embargo_adherence=True) or `DECLINED`
(embargo_adherence=False), plus `LAPSED` (was signatory; embargo revised but
not yet re-accepted). `LAPSED` is distinct from `DECLINED` because a lapsed
participant had prior good standing. Both `INVITED` and `LAPSED` have
timer-based "pocket-veto" transitions to `DECLINED` (configurable timeout).

Implement with `transitions` library in
`vultron/core/states/participant_embargo_consent.py`. Full spec in
`notes/participant-embargo-consent.md`.

**Embargo meta-protocol delivery**: `Offer(Embargo)`, `Invite(Embargo)`, and
`Announce(Embargo)` MUST be delivered to `DECLINED` and `LAPSED` participants
so they can re-accept without deadlocking. Only case content is gated on
`embargo_adherence=True`.

**Accept(Invite(case)) implies embargo consent**: If the case has an active
embargo when a participant accepts the case invitation, the acceptance MUST
simultaneously set consent to `SIGNATORY`. The reverse DOES NOT apply:
accepting an embargo does not imply case participation.

**Full case delivery precondition**: The case owner MUST only send
`Announce(VulnerabilityCase)` with full case details when BOTH
`rm_state=ACCEPTED` AND `embargo_adherence=True` (or no active embargo). This
check MUST be in the BT subtree for `AcceptInviteActorToCase`, not in
post-BT procedural code.

#### DR-07 Update — InviteActorToCasePattern Missing object_

`InviteActorToCasePattern` in `vultron/wire/as2/extractor.py` has no `object_`
field, violating SE-03-003. Per AS2 spec ("extending an invitation for the
**object** to the **target**") and the existing notes in
`notes/activitystreams-semantics.md`, `Invite(object=Actor, target=Case)` is
the correct structure. Fix: add `object_=AOtype.ACTOR`.

**Constraint discovered (2026-04-20):** `AOtype.ACTOR = "Actor"` only matches
the base `as_Actor` class (`type_="Actor"`). Real AS2 actor subtypes
(`VultronPerson`, `VultronOrganization`, `CaseActor`) have `type_="Person"`,
`type_="Organization"`, `type_="Service"` respectively. The pattern matcher
uses exact string equality (`pattern_field == getattr(activity_field, "type_",
None)`), so `object_=AOtype.ACTOR` would NOT match real invite objects
containing actor subtypes. Adding it breaks existing tests and real invite
flows. Requires subtype-aware matching in `_match_field()` (e.g., check
`isinstance(activity_field, as_Actor)`) or a custom actor-type predicate in
`ActivityPattern` before this can be implemented.

#### DR-13 Update — cc Addressing Not Supported

`cc` addressing has no defined handler semantics in the current protocol
version. When a receiving actor finds itself in `cc` of an `Offer(Report)`:

- Log WARNING (not DEBUG): "`cc` addressing is not supported; activity discarded"
- Discard without creating a case
This is a deliberate simplification — implementing an "informational receive"
use case for `cc` recipients would require defining what "informational only"
means, which we're deferring.

#### DR-14 — Dead-Letter Handling for Unresolvable object_ (New)

When `find_matching_semantics()` returns UNKNOWN because `object_` is a bare
string URI after rehydration (VAM-01-009), this is NOT the same as UNKNOWN due
to no registered pattern. The two cases require different handling:

- **UNKNOWN_NO_PATTERN** (no matching `ActivityPattern`): raise
  `VultronApiHandlerMissingSemanticError` as currently
- **UNKNOWN_UNRESOLVABLE_OBJECT** (`object_` still bare string after rehydration):
  log WARNING, store dead-letter record, return silently

Dead-letter record schema:

```json
{
  "activity_id": "urn:uuid:...",
  "activity_json": {},
  "unresolvable_uri": "https://...",
  "actor_id": "https://...",
  "received_at": "2026-..."
}
```

For future synchronous paths: return HTTP 422 Unprocessable Content with the
unresolvable URI in the error body.

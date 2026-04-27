## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

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

~~**Decision**: The `name` field of outbound activities is semantic content
(human-readable label), not a wire-format concern. BT nodes that set `name`
when constructing activities MUST use `object_.name or object_.id_` — never
`repr(object_)` or `str(object_)`. The outbound adapter does not sanitize
semantic content.~~
~~**Files to audit**: any BT node in `vultron/core/behaviors/` that constructs
`Add`, `Invite`, or `Accept` activities with a computed `name` string.~~
→ captured in `notes/activitystreams-semantics.md`; pitfall in `AGENTS.md`

#### DR-03 — Semantic extraction: bare-string object_ guard

**Decision**: `find_matching_semantics()` in `vultron/wire/as2/extractor.py`
MUST return `MessageSemantics.UNKNOWN` immediately when `object_` is a bare
string after rehydration. It MUST NOT continue matching typed-object patterns
against a string reference.

**General rule** (formal requirement to add to `specs/semantic-extraction.yaml`):
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

~~**Decision**: Actor IDs MUST be full URIs everywhere in the system. Normalize
to full URI at the point the actor ID is first established (actor creation,
seed load, session context). No function downstream of that point should ever
receive or handle a short UUID.~~
~~**Audit**: Search for short-UUID actor ID assignment in
`vultron/demo/`, `vultron/adapters/`, and `vultron/core/` seeding code.~~
→ captured in `notes/codebase-structure.md`; pitfall in `AGENTS.md`

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
- A new `specs/stub-objects.yaml` (or section in `specs/message-validation.yaml`)
  MUST formally define when stubs are permitted.

**Connection to MV-09-001**: Stub objects are a controlled exception to the
"full inline typed object" requirement. The spec must be updated to define
this exception explicitly.

**Implementation lessons (2026-04-21)**:

- `event.activity` cannot be reduced to ID strings for DR-10 announcement
  handling. `AnnounceVulnerabilityCaseReceivedUseCase` needs the full inline
  `VulnerabilityCase` on `activity.object_`, so `extract_intent()` must
  preserve rich `object_` / `target` / `context` values when
  `include_activity=True`.
- `VulnerabilityCaseStub` must override the inherited `published` and
  `updated` defaults from `as_Object`; otherwise `model_dump(exclude_none=True)`
  leaks timestamps and violates the "stub carries only id/type(+summary)"
  selective-disclosure rule.

#### DR-11 — PersistCase: upsert semantics

~~**Decision**: `PersistCase` BT node calls `dl.save()` with upsert / idempotent
semantics. Duplicate-key conditions MUST be silently handled. No WARNING log
for a pre-existing case with the same `id_`.~~
→ tracked as `plan/IMPLEMENTATION_PLAN.md` TASK-CCDRIFT CCDRIFT.2

#### DR-12 — BT failure reason propagation

~~**Decision**: Add `get_failure_reason(tree) -> str` utility in
`vultron/core/behaviors/bridge.py`. Implementation: walk the behaviour tree
depth-first; return the first node with `status == Status.FAILURE` and its
`feedback_message`. If no node has a feedback message, return the failing
node's class name.~~
~~Apply to all BT-failure log messages (e.g., `EngageCaseBT`,
`ValidateReportBT`, etc.).~~
→ captured in `notes/bt-integration.md`; pitfall in `AGENTS.md`

#### DR-13 — SubmitReportReceivedUseCase: remove vendor/target assumptions

~~**Decision**: Remove the `vendor_actor_id` / `Offer.target` lookup from
`SubmitReportReceivedUseCase`. The "vendor" label is a demo convenience; at the
protocol level all actors are generic. `Offer.target` has no defined semantic
meaning for `Offer(Report)` — it is misuse of the AS2 `target` field.~~

~~**Correct `to`/`cc` semantics**:~~

~~- Receiving actor in `Offer.to` → create a case (primary recipient).~~
~~- Receiving actor in `Offer.cc` → informational; log DEBUG; do NOT create a
  case.~~
~~- Receiving actor not in `to` or `cc` → log WARNING (why did this arrive?).~~

~~**Add to `specs/handler-protocol.yaml`**: document the `to`-only case-creation
rule as a formal requirement.~~
→ `cc` guard tracked as TASK-CCDRIFT CCDRIFT.1; pitfall in `AGENTS.md`
(notes/activitystreams-semantics.md)

---

### 2026-04-17 BUG-26041701 design scope expansion

**Scope decision**: BUG-26041701 absorbs IDEA-26041702 (generalize
`CreateFinderParticipantNode`) but NOT IDEA-26041703 (broad BT composability
audit). The immediate fix plus node generalization form a single coherent
change; IDEA-26041703 is tracked as a separate future task in
`plan/PRIORITIES.md`.

This analysis has been folded into **PRIORITY-347** in `IMPLEMENTATION_PLAN.md`
(after P-345 DL-REHYDRATE). IDEA-26041703 becomes a subsequent priority block
with `notes/bt-reusability.md` and `specs/behavior-tree-node-design.yaml` as
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

~~When `find_matching_semantics()` returns UNKNOWN because `object_` is a bare
string URI after rehydration (VAM-01-009), this is NOT the same as UNKNOWN due
to no registered pattern. The two cases require different handling:~~

~~- **UNKNOWN_NO_PATTERN** (no matching `ActivityPattern`): raise
  `VultronApiHandlerMissingSemanticError` as currently~~
~~- **UNKNOWN_UNRESOLVABLE_OBJECT** (`object_` still bare string after rehydration):
  log WARNING, store dead-letter record, return silently~~

~~Dead-letter record schema:~~

~~```json
{
  "activity_id": "urn:uuid:...",
  "activity_json": {},
  "unresolvable_uri": "https://...",
  "actor_id": "https://...",
  "received_at": "2026-..."
}

```~~

~~For future synchronous paths: return HTTP 422 Unprocessable Content with the
unresolvable URI in the error body.~~
→ captured in `notes/activitystreams-semantics.md`; tracked as
TASK-SEDRIFT SEDRIFT.3; pitfall in `AGENTS.md`

---

### 2026-04-22 BUG-26041701 closure verification

BUG-26041701 no longer reproduces in the current tree. The relevant fix points
are now split across three layers:

- initiating activity models reject bare string / Link `object_` values at
  construction time;
- `CreateCaseParticipantNode` emits `AddParticipantToCaseActivity` with an
  inline typed `CaseParticipant`; and
- the outbox handler expands legacy bare-string `object_` values for the
  transitive initiating activity types it still needs to bridge, then raises an
  integrity error if expansion fails.

Practical lesson: when a backlog bug may already be fixed, close it with
concrete code-search and regression-test evidence rather than forcing a
redundant follow-up patch.

---

### 2026-04-22 BUG-26041801 — Reporter terminology at report receipt

- `finder_actor_id` was part of the externally visible contract for
  receive-report orchestration, so the rename had to cover scenario/demo helper
  functions and their tests along with the core BT factory.
- The correct semantic claim is "report submitter" / "reporter", not "finder".
  Keep role taxonomies and participant-state concepts separate from field names
  that identify who sent an `Offer(VulnerabilityReport)`.
- For terminology bugs, search adapter/demo layers as well as core code. Demo
  helpers often mirror public parameter names closely enough that leaving them
  behind creates avoidable inconsistency.

---

### 2026-04-22 BUG-26042101 — Trigger-side embargo ownership gate

- Trigger-side embargo responses need the same owner-vs-participant split as the
  receive-side embargo handlers. The case owner drives shared EM transitions;
  non-owner participants mutate only their own consent state.
- For compatibility with older single-actor fixtures and legacy cases,
  `case.attributed_to is None` should fall back to treating the triggering actor
  as the owner. Without that fallback, existing single-actor embargo triggers
  silently stop advancing the shared EM state.
- Participant-only accept/reject updates should avoid re-running the PEC machine
  when the participant is already in the target state (`SIGNATORY` /
  `DECLINED`), so idempotent repeats do not create avoidable invalid-transition
  warnings.

---

### 2026-04-22 BUG-26041802 — transitive activity object contract

- If a field is semantically required across an entire AS2 activity family, the
  shared base type must encode that requirement. Keeping the base
  `as_TransitiveActivity.object_` optional let generic `as_*` constructors drift
  out of sync with the stricter typed subclasses.
- Use a distinct required-reference alias instead of only changing a `Field(...)`
  default. `ActivityStreamRef` still includes `None`, so type-level and runtime
  contracts diverge unless required fields use `ActivityStreamRequiredRef`.
- Wire/domain translation tests must reflect the stricter contract too:
  `VultronAS2Activity.from_core()` should reject objectless transitive domain
  activities rather than silently materializing invalid wire objects.

---

### 2026-04-22 BUG-26042201 — base-typed activity serialization can drop inline subtype fields

- When a typed AS2 activity stores `object_` through a base reference annotation
  like `as_ObjectRequiredRef`, plain `model_dump()` can serialize the nested
  value as the base `as_Object` shape and silently omit subtype-only fields.
- For any adapter path that re-validates or delivers rehydrated activities,
  prefer `model_dump(..., serialize_as_any=True)` so inline typed payloads such
  as `CaseLogEntry` survive semantic coercion and HTTP delivery intact.
- Regression coverage needs to hit both persistence and outbound delivery
  boundaries. A DataLayer round-trip test alone would not catch the same field
  loss in the outbox adapter.

---

### 2026-04-22 BUG-26042202 — case triggers must normalize actor IDs before outbox updates

- Trigger paths that accept short actor IDs from router path params need to
  overwrite `actor_id` with the resolved `actor.id_` before any outbox mutation.
- SQLite bare-UUID compatibility in `dl.read()` hides this class of bug for
  `urn:uuid:` actor IDs, so regressions must use URL-form actor records to
  exercise the missing canonicalization path.
- For short-ID trigger regressions, asserting both `outbox.items` mutation and
  absence of the warning log is a better guard than checking the queued activity
  alone.

---

### 2026-04-22 BUG-26042203 — invite response parsing lessons

- Generic AS2 parsing must recurse into nested inline dicts, not just the outer
  `object`, or `Accept(Invite(...))` / `Reject(Invite(...))` lose the actor and
  stub-object subtype information that `ActivityPattern` matching relies on.
- Minimal `{id, type[, summary]}` `VulnerabilityCase` dicts should be expanded
  as `VulnerabilityCaseStub`, not full `VulnerabilityCase`, so selective
  disclosure survives generic inbound parsing.
- Setting `inReplyTo` directly on invite accept/reject activity models is a
  safer invariant than relying on every trigger/demo/example call site to wire
  the original invite ID correctly.

---

### 2026-04-22 BUG-26042204 follow-on requirement — available embargo at case creation

- This bug was fixed by correcting the demo orchestration, not by changing the
  underlying case-initialization semantics.
- Follow-on requirement to capture in `notes/` / `specs/` / planning: when a
  case is created with an available embargo, the authoritative case should be
  initialized directly into `EM.ACTIVE`, and the case owner should be seeded as
  a `SIGNATORY` from the start.
- Rationale: the case creator is the case owner by default, so the owner should
  not be able to create or receive a case in a state where they are effectively
  locked out of their own active embargo until a separate accept step occurs.

---

### 2026-04-23 TOOLS-1 — Python 3.14 deferred

Python 3.14.0rc2 is available but the test suite fails with:

```text
TypeError: _eval_type() got an unexpected keyword argument 'prefer_fwd_module'
Unable to evaluate type annotation 'ClassVar[MetaData]'
```

Root cause: `pydantic==2.13.3` uses the old `typing._eval_type()` call
signature that Python 3.14 removed. There is no Pydantic update available
that resolves this. Revisit when Pydantic releases Python 3.14-compatible
builds. Until then, `requires-python = ">=3.12"` and docker base image
`python:3.13-slim-bookworm` are unchanged.

---

### 2026-04-23 DOCS-3 — User Stories with Insufficient Specification Coverage

Source: `notes/user-stories-trace.md` traceability review.

The following 14 user stories have no mapped requirements or only partial
coverage in `specs/`. For each story, the gap is described and concrete
steps toward remediation are identified.

#### Bug Bounty Stories (Out-of-Scope for Current Protocol)

- **story_2022_055** — "As a Participant, state that I paid or received a bounty"
  - **Gap**: No spec coverage. Bug bounty payment state is not modelled in
    the Vultron Protocol.
  - **Remediation**: Requires a new activity type (e.g.,
    `BountyPaymentActivity`) in `vultron-as2-mapping.md` and a corresponding
    state field in the case participant model. Also requires a new requirement
    section in `case-management.md` or a new `bug-bounty.md` spec.
  - **Condition**: Bug bounty features must be explicitly elevated to
    in-scope. This is currently `:material-block-helper:` (out-of-scope) in
    the user story table.

- **story_2022_056** — "As a Participant, ask if another Participant paid a reporter"
  - **Gap**: No spec coverage. No query activity type for bounty status.
  - **Remediation**: Same as `story_2022_055`; a bounty query activity
    type and a corresponding use case would be required.
  - **Condition**: Same as `story_2022_055`.

- **story_2022_057** — "As a Participant, ask a reporter if they were paid"
  - **Gap**: No spec coverage. Similar to `story_2022_056` but
    reporter-targeted.
  - **Remediation**: Same as `story_2022_055` / `story_2022_056`.
  - **Condition**: Same as `story_2022_055`.

- **story_2022_084** — "As a vendor, reward the reporter by paying a bounty"
  - **Gap**: No spec coverage. Entirely out-of-scope in the current
    Vultron Protocol.
  - **Remediation**: Would require defining bounty payment as a
    protocol-level event, including payer/payee actors, amounts, and
    acknowledgment activities. No existing spec provides a foundation.
  - **Condition**: Out-of-scope; explicit prioritization decision required
    to expand protocol scope.

- **story_2022_085** — "As a reporter, be rewarded with a bounty"
  - **Gap**: No spec coverage. Recipient side of bounty payment.
  - **Remediation**: Same as `story_2022_084`.
  - **Condition**: Same as `story_2022_084`.

#### Bug Bounty Story with Partial Coverage

- **story_2022_011** — "As a Participant, provide bug bounty program info"
  - **Gap**: Only `EP-01-001` (actor profile MAY include `embargo_policy`
    field) is mapped as a loose proxy. No requirement defines actor profile
    fields for bug bounty program name, URL, or payout range.
  - **Remediation**: Add a new section to `embargo-policy.md` (or a
    separate `bug-bounty.md`) defining optional bug bounty fields on the
    actor profile: at minimum `bounty_program_url` and `bounty_max_payout`.
  - **Condition**: Bug bounty feature must be moved to in-scope and
    prioritized above Priority 3000.

#### Privacy and Anonymity Stories with Partial Coverage

- **story_2022_024** — "As a Finder/Reporter, constrain communication for anonymity"
  - **Gap**: Only `VP-08-017` (MAY delay notifying potential Participants)
    is mapped. No spec covers pseudonymous reporting, reporter identity
    stripping, or coordinator-mediated anonymous submission.
  - **Remediation**: Add requirements to `handler-protocol.md` or a new
    `privacy.md` spec covering: (a) coordinator-mediated anonymous
    submission where the coordinator does not forward reporter identity,
    (b) actor alias/pseudonym support in the wire vocabulary, and
    (c) the CaseActor's obligation not to expose the reporter's identity
    without consent.
  - **Condition**: Requires identity/authentication spec expansion and
    a prioritization decision on privacy features. Upstream dependency on
    `encryption.md` PROD_ONLY requirements.

- **story_2022_033** — "As a Participant, request anonymity in a case"
  - **Gap**: Only `VP-08-017` is mapped as a loose proxy. No spec defines
    how a participant opts into case anonymity, how the CaseActor
    handles it, or how other participants are notified.
  - **Remediation**: Add requirements defining a case anonymity opt-in
    mechanism, likely as a new `CaseParticipant.anonymous` flag with
    associated handler logic in `case-management.md`. Define how
    announcements to other participants omit the anonymous participant's
    real identity.
  - **Condition**: Same as `story_2022_024`.

#### Trust and Reputation Stories with Partial Coverage

- **story_2022_095** — "As a Participant, provide evidence of reputation to others"
  - **Gap**: Only `VP-05-013` (consider others' compliance history) and
    `EP-01-001` (policy as reputation proxy) are mapped. No spec defines
    how actors publish reputation attestations, what format they take,
    or how recipients verify them.
  - **Remediation**: Add requirements (potentially in `embargo-policy.md`
    or a new `trust.md` spec) defining: (a) a machine-readable compliance
    history format on the actor profile, (b) how attestations reference
    past case IDs without leaking case contents, and (c) optional
    third-party endorsement activity type.
  - **Condition**: Reputation features must be prioritized; may depend on
    decentralized identity mechanisms currently deferred as PROD_ONLY.

- **story_2022_096** — "As a Participant, record/log trust/reputation of others"
  - **Gap**: Only `VP-05-013` and `VP-08-010` are mapped. No spec
    defines a local trust/reputation log data model, persistence
    requirements, or how logged reputation feeds into case engagement
    decisions.
  - **Remediation**: Add requirements to `datalayer.md` for a
    per-actor reputation record (keyed by actor URI), and to
    `case-management.md` specifying that CaseActors SHOULD update
    reputation records after each case where embargo compliance can be
    assessed.
  - **Condition**: Same as `story_2022_095`.

#### TLP (Traffic Light Protocol) Stories with Partial Coverage

- **story_2022_070** — "As a Participant, convey how information I provide can be used"
  - **Gap**: Only embargo-related constraints (`VP-05-006`, `VP-16-001`)
    are mapped. No spec defines TLP marking on activities or objects, nor
    how recipients are expected to enforce handling restrictions.
  - **Remediation**: Add a new `tlp.md` spec (or extend
    `vocabulary-model.md`) defining: (a) a `tlp` field on
    `as_Object`-derived types carrying one of
    `WHITE | GREEN | AMBER | RED`, (b) wire serialisation rules, and
    (c) recipient obligations for each TLP level.
  - **Condition**: TLP integration must be prioritised. Upstream
    dependency on wire vocabulary extension mechanism in
    `vocabulary-model.md`.

- **story_2022_071** — "As a Participant, convey information use while obeying TLP"
  - **Gap**: Same as `story_2022_070` plus enforcement requirements.
    No spec covers how a recipient enforces TLP restrictions when
    forwarding or storing received information.
  - **Remediation**: Same as `story_2022_070`; add enforcement
    requirements (e.g., a handler MUST NOT forward a TLP:RED message
    outside the originating case) to the proposed `tlp.md` spec.
  - **Condition**: Same as `story_2022_070`.

- **story_2022_072** — "As a Participant, convey what restricted info I will accept"
  - **Gap**: Only `EP-01-002` (embargo policy required fields) and
    `VP-05-007` (smallest-set restriction) are mapped as proxies. No spec
    defines policy fields for acceptable TLP levels.
  - **Remediation**: Add optional `acceptable_tlp_levels` field to the
    embargo policy record in `embargo-policy.md`, or add equivalent fields
    to the proposed `tlp.md` spec.
  - **Condition**: Builds on `story_2022_070` remediation; TLP spec must
    exist first.

- **story_2022_073** — "As a Participant, convey TLP restriction level I will accept"
  - **Gap**: Only `EP-01-003` (optional embargo policy fields) is mapped.
    No spec defines how an actor declares its maximum acceptable TLP level.
  - **Remediation**: Same as `story_2022_072`; the specific field would
    be `max_acceptable_tlp_level: TLPLevel` on the actor profile or
    embargo policy record.
  - **Condition**: Same as `story_2022_072`.

---

### 2026-04-23 CC-ENFORCEMENT — Cyclomatic Complexity Gate Design

Source: structured design interview (grill-me session). Tasks tracked in
`plan/IMPLEMENTATION_PLAN.md` CC-1 and CC-2. Priority captured in
`plan/PRIORITIES.md` Priority 450.

#### Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Tooling | `flake8-mccabe` (bundled) | Already in flake8 7.3.0; zero new deps |
| Threshold model | Single hard threshold | Warn tier adds complexity without enforcement value |
| Initial gate | CC=15 | 5 violations at CC>15 — fixable before gate lands |
| Final target | CC=10 | Accepted upper bound for maintainable functions |
| Scope | `vultron/` and `test/` | Uniform standard; high-CC test fixtures are bugs too |
| CI integration | Existing `lint-flake8` job | Free — just add `max-complexity` to `.flake8` |
| Pre-commit | Add `flake8` hook | Gives immediate developer feedback |
| Refactor target | CC≤10 for all tasks | Phase 1 refactors go to final target; no revisiting |

Ruff (`C901`) was considered and rejected — `flake8-mccabe` is already
present and Ruff is not in the stack. Radon + pytest two-tier model was
considered and rejected — single hard threshold with progressive tightening
achieves the same outcome without new dependencies or pytest complexity.

#### Configuration changes (CC-1.6)

**`.flake8`** — add under `[flake8]`:

```ini
max-complexity = 15
```

Lower to `10` in CC-2.2.

**`.pre-commit-config.yaml`** — add new hook entry:

```yaml
- repo: https://github.com/PyCQA/flake8
  rev: 7.3.0
  hooks:
    - id: flake8
      args: ["--max-complexity=15", "--select=C901,E,W,F"]
```

Update `--max-complexity` to `10` when CC-2.2 lands.

**`.github/skills/run-linters/SKILL.md`** — add a note that flake8 now
enforces a cyclomatic complexity gate (`max-complexity = 15`, tightening
to `10` after CC-2).

#### Phase 1 violation inventory (CC>15 — must reach CC≤10 before CC-1.6)

| CC | File | Function | Line |
|---|---|---|---|
| 34 | `vultron/wire/as2/extractor.py` | `extract_intent` | 445 |
| 18 | `vultron/wire/as2/rehydration.py` | `rehydrate` | 43 |
| 17 | `vultron/scripts/ontology2md.py` | `thing2md` | 33 |
| 17 | `test/core/behaviors/test_performance.py` | `mock_datalayer` | 45 |
| 16 | `vultron/core/case_states/make_doc.py` | `print_model` | 77 |

**`extract_intent` refactoring approach (CC=34):** This function is the core
semantic extraction dispatcher in `extractor.py`. It contains a large
conditional chain over (activity type × object type) combinations. The
function already has `SEMANTICS_ACTIVITY_PATTERNS` as an ordered pattern
list; `extract_intent` likely re-implements or augments that dispatch
imperatively. Recommended approach:

1. Audit whether `extract_intent` duplicates logic already in
   `find_matching_semantics()` / `ActivityPattern.match()`.
2. Extract per-type sub-dispatchers (e.g., `_extract_create_intent`,
   `_extract_offer_intent`) — each becomes a short, focused function.
3. Replace the top-level conditional with a dict keyed on `as_type` that
   delegates to the appropriate sub-dispatcher.
4. Verify that all existing pattern-matching tests still pass.

**`mock_datalayer` refactoring approach (CC=17):** A test fixture with 17
branches is hard to trust. Consider splitting into smaller, composable
fixtures (one per capability area: reads, writes, case lookups, actor
lookups) and composing them in a `conftest.py` fixture factory.

#### Phase 2 violation inventory (CC 11–15 — must reach CC≤10 before CC-2.2)

18 functions. Ordered by CC descending:

| CC | File | Function | Line |
|---|---|---|---|
| 15 | `vultron/core/use_cases/received/embargo.py` | `AcceptInviteToEmbargoOnCaseReceivedUseCase.execute` | 271 |
| 15 | `vultron/core/behaviors/report/nodes.py` | `CreateCaseActivity.update` | 496 |
| 14 | `vultron/core/use_cases/received/report.py` | `SubmitReportReceivedUseCase.execute` | 74 |
| 13 | `vultron/wire/as2/extractor.py` | `ActivityPattern.match` | 58 |
| 13 | `vultron/demo/scenario/two_actor_demo.py` | `verify_vendor_case_state` | 581 |
| 13 | `vultron/demo/scenario/multi_vendor_demo.py` | `verify_multi_vendor_case_state` | 364 |
| 13 | `vultron/core/use_cases/triggers/embargo.py` | `SvcAcceptEmbargoUseCase.execute` | 336 |
| 13 | `vultron/core/case_states/validations.py` | `is_valid_transition` | 232 |
| 13 | `vultron/core/behaviors/case/nodes.py` | `CreateCaseParticipantNode.update` | 877 |
| 13 | `vultron/core/behaviors/case/nodes.py` | `InitializeDefaultEmbargoNode.update` | 732 |
| 12 | `vultron/demo/scenario/three_actor_demo.py` | `verify_case_actor_case_state` | 417 |
| 12 | `vultron/core/use_cases/triggers/embargo.py` | `SvcRejectEmbargoUseCase.execute` | 571 |
| 12 | `vultron/core/behaviors/case/nodes.py` | `CreateInitialVendorParticipant.update` | 519 |
| 12 | `vultron/adapters/driving/fastapi/routers/actors.py` | `post_actor_inbox` | 366 |
| 11 | `vultron/demo/scenario/two_actor_demo.py` | `find_case_for_offer` | 528 |
| 11 | `vultron/core/use_cases/received/status.py` | `AddCaseStatusToCaseReceivedUseCase.execute` | 52 |
| 11 | `vultron/core/use_cases/received/embargo.py` | `RemoveEmbargoEventFromCaseReceivedUseCase.execute` | 115 |
| 11 | `vultron/adapters/driving/fastapi/main.py` | `main` | 85 |

**Pattern observations for Phase 2:**

- **`execute()` methods in use cases** (embargo, report, status): High CC
  often indicates missing BT subtree decomposition. Per `AGENTS.md`, all
  protocol-significant branching MUST live in the BT, not in `execute()`.
  Reducing CC here may also fix BT-06-001 compliance gaps.
- **`verify_*` functions in demo scenarios**: These enumerate state machine
  assertions. Consider extracting per-state-machine helpers
  (`verify_rm_state`, `verify_em_state`, `verify_cs_state`) and composing
  them, or using a table-driven assertion loop.
- **`is_valid_transition` (CC=13)**: State machine validity checkers benefit
  from lookup tables (set or dict of valid `(from, to)` pairs) rather than
  nested conditionals.
- **`ActivityPattern.match` (CC=13)**: After CC-1.1 refactors
  `extract_intent`, revisit whether `match` complexity can also be reduced
  via the same dispatch-table approach.
- **`post_actor_inbox` (CC=12)**: High CC in a FastAPI router handler
  violates the "routers delegate immediately" rule. Extract the branching
  logic into a helper in the adapter layer.

#### Verification command

```bash
# Check current violation count at a given threshold
uv run flake8 vultron/ test/ --max-complexity=10 --select=C901

# Check only Phase 1 targets
uv run flake8 vultron/wire/as2/extractor.py \
              vultron/wire/as2/rehydration.py \
              vultron/scripts/ontology2md.py \
              vultron/core/case_states/make_doc.py \
              test/core/behaviors/test_performance.py \
              --max-complexity=10 --select=C901
```

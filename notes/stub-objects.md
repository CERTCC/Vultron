---
title: Stub Objects
status: active
kind: guidance
description: >
  Rules for the VulnerabilityCase stub, the only stub type the protocol
  permits. The wider selective-disclosure and redaction design is a plan in
  notes/selective-disclosure.md.
related_specs:
  - specs/stub-objects.yaml
  - specs/message-validation.yaml
  - specs/case-management.yaml (CM-11-013, CM-17-002, CM-17-010, CM-17-011, CM-17-025, MV-10-001)
  - specs/actor-knowledge-model.yaml (AKM-05-017)
  - specs/case-ledger-processing.yaml (CLP-15-011)
  - specs/semantic-extraction.yaml (SE-01-009)
  - specs/vultron-as2-mapping.yaml (VAM-04-004)
  - specs/object-ids.yaml (OID-01-013)
related_notes:
  - vultron/core/ports/AGENTS.md
  - notes/wire-core-boundary.md
  - notes/case-joining.md
  - notes/selective-disclosure.md
  - notes/participant-embargo-consent.md
  - notes/as2-vocabulary-alignment.md
relevant_packages:
  - vultron/wire/as2
---

# Stub Objects

The `VulnerabilityCase` stub (`as_CasePreview`) is the only stub type
the protocol permits (MV-10-001, narrowed by ADR-0090). Requirements: MV-10 in
`specs/message-validation.yaml`. A typed reference is not a stub: it claims only
the `id` and `type` its sender knows (MV-10-011, ADR-0198). The actor reference
of AKM-05-017 is its built case; for other types it is a receiver-side rule only
(`vultron/wire/as2/typed_reference.py`), since this codebase's senders keep
inlining (AKM-03-003). Redaction exists only inside a preview (ADR-0193); the
wider design is in [selective-disclosure.md](selective-disclosure.md).

## Why Only `VulnerabilityCase`

An invitee must evaluate a case *before* accepting, and the case cannot be shared
until they accept (MV-10-005). So the stub is transient: the case's `preview`,
read as received, until the full case is announced once the invitee is
admitted. Everywhere else,
this codebase sends the full inline object (AKM-03-003, a prototype shortcut;
the protocol allows a fetchable reference, AKM-03-001), or a bare URI or `Link`
for an object the recipient already holds.

The stub is the `preview` of a typed case reference, `{id, type, preview}`, that
is the stub Invite's `object` (CM-11-013, ADR-0205). The reference's `id` names
the case; the stub's own `id` is not the case's, nor derived from it. Its own
`type`, `CasePreview`, is the case's defined preview (MV-10-012), and
its own `id` is minted like any object's (OID-01-013). The Invite is routed by
the reference's `type` and its form: only a pattern with
`object_form=PREVIEWED_REFERENCE` matches it (SE-01-009).

## Do Not Add Stubs of Other Types

A recognized inline object that fails its own class's validation is refused
(MV-04-003). Do not reintroduce arbitrary-type partial objects to get past that
refusal: a partial inline object and a corrupt one are indistinguishable to the
parser, which is why the refusal exists. The shape is the test (ADR-0198): exactly
`id` and `type`, with or without `preview`, is a typed reference; any other key
makes a whole object, validated in full and never completed by a default that
creates state (#5265). A `preview` is refused unless it is its type's preview, and
only the case has one: the stub, carried inline (MV-10-012, ADR-0205). Inside the
stub the rule differs: what a preview shows is read as its sender sent it, each
nested object in a loose form of its class, so a cut-down object there is not
refused (MV-12-006, [selective-disclosure.md](selective-disclosure.md)).

## Receiving a Stub

A stub is accepted only as the `preview` of a case reference that is an
`Invite`'s `object`, wherever that `Invite` is carried inline: in its `Accept` or
`Reject`, or in a refusal notice quoting such a reply. The parser refuses it
anywhere else, an `Invite`'s `target` and an embargo invitation included, because
only the stub Invite asks the question the stub answers (MV-10-002,
`refuse_misplaced_forms`).

That reference is read as received (MV-10-013): rehydration, the stored row and
the inbox never put the held case in its place or fetch the case, and only a
pattern that sets `object_form=PREVIEWED_REFERENCE` matches it (SE-01-009). Every
other pattern skips it, so a preview never seeds or updates a replica. A stub never
overwrites a full object already held (MV-10-003) and never creates a new domain
record (MV-10-004). The extractor carries the preview's content into core as a
`PreviewedCaseReference` whose `preview` is a `CasePreview`
(`vultron/core/models/case_preview.py`); core reads a recorded stub Invite's case
with `previewed_case_id`, never from the stub.

The parser checks a stub Invite's preview where it recognizes it, by position,
not in the `CasePreview` type: `refuse_unenveloped_invitation_previews`
(`vultron/wire/as2/invitation_preview_envelope.py`) refuses one that lacks or
marks its summary or Case Owner, or, with an embargo in force, its in-force
`embargoRegister` entry or EM state, or that carries an open proposal
(MV-10-007). It reads nothing else, because every other field is the sender's
choice (MV-12-006). The rules live in `invitation_preview_faults`, which the
sender's cut runs too, so both sides judge one envelope.

## Building the Stub

- The stub is `CasePreview.from_case(case, INVITATION_PROFILE)`
  (`vultron/core/models/case_preview_profile.py`, CM-17-010, ADR-0217). Each
  case field has one row: the operations the envelope permits and the one this
  codebase applies. A held field with no value is left out, never marked
  (MV-12-004).
- A new `VulnerabilityCase` field fails `from_case` and the drift tests in
  `test/core/models/test_preview_object.py` until it has a row. Classify it by
  the envelope: show it, mark it, or, for bookkeeping, make it omit-only and
  leave it undeclared on `CasePreview` (CM-17-025), so a received one is set
  aside (MV-11-003).
- `summary` is substituted from `VulnerabilityCase.stub_summary`, which the
  Case Owner sets before a stub Invite; `from_case` refuses with
  `VultronActivityConstructionError` without it, and
  `as_CasePreview._refuse_absent_summary` refuses an inbound stub with no
  `summary` key.
- `caseStatuses` is the case's current status, whole (CM-17-013), so its PXA
  state is the case's and its `published` is the status's own (CLP-15-010).
  Do not build a status for the stub: a class default states a value nobody
  observed.
- "In force" means the register holds an `ACTIVE` entry: EM `ACTIVE` or
  `REVISE`, never the exact EM state alone. Read it with `in_force_entry`, the
  entry the consent row and the Accept's signing name (CM-11-001, CM-11-006),
  or a `REVISE` invitee is bound to terms it never saw (CM-17-014, #4697). The
  open revision stays out of the stub; EP-09-011 relays it after joining.
- The stub's `embargoRegister` is that one entry, its embargo the full
  `EmbargoEvent` as the sender holds it, never a copy rebuilt from its ID and
  `end_time` (CM-17-011). The protocol lets a stub name the embargo by ID for
  the invitee to fetch (CM-17-002), but an invitee is not yet an active
  participant, and the case host serves case objects only to those
  (AKM-05-006), so the cut refuses an entry holding only the ID. The factory
  takes the fetched embargo as `embargo_obj` and carries it on a copy of the
  case.
- A stored case names its vul items by id, so the invite adapter carries the
  stored items on a copy before the cut; an item it cannot read is marked
  `Redacted`, since the cut shows each item only as its `ids` (CM-05-018).
- `AnnounceVulnerabilityCaseReceivedUseCase` needs the full inline case on
  `activity.object_`, so `extract_intent()` keeps rich `object_`, `target`, and
  `context` values when `include_activity=True`.

## Loose Forms

- `CasePreview` is a hand-written loose case: the case's fields under the
  case's names, every one optional, each loosened with `Redactable[T]`. It is
  not a subclass of `VulnerabilityCase`, so a full case is never a preview. Its
  `id`, `type` and `summary` hold no marker (MV-10-001).
- Nested loose forms are derived, not written: `loose_form(cls)` in
  `vultron/core/models/preview_object.py` builds each nested class's form, all
  the way down, so none falls behind its full class. A form keeps its full
  class's wire `type`, takes no type-registry slot (`shares_full_form_type`),
  and is picked by the parser where a preview field declares it. A class with
  its own wire shape (a scalar dimension) is shown whole or marked.
  `to_loose(obj, fields)` is how a sender shows a held object.
- A loose form reads a value as its full class does: it carries the class's
  `before` field validators and `plain` serializers, a marker passed by. It
  drops `after` and model validators, which are invariants a cut-down object
  does not have, and keeps `type_` and any `Literal` tag, so a discriminated
  union still picks its member.
- A leaky marker is the sender's fault. The parse edge sets aside an unknown
  key before the class validates (MV-11-003), so a marker carrying `content`
  arrives without it; do not add a parse-edge refusal of those keys, which
  would not undo the leak (MV-12-005).

---
title: Selective Disclosure and Redaction (Design Direction)
status: draft
kind: plan
tracks:
  - "#3258"
  - "#6372"
  - "#6641"
  - "#6692"
  - "#6511"
description: >
  Design direction for referencing objects without inlining them, the
  preview-only redaction marker (ADR-0193), and the field-by-field profile that
  cuts a stub Invite's case preview from the case (ADR-0217). The marker type
  exists, but no preview field accepts it yet; the delivered VulnerabilityCase
  stub is in notes/stub-objects.md.
related_specs:
  - specs/message-validation.yaml (AKM-03-001, MV-10-002, MV-12)
  - specs/actor-knowledge-model.yaml (AKM-05-006, AKM-05-007)
  - specs/case-management.yaml (CM-17-005, CM-17-010, CM-17-013, CM-17-021, CM-17-022, CM-17-023)
related_notes:
  - notes/stub-objects.md
  - notes/wire-core-boundary.md
  - notes/protocol-asks.md
  - notes/as2-vocabulary-alignment.md
  - notes/vulnerability-items.md
relevant_packages:
  - vultron/wire/as2
  - vultron/core/models
---

# Selective Disclosure and Redaction (Design Direction)

In this codebase outbound initiating activities carry full inline typed objects
(AKM-03-003, a prototype shortcut; the protocol allows either form, AKM-03-001).
That raises two concerns this plan addresses, beyond the one sanctioned
`VulnerabilityCase` stub ([stub-objects.md](stub-objects.md)):

1. **Verbosity**: inlining a full case or report in every activity that
   references it may become a performance problem.
2. **Privacy**: an actor may want to convey an object's identity and type without
   its contents.

## Dereferencing a URI Reference (#3258)

In AS2 the idiomatic way to reference an object you are not inlining is a URI or
a `Link`, which the receiver dereferences. Vultron resolves only a few references:
a participant fetches a case object from the CASE_MANAGER's case-scoped read
(AKM-05-006) when an activity cannot be classified without it, and the other
cases AKM-05-007 lists. A `Link` is never resolved, so a sender must still inline
the full object or accept an opaque reference. This is a prototype limitation,
not a production property, so dict-shaped partial objects must not become the
workaround.

## Redaction Builds a Preview (#4568, ADR-0193)

A field can be absent (unknown or not applicable), `null` (no value), or
**redacted**: it has a value the sender withholds from this recipient. Only a
preview can say the last one. A preview is a limited view of an object for a
recipient not yet entitled to it, never the object itself. The case stub is the
first, and is the case's AS2 `preview` (ADR-0205); wider previews (report,
reserved vul record, draft advisory) are #6257.

- **Wire form** (MV-12-003): `{"type": "Redacted", "summary": "<reason>"}`,
  `summary` optional, no other field, never the withheld value. `Redacted` is
  declared as a Vultron extension term under the rule #5743 writes.
- **Previews only** (MV-12-002): a receiver refuses a marker in any other
  position. A full object never holds one, so no domain field widens to "value or
  marker" and a stored case never carries one. Withholding one field of an
  otherwise full object is not supported: the shared, hash-chained ledger would
  hide it from the whole case anyway.
- **Not anonymity.** Hiding a participant's identity (#2562) gives the others a
  working stand-in, an alias a Coordinator relays through, held in the shared
  case for good. A redaction is a visible gap, usually lifted on admission, and
  a redacted identity cannot be addressed.
- **Not CM-09's redacted case view.** `RedactedVulnerabilityCase` (CM-09-001)
  is a planned production type: a whole, separate case object for an invitee.
  A preview marker withholds single fields of a limited view; neither replaces
  the other.

The marker type is `vultron/core/models/redacted.py`, registered in
`WIRE_TYPE_MAP`, and refuses every field but `type` and `summary`.
`reads_as_typed_reference` excludes `Redacted`, so a marker of only `id` and
`type` is a marker, never a reference. Today `CasePreview.redactable_fields` is
empty, so a marker anywhere is refused; #6372's loose `CasePreview` removes that
list, so any preview field may carry the marker.

## The Case Preview Profile (#6641, ADR-0217)

A preview is cut from the full case field by field. The protocol sets an
**envelope**, the operations each field permits; this codebase picks one of them
per field in a static **profile**, so the cut is mechanical and makes no choice
per invitation. Each field takes exactly one operation:

- **include**: the case's value, as held;
- **substitute**: a replacement (`summary` from the owner's `stub_summary`) or
  a reduction of the held value (the latest status only; items cut to their
  `ids`);
- **redact**: the marker. A list field is redacted as one marker, not a list of
  them;
- **omit**: no key.

**Value rules.** A held value the sender does not show is redacted, unless its
existence is itself the sensitive fact, when the sender may omit it. A field with
no held value (absent, `None`, or an empty collection) is omitted or substituted,
not redacted; a shown field with neither a value nor a substitute means the
preview cannot be built, as an unset `stub_summary` refuses today.

**Envelope.** Every operation is permitted unless a reason forbids it; past the
shown items, the sender chooses. "Shown" means include or substitute, not
redact or omit. Envelope cells: ✓ permitted, – forbidden. **Ours** is this
codebase's choice and is always a ✓ in its row.

| Case field | Include | Substitute | Redact | Omit | Ours | Reason for a – |
|---|---|---|---|---|---|---|
| `summary` | ✓ | ✓ | – | – | substitute: `stub_summary` | invitee needs readable context (MV-10-001) |
| `attributedTo` (Case Owner) | ✓ | ✓ (alias) | – | – | include | nobody joins a case without knowing who runs it |
| `caseStatuses` | ✓ | ✓ | ✓ / – in force | ✓ / – in force | substitute: `case_statuses[-1:]`, whole | EM state shown while in force (CM-17-013) |
| `name` | ✓ | ✓ | ✓ | ✓ | include | |
| `published`, `updated` | ✓ | ✓ | ✓ | ✓ | include | |
| `vulnerabilityItems` | ✓ | ✓ | ✓ | ✓ | substitute: each item cut to `ids` | |
| `content` | ✓ | ✓ | ✓ | ✓ | redact | |
| `caseParticipants` | ✓ | ✓ | ✓ | ✓ | redact | |
| `vulnerabilityReports`, `notes`, `caseReferences` | ✓ | ✓ | ✓ | ✓ | redact | |
| parent, child and sibling cases | ✓ | ✓ | ✓ | ✓ | redact | |
| any other AS2 property the case holds | ✓ | ✓ | ✓ | ✓ | redact | |
| `embargoRegister` | – | ✓ (must hold the in-force embargo, whole or by id, and no open proposal) | ✓ / – in force | ✓ / – in force | substitute: the in-force entry only, whole (CM-17-011) | consent to the in-force terms (CM-17-002); open proposals reach the invitee after joining (CM-17-014) |
| `pendingEmbargoProposalIndex` | – | – | – | ✓ | omit | relayed after joining (CM-17-014) |
| `genesisHash`, `ledgerPosition`, `actorParticipantIndex`, `caseActivity`, `stubSummary` | – | – | – | ✓ | omit | case bookkeeping, meaningless outside the case |

The preview keeps its own minted `id` and its `type` `CasePreview`; the case
reference carrying it names the case (ADR-0205). The embargo in force travels
as the case's own field, `embargoRegister`, reduced to its in-force entry, as
`caseStatuses` is reduced to the current status; the case's derived
`active_embargo` is not a field, so the preview does not carry it. Today a
register entry wraps the embargo and its status; ADR-0202 makes it the embargo
itself, and the reduction is the same either way. With no embargo in force our
reduction is empty, so the field is omitted. The CVE ID is an ordinary `ids`
entry (`systemName: "CVE"`), so the cut to `ids` keeps it (CM-05-018).
Our cut, with an embargo in force:

```json
{"id": "https://example.org/cases/abc", "type": "VulnerabilityCase",
 "preview": {
   "id": "urn:uuid:…", "type": "CasePreview",
   "summary": "A remote code execution vulnerability in widget.",
   "name": "Widget RCE",
   "published": "2026-08-03T00:00:00Z", "updated": "2026-11-01T00:00:00Z",
   "attributedTo": "https://example.org/actors/vendor",
   "embargoRegister": [{"type": "EmbargoEvent", "…": "the in-force embargo, whole"}],
   "caseStatuses": [{"type": "CaseStatus", "…": "the current status, whole"}],
   "vulnerabilityItems": [{"type": "VulnerabilityItem",
     "ids": [{"systemName": "CVE", "text": "CVE-2026-1234"}]}],
   "content": {"type": "Redacted"},
   "caseParticipants": {"type": "Redacted"},
   "vulnerabilityReports": {"type": "Redacted"},
   "notes": {"type": "Redacted"}}}
```

### Code Shape

- **`CasePreview` is a hand-written loose case** (#6372): the case's fields
  under the case's names, every one optional, each loosened with a
  `type Redactable[T] = T | Redacted` alias, nested objects in their own loose
  forms (a loose `VulnerabilityItem`). It is not a subclass of
  `VulnerabilityCase`, so `isinstance(case, CasePreview)` stays false for a full
  case. Omit-only fields are not declared: a received one is set aside as an
  unknown key (MV-11-003), the sender's fault, like a leaky marker.
- **A drift test** (#6692) pins every `CasePreview` field to a `VulnerabilityCase`
  field, and every `VulnerabilityCase` field to the preview or the profile's
  omit-only rows, so a new case field fails CI until it is classified. It lands
  with #6692, which gives the preview its final fields: until then #6372's loose
  type also keeps today's `activeEmbargo` and `caseStatus`, which no case field
  matches.
- **`CasePreview.from_case(case, profile)`** (#6692) applies the profile
  mechanically and refuses a cut that breaks the envelope. A property-style test
  checks that the cut of every valid case is a valid preview. It replaces
  `_project_case_to_preview`. Its `caseStatuses` replaces today's singular,
  built-for-the-preview `caseStatus`, and its `embargoRegister` replaces
  `activeEmbargo`.
- **The receiver's envelope check** runs where the stub Invite is recognized,
  not in the type: a receiver knows an invitation preview by its position, and a
  later profile (a transfer offer's preview, say) may share the loose type.

### A Leaky Marker Is the Sender's Fault

The parse edge sets aside an unknown key before the class validates
(MV-11-003), so a marker carrying `content` or `id` arrives at `Redacted`
without them. Do not add a parse-edge refusal of those keys: the receiver keeps
the normal unknown-key handling, and the rule moves to the sender (MV-12-005
below).
`test/wire/as2/test_redaction_marker.py::test_a_marker_carrying_the_withheld_value_is_refused`
asserts the old receiver-side refusal; #6372 replaces it.

### Requirement Changes the Tasks Land

Each change lands with the code that verifies it, so no requirement states a rule
its tests contradict.

Landed by #6372 (`message-validation.yaml`):

- **MV-12-001**: a receiver reads a marker in *any* field of a preview as that
  field's value withheld, never as absent or empty. The per-type opening goes.
- **MV-12-002**: a receiver refuses a marker anywhere other than a preview's
  field, naming the position.
- **MV-12-004**: a sender redacts a held value it does not show, unless the
  value's existence is itself sensitive, when it MAY omit the field. A field
  with no held value is not redacted.
- **MV-12-005**: becomes a sender rule. A sender MUST NOT put any field but
  `type` and `summary` in a marker. A receiver applies MV-11-003 to a marker's
  other keys.

Landed by #6692 (`case-management.yaml`, `message-validation.yaml`):

- **CM-17-010**: replaced by the envelope. A stub Invite's preview MUST show
  its `summary` and the Case Owner, and while an embargo is in force its terms
  (CM-17-002) and EM state (CM-17-013); it MUST omit open embargo proposals
  (CM-17-014) and case bookkeeping; every other field is the sender's choice of
  include, substitute, redact or omit.
- **CM-17-013**: the EM state travels in the preview's `caseStatuses`.
- **CM-17-002, CM-17-011, CM-17-024**: the in-force embargo travels as the
  preview's `embargoRegister`, reduced to that one entry, not as `activeEmbargo`.
  CM-17-014 holds by the reduction: no open proposal is in it.
- **CM-17-021** goes: this codebase shows the case name, and the envelope lets a
  sender substitute, redact or omit it.
- **CM-17-022** goes: the envelope replaces "no other case content".
- **CM-17-023** goes: the Case Owner is shown. Its only reason was that the
  Invite names the inviter, which is the CASE_MANAGER, not necessarily the owner.
- **CM-17-005, MV-10-005**: an invitee is entitled to what a preview shows,
  and to no other case content until it is active.
- **MV-10-007**: a receiver also refuses an invitation preview that lacks, or
  marks, the Case Owner, or, with an embargo in force, its terms or EM state.

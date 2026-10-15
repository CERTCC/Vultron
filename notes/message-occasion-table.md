---
title: "Message Occasion Table: Generated Fragments, Addressees and Sender Rules"
status: active
kind: plan
tracks:
  - "#4417"
description: >-
  Design of the occasion lookup table (ADR-0128, ADR-0129): how "Sent by" and
  "Send to" are derived from the sender rule and the occasion's addressee, the
  "When…" grammar, and typed distinguishers. Occasions, the generated
  fragments, the pages that include them, the how-to embeds with "Seen in" and
  the addressees (#4438) have landed.
related_specs:
  - specs/message-semantics-mapping.yaml
  - specs/handler-protocol.yaml
  - specs/project-documentation.yaml
  - specs/case-management.yaml
related_notes:
  - notes/message-type-reference.md
  - notes/case-communication-model.md
relevant_packages:
  - vultron/semantic_registry
  - vultron/metadata/msm
---

# Message Occasion Table

ADR-0128 (occasions; generated pages) and ADR-0129 (sender rules). Requirements:
MSM-08. Current-state guidance for the message pages: `notes/message-type-reference.md`.

A builder asks "a fix is ready — what do I send?", not "what wire form does `CF`
take?". The answer is one table keyed by **occasion**: a situation in a case that
a sender conveys with a wire activity, sometimes narrowed by a distinguishing
field value or state context (glossary, Messaging and Protocol). One semantic
type has one or more occasions (`Add(CaseStatus)` has three), so the table has one
row per (occasion, wire activity): When… | Send | Send to | Sent by |
Distinguished by | Details. The formal shorthand is only the Details link text.

## Where each fact lives

Nothing derivable is typed by hand. The occasions, `SemanticEntry.page`, the
derived `MappingStatus` and discriminator (#4429) and the generated YAML and
fragments (#4430) and the addressee (#4438) have landed (rules in
`notes/message-type-reference.md` § Occasions).

| Fact | Owner |
|---|---|
| when, distinguishing value, anchor ID, description, example, how-to link, shorthand, notes, section heading (when no own shorthand) | `SemanticEntry.occasions` |
| formal message name | `ProtocolShorthand.formal_name`, held to `formal_protocol/messages.md` by a test |
| wire summary | the entry's `ActivityPattern`, rendered as today |
| send to (addressee) | `Occasion.addressee`, an `AddresseeSide`, worded by its `send_to` (ADR-0129) |
| sent by | the side of the received use case's `sender_entitlement` matching the occasion's addressee (ADR-0115, ADR-0129) |
| page | `SemanticEntry.page`, a `MessagePage` value |
| `MappingStatus`, distinguished by | derived from the occasions by `vultron/metadata/msm/_mapping.py` (`evolved` declared on its occasion) |
| "Seen in" | the include directives on `docs/` pages (landed, #4432) |

The message pages include the generated fragments (#4431); the fragments exist
because MkDocs does not rewrite a `.md` link printed from an exec block, and a
lookup table is mostly links.

## "Sent by" is the receiver's rule

- The column states the `sender_entitlement` the received use case declares,
  because that is what another implementation must satisfy, and it cannot drift.
  It is often broader than CVD convention (any participant may send
  `Add(ParticipantStatus)` with `vf_state` `VF`), so an occasion may add a
  "usually" note typed as `CVDRole` values: "a participant (usually: vendor)"
  (MSM-08-005).
- "A participant" (`PARTICIPANT`) is any actor with a participant record on the
  case, active or not; "an active participant" (`ACTIVE_PARTICIPANT`) is one
  entitled to the case's content (CM-10-004). The two kinds split in #4437 so
  that each declaration says which one its handler checks.
- The wording is declared on each kind, not kept here: see
  `SenderEntitlementKind.sent_by` and `.term`, and `AddresseeSide.send_to`, in
  `vultron/core/behaviors/sender_entitlement.py` (MSM-08-010). A test holds every
  term to a glossary row. A position's wording names its object with an
  `{object}` placeholder ("the addressee of the case proposal", "the note's
  author"), and a nested request by its object and verb ("the addressee of the
  vulnerability case offer"); an exemption reads "not yet checked". About half
  the received use cases are exempt today, so the column fills in only as
  exemptions close; never paper over that with hand-written values.
- **Positions are entitlement kinds, not roles and not a second list**
  (HP-01-009). "The invitee" holds that position only within one exchange, and a
  report precedes any case, so no position joins `CVDRole`. A separate
  exchange-position enum was rejected; a position a new rule needs (the note's
  author) becomes a kind.
- **One addressee kind, worded from the exchange.** The actor a request was
  addressed to (other than an Invite) is one kind; its wording takes the request
  from the answered activity's object type ("the addressee of the case
  proposal"). It is `NAMED_ACTOR`; each use case's `SenderCheckContext` names the
  record holding its request (the case-proposal link, the report Offer, the
  ledgered ownership Offer), and each record has one small check on a shared base
  (#4437). The sync check that the CASE_MANAGER's own `Announce(CaseLedgerEntry)`,
  echoed back, came from itself is CASE_MANAGER standing and uses that kind's
  node. A `Reject(CaseLedgerEntry)` is a participant's, but a closed participant
  keeps it, so it is the `LEDGER_PEER` kind, not `ACTIVE_PARTICIPANT` (SYNC-03-005,
  CM-23-018). The invitee stays its own kind: it is checked
  against the `to` of the recorded Invite (EP-09-010, CM-11-017).
- **A declaration is the full rule, per addressee side** (HP-01-008). It is
  "any of" several kinds, stated per addressee (the CASE_MANAGER, a participant,
  or an actor outside any case), and the factory builds the guard from it alone.
  Declarations that used to be a floor with the rest in the tree now state the
  whole rule (#4437): `Remove(Note)` admits the note's author or the Case Owner
  at the CASE_MANAGER, and the embargo `Invite(Event)` admits the CASE_MANAGER or
  an active participant there; at a participant both admit only the
  CASE_MANAGER.
- **Each occasion names its addressee; "Sent by" and "Send to" are derived**
  (MSM-08-009). One wire activity can carry occasions with different senders: a
  participant's `Invite(Event)` to the CASE_MANAGER and the CASE_MANAGER's
  `Invite(Event)` to a participant match one entry and one use case, so they are
  two occasions (`embargo-proposal` and `relay-embargo-proposal`); `Remove(Event)`
  likewise has the Case Owner's `embargo-termination` and the CASE_MANAGER's
  `embargo-termination-notice`. `SemanticEntry` refuses an occasion whose
  addressee is a side its use case's rule leaves empty; an exemption constrains
  no addressee until it closes.

## Row content rules

- **One grammar for "When…"**: the sender's situation, from the sender's side,
  for mechanics too ("the case manager has committed a case event"), so every
  wire activity keeps at least one row.
- **Occasion prose is docs prose.** It renders on reference pages and how-to
  guides, so it follows the docs style guide, glossary terms, and no "you"
  (DF-09-008, MSM-08-007).
- **Details link** names the formal message and code ("Fix Readiness (CF)")
  (DF-09-010, MSM-08-008). Expansion rows (`GI`, `RV`, `RI`, `RC`) link by
  section heading instead, since one label would repeat on every row.
- **A distinguisher is typed** (MSM-08-002): a field value checked against its
  enum, or a state context naming a state machine and states (the EM state
  separating `EP` from `EV` on `Invite(Event)`).

---
source: NOTES-as2-vocabulary-alignment--refusal-is-its-own-type
timestamp: '2026-11-14T00:47:54.029807+00:00'
title: 'Archived notes section: Refusal Is Its Own Type (as2-vocabulary-alignment)'
type: note
---

## Refusal Is Its Own Type

Issue: #6254. Built by #6433 (type list at the wire edge), then #6434 (the `Refuse`
type), then #6435 (the owner-close answer).

**Decision.** A refusal notice is `"type": ["Refuse", "Reject"]`: `class
Refuse(Reject)` in the wire vocabulary, and `vultron:Refuse rdfs:subClassOf
as:Reject` in the Vultron context. The wire then follows CLP-02-016's *refused*
versus *rejected* (ADR-0196).

- **The list stays at the wire edge.** One shared resolver narrows a received `type`
  list to the most specific class the vocabulary knows, in any order, ignoring terms
  it does not know (`["Foo", "Reject"]` is a `Reject`); core holds one string
  (`"Refuse"`). The serializer writes the list for a class that declares a core
  supertype. Reason: a list in core changes every `type_` and type check for no gain.
- **Two known, unrelated types in one list are refused** as an unknown type (422). A
  bare `"Refuse"` is accepted. Reason: neither class is the more specific one.
- **A resolved `Refuse` matches no `Reject` pattern**, so `RefusalNoticePattern`
  drops its `Invite`/`Offer` exclusion and a refusal of a request reaches the
  refusal-notice use case, not the decline. Reason: ADR-0196 replaces ADR-0141's
  "a refusal of a request reads as a decline".
- **Refuse versus Reject is by who decides.** The CASE_MANAGER's guard refusal is a
  `Refuse`, including its answer to the owner's `Leave(VulnerabilityCase)` during an
  active embargo (CM-23-011) and its optional reply to a late `Leave` after close
  (CM-23-040, CM-23-057; ADR-0131's drop default stays).
  A participant's own `Reject(Invite(EmbargoEvent))` at P/X/A stays a `Reject`: it
  is the addressee's decline (EMB-01-002).

**AS2 basis.** No AS2 verb fits "I won't admit your act": `Ignore` is ignoring and is
our RM defer, `Block` targets an actor and is not delivered to it (ActivityPub), `Flag`
reports content to a moderator, `TentativeReject` is not final and is our RM invalid,
`Dislike` is sentiment. CORE extension guidance: an extension type that overlaps a
core type MUST carry the core type too (the spec's example is `["Resign","Leave"]`).

**Today.** `as_Refuse` (`vultron/wire/as2/vocab/extension_activities.py`) declares
`_as2_core_supertype = as_Reject`; the refusal notice is a `Refuse(<refused activity
inline>)` sent as `["Refuse", "Reject"]`, and `RefusalNoticePattern` matches
`Refuse` of any inline activity. `wire-context` writes the `@graph` subclass
statement from that one declaration. What remains is #6435: the close-case tree
still answers the owner's `Leave(VulnerabilityCase)` with a plain
`Reject(Leave(Case))`, which now matches no pattern, so
`test_a_declined_leave_closes_the_owners_pending_leave` is a strict `xfail` until
that answer becomes the standard `Refuse`. Reason: AC-3 of #6434 keeps no fallback
for a plain `Reject` of a non-request.

**Touches.** ADR-0131, ADR-0141, ADR-0196, MSM-05-001, CLP-02-005, CLP-05-001,
CLP-02-016, CM-23-011, CM-23-040, CM-23-057, VM-03, `REFUSAL_NOTICE`, the
`OWNER_CLOSE_DECLINE` refusal-notice exemption, and `docs/ns/context.jsonld`.

Delivered by #6433, #6434 and #6435. The lasting rule (a refusal notice is a `Refuse`; a participant's `Reject` of a request stays a decline) is in `notes/case-ledger-authority.md`, and the type-list rules are in `notes/vocabulary-registry.md`.

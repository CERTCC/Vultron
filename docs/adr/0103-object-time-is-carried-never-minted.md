---
status: accepted
date: 2026-09-23
deciders: Allen D. Householder
consulted: CERT/CC Vultron protocol team
informed: CERT/CC Vultron protocol team
---

# An Object's Time Is Carried, Never Minted by the Receiver

## Context and Problem Statement

ActivityStreams 2.0 makes `published` and `updated` optional on every object,
and nested (inline) objects routinely omit them. Vultron's wire classes declared
both with `default_factory=now_utc`, so an omitted timestamp was filled with the
*receiver's* wall clock during validation. After `model_validate` returned, that
fabricated value was indistinguishable from one the sender had supplied.

The same classes author outbound activities and validate inbound ones, so the
default was simultaneously right (for an object this process creates) and wrong
(for an object it receives). Three consequences were measured:

- **Genesis diverged per receiver.** A case's `genesis_hash` is derived from its
  `published` (CLP-08-002). Core recomputed it from the minted time, so each
  receiver derived a different genesis for the same case (ISSUE-3257).
- **Received statuses ordered by arrival.** `current_status` orders by
  `updated or published`. Minted values order by *when the list happened to be
  rendered*, not when the statuses were recorded (ISSUE-2553).
- **Ledger dedup was a race against the clock.** Re-rendering one stored object
  twice yielded two different snapshots, so a retry landing in the next whole
  second appended a duplicate ledger index — the instability ADR-0041 forbids.

The question issue #2553 asked directly: *should an object carry its own
creation and modification time, and should the render carry it rather than mint
it?*

## Decision Drivers

- A receiver-minted value is later indistinguishable from the sender's claim,
  and `payloadSnapshot` comparisons (CLP-14-006/007/008) assume `published` is
  the asserting participant's claim.
- Rendering one stored object twice must produce equal dicts, or no comparison,
  hash or ordering over rendered objects is meaningful.
- Absence is common and mostly harmless: AS2 permits it everywhere, and most
  consumers only order by time.
- Fabricating data to satisfy a type is the failure mode ADR-0032 exists to
  prevent — validate at the edge, do not correct downstream.
- Outbound authoring genuinely needs a clock default; the two directions must be
  separated rather than one of them losing.

## Considered Options

1. **Carry the time; refuse only where a decision needs it** (chosen).
2. **Keep minting, and treat timestamps as non-semantic everywhere.** Every
   consumer stops comparing, hashing or ordering by them.
3. **Keep minting, but record provenance.** Add a "was this minted?" flag beside
   each timestamp so consumers can tell claim from fabrication.

## Decision Outcome

Chosen option: **carry the time; refuse only where a decision needs it**.

An object's `published`/`updated` is taken as received at every boundary —
parsing, extraction, storage, rendering. A timestamp the sender omitted stays
absent (`None`); the receiver never substitutes its own clock. Absence is
refused *only* where a decision actually reads the value, and that refusal
happens at message validation, not deep in core:

- a case with no `genesisHash` and no `published` (CLP-08-002);
- an embargo with no `endTime` — the value embargo decisions read;
- a replicated ledger entry with no `published`/`receivedAt` (CLP-14-002,
  CLP-02-008; `received_at` is hashed content, so a replica must not re-stamp
  it).

Locally authored objects keep the `default_factory` clock. The two directions
are told apart by **validation context**, not by a field default: the parser
passes an inbound marker, and `as_Base.carry_absent_times_on_inbound` reads
absent clock-defaulted timestamps as `None` for the class being validated.

Option 2 was rejected because the values are load-bearing in the protocol, not
merely informational: CLP-14-006/007/008 and CLP-15-003 read `published` as the
sender's claim, so making timestamps non-semantic would mean deleting protocol
requirements rather than satisfying them. It also keeps the fabrication in the
stored data, where every future consumer inherits the trap. Option 3 was
rejected because a provenance flag makes every consumer responsible for checking
it — the same guard-at-every-call-site pattern ADR-0032 replaced — and `None`
already carries exactly that information at no cost.

### Consequences

- Good, because a timestamp on a stored object is now always somebody's claim,
  so comparing, hashing and ordering over rendered objects is meaningful.
- Good, because rendering one stored object twice produces equal dicts, which
  lets ledger dedup stop normalising timestamps away recursively — a nested time
  that differs is now a genuinely different assertion.
- Good, because each receiver derives the same genesis for the same case.
- Bad, because `published`/`updated` are now `datetime | None` on `CoreObject`,
  so consumers must handle absence. `most_recent_status` sorts `None` lowest and
  breaks ties by append order; `CaseLedgerEntry.published` and an embargo's
  `end_time` stay required precisely because decisions read them.
- Bad, because a sender that omits a time a decision needs now gets a 422 where
  it previously got silent acceptance. That is the intended trade: the message
  was never interpretable, and failing at the edge names the missing field.
- Neutral, because the inbound marker is a validation-context key. It is set in
  exactly one place (`parse_activity`); passing it while *authoring* an object
  would silently drop that object's time.

## Validation

- `specs/case-ledger-processing.yaml` CLP-15-007 states the rule normatively.
- `test/wire/as2/test_nested_timestamps.py` covers every nested kind ×
  omitted/blank/null, plus genesis, embargo and ledger-entry refusals.
- `test/core/behaviors/sync/nodes/test_participant_status_effect.py` pins that a
  replica rebuilding a status from a snapshot carries absence rather than
  stamping its own clock.
- `test/adapters/driven/test_wire_render_adapter.py` pins that rendering across
  a clock tick is deterministic.

## More Information

Supersedes nothing, but narrows two earlier decisions in scope:

- **ADR-0090** (a blank required field is absence) established that blank and
  `null` both mean absence. This extends that reading to *omission* on the
  inbound path, so all three spellings arrive as the same `None`.
- **ADR-0032** (validate at the edge, promote to strict core types) is the
  reason refusal happens at parse rather than being corrected downstream. Note
  the direction: this ADR makes a core field *looser* (`datetime | None`), which
  is consistent with ADR-0032 because `None` here is a real, distinct state —
  "the sender claimed no time" — not a silent failure to be guarded at every
  call site.
- **ADR-0041** (ledger index stability) is what the clock race violated.

Issues: #2553 (render mints instead of carrying), #3257 (nested objects get the
receiver's clock).

Generated spec requirements: `case-ledger-processing.yaml` CLP-15-007.

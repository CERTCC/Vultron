---
source: IDEA-605
timestamp: '2026-09-01T21:11:58.981080+00:00'
title: Consolidated per-message-type reference pages
type: idea
---

## Original Idea

Create one consolidated reference page per Vultron message type covering the
message's role in the protocol, its ActivityStreams 2.0 representation, links to
the relevant how-to guide, and a rendered example. Message documentation was
scattered across `howto/activitypub/activities/` (task-oriented pages),
`reference/examples/` (~45 raw JSON files not surfaced in the nav), and
`reference/formal_protocol/messages.md` (formal listing), with no single place to
look up a message type and get the full picture.

## What Planning Found

The literal request was unbuildable as stated, and finding out why produced the
most valuable output of this round.

**The two message vocabularies are different shapes.** The formal protocol defines
28 shorthand symbols partitioned by state machine; the implementation has 51
`SEMANTIC_REGISTRY` entries partitioned by ActivityStreams verb and object. The
correspondence is many-to-many in both directions, so no single key indexes both
worlds one-to-one:

- Collapses: `CV`/`CF` share `as_ParticipantStatus.vf_state`; `CP`/`CX`/`CA` share
  `as_CaseStatus.pxa_state`; `EV`/`EJ`/`EC` are sent as `EP`/`ER`/`EA`; the RM
  ladder also rides `rm_state` in parallel with its dedicated report activities.
- Expansions: `EP` is realized by four wire activities; `GI` covers the note
  lifecycle *and* the actor-suggestion handshake; the `Create(X)` + `Add(X → Y)`
  split is a wire artifact with no formal counterpart at all.
- Roughly half the registry has no formal counterpart: case lifecycle, roster,
  invitations, role delegation, ownership transfer, case proposal, ledger
  replication.

**A normative defect was found and fixed.** MSM-03-001/-002/-003 asserted at
`MUST` / `kind: protocol` that `CV`/`CF`/`CD` dispatch as
`ADD_CASE_STATUS_TO_CASE` with `vendor_aware`/`fix_ready`/`fix_deployed` payload
fields. No such fields exist on `as_CaseStatus`. V/F/D are participant-scoped and
live on `as_ParticipantStatus` as `vf_state`/`d_state` per ADR-0075 — there are no
case-level V/F/D states at all. A case-level status cannot express *which* vendor
is aware, which is the entire purpose of the V dimension in MPCVD. The spec
contradicted an invariant `notes/case-state-model.md` already documented as
structurally enforced. Cause: MSM-03 predates ADR-0075 and ADR-0036, and its
group description generalized "all CS shorthands share ADD_CASE_STATUS_TO_CASE"
onto entries that should have diverged.

**Two mechanisms evolved rather than went missing.** MSM previously recorded
`RE`/`EE`/`CE`/`EK`/`CK` as having "no AS2 wire representation", which read as
unimplemented. They are implemented on different axes:

- Faults partition by **failure mode**, not state machine:
  `Create(ProcessingFault)` (not understood), `as:Reject` (understood, declined),
  `Create(Note)` (needs explanation).
- Ledger acknowledgement is **cumulative and implicit** via hash-chain continuity:
  a matching `prev_log_hash` is the ack; a mismatch triggers
  `Reject(CaseLedgerEntry)` and gap-fill replay. Closer to TCP cumulative
  ACK/SACK than to per-message `EK`/`CK`/`GK`.

**A documented wire format was never built.** `howto/.../error.md` depicts
`RmError`/`EmError`/`CsError`/`GmError` discriminated by `as:inReplyTo`. Those
types exist in no ontology file and no code, and `ActivityPattern.in_reply_to_` is
used by zero registered patterns.

**The how-to pages are misfiled.** `howto/activitypub/activities/` is a Diátaxis
partial collapse violating DF-01-003: 17 pages each mixing Explanation (design
rationale, alternatives weighed, activity-graph diagrams), Reference (rendered AS2
examples), and a thin How-to tail (the `vultron-demo` Try-it blocks). Titles are
noun phrases where DF requires "How to [Action]"; `acknowledge.md` is almost
entirely rationale and passes the bath test. So the requested reference pages are
the Reference half of un-blurring an existing collapse, not a fourth surface.

## Decisions

- Pages grouped **by state machine** with one section per message type, not one
  page per shorthand — six CS shorthands share two wire activities, so a page per
  shorthand would be a page per payload-field value.
- Mapping tables **rendered at build time** from the MSM spec registry joined
  against `SEMANTIC_REGISTRY`, never hand-written.
- Examples **rendered at build time** via `markdown_exec`, following
  `docs/reference/specs/protocol.md`.
- Full **three-way Diátaxis split** in one campaign: Reference to
  `docs/reference/messages/`, Explanation to `docs/topics/`, genuine task content
  retained as how-to guides.
- `docs/reference/examples/` JSON **kept as downloadable artifacts**, with the
  generator's hardcoded relative path fixed and a regeneration check added.
- Divergences **recorded, not silently resolved** — whether `messages.md` should
  change is a normative question routed to Concerns.

## Outcome

**Processed**: 2026-09-01.

- Implementation tracked in issues #2998, #2999, #3001, #3002, #3003 and #3004.
- Normative-specification questions raised as Concerns #3005 and #3006.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2997>
ADR: `docs/adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md`
Spec: `specs/message-semantics-mapping.yaml` (MSM-04 through MSM-06; MSM-03 fixes)
Notes: `notes/message-type-reference.md`

All implementation issues are blocked by #2904 (single root cause behind all 101
failing `markdown_exec` example blocks), since the pages render examples that way.

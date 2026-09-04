---
status: accepted
date: 2026-07-31
deciders: [adh, Claude Opus 4.8]
---

# ADR-0049: Core Does Not Model Inbound Protocol Error Message Types; No `create_inbound_error_followup_tree`

## Context and Problem Statement

The fuzzer node catalog (FUZZ-08a-bis, `notes/bt-fuzzer-nodes-messaging.md`)
maps the simulation node
`vultron/bt/messaging/inbound/_behaviors/fuzzer.py:FollowUpOnErrorMessage` to a
`FUTURE:` production factory function
`vultron.core.behaviors.inbox.create_inbound_error_followup_tree`, tracked by
Idea #1254 under Epic #1285 (FUZZ-D). The simulation node is a `fallback_node`
that, with p=0.5, emits a General Inquiry (`EmitGI`, `MT.GI`) follow-up to the
sender when an unexpected or error message type (RE/EE/CE/GE) is received —
modelling "A sends B something malformed; B follows up to ask what went wrong
and how it can help."

Planning #1254 required first checking whether that behavior has a production
home. It does not, and the reason is structural, not an oversight:

1. **Core cannot send the message this responds to.** The simulation's
   error/inquiry message vocabulary (`MT.{RE, EE, CE, GE, GI, ...}` in
   `vultron/bt/messaging/outbound/behaviors.py`) does **not exist in core**. A
   sweep of `vultron/core/` and `vultron/semantic_registry/` for
   `GI`/`GE`/`CE`/`RE`/`EE`/`GeneralInquiry`/error-message finds nothing. Core
   emits no error message types and registers no GI semantic. A production
   subtree that responds to an inbound error message would be responding to a
   message class core has no notion of — building the responder before the
   stimulus exists.

2. **The underlying intent is already served by an existing path.** The real
   production expression of "flag a problem on a case and get a response back to
   the originator" is the note-to-case flow:
   `create_note_tree`, `create_add_note_to_case_received_tree`, and
   `add_note_to_case_trigger_bt` (`vultron/core/behaviors/note/`). A participant
   posts `Add(Note, target=Case)`; the Case Owner sees it and responds with
   another `Add(Note, ...)` that propagates back to the originator via case
   ledger sync (SYNC-02-002), **not** a direct broadcast. Any communication
   outside that path (e.g. direct actor-to-actor troubleshooting) is
   out-of-band and out of scope by definition.

3. **`FollowUpOnErrorMessage` was a fuzzer stub, not a modelled protocol
   exchange.** Its own docstring calls it "a stub for following up on an error
   message" that emits stochastically "to simulate sending a follow-up
   inquiry." It models the *uncertainty* of a human analyst deciding to follow
   up — not a deterministic protocol obligation. There is no acknowledgment
   message type or negative-acknowledgment obligation in the protocol for it to
   port to.

The question is therefore: **should core introduce inbound error message types
and a `create_inbound_error_followup_tree` factory to host this call-out point,
or should it record that this simulation node has no production analog?**

This follows the pattern of the sibling issue #1253
(`create_close_report_tree`), which during implementation was found to be a
seam-only stub rather than a workflow (#1855) — the value was in documenting
the non-thing, not in building it.

## Decision Drivers

- Core must not carry infrastructure for a stimulus it cannot produce (no
  RE/EE/CE/GE emit path, no GI semantic).
- BT-16-001: core tree builders must not depend on `vultron/demo/`; a factory
  whose only backend is the stochastic fuzzer stub would violate the intent of
  the call-out abstraction (a real injection seam, not a tightly-coupled stub —
  BT-18-004).
- The `FUTURE:` catalog pointer will cause a future agent to re-plan this exact
  issue unless the decision is recorded durably.
- Scope discipline: the legitimate open question (should core notify a sender
  when it cannot process their inbound?) is a distinct protocol question, not a
  port of this node.

## Considered Options

1. **Record that core does not model error message types; do not build the
   factory** (chosen). Close #1254 with no production code. Flip the catalog's
   `FUTURE:` pointer to `RESOLVED:`. Capture the sender-notification question
   as a separate Concern.

2. **Build `create_inbound_error_followup_tree` as a seam-only stub anyway.**
   Introduce a messaging call-out bundle and a factory exposing a Composer
   seam, unwired, defaulting to a DETERMINISTIC backend. Rejected: it manifests
   the simulation's structure (`ReceiveMessagesBt` error arm) that does not
   exist in core, adds a bundle and factory with no caller and no stimulus, and
   creates the appearance of a supported behavior that emits nothing. This is
   dead scaffolding that a later reader must reverse-engineer.

3. **Introduce error/GI message types into core and wire a full follow-up
   workflow.** Rejected here: this is a large, speculative protocol expansion
   (a new message-type family plus dispatch, semantics, and use cases) that
   #1254 does not justify. If a sender-notification requirement is later
   established, it should be designed on its own merits, not reverse-derived
   from a fuzzer stub.

## Decision Outcome

**Chosen option: record the boundary; build nothing (Option 1).**

- Core deliberately does **not** model inbound protocol *error* message types
  (RE/EE/CE/GE) or the General Inquiry (GI) follow-up message. The simulation's
  `FollowUpOnErrorMessage` has **no production analog** and
  `create_inbound_error_followup_tree` will **not** be created.
- The intent it approximated — surfacing and responding to a problem on a case
  — is served by the existing note-to-case-via-ledger path
  (`vultron/core/behaviors/note/`, SYNC-02-002) and by out-of-band
  communication, which is out of scope.
- Today, an inbound object core cannot resolve is dead-lettered
  (`create_store_dead_letter_tree`, `UnresolvableObjectReceivedEvent`) and a
  protocol-invalid payload yields an `InboxOutcome` of `"rejected"`
  (`vultron/core/behaviors/inbox/_process_payload.py`). Neither notifies the
  sender — this is the status quo and is unchanged by this ADR.

### Consequences

- Good, because core avoids scaffolding (a messaging call-out bundle, a
  factory, a `ReceiveMessagesBt`-shaped error arm) for a stimulus it cannot
  generate.
- Good, because the `FUTURE:` catalog pointer becomes a resolved decision,
  preventing re-planning of #1254.
- Good, because the boundary "core does not model error message types" is now
  explicit for future protocol work.
- Neutral, because the deferred question (should core notify a sender on
  unprocessable inbound?) is preserved as a tracked Concern rather than
  silently dropped.
- Bad, because a reader expecting one-to-one fuzzer-node-to-factory coverage in
  Epic #1285 will find a deliberate gap here; this ADR and the catalog
  `RESOLVED:` note are the explanation.

## Validation

- Grep sweep confirming no `RE`/`EE`/`CE`/`GE`/`GI`/`GeneralInquiry` message
  type or `create_inbound_error_followup_tree` symbol exists in `vultron/core/`
  or `vultron/semantic_registry/`.
- `notes/bt-fuzzer-nodes-messaging.md` `FollowUpOnErrorMessage` entry updated
  from `FUTURE:` to `RESOLVED:` with a pointer to this ADR.
- Idea #1254 closed with a resolution comment referencing this ADR.

## More Information

- Source: Idea #1254 (reframed to a no-build decision), Epic #1285 (FUZZ-D).
- Precedent: #1253 / #1855 — `create_close_report_tree` similarly collapsed
  from a "workflow" to a documented non-workflow during planning.
- Related open question (filed as a Concern): core silently dead-letters or
  rejects unprocessable inbound with no sender notification. Whether the
  protocol needs a negative-acknowledgment / error-reply facet is a separate
  design question, not a port of `FollowUpOnErrorMessage`.
  **Discharged by ADR-0080 (2026-08-31), CONCERN-1880.** That Concern is the
  Concern this ADR asked to be filed, and the deferral is now resolved with a
  recorded *yes*: an authenticated sender whose message fails after
  authentication receives `Create(ProcessingFault)` (ASK-07-001). This ADR's own
  decision is **unchanged** — core still does not model the RE/EE/CE/GE/GI
  message family, and `create_inbound_error_followup_tree` is still not created.
  One dedicated fault object type carried on `Create` is not that family, and it
  was designed on its own merits (from the need to close an outstanding ask
  promptly rather than let it expire) rather than reverse-derived from
  `FollowUpOnErrorMessage`, which is what this ADR required of any later design.
- BT-18-004 (call-out points are injection seams via backend factories) and
  BT-16-001 (core must not import from `vultron/demo/`) informed the rejection
  of the seam-stub option.
- Existing production analog: `vultron/core/behaviors/note/` note-to-case flow;
  dead-letter path `vultron/core/behaviors/inbox/dead_letter_tree.py`.

---
title: Capability Shapes Design Notes
status: active
kind: plan
tracks:
  - "#1143"
  - "#1147"
  - "#1845"
  - "#1856"
  - "#1893"
  - "#1943"
  - "#2450"
  - "#5415"
  - "#6078"
description: >
  Design for the capability layer's unbuilt work: the participant-suggestion
  port's Sentinel caller (#5415) and the Sentinel call-in pattern (#2450).
  Also says where the demos' static suggestion adapter runs. Also states the
  call-out time budget rule, routes a design question to a capability, an
  ask, or a call-in monitor, and says why Sentinel is not a fifth shape; the call-in and
  call-out surfaces themselves are defined in call-out-configuration.md.
related_notes:
  - notes/bt-integration.md
  - notes/agentic-workflow.md
  - notes/call-out-configuration.md
  - notes/protocol-asks.md
related_specs:
  - specs/behavior-tree-node-design.yaml
  - specs/behavior-tree-integration.yaml
  - specs/case-ledger-processing.yaml
relevant_packages:
  - vultron/core/behaviors/call_out
  - vultron/demo/fuzzer
  - vultron/core/use_cases/triggers
  - vultron/core/behaviors
---

# Capability Shapes Design Notes

A **call-out point** is a BT node where the protocol cannot decide the next action
itself and must ask an external party inside the tick. The four **capability
shapes** — **Evaluator**, **Retriever**, **Composer**, **Actuator** — are the
interface contracts that answer them. Definitions: `CONTEXT.md` § Capability
Shapes; taxonomy: ADR-0097 (superseding ADR-0024's five shapes).

The call-in and call-out surfaces are defined in
`notes/call-out-configuration.md` § "Two Integration Surfaces: Call-In and
Call-Out"; all four shapes live on the call-out surface.

## Which Surface a Question Belongs On

The discriminator is **who can answer, and when** (BT-18-014, BT-18-023):

| The question… | Surface | Mechanism |
|---|---|---|
| can be answered by a service *this actor operates*, within one tick | call-out | a capability, injected as a `CallOutBackendFactory` |
| needs a decision from *another actor in the case* | neither — it is an **ask** | `Offer` + terminate; route on conversation state (ADR-0080) |
| is "has the moment to act arrived yet?", asked by nobody | call-in | a monitor that decides for itself and calls a trigger endpoint (the Sentinel pattern) |

An ask modelled as a call-out point is a gate that can only ever answer no,
because no answer exists at the moment of asking (ADR-0080). If the answer must
come from a peer, see `notes/protocol-asks.md`. A synchronous boolean query of an
external system is a **Retriever**, never a Sentinel (BT-18-013).

## Capability Declarations Are the Roster

Every named capability is declared once, in core, under
`vultron/core/behaviors/call_out/capabilities/`, as a subclass of a shape base in
`vultron/core/behaviors/call_out/capability.py` whose typed ports are its contract
(BT-18-012, BT-18-020, BT-18-021).

- Derive any per-capability list from `capability_declarations()`, never a hand-kept
  list: a bundle field's DETERMINISTIC default binds to its capability's
  declaration (`always_succeed_as` / `always_fail_as`) and writes its
  `OUTPUT_PORTS`, and the docs catalog renders from the same roster
  (`vultron/metadata/docs/capability_catalog.py`). Reason: a second list drifts,
  which is what ADR-0097#core-declared-typed-port-contract removed.
- A field answers what its simulation node binds, so a new capability's field binds
  both sides (`test/core/behaviors/call_out/test_defaults_write_declared_outputs.py`).
- A declaration in a new module needs a domain section on
  `docs/topics/capability_model/index.md` that names the module in a
  `render_capability_table` block; `test/metadata/docs/test_capability_catalog.py`
  fails until it does, because the page's headings and prose are hand-written.
- A new capability adds a declaration there, then a fuzzer node that
  subclasses it; the roster tests then require the docstring contract to match the
  ports and the node to write every output on *yes*
  (`test/core/behaviors/call_out/test_capability_declarations.py`).
- A port names a concrete `data_type`, never `object`: a mismatch on read or write
  fails the whole tree run (BTND-03-021), and `object` would let every value
  through.

Why a contract declared outside core fails: `notes/call-out-configuration.md` §
"A data-producing capability's default must write its outputs".

## A Capability Answers Fast, or It Is Not a Capability

A backend answers within one tick (BT-18-011) **and** within the local actor's
`ActorConfig.call_out_time_budget` (BT-18-015). Work that cannot meet the budget
is an ask or a call-in monitor, not a capability. `TimeBoundedCallOut` in
`vultron/core/behaviors/call_out/guard.py` detects an overrun after the backend
returns and names the node; it never interrupts the backend, so a slow backend
still holds the worker.

## Fuzzer Nodes Are Call-Out Point Candidates

Each fuzzer node in `vultron/demo/fuzzer/` stands in for logic not yet identified.
For each, ask what actually drives the choice:

1. Deterministic from data the case already holds → ProtocolInternal, no
   capability.
2. External data, including a binary query → **Retriever**.
3. Judgment → **Evaluator**.
4. A side effect in an external system → **Actuator**.
5. Drafted content → **Composer**.
6. A decision from another case actor → a **protocol ask** (ADR-0080).
7. A condition watched over time that should trigger an action → the **Sentinel
   pattern** on the call-in surface.

The docstring's `Input category` and `Automation potential` give a first guess:
`High` + `Environmental check` needs no capability; `Low` + `Human decision` is an
Evaluator (or human). Say **call-out point**, never "touchpoint" (ADR-0025).

## The Sentinel Pattern Is Call-In, Not a Shape (#2450)

A Sentinel runs on its own: it watches a condition and, when it fires, calls a
trigger endpoint. None of the capability machinery applies to it — no
`CallOutBackendFactory`, no bundle field, no blackboard contract, no
`SynchronousCallOut`, no ceiling/floor rule (BT-23-002) — so ADR-0097 removed it
from the taxonomy (BT-18-013).

- **The discriminator is who initiates, not where the data comes from.** A
  capability is consulted at a call-out point; a Sentinel is never consulted, it
  decides the moment has come. A Sentinel may watch the case's own replicated
  state (#1856) and post into the case (#1845).
- **Observer is a role; Sentinel is a pattern.** A participant Sentinel usually
  holds `CVDRole.OBSERVER` (ADR-0057) by enacting the pattern; keep the terms
  distinct.
- **Two deployment shapes, chosen per monitor for protocol visibility:**

| | Participant Sentinel | Operator-side Sentinel |
|---|---|---|
| Case identity | an Actor on the roster, typically `CVDRole.OBSERVER` | none — not a participant |
| Sees case state by | `Announce(CaseLedgerEntry)` replication | whatever its host actor already knows |
| Acts by | emitting protocol messages (`Note`, `Add(ParticipantStatus)`) | calling its host actor's trigger endpoints |
| Visible to other participants | yes | no — messages appear to come from the host actor |
| Admission | Invite / Accept | deployment credentials |

A monitor accountable to the case wants the participant form; an embargo timer
that is just how one organisation runs its actor wants the operator-side form.
ADR-0080's `reap-expired-asks` trigger (ASK-05-002) is the canonical seam: core
exposes a trigger, and a watcher calls it.

Open questions for #2450 (Sentinel Ideas stay parented under #1147): invocation
model, authentication to trigger endpoints, per-case versus global scope,
behaviour when the endpoint is unreachable, audit visibility, and participant
versus external monitor.

## Per-Shape Integration

All four shapes share one convention: synchronous, in-process,
`name: str → Behaviour`; `SynchronousCallOut` raises `CallOutContractError` on a
`RUNNING` return (BT-18-011). Nothing suspends.

- **Evaluator** — receives case context and the decision; returns a structured
  answer that routes the BT. SSVC decision points (decision point + enumerated
  answers) are a natural input/output schema.
- **Retriever** — returns external facts. Where the case or the actor's own
  store already holds the fact, the tree reads it there and does not call the
  Retriever: a repeat call costs budget and can contradict the case
  (BT-18-039). Any cache of external data belongs to the capability
  implementation, which alone knows how fast its source changes, so where the
  cache lives, how long an entry stays fresh and what clears it are its choice;
  the call-out seam provides none (BT-18-029). A stale answer is the
  implementation's wrong answer, like any other. Caching is also how a slow
  lookup meets the BT-18-015 budget.
- **Composer** — produces a content artifact (notification body, advisory draft)
  written to its output port; it does not steer control flow unless it fails.
  Auto-send versus human review is deployment policy. A tree that carries
  content its caller supplied consults no Composer: the note trees under
  `vultron/core/behaviors/note/` take `note_content` from the trigger, and an
  actor that wants a drafted note drafts it before it calls the trigger. A
  Composer sits only at a step where the tree itself produces the artifact, such
  as `DraftAdvisoryArtifact`, `ReviseAdvisoryDraft`, `CreateFix` and `AssignId`
  (BT-18-030). Reusing prior advisory text is that Composer's own choice, not a
  composite with a Retriever: a composite exists only when the protocol needs
  the parts as separate answers.
- **Actuator** — causes an external side effect (e.g. `OnEmbargoExit`,
  `InjectParticipant`, `RemoveRecipient` hooks) and answers yes, no or error
  like every backend (ADR-0183). It acts on one target per call, keyed on an id
  the tree derives, so a re-run from holding repeats no side effect; a side
  effect it cannot confirm, or a rejected credential, is *error*. Its
  credentials and the systems it may reach are a deployment matter. A hook that
  cannot confirm promptly is an ask or call-in monitor.

## Trust / Execution Authority

Auto-execute versus advisory (human confirms) is orthogonal to shape: one
Evaluator can run in either mode by deployment configuration, so a call-out point
must handle both. Recording each recommendation with its outcome (accepted as-is
or overridden) is what lets an Evaluator earn promotion to auto-execute.

A capability's output never enters the case ledger as itself. The ledger holds
acts and case-file changes, not an actor's own observability content or a
decision that changes nothing (CLP-07-001, CLP-07-004, CLP-07-013), so a verdict
reaches it only through the act or change it leads to. The recommendation
records above, and the rationale behind a verdict, stay in the actor's own
store; otherwise one actor's private triage would replicate to every
participant. An actor that wants others to see its reasoning sends it, for
example as a Note.

## Participant Suggestion: One Port, Two Callers

The port is `vultron/core/ports/participant_suggestion.py`; the service every
caller goes through is `suggest_case_participants` in
`vultron/core/services/participant_suggestion.py`; the context and suggestion
models are in `vultron/core/models/participant_suggestion.py`.

- **"Who else should be in this case?" is one driven port, not a call-out
  capability.** A thin Retriever call-out wraps it for a tree, and a Sentinel
  calls the same service from outside, so one adapter serves both (BT-24-001,
  ADR-0186). A slow adapter that cannot meet the call-out budget is reachable
  only through the Sentinel.
- **Core narrows the case before the port sees it.** The port takes a
  core-owned suggestion context built by one core projection, because which
  embargoed information leaves the actor is a disclosure decision made once
  (BT-24-002, BT-24-003, BT-24-008). An adapter that wants more input changes
  that type.
- **The context is a case profile, not a subclass of the case.** Its fields are
  a ratchet-checked subset of the case's, nested objects included, and it builds
  itself with `from_case`. A subclass would inherit every future case field and
  fail open (BT-24-009). It carries the reports' content as evidence, since a
  report may name a vendor not yet in the case, and the participants (id and
  roles) as who is already included; current vendors hold VENDOR.
- **A suggestion is an identity with a reason.** Actor id, suggested role,
  rationale; no timing, because the receiver schedules invites from the
  invitee's embargo policy (BT-24-004, BT-24-006). Prefer over-suggesting
  (BT-24-005).
- **Name it a suggestion, not a discovery.** The answer is not definitive, and
  "actor resolution" is the URI-to-profile seam (ActorResolution).
- **A CSAF suggester is an adapter, not a port type.** It turns the suggestion
  context into CSAF for an outside service; core never depends on CSAF.
- **The demo answers from a declared table** (BT-24-007): no directory or
  recommender service is built. Retriever-plus-Evaluator search and affinity
  memory are implementation choices behind the port, not part of its contract.
  Affinity memory is the adapter's own store, under the same rule as a
  Retriever cache (BT-18-029), and never enters the case ledger.
- **The demo's adapter runs in the demo runner, not in an actor container.**
  `ask_who_else_belongs` (`vultron/demo/helpers/participant_suggestion.py`)
  copies the asker's replica into a private store, asks the core service with
  `StaticParticipantSuggester`, then fires the asker's `suggest-actor-to-case`
  trigger, as an operator-side Sentinel would. Reason: a table configured per
  container is per-actor config, which runs green in-process and red under
  Docker (`notes/testing-pitfalls.md`); in the runner both harnesses ask the
  same adapter (#6152). A scenario names its rows by cast member, one row per
  role, since actor ids are known only once the cast is seated.

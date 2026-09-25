---
status: accepted
date: 2026-09-18
deciders: Allen D. Householder
consulted: Claude Opus 5
informed: []
stakeholder_type: [project-contributor]
---

# The Capability Layer: Four Call-Out Shapes, Core-Declared Typed-Port Contracts, and Sentinel as a Call-In Pattern

## Context and Problem Statement

ADR-0024 named five capability shapes and ADR-0025 established the factory
injection seam that answers a call-out point. Between them they left the middle
tier of the three-level taxonomy — the **capability** — without a formal
definition, and three Ideas were filed against that gap:

- **#2452** — what must a named capability define?
- **#2453** — how is a capability implementation invoked at runtime?
- **#2454** — should the shape class names in the codebase be renamed?

Planning group G07 (CONCERN-2835) took all three together, on the premise that
answering them separately would produce three inconsistent answers. Reading the
code first changed what the questions were.

### The calling convention was already decided, by G01

Issue #2453 listed four candidates: synchronous HTTP, async callback with the
tree suspended, queue-based dispatch, and an in-process callable. One of them was
already impossible and already guarded.

ADR-0080 (planning group G01) established that nothing in Vultron suspends: the
bridge busy-loops on a root `RUNNING` until it exhausts `max_iterations` and then
fails opaquely, and `finally: bt.shutdown()` discards the tree at the end of every
invocation. BT-18-011 turned that into an enforced contract at the call-out seam
specifically — `SynchronousCallOut`
(`vultron/core/behaviors/call_out/guard.py`) is applied to every factory a bundle
hands out, in `CallOutBundle.__post_init__`, and raises `CallOutContractError` on
a `RUNNING` return. A static ratchet covers in-repo nodes.

So the convention is settled: **uniform across shapes, synchronous, in-process,
`name: str → Behaviour`**. The per-shape variation #2453 anticipated survives only
for Sentinel, which is not invoked by a tree at all.

### What #2453 was actually pointing at

Two real questions remained underneath it.

The first is a **classification** question, and ADR-0080 had already hit it from
the other side: it amended ADR-0076 because an approval gate had been modelled as
an Evaluator call-out, and *"at the moment of asking no answer exists and an
Evaluator can therefore only ever answer no."* The distinction — answerable now by
a service the actor runs, versus requiring a decision from another actor in the
case — decides whether something is a call-out point at all. It was documented as
prose in `docs/topics/capability_model/index.md` and was normative nowhere.

The second is **latency**. The guard forbids `RUNNING` but says nothing about a
backend that simply blocks. `docs/howto/wire_capability.md` invites implementers
to call an external service from `update()`, and the pipeline runs under FastAPI
`BackgroundTasks`, so a slow backend stalls a worker with no diagnostic.

### The contract lives in the wrong layer, and the default cannot honour it

BT-18-002 (MUST) requires a backend to write all declared output keys when it
returns SUCCESS, and MUST NOT return SUCCESS without them. `AlwaysSucceed`
(`vultron/core/behaviors/call_out/nodes.py`) returns SUCCESS and writes nothing.
It is the DETERMINISTIC default — which BT-23-001 makes the default for every
tree builder, test, and demo, and which BT-23-008's rationale calls *"the
production-usable happy-path backend a real actor uses before a capability
implementation is wired in."*

It cannot honour the contract, because the only machine-readable form of the
contract is an `output_keys` dict on a mixin in `vultron/demo/fuzzer/`, which core
must not import (BTND-04-002; BT-16-001 is why the probabilistic nodes live
there). The rest of the contract is docstring prose.

Measured at the time of this decision:

| | Count |
|---|---|
| Core DETERMINISTIC factory fields | 65 |
| …defaulting to a bare `_always_succeed` | 49 |
| …defaulting to a bare `_always_fail` | 13 |
| …defaulting to `_require_case_owner_approval` (the BT-23-012 gates) | 2 |
| …wired to a contract-honouring backend | **1** |
| Capabilities declaring non-empty output keys | 60 (45 Evaluator, 9 Composer, 6 Retriever) |

The two halves of that table count different things — bundle *fields* and
declared *capabilities* — and are not a clean cross-tabulation: some fields answer
capabilities that produce no data (Actuators, binary Retrievers), and some
declaring capabilities have no bundle field at all, because the tree that would
have consulted them was removed (`report_to_others`, ADR-0047/#1848). The
load-bearing figure is the last-but-one row: exactly one field resolves to a
backend that writes what its capability declares.

That single exception, `_DeterministicPrioritizePublicationIntents`, is the
familiar shape of this project's recurring problem: the mechanism exists, built
by hand, once.

The consequence is silent rather than loud. Core guards the read
(`required=False`), so `ShouldPublishFix` reads a missing
`publication_intent_decision`, returns FAILURE, and the arm no-ops. In
DETERMINISTIC mode every data-gated arm quietly does nothing — inverting the
stated premise of BT-23-002 and BT-23-007, which chose `AlwaysSucceed` *"so that
deterministic demo scenarios make forward protocol progress."* (BT-23-006 is not
part of that group: it selects `AlwaysFail`, for a different reason.) The ceiling
rule was written for boolean call-outs and silently generalised to data-producing
ones.

The one place a test guards this is the one place the mechanism was built:
`test_publication_tree.py` carries a regression test asserting that the
DETERMINISTIC bundle *does* write `PublicationIntentDecision`, *"Without this
write, all three arms silently take the Inverter-skip path."* That test passes
only because `_DeterministicPrioritizePublicationIntents` exists. No equivalent
guard exists for any other data-producing capability, so for the rest the gap is
unobserved rather than caught.

The blast radius is currently latent: `create_publication_tree` and
`create_acquire_exploit_strategy_tree` have no callers outside tests.

### The mechanism for a machine-readable contract already exists

ADR-0044 adopted py_trees typed ports as *"the standard base for all nodes in
`vultron/core/behaviors/`"*, with `INPUT_PORTS` / `OUTPUT_PORTS` as the
single source of truth for a node's blackboard contract and runtime type checks
on both read and write. **51 core files declare typed ports. No call-out backend
does.** #2452 was not asking for a new artifact; it was asking why call-out
points never adopted ADR-0044.

### Sentinel shares none of the machinery

Every rule that makes the capability layer work applies to four shapes and
explicitly not to the fifth:

| | Evaluator / Retriever / Composer / Actuator | Sentinel |
|---|---|---|
| `CallOutBackendFactory` | yes | no |
| Domain bundle field | yes | no |
| Blackboard contract | yes | none |
| `SynchronousCallOut`, BT-18-011 | yes | not applicable |
| Ceiling/floor rule | yes | not applicable |
| Surface | call-out | call-**in** |

BT-18-006 exists solely to stop authors misclassifying call-outs as Sentinels.
`SentinelCallOutPoint` and its three subclasses are dead code that contradicts
the definition — py_trees Behaviours carrying a `success_rate`, wired into no
bundle and instantiated only by their own unit tests
(`test/demo/fuzzer/test_call_out_point.py`), while `CheckNoNewDeploymentInfoNode` reads a
blackboard flag documented as written by a Sentinel that never runs. Annex G even
assigns Sentinel a *"returns SUCCESS/FAILURE… used as a precondition guard"*
contract, which is precisely the call-out framing it is not.

Meanwhile the real pattern is well attested. ADR-0080 gave it a job — a watcher
calling the `reap-expired-asks` trigger (ASK-05-002) — and all four Sentinel Ideas
(#1845, #1856, #1893, #1943) share one structure: watch a condition and decide for
themselves when to act on it.

## Decision Drivers

- Three Ideas each asked for a cross-cutting answer; giving them three separate
  answers is the failure mode the grouping existed to prevent
- A MUST-level requirement (BT-18-002) is violated by the default backend for
  all but one data-producing capability, and cannot be satisfied at all while the
  contract lives in a layer core may not import
- A decision already taken (ADR-0044) covers the gap, so a new registry would be
  a second mechanism for a solved problem
- Sentinel's every distinguishing property is "unlike the other four", and its
  in-code representation contradicts its own definition
- The published vocabulary (glossary, Annex G, `docs/topics/`) is load-bearing for
  external implementers, so a taxonomy change costs a real rewrite and must be
  worth it
- A catalog that no test can check decays into confident wrong answers, which is
  what the existing 44-entry docs catalog is on track to do

## Considered Options

### For the capability declaration (#2452)

1. **Typed ports in core** — the capability declares its contract via ADR-0044
   `INPUT_PORTS` / `OUTPUT_PORTS` on a core-owned declaration.
2. **A new declarative capability registry** — one `Capability` record per
   capability with a stable ID, shape, domain, and input/output schema, which
   bundle fields reference.
3. **Keep docstrings, add a ratchet** — leave the contract as prose plus the
   simulation-layer `output_keys` dict, and add a test that fails when the bundle
   fields, fuzzer nodes, and docs catalog disagree.

### For Sentinel

1. **Keep five shapes, split the spec** — Sentinel stays named as a shape but
   gets its own call-in contract.
2. **Demote Sentinel out of the taxonomy** — four call-out shapes; Sentinel
   becomes a call-in integration pattern under Agentic Participants (#2450).
3. **Leave Sentinel untouched** and spec only the four call-out shapes.

### For the shape base classes (#2454)

1. **Move to core and rename** to the capability vocabulary.
2. **Move to core, keep the names.**
3. **Delete the mixins**; shape becomes metadata rather than a class hierarchy.

## Decision Outcome

### 1. A capability declares its blackboard contract with ADR-0044 typed ports, in core

<a id="core-declared-typed-port-contract"></a>

Chosen: **typed ports in core**. The capability declaration is core-owned and
machine-readable, so `AlwaysSucceed` can read it, BT-18-002 becomes testable, and
the docstring contract becomes descriptive rather than the only authority.

Option 2 was rejected as a second mechanism for a problem ADR-0044 already
solved — and it would have to duplicate the type information typed ports already
carry and enforce. Option 3 was rejected because it leaves the defect in place:
no ratchet over prose lets `AlwaysSucceed` honour a contract it cannot read.

Structural discovery follows from this, answering #2452's catalog question: the
enumeration of capabilities is derived from the core declarations, not maintained
by hand. The docs catalog is generated from or ratcheted against them.

### 2. The calling convention is uniform, synchronous, and in-process

<a id="uniform-synchronous-in-process-convention"></a>

Chosen: **adopt ADR-0080's primitive rather than define a parallel one.** All
four call-out shapes share one convention — `CallOutBackendFactory`,
`name: str → Behaviour`, answering within a single tick with SUCCESS or FAILURE.
This ADR adds no new mechanism here; it records that #2453's question was
answered by G01 and closes it.

### 3. Call-out point versus protocol ask is a normative classification rule

<a id="call-out-versus-protocol-ask-rule"></a>

A question that a service the actor itself runs can answer within a tick is a
**call-out point**. A question that requires a decision from another actor in the
case is a **protocol ask** (ADR-0080): the actor emits the request, terminates
successfully, and the reply starts new work. An action with no representable
not-yet state is refused rather than asked about (ASK-02-005).

Modelling an ask as a call-out point produces a gate that can only ever answer
no, which is the defect ADR-0080 found in ADR-0076. The rule existed as prose in
`docs/topics/capability_model/index.md`; it becomes normative so a future author
applies it when adding a seam rather than discovering it by audit.

### 4. A call-out backend's answer is time-bounded, and the bound is configuration

<a id="bounded-configurable-call-out-latency"></a>

A backend MUST answer within a bounded budget and MUST NOT perform unbounded
blocking I/O in `update()`. Work that cannot meet the budget is not a call-out
point — it is a protocol ask or a call-in monitor.

The **spec asserts that a bound exists and is configurable; it does not fix the
number.** The distinction that matters is **wire visibility**, not
configurability. An ask deadline travels on the wire in the AS2 `endTime` field, so
both parties must read the same value (ASK-03-004); a call-out budget is local to
one actor and observable by nobody else, so two deployments choosing different
values is not divergence. Both are actor configuration — ask deadline durations
are `ActorConfig`-configurable too (ASK-03-005) — which is why the contrast has to
be drawn on visibility rather than on where the number is set. `ActorConfig`
(`vultron/config/actor.py`) already carries `timedelta` settings
(`min_rsvp_window`, `default_rsvp_window`) and is layer-neutral, so it is the home
for this one as well.

The guard is a sibling of `SynchronousCallOut`, applied at the same place.
Implementation must state honestly whether it *interrupts* an overrunning backend
or merely *detects* the overrun after the fact: a py_trees tick is synchronous, so
interruption requires running the backend off the ticking thread.

### 5. Sentinel is demoted out of the capability-shape taxonomy

<a id="sentinel-demoted-to-call-in-pattern"></a>

Chosen: **four call-out capability shapes.** Sentinel is reclassified as a
**call-in integration pattern**, and its design work belongs to the Agentic
Participants epic
(#2450), where an independently-acting process — with its own schedule, its own
credentials, and possibly its own protocol identity — belongs.

This partially supersedes ADR-0024: only its enumeration of five shapes. ADR-0024
remains the authority for "call-out point" as the canonical term, the three-level
taxonomy, boolean-external-queries-are-Retrievers, the exclusion of
message-driven responses, and the deferral of Orchestrator.

BT-18-006 survives and is strengthened — with Sentinel no longer a call-out
shape, a synchronous on-demand external query has no competing classification at
all. ADR-0047's decision (party discovery belongs to an external monitor rather
than an inline tick-driven BT loop) is unaffected; only its vocabulary changes,
so it is revised in place.

The four Sentinel Ideas were checked against this before deciding, and the
demotion fits them better than the shape framing did: #1845 (threat feed →
`Add(ParticipantStatus)`), #1856 (close readiness → notify the Case Owner), #1893
(embargo timer → `terminate_embargo`), and #1943 (active-embargo review) all
decide for themselves when to act. None needs a call-out node, a blackboard
contract, a bundle field, or a factory.

#### The discriminator is who initiates, not where the information comes from

It is tempting to define a Sentinel as the shape that reads *external*
information. That is wrong, and the error matters, because a Sentinel may be a
**case participant** — an Actor admitted through the ordinary Invite/Accept path,
most naturally holding `CVDRole.OBSERVER`, the base role with no
vendor-fix-deployment obligations (ADR-0057, CM-25). Such a Sentinel receives
`Announce(CaseLedgerEntry)` like any participant, so the condition it monitors can
be **the case's own state**, reached through ordinary replication rather than an
outside feed. Two of the four Ideas already assume this: #1856 observes case state,
and #1845's title has its monitor *posting `Add(ParticipantStatus)` to the case*.

So the real discriminator is **who initiates**. A capability is consulted: the
protocol reaches a call-out point, asks, and uses the answer within that tick. A
Sentinel is never consulted; it decides for itself that the moment has come and
acts. That is the call-in/call-out axis, and it holds regardless of whether the
information came from a threat feed or from the case ledger.

This also gives the demotion a stronger basis than "it shares none of the
machinery." A participant Sentinel holds protocol identity, a roster seat, a role,
and a case replica, and it acts by emitting ordinary protocol messages. That is a
**peer**, not an interface contract at a BT seam — which is the Agentic
Participants concept precisely, and why #2450 is the right home.

#### Two deployment shapes, with different protocol visibility

The distinction is worth naming, because it changes what the case can see:

| | Participant Sentinel | Operator-side Sentinel |
|---|---|---|
| Case identity | an Actor on the roster, typically `CVDRole.OBSERVER` | none — not a participant |
| Sees case state by | `Announce(CaseLedgerEntry)` replication | whatever its host actor already knows |
| Acts by | emitting ordinary protocol messages (`Note`, `Add(ParticipantStatus)`) | calling its host actor's trigger endpoints |
| Visible to other participants | yes — its observations and actions replicate | no — the resulting messages appear to come from the host actor |
| Admission | Invite / Accept | deployment credentials |

Neither is preferred in general. A threat-intelligence monitor that should be
*accountable* to the case wants the participant form; an embargo timer that is
merely part of how one organisation operates its own actor wants the operator-side
form. The choice is a protocol-visibility decision, and the Sentinel design work
under #2450 owes an answer per monitor rather than one answer for all of them.

One terminology hazard to record: the glossary lists "monitor" and "watcher"
among the aliases to *avoid* for the Observer role. "Sentinel" and "Observer"
must stay distinct — Observer is a **role a participant holds**, Sentinel is a
**behavioural pattern**, and a participant Sentinel is something that holds the
one by enacting the other.

### 6. The four shape base classes move to core and are renamed

<a id="shape-base-classes-move-to-core-and-are-renamed"></a>

Chosen: **move and rename.** The mixins move from
`vultron/demo/fuzzer/call_out_point.py` into
`vultron/core/behaviors/call_out/`, fix the typed-port *lifecycle* for their
shape, and are
renamed to the capability vocabulary (`EvaluatorCapability`, `RetrieverCapability`,
`ComposerCapability`, `ActuatorCapability`).

A shape base class cannot hold a *per-capability* contract, since many
capabilities share one shape — which is why the `output_keys` dict sits on the
concrete subclasses today. So decision 1 forces a **split** that this decision
only half completes: each named capability gets a core-owned declaration carrying
its own ports, and the probabilistic node that stands in for it stays in
`vultron/demo/fuzzer/` (BT-16-001) and binds to that declaration instead of
restating the contract. Core owns what the capability promises; the simulation
layer owns one way of pretending to keep it. The module layout for those
declarations is left to #3421.

Issue #2454 framed the rename as churn for vocabulary's sake and weighed it
against a permanent docs/code translation burden. That framing does not survive
decision 1:
the classes hold the only machine-readable contract, core needs to read it, and
BTND-04-002 forbids core importing from `vultron/demo/`. **The move is required
regardless, so the rename is a free rider** — the migration cost is the move, not
the word. The simulation layer re-exports the old names so the 81 existing
subclasses of the four retained shapes keep working.

`SentinelCallOutPoint` and its three subclasses are deleted rather than moved, per
decision 5.

### 7. The capability-layer requirements extend BT-18 and BT-23 in place

<a id="requirements-extend-bt-18-and-bt-23-in-place"></a>

No new spec file and no new prefix. BT-18-001…011 and BT-23-001…012 already *are*
the capability layer; giving it a second home would split the corpus and
invalidate cross-references from RSH-07, BT-20, and BTND-05.

### Consequences

- Good: BT-18-002 becomes enforceable for the first time, by a ratchet rather
  than by review
- Good: the DETERMINISTIC bundle can actually be what BT-23-008 claims it is — a
  production-usable happy-path default — instead of silently no-opping every
  data-gated arm
- Good: #2452, #2453, and #2454 close with one consistent answer, and two of the
  three close mostly by recording what the code already enforces
- Good: the capability catalog becomes derivable, so it can be ratcheted instead
  of decaying into confident wrong answers
- Good: no new mechanism is introduced. Typed ports, `CallOutBackendFactory`,
  bundles, the guard pattern, and `ActorConfig` all exist
- Neutral: the taxonomy is four shapes, not five. External-facing vocabulary
  (glossary, Annex G, `docs/topics/`, `docs/reference/vultron-taxonomy.md`)
  changes, and 118 lines across 31 files carry the capability-shape sense of
  "Sentinel"
- Neutral: Sentinel work is not cancelled, only rehomed *conceptually*. #1143 and
  the four Sentinel Ideas stay parented to #1147 — the G07 planning protocol
  (#2828) keeps members on their existing domain-epic parents — while their design
  questions become Agentic Participants questions (#2450). G14's premise ("define
  Sentinel once, instantiate four times") shifts from a shape contract to a
  call-in one
- Bad: making the remaining DETERMINISTIC defaults honour their contracts is a
  real behaviour change, affecting every bundle field whose capability declares
  output ports except the one already conforming. It is latent today (no live
  caller reaches a data-gated arm), but it will change what those arms do the
  moment one is wired
- Bad: the three `SentinelCallOutPoint` subclasses are deleted, which also deletes
  their unit tests in `test/demo/fuzzer/test_call_out_point.py`, and leaves the
  change-detection flags they were documented as writing without an attributed
  writer until #3424 resolves each one
- Bad: shape remains a class-hierarchy property rather than queryable metadata, so
  a capability's shape is still read by inspecting its base class

## Validation

- Every bundle field whose capability declares output ports resolves to a default
  that writes them; a ratchet fails if one does not
- A capability's declared output ports, not its docstring, are what a test reads
  to verify BT-18-002
- No `*CallOutPoint` shape class remains in `vultron/demo/fuzzer/` except as a
  back-compatible re-export, and none is imported by `vultron/core/`
- No class named `*Sentinel*` exists in the call-out taxonomy, and no blackboard
  flag is documented as written by a Sentinel
- The docs capability catalog is derived from or ratcheted against the core
  capability declarations, and the derivation fails on drift
- A call-out backend that exceeds the configured budget surfaces as an internal
  error naming the offending node, and the budget is read from configuration
  rather than a literal

## More Information

- **Partially supersedes ADR-0024** — only its five-shape enumeration; ADR-0024
  remains authoritative for its other five decisions
- **Amends ADR-0025** — decision 6 (shape base classes move to core and are
  renamed) and its ceiling/floor amendment (a data-producing capability's ceiling
  is a contract-honouring default, not bare `AlwaysSucceed`)
- **Revises ADR-0047 in place** — its decision stands; its Sentinel vocabulary
  changes to the call-in pattern
- **Builds on ADR-0044** — the typed-port mechanism it mandates, which call-out
  points had not adopted
- **Builds on ADR-0080** — the synchronous-answer invariant and the protocol-ask
  alternative, rather than defining a parallel async primitive
- Sources: CONCERN-2835 (planning group G07), IDEA-2452, IDEA-2453, IDEA-2454
- Specs: `specs/behavior-tree-integration.yaml` BT-18 and BT-23
- Notes: `notes/coordination-agents.md`, `notes/call-out-configuration.md`

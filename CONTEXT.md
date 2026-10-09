# Vultron

A federated, decentralized protocol for Coordinated Vulnerability Disclosure (CVD). Vultron
models multi-party CVD (MPCVD) as a set of interacting state machines — Report Management
(RM), Embargo Management (EM), and Case State (CS) — executed as Behavior Trees.

## Language

**Vulnerability (vul)**:
A flaw in a product or system that an attacker could exploit. Abbreviated *vul*, not *vuln*.
*Avoid*: vuln, bug (when the security-relevant sense is intended)

**Coordinated Vulnerability Disclosure (CVD)**:
A process in which a vulnerability is reported to the affected vendor(s), a fix is developed,
and public disclosure is timed to minimize harm.
*Avoid*: responsible disclosure, full disclosure (these have distinct meanings)

**Multi-Party CVD (MPCVD)**:
CVD involving more than two parties — typically a finder/reporter, a coordinator, and multiple
affected vendors.
*Avoid*: coordinated disclosure (too generic when multiple vendors are involved)

**Case**:
The unit of coordination in Vultron. A case captures all state and history for one MPCVD
engagement: participants, embargo status, report management state, and the canonical ledger.
*Avoid*: ticket, report (a report is what initiates a case, not the case itself)

**Actor**:
A participant in the Vultron protocol — a person, organization, or automated service that sends
and receives protocol messages. Actors have persistent identities (URIs) and maintain their own
DataLayer.
*Avoid*: user, agent (in the protocol-participant sense; see Capability Shapes below)

**Case Actor**:
A special-purpose service actor that owns the canonical ledger for a case, coordinates
participant invitations, and fans out protocol messages to all participants. Not a human.
*Avoid*: coordinator (the Case Actor is a protocol role, not an organizational role)

**Active participant / inert participant**:
A participant is *active* — entitled to case content — when it was seated by case
initialization or has accepted its stub Invite, and, only while an embargo is active, is
SIGNATORY to it. Every other participant record is *inert*: tracked, but sent no case
content (ADR-0114).
*Avoid*: treating roster membership as entitlement to case content

**Stub Invite / full-case Invite**:
The stub Invite (`Invite(Actor, VulnerabilityCaseStub)`) asks an actor to join and creates
its inert record; the full-case Invite (`Invite(Actor, VulnerabilityCase)`) later asks a
joined participant to judge the case (ADR-0114, ADR-0121).
*Avoid*: "the case Invite" without saying which

**Embargo**:
A time-limited agreement among case participants to withhold public disclosure of a
vulnerability until a specified date or condition.
*Avoid*: NDA, hold

**Embargo Register**:
The case's append-only list of every embargo ever proposed on it, each with its own
status (proposed, active, rejected, superseded, cancelled, terminated).
*Avoid*: embargo history (it is a record of status, not a log of events)

**Embargo Management (EM) state**:
The case-level embargo position (`NONE`, `PROPOSED`, `ACTIVE`, `REVISE`, `EXITED`). It is
computed from the Embargo Register, never set directly, and every change to it must
still be one of the EM state machine's transitions. Computing EM from the register adds
a layer under the EM state machine; it does not replace the machine.
*Avoid*: "EM has no transition table", "EM is just a view"

---

## Messages

Canonical definitions: `docs/reference/glossary.md` § Messaging and Protocol, which
also defines **Message Type** and **Protocol Shorthand** for the formal message set
(`RS`, `EP`, …).

**Wire activity**:
An ActivityStreams 2.0 (AS2) activity of a given shape, such as
`Offer(VulnerabilityReport)`, written with the literal AS2 type names a sender puts on
the wire.
*Avoid*: message type (that is the formal message set)

**Semantic type**:
What a receiver recognizes an incoming wire activity as, judged from its shape alone.
Not a Message Type: the two are many-to-many.
*Avoid*: meaning (use *occasion* for the sender's situation)

**Occasion**:
A situation in a case that a sender conveys with a particular wire activity, sometimes
narrowed by a distinguishing field value. One semantic type has one or more —
`Add(CaseStatus)` has three.
*Avoid*: meaning, use, event (an occasion is the sender's situation, not a received
event)

---

## Capability Shapes

Vultron's Behavior Trees include **call-out points** — locations where the protocol cannot
proceed automatically and must request input from an external party. Capability shapes are
abstract interface contracts that characterise how those call-out points interact with the
protocol.

**Call-out point**:
A location in a Vultron workflow where the protocol cannot determine the correct next action
on its own and must request input — a fact, a decision, or content — from an external party
(a human, a function, or an external system) before it can continue.
*Avoid*: decision point (reserved for SSVC scoring trees), touchpoint, integration point

**Capability shape**:
One of the four abstract interface contracts (Evaluator, Retriever, Composer, Actuator)
that characterises the interaction pattern between a call-out point and the protocol.
A capability shape does not prescribe the implementation — the implementation (function, human
workflow, LLM agent) is a deployment-time decision.
*Avoid*: Coordination Agent (retired; see ADR-0024); "the five shapes"; "Sentinel shape"
(Sentinel is a call-in pattern, not a shape — ADR-0097, BT-18-013)

**Capability**:
A specific named call-out point with its own blackboard contract (e.g., `EvaluateReportCredibility`).
A capability implements one capability shape for a particular domain context.

**Capability implementation**:
The factory backend fulfilling a capability at runtime. May be a Python function, a human
workflow, a rules engine, or an LLM agent — any callable that honours the blackboard contract.

The canonical capability shapes:

**Evaluator**:
A capability shape that is called by the protocol with a described situation and a set of
options, and returns a structured recommendation or decision. The output shapes what the
Behavior Tree does next.
*Avoid*: advisor, scorer (these are valid sub-types but not the canonical shape name)

**Retriever**:
A capability shape that is called with a query and returns structured facts from an external
source — vendor records, CPE entries, EPSS scores, threat intel, asset inventory, or similar.
Boolean/binary results (yes/no queries) are also Retriever capabilities. The Retriever fetches
what already exists; it does not generate new content.
*Avoid*: lookup, fetcher

**Composer**:
A capability shape that is called with context (case state, participants, prior decisions)
and generates a new content artifact — a notification draft, an advisory, a case summary, a
participant invitation. The Composer produces something that did not exist before.
*Avoid*: drafter, writer

**Actuator**:
A capability shape that receives a trigger and context, invokes an external system to cause a
side effect (notification dispatch, state write, queue mutation, API call), and returns SUCCESS
when the side effect is confirmed. Does not produce a content artifact on the blackboard.
*Avoid*: executor, dispatcher (these are valid sub-types but not the canonical shape name)

Not a capability shape:

**Sentinel**:
A **call-in integration pattern**, not a capability shape (ADR-0097, BT-18-013). A process
that monitors a condition and, when it is met, acts on its own initiative — calling a Vultron
trigger endpoint, or emitting protocol messages if it is itself a case participant. The
protocol never consults it, so it has no call-out point, no blackboard contract, and no
backend factory. The discriminator is *who initiates*, not whether the information is
external. Design work belongs to Agentic Participants (#2450).
*Avoid*: watcher, monitor (as standalone names); "Sentinel capability"; "Sentinel shape"

---

## SSVC

**SSVC (Stakeholder-Specific Vulnerability Categorization)**:
A decision-support framework for vulnerability prioritization. SSVC defines decision points,
enumerated answer sets, and decision tables that reduce multiple inputs to a prioritization
outcome. Vultron reuses SSVC decision-point structures to represent process decisions at
call-out points.
*Avoid*: CVSS (a scoring system, not a decision framework)

**Decision point** (SSVC sense):
Within an SSVC tree, a specific question with an enumerated answer set that contributes to a
prioritization outcome. Do not use this term for Vultron workflow call-out points more broadly.
*Avoid*: (using this term outside the SSVC context)

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

**Embargo**:
A time-limited agreement among case participants to withhold public disclosure of a
vulnerability until a specified date or condition.
*Avoid*: NDA, hold

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
One of the five abstract interface contracts (Sentinel, Evaluator, Retriever, Composer,
Actuator) that characterises the interaction pattern between a call-out point and the protocol.
A capability shape does not prescribe the implementation — the implementation (function, human
workflow, LLM agent) is a deployment-time decision.
*Avoid*: Coordination Agent (retired; see ADR-0024)

**Capability**:
A specific named call-out point with its own blackboard contract (e.g., `EvaluateReportCredibility`).
A capability implements one capability shape for a particular domain context.

**Capability implementation**:
The factory backend fulfilling a capability at runtime. May be a Python function, a human
workflow, a rules engine, or an LLM agent — any callable that honours the blackboard contract.

The five canonical capability shapes:

**Sentinel**:
A capability shape that monitors a condition and, when the condition is met, calls a Vultron
trigger endpoint to initiate a protocol action. Sentinels are proactive — they loop or watch;
they are not called by the protocol. A Sentinel has no BT call-out point.
*Avoid*: watcher, monitor (as standalone shape names)

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

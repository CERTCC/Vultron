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
*Avoid*: user, agent (in the protocol-participant sense; see Coordination Agent below)

**Case Actor**:
A special-purpose service actor that owns the canonical ledger for a case, coordinates
participant invitations, and fans out protocol messages to all participants. Not a human.
*Avoid*: coordinator (the Case Actor is a protocol role, not an organizational role)

**Embargo**:
A time-limited agreement among case participants to withhold public disclosure of a
vulnerability until a specified date or condition.
*Avoid*: NDA, hold

---

## Coordination Agents

Vultron's Behavior Trees include **call-out points** — locations where the protocol cannot
proceed automatically and must request input from an external party. Coordination agents are
the capabilities that answer those call-out points.

**Call-out point**:
A location in a Vultron workflow where the protocol cannot determine the correct next action
on its own and must request input — a fact, a decision, or content — from an external party
(a human, an agent, or an external system) before it can continue.
*Avoid*: decision point (reserved for SSVC scoring trees), touchpoint, integration point

**Coordination agent**:
An external capability — a skill, a set of skills with light orchestration, or a human — that
answers a call-out point. A coordination agent has a narrow responsibility, explicit inputs,
and explicit outputs. No single coordination agent is responsible for managing an entire case.
*Avoid*: agent (alone; too broad), uber-agent

The four canonical shapes a coordination agent can take:

**Sentinel**:
A coordination agent that monitors a condition and, when the condition is met, calls a Vultron
trigger endpoint to initiate a protocol action. Sentinels are proactive — they loop or watch;
they are not called by the protocol.
*Avoid*: watcher, monitor (as standalone agent names)

**Evaluator**:
A coordination agent that is called by the protocol (or by an orchestrator) with a described
situation and a set of options, and returns a structured recommendation or decision. The output
shapes what the Behavior Tree does next.
*Avoid*: advisor, scorer (these are valid sub-types but not the canonical type name)

**Retriever**:
A coordination agent that is called with a query and returns structured facts from an external
source — vendor records, CPE entries, EPSS scores, threat intel, asset inventory, or similar.
The Retriever fetches what already exists; it does not generate new content.
*Avoid*: lookup, fetcher

**Composer**:
A coordination agent that is called with context (case state, participants, prior decisions)
and generates a new content artifact — a notification draft, an advisory, a case summary, a
participant invitation. The Composer produces something that did not exist before.
*Avoid*: drafter, writer

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

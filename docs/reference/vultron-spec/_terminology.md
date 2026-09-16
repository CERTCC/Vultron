## 2. Terminology [N/I]

Vultron gives several ordinary Coordinated Vulnerability Disclosure (CVD) words a
narrower meaning than they carry in general use. The tables in this section state
the protocol meaning of each term. Where the protocol meaning differs from common
usage, the protocol meaning applies throughout this specification.

This section is the authoritative source for the terms it defines, including the
role enumeration in [§2.2](index.md#22-roles). An implementation derives its
vocabulary from this specification.

### 2.1 Actors, Participants and Cases

These four terms are ordered deliberately: each builds on the one before it.

| Term | Definition |
|---|---|
| **Vulnerability** | A weakness in an information system that could be exploited to cause harm. Vulnerabilities are the subject of every Vultron case. |
| **Report** | A document describing a specific vulnerability, submitted to initiate coordination. |
| **Case** | The coordination context around a specific vulnerability: the participants, the shared state, the messages exchanged, and any embargo agreement. The case is the unit of Vultron protocol activity. |
| **Actor** | An identity in the protocol, named by a URI. An actor may be an organization, a person, or a service. Actors exist independently of any case. |
| **Participant** | An actor that has joined a specific case. The case holds a `CaseParticipant` record for each participant, associating that actor with the roles it holds and the state it owns. An actor is a participant *in a case*; the same actor may participate in many. |

### 2.2 Roles

A role is a position held within a case. It determines what a participant is
obliged to do and which transitions it is authorized to cause. Roles are granted
through the case's authority chain ([§11.1](index.md#111-role-assignment-n)), not
claimed. A participant may hold several at once.

Roles fall into two categories, which
[§12.3](index.md#123-role-taxonomy) develops further.

**Process roles** describe what an actor *does* in a case:

| Role | Definition |
|---|---|
| **Reporter** | A participant that submitted the report. The protocol is concerned with who reported the vulnerability, not who discovered it; a discoverer who reports holds the Reporter role. |
| **Vendor** | A participant that produces a product containing the vulnerability and is responsible for developing a fix. |
| **Coordinator** | A participant that facilitates multi-party coordination without being responsible for developing a fix itself. |
| **Deployer** | A participant that deploys a vendor's fix to systems it operates. Distinct from Vendor: producing a fix and applying it are separate acts. |
| **CVE Numbering Authority (CNA)** | A participant authorized to assign CVE IDs directly, rather than delegating assignment to an external service. Orthogonal to the other process roles and commonly held alongside Coordinator or Vendor. |
| **Observer** | A participant with no obligation to drive vendor/fix/deploy transitions. An Observer still tracks case state, is subject to embargo consent, and may report observations about the world. |

**Protocol authority roles** describe what an actor *controls* in the protocol
itself:

| Role | Definition |
|---|---|
| **Case Owner** | The party whose disclosure decision the case exists to serve. It decides who is admitted, which roles they hold, and whether embargo terms are accepted or torn down. Case ownership is never delegated, though it may be transferred ([§11.3](index.md#113-case-ownership-transfer-n)). |
| **Case Manager** | The participant that writes the canonical case ledger and relays case-scoped messages, acting on the Case Owner's behalf. It is the case's single-writer authority ([§5.4.1](index.md#541-single-writer-authority)). The Case Owner may delegate this role. |

!!! note "Observer names two different things"
    *Observer* is used in this specification for the process role defined above,
    and also as the name of the minimum conformance capability set that **every**
    participant must provide ([§12.2](index.md#122-capability-sets)). The reuse is
    deliberate — the capability set is named after the least-privileged role — but
    the two are not the same kind of thing. A role is a position in a case; a
    capability set is a property of software
    ([§12.3.3](index.md#1233-roles-and-capability-sets-are-independent)).

!!! note "Informative: the CASE_MANAGER role and the actor that holds it"
    Authority over a case follows the Case Manager **role**. It does not follow
    any actor's name, URI, or hosting location. Normative text in this
    specification therefore names the authority *the CASE_MANAGER*, meaning
    whichever participant currently holds the role.

    The reference implementation happens to satisfy the role with an automated
    software actor it labels a *case actor*, provisioned by a *case actor
    service*. Those are implementation labels with no protocol meaning. An
    implementation MUST NOT infer authority from them.

!!! note "Informative: Finder is not a protocol role"
    Earlier CVD models distinguish the *finder* of a vulnerability from its
    *reporter*. Vultron does not: nothing in the protocol depends on who
    discovered the vulnerability, so an actor that discovers and reports holds the
    Reporter role. The discoverer's identity may be recorded in the report
    content or in a case note.

### 2.3 Protocol Objects and Messages

| Term | Definition |
|---|---|
| **Activity** | The wire form of a Vultron message: an ActivityStreams 2.0 Activity. Every message this specification describes is carried as an Activity ([§5](index.md#5-syntactic-layer-wire-format-n)). |
| **Message** | A protocol operation sent from one actor to another. A message states that something has happened; it is not an instruction to the recipient. |
| **Message type** | One of the operations the protocol defines, each named by a protocol shorthand. `RS` (Report Submission) and `EP` (Embargo Proposal) are message types ([§4](index.md#4-semantic-layer-message-meanings-n)). |
| **Protocol shorthand** | The two-letter code naming a message type by its meaning rather than its wire form — `RS`, `EP`, `CV`, and so on. Introduced in [§4](index.md#4-semantic-layer-message-meanings-n) and mapped to wire forms in [§4.7](index.md#47-shorthand-wire-form-mapping). A reader meeting a shorthand before [§4](index.md#4-semantic-layer-message-meanings-n) may treat it as an opaque label. |
| **Case stub** | A minimal description of a case, carrying enough for an invited actor to decide whether to join and no vulnerability detail. Sent with an invitation, before the invitee has been admitted ([§11.2](index.md#112-invitation-and-acceptance-n)). |
| **Case ledger** | The case's authoritative, append-only history. The CASE_MANAGER is its only writer, and every participant holds a replica built from what the CASE_MANAGER sends. |
| **`CaseLedgerEntry`** | One entry in the case ledger. Each entry records one accepted change, carries a timestamp assigned by the CASE_MANAGER, and is hash-chained to its predecessor so a participant can tell whether it holds the entries in order and without gaps. |
| **`ParticipantStatus`** | A participant's report about its own state, or its observation about the world. A `ParticipantStatus` is a **claim**: any participant may write one, and writing one does not change the case's state ([§10.3](index.md#103-status-adoption-the-two-seam-model)). |
| **`CaseStatus`** | The case's shared state — its embargo state and what is publicly known. A `CaseStatus` is **canonical**: only the CASE_MANAGER writes it, and it changes only when a claim is adopted ([§10.3](index.md#103-status-adoption-the-two-seam-model)). |
| **Channel** | The path a message travels. In Vultron the delivery path is inbox to inbox, and case-scoped messages route through the CASE_MANAGER ([§5.4.2](index.md#542-routing-topology)). |

### 2.4 State, Embargo and Disclosure

| Term | Definition |
|---|---|
| **State** | The current value of one state machine. Always qualified in this specification — RM state, embargo state, case state — because the unqualified word is ambiguous. |
| **Transition** | A change from one state to another. |
| **Track** | To maintain a local value for a state machine and update it as incoming messages report transitions. Every participant tracks all five machines ([§12.2](index.md#122-capability-sets)). |
| **Drive** | To cause a transition that the participant's roles authorize, and announce it so the other participants learn of it. Which transitions a participant may drive depends on its roles ([§12.4](index.md#124-role-specific-normative-requirements)). |
| **Embargo** | A time-bounded agreement among the participants of a case not to disclose the vulnerability publicly before an agreed point. Tracked for the case by the embargo state machine ([§7](index.md#7-embargo-management-em-state-machine-n)) and per participant by embargo consent ([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)). |
| **Teardown** | Ending an active embargo. The CASE_MANAGER performs the teardown and records it; a participant may report that it intends to exit, or propose an earlier end, but does not end the case's embargo itself ([§10.2](index.md#102-embargo-revision-and-termination-cascades)). |
| **Publication** | A deliberate act by a participant that makes vulnerability information publicly available. Publication is something a participant *does*, and the embargo constrains when a participant may do it. |
| **Public awareness** | The condition of the vulnerability being known outside the case, however that came about. Public awareness may arise with no participant publishing anything: an attacker may discover the vulnerability independently, a commit may reveal it, or a non-participant may write about it. |

!!! warning "Publication and public awareness are not the same thing"
    Vultron governs **publication** — what a participant may deliberately
    disclose, and when. It cannot govern **public awareness**, which is a fact
    about the world that no participant controls.

    The distinction is load-bearing because most of the protocol's disclosure
    logic keys off whether information *is* public, not off how it became public.
    An embargo that is overtaken by an independent leak is over as surely as one
    ended by agreement, and the case state records Public Aware either way
    ([§8.2](index.md#82-pxa-public-aware-exploit-public-attacks-observed)).

!!! info "See also"
    - [Glossary](../glossary.md) — project-wide terminology, including terms
      outside this specification's scope
    - [Formal Protocol Messages](../formal_protocol/messages.md)

---

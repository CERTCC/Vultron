### 13.2 Capability Sets

A capability set is a named group of the obligations that an implementation takes on.
Where an obligation is a protocol requirement, this section renders it as a callout; the others link the section that describes them.
Three are defined.
Case Observer is the set that every participant provides.
Case Decision and Case Hosting add the requirements of deciding for a case and of running one.
The **Case** prefix marks each as a capability set — a property of software — distinct from the similarly-named roles it serves.

Most of what a capability set requires is expressed as maintaining a state machine, so that phrase needs pinning down first.

!!! note "What 'implement a state machine' means"
    Implementing a state machine has two components:

    1. **Track**: maintain a local value for the machine, and update it as incoming messages report transitions.
    2. **Drive**: cause a transition that the participant's roles authorize, and announce it so the other participants learn of it.

    The two are separate obligations.
    A participant that tracks but does not drive leaves the others to discover its state changes some other way.
    A participant that drives but does not track acts on case state it does not know.
    Which transitions a participant can drive depends on its roles ([§13.4 Role-Specific Normative Requirements](../conformance.md#134-role-specific-normative-requirements)); every participant tracks.

{% include-markdown "../includes/_dimensions-vs-machines.md" %}

#### Case Observer capability set

The Case Observer capability set is the participation floor.
Every actor that participates in a Vultron case provides it, because the Observer role is the base role and every other role adds to it.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-25-001"))
```

There is no sub-Observer participation level.
An actor that accepts a case invitation has committed to Observer behavior from that point: it tracks state and reports its own transitions.

A Case Observer implementation maintains all five state machines — **RM, EM, PEC, VFD, PXA** — for itself.
It holds a current value for each, and it drives the transitions that its roles authorize.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-03-001", "CM-03-002", "CM-03-005", "CM-03-008"))
```

It also tracks the states of the other participants in the case, to inform its own decisions.
That is a recommendation rather than a requirement, because the protocol does not depend on any participant holding perfect information about the others.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("VP-01-001", "VP-01-002", "VP-01-003"))
```

When its own state changes, the protocol recommends that it send the message for the transition.
When it is told of another participant's transition, it updates its local state.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("VP-03-012", "CM-04-001", "CM-04-002", "CM-04-004"))
```

It takes part in embargo negotiation: it answers an `Invite(EmbargoEvent)` addressed to it, and the CASE_MANAGER records its consent or refusal in PEC ([§9 Participant Embargo Consent (PEC) State Machine](../tracking-models.md#9-participant-embargo-consent-pec-state-machine-n)).

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("EP-09-003", "EMB-15-004"))
```

It sends every case-scoped message to the CASE_MANAGER ([§10.2 Routing Topology](../interactions.md#102-routing-topology)).

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("PCR-08-001", "PCR-08-005"))
```

It can report PXA observations ([§13.4.2 Participant-Agnostic CS Transitions (PXA)](../conformance.md#1342-participant-agnostic-cs-transitions-pxa)).
It has no VFD drive obligations unless one of its roles adds them.

!!! note "Why there is no sub-Observer level"
    A monitoring-only actor might seem to need message parsing and nothing else.
    Two things rule that out.
    An actor that does not track its own PEC state cannot take part in embargo negotiation, and the CASE_MANAGER decides what to send it on the basis of that state — so an untracked participant cannot be reliably served.
    An actor that does not track RM has no basis for evaluating case status.
    Meaningful use of Vultron data requires the full Observer set.

    The protocol governs what the CASE_MANAGER **sends**, not what a recipient does with information it already holds.
    Vultron gates dissemination; it cannot constrain display.

    A parse-only tool is not a case Participant: it holds no `CaseParticipant` record and no case is obliged to deliver anything to it.

!!! note "Role-specific drive obligations"
    All Observer participants **track** all five machines.
    Which transitions a participant **drives** depends on its role extension set: a Vendor drives its own fix-ready transition, a Deployer drives its own fix-deployed transition, and any participant can report PXA observations.
    See [§13.3 Role Taxonomy](../conformance.md#133-role-taxonomy) and [§13.4 Role-Specific Normative Requirements](../conformance.md#134-role-specific-normative-requirements).

#### Case Decision capability set

The Case Decision capability set provides what the Case Owner role needs.
It is separable from the Case Hosting capability set.
It adds these to the Case Observer capability set:

- The Case Owner's own status reports are adopted without an approval step, because its updates are authoritative ([§11.3 Status Adoption: The Two-Seam Model](../interactions.md#113-status-adoption-the-two-seam-model)).
- The Case Owner decides the shared embargo: it activates and rejects embargo proposals for the case, and terminates the embargo in force.
- The Case Owner can transfer case ownership, by a proposal to the CASE_MANAGER ([§12.3 Case Ownership Transfer](../interactions.md#123-case-ownership-transfer-n)).

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-02-005", "MSM-07-008", "MSM-07-009", "CM-21-005"))
```

A human Coordinator typically provides the Case Decision capability set while a service actor provides Case Hosting.

#### Case Hosting capability set

The Case Hosting capability set provides what the CASE_MANAGER role needs.
It is separable from the Case Decision capability set.
It adds the following to the Case Observer capability set.

It holds the **CASE_MANAGER** role for each case it hosts, and so it is that case's single writer ([§10.1 Single-Writer Authority](../interactions.md#101-single-writer-authority)).

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-02-001", "CM-02-002", "BT-10-003", "BT-10-004"))
```

It keeps the canonical case ledger, and replicates each entry to the participants as `Announce(CaseLedgerEntry)`.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CLP-04-001", "CLP-04-004", "PCR-08-003"))
```

It runs multi-party case management: participant invitation and acceptance, role assignment and case ownership operations, each under the case's authorization rules.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-02-006", "PCR-08-008", "PCR-08-009"))
```

It applies the two-seam status adoption model, including the canonical-write-before-side-effects ordering ([§11.3 Status Adoption: The Two-Seam Model](../interactions.md#113-status-adoption-the-two-seam-model)).

It delivers full case content only to a participant that passes the gate of [§9.7 Gating Full Case Delivery](../tracking-models.md#97-gating-full-case-delivery).

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("CM-10-004", "CM-10-005"))
```

!!! note "Ledger replication mechanics are specified separately"
    This specification states what the ledger is and that the CASE_MANAGER replicates it.
    One CASE_MANAGER holds exclusive write authority, and sends each entry to every participant actor.

    The mechanics of that replication — hash-chaining, gap detection and ordering guarantees — are specified in a companion Vultron Ledger Replication Specification, which is still in draft and is not yet published alongside this document.
    An implementation cannot demonstrate conformance to the replication mechanics from this document alone.
    The reasoning for splitting them is recorded in [ADR-0077](../../../adr/0077-ledger-replication-companion-spec.md).

    Distributed consensus among several case managers is a possible future extension and is out of scope here.

#### Named configurations

Common combinations of capability sets have names because they appear frequently in real deployments.
These names are informative; conformance claims use the full capability set list.

| Configuration | Capability sets | Roles |
|---|---|---|
| **Hosting Coordinator** | Case Observer + Case Decision + Case Hosting | Coordinator + Case Owner |
| **Self-coordinating Vendor** | Case Observer + Case Decision + Case Hosting | Vendor + Deployer + Case Owner |
| **Bug Bounty Platform** | Case Observer + Case Hosting | Case Manager (Case Decision optional) |

A Hosting Coordinator is a `type:service` actor that holds both `CASE_OWNER` and `CASE_MANAGER` roles.
It decides and executes without a separate human approval step for its own status updates.

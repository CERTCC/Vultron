### 12.2 Capability Sets

!!! note "What 'implement a state machine' means"
    Implementing a state machine has two components:

    1. **Track**: maintain a local value for the machine, and update it as
       incoming messages report transitions.
    2. **Drive**: cause a transition that the participant's roles authorize, and
       announce it so the other participants learn of it.

    The two are separate obligations. A participant that tracks but does not
    drive leaves the others to discover its state changes some other way. A
    participant that drives but does not track acts on case state it does not
    know. Which transitions a participant may drive depends on its roles
    ([§12.4](../index.md#124-role-specific-normative-requirements)); every
    participant tracks.

{% include-markdown "../includes/_dimensions-vs-machines.md" %}

#### Observer capability set

The Observer capability set is the participation floor.
**Every actor that participates in any Vultron case MUST implement it.**

There is no sub-Observer participation level. An actor that accepts a case
invitation has committed to Observer behavior from that point. It must track
state and notify others of its own transitions.

- MUST maintain all five state machines — **RM, EM, PEC, VFD, PXA** — for
  itself: it MUST hold a current value for each, and MUST drive the transitions
  its roles authorize
- SHOULD also track the states of the other participants in the case, to inform
  its own decisions. This is a SHOULD rather than a MUST because correct
  operation of the protocol MUST NOT depend on any participant holding perfect
  information about the others
- MUST send the messages appropriate to its claimed roles when its own state
  transitions occur
- MUST receive and update local state when notified of other participants'
  transitions
- MUST participate in embargo negotiation: responding to `Invite(Event)`, and
  recording consent or refusal via PEC
- MUST route all case-scoped messages through the CASE_MANAGER ([§5.4.2](../index.md#542-routing-topology))
- MAY report PXA observations; no VFD drive obligations unless a role extension
  set adds them

!!! note "Why there is no sub-Observer level"
    A monitoring-only actor might seem to need message parsing and nothing else.
    Two things rule that out. An actor that does not track its own PEC state
    cannot take part in embargo negotiation, and the CASE_MANAGER decides what to
    send it on the basis of that state — so an untracked participant cannot be
    reliably served. An actor that does not track RM has no basis for evaluating
    case status. Meaningful use of Vultron data requires the full Observer set.

    The protocol governs what the CASE_MANAGER **sends**, not what a recipient
    does with information it already holds. Vultron gates dissemination; it
    cannot constrain display.

    A parse-only tool is not a case Participant: it holds no `CaseParticipant`
    record and no case is obliged to deliver anything to it.

!!! note "Role-specific drive obligations"
    All Observer participants **track** all five machines. Which transitions a
    participant **drives** depends on its role extension set: a Vendor drives its
    own VFD transitions; a Reporter drives RM; any participant may report PXA
    observations. See [§12.3](../index.md#123-role-taxonomy) and [§12.4](../index.md#124-role-specific-normative-requirements).

#### Authority capability set

The Authority capability set defines Case Owner governance capabilities.
It is separable from the Hosting capability set.

- Observer capability set, plus:
- Status updates MUST be adopted without requiring an external approval gate
  (the Case Owner's own updates are authoritative)
- MUST be able to drive shared EM transitions
- MUST be able to transfer case ownership via the `Offer(VulnerabilityCase)` /
  `Accept` handshake

A human Coordinator typically holds Authority while a service actor provides Hosting.

#### Hosting capability set

The Hosting capability set defines Case Manager infrastructure capabilities.
It is separable from the Authority capability set.

- Observer capability set, plus:
- MUST hold the **CASE_MANAGER** role for each case it hosts, and therefore MUST implement the
  single-writer authority rules of [§5.4.1](../index.md#541-single-writer-authority)
- MUST maintain the authoritative canonical case ledger and replicate it to
  participants via `Announce(CaseLedgerEntry)`
- MUST implement multi-party case management: participant invitation,
  acceptance, role assignment, and case ownership operations
- MUST implement the two-seam status adoption model ([§10.3](../index.md#103-status-adoption-the-two-seam-model)), including the
  canonical-write-before-side-effects ordering
- MUST deliver full case content only when the [§9.7](../index.md#97-gating-full-case-delivery) gate is satisfied

!!! note "Ledger replication scope"
    The detailed replication mechanics (hash-chaining, gap detection, ordering
    guarantees) are specified in a companion document,
    `docs/reference/draft-vultron-replication-spec.md`, not in this specification. See ADR-0077. The single-hub / single-writer + fan-out model is the normative
    replication architecture: one CASE_MANAGER holds exclusive write authority and
    replicates entries to participant actors via `Announce(CaseLedgerEntry)`.
    Distributed consensus (a multi-node case manager cluster) is a future extension
    out of scope for this specification.

#### Named configurations

Common combinations of capability sets have names because they appear frequently
in real deployments. These names are informative; conformance claims use the
full capability set list.

| Configuration | Capability sets | Roles |
|---|---|---|
| **Hosting Coordinator** | Observer + Authority + Hosting | Coordinator + Case Owner |
| **Self-coordinating Vendor** | Observer + Authority + Hosting | Vendor + Deployer + Case Owner |
| **Bug Bounty Platform** | Observer + Hosting | Case Manager (Authority optional) |

A Hosting Coordinator is a `type:service` actor that holds both `CASE_OWNER`
and `CASE_MANAGER` roles. It decides and executes without a separate human
approval step for its own status updates.

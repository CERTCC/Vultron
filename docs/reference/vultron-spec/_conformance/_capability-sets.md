### 12.2 Capability Sets

!!! note "What 'implement a state machine' means"
    Implementing a state machine has two components:

    1. **Track**: maintain a local instance of the machine and update it when
       relevant protocol messages are received from other participants.
    2. **Drive**: send the appropriate protocol messages when *this participant's
       own* state transitions occur (per the "Avoid Surprise" principle).

    Every participant must both track and drive the machines relevant to their
    role. Tracking without driving means other participants are surprised by your
    state changes. Driving without tracking means you are unaware of the case
    state you are acting on.

#### Observer capability set

The Observer capability set is the participation floor.
**Every actor that participates in any Vultron case MUST implement it.**

There is no sub-Observer participation level. An actor that accepts a case
invitation has committed to Observer behavior from that point. It must track
state and notify others of its own transitions.

- MUST implement all five state machines: **RM, EM, PEC, VFD, PXA**
  (track and drive, per the definition above)
- MUST send the messages appropriate to its claimed roles when its own state
  transitions occur
- MUST receive and update local state when notified of other participants'
  transitions
- MUST participate in embargo negotiation: responding to `Invite(Event)`, and
  recording consent or refusal via PEC
- MUST route all case-scoped messages through the Case Actor ([§5.4.2](../index.md#542-routing-topology))
- MAY report PXA observations; no VFD drive obligations unless a role extension
  set adds them

!!! note "Why there is no sub-Observer level"
    A monitoring-only actor might seem to need only message parsing, with no
    state tracking required. But an actor that cannot track PEC cannot know what
    it is permitted to display. An actor that cannot track RM has no basis for
    evaluating case status. Meaningful use of Vultron data requires the full
    Observer set. A parse-only tool is not a case Participant: it holds no
    `CaseParticipant` record and no case is obliged to deliver anything to it.

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
- MUST act as or host a **Case Actor**, and therefore MUST implement the
  single-writer authority rules of [§5.4.1](../index.md#541-single-writer-authority)
- MUST maintain the authoritative canonical case ledger and replicate it to
  participants via `Announce(CaseLedgerEntry)`
- MUST implement multi-party case management: participant invitation,
  acceptance, role assignment, and case ownership operations
- MUST implement the two-seam status adoption model ([§10.1](../index.md#101-status-adoption-the-two-seam-model)), including the
  canonical-write-before-side-effects ordering
- MUST deliver full case content only when the [§9.7](../index.md#97-gating-full-case-delivery) gate is satisfied

!!! note "Ledger replication scope"
    The detailed replication mechanics (hash-chaining, gap detection, ordering
    guarantees) are specified in a companion document,
    `docs/reference/draft-vultron-replication-spec.md`, not in this RFC. See ADR-0077. The single-hub / single-writer + fan-out model is the normative
    replication architecture: one Case Actor holds exclusive write authority and
    replicates entries to participant actors via `Announce(CaseLedgerEntry)`.
    Distributed consensus (multi-node CaseActor cluster) is a future extension
    out of scope for this RFC.

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

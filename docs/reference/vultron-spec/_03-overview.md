## 3. Protocol Overview [I]

### 3.1 The Protocol as a Communicating Hierarchical State Machine

The Vultron protocol is a Communicating Hierarchical State Machine (CHSM). It
has $N$ independent processes — one per Participant. Each process maintains a
disjoint set of states and a message set for communicating with the others. The
global state of the protocol at any moment is the pair $(S, C)$, where $S$ is
the tuple of all individual process states and $C$ is the set of messages
currently in transit.

No central process owns the global state. Each Participant holds a replica of
the case and advances its own state machines independently. The Case Actor
enforces single-writer authority over shared state ([§5.4.1](index.md#541-single-writer-authority)) and replicates
canonical changes to all Participants via `Announce(CaseLedgerEntry)`.

!!! info "See also"
    - [Formal Protocol Definition](../formal_protocol/index.md)

### 3.2 Tracking Dimensions

The protocol tracks coordination state across four dimensions:

- **Report Management (RM)** — lifecycle of a report from receipt to closure,
  tracked independently by each Participant. Seven states: `START`, `RECEIVED`,
  `INVALID`, `VALID`, `DEFERRED`, `ACCEPTED`, `CLOSED`.
- **Embargo Management (EM)** — negotiated disclosure timing at the case
  level. Five states: `NONE`, `PROPOSED`, `ACTIVE`, `REVISE`, `EXITED`.
- **Case State (CS)** — multi-dimensional public knowledge state, tracking
  what the world knows. CS is the pair `(VFD, PXA)`.
- **Participant Embargo Consent (PEC)** — per-participant embargo consent
  posture. Five states: `NO_EMBARGO`, `INVITED`, `SIGNATORY`, `LAPSED`,
  `DECLINED`.

!!! note "Four dimensions, five state machines"
    These four dimensions are realized as **five** state machines, because CS is
    a compound of two independent axes: `VFD` (participant-specific — vendor
    aware, fix ready, fix deployed) and `PXA` (participant-agnostic — public
    aware, exploit public, attacks observed). CS is the pair `(VFD, PXA)`.

    This document says "four dimensions" when discussing what is tracked, and
    "five state machines" when discussing what must be implemented ([§6](index.md#6-report-management-rm-state-machine-n)–[§11](index.md#11-participant-lifecycle-within-a-case-n),
    [§12.2](index.md#122-capability-sets)). Both counts are correct; they count different things.

RM, EM, and CS were present in the original protocol design. PEC emerged
during implementation (see [§9](index.md#9-participant-embargo-consent-pec-state-machine-n)) and is fully normative.

### 3.3 How the Dimensions Interact

The four dimensions are not independent. State transitions in one dimension
can trigger obligations or cascades in others.

**RM drives case progression.** A Participant's RM state governs what it is
obligated to do and what the Case Actor may deliver to it. Case content is
not delivered until a Participant has been admitted at `RM.RECEIVED` and
satisfied the embargo consent gate ([§9.7](index.md#97-gating-full-case-delivery)).

**EM gates publication.** An active embargo holds all Participants to deferred
disclosure. Any Participant transitioning EM to `EXITED` — or the arrival of
a triggering PXA observation — starts the teardown process ([§10.1](index.md#101-status-adoption-the-two-seam-model)).

**CS reflects observable reality.** CS transitions are not decisions; they
are observations. Any Participant may report a PXA observation. VFD
transitions are facts about what a specific Participant has done.

**PEC and EM are orthogonal.** EM says whether a case has an embargo; PEC
says whether a given Participant has consented to it. A case at `EM.ACTIVE`
may hold a Participant at `PEC.NO_EMBARGO` (one that joined after embargo
was set, or one that declined). Cascade rules keep the two in sync ([§10](index.md#10-model-interactions-and-cascade-rules-n)).

### 3.4 Participants and Roles

Participants take on **roles** that define their protocol obligations and drive
authority.

**Roles are not exclusive.** A Participant may hold Reporter, Vendor, and
Coordinator simultaneously. For example, a Vendor who discovers their own
product's vulnerability is both Reporter and Vendor.

**$N$ is Participant count, not role count.** The state machine population is
the set of Participants in the case. Each Participant runs all five state
machines regardless of its roles; roles govern which transitions it may drive.

**Two distinct role categories apply** (see [§12.3](index.md#123-role-taxonomy) for the full taxonomy):

- **Process roles** — what an actor *does* in a case: Reporter, Vendor,
  Coordinator, Deployer, CNA, Observer. These determine which protocol
  transitions an actor may drive.
- **Protocol authority roles** — what an actor *controls* in the protocol
  machinery: Case Owner, Case Manager. These confer specific write authority
  independent of domain activity.

Roles are assigned by the Case Owner through a defined authority chain
([§11.1](index.md#111-role-assignment-n)). An actor MUST NOT self-assign a role to a case it did not initiate.

!!! info "See also"
    - [Formal Protocol: Number of Processes](../formal_protocol/index.md)
    - [Role Taxonomy](../../topics/background/index.md)

---

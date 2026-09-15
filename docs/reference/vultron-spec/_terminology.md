## 2. Terminology [N/I]

### 2.1 Core Terms

The Vultron protocol uses a precise vocabulary where terms carry specific
protocol-level meanings that may differ from informal usage.

!!! info "Terminology reference"
    Full definitions, including aliases to avoid, are in the
    [Glossary](../glossary.md). The authoritative role enumeration is `CVDRole`
    in `vultron/enums/roles.py`.

Key terms used throughout this specification:

- **Vulnerability** — a weakness in a system that can be exploited to cause
  harm. Vulnerabilities are the subject of every Vultron case.
- **Report** — a document describing a specific vulnerability, submitted by
  a Reporter to initiate coordination.
- **Case** — the coordination context around a specific vulnerability; the
  unit of Vultron protocol activity.
- **Participant** — any organization or service actor that holds a
  `CaseParticipant` record in a case.
- **Actor** — an ActivityStreams actor (person, organization, service, or
  group); the identity unit in the wire protocol.
- **Reporter** — a Participant that submitted the original Report.
- **Vendor** — a Participant that produces a software or hardware product
  containing the vulnerability, and is responsible for developing a fix.
- **Coordinator** — a Participant that facilitates multi-party coordination
  without being responsible for developing a fix itself.
- **Deployer** — a Participant that deploys a Vendor's fix to end systems.
- **Observer** — a Participant with no VFD drive obligations; present to
  track case state.
- **Case Owner** — the actor with authoritative decision-making authority for
  a specific case. See [§12.3.2](index.md#1232-protocol-coordination-roles-protocol-authority).
- **Case Manager** — the actor performing canonical ledger management and
  case administration on behalf of the Case Owner. See [§12.3.2](index.md#1232-protocol-coordination-roles-protocol-authority).

### 2.2 Protocol Terms

- **Message** — a protocol operation sent between actors. Represented on the
  wire as an ActivityStreams 2.0 Activity.
- **Activity** — the ActivityStreams 2.0 base type for all wire messages.
- **Object** — the ActivityStreams 2.0 base type for content items:
  `VulnerabilityCase`, `VulnerabilityReport`, `CaseStatus`, etc.
- **Channel** — the path by which messages flow between actors. In
  Vultron, the primary channel is inbox-to-inbox HTTP POST via the Case
  Actor routing topology ([§5.4.2](index.md#542-routing-topology)).
- **State** — the current value of a state machine. Each participant
  maintains its own replica.
- **Transition** — a change from one state to another, triggered by a
  message or a local event.
- **Event** — a domain occurrence (message received, timer fired, trigger
  raised) that causes a state machine transition.
- **Embargo** — a time-bound agreement among case participants to defer
  public disclosure. Managed by the EM state machine ([§7](index.md#7-embargo-management-em-state-machine-n)) and tracked
  per-participant by PEC ([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)).
- **Publication** — the act of making vulnerability information publicly
  available, which typically terminates an active embargo.
- **Protocol shorthand** — the two-letter codes (`RS`, `EP`, `CV`, …) naming
  protocol messages by meaning rather than by wire form. Introduced in [§4](index.md#4-semantic-layer-message-meanings-n)
  and mapped to AS2 wire forms in [§4.7](index.md#47-shorthand-wire-form-mapping). Readers encountering a shorthand
  before [§4](index.md#4-semantic-layer-message-meanings-n) may treat it as an opaque label for a message type.

!!! info "See also"
    - [Glossary](../glossary.md)
    - [Formal Protocol Messages](../formal_protocol/messages.md)

---

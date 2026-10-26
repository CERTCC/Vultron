## 15. Security Considerations [N/I]

### 15.1 Trust Model

**Actor identity.** The protocol uses actor URIs as process identifiers. An
actor URI is the identity anchor for all messages sent by that actor, and for
the canonical case ledger if the actor holds the CASE_MANAGER role.
Actor URI equality is identity equality: two messages with the same `actor` URI are from the same actor.

**Verification.** The protocol does not currently mandate a specific identity
verification mechanism. The reference implementation anticipates HTTP Signatures
(as used in ActivityPub) as the authentication layer for inbound messages. A
future version of this specification is expected to normatively require HTTP
Signatures at the transport layer.

**Case bootstrap as the trust establishment mechanism.**
The `Create(VulnerabilityCase)` message that the report receiver sends to the reporter as itself is the trust root for a case ([§10.3 Case Bootstrap and the Trust Root](interactions.md#103-case-bootstrap-and-the-trust-root)).
Late joiners receive a case snapshot and prior ledger entries from the CASE_MANAGER.
A late joiner trusts the CASE_MANAGER's delivery because it trusts the invitation that named the CASE_MANAGER.
This chain is the minimal trust model; cryptographic ledger integrity (hash-chaining) provides tamper detection.

!!! info "See also"
    - [§4.1 Rules Under Any Coordination Model](layers.md#41-rules-under-any-coordination-model) (messages that arrive before their case)
    - [§5.3 Transport](layers.md#53-transport-ni) (addressing and channels)

### 15.2 Embargo Integrity

**Protocol adherence.** An active embargo is an agreement, not a technical
enforcement. The protocol provides the signaling infrastructure — Participant Embargo Consent (PEC) state
tracks which participants have consented, [§9.5 Embargo Traffic Reaches Non-Signatories](tracking-models.md#95-embargo-traffic-reaches-non-signatories) ensures all participants receive
meta-protocol messages — but it cannot prevent a participant from disclosing
outside the protocol.

**Defection.** If a participant discloses publicly while an embargo is `ACTIVE`,
the `CP` (public awareness) message will trigger the embargo teardown cascade
([§11.3 Status Adoption: The Two-Seam Model](interactions.md#113-status-adoption-the-two-seam-model)). The teardown is a state machine consequence, not a penalty mechanism.
The protocol has no built-in penalty for defection; enforcement is an
out-of-band organizational matter.

**Confidentiality gate.** Sensitive case content is gated on embargo consent ([§9.7 Gating Full Case Delivery](tracking-models.md#97-gating-full-case-delivery)).
While an embargo is in force, a participant that is not a signatory to it, because its consent row for that embargo is not `AGREED`, does not receive full case details.
This is the primary technical lever the protocol provides against inadvertent over-disclosure to non-consenting parties.

### 15.3 Replay and Idempotency

**Message deduplication.** Each ActivityStreams Activity carries a unique `id`, so a receiver can recognize a message it has already processed.
Duplicate delivery does not change state.

**Ledger idempotency.** The canonical case ledger is append-only and hash-chained.
A re-delivered `Announce(CaseLedgerEntry)` adds no second entry, and replaying entries a receiver already holds changes nothing.
The ledger NAK path (`Reject(CaseLedgerEntry)`) and gap-fill replay provide recovery from missed entries.

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("ID-01-001", "SYNC-03-003", "SYNC-08-003"))
```

### 15.4 Confidentiality

**In-transit protection.** The protocol does not currently mandate a specific
in-transit encryption mechanism. Transport Layer Security (TLS) is the expected transport protection for
HTTP delivery. A future version of this specification is expected to require TLS.

**At-rest and end-to-end confidentiality.** Content-level encryption — protecting
case details from the CASE_MANAGER itself, or supporting future multi-party
computation — is not specified by this version.
Any unencrypted case content is accessible to whoever operates the CASE_MANAGER.

**Scope.** This section covers security requirements for the protocol as
specified. Operational security measures (key management, access control,
incident response for actor compromise) are out of scope for this specification.

---

## 13. Security Considerations [N/I]

### 13.1 Trust Model

**Actor identity.** The protocol uses actor URIs as process identifiers. An
actor URI is the identity anchor for all messages sent by that actor, and for
the canonical case ledger if the actor holds the Case Actor role. Implementations
MUST treat actor URI equality as identity equality: two messages with the same
`actor` URI are from the same actor.

**Verification.** The protocol does not currently mandate a specific identity
verification mechanism. The reference implementation anticipates HTTP Signatures
(as used in ActivityPub) as the authentication layer for inbound messages. A
future version of this specification is expected to normatively require HTTP
Signatures at the transport layer.

**Case bootstrap as the trust establishment mechanism.** The
`Create(VulnerabilityCase)` message signed by the originating actor is the
trust root for a case. Late joiners receive a case snapshot and prior ledger
entries from the Case Actor. A late joiner trusts the Case Actor's delivery
because it trusts the `Create` message that introduced the Case Actor. This
chain is the minimal trust model; cryptographic ledger integrity (hash-chaining)
provides tamper detection.

!!! info "See also"
    - §4.5 (trust and bootstrap semantics)
    - §5.4 (addressing and channels)
    - `specs/case-bootstrap-trust.yaml` CBT-01 through CBT-05

### 13.2 Embargo Integrity

**Protocol adherence.** An active embargo is an agreement, not a technical
enforcement. The protocol provides the signalling infrastructure — PEC state
tracks which participants have consented, §9.5 ensures all participants receive
meta-protocol messages — but it cannot prevent a participant from disclosing
outside the protocol.

**Defection.** If a participant discloses publicly while an embargo is `ACTIVE`,
the `CP` (public awareness) message will trigger the embargo teardown cascade
(§10.1). The teardown is a state machine consequence, not a penalty mechanism.
The protocol has no built-in penalty for defection; enforcement is an
out-of-band organizational matter.

**Confidentiality gate.** Sensitive case content is gated on embargo consent
(§9.7). A participant that has not achieved `PEC.SIGNATORY` does not receive
full case details. This is the primary technical lever the protocol provides
against inadvertent over-disclosure to non-consenting parties.

### 13.3 Replay and Idempotency

**Message deduplication.** Each ActivityStreams Activity carries a unique `id`.
Implementations MUST deduplicate inbound messages by `id` before processing
them. Duplicate delivery does not change state.

**Ledger idempotency.** The canonical case ledger is append-only and
hash-chained. A re-delivered `Announce(CaseLedgerEntry)` with a known entry
hash MUST be treated as a no-op. The ledger NAK path (`Reject(CaseLedgerEntry)`)
and gap-fill replay provide recovery from missed entries.

### 13.4 Confidentiality

**In-transit protection.** The protocol does not currently mandate a specific
in-transit encryption mechanism. TLS is the expected transport protection for
HTTP delivery. A future version of this specification is expected to require TLS.

**At-rest and end-to-end confidentiality.** Content-level encryption — protecting
case details from the Case Actor itself, or supporting future multi-party
computation — is deferred in the current prototype. The encryption architecture
is tracked in `specs/encryption.yaml`. Implementations SHOULD treat any
unencrypted case content as potentially accessible to the Case Actor operator.

**Scope.** This section covers security requirements for the protocol as
specified. Operational security measures (key management, access control,
incident response for actor compromise) are out of scope for this specification.

---

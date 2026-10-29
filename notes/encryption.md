---
title: Signing and encryption implementation notes
status: active
kind: plan
tracks:
  - "#1156"
  - "#1184"
  - "#2841"
  - "#3477"
  - "#5380"
  - "#5383"
  - "#5386"
description: >
  Implementation notes for actor signing (object-level proofs from seeded keys,
  ADR-0164) and the open design of message encryption using keys published in
  actor profiles.
related_specs:
  - specs/signing.yaml
  - specs/encryption.yaml
  - specs/message-validation.yaml
  - specs/actor-knowledge-model.yaml
related_notes:
  - archived_notes/federation_ideas.md
  - notes/case-ledger-genesis-hardening.md
  - notes/case-actor-cluster.md
---

# Signing and encryption implementation notes

## Overview

- Signing is settled ([ADR-0164](../docs/adr/0164-actors-sign-content-with-object-level-proofs-from-seeded-keys.md),
  `specs/signing.yaml`) and is built by the Tasks under epic #1156.
- Encryption is not designed yet. It is its own later epic, blocked by signing.
- Both use keys an actor publishes in its actor profile, so neither needs a
  separate key-exchange channel.

## Key material binds to an actor, not to a case

ENC-01-001 requires a key pair per actor identity, generated when that identity
is provisioned. It does **not** require one per case, and no code may derive
key material from a case id.

Per-case key separation is a property of **deployment topology**, not of the
key-binding rule:

- An actor that enacts `CVDRole.CASE_MANAGER` for several cases uses **one** key
  pair across all of them. This is the shape the prototype has: a single
  `case-actor` container identity holds N cases, and the case a given activity
  belongs to travels in `activity.context` rather than in the actor URI.
- Where a **case actor service** provisions a dedicated CASE_MANAGER actor per
  case (glossary, "Case Actor Service"), each case ends up with distinct key
  material — because each case has its own actor, not because a per-case key
  rule exists.

Which of those a production deployment should use is unresolved, and it is the
question that decides how much cryptographic separation exists between cases on
one host. It belongs to the actor identity model (#2841) and to production key
handling (#1184).

Do not derive anything per-case from a CASE_MANAGER's identity: no container
registers a per-case identity (ADR-0088).

## Signing

The rules are SIG-01 to SIG-05; these notes say how to build them.

- **Seeded keys make no security claim.** A prototype actor's key pair comes
  from a fixed seed tied to its actor id (SIG-05-001), so proofs repeat across
  runs. Only the owner computes its key from the seed; verification reads the
  key from the author's profile (SIG-05-002). Never deploy seeded keys; random
  keys, storage and rotation are #1184 (ENC-01-001, ENC-01-004 to ENC-01-006).
- **One module signs and verifies** (SIG-05-003), the way
  `vultron.wire.as2.factories` owns outbound construction. Tests sign through a
  shared test helper built on it, never by hand.
- **Use RFC 8785 JCS, not the ledger hash's canonical form.** The ledger's
  `_canonical_bytes` in `vultron/core/models/case_ledger.py` is not JCS; reusing
  it makes proofs no other `eddsa-jcs-2022` verifier accepts. Refuse duplicate
  JSON keys and integers above 2^53 rather than sign or verify them, since
  parsers disagree on both.
- **Sign before the body is sealed.** The sealed body is final (OX-07-001), so
  the outbox signs the activity immediately before sealing it. The delivered
  body, the ledger snapshot and the relayed `Announce` then hold the same bytes
  (VM-08-003).
- **The proof survives the store.** A sender's `proof` reaches the ledger
  snapshot because the snapshot is the body as received (SIG-04-001). Check it
  survives the store's wire-identity rekeying (`_rekey_wire_identity` in
  `vultron/adapters/driven/db_record.py`) inside a snapshot.
- **Verify as its own ingress stage**, after the body-size, media-type and
  JSON-shape checks and before the parser (SIG-03-003). The pre-parsed
  `as_Activity` ingress path has no body to verify and goes when verification
  lands (#5386).
- **Strict from the start, with no switch** (SIG-03-002). The order of the
  Tasks is the ratchet: everything signs first, then every test delivery signs
  through the shared helper, then verification turns on. Verification cannot
  merge while any inbox delivery is unsigned.
- **Keys come from the author's profile** (SIG-02-001): a stored copy, else a
  plain GET of the profile, which needs no proof (SIG-02-002). Check that the
  `Multikey`'s `controller` is the actor whose profile lists it. When a profile
  copy expires, and how a rotated key is found, are #1184.

## Encryption principles

- Publish an encryption key in the actor profile beside the signing key: an
  encryption key belongs under `keyAgreement`, not `assertionMethod`.
- Decrypt before semantic extraction and dispatch, so semantics can be
  recognized reliably (ENC-03-001).
- Keep messages scoped to a single recipient when feasible, to avoid complex
  multi-recipient encryption.
- Default to encrypting outgoing messages when the recipient advertises a key.

## Incoming messages — where to decrypt

- Decryption should occur upstream of the dispatcher/handler layer, because:
  - Semantic extraction depends on object types and fields that may be
    unavailable on ciphertext.
  - Handlers expect rehydrated objects and validated structures.
- Practical flow:
  1. HTTP endpoint receives activity payload.
  2. If the payload is encrypted, decrypt it with the actor's private key
     during request handling.
  3. Verify the decrypted activity's proof (SIG-03-001), then continue with
     parsing, semantic extraction and dispatch.

## Outgoing messages — strategies and trade-offs

- Per-recipient messages (recommended):
  - For each intended recipient, encrypt a separate message to that
    recipient's public key and send it directly.
  - Pros: simple, compatible with most public-key schemes, preserves
    recipient-only confidentiality.
  - Cons: more messages to send when many recipients exist.
- Single-message multi-recipient encryption (optional):
  - Use hybrid schemes (one symmetric key encrypted to multiple public keys)
    or standards like CMS (S/MIME) that allow multiple recipients.
  - Pros: fewer HTTP messages.
  - Cons: more complex implementation, harder key management, and potential
    interoperability issues with ActivityPub toolchains.
- Recommendation: use per-recipient encryption by default; evaluate
  multi-recipient schemes only if the message volume or latency requires it.

## Implementation guidance

- Log encryption and decryption actions at INFO or DEBUG without exposing
  private material or plaintext content (ENC-01-004).
- When persisting activities, store ciphertext only if you intend to retain
  encrypted blobs; otherwise store the canonical plaintext activity objects.
- For Accept/Reject responses and similar reply activities, carry the
  referenced activity **inline** in `object`, as this codebase does for every
  outbound activity (AKM-03-003); a bare ID string is refused at delivery
  (MV-09-002). Encryption wraps the whole sealed body, so it does not change
  this.

## Open questions (to decide)

- Do we accept the extra network cost of per-recipient messages to simplify
  crypto, or do we invest in multi-recipient schemes?
- Should we standardize on a specific envelope format for interoperability
  (e.g., JWE, CMS, or a custom hybrid)?
- Is the signed plaintext encrypted whole, so the proof survives decryption,
  or does encryption carry its own integrity check?

## References

- FEP-8b32, Object Integrity Proofs: <https://codeberg.org/fediverse/fep/src/branch/main/fep/8b32/fep-8b32.md>
- W3C Data Integrity EdDSA Cryptosuites v1.0: <https://www.w3.org/TR/vc-di-eddsa/>
- ActivityPub security considerations: <https://docs.joinmastodon.org/spec/security/>

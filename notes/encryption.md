---
title: Signing and encryption implementation notes
status: active
kind: plan
tracks:
  - "#1156"
  - "#1184"
  - "#2841"
  - "#3477"
  - "#5383"
  - "#5385"
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
  - specs/error-handling.yaml
  - specs/vocabulary-model.yaml
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
  A `SigningKey` exports no private key and shows only its public half, so
  logging one discloses nothing (ENC-01-007).
- **One module signs and verifies** (SIG-05-003): `vultron/wire/as2/signing.py`,
  the way `vultron.wire.as2.factories` owns outbound construction. Tests sign
  through a shared test helper built on it, never by hand. A verifier passes it
  the author's published `publicKeyMultibase`, never a `SigningKey`.
- **Use RFC 8785 JCS, not the ledger hash's canonical form.** The ledger's
  `_canonical_bytes` in `vultron/core/models/case_ledger/hashing.py` is not JCS; reusing
  it makes proofs no other `eddsa-jcs-2022` verifier accepts. Refuse duplicate
  JSON keys and integers above 2^53 rather than sign or verify them, since
  parsers disagree on both.
- **A signed activity's `@context` is a list.** Signing appends
  `https://w3id.org/security/data-integrity/v2` to the activity's own
  `@context`, as FEP-8b32's examples do and other implementers expect, so the
  default AS2-then-Vultron list (VM-10-001) gains a third entry and a single
  received context becomes a list. `@context` on the wire and core roots is
  `JsonLdContext` (`vultron/core/models/base/context.py`): one IRI or a
  non-empty list of IRIs, never an inline term map; reuse it, do not widen a
  field again.
- **Tests sign through `test/support/signing.py`**: `signed_body`, `resigned`
  (an altered copy, re-signed), `post_signed`. Proofs there are deterministic
  (seeded key, fixed `created`), so a resend is the archived bytes. In
  `test/support/received.py`, `body_of` (behind `archive_received` and
  `intake_received`) and `hold_deferred` seed signed bodies; a test that resends
  against them signs its delivery too, or IE-10-002 refuses it. Every other
  helper there is still unsigned; #5385 repoints them with the other test
  deliveries.
- **The parser sets `proof` aside** as a foreign key (MV-11-003), with one INFO
  record per delivery; the received evidence keeps it (SIG-04-001). Verification
  reads the raw body before the parser (#5386), so nothing needs it parsed.
- **Sign before the body is sealed.** The sealed body is final (OX-07-001), so
  `seal_outbound_body` signs it as its author, the activity's `actor`
  (`signed_outbound_body` in `vultron/adapters/outbox_sealed_body.py`). The
  delivered body, the ledger snapshot and the relayed `Announce` then hold the
  same bytes (VM-08-003). Sign nowhere else: a relay signs its own `Announce`
  at its own seal, and never touches the nested snapshot's proof.
- **`dump_outbound_body` is the unsigned dump.** A test that builds a delivery
  from it sends no proof, so once verification is on (#5386) it signs it
  through `test/support/signing.py`, or reads the sealed body instead.
- **The proof survives the store.** A sender's `proof` reaches the ledger
  snapshot because the snapshot is the body as received (SIG-04-001). Check it
  survives the store's wire-identity rekeying (`_rekey_wire_identity` in
  `vultron/adapters/driven/db_record/codec.py`) inside a snapshot.
- **Verify as its own ingress stage**, after the body-size, media-type and
  JSON-shape checks and before the parser (SIG-03-003). The pre-parsed
  `as_Activity` ingress path has no body to verify and goes when verification
  lands (#5386).
- **An uncanonicalizable body fails at the CASE_MANAGER's seal until #5386.**
  A received body holding an integer beyond ±(2^53 - 1) cannot be signed, so
  the `Announce(CaseLedgerEntry)` carrying its snapshot fails to seal and the
  commit tree fails without a named refusal. A sender's outbox cannot sign
  such a body either, so the verification stage should refuse it at ingress.
- **The parser drops `proof` from what it parses.** Only the ledger snapshot
  keeps the received body, so an activity a receiver re-embeds from its parsed
  copy carries no original proof. A relay that must carry an author's proof
  takes it from the received evidence (SIG-04-001).
- **A failed proof raises `VultronProofVerificationError`** (EH-03-005), which
  `translate_domain_errors` answers 422 as `ProofVerificationError`, not 401:
  the proof is content, not an HTTP credential. `signing.verify` raises its
  subclass `VultronProofInvalidError`. Decide in #5386 whether a malformed
  published key (`VultronMultikeyError`) or an uncanonicalizable body
  (`VultronUnsignableJsonError`) is also refused 422; both are unmapped today.
- **Strict from the start, with no switch** (SIG-03-002). The order of the
  Tasks is the ratchet: everything signs first, then every test delivery signs
  through the shared helper, then verification turns on. Verification cannot
  merge while any inbox delivery is unsigned.
- **Keys come from the author's profile** (SIG-02-001): a stored copy, else a
  plain GET of the profile, which needs no proof (SIG-02-002). Check that the
  `Multikey`'s `controller` is the actor whose profile lists it. When a profile
  copy expires, and how a rotated key is found, are #1184.
- **Read a key from `CoreActor.assertion_method`, not from raw JSON.** It is a
  list of core `Multikey` values (`vultron/core/models/multikey.py`), and
  validation already guarantees each key id is `<controller>#<fragment>` and
  each controller is the profile's own actor. A resolver strips the fragment
  to find the profile, then matches the key id exactly (ENC-01-002).
- **The hosted actor's key is published, not stored.** Both profile routes,
  `/actors/{id}` and `/actors/{id}/profile`, list the actor's own
  `signing.published_multikey` and replace any key its record states: a
  published key other than the signing key fails every proof. Only the
  owner's routes compute it; a peer's key comes from its profile
  (SIG-05-002). `GET /actors/` lists each hosted actor the same way.
- **An inline sender profile carries no key.** An activity carries the
  sender's own stored record as held (AKM-05-005), and that record lists no
  key, while a receiver keeps a held copy over a fetched one (MV-10-003). The
  #5383 resolver must fetch the profile when its held copy lists no key the
  proof names, not refuse on the held copy alone.
- **A profile typed `"Actor"` loses its key at parse.** The wire `as_Actor`
  ignores unknown fields, so it drops `assertionMethod`, while the five
  concrete actor types keep it. The #5383 resolver then finds no key and fails
  closed (SIG-02-001); its refusal should name the generic type as the cause,
  not say the actor published no key.
- **The served profile's `@context` defines the key terms.** The Vultron
  context defines no `assertionMethod`, `Multikey`, `controller` or
  `publicKeyMultibase`, so `profile_of_record` appends
  `signing.MULTIKEY_CONTEXT` to the dumped `@context`, after whatever default
  the actor has; a JSON-LD-expanding verifier drops the key without it.

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
  private material or plaintext content (ENC-01-007).
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

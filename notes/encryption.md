---
title: Encryption implementation notes
status: active
description: >
  Exploratory notes on encryption options for Vultron using ActivityPub
  public-key infrastructure.
related_specs:
  - specs/encryption.yaml
related_notes:
  - notes/federation_ideas.md
---

# Encryption implementation notes

> **Tracked by**: issue #1156 and its children. This file is the design seed
> for that implementation work.

## Overview

- ActivityPub supports public-key distribution via actor profiles.
- Leverage ActivityPub public keys where possible to avoid re-inventing
  discovery and distribution.
- Goal: enable the actor enacting `CVDRole.CASE_MANAGER` and other actors to
  send and receive encrypted messages while preserving semantic routing and
  handler behavior.

## Key material binds to an actor, not to a case

ENC-01-001 requires a key pair per actor identity, generated when that identity
is provisioned. It does **not** require one per case, and no code may derive
key material from a case id.

Per-case key separation is a property of **deployment topology**, not of the
key-binding rule:

- An actor that enacts `CVDRole.CASE_MANAGER` for several cases uses **one** key
  pair across all of them. This is the shape the prototype has: a single
  `case-actor` container identity holds N cases, and the case a given activity
  belongs to travels in `activity.context` rather than in the actor URI
  (ISSUE-1872).
- Where a **case actor service** provisions a dedicated CASE_MANAGER actor per
  case (glossary, "Case Actor Service"), each case ends up with distinct key
  material — because each case has its own actor, not because a per-case key
  rule exists.

Which of those a production deployment should use is unresolved, and it is the
question that decides how much cryptographic separation exists between cases on
one host. It belongs to the actor identity model (#2841, epic #1156).

The pitfall this replaces: ENC-01 was written as "one key pair per case, bound
to the CaseActor for that case's lifetime", which invited an implementation
keyed on the case. Deriving anything per-case from a CaseActor's *identity* is
the category error ADR-0088 names — no container has registered a per-case
identity, so calls to it answer 404.

## Principles

- Prefer standard mechanisms (Actor.publicKey) for discovery and storage.
- Perform decryption before semantic extraction/dispatch so semantics can be
  recognized reliably.
- Keep messages scoped to a single recipient when feasible to avoid complex
  multi-recipient encryption requirements.
- Default to encrypting outgoing messages when the recipient advertises a
  public key.

## Incoming messages — where to decrypt

- Decryption should occur upstream of the dispatcher/handler layer. Reasons:
  - Semantic extraction depends on object types and fields that may be
    unavailable on ciphertext.
  - Handlers expect rehydrated objects and validated structures.
- Practical flow:
  1. HTTP endpoint receives activity payload.
  2. If payload appears encrypted, perform decryption using the actor's
     private key (or a configured keyring) during request handling.
  3. Rehydrate any URI references and continue normal semantic extraction and
     dispatching.
- Ensure authorization and integrity checks (signatures, sender identity)
  are performed as part of decryption/validation.

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

## Public key discovery and rotation

- Read public keys from the recipient actor's profile (ActivityPub
  `publicKey` property). Validate the key format and its association with the
  actor.
- Support key rotation:
  - Allow multiple public keys to be published temporarily.
  - Prefer keys with explicit creation/expiration metadata if available.
  - Fall back to sending an unencrypted message with a warning only if
    encryption is explicitly required and no valid key exists.

## Implementation guidance

- Store private keys securely (OS key store, HSM, or encrypted configuration).
- Log encryption/decryption actions at INFO or DEBUG levels without exposing
  private material or plaintext content.
- Implement decryption in the HTTP ingress layer (or a dedicated middleware)
  so downstream components receive plaintext, validated activities.
- When persisting activities, store ciphertext only if you intend to retain
  encrypted blobs; otherwise store the canonical plaintext activity objects.
- For Accept/Reject responses and similar reply activities, set `object` to
  the referenced activity's ID string (not an inline object) to ensure
  rehydration and validation succeed after transport.

## Open questions (to decide)

- Do we accept the extra network cost of per-recipient messages to simplify
  crypto, or do we invest in multi-recipient schemes?
- Should we standardize on a specific envelope format for interoperability
  (e.g., JWE, CMS, or a custom hybrid)?
- How should public-key metadata (creation, expiry, usage rules) be surfaced
  in actor profiles for automated decision-making?

## References

- ActivityPub actor publicKey: <https://docs.joinmastodon.org/spec/activitypub/#publicKey>
- ActivityPub security considerations: <https://docs.joinmastodon.org/spec/security/>

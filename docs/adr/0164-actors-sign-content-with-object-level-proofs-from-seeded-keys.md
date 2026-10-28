---
status: accepted-provisional
date: 2026-10-28
created: 2026-10-28
updated: 2026-10-28
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; FEP-8b32 (Object Integrity Proofs); W3C Data Integrity EdDSA
  Cryptosuites (eddsa-jcs-2022); RFC 8785 (JCS); RFC 9421 (HTTP Message
  Signatures); specs/encryption.yaml ENC-01; specs/outbox.yaml OX-07-001,
  OX-10; specs/vocabulary-model.yaml VM-08-003; specs/message-validation.yaml
  MV-11; issues #509, #1156, #1162, #1163, #1184
informed: []
stakeholder_type: [project-contributor]
---

# Actors Sign Content with Object-Level Proofs from Seeded Keys

## Context and Problem Statement

A Vultron receiver cannot tell who wrote an activity it receives (#509).
The inbox accepts any well-formed body, so any client can post an activity in another actor's name.

Signed content has to travel further than one delivery.
The CASE_MANAGER commits a participant's activity to the case ledger as the entry's `payloadSnapshot` and relays it to every replica inside an `Announce(CaseLedgerEntry)` (VM-08-003).
A replica that applies the entry acts on the participant's words, delivered by the CASE_MANAGER.

The prototype also needs repeatable output: tests, demos and documentation examples compare and show exact wire bodies.

How does an actor sign what it sends so that every later reader can check it, and what keys does the prototype use?

## Decision Drivers

- The proof must stay checkable after a relay and after a ledger commit, not only on the first delivery.
- A receiver must get an author's key from somewhere it can trust as much as it trusts the author's identity.
- Signing must leave the sealed body (OX-07-001) the exact bytes that are delivered and committed (VM-08-003).
- Tests, demos and documentation examples need proofs that are the same on every run.
- The prototype must not suggest that its key handling is fit for production.
- A verification rule that is off in tests is a rule nobody checks.

## Considered Options

- HTTP Signatures (RFC 9421, or the draft-cavage form) on each delivery request.
- Object-level proofs inside the activity (FEP-8b32, `eddsa-jcs-2022`).
- Both at once.
- Random keys generated at provisioning, stored by each actor.
- Keys computed from a fixed seed per actor (seeded keys).
- Verification behind a runtime switch, off in tests and demos.
- Strict verification from the start, with no switch.

## Decision Outcome

Chosen options: "object-level proofs inside the activity", "seeded keys" and "strict verification from the start, with no switch", because only a proof inside the content survives the relay and the ledger, seeded keys give repeatable proofs while making no security claim, and a rule that is always on is a rule the suite always checks.

- **The proof lives inside the message.**
  Every activity an actor sends carries a `proof` (FEP-8b32): a `DataIntegrityProof` using the `eddsa-jcs-2022` cryptosuite, Ed25519 over the RFC 8785 canonical form of the activity.
  The outbox signs the activity before it seals the body, so the sealed body is the signed body.
- **The ledger stores what was received.**
  A ledger entry's `payloadSnapshot` keeps the sender's `proof` unchanged.
  The CASE_MANAGER's own proof covers the `Announce(CaseLedgerEntry)` it sends.
- **Keys come only from the author's profile.**
  Each actor publishes its public key as a `Multikey` under `assertionMethod` in its actor profile.
  A receiver reads the key from a copy of the profile it holds or by fetching the profile.
  Fetching a profile needs no proof.
  The CASE_MANAGER no longer hands its key to each participant when it adds them.
- **Seeded keys.**
  A prototype actor's key pair is computed from a fixed seed.
  It makes no security claim.
  Only the key's owner computes the key from its seed: verification never derives a key.
- **Strict from the start.**
  A missing or invalid proof is refused at the inbox and on replicas, in tests and demos too.
  There is no switch to turn verification off, and no test escape.
  The order of the work is the ratchet: everything signs first, and verification cannot merge while anything unsigned is still delivered.
- **Replicas check both proofs.**
  A replica checks the CASE_MANAGER's proof on an `Announce(CaseLedgerEntry)` and, for a participant's act, its author's proof on the `payloadSnapshot`.
  It refuses the whole entry if either fails.
- **One helper module.**
  One compact module creates and verifies every proof, the way the activity factories own outbound construction.
  Nothing signs or verifies by hand, tests included.
  It builds on the `cryptography`, `rfc8785` and `base58` libraries.

HTTP Signatures, production key generation, private-key storage and key rotation are productionization work (#1184).
Encryption is out of scope.

### Consequences

- Good, because a replica can check that a participant wrote what the CASE_MANAGER relays, with no extra exchange.
- Good, because the sealed body, the delivered body and the ledger snapshot stay the same bytes.
- Good, because seeded keys make every signed example and test body repeatable.
- Good, because key discovery reuses the actor profile that peers already fetch.
- Bad, because every test that delivers to an inbox must sign its body, which needs a shared test helper and a migration of many tests before verification can be turned on.
- Bad, because mainstream ActivityPub servers expect HTTP Signatures, so the prototype does not interoperate with them until #1184 adds them.
- Bad, because anyone who knows the seed scheme can sign as a prototype actor; the prototype must never be deployed with seeded keys.

## Validation

Strict-`xfail` marker tests for the signing requirements (`specs/signing.yaml`) are in CI from the start.
Each names the Task that turns it green, and the Task that does removes the marker.
The epic is done when every marker has flipped.

## Pros and Cons of the Options

### HTTP Signatures on each delivery

- Good, because mainstream ActivityPub servers use them.
- Good, because they authenticate the server that delivers the request.
- Bad, because the signature covers one request: once the CASE_MANAGER relays an activity or commits it to the ledger, nothing shows that the participant wrote it.
- Bad, because a delivery proxy or test router that rebuilds the request breaks the signature.

### Object-level proofs inside the activity

- Good, because the proof travels with the content through relays, the ledger and replicas.
- Good, because a test or demo can check a proof on a body without an HTTP request.
- Neutral, because FEP-8b32 is a Fediverse Enhancement Proposal, not a finished standard; it builds on the W3C Data Integrity recommendation.
- Bad, because the signer and the verifier must canonicalize the same JSON the same way, so duplicate keys and large integers must be refused.

### Both at once

- Good, because it gives the content guarantee and server interoperability together.
- Bad, because it doubles the prototype's crypto surface for an interoperability goal the prototype does not have yet.

### Random keys generated at provisioning

- Good, because this is how production must work (ENC-01-001).
- Bad, because every run and every test gets different proofs, so examples and exact-body assertions cannot be repeated.
- Bad, because it needs private-key storage that the prototype would have to build and then claim is safe.

### Seeded keys

- Good, because proofs are the same on every run.
- Good, because the prototype makes no security claim it cannot keep.
- Bad, because anyone who knows the scheme can compute any actor's private key.

### Verification behind a switch

- Good, because tests could stay unsigned.
- Bad, because the suite would check verification only where the switch is on, and the switch would become the way to make a test pass.

### Strict verification with no switch

- Good, because every test and demo exercises the real refusal path.
- Bad, because verification cannot merge until every delivery is signed.

## More Information

Generated spec requirements: the SIG requirements in `specs/signing.yaml`; ENC-01-002 (reworded).
ENC-01-003, which had the CASE_MANAGER share its key with each new participant, is retired.

- FEP-8b32, Object Integrity Proofs: <https://codeberg.org/fediverse/fep/src/branch/main/fep/8b32/fep-8b32.md>
- W3C Data Integrity EdDSA Cryptosuites v1.0: <https://www.w3.org/TR/vc-di-eddsa/>
- RFC 8785, JSON Canonicalization Scheme: <https://www.rfc-editor.org/rfc/rfc8785>

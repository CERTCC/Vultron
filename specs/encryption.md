# Encryption Specification

## Overview

Requirements for encrypted messaging and actor key management using
ActivityPub extension conventions. Ensures that sensitive vulnerability
information can be protected in transit between actors.

**Source**: `plan/IDEATION.md` (Encryption and keys)
**Note**: All requirements in this file are `PROD_ONLY`. Encryption is not
implemented in the prototype.
**Cross-references**: `prototype-shortcuts.md` PROTO-01-001,
`case-management.md`, `inbox-endpoint.md`, `semantic-extraction.md`

---

## Key Management (MUST)

- `ENC-01-001` `PROD_ONLY` Each CaseActor MUST generate an asymmetric key
  pair at instantiation
  - Key pairs MUST use a well-supported algorithm (e.g., RSA-2048 or Ed25519)
- `ENC-01-002` `PROD_ONLY` The CaseActor MUST publish its public key in its
  ActivityPub actor profile using the `publicKey` property per ActivityPub
  HTTP Signatures conventions
  - See: https://docs.joinmastodon.org/spec/activitypub/#publicKey
- `ENC-01-003` `PROD_ONLY` The CaseActor MUST share its public key with
  each case participant when they are added to the case
- `ENC-01-004` `PROD_ONLY` Private keys MUST be stored securely and MUST
  NOT be logged or included in API responses

## Message Encryption (SHOULD)

- `ENC-02-001` `PROD_ONLY` Case participants MAY encrypt messages sent to
  the CaseActor using the CaseActor's published public key
- `ENC-02-002` `PROD_ONLY` When sending messages to case participants, the
  CaseActor SHOULD encrypt each outbound message to the recipient's public
  key individually (one encrypted payload per recipient)
  - Broadcast encryption to multiple recipients in a single message payload
    is out of scope for the initial implementation

## Decryption Pipeline (MUST)

- `ENC-03-001` `PROD_ONLY` Decryption of inbound encrypted activities MUST
  occur in the inbox handler before the activity is passed to semantic
  extraction or dispatch
  - Handler functions MUST receive already-decrypted activities
  - **Cross-reference**: `inbox-endpoint.md`, `semantic-extraction.md`
- `ENC-03-002` `PROD_ONLY` If decryption fails, the inbox handler MUST
  return HTTP 400 with a structured error indicating decryption failure
  - **Cross-reference**: `error-handling.md`, `http-protocol.md`
- `ENC-03-003` `PROD_ONLY` The decryption layer MUST be separate from
  semantic extraction logic; the two concerns MUST NOT be mixed

## Verification

### ENC-01-001, ENC-01-002 Verification

- `PROD_ONLY` Unit test: CaseActor instantiation produces a key pair
- `PROD_ONLY` Integration test: `GET /actors/{id}` response includes
  `publicKey` field

### ENC-02-001 Verification

- `PROD_ONLY` Integration test: Message encrypted with actor public key is
  accepted and decrypted successfully

### ENC-03-001, ENC-03-002 Verification

- `PROD_ONLY` Unit test: Inbox handler passes decrypted content to
  semantic extraction
- `PROD_ONLY` Unit test: Inbox handler returns HTTP 400 on decryption
  failure

## Related

- **Inbox Endpoint**: `specs/inbox-endpoint.md`
- **Semantic Extraction**: `specs/semantic-extraction.md`
- **HTTP Protocol**: `specs/http-protocol.md`
- **Error Handling**: `specs/error-handling.md`
- **Prototype Shortcuts**: `specs/prototype-shortcuts.md` (PROTO-01-001)
- **Case Management**: `specs/case-management.md`
- **ActivityPub publicKey**: https://docs.joinmastodon.org/spec/activitypub/#publicKey
- **Mastodon security spec**: https://docs.joinmastodon.org/spec/security/

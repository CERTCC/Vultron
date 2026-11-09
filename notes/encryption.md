---
title: Signing and encryption implementation notes
status: active
kind: plan
tracks:
  - "#1156"
  - "#1184"
  - "#2841"
  - "#3477"
  - "#5387"
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
  - specs/object-ids.yaml
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
- **An outbox signs only its own actor's messages** (SIG-05-004). The seed
  scheme is guessable by design, so any code could compute any actor's key;
  the guarantee is that only the owning actor's outbox calls the signer for
  that actor. `seal_outbound_body` passes its store's `actor_id` (DL-07-004)
  to `sign_as_author`, which refuses an activity whose `actor` names anyone
  else with `VultronForeignAuthorError` before signing or storing. Never
  sign through a store that is not the author's, and never add a fallback.
- **`actor` is the signer; `attributed_to` is the initiator** (SIG-05-005).
  An actor that sends on another's behalf, such as the CASE_MANAGER recording
  a status the case owner set, names itself as `actor` and carries the owner
  in `attributed_to`. When the actor initiated it, leave `attributed_to` out:
  it would only repeat the `actor`.
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
  (an altered copy, re-signed), `post_signed`, and `post_delivered` for a body
  that is signed already. Proofs there are deterministic
  (seeded key, fixed `created`), so a resend is the archived bytes.
  `delivered_body` and `evidence_for` in `test/support/received.py` sign what
  they return, and `body_of`, `hold_deferred` and `with_evidence` build on
  them, so never wrap their result in `signed_body` (a second proof raises).
  `LedgerNetwork.delivered_body` signs any body but the one its sender's
  outbox sealed. A test that alters a signed body builds the copy with
  `resigned`, since an edit in place leaves a stale proof that verification
  refuses. A body read back from a sealed outbox is
  signed by the outbox (#5382), never by the test.
- **Unsigned test bodies that reach no verifier stay unsigned**: a body
  parsed only to test the parser (what it keeps, refuses or sets aside), since
  verification is an ingress stage before the parser; placeholder held or
  stored bodies that nothing parses; `{}` behind a stubbed ingress; and
  parse-refusal posts. A body a test carries past the parse, as a reply's
  embedded copy, an archive or a routed event, is signed.
  A post that reaches the inbox is verified before it is parsed, so a test of
  a parse refusal at the inbox posts a signed body, or it meets the proof
  refusal first.
- **The parser sets `proof` aside** as a foreign key (MV-11-003), with one INFO
  record per delivery; the received evidence keeps it (SIG-04-001). Do not
  declare it: verification reads the body before the parser, so nothing needs
  it parsed, and a declared spelling must be a field (MV-11-001), which would
  carry the proof into the parsed object and its stored form (MV-11-010).
- **Sign before the body is sealed.** The sealed body is final (OX-07-001), so
  `seal_outbound_body` signs it as its author, the activity's `actor`
  (`signed_outbound_body` in `vultron/adapters/outbox_sealed_body.py`). The
  delivered body, the ledger snapshot and the relayed `Announce` then hold the
  same bytes (VM-08-003). Sign nowhere else: a relay signs its own `Announce`
  at its own seal, and never touches the nested snapshot's proof.
- **`dump_outbound_body` is the unsigned dump.** A test that builds a delivery
  from it sends no proof, so it signs it through `test/support/signing.py`, or
  reads the sealed body instead.
- **The proof survives the store.** A sender's `proof` reaches the ledger
  snapshot because the snapshot is the body as received (SIG-04-001). Check it
  survives the store's wire-identity rekeying (`_rekey_wire_identity` in
  `vultron/adapters/driven/db_record/codec.py`) inside a snapshot.
- **Verify as its own ingress stage**, after the body-size, media-type and
  JSON-shape checks and before the parser (SIG-03-003): the inbox route's
  `verified_delivery` dependency (`routers/actors/_inbox.py`) decodes the raw
  body with `signing.load_json` and runs the `get_proof_verifier` port
  (`ProfileKeyProofVerifier` in `inbox_verification.py`). Never verify in
  semantic extraction or in core. The route hands the background task the
  verified body, and `FastAPIIngressAdapter.parse` takes only a body, never a
  parsed activity, which carries no proof.
- **A replica's check is the same stage** (SIG-04-002). An `Announce(CaseLedgerEntry)`
  needs its `payloadSnapshot`'s proof too, verified by the key of the snapshot's own
  `actor`: the CASE_MANAGER's for a native entry, the author's for a relayed act. Either
  failure refuses the whole delivery, and a snapshot naming no actor is refused, since
  every activity names its signer (SIG-05-005). Find the entry and snapshot under every
  spelling the parser reads (`object_`, `payload_snapshot`, `type_`): a check that reads
  only the alias is stepped around by the field name. It reads the body as received,
  since no parsed copy keeps a proof. Whether the `Announce`'s actor is the CASE_MANAGER
  stays core's check. A test entry's snapshot is a signed activity too, never a
  placeholder dict.
- **The inbox answers a body it cannot read by RFC 9110's split.** Text that
  is not RFC 8259 JSON (`VultronJsonSyntaxError`: not JSON, not UTF-8, `NaN`,
  `Infinity`) is 400; well-formed JSON it refuses (`VultronRefusedJsonError`:
  not an object, a duplicate key, an integer beyond ±(2^53 - 1), a number too
  large for a double) is 422 `ValidationError`
  (`inbox_body_http_exception`). Raise the subclass that says which; never
  tell them apart by message. So a body no outbox could sign is refused at
  ingress, not when the CASE_MANAGER seals its `Announce`.
- **The parser drops `proof` from what it parses.** Only the ledger snapshot
  keeps the received body, so an activity a receiver re-embeds from its parsed
  copy carries no original proof. A relay that must carry an author's proof
  takes it from the received evidence (SIG-04-001).
- **A failed proof raises `VultronProofVerificationError`** (EH-03-005), which
  `translate_domain_errors` answers 422 as `ProofVerificationError`, not 401:
  the proof is content, not an HTTP credential. `signing.verify` raises its
  subclass `VultronProofInvalidError`. A published key that is not an Ed25519
  Multikey (`VultronMultikeyError`) is a key that cannot be read: the stage
  raises `VultronVerificationKeyError`. The translator maps no other signing
  error.
- **Strict, with no switch** (SIG-03-002). A test app that receives signed
  bodies gives their authors a profile to be read from, never a bypass:
  `serve_published_profiles` (`test/support/signing.py`) for a single app, and
  `create_isolated_actor_app`'s `InProcessObjectFetcher`, which fetches the
  profile from the node that serves it; the single-node demo `client`
  fixture installs the same fetcher on `app_v2`. An unsigned body a test posts
  on purpose is a refusal test, or a strict `xfail` naming the Task that signs
  it (the tutorial's report, #5387).
- **Demo and harness code never signs as an actor.** Only an actor's own
  outbox signs (SIG-05-004). An exchange demo's hand-built activity goes
  through the sender's outbox on the same server (`post_to_inbox_and_wait`
  posts it to `/actors/{sender}/outbox/`), which signs it as its owner; a
  scenario step goes through a trigger. Tests sign only through
  `test/support/signing.py`, never from `vultron/`.
- **Resolve a key with `resolve_verification_key`**
  (`vultron/core/services/verification_key.py`), never by hand. It takes the
  proof's `verificationMethod`, the document's author and an
  `ActorProfileFetchPort` (`HttpActorProfileFetchAdapter` in
  `vultron/adapters/driven/http_actor_profile_fetch.py`), and returns the
  core `Multikey` whose `publicKeyMultibase` goes to `signing.verify`. It always
  fetches `{actor}/profile` with a plain GET and no proof (SIG-02-001,
  SIG-02-002), and takes no store. It refuses a key whose actor is not the author
  before any fetch, and checks the profile's id and the key's `controller` are
  the key's actor. The inbox names the activity's `actor` as the author
  (SIG-05-005).
  Pinning the first key fetched (trust on first use), caching and rotation are
  #1184.
- **The resolver is async and refuses with `VultronVerificationKeyError`**, a
  `VultronProofVerificationError`, so the ingress answers an unresolvable key
  as it answers a failed proof (SIG-03-002). A fetch failure is
  `VultronActorProfileFetchError`, chained as the refusal's cause and logged;
  the refusal text names only the key and its actor, since it goes back to the
  sender. Anything else a fetcher raises is a fault and propagates.
- **A verifier trusts only a fetched key** (SIG-02-003). A stored copy of a
  peer's profile came from somewhere other than the peer, so no store is read
  for a key; never add a held-copy shortcut, a fetch is what proves the key is
  the peer's.
- **Keys embedded in a received activity are discarded at parse** (SIG-02-004).
  The MV-11 walk (`unknown_keys._partition_object`) sets aside
  `assertionMethod`, under any spelling, on every actor profile below the
  envelope and reports it as a set-aside key, so no parsed object or stored
  record carries a peer's key. The received evidence and a ledger snapshot keep
  the body as received; no key is read from them. A profile the lookup fetches
  is parsed by `parse_fetched_object` and keeps its key, as the owner's served
  profile does.
- **A key lookup runs before the sender is verified**, so an unsigned or forged delivery
  chooses the URL the receiver fetches. Keep it bounded:
  `deps.get_actor_profile_fetcher` makes one attempt, its timeout
  (`verification_key_fetch_timeout_seconds`, no AKM-05-008 retries) bounding the
  whole attempt and its body capped (`MAX_VERIFICATION_PROFILE_BYTES`), and
  `check_profile_fetch_target` admits only an `http`/`https` URL with an ASCII host,
  no user info, query or fragment and no non-public IP literal, read in every spelling
  the resolver reads (`inet_aton` forms, a trailing dot, IPv4 inside IPv6). A
  non-ASCII host is refused because httpx maps it (IDNA) before it connects, so
  `127。0。0。1` would reach loopback past the check. Host names pass, `localhost`
  too: the Docker demos name peers by internal names. An allow-list is #1184. The
  addressed actor is found first, so a post to an actor the node does not host fetches
  nothing.
- **Actor ids are compared normalised** (OID-01-006): the key's actor, the
  profile id and the `controller`, each without a trailing slash; the fetch goes
  to the normalised id.
- **The hosted actor's key is published, not stored.** Both profile routes,
  `/actors/{id}` and `/actors/{id}/profile`, list the actor's own
  `signing.published_multikey` and replace any key its record states: a
  published key other than the signing key fails every proof. Only the
  owner's routes compute it; a peer's key comes from its profile
  (SIG-05-002). `GET /actors/` lists each hosted actor the same way.
- **A profile typed `"Actor"` loses its key at parse.** The wire `as_Actor`
  ignores unknown fields, so it drops `assertionMethod`, while the five
  concrete actor types keep it. The fetch adapter refuses a profile typed
  `"Actor"` with a `VultronActorProfileFetchError` naming the generic type, not
  saying the actor published no key; the resolver logs it.
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

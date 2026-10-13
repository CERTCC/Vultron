---
title: Case Ledger Genesis Hardening — Secret Nonce and CASE_MANAGER Keys
status: active
kind: plan
tracks:
  - "#1162"
  - "#1156"
description: >
  Unbuilt hardening of the per-case genesis hash: the targeted-DoS gap a
  computable hash leaves, and the two candidate fixes (a secret nonce, or a
  CASE_MANAGER key in the hash input).
related_specs:
  - specs/case-ledger-processing.yaml
related_notes:
  - notes/case-ledger-authority.md
  - notes/encryption.md
---

# Case Ledger Genesis Hardening

The genesis hash in force is
`SHA-256(case_id | created_at | owner_actor_id)` (CLP-08-002, ADR-0117); see
[case-ledger-authority.md](case-ledger-authority.md) § "Per-Case Genesis Hash".
This note plans what replaces it in production.

## The gap

A case URI with a random UUID path satisfies CLP-08-006. But in a federated
protocol the inputs (`case_id`, `created_at`, owner id) can be observed, and then
anyone can compute the hash:

- Hash-chain integrity still holds: an attacker cannot forge or drop entries from
  a chain whose genesis hash a receiver stored independently.
- DoS amplification drops from "any case" to "a case whose metadata the attacker
  knows", but is not gone.

## Option A: secret nonce

Add a random value the CASE_MANAGER generates at case creation and never sends on
the wire to the hash input. It closes the targeted DoS vector even when metadata
leaks. Cost: the nonce must be stored securely and shared with legitimate
participants over an authenticated channel, which is key management.

## Option B: CASE_MANAGER keypair

Once actors have keypairs (#1162), hash the CASE_MANAGER's public key in place of
the owner id, or hash a key-signed commitment over the creation data. This:

- lets anyone holding the public key verify the ledger's origin without trusting
  the DataLayer's `case_id`;
- closes the targeted DoS vector, since the private key is never on the wire;
- lets third parties audit provenance from the public key alone.

Either form moves the anchor from the owner's id to a CASE_MANAGER key, so it
revisits ADR-0117 rather than extending it. Until one lands, CLP-08-002 is the
correct implementation.

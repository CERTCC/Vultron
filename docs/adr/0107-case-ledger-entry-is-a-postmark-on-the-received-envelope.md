---
status: proposed
date: 2026-09-25
deciders: Allen D. Householder
consulted: notes/wire-artifact-immutability.md, notes/case-ledger-authority.md, notes/datalayer-design.md, docs/adr/0074-wire-activity-artifact-immutability.md, docs/adr/0099-one-object-model-as2-is-a-serialization.md
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# A Case Ledger Entry Is a Postmark on the Received Envelope; References Resolve by Dereference

## Context and Problem Statement

A case ledger entry exists to record what arrived.
Its `payloadSnapshot` is replicated to every participant through `Announce(CaseLedgerEntry)`, and `entry_hash` covers it, so what the snapshot holds is what every replica treats as the event.

On the receive side, the snapshot is not what arrived.
It is rebuilt from the object graph after parsing, in six ways:

- ingress rehydration replaces nested objects with the receiver's stored copies;
- the snapshot builder keeps a fixed set of fields and re-dumps them by alias;
- bare references are inlined from the receiver's DataLayer (CLP-07-006);
- an actor field is patched in;
- `context` is written in from the case the receiver resolved;
- per-dimension adjudication merges its verdict into the recorded object (RSH-05-004, `BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE`).

Two snapshots are not rebuilt but invented: the embargo Lapse and the case-closed entries are hand-built dictionaries for activities nobody sent.

Each rewrite exists for a reason.
Most of them stand in for one missing capability: a replica cannot fetch an object it was sent only by `id`, so the CASE_MANAGER fills it in before recording.
The others reshape the record to match a decision (partial accept) or a convenience (hand-built snapshots).

ADR-0074 held that the received activity is immutable evidence, and relied on `frozen=True` to keep it so.
ADR-0099 detail 3 made every paired nested object a mutable core class, which `frozen` on the envelope does not reach, so that mechanism no longer holds the evidence either (#3584).

What should a ledger entry record, and how does a replica get the objects a bare reference names?

## Decision Drivers

- **Evidence**: a ledger that records the receiver's reconstruction cannot show what the sender claimed, which is the accountability the ledger exists for.
- **Replication fidelity**: every replica must be able to hold the same record, byte for byte, and recompute its hash.
- **Follow the protocol we are built on**: ActivityPub already answers "how does a receiver get an object it was sent by reference" — it dereferences the `id`. Each workaround Vultron adds instead is one more place the prototype diverges from it.
- **Never leave the system broken**: the change is staged so each step lands with the demos passing.

## Considered Options

1. **The entry is a postmark on the received envelope; replicas dereference bare references** — the CASE_MANAGER adds metadata around the exact received JSON and changes none of it.
2. **The CASE_MANAGER annotates the envelope** — keep the received JSON, and attach the objects it resolved alongside it so replicas need not fetch.
3. **Keep the reconstructed snapshot** — accept that the ledger records the receiver's view, and harden the rebuild instead.

## Decision Outcome

Chosen option: **"The entry is a postmark on the received envelope"**, because it is the only option under which the ledger records what was sent, and it resolves references with the mechanism ActivityPub already defines rather than one Vultron would have to maintain alone.

### Decision details

1. **The received JSON is sealed at parse.**
   `parse_activity` serializes the body before anything expands or validates it, and seals the text onto the parsed activity as its received evidence.
   The evidence is a `str`, which nothing can mutate in place, and every read returns a fresh copy.
   It is independent of the object graph, so no class configuration has to hold it (#3584; ADR-0099 records why `frozen` cannot).
   The text is the decoded body re-serialized, not the request bytes: keys, key order and values are the sender's, while whitespace, number spelling and escapes are not.
   Every replica re-serializes the same way, so the recorded snapshot is identical across replicas even though it is not the bytes on the wire.
2. **The ledger entry records the evidence verbatim.**
   The CASE_MANAGER adds envelope metadata (index, hashes, commit and receipt times, `case_id`) and changes nothing inside the snapshot.
   No field is dropped, re-dumped, inlined, patched, or merged.
3. **A replica dereferences a bare reference.**
   An object named only by `id` is fetched by an authenticated `GET` on the case host, and the effect that needs it is deferred until the object arrives.
4. **A sender inlines the objects it introduces.**
   A `Create` or `Add` of a new Note, status, participant, or report carries that object inline, so first delivery does not depend on a fetch.
   References to objects the receiver already holds may stay bare.
5. **A participant status update is accepted whole or rejected whole.**
   Partial accept records a status nobody sent, so it cannot coexist with detail 2.
   This retires per-dimension adjudication (RSH-05).
6. **Every recorded activity is one that was sent.**
   The embargo Lapse and case-closed snapshots become real activities the CASE_MANAGER emits through a factory, so the recorded blob is also the delivered blob (VM-08-003).

### Staging

Each step leaves a working system with the demos passing, so additive steps come first and each removal follows its replacement.

| step | change | issue |
|---|---|---|
| 1 | seal the received JSON at parse and carry it through ingress rehydration; nothing consumes it yet | #3584 |
| 2 | fetch-by-`id` endpoint on the case host; replica fetch-and-defer | #3739 |
| 3 | senders inline what they introduce; fix demo and factory bare-`id` paths | #3740 |
| 4 | whole accept or reject for participant status; retire RSH-05 | #3741 |
| 5 | ledger records the evidence verbatim; persist it for deferred replay; rewrite CLP-07-006 | #3742 |
| 6 | Lapse and case-closed become emitted activities | #3743 |

Tracked under Epic #3738.

Step 1 stops at ingress.
A deferred activity replayed by `StoredActivityIngressAdapter` is rebuilt from storage, which does not keep the evidence, so replay carries none until step 5 persists it.

### Consequences

- Good, because the ledger becomes evidence of what was sent, which every replica can hold identically and re-verify.
- Good, because a replica no longer depends on the CASE_MANAGER to have filled in every object, which is the precondition for selective disclosure and for a replica that joins late.
- Good, because the reference model is ActivityPub's, so interoperating implementations already understand it.
- Bad, because a replica can now wait on a fetch, so an effect can be deferred, and a fetch that never succeeds has to surface rather than hang.
- Bad, because entry hashes change at step 5, since the recorded snapshot changes; any stored chain from before that step does not verify against the new rule.
- Bad, because retiring partial accept removes a behavior the embargo-revision scenarios exercise, which step 4 has to replace, not just delete.

## Pros and Cons of the Options

### The entry is a postmark; replicas dereference

- Good, because nothing between receipt and recording can change what is recorded.
- Good, because it removes the six rewrites rather than hardening them.
- Bad, because it needs a fetch path and a deferral that do not exist yet (steps 2 and 5).

### The CASE_MANAGER annotates the envelope

- Good, because replicas never fetch, and the received JSON is still kept.
- Bad, because the annotation is the CASE_MANAGER's reconstruction under another name, so a replica cannot tell the sender's claim from the CASE_MANAGER's fill-in without a second verification rule.
- Bad, because it hardens the full-hydration shortcut into the protocol, where every later feature that wants a partial view would have to work around it.

### Keep the reconstructed snapshot

- Good, because nothing changes.
- Bad, because the record stays the receiver's view, and each new rewrite is one more thing a replica must reproduce exactly to verify a hash.

## Validation

- `test/architecture/test_wire_artifact_immutability.py` tampers with every class reachable in a parsed example activity and asserts the received evidence is unchanged (VM-08-002).
- `test/wire/as2/test_received_evidence.py` pins that the evidence is taken before expansion and is not reachable through the parsed object or the caller's `dict`.
- `test/adapters/driving/fastapi/test_ingress_received_evidence.py` pins that ingress rehydration carries the evidence, with bare references as received.
- Steps 2 to 6 each add the tests named in their issue.

## More Information

- [ADR-0074](0074-wire-activity-artifact-immutability.md) states the principle this ADR keeps: a received activity is evidence.
- [ADR-0099](0099-one-object-model-as2-is-a-serialization.md) records why its `frozen` mechanism no longer holds for nested objects.
- #3258 records the dereference gap that step 2 closes.

Source: ISSUE-3584.

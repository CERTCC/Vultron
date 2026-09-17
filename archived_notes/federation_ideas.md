---
title: Federation Design Ideas
status: superseded
superseded_by: docs/topics/future_work/federation.md
description: >
  Exploratory federation architecture ideas for Vultron captured from design
  discussion; input for future ADRs.
relevant_packages:
  - pydantic
  - rdflib
  - vultron/wire/as2
  - vultron/adapters
---

# Federation Design Ideas

> Captured from architecture discussion. Intended as input to design specs and
> ADRs.
>
> **Terminology (ADR-0088).** "CaseActor" throughout this file means the
> *concrete actor* that enacts `CVDRole.CASE_MANAGER` — the thing with an inbox,
> an outbox, key material and a URI that can migrate. That is the referent the
> glossary reserves the name for, so it is kept here rather than rewritten.
> It is **not** a synonym for the authority. Authority over a case is the
> `CASE_MANAGER` role and nothing else: no protocol logic may derive it from this
> actor's name, its URL shape, or where it is hosted (ARCH-24-004, CM-02-013).
> Where this file describes the authority *as such* — who may write canonical
> history, who a participant must route through — read "the CASE_MANAGER".
> Anything below that appears to make the name or hosting location load-bearing
> is superseded by ADR-0088.

---

## Context

A federated, open-source, containerized coordination service for multiparty case
handling (e.g., cross-vendor vulnerability tracking). Each organization runs
their own
instance, which acts as a gateway between their proprietary internal tracker and
a shared coordination protocol based on Activity Streams 2.0. Organizations
don't need to know anything about each other's internal systems — only how to
speak the shared protocol.

The model is closer to **email federation** (SMTP) or **Matrix homeservers**
than
to Mastodon-style public ActivityPub. Federation is bilateral/multilateral
between known, trusted peers, not open-web broadcast.

---

## Core Design Choices

### 1. Activity Streams 2.0 as the Protocol Vocabulary

- AS2 is used as the semantic vocabulary for all coordination messages ("
  sentences" of who did what to what and when).
- Custom object and activity types are defined as AS2 vocabulary extensions
  using JSON-LD `@context`.
- Full ActivityPub server machinery (WebFinger, NodeInfo, public outboxes) is *
  *not** required — AS2 is adopted as a vocabulary and message format, not as a
  public social protocol.

### 2. Actor / Inbox / Outbox Model

- The AS2 actor model (actors with inboxes and outboxes) is adopted as the
  coordination primitive.
- Each deployed instance has instance-level actors for peering and cold-contact
  delivery.
- Per-case coordination is handled by whichever actor holds `CVDRole.CASE_MANAGER`
  for that case — in the prototype, a **CaseActor** (see below).

### 3. Case Object Model

```text
Actor (global, instance-scoped)
  └── referenced by → Participant (case-scoped wrapper)
                           ├── roles (can have multiple: reporter, finder, 
                           vendor, coordinator, other, case owner, ...) 
                           ├── joinedAt, status, authorization level
                           └── associated Case

Case
  ├── attributed_to → Actor (current owning instance)
  ├── participants  → [Participant, ...]
  └── managed by   → the CASE_MANAGER role-holder
                       (in the prototype, a CaseActor; see note below)

CaseActor  (is a full AS2 "Service" Actor)
  ├── inbox    — receives activities from participants
  ├── outbox   — Case Journal (canonical, syncable history)
  └── streams/delivery — Delivery Log (operational, not synced)
```

- **Participant** is a wrapper object that points to a global Actor and carries
  case-scoped role and authorization metadata. An actor can be a participant in
  many cases with distinct (and sometimes multiple) roles in each.
- **CaseActor** is the coordination hub for a case. It owns the inbox, manages
  fan-out to participants, and maintains the authoritative case history — not
  because of what it is called, but because it holds `CVDRole.CASE_MANAGER`.
  Note that this sketch's original "1:1 with Case" framing is wrong: one actor
  enacts the role for *many* cases, one per container rather than one per case
  (CP-08-002/003, #1872). A per-case identity was tried and abandoned — it was
  unhostable by construction, so its delivery 404'd.

### 7. Relay Pattern (Announce Extension)

When CaseActor relays a participant's activity to other participants, it wraps
and re-signs it as a AS2 `Announce`:

```json
{
  "type": "Announce",
  "id": "https://vendorb.com/cases/1234/actor/outbox/relay/88",
  "actor": "https://vendorb.com/cases/1234/actor",
  "published": "2025-03-08T12:00:00Z",
  "vultron:journalSeq": 3,
  "vultron:journalPrev": "hash-of-journal-seq-2",
  "to": "https://vendora.com/users/alice",
  "object": {
    "type": "Create",
    "actor": "https://vendora.com/users/alice",
    "object": {
      "type": "Note",
      "content": "Reproduced on version 4.2"
    },
    "signature": "...alice's original signature..."
  },
  "signature": "...caseactor's signature..."
}
```

- **Alice's inner signature**: proves the activity genuinely originated from
  Alice.
- **CaseActor's outer signature**: proves it was received and relayed by the
  authoritative hub, at a specific journal position.
- Recipients can verify both independently.
- `journalSeq` and `journalPrev` allow recipients to slot the relayed activity
  into the correct position in their local mirror without waiting for a pull
  sync.

### 9. Mirror Consistency Protocol

Delivered for the single-instance prototype — push/pull ledger replication, gap
detection, and hash-chain non-repudiation now live in
`specs/sync-ledger-replication.yaml` and `notes/participant-case-replica.md`.
Cross-instance mirror-consistency (federation across separate deployments)
remains future work; the original single-instance design sketch is archived at
`plan/history/2609/note/NOTES-federation-ideas--mirror-consistency-protocol.md`.

### 10. Instance Federation Model

- Federation is between **known, trusted peer instances** — not open-web
  discovery.
- Each instance is autonomous; it knows only its own internal tracker mapping.
- Instances communicate via HTTPS with authenticated transport.
- **Preferred transport auth**: mTLS (mutual TLS) between instances, handling
  authentication at the transport layer without per-message overhead.
- **Message-level authentication**: activities are signed with instance/actor
  keypairs for non-repudiation independent of transport.

### 11. Instance Identity and Trust

Proposed DNS-anchored trust model (analogous to DKIM + MX for email):

1. Each instance operator publishes a DNS TXT record at their domain containing
   their instance public key fingerprint.
2. Peering begins out-of-band (exchange of instance domain names via human
   channels).
3. The connecting instance fetches the DNS TXT record → verifies key
   fingerprint.
4. The connecting instance fetches `/.well-known/vultron-meta.json` → gets full
   public key, inbox URL, supported vocabulary extensions.
5. Key is verified against DNS TXT fingerprint.
6. Connecting instance POSTs a signed `Follow` AS2
   activity to the peer's instance inbox.
7. Peer verifies reciprocally, responds with `Accept` or `Reject`.
8. Both sides store the peered instance record locally.

**`/.well-known/vultron-meta.json`** fields (proposed):

- Instance public key
- Instance inbox URL
- Supported Vultron vocabulary version(s)
- Contact / operator info

### 12. Peering Handshake

- Out-of-band exchange is the trust bootstrap (organizational trust, not just
  cryptographic).
- **Invite token option**: Instance A generates a signed invite token, sends
  out-of-band. Instance B presents it with the peering request. Automates "did I
  invite this peer" verification without a directory.
- Peering itself is expressed as AS2 activities (`Follow` / `Accept` / `Reject`)
  between instance-level actors.

### 13. Delivery Architecture

- Each instance's outbound activities are written to a **durable delivery queue
  ** before transmission.
- Workers attempt HTTPS delivery to peer instance inboxes with retry/backoff.
- **Per-instance deduplication**: when CaseActor fans out to multiple
  participants on the same peer instance, delivery is deduplicated — one POST to
  the peer instance's shared inbox, not one per participant.
- In the prototype, delivery queue can be stubbed with synchronous delivery
  underneath, but the architecture should allow for async delivery with retries in production.
- Each instance exposes a **shared case inbox** (analogous to ActivityPub's
  `sharedInbox`) that receives activities on behalf of any local actor and
  distributes internally.

### 14. Connector / Adapter Architecture

- The containerized service is tracker-agnostic. It speaks only the Vultron AS2
  protocol.
- Each deployment ships the core service + a **connector plugin** specific to
  their internal tracker.
- Connectors are implemented as Python entry-point plugins (
  `importlib.metadata`), discovered at startup without modifying the core.
- The connector interface translates between internal tracker events and AS2
  activities in both directions.

---

## Open Questions

### CaseActor Migration on Ownership Transfer

When case ownership transfers, the CaseActor needs to move to (or be re-homed
at) the new owning instance. Options:

- **Migrate**: CaseActor URI changes, all participants notified of new address.
  Clean but complex. Requires careful handling of in-flight messages during
  the transition, and participants need to update their mirrors to point to
  the new CaseActor URI.
- **Proxy**: Old instance forwards to new CaseActor. Simple but creates ongoing
  dependency on old instance. Not recommended because it can create a
  fragile chain of dependencies if ownership transfers multiple times.
- **HTTP redirect + AS2 Move**: CaseActor URI stays canonical, new instance
  handles it, old instance returns HTTP 301. Borrows from ActivityPub actor
  migration. Probably most pragmatic.
- **New CaseActor**: New instance creates a new CaseActor, old one is frozen.
  Clean but loses continuity in the CaseActor's identity and history.
  CaseActor key material would need to be regenerated, which could
  complicate signature verification across the ownership transfer.

### Participant Activity Routing / Filtering

The Participant wrapper's role metadata should control which Journal activities
each participant receives. The routing rules (e.g., observers get fewer updates
than assignees) need to be formally specified. Where does this logic live — in
the Participant object itself, or in CaseActor policy? It would be more
consistent if the CaseActor had a role-based rule set that it applies when
deciding which activities to relay to which participants. Stubbing this out
in the prototype with a simple rule (e.g., all participants get all
activities) is fine, but the architecture should allow for more complex
rules in the future. At one level, the CaseActor just needs a consistent
`for participant in participants: send_to_participant(participant,activity)`
and it's really internal to `send_to_participant()` how it decides whether
to actually send the activity or not based on the participant's role and the
activity type.

### Report Object Model

Reports are distinct from Cases. They are the object of the initial Offer
that starts the process, and a Case is only created when the Offer is accepted.
Two potential formats are already known: plain text and CSAF-formatted JSON.
Other formats may be added in the future.

Unclear how to resolve when a Report is `Offer`ed to multiple recipients
simultaneously. Presumably in this situation each recipient could choose to
`Accept` then create a new Case from the same Report. This could be awkard
for the reporter, but it's a bit of an *own-goal* on the recipient's side to
submit the same Report to multiple recipients without receiving any feedback
from the first one. The protocol should allow for this to happen, but it is
expected to be rare in practice because it's not a great look for the
recipient to be doing this. (Instead, they should probably create their own
Case and invite multiple vendors to it, with the option to transfer case
ownership to one of the vendors in the future if they want to delegate the
coordination role.)

However,
the multiple Offers from one report scenario does raise the question of
how things
should work when a reporter makes an `Offer` that is unresponded to for a
period of time, and then the reporter decides to submit an `Offer` of the
same Report (should probably be a new `Offer` ID, so the "Offer ID" should
be unique to the report/recipient pair at least, if not just unique every
time it's submitted). The "vendor didn't respond, so I'll try asking a
coordinator for help" scenario is rather common in practice, much moreso
than "I'll ask multiple vendors to coordinate this at the same time".

A case
merge mechanism might be a way to resolve this. If the second offer is
accepted followed by the first offer being accepted, then one of the cases
could be merged into the other. We would need to design exactly how one case
merges into another -- do they reconcile journals (this seems complex), or does
one case just get frozen into a read-only section of the other case and
perhaps leave some breadcrumb redirects behind to cause access to the frozen
case to be redirected to the merged case? The second option seems more
practical, but more specification will be necessary.

### Directory Service

A voluntary public registry for instance discovery is desirable but secondary to
the peering protocol. Open questions:

- Who operates it? (A neutral foundation, a git repo, a DNS zone?)
- Is it just a list of domain names (with trust verified via DNS TXT), or does
  it carry richer metadata?
- How are stale/offline instances handled?

### Shared Vocabulary Governance

Custom Vultron vocabulary extensions need a versioning and governance story:

- How are new activity/object types proposed and ratified?
- How do instances negotiate which vocabulary versions they support during
  peering?
- What is the `@context` URI and who hosts the JSON-LD context document?

### Multi-Party Fan-out Ordering

When CaseActor fans out a Journal entry to N peer instances, delivery is not
instantaneous. Participants on different instances may see activities in
different orders temporarily. Is eventual consistency acceptable, or does the
protocol need stronger ordering guarantees for multi-party coordination
correctness?

Eventual consistency seems fine for now and we should probably make sure
that things work without requiring strong arrival ordering guarantees.
Note that the `journalSeq` fields permit participants to recognize that
they might be missing data if they observe discontinuities in the sequence,
so they can trigger a pull sync to fill in the gaps.

### Delivery Receipts

Should participants send acknowledgment activities back to CaseActor on receipt?
This would allow CaseActor's Delivery Log to record confirmed delivery vs.
best-effort delivery, and enable smarter retry logic. Cost: additional message
volume. It seems like Receipts should probably be optional (MAY or SHOULD, not
MUST). In the prototype, we can skip implementing Receipts and just log delivery
attempts in the Delivery Log, but the architecture should allow for Receipts to be
added in the future without breaking the core protocol. Possible receipt
activity types: `Read` might be too strong (implies the participant actually
processed the activity), but a `Receive` or `Ack` activity could be a
lightweight confirmation that the activity was delivered to the
participant's inbox.

---

## Python Stack Notes

Candidate packages for implementation (not yet decided):

| Concern                      | Candidate                                                 |
|------------------------------|-----------------------------------------------------------|
| JSON-LD / AS2 processing     | `pyld`, `rdflib`                                          |
| HTTP transport               | `httpx` (with mTLS), `aiohttp`                            |
| Inbox endpoint               | `FastAPI`                                                 |
| Delivery queue / retry       | `Celery + Redis` or other TBD                             |
| Activity store               | MongoDB                                                   |
| AS2 type modeling            | `pydantic` (custom types serialize to valid AS2)          |
| Signing / keypairs           | `cryptography`                                            |
| Plugin / connector discovery | `importlib.metadata` entry points                         |
| Case state machines          | `transitions`, or `temporalio` for long-running workflows |

Full ActivityPub server libraries (`bovine`, `pyfed`) are likely too opinionated
for this use case. The above is a composable stack built around AS2 as a
*vocabulary* rather than full ActivityPub as a protocol, although some core
concepts from ActivityPub (actors, inboxes, outboxes) are still adopted as primitives.

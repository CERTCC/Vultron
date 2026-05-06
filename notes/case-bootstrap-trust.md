---
title: Case Bootstrap Trust — Implementation Notes
status: active
description: >
  Design notes for trust establishment at non-owner sites: creator-signed
  bootstrap for the original report path, invite-based bootstrap for
  late joiners, and CaseActor authority after trust establishment.
related_specs:
  - specs/case-bootstrap-trust.yaml
  - specs/participant-case-replica.yaml
  - specs/actor-knowledge-model.yaml
  - specs/case-management.yaml
related_notes:
  - notes/participant-case-replica.md
  - notes/activitystreams-semantics.md
  - notes/actor-knowledge-model.md
relevant_packages:
  - vultron/core/use_cases/received
  - vultron/core/use_cases/triggers
  - vultron/adapters/driving/fastapi
  - vultron/wire/as2/factories
---

# Case Bootstrap Trust — Implementation Notes

**Relates to**: `specs/case-bootstrap-trust.yaml`

**Source**: 2026-05-06 design conversation about #440 and #457.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| What establishes first trust for the original report-submission path? | The case creator sends a one-time `Create(VulnerabilityCase)` to the report submitter. | The report submitter already knows who received the report; the bootstrap reuses that trust anchor to introduce the CaseActor safely. |
| Is `Announce(VulnerabilityCase)` still the first snapshot for that path? | No. After bootstrap, later snapshots come from the CaseActor via `Announce`. | Keeps initial trust establishment separate from ongoing single-writer replication. |
| What must be in the bootstrap payload? | A full case snapshot naming the case creator/owner, the CaseActor, and the report submitter when they are already in the loop. | The receiver needs both the case state and the identities required for future trust checks. |
| What roles should those participants carry? | Case creator/owner gets `CASE_OWNER`; CaseActor gets `COORDINATOR`. | Distinguishes ownership from coordination authority. |
| Is an extra ack needed before CaseActor updates are trusted? | No. Local validation of the bootstrap is enough. | Avoids an unnecessary extra round trip. |
| What if a CaseActor update arrives before bootstrap? | Queue briefly, do not apply it, then drop and warn if bootstrap never arrives. | Tolerates reordering without making ordering skew a protocol failure. |
| Who gets the replay request if bootstrap times out? | The original report receiver / case creator. | The CaseActor is not trusted yet; the replay request asks for the trust-establishing message. |
| How do late joiners establish trust? | `InviteActorToCase` from the case creator establishes trust; then the CaseActor may `Announce` the case. | Late joiners have no prior report relationship to anchor trust. |
| Can ordinary updates replace the trusted CaseActor? | No. CaseActor rotation requires an explicit transfer workflow. | Prevents silent authority takeover. |
| Do encrypted/authenticated DMs replace this bootstrap? | No. They secure transport, but they do not authorize a newly introduced CaseActor for a case. | Sender authenticity alone is weaker than case-specific authority. |

---

## Two Bootstrap Paths

### 1. Original report-submission path

The original report submitter already has a trust anchor: they know who
received the report. The bootstrap uses that known actor to introduce the
case and its CaseActor.

```text
report_submitter -> Offer(VulnerabilityReport) -> report_receiver
report_receiver == case_creator

case_creator -> Create(VulnerabilityCase full snapshot) -> report_submitter
report_submitter validates:
  - sender == report_receiver
  - case references the submitted report
  - case identifies the CaseActor

CaseActor -> Announce(VulnerabilityCase updates) -> report_submitter
```

### 2. Late-joiner path

Late joiners do not have a prior report exchange with the case creator, so the
creator-signed invite becomes the trust-establishing message.

```text
case_creator -> InviteActorToCase -> late_joiner
late_joiner validates invite + CaseActor identity
late_joiner -> Accept(InviteActorToCase) -> case_creator
CaseActor -> Announce(VulnerabilityCase full snapshot) -> late_joiner
```

---

## Required Bootstrap Payload Shape

For the original report-submission path, the bootstrap `Create(VulnerabilityCase)`
should already contain enough information for the receiver to accept future
CaseActor updates without another handshake:

1. The full inline `VulnerabilityCase`
2. A participant record for the case creator / owner with `CASE_OWNER`
3. A participant record for the CaseActor with `COORDINATOR`
4. A participant record for the report submitter when they are already a live
   participant in the case
5. A reference to the submitted report so the receiver can link
   report-to-case state

The important consequence is that the CaseActor is not merely an opaque
service reference. It is an identity the receiver must learn and bind to the
case during bootstrap.

---

## Trust Anchors to Persist

After a valid bootstrap, persist all of the following together:

- `report_id -> case_id`
- `case_id -> trusted_case_creator_id`
- `case_id -> trusted_case_actor_id`

This prevents the receiver from having to re-derive trust from later traffic
and gives handlers a stable basis for rejecting spoofed or stale senders.

---

## Out-of-Order Handling

Permanent rejection of pre-bootstrap CaseActor messages is cleaner, but it
makes delivery order part of protocol correctness. The agreed design instead
uses a short bounded queue:

1. A CaseActor message arrives before bootstrap.
2. The receiver verifies that the CaseActor is not yet trusted for this case.
3. The message is queued briefly and remains unapplied.
4. If bootstrap arrives in time, normal validation may resume.
5. If bootstrap does not arrive, drop the queued message, log a warning, and
   ask the case creator to replay bootstrap.

The replay request should be a generic `Question` directed to the original
report receiver / case creator. The semantics are "please resend the
bootstrap `Create(VulnerabilityCase)` for this report/case relationship."

---

## Migration Guidance

This design supersedes the non-owner bootstrap assumptions currently written in
`notes/participant-case-replica.md` and the corresponding PCR bootstrap rules:

- Original participants do **not** start with `Announce(VulnerabilityCase)`
  from the CaseActor.
- `Create(VulnerabilityCase)` is no longer forbidden as a snapshot vehicle in
  all cases; it is allowed exactly once for creator-signed bootstrap on the
  original report path.
- Late joiners still converge on CaseActor-authored `Announce` after their
  invite-based trust handoff.

When implementation work begins, update these call sites consistently:

1. Case creation at report receipt
2. Outbound bootstrap activity construction
3. Participant-side bootstrap validation and trust persistence
4. Unknown-context / pre-bootstrap queueing and replay request behavior
5. Invite-to-case handling for late-joiner trust establishment

---

## Layer and Import Rules

- Trust-establishment rules belong in core use-case / behavior logic, not in
  FastAPI routers.
- Outbound bootstrap activities must be built through
  `vultron.wire.as2.factories`, not by importing internal activity subclasses.
- Persisted trust anchors should live in core models / ports, not in
  wire-specific helper objects.
- Transport security checks may support the decision, but they must not become
  the sole authority check for a new CaseActor.

---

## Testing Patterns

```python
def test_bootstrap_create_establishes_trusted_case_actor(
    dl, report_submitter, report_receiver, submitted_report, bootstrap_activity
):
    event = build_event(bootstrap_activity, actor_id=report_submitter.id_)
    CreateVulnerabilityCaseReceivedUseCase(dl, event).execute()

    trust = dl.read(case_bootstrap_trust_id(submitted_report.id_))
    assert trust.trusted_case_creator_id == report_receiver.id_
    assert trust.trusted_case_actor_id is not None
```

```python
def test_pre_bootstrap_case_actor_announce_is_queued_not_applied(
    dl, queue_dl, case_actor_announce
):
    process_inbox_item(case_actor_announce, dl, queue_dl)

    assert local_case_not_updated(dl, case_actor_announce.context)
    assert queued_for_bootstrap(queue_dl, case_actor_announce.id_)
```

```python
def test_late_joiner_invite_establishes_case_actor_trust(
    dl, invite_activity, announce_activity
):
    InviteActorToCaseReceivedUseCase(dl, build_event(invite_activity)).execute()
    AnnounceVulnerabilityCaseReceivedUseCase(
        dl, build_event(announce_activity)
    ).execute()

    assert late_joiner_replica_created(dl, announce_activity.context)
```

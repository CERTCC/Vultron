---
source: CONCERN-3274
timestamp: '2026-09-16T20:13:29.570418+00:00'
title: First-contact replica seeding has no trust anchor against a fabricated case
  roster
type: learning
---

## Context

Surfaced by #3273 while implementing ADR-0088. Not a regression — a gap the
previous code hid behind a signal that was itself wrong.

`AnnounceVulnerabilityCaseReceivedUseCase` decides whether an inbound
`Announce(VulnerabilityCase)` may seed a local replica. At **first contact** the
case is not in the local store, so there is no locally-derived roster to check
the sender against. The check therefore falls back to the roster carried in the
announced payload (CP-09-004 embeds participants inline).

## The gap

That roster is supplied by the sender. It catches the realistic imposter — an
actor replaying or forwarding a *legitimate* case whose roster names somebody
else as the authority — but a wholly **fabricated** case naming the sender as its
own `CVDRole.CASE_MANAGER` passes. Nothing currently available at first contact
can refute it.

The previous `Service`-hosting check was not actually better: it only answered
when the receiver had already written a CaseActor `Service` for that case, and it
keyed off hosting location, which ADR-0088 established is not evidence of
authority (ARCH-24-004, CM-02-013). It gave the appearance of a guard in a
narrower window.

## Resolution

No legitimate protocol sequence delivers an unsolicited first-contact
`Announce(VulnerabilityCase)` — one always follows either a
`Create(VulnerabilityCase)` bootstrap (sets `VultronReportCaseLink.trusted_case_actor_id`)
or an `InviteActorToCase` exchange (requires an invite trust anchor on the
invitee's side). The permissive fallback (`_announced_case_manager_id`) must be
removed; the unseeded authority check must fail closed when no prior local record
exists. The invite path also requires a trust anchor to be written when the
invitee processes an incoming `InviteActorToCase`.

**Resolved**: 2026-09-16 — implementation tracked in #3298.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3297>.
Spec: `specs/participant-case-replica.yaml` (PCR-03-004, PCR-07-010).
Notes: `notes/participant-case-replica.md`.

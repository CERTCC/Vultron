---
source: CONCERN-3106
timestamp: '2026-09-03T20:20:41.912375+00:00'
title: Case closure advances only the leaver's RM; bystanders retain their rung
type: learning
---

## Original Concern

Case closure force-advances a departing participant's RM state to `RM.CLOSED`
regardless of the rung its RM machine is on. `RM.CLOSED` is reachable only from
`ACCEPTED`, `INVALID` or `DEFERRED`, so a participant at `START`/`RECEIVED`/`VALID`
is moved through a transition the protocol does not have. The concern asked
whether case closure should touch participant RM state at all, and posed four
questions (write RM at closure? what carries the closure signal? correct end
state for a never-triaged participant? does fan-out differ from self-leave?).

Surfaced by #3050, which composed the ParticipantStatus write rules into one
evaluator that gave `CreateParticipantStatusNode` an RM check for the first time;
three call sites failed on `START → CLOSED` and were exempted via `force_rm_state`.

## Resolution (2026-09-03)

The behavior was **already correct**; only half the governing principle was
written down. No behavior change was required — the resolution is spec + docs +
regression pins.

**Principle (now CM-23-012, MUST):** A `Leave(VulnerabilityCase)` advances only
the leaving actor's own RM state to `RM.CLOSED`, regardless of rung — because a
`Leave` is that actor's own self-declaratory closure act (ADR-0084). Owner-close
is a case-level *write boundary* (ADR-0085): it advances only the Owner + Case
Actor (CM-23-002) and never advances bystander participants, which retain their
last RM state ("the library closed before every book was returned").

Answers: (1) yes, but only for the leaver, and it is sanctioned self-declaration;
(2) moot — the all-participants-RM.CLOSED derivation stays, and owner-close emits
`case_fully_closed` directly; (3) the never-triaged bystander stays exactly where
it is — no distinct "disengaged" state needed; (4) same principle — the fan-out
only replicates the single departing actor's own Leave across replicas, never a
bystander.

Verified structurally: the only three `force_rm_state` sites each target one
named actor (leaver, or Case Actor on owner-close), and no participant-iterating
close path exists — so a bystander at `RECEIVED`/`VALID` cannot be forced to
`CLOSED`. The `force_rm_state` override is thus sanctioned, not a standing
violation; its caveats and `notes/domain-validation.md` were reframed
accordingly, keeping the shrink-only pin.

**Resolved**: 2026-09-03 — no follow-on implementation issues; the resolution is
fully contained in the docs PR.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3150>.
Spec: `specs/case-management.yaml` (CM-23-012).
Notes: `notes/domain-validation.md`.

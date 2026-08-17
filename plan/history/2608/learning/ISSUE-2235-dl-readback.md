---
title: "Comments on the DataLayer read-back claim it returns wire-format objects; ADR-0034 says core. The read-back may be vestigial"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2235-dl-readback
signal: concern
---

Two places on the participant-status paths save a `ParticipantStatus` and then
immediately read it back from the DataLayer before appending it to
`participant.participant_statuses`, with a comment explaining that the read-back
is needed "to obtain the vocabulary-typed (wire-format) version" — the claim
being that appending a core-model instance to a list declared as
`list[WireParticipantStatus]` makes Pydantic serialize defaults instead of actual
values. The comment now lives in
`vultron/core/behaviors/sync/nodes/participant_status_effect.py`; an equivalent
one was in `status/nodes/append.py`.

ADR-0034 says the DataLayer port returns **core** domain objects, and that is
what `SqliteDataLayer.read()` was observed to do while diagnosing ISSUE-2235: a
read-back `ParticipantStatus` has `.rm` / `.vfd` dimension objects, not the flat
`.rm_state` / `.vfd_state` of the wire model. So the stated reason for the
read-back cannot be right as written.

What is not established is whether the read-back is therefore *unnecessary*. It
may still be doing something real (normalizing through the vocabulary registry,
or catching a save failure), or it may be a leftover from before ADR-0034 that
now costs an extra query per apply. I did not change it — ISSUE-2235 had no
reason to touch it and the round-trip is load-bearing for the tests as they
stand.

Cost paid this session: the misleading comments sent the initial diagnosis toward
a wire/core serialization theory before the actual all-or-nothing control-flow
defect was found. Someone should determine which of the two — the comment or the
read-back — is the thing that is wrong, and delete it.

**Promoted**: 2026-08-17 — captured in GitHub #2321 (Concern: vestigial read-back contradicts ADR-0034).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.

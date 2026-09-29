---
title: "ARCH-12-003's rationale cites ADR-0099 detail 7 as the argument it enforces, while its MUST does the opposite of the detail's second sentence — and the ADR graduated to accepted with the contradiction suppressed"
type: learning
timestamp: "2026-09-29T20:30:00Z"
source: ISSUE-3888
signal: spec-contradiction
---

ADR-0099 detail 7 says: recognised fields are validated strictly, and
"unrecognised fields are set aside before validation, **not rejected** — AS2 is
designed to be extended, and refusing on an unknown key would make Vultron
unable to federate with any implementation that adds a property." Detail 8 says
every set-aside field is logged at INFO with a WARNING on a near miss.

ARCH-12-003 (MUST) says core types MUST resolve `extra="forbid"` "so that an
unrecognised key raises", and its rationale names detail 7 as "where that
argument attaches" and `forbid` as "its enforcement". The code matches the spec:
`CoreObject` refuses an unknown key on every path, inbound message slots
included (measured: `VulnerabilityCase.model_validate({..., "fooBar": 1})`
raises), and `as_Base` keeps Pydantic's default `extra="ignore"`, so an unknown
key on the wire envelope is dropped without a trace. No set-aside path and no
near-miss check exist anywhere under `vultron/`.

So the spec and the ADR each claim the other as support while requiring
opposite behaviour, and the ADR's own disposition row for #2940 said `forbid`
would be "re-scoped to the persistence path; inbound is covered by details 7
and 8" — which never happened. The federation argument in detail 7 has not been
answered anywhere in the record.

How it stayed hidden: #3491 graduated the ADR from `accepted-provisional` to
`accepted` when its migration issues closed, and added
`lint_suppress: [status_prose_contradiction]` because the body still said
"remains provisional". The suppression was meant for an ADR that *discusses*
provisional-ness; here it silenced the one gate that would have asked whether
the prose and the status agreed. Closing every issue under an ADR's epic is
evidence that the *work items* are done, not that each decision detail was
built — two of the ten were not, and nothing compared the details to the tests.

Open question (Gate 2, raised on PR #3898): which behaviour does the project
mean? (a) amend details 7/8 to adopt fail-loudly and answer the federation
argument in the ADR; (b) build set-aside + reporting and return the ADR to
`accepted-provisional` until it lands; or (c) leave `accepted` and track the gap
as work. Until one is chosen, ARCH-12-003 and ADR-0099 point at each other and
an agent implementing either reads the other as confirmation.

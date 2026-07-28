---
title: SE-07 spec gap — summary rendering when actor_uri is absent
type: learning
timestamp: 2026-07-28
source: ISSUE-1729
signal: spec-gap
---

SE-07 specifies phrase templates and slot names but does not describe rendering behaviour when the actor slot cannot be filled (i.e., `actor_uri=None` on a `CaseTimelineEvent`). The implemented approach strips the leading em-dash prefix (`"— "`) from the rendered phrase and capitalises the resulting verb, producing e.g. `"Validated the report"` rather than `"— validated the report"`.

This behaviour should be back-ported into SE-07 (or a new sub-requirement SE-07-005) so future renderers and display helpers agree on the no-actor fallback contract.

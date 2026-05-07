## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-05-06 PCR — Replica seeding and deferred inbox replay

- First-time `Announce(VulnerabilityCase)` seeding cannot require a locally
  stored CaseActor yet; only reject the sender when a CaseActor for that case
  is already known and does not match.
- Unknown case-context activities need actor-scoped persisted deferral so the
  inbox can replay them after a later `Announce(VulnerabilityCase)` seeds the
  missing replica.
- Reporter-side report-to-case tracking benefits from a dedicated persisted
  link object so later announce handling can attach a received case replica to
  an earlier submitted report without scanning unrelated state.

## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-06-08 ISSUE-654 — Surrogate-key routing collision handling

- Surrogate-key resolution must treat ambiguous matches as errors, not
  first-match wins; otherwise actor/case lookups become non-deterministic when
  multiple canonical IDs share a tail segment.
- Case-key resolution should continue to short-key fallback even when
  `dl.read(key)` returns a non-case object; otherwise non-case IDs can shadow
  valid case keys and produce false 404/validation failures.
  
### 2026-06-08 ISSUE-757 — Shared participant lookup must support both case participant surfaces

- `VulnerabilityCase` fixtures and call sites are mixed: some populate
  `case_participants`, others rely on `actor_participant_index`.
- A shared BT lookup node that only scans `case_participants` regresses
  status workflows that previously used `actor_participant_index` checks.
- The reusable participant-finder logic should seed from the
  `actor_participant_index` direct hit first, then scan `case_participants`.

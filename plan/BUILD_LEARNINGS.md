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

### 2026-06-08 ISSUE-718 — Shared-inbox stubs must fail fast with a concrete type

- A docstring-only adapter stub does not satisfy OX-11-004 because accidental
  imports/callers get no runtime signal.
- Stubbed transport adapters should define an explicit class and raise
  `NotImplementedError` in `__init__` with spec reference context so failures
  are immediate and diagnosable.

### 2026-06-08 ISSUE-750 — Embargo subtree decomposition must preserve idempotent side effects

- Decomposing a god node into sequential BT leaves can silently change
  duplicate-run behavior when side-effect leaves always execute.
- Preserve previous semantics explicitly with a blackboard flag that tracks
  whether the current execution actually initialized a new embargo.
- When moving EM transition logic to `EmbargoLifecycle.propose_embargo`,
  keep event creation and participant-seeding behavior aligned with existing
  duplicate-report tests to avoid introducing warning-level regressions.

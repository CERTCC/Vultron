---
status: accepted
date: 2026-08-11
deciders: ahouseholder
consulted: specs/ci-security.yaml
informed: .github/workflows/
---

# CI Failure Alerting via GitHub Issues on Main-Branch and Scheduled Workflows

## Context and Problem Statement

CI failures on `main` (push-triggered and scheduled workflows) are not reported
anywhere. The team only finds out when someone manually checks the Actions tab or
notices a broken badge. Broken `main` can persist for days; developers stack PRs
on a broken base; scheduled workflow failures (sweeper, quarterly tag) have zero
visibility. The root cause is a missing alerting contract: no structured feedback
loop exists from CI failure to the issue tracker.

See CONCERN-2132.

## Decision Drivers

- Failures on `main` must produce a visible, trackable signal in the issue tracker.
- Recovery must close the signal automatically so the tracker reflects current health.
- The solution must be self-contained: no external services (Slack, email) whose
  configuration can drift or break silently.
- The solution must be maintainable: a shared composite action avoids per-workflow
  divergence as new workflows are added.
- The signal must be deduplicated: one open issue per failing workflow, not a new
  issue per run.

## Considered Options

1. **GitHub Issues via a shared `notify-failure` composite action** (chosen)
2. External notification (Slack webhook / email via third-party action)
3. No dedicated notification — rely on GitHub notification subscriptions and status
   badges only (status quo)

## Decision Outcome

Chosen option: **Option 1 — GitHub Issues via `notify-failure` composite action**,
because the issue tracker is already the team's single source of truth for work
items; filing a failure issue there creates a trackable, closeable signal without
any external service dependency.

The composite action lives at `.github/actions/notify-failure`. Every qualifying
workflow (push to `main` or `schedule` trigger) wires two steps: one conditioned
on failure (file/update an issue) and one conditioned on success (close the
matching issue). Each step calls the composite action with a `mode` input
(`notify` vs `close`). Keeping the two steps separate avoids embedding
workflow-status detection logic inside the action itself — the caller's
`if: failure()` / `if: success()` conditions handle that entirely.

The `ci:main-failure` label is reserved for this mechanism; the label description
documents that it is bot-managed.

### Consequences

- **Good**: Failures are visible in the issue tracker where the team already
  triages work — no context switch to the Actions tab required.
- **Good**: Recovery is automatically tracked; issues close when the workflow
  next passes.
- **Good**: Deduplication (one open issue per workflow) keeps the tracker clean
  across repeated failures.
- **Good**: A shared composite action keeps all workflows consistent; adding a
  new qualifying workflow is a one-line change.
- **Good**: No external service dependency; the only requirement is the standard
  `GITHUB_TOKEN` already available to every workflow.
- **Neutral**: Requires `issues: write` permission on qualifying workflows. This
  is a minimal, standard permission for a bot-authored issue.
- **Bad**: Failure issues appear in the same tracker as feature/bug work. The
  dedicated `ci:main-failure` label is the mitigation — it keeps the signal
  filterable and clearly distinct from human-authored issues.

## Validation

Compliance is verified by `test/ci/test_workflow_failure_notification.py` (to be
added as part of CISEC-05-004), which discovers all qualifying workflows and
asserts each includes the `notify-failure` step.

## Pros and Cons of the Options

### Option 1 — GitHub Issues via `notify-failure` composite action

- Good, because it is self-contained (no external service)
- Good, because failure signals are co-located with other tracked work
- Good, because recovery automatically closes the issue (feedback loop is complete)
- Neutral, because it requires `issues: write` permission on qualifying workflows

### Option 2 — External notification (Slack / email)

- Good, because it reaches the team wherever they are, not just in GitHub
- Bad, because it requires configuring and maintaining an external service
  (webhook URL, credentials, bot token) whose expiry or misconfiguration silently
  breaks alerting
- Bad, because notifications do not produce a trackable, closeable work item

### Option 3 — Status quo (rely on badge / subscriptions)

- Good, because it requires zero implementation effort
- Bad, because it provides no guarantee of visibility — developers must happen to
  look at the badge or be watching Actions emails
- Bad, because scheduled workflow failures (no commit or PR context) produce no
  natural notification signal

## More Information

- CONCERN-2132 — the motivating concern
- `specs/ci-security.yaml` CISEC-05-001 through CISEC-05-004 — generated spec
  requirements
- `.github/actions/notify-failure/` — implementation (to be added)
- `test/ci/test_workflow_failure_notification.py` — enforcement test (to be added)

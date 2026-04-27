---
status: accepted
date: 2026-03-30
deciders: ahouseholder
consulted: specs/ci-security.md
informed: plan/IMPLEMENTATION_PLAN.md
---

# Pin GitHub Actions to Full Commit SHAs with Version Comments

## Context and Problem Statement

GitHub Actions workflow files reference third-party actions using `uses:`
directives. When these references use mutable identifiers — version tags (e.g.,
`@v4`) or branch names (e.g., `@main`) — a compromised or modified upstream
action can silently inject malicious code into CI without any change to the
repository. This is a known software supply-chain attack vector.

The Vultron project uses GitHub Actions for CI (tests, linting, deployment,
link-checking) and needs a sustainable, low-maintenance policy that prevents
this class of attack while keeping pins up-to-date.

## Decision Drivers

- Prevent supply-chain compromise via tag or branch mutation in upstream
  actions.
- Keep the maintenance burden low so that pins do not become stale.
- Maintain human-readable context for each pin so that reviewers can
  understand which version is pinned without decoding a SHA.

## Considered Options

1. **SHA-pin every `uses:` line; use Dependabot for automatic pin updates**
2. SHA-pin only third-party (non-`actions/`) actions
3. Rely on version tags only (no SHA pinning)

## Decision Outcome

Chosen option: **Option 1 — SHA-pin every `uses:` line with Dependabot**,
because it provides complete protection against tag/branch mutation for all
actions (including first-party GitHub actions that are also susceptible),
while Dependabot automates the routine maintenance of keeping SHAs current.

All six workflow files under `.github/workflows/` have been updated to pin
every `uses:` reference to a full 40-character commit SHA. Each pin carries
an inline comment with the human-readable version tag (e.g., `# v4.1.0`).
Dependabot is configured (`.github/dependabot.yml`) to monitor
`github-actions` on a weekly schedule, providing automatic pull requests
whenever a new version is released.

An automated pytest test (`test/ci/test_workflow_sha_pinning.py`) verifies
at every CI run that no unpinned `uses:` line is accidentally introduced.

### Consequences

- **Good**: Every `uses:` line is immutable at the referenced commit,
  eliminating supply-chain risk from tag or branch mutation.
- **Good**: Dependabot opens PRs automatically when new versions are
  released, so pins do not become stale without manual tracking.
- **Good**: Inline version comments preserve human-readable context for
  code review.
- **Good**: The automated test (`CISEC-01-003`) catches any regression
  before it reaches `main`.
- **Neutral**: SHA-only references are harder to read without the version
  comment, mitigated by the mandatory comment requirement
  (`CISEC-01-002`).
- **Bad**: Dependabot may open PRs for patch and minor releases that have
  not been security-reviewed; reviewer discretion is required when merging
  pin-bump PRs.

## Validation

Compliance is verified continuously by
`test/ci/test_workflow_sha_pinning.py`, which:

1. Discovers all `.github/workflows/*.yml` files.
2. For each `uses:` line, asserts that the referenced version is a full
   40-character hexadecimal SHA (CISEC-01-001).
3. For each SHA line, asserts that an inline `# <version>` comment is
   present (CISEC-01-002).

This test runs as part of the standard `pytest` suite in every CI pipeline
execution.

## More Information

- `specs/ci-security.md` — full requirement set (CISEC-01-001 through
  CISEC-04-002)
- `.github/dependabot.yml` — Dependabot configuration
- `test/ci/test_workflow_sha_pinning.py` — automated enforcement test

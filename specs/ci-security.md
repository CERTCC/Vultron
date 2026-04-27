# CI Security Specification

## Overview

Requirements for securing CI/CD workflows and GitHub Actions usage in the
Vultron project.

**Source**: `plan/IMPLEMENTATION_PLAN.md` SECOPS-1, `.github/workflows/`
**Note**: Applies to all GitHub Actions workflow files under
`.github/workflows/`

---

## Action Version Pinning

- `CISEC-01-001` All `uses:` references in `.github/workflows/*.yml` MUST
  be pinned to a specific commit SHA rather than a version tag or branch name
  - SHA pinning prevents supply-chain attacks from tag mutation or
    branch-force-push
  - Exception: an ADR documenting the risk and justification is required for
    any unpinned reference
- `CISEC-01-002` Each SHA-pinned `uses:` reference MUST carry an inline
  comment identifying the corresponding human-readable version tag
  (e.g., `# v4.1.0`) to aid maintainability

## Secrets Management

- `CISEC-02-001` Workflow secrets and tokens MUST be stored in GitHub
  Secrets and MUST NOT appear in repository files
- `CISEC-02-002` The minimal set of permissions required MUST be declared
  explicitly via `permissions:` at the job or workflow level
  - Workflows MUST NOT use `permissions: write-all`

## Automated Pin Verification

- `CISEC-01-003` A CI verification test SHOULD confirm that all `uses:`
  lines in `.github/workflows/*.yml` reference a SHA hash rather than a
  mutable version tag or branch name, and that each SHA line carries the
  human-readable version comment required by CISEC-01-002
  - This test SHOULD be implemented as a Python script (e.g., parsing
    workflow YAML files) so it can run in the same CI environment as other
    project tests

## Artifact Integrity

- `CISEC-03-001` (MUST) CI workflows that download third-party artifacts or tools
  MUST verify signatures or checksums before using them
  - **Rationale**: Prevents supply-chain attacks via compromised artifacts

## Maintenance

- `CISEC-04-001` SHA pins SHOULD be reviewed and updated on a documented
  periodic cadence, at minimum when a security advisory is issued for the
  pinned action or when a new minor version is released
  - Where Dependabot is configured for GitHub Actions, it SHOULD be treated
    as the primary mechanism for keeping SHA pins current; the periodic
    manual review cadence is then a secondary backstop for cases Dependabot
    does not cover
- `CISEC-04-002` (MUST) When adding a new workflow step or action, the SHA pin and
  version annotation MUST be included before the step is merged to `main`

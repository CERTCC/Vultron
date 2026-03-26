# CI Security Specification

## Overview

Requirements for securing CI/CD workflows and GitHub Actions usage in the
Vultron project.

**Source**: `plan/IMPLEMENTATION_PLAN.md` SECOPS-1, `.github/workflows/`
**Note**: Applies to all GitHub Actions workflow files under
`.github/workflows/`

---

## Action Version Pinning (MUST)

- `CI-SEC-01-001` All `uses:` references in `.github/workflows/*.yml` MUST
  be pinned to a specific commit SHA rather than a version tag or branch name
  - SHA pinning prevents supply-chain attacks from tag mutation or
    branch-force-push
  - Exception: an ADR documenting the risk and justification is required for
    any unpinned reference
- `CI-SEC-01-002` Each SHA-pinned `uses:` reference MUST carry an inline
  comment identifying the corresponding human-readable version tag
  (e.g., `# v4.1.0`) to aid maintainability

## Secrets Management (MUST)

- `CI-SEC-02-001` Workflow secrets and tokens MUST be stored in GitHub
  Secrets and MUST NOT appear in repository files
- `CI-SEC-02-002` The minimal set of permissions required MUST be declared
  explicitly via `permissions:` at the job or workflow level
  - Workflows MUST NOT use `permissions: write-all`

## Artifact Integrity (SHOULD)

- `CI-SEC-03-001` CI workflows that download third-party artifacts or tools
  SHOULD verify signatures or checksums before using them
  - **Rationale**: Prevents compromised artifacts from entering the build
    pipeline

## Maintenance (SHOULD)

- `CI-SEC-04-001` SHA pins SHOULD be reviewed and updated on a documented
  periodic cadence, at minimum when a security advisory is issued for the
  pinned action or when a new minor version is released
- `CI-SEC-04-002` When adding a new workflow step or action, the SHA pin and
  version annotation MUST be included before the step is merged to `main`

---
title: "SECOPS-1 \u2014 CI Security: ADR + Automated SHA-Pin Verification\
  \ Test (2026-03-30)"
type: implementation
timestamp: '2026-03-30T00:00:00+00:00'
source: SECOPS-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 3572
legacy_heading: "SECOPS-1 \u2014 CI Security: ADR + Automated SHA-Pin Verification\
  \ Test (2026-03-30)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-30'
---

## SECOPS-1 — CI Security: ADR + Automated SHA-Pin Verification Test (2026-03-30)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:3572`
**Canonical date**: 2026-03-30 (git blame)
**Legacy heading**

```text
SECOPS-1 — CI Security: ADR + Automated SHA-Pin Verification Test (2026-03-30)
```

**Legacy heading dates**: 2026-03-30

**Task:** SECOPS-1 (PRIORITY-250 pre-300 cleanup)

**What was done:**

- Created `docs/adr/0014-sha-pin-github-actions.md`: ADR documenting the
  SHA-pinning policy (all `uses:` references must be pinned to a 40-char commit
  SHA with an inline human-readable version comment), the use of Dependabot as
  the primary maintenance mechanism, and the automated test as the continuous
  enforcement mechanism. References CISEC-04-001.
- Added ADR-0014 to `docs/adr/index.md`.
- Created `test/ci/__init__.py` and `test/ci/test_workflow_sha_pinning.py`:
  53 parametrised pytest tests covering every `uses:` line across all 6
  `.github/workflows/*.yml` files. Tests verify:
  - CISEC-01-001: reference is pinned to a full 40-hex-character SHA
  - CISEC-01-002: SHA line carries an inline version comment (e.g., `# v4.1.0`)

**Tests:** 1080 passed (+53 new), 5581 subtests passed.

**Commit:** 3e5b3079

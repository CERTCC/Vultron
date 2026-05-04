---
title: "DOCS-1 \u2014 Update `docker/README.md` (2026-03-19)"
type: implementation
timestamp: '2026-03-19T00:00:00+00:00'
source: DOCS-1
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2455
legacy_heading: "DOCS-1 \u2014 Update `docker/README.md` (2026-03-19)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-19'
---

## DOCS-1 — Update `docker/README.md` (2026-03-19)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2455`
**Canonical date**: 2026-03-19 (git blame)
**Legacy heading**

```text
DOCS-1 — Update `docker/README.md` (2026-03-19)
```

**Legacy heading dates**: 2026-03-19

**Task**: Update `docker/README.md` to accurately reflect the current
docker-compose services.

**What was done**:

- Replaced the outdated list of individual per-demo service entries
  (`receive-report-demo`, `initialize-case-demo`, `establish-embargo-demo`,
  `invite-actor-demo`, `status-updates-demo`, `suggest-actor-demo`,
  `transfer-ownership-demo`) with the consolidated `demo` service.
- Updated the "Running Demos" section to document the `DEMO` env-var
  non-interactive mode and the interactive shell mode.
- Listed all available `vultron-demo` sub-commands.
- Retained the Networking and Customizing sections unchanged.
- Linted with `markdownlint-cli2`: 0 errors.

**Result**: `docker/README.md` now accurately reflects the five services
(`api-dev`, `demo`, `test`, `docs`, `vultrabot-demo`) in the current
`docker-compose.yml`.

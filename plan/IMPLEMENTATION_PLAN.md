# Vultron API v2 Implementation Plan — Read-Only Index

> **Tasks have moved to GitHub Issues.**
> This file is a read-only index. Do not add new tasks here.

## Where to find work

- **Open issues**: <https://github.com/CERTCC/Vultron/issues>
- **Priority ordering**: [`plan/PRIORITIES.md`](PRIORITIES.md)
- **How tasks are selected**: `build` skill reads `PRIORITIES.md` for the
  top-priority group, then queries GitHub for open leaf Issues with that
  `group:` label.

## Migrated items

The deferred items that were tracked here have been migrated to GitHub Issues:

| Former ID | Issue | Description |
|---|---|---|
| USE-CASE-01 | [#422](https://github.com/CERTCC/Vultron/issues/422) | CloseCaseUseCase wire-type construction |
| USE-CASE-02 | [#423](https://github.com/CERTCC/Vultron/issues/423) | UseCase Protocol generic enforcement |
| EP-02/EP-03 | [#424](https://github.com/CERTCC/Vultron/issues/424) | EmbargoPolicy API + compatibility evaluation (PROD_ONLY) |
| AR-04/05/06 | [#425](https://github.com/CERTCC/Vultron/issues/425) | Job tracking, pagination, bulk ops (PROD_ONLY) |
| AGENTIC-00 | [#426](https://github.com/CERTCC/Vultron/issues/426) | Agentic AI integration (Priority 1000) |
| FUZZ-00 | [#427](https://github.com/CERTCC/Vultron/issues/427) | Fuzzer node re-implementation (Priority 500) |
| DEMOMA | [#387](https://github.com/CERTCC/Vultron/issues/387) | Multi-actor demo infrastructure (existing issue) |
| ARCH-VIOLATIONS | [#428](https://github.com/CERTCC/Vultron/issues/428) | Broader core→wire ARCH-01-001 violations |

New GitHub Actions workflow issues (from parallel-development migration):

| Issue | Description |
|---|---|
| [#429](https://github.com/CERTCC/Vultron/issues/429) | Stale-claim sweeper workflow |
| [#430](https://github.com/CERTCC/Vultron/issues/430) | size:S auto-merge workflow |
| [#431](https://github.com/CERTCC/Vultron/issues/431) | Docs-only auto-merge workflow |

## Completed work

See [`plan/history/`](history/) for the archive of completed implementation
work.

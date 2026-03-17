---
status: accepted
date: 2026-03-17
deciders: ahouseholder
---

# Remove API v1 and consolidate vocabulary examples into API v2

## Context and Problem Statement

The project has two API versions mounted side-by-side: `api/v1` (at `/api/v1`)
and `api/v2` (at `/api/v2`). The `api/v1` package consists entirely of stub
endpoints that return `vocab_examples` objects and have no business logic.
All real protocol behaviour lives in `api/v2`. The v1 stubs create confusion
about which API to use and add dead code to the project.

## Decision Drivers

- Reduce dead code and confusion about which API version is authoritative.
- Keep the vocabulary showcase / validation capability that v1 provided.
- Align with the hexagonal architecture where `api/v2` is the single driving
  adapter for HTTP.
- Simplify `vultron/api/main.py` by removing the v1 sub-application mount.

## Considered Options

- **Option A**: Keep `api/v1` as-is with a clear "vocabulary showcase" label.
- **Option B**: Migrate the `/examples/` endpoints from v1 into v2 as a
  `/examples/` subrouter, then remove v1.
- **Option C**: Deprecate and remove v1 with no migration of its endpoints.

## Decision Outcome

Chosen option: **Option B** — migrate the vocabulary-showcase endpoints into
the existing `api/v2/routers/examples.py` router and delete the `api/v1`
package.

The v2 examples router already covers `actors` and `notes`. It is extended to
include `reports`, `cases`, `cases/statuses`, `cases/participants`,
`cases/participants/statuses`, and `cases/embargoes` from v1. All other v1
stub routes (CRUD-style operations on actors, reports, cases, etc.) are
removed without replacement because they are fully superseded by the
inbox-based protocol implementation in v2.

### Consequences

- Good, because the codebase no longer contains ~1 000 lines of stubs.
- Good, because `/api/v2/examples/` provides a single place to explore and
  validate vocabulary objects.
- Good, because `vultron/api/main.py` no longer imports or mounts the v1 app.
- Bad, because any client that relied on `/api/v1/*` endpoints will need to
  update to `/api/v2/examples/*` (for the examples) or to the real v2
  protocol endpoints.

## Validation

- `uv run pytest --tb=short` passes with no regressions.
- `GET /api/v2/examples/reports`, `/api/v2/examples/cases`, etc. return
  valid example objects.
- `POST` to each examples endpoint validates an object through Pydantic.
- The `vultron/api/v1/` directory no longer exists.

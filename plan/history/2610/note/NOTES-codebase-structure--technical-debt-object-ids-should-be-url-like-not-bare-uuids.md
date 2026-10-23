---
source: NOTES-codebase-structure--technical-debt-object-ids-should-be-url-like-not-bare-uuids
timestamp: '2026-10-02T16:25:54.908531+00:00'
title: 'Technical Debt: Object IDs Should Be URL-Like, Not Bare UUIDs'
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered + redundant — generate_new_id() returns urn:uuid: or prefix/uuid IDs and surrogate-key routing exists; ADR-0010 records the decision
**Superseded by:** ADR-0010; vultron/wire/as2/vocab/base/utils.py generate_new_id(); notes/codebase-structure-fastapi-patterns.md surrogate-key routing

---

## Technical Debt: Object IDs Should Be URL-Like, Not Bare UUIDs

The `datalayer.read(key)` method and the `/datalayer/{key:path}` route use
`as_id` as the lookup key. Currently `generate_new_id()` returns a bare
UUID-4 string (e.g., `2196cbb2-fb6f-407c-b473-1ed8ae806578`) rather than a
full URL (e.g., `https://vultron.example/participants/2196cbb2-...`).

**Why bare UUIDs were used**: Avoids URL-encoding/escaping issues when
using object IDs as path segments in API routes (a full URL contains `/`
characters that are treated as path-segment separators by Starlette, even
after percent-encoding as `%2F`).

**Current tactical fix**: The `/{key:path}` Starlette path converter is used
throughout the FastAPI routers (actors, datalayer) to accept URL-form keys
with embedded slashes. See
[Starlette Path-Type Parameters for URL-Keyed Endpoints](#starlette-path-type-parameters-for-url-keyed-endpoints)
below.

**Deeper architectural goal**: Object IDs should be proper URL-like identifiers
per the ActivityStreams spec. The long-term resolution is to separate routing
identity from object identity by assigning each actor and case a stable,
locally-unique, routing-safe surrogate key (e.g., a UUID or slug) used in all
URL path segments while keeping the full IRI as the canonical `id` field inside
the object graph. This mirrors ActivityPub practice of using
`preferredUsername` for routing while the full actor IRI lives in the payload.

**Affected areas**:

- `generate_new_id()` in `vultron/wire/as2/vocab/base/utils.py` — add a default
  `prefix` based on object type
- Demo scripts and tests that assert on `as_id` format
- Any handler that constructs participant or case IDs inline

---

---
status: accepted
date: 2026-03-10
deciders:
  - vultron maintainers
consulted:
  - project stakeholders
informed:
  - contributors
---

# Standardize Object IDs to URI Form

## Context and Problem Statement

The Vultron ActivityStreams 2.0 (AS2) object model requires every object to
have an `id` field. The `generate_new_id()` utility in
`vultron/wire/as2/vocab/base/utils.py` currently returns a bare UUID-4 string
(e.g., `2196cbb2-fb6f-407c-b473-1ed8ae806578`) as the default `as_id` for
new objects. The AS2 specification and the Vultron object-IDs spec
(`specs/object-ids.yaml` OID-01-001) require that `id` values be full URI
identifiers. Bare UUIDs are not valid AS2 identifiers and will cause
interoperability problems once federation is implemented.

## Decision Drivers

- **AS2 compliance**: ActivityStreams 2.0 requires `id` to be an absolute
  IRI. Bare UUIDs are not IRIs.
- **Federation readiness**: Federated delivery requires globally unique,
  resolvable identifiers. Bare UUIDs cannot be resolved across systems.
- **Blackboard key safety**: py_trees blackboard keys derived from full-URI
  IDs must not use the raw URI (which contains slashes). Using the last path
  segment or UUID suffix as the key avoids hierarchical key-parsing issues
  (OID-03-001).
- **DataLayer compatibility**: The DataLayer uses `as_id` as the primary
  lookup key. Changing the default ID format is a forward-looking migration;
  any existing bare-UUID records are a prototype artifact.

## Considered Options

1. **`urn:uuid:` prefix** — `urn:uuid:{uuid4}` (e.g.,
   `urn:uuid:2196cbb2-fb6f-407c-b473-1ed8ae806578`)
2. **Configurable HTTPS base URL** — `https://{base}/{type}/{uuid4}` driven
   by a `VULTRON_BASE_URL` environment variable
3. **Continue using bare UUIDs** — defer the change

## Decision Outcome

Chosen option: **Configurable HTTPS base URL with `urn:uuid:` fallback**,
because:

- HTTPS URLs are the canonical AS2 `id` form and are directly resolvable.
- A configurable base URL (via `VULTRON_BASE_URL` env var) allows deployment
  flexibility without hard-coding a hostname.
- When `VULTRON_BASE_URL` is not set, the helper defaults to `urn:uuid:`
  form, which is a valid absolute IRI and avoids any need for a running HTTP
  server during development and testing.
- The `make_id()` helper in `vultron/api/v2/data/utils.py` (which already
  uses HTTPS base-URL form) becomes the shared canonical ID factory for all
  layers, satisfying OID-01-004.

### Consequences

- Good: all newly created objects carry globally unique, AS2-compliant `id`
  values.
- Good: `VULTRON_BASE_URL` enables environment-specific ID namespaces
  (dev / staging / production) without code changes.
- Good: `urn:uuid:` default keeps development and test setups self-contained.
- Neutral: existing bare-UUID records in prototype data stores remain usable
  during the prototype phase; a migration script is not required until
  production deployment (OID-04-002, PROTO-01-001).
- Bad: `generate_new_id()` now produces IDs that contain colons, which must
  not be used directly as py_trees blackboard keys (use the UUID suffix
  portion only — see OID-03-001).

## Validation

- Unit tests in `test/wire/as2/vocab/base/test_utils.py` assert that
  `generate_new_id()` returns a value starting with `urn:uuid:` or a
  configured HTTPS prefix.
- Unit tests in `test/api/v2/data/test_utils.py` confirm that `make_id()`
  produces HTTPS-prefixed IDs and that `BASE_URL` is read from
  `VULTRON_BASE_URL` when set.
- Code review: no new code should assign a bare UUID directly to `as_id`
  without wrapping it in a URI prefix.

## Pros and Cons of the Options

### `urn:uuid:` prefix

- Good: simple — no environment configuration required.
- Good: valid absolute IRI; accepted by AS2 parsers.
- Good: no slashes in the ID, so the full ID can be used as a path segment
  without percent-encoding.
- Neutral: not directly HTTP-resolvable.
- Bad: does not support the future federation model where IDs are resolvable
  URLs on actor servers.

### Configurable HTTPS base URL

- Good: IDs are HTTP-resolvable, matching the ActivityPub federation model.
- Good: per-environment namespacing via `VULTRON_BASE_URL`.
- Bad: IDs contain slashes; API routes must URL-encode or use query
  parameters for ID-based lookups.
- Bad: requires a configured hostname to produce meaningful IDs.

### Continue using bare UUIDs

- Good: no code changes required.
- Bad: violates AS2 spec; blocks federation.
- Bad: violates `specs/object-ids.yaml` OID-01-001.

## More Information

- `specs/object-ids.yaml` — normative requirements OID-01 through OID-04.
- `notes/codebase-structure.md` — "Technical Debt: Object IDs Should Be
  URL-Like, Not Bare UUIDs" section.
- `plan/IMPLEMENTATION_PLAN.md` — TECHDEBT-3.
- Related ADRs:
  - [ADR-0005](0005-activitystreams-vocabulary-as-vultron-message-format.md)
    — rationale for using AS2 as the wire format.
  - [ADR-0009](0009-hexagonal-architecture.md) — hexagonal architecture that
    separates wire format concerns from domain logic.

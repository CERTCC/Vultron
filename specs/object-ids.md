# Object ID Specification

## Overview

Requirements for the format and handling of object identifiers throughout
the Vultron system. Establishes full-URI IDs as the canonical form for all
ActivityStreams objects and DataLayer records.

**Source**: `plan/IDEATION.md` (ADR for standardizing Object ID format,
Update codebase to use full-URI IDs), `plan/IMPLEMENTATION_PLAN.md`
(TECHDEBT-3)
**Cross-references**: `case-management.md`, `handler-protocol.md`,
`behavior-tree-integration.md`

---

## ID Format (MUST)

- `OID-01-001` All ActivityStreams object IDs (`as_id`) MUST use full URI form
  - Acceptable forms: `https://example.org/objects/{uuid}` or
    `urn:uuid:{uuid}`
  - Bare UUIDs (e.g., `abc123`) MUST NOT be used as canonical IDs
- `OID-01-002` IDs MUST be globally unique within the system
- `OID-01-003` The canonical base URI for locally created objects MUST be
  configurable via an environment variable (`VULTRON_BASE_URL` or equivalent)
- `OID-01-004` Helper functions for constructing full-URI IDs from UUIDs
  MUST be provided in a shared utility module (e.g.,
  `vultron.as_vocab.utils.make_id`)

## DataLayer Handling (MUST)

- `OID-02-001` The DataLayer MUST store and retrieve objects using their
  full-URI `as_id` as the primary key
- `OID-02-002` `object_to_record()` MUST preserve the full-URI `as_id` when
  serializing objects to the DataLayer
- `OID-02-003` `record_to_object()` MUST reconstruct objects using the
  full-URI `as_id` stored in the record
- `OID-02-004` DataLayer lookups MUST accept full-URI IDs; bare UUIDs MUST
  NOT be accepted as valid lookup keys

## Blackboard Key Handling (MUST)

- `OID-03-001` Behavior Tree blackboard keys derived from object IDs MUST
  NOT use the raw full URI as the key
  - Use the last path segment or UUID portion (e.g., `object_{uuid}`) to
    avoid hierarchical key parsing issues in py_trees
  - **Cross-reference**: `behavior-tree-integration.md` BT-03-003

## ADR Requirement (SHOULD)

- `OID-04-001` An Architecture Decision Record MUST be created at
  `docs/adr/ADR-XXXX-standardize-object-ids.md` before migrating existing
  data
  - The ADR MUST cover: chosen canonical form, migration strategy, timeline,
    and backward-compatibility shims
- `OID-04-002` Any migration of existing bare-UUID records MUST be
  accompanied by a migration script or documented manual steps

## Verification

### OID-01-001, OID-01-002 Verification

- Unit test: All `as_id` values produced by factories contain `://` or
  `urn:` prefix
- Code review: No bare UUID assigned directly to `as_id` without URI wrapping

### OID-02-001 through OID-02-004 Verification

- Unit test: `object_to_record(obj)` round-trips to `record_to_object()`
  with identical full-URI `as_id`
- Unit test: DataLayer `read(bare_uuid)` raises `KeyError` or returns `None`

### OID-03-001 Verification

- Unit test: Blackboard key for object with URI id uses `_{uuid}` suffix
  form, not full URI

### OID-04-001 Verification

- Code review: ADR file exists and is referenced from `docs/adr/` index

## Related

- **Case Management**: `specs/case-management.md`
- **Handler Protocol**: `specs/handler-protocol.md`
- **BT Integration**: `specs/behavior-tree-integration.md` (BT-03-003)
- **Domain Model**: `notes/domain-model-separation.md`
- **Codebase Structure**: `notes/codebase-structure.md`
- **Implementation Plan**: `plan/IMPLEMENTATION_PLAN.md` (TECHDEBT-3)

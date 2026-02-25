# Embargo Policy Specification

## Overview

Requirements for a standardized embargo policy record associated with an
Actor profile. Allows actors to declare their default embargo preferences
so that coordinators can evaluate compatibility before proposing an embargo
or inviting an actor to a case.

**Source**: `plan/IDEATION.md` (Consider a standard format for default
embargo policies on Actor profiles)
**Cross-references**: `case-management.md`, `response-format.md`,
`agentic-readiness.md`

---

## Policy Record Format (MUST)

- `EP-01-001` An Actor profile MAY include a `embargo_policy` field
  containing a structured embargo policy record
- `EP-01-002` The embargo policy record MUST include the following fields:
  - `actor_id`: URI of the Actor to which the policy applies
  - `inbox`: URL of the Actor's ActivityPub inbox
  - `preferred_duration_days`: integer representing the Actor's preferred
    embargo duration in days
- `EP-01-003` The embargo policy record SHOULD include the following fields:
  - `minimum_duration_days`: minimum acceptable embargo duration in days;
    the Actor SHOULD reject embargoes shorter than this value
  - `maximum_duration_days`: maximum acceptable embargo duration in days;
    the Actor SHOULD reject embargoes longer than this value
  - `notes`: free-text description of the Actor's embargo preferences (e.g.,
    "prefer 45 days but consider shorter for critical vulnerabilities")
- `EP-01-004` The embargo policy record MUST be serializable as a Pydantic
  model and persisted in the DataLayer
- `EP-01-005` The embargo policy record MUST use full-URI IDs for `actor_id`
  - **Cross-reference**: `object-ids.md` OID-01-001

## API Endpoint (SHOULD)

- `EP-02-001` `PROD_ONLY` Each Actor SHOULD expose its embargo policy at
  `GET /actors/{actor_id}/embargo-policy`
  - Response MUST use the policy record format defined in EP-01-001 through
    EP-01-003
  - Response MUST return HTTP 404 if the Actor has not declared a policy
- `EP-02-002` `PROD_ONLY` The policy endpoint MUST be machine-readable
  (returns JSON) and MUST be listed in the Actor's ActivityPub profile under
  a well-known key (e.g., `vultron:embargoPolicy`)

## Policy Compatibility Evaluation (SHOULD)

- `EP-03-001` `PROD_ONLY` Before proposing an embargo or inviting an actor
  to join an existing embargo, the CaseActor SHOULD retrieve and evaluate
  the target actor's embargo policy for compatibility with the proposed
  embargo terms
- `EP-03-002` `PROD_ONLY` Compatibility evaluation MUST check that the
  proposed duration falls within the target actor's
  `minimum_duration_days`–`maximum_duration_days` range, if declared

## Verification

### EP-01-001 through EP-01-004 Verification

- Unit test: `EmbargoPolicy` Pydantic model validates required fields
- Unit test: Serialization round-trip via `object_to_record` preserves all
  fields

### EP-02-001 Verification

- `PROD_ONLY` Integration test: `GET /actors/{id}/embargo-policy` returns
  200 with valid JSON for an actor with a declared policy
- `PROD_ONLY` Integration test: Returns 404 for an actor without a policy

### EP-03-001, EP-03-002 Verification

- `PROD_ONLY` Unit test: Compatibility check returns `True` when proposed
  duration is within range, `False` otherwise

## Related

- **Case Management**: `specs/case-management.md`
- **Response Format**: `specs/response-format.md`
- **Agentic Readiness**: `specs/agentic-readiness.md`
- **Object IDs**: `specs/object-ids.md`
- **IDEATION Notes**: `plan/IDEATION.md` (embargo policy section)
- **Prior Art**: RFC 9116 (security.txt), disclose.io DIOSTS and DIOTerms

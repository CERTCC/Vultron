# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## 2026-03-06 (gap analysis refresh #13)

### `Publication` → `CaseReference` rename (captured in SC-1.2)

> **Captured in**: `plan/IMPLEMENTATION_PLAN.md` SC-1.2

`specs/case-management.md` CM-05-001 renamed the `Publication` domain object
type to `CaseReference` (commit ad46802, 2026-03-06). The new model uses a
required `url` field and optional `name` and `tags` fields, aligned with the
CVE JSON schema reference format. SC-1.2 updated accordingly. Any existing
code or test references to `Publication` as a domain type should be treated
as the old name and updated to `CaseReference`.

### Pyright gradual adoption (captured in TECHDEBT-8)

> **Captured in**: `plan/IMPLEMENTATION_PLAN.md` TECHDEBT-8

`specs/tech-stack.md` IMPL-TS-07-002 added a SHOULD requirement to adopt
pyright for static type checking with a gradual approach. No pyright
configuration currently exists. Baseline inventory step is low friction and
should precede any new type annotation work.


---

## Markdown Linting Bug Fix (2026-03-06)

**Issue**: CI reported 45 markdownlint errors across `notes/` and `prompts/`
files.

**Root cause**:

- `notes/bt-integration.md`: trailing space on line 213
- `notes/encryption.md`: missing blank lines around lists (MD032) and bare
  URLs (MD034)
- `prompts/LEARN_EXTRA_prompt.md`: trailing spaces (MD009), spaces inside
  emphasis markers (MD037), and globally-incrementing ordered list numbers
  spanning section headers (MD029)
- `prompts/PLAN_prompt.md`: trailing spaces (MD009)

**Resolution**: Ran `markdownlint-cli2 --fix` to auto-fix trailing spaces,
list spacing, bare URLs, and emphasis issues. Manually renumbered each
section's ordered list to start from 1 in `prompts/LEARN_EXTRA_prompt.md`
(the file used a single counter from 1–18 across five `###` section headers,
which markdownlint treats as separate lists).

**No architectural implications.**

---

## EP-1.1: EmbargoPolicy Pydantic model (2026-03-06)

**Task**: Add `EmbargoPolicy` Pydantic model (EP-01-001 to EP-01-004).

**Implementation**:

1. Added `EMBARGO_POLICY = "EmbargoPolicy"` to `VultronObjectType` in
   `vultron/enums.py`.

2. Created `vultron/as_vocab/objects/embargo_policy.py`:
   - `EmbargoPolicy` model inheriting from `VultronObject` with
     `@activitystreams_object` decorator for registry integration
   - Required fields: `actor_id` (str), `inbox` (str),
     `preferred_duration_days` (int, ≥ 0)
   - Optional fields: `minimum_duration_days` (int|None, ≥ 0),
     `maximum_duration_days` (int|None, ≥ 0), `notes` (str|None)
   - Validators: `actor_id` and `inbox` reject empty strings;
     `notes` rejects empty strings (CS-08-001 pattern)
   - Pydantic `ge=0` constraint on all duration fields
   - `EmbargoPolicyRef` TypeAlias for ActivityStreamRef usage

3. Created `test/as_vocab/test_embargo_policy.py`:
   - 24 tests covering creation, required fields, optional fields,
     validators (empty string, negative int, None acceptance),
     serialization via `object_to_record`, DataLayer round-trip, JSON
     serialization, and type distinctness
   - Follows the `TestCaseReference` pattern for consistency

**Test Results**: 649 passed, 5581 subtests (24 new tests added)

---

## SC-1.3: create_case BT vendor initial participant (2026-03-06)

**Task**: Verify `create_case` BT records vendor as initial
`CaseParticipant` before other participants (CM-02-008).

**Implementation**:

1. Added `SetCaseAttributedTo` BT node to `vultron/behaviors/case/nodes.py`:
   - Sets `case_obj.attributed_to = actor_id` before case persistence
   - Runs before `PersistCase` so the stored case carries the vendor/owner ID

2. Added `CreateInitialVendorParticipant` BT node to
   `vultron/behaviors/case/nodes.py`:
   - Creates a `VendorParticipant(attributed_to=actor_id, context=case_id)`
   - Persists the participant and appends it to `case.case_participants`
   - Idempotent: skips creation if participant already exists

3. Updated `vultron/behaviors/case/create_tree.py` sequence:
   - Inserted `SetCaseAttributedTo` between `ValidateCaseObject` and
     `PersistCase`
   - Inserted `CreateInitialVendorParticipant` between `PersistCase` and
     `CreateCaseActorNode`

4. Added two new tests to `test/behaviors/case/test_create_tree.py`:
   - `test_create_case_tree_sets_attributed_to`: asserts stored case
     `attributed_to == actor_id`
   - `test_create_case_tree_creates_vendor_participant`: asserts a
     `VendorParticipant` with VENDOR role exists in DataLayer for the case

5. Updated `vultron/demo/initialize_participant_demo.py`:
   - Removed explicit `VendorParticipant` creation/add in
     `setup_case_precondition` since the BT now handles it automatically
   - Removed now-unused `VendorParticipant` import

**Test Results**: 625 passed, 5581 subtests passed (2 new tests added)

### SC-1.1 and SC-1.2: VulnerabilityRecord and CaseReference Models

**Completed**: SC-1.1 (VulnerabilityRecord) and SC-1.2 (CaseReference)

**Implementation**:

1. Created `vultron/as_vocab/objects/vulnerability_record.py`:
   - `VulnerabilityRecord` Pydantic model with required `name` field
   - Optional `aliases` (list of alternative identifiers) and `url` fields
   - Validators ensuring `name` is non-empty string; all aliases are non-empty
   - Supports opaque identifiers (CVE, CERT/CC VU#, vendor-specific, etc.)
   - Per CM-05-001, CM-05-008, CM-05-009

2. Created `vultron/as_vocab/objects/case_reference.py`:
   - `CaseReference` Pydantic model with required `url` field
   - Optional `name` (human-readable title) and `tags` (type descriptors)
   - `tags` aligned with CVE JSON schema reference vocabulary (19 valid tags)
   - Validators ensuring `url` and `name` are non-empty; tags is non-empty list
   - Per CM-05-001, CM-05-005

3. Updated `vultron/enums.py`:
   - Added `VULNERABILITY_RECORD` and `CASE_REFERENCE` to `VultronObjectType`

4. Created comprehensive test suites:
   - `test/as_vocab/test_vulnerability_record.py`: 11 tests covering creation,
     validation, round-trip serialization, type distinctness, and opaque
     identifier acceptance
   - `test/as_vocab/test_case_reference.py`: 20 tests covering all fields,
     validation, CVE schema tags, round-trip serialization, and type
     distinctness

**Test Results**: 623 passed, 5581 subtests passed (all existing tests still pass)

**Notes**:
- Both models inherit from `VultronObject` and use `@activitystreams_object`
  decorator for registry integration
- `name` field in SC-1.1 task description mentioned `case_id`, but CM-05-001
  spec does not define `case_id` on the record itself; records are referenced
  from cases via other relationships. Implemented with `name`, `aliases`, and
  optional `url` per spec requirements.
- All validators follow project conventions: raise `ValueError` for invalid
  input; validators are marked with `@classmethod`
- Both models can be imported from their respective files and are registered
  in the ActivityStreams vocabulary registry

---

## EP-1.2: VultronActorMixin and Vultron actor subclasses (2026-03-06)

**Task**: Add `embargo_policy` optional field to an actor profile model
(EP-01-001).

**Implementation**:

1. Created `vultron/as_vocab/objects/vultron_actor.py`:
   - `VultronActorMixin(BaseModel)`: shared mixin adding optional
     `embargo_policy: EmbargoPolicyRef | None` field
   - `VultronPerson(VultronActorMixin, as_Person)`: Person with Vultron
     profile fields; retains `as_type == "Person"`
   - `VultronOrganization(VultronActorMixin, as_Organization)`: Organization
     with Vultron profile fields; retains `as_type == "Organization"`
   - `VultronService(VultronActorMixin, as_Service)`: Service with Vultron
     profile fields; retains `as_type == "Service"`
   - TypeAlias helpers: `VultronPersonRef`, `VultronOrganizationRef`,
     `VultronServiceRef`
   - All three concrete classes decorated with `@activitystreams_object`

2. Created `test/as_vocab/test_vultron_actor.py`: 16 tests covering actor
   type preservation, embargo_policy defaults, inline object and reference
   string acceptance, `VultronActorMixin` isinstance checks, and JSON
   serialization.

**Test Results**: 665 passed, 5581 subtests (16 new tests added)

**Design Notes**:
- The mixin approach keeps the `embargo_policy` field DRY across actor
  types rather than repeating it in each subclass.
- The actor's ActivityStreams type is intentionally preserved (Person,
  Organization, Service) so that external ActivityPub clients that do not
  know about Vultron extensions continue to work correctly.
- A fully standards-conformant implementation would extend the JSON-LD
  `@context` to define `embargoPolicy` under a Vultron namespace (e.g.,
  `https://certcc.github.io/Vultron/ns#` or `https://vultron.cert.org/ns#`) so 
  that 
  decentralized clients can
  understand or safely ignore the custom field. This is deferred; see
  Priority 1000 (Agentic AI readiness) and the JSON-LD extension pattern
  described in the user's note on 2026-03-06.
- The longer-term goal is likely going to be a broader
  `VulnerabilityDisclosurePolicy` object that
  contains `embargoPolicy` as a sub-field (analogous to security.txt /
  DIOSTS). That wrapper model is a future work item and should be tracked
  as a follow-on to EP-01 when a formal spec is drafted. DIOSTS format is 
  a likely candidate for the policy representation, but the embargo-specific 
  fields require a custom extension to the standard DIOSTS schema. DIOSTS 
  example follows:
```json
  {
    "security_txt_domain": "certcc.github.io",
    "source": "diosts-v0.2.2",
    "retrieval_url": "https://certcc.github.io/.well-known/security.txt",
    "last_update": "2026-03-06T19:53:28Z",
    "policy_url": "https://certcc.github.io/CERT-Guide-to-CVD/reference/certcc_disclosure_policy/",
    "contact_url": "https://kb.cert.org/vuls/report/",
    "hall_of_fame": "https://kb.cert.org/vuls/",
    "pgp_key": "https://certcc.github.io/pgp/asc/latest.asc",
    "hiring": "https://cmu.wd5.myworkdayjobs.com/SEI",
    "securitytxt_url": "https://certcc.github.io/.well-known/security.txt",
    "preferred_languages": "en",
    "expires_at": "2029-10-05T04:00:00Z",
    "rfc_compliant": true
  }
```


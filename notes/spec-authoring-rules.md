---
title: Spec Authoring Rules — Field Values, Lint Traps, and Coverage Gates
status: active
description: >
  Mechanical rules for authoring spec YAML: the exact enum values spec-lint
  accepts for `kind`, `priority`, and `rel_type`; keys that are silently
  dropped; the protocol-coverage ratchet and its xfail pattern; and the audit
  passes required when retiring a name or splitting a compound requirement.
related_specs:
  - specs/meta-specifications.yaml
  - specs/spec-registry.yaml
related_notes:
  - notes/specs-vs-adrs.md
  - notes/behavioral-conformance-specs.md
  - notes/testing-pitfalls.md
---

# Spec Authoring Rules — Field Values, Lint Traps, and Coverage Gates

Canonical write-ups for the mechanical spec-authoring pitfalls. `specs/AGENTS.md`
keeps the short index; the decision of *what* belongs in a spec at all is in
[notes/specs-vs-adrs.md](specs-vs-adrs.md).

---

## Field Value Enums

### Valid `kind:` Values

The `kind:` field accepts exactly four values:

```text
protocol  architecture  project  process
```

`implementation` is **NOT** valid and causes spec-lint to reject the file at
commit time. The error may look like a YAML syntax error — it is not.

- Use `kind: protocol` for external protocol obligations (what a Vultron
  participant must do on the wire).
- Use `kind: architecture` for structural constraints on the system (layering,
  import rules, module boundaries).
- Use `kind: project` for internal project conventions that do not affect
  external protocol behavior.
- Use `kind: process` for development process rules (testing, documentation,
  CI).

Check existing entries in the same spec file for context before writing a new
entry. *Source: ISSUE-2258*

### Valid `priority:` Values — Underscores, Not Spaces

The `priority:` field enum uses **underscores**: `MUST_NOT`, `SHOULD_NOT`.
**Not spaces.** MS-02-002 prose writes "MUST NOT" with a space, but the Pydantic
validator enum uses underscores. Using `MUST NOT` (space) breaks spec-lint with
a FATAL registry load error.

Valid values:

```text
MUST  MUST_NOT  SHOULD  SHOULD_NOT  MAY
```

Source: ISSUE-2393

### Valid `rel_type` Values in Spec Relationships

When adding a `relationships:` entry to a spec requirement, `rel_type` MUST be
one of the enumerated values validated by `SpecFile`. Using an invalid value
causes a Pydantic `ValidationError` at `spec-dump` time.

**Valid `rel_type` values:**

```text
implements, supersedes, extends, depends_on, conflicts, refines,
derives_from, verifies, part_of, constrains, satisfies
```

`related_to` is **NOT** valid. If the intent is a loose relationship, use
`refines` with a clarifying `note:` field, or omit the relationship entirely if
no normative link exists.

### `references:` Key in Spec YAML Is Silently Dropped by `spec-dump`

The `StatementSpec` schema does not include a `references:` field; unknown YAML
keys are silently discarded. The correct field for linking a spec entry to an
ADR is `adr:`, which `spec-lint` validates against known ADR filenames. After
adding any new key to a spec YAML, verify it appears in
`PYTHONPATH= uv run spec-dump` output before treating it as persisted.

Source: ISSUE-2237

---

## Protocol Coverage Ratchet

### Adding or Modifying a `kind: protocol` Entry Requires a Same-PR Marker Test

(SR-05-005, ISSUE-2117)

The CI ratchet (`MAX_UNCOVERED_PROTOCOL_SPECS` in
`test/architecture/test_spec_coverage_ratchet.py`) counts uncovered
protocol-kind IDs. Its ceiling can only be lowered, never raised. Adding or
modifying a `kind: protocol` spec entry without a corresponding
`@pytest.mark.spec("<ID>")` marker in a test raises the uncovered count and
fails CI.

**Fix:** add `@pytest.mark.spec("<new-id>")` to a test in the same PR, before
the branch lands. Run `spec-coverage` to verify coverage after adding the
marker. See SR-05-004, SR-05-005.

### Never Raise the Ceiling — Use a Strict `xfail` for Not-Yet-Implemented Specs

`test_protocol_spec_coverage_floor` counts uncovered `kind: protocol` specs
immediately. If no test carries `@pytest.mark.spec("SPEC-ID")`, the uncovered
count rises above the ceiling and CI fails. The ceiling comment says "never
raise it."

Pattern for a spec whose implementation does not yet exist: write a test
asserting the not-yet-implemented behavior, then mark it

```python
@pytest.mark.xfail(strict=True, reason="SPEC-ID: <short description>. Tracked by Bug #N.")
@pytest.mark.spec("SPEC-ID")
```

Do NOT add a stub class — use an existing node or assertion that fails for the
right reason. The xfail auto-promotes to passing once the feature lands, and the
`reason=` links the test back to the implementation issue.

Source: ISSUE-2606

---

## Audit Passes

### Retiring a File or Label Requires Auditing All Specs for Bare-Filename References

`MS-15` (`_check_phantom_paths`) only flags backtick-quoted tokens containing a
directory separator (e.g. `` `plan/PRIORITIES.md` ``). Bare filenames such as
`PRIORITIES.md` or bare label names such as `group:unscheduled` written without
backticks or without a `/` pass the lint check silently. When retiring any file,
label, or convention, grep `specs/` for the bare name as well as the
quoted/path form, and update every spec entry that references it — including
`statement:`, `rationale:`, and cross-reference fields.

Source: ISSUE-2011

### Sub-Agent Spec Splits: Re-Run the Violation Detection Script After the Parallel Pass

After parallel sub-agents split compound spec requirements, re-run the
compound-statement detection script. Agents frequently add new child entries but
leave the original parent statement text unchanged (with all semicolons intact).
The spec-lint failure surfaces the symptom; the detection script identifies which
parent was not trimmed. Do not trust agent completion reports for this class of
task.

Source: ISSUE-2393

### "CaseActor MUST …" Is Often a Specification Error — CaseActor Is a Role, Not a Component

`CaseActor` names a *role* (the participant holding `CVDRole.CASE_MANAGER`), not
a dedicated component. Anything per-case in a CaseActor's *identity* (e.g., a
per-case service URL derived from the case slug) is a category error: no
container has registered that identity, so any call to it answers 404. When a
spec says "CaseActor MUST create X" or "CaseActor MUST send Y", verify the
requirement is using CaseActor as a role (whichever actor holds CASE_MANAGER for
this case) rather than as a singleton object. A spec that mints an object to
satisfy a role requirement will be faithfully implemented and faithfully wrong.
Grep the spec corpus for MUST requirements whose subject is a role name to catch
these before they hide defects.

Source: ISSUE-1872

### Never Restate Counts in Cross-References

See [notes/specs-vs-adrs.md](specs-vs-adrs.md) § "Never State Ephemeral Counts
in Long-Lived Docs" (MS-16-001).

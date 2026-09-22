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

**Reading a lint or loader failure**: the mechanics of how these tools report a
file they cannot read — and the three reasons a failure can arrive without
naming its file — are in
[`vultron/metadata/AGENTS.md`](../vultron/metadata/AGENTS.md) § "Loader Failure
Attribution". Read that first if the output you are looking at is a traceback
rather than an `[ERROR]` line.

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

### A Grep-Corpus Guard Can Resolve Its Own Documentation

Any lint check that validates spec prose against a *textual* scan of the source
tree — the MS-15-004 phantom-symbol guard (`_check_phantom_symbols` in
`vultron/metadata/specs/lint.py`) is the canonical case — can be blinded by its
own docstrings and error messages. Naming a symbol in the check's own prose puts
that token back into the scanned corpus, so the guard resolves it as "live" and
stops flagging the very defect it was written to catch (verified directly:
`'SEMANTICS_ACTIVITY_PATTERNS' in _SourceScan(Path('.')).symbols` became `True`
once the docstring named it).

**How to apply:**

- When adding such a check, assert the negative directly — a test that a symbol
  named *only* inside the linter's own source is still rejected — rather than
  assuming the corpus excludes it.
- Prefer **file-scoped** exclusions over **package-scoped** ones. A linter
  package usually mixes prose (safe to exclude) with real spec-cited definitions
  (must stay scanned): excluding all of `vultron/metadata/specs/` re-introduced
  false positives for `SHOULD_NOT` (a real `RFC2119Priority` member in
  `schema.py`) and `SCREAMING_SNAKE_CASE` (a token *shape* named in MS-15-004's
  own statement).
- Keep the two exclusion sets distinct and documented: the phantom-*ID* allowlist
  excludes only `test/metadata/specs` (a stale spec ID cited by the linter is a
  real defect, so `vultron/metadata/specs/` stays scanned), while the *symbol*
  corpus additionally excludes `lint.py` (which names symbols as examples, not as
  code the specs describe).

Source: ISSUE-3022

### A Retired-Symbol Sweep Is Not a Substitution — Check the Shape First

An acceptance criterion phrased as a mechanical substitution ("replace all N
occurrences of `OLD` with `NEW`") carries an unstated premise that the swap is
meaning-preserving. When the replacement has a **different data shape**, a
find-and-replace silently turns a stale requirement into a *wrong* one — strictly
worse, because a wrong MUST reads as authoritative.

Concretely, `SEMANTICS_ACTIVITY_PATTERNS` was a
`dict[MessageSemantics, ActivityPattern]`; `SEMANTIC_REGISTRY` is an ordered
`list[SemanticEntry]` in which *every* `MessageSemantics` value has an entry —
including the `UNKNOWN` / `UNKNOWN_UNRESOLVABLE_OBJECT` sentinels, whose entries
carry `pattern=None`. Three specs phrased in dict terms had to be re-derived, not
renamed: statements about a value having no "entry", about "keys", or about
"containment" all invert when a mapping becomes a sequence.

**How to apply:** before auditing a corpus for a retired symbol, ask whether the
replacement has the same shape. If a mapping became a sequence (or vice versa),
treat every statement phrased in terms of *keys*, *entries*, or *containment* as
a candidate for a semantic rewrite. When authoring such an issue, state the
intent ("every reference names the live registry accurately"), not the mechanism.

Source: ISSUE-3022

### Sub-Agent Spec Splits: Re-Run the Violation Detection Script After the Parallel Pass

After parallel sub-agents split compound spec requirements, re-run the
compound-statement detection script. Agents frequently add new child entries but
leave the original parent statement text unchanged (with all semicolons intact).
The spec-lint failure surfaces the symptom; the detection script identifies which
parent was not trimmed. Do not trust agent completion reports for this class of
task.

Source: ISSUE-2393

### Name the Authority "CASE_MANAGER", Not "CaseActor" (CaseActor Is the Prototype Identity)

The authority for a case is a **role** — the participant holding
`CVDRole.CASE_MANAGER` — not a dedicated component and not a fixed identity.
Protocol-normative prose MUST name that authority **the CASE_MANAGER** (the role
holder). Reserve **"CaseActor"** for the concrete prototype/demo actor that
enacts the role, and **"case actor service"** for the provisioning endpoint that
spawns `case-actor` identities (glossary; ADR-0088). Anything per-case in a
CaseActor's *identity* (e.g., a per-case service URL derived from the case slug)
is a category error: no container has registered that identity, so any call to
it answers 404.

When a spec says "CaseActor MUST create X" or "CaseActor MUST send Y", rewrite it
to "the CASE_MANAGER MUST …" unless the requirement is genuinely about the
prototype actor (a demo/scenario spec such as `multi-actor-demo.yaml`). A spec
that mints an object to satisfy a role requirement — or that invites a reader to
compare `actor_id` against a computed `case_actor_id` — will be faithfully
implemented and faithfully wrong. Grep the spec corpus for MUST requirements
whose subject is `CaseActor` to catch these before they hide defects.

Source: ISSUE-1872, ISSUE-3260

### Name Which Member of a Population a Requirement Constrains

When a requirement constrains one member of a set of similar things — one of
several timestamps on an object, one of several registries consulted on the same
value, one of several *kinds* of entry in a list — it MUST name **which one**.
An RFC 2119 verb applied to an unnamed member is not merely vague; it is often
*wrong under the plainer reading a new implementer will take*, producing a check
that is either vacuous or falsely rejecting:

- **Timestamps (ISSUE-2824).** A `CaseLedgerEntry` carries both an envelope
  `published` (the CASE_MANAGER's commit stamp) and a `payloadSnapshot.published`
  (the asserting participant's claimed time). CLP-14/CLP-15 constrained "the
  published timestamp" without saying which; applied to the claimed field,
  CLP-14-003's monotonicity check compares two participants' unsynchronised
  clocks — the wall-clock ordering ADR-0079 rejected — and rejects well-formed
  assertions. The fix names the field in every entry.
- **Registries (ISSUE-3217).** Two lookups act on an activity's `type`: the AS2
  vocabulary (`parse_activity` → reject with HTTP 422) and the semantic pattern
  registry (`find_matching_semantics` → route to `UNKNOWN`). MV-01-006 said
  "unrecognized activity types" without naming the registry, so "reject" and
  "route to UNKNOWN" both looked correct. The fix names the semantic pattern
  registry and points the parse-time behaviour at MV-01-001.
- **List kinds (ISSUE-3207).** ADR-0089's ratchet exclusion list holds two
  *writer* exclusions plus a permanent non-writer over-catch. An AC that says
  the list "ends at exactly two entries" (dropping *writer*) contradicts the
  design that made the gate deliberately over-broad. Count the kind, not the
  whole population.

**Corollary — name the enforcing side of a participant obligation.** A
requirement written as a participant duty ("a participant MUST emit … in causal
order") MUST also say what the *receiver* does about it: enforce, flag, or
nothing. A group heading is not a substitute — CLP-15's *Participant Assertion
Timestamp Obligations* heading did not stop four entries from being read as
CASE_MANAGER duties, and seven `xfail(strict=True)` stubs were written against a
per-assertion enforcement that CLP-15-005 forbids and a stateless commit boundary
cannot perform. Give such a requirement a `note` naming the enforcing side and a
`verification` pointing at the vantage point (e.g. a whole-scenario
`check_causal_edges`) from which the obligation is actually observable.

Source: ISSUE-2824, ISSUE-3217, ISSUE-3207

### Verify an "All-Members" Group Claim Against Each Member

The verification-side companion to the rule above. When a spec **group
description** asserts a property of *all* its members ("All CS shorthands share
the `ADD_CASE_STATUS_TO_CASE` semantic"), check each member against the code
before relying on the generalization. Group descriptions are written once and
rarely revisited when one member's behaviour later diverges, so a stale "all"
claim silently mis-specifies the members that changed. MSM-03-001/002/003
inherited exactly this: the group generalized a `CaseStatus` semantic onto `CV`/
`CF`/`CD`, which actually carry participant-scoped VF/D state
(`as_ParticipantStatus`, ADR-0075) — so the group asserted, normatively, the
opposite of an invariant the domain model enforces. An implementer following it
faithfully would have dropped the vendor identity.

Source: MSM-03-001/002/003 (promoted from notes/message-type-reference.md)

### Never Restate Counts in Cross-References

See [notes/specs-vs-adrs.md](specs-vs-adrs.md) § "Never State Unverifiable,
Drift-Prone Facts in Long-Lived Docs" (MS-16-001, generalised by MS-16-002).

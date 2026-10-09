---
title: Spec Authoring Rules — Field Values, Lint Traps, and Coverage Gates
status: active
description: >
  Mechanical rules for authoring spec YAML: the MS-12 decision tree for
  choosing a `kind` and why copying neighbouring entries is the wrong
  heuristic; the exact enum values spec-lint accepts for `kind`, `priority`,
  and `rel_type`; keys that are silently dropped; the protocol-coverage
  ratchet and its xfail pattern; the audit passes required when retiring a
  name or splitting a compound requirement; priority tiers (MS-02-003/004); and
  the per-requirement `verification_debt` marker and its owner and
  terminal-state rules (MS-10-006..008); the rule that a verification clause
  names a check that inspects its property (MS-10-009); and the
  CASE_MANAGER-versus-CaseActor naming discriminator.
related_specs:
  - specs/meta-specifications.yaml
  - specs/spec-registry.yaml
  - specs/triggerable-behaviors.yaml
  - specs/testability.yaml
  - specs/docs-build-workflow.yaml
  - specs/demo-ci.yaml
related_notes:
  - notes/specs-vs-adrs.md
  - notes/behavioral-conformance-specs.md
  - notes/testing-pitfalls.md
  - notes/architecture-ratchet-corpus.md
  - notes/agentic-workflow.md
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

These glosses come from *ISSUE-2258*.

#### Apply the decision tree, not the neighbouring entries

The four one-line glosses above are a summary, not the rule. The authoritative
rule is the decision tree in **MS-12-001 … MS-12-005** (`meta-specifications.yaml`),
established by [ADR-0038](../docs/adr/0038-four-tier-specification-taxonomy.md).
Apply it in order and stop at the first match:

1. About how the project is run — CI, workflow, agent conventions, docs
   standards, spec authoring rules? → `process`
2. References a language construct, library, file path, class, function,
   module, or codebase mechanism (`py_trees`, `pydantic`, `vultron/`, `.py`,
   `pytest`, BT nodes)? → `project`
3. Must an independent implementer satisfy it to be Vultron-compliant, in any
   language? → `protocol`
4. None of the above — implementation-independent but not compliance-bearing?
   → `architecture`

Step 2 is the one that gets skipped. A codebase reference disqualifies
`protocol` **even when the surrounding requirement feels protocol-ish**, which
is why the ordering is normative in MS-12-005 rather than advisory.

Do **not** infer a spec's `kind` by copying the entries around it. That heuristic
is what produced the defect behind ISSUE-2601: MS-12 went unenforced from its
adoption until 2026-09, and by then a large fraction of the `kind: protocol`
corpus was carrying `lint_suppress: [missing_story_reference]` instead of a
corrected `kind` — code naming conventions, test-coverage requirements, and
build-file formats all tagged as wire-protocol obligations. For the live count,
read `MAX_MISSING_STORY_SUPPRESSIONS` in
`test/architecture/test_spec_kind_ratchet.py`, the ceiling MS-12-007 pins; it is
the authoritative figure and it only goes down. Suppressing the
story-traceability gate is almost never the right response to it firing; a spec
that cannot be traced to a user story is usually mis-classified, not story-less.
MS-12-006 now makes the unambiguous cases a hard error, and MS-12-007 ratchets
the suppression count downward, but neither detects a misclassification whose
statement names no code. MS-12-008 gives MS-12-006's own escape hatch,
`protocol_kind_with_code_reference`, a ceiling of its own
(`MAX_CODE_REFERENCE_SUPPRESSIONS`, 0 at introduction), so a suppression cannot
move from one code to the other unseen.

#### Why MS-12-006 is scoped the way it is

MS-12-006's rationale defers here, because the three scoping decisions are what
keep it from becoming the problem it was written to solve. Each one was measured
against the live corpus.

**It fires only on specs with no `stories:`.** Scanning every `kind: protocol`
spec looks stricter and is much worse. A protocol spec that traces to a user
story has already demonstrated it is protocol, and its `verification:` field
names a `test/…py` path *because MS-10-003 obliges every MUST to carry one and
MS-15-001 obliges the path to resolve*. Applied to the whole protocol corpus the
detector flags roughly half of it, and the majority of those hits are specs that
are fully SR-11-compliant. The author's only available remedies would then be
relabeling a genuine protocol spec as `project` or adding a suppression — the
wrong-way ratchet described above, re-created by the check meant to stop it.
Gating on the absence of a story confines the check to the population where a
codebase reference actually indicates misclassification.

**The token list excludes bare `module`, `class`, and `function`.** Those read as
ordinary domain English in wire requirements — "a machine-readable failure
class", "the same action class", "the actor's function in the CVD process". Left
in, they flag two dozen genuine protocol statements and instruct the author to
set `kind: project` on a pure wire obligation. `.py`, `vultron/`, `test/`,
`scripts/`, `pytest`, `pydantic`, and `py_trees` carry no such second meaning.
The cost of the omission is a handful of true positives the check will not catch;
those are MS-12-006's acknowledged blind spot, not an oversight.

**The error names the whole tree, not `project`.** MS-12-002 is not always the
right answer for a spec that names code: MS-12-005 gives MS-12-001 precedence,
and `pytest`, `test/`, and `scripts/` land squarely in the CI-and-authoring-rules
territory MS-12-001 claims for `process`. MS-12-006 and MS-12-007 are themselves
the demonstration — both name those tokens, and both are correctly `process`. A
message that prescribed `project` would send those specs to the wrong tier.

The general lesson, from ISSUE-3480: **an enforced MUST advertises itself through
full compliance in the artifacts; an unenforced one anti-advertises.** A rule at
half adoption reads to the next author as "no rule here" — worse than one at zero
adoption, which at least reads as "not done yet".

#### Relabeling a `kind:` moves more than the field

A relabel pass (the MS-12 passes in #3600 and #3601) has three mechanical
consequences, each with a tool:

- **Anchors move.** A spec renders only on its own kind's docs page (SR-09-002),
  so every prose link to `specs/protocol.md#xx-nn-nnn` dangles the moment the
  item becomes `project`, and so does a group anchor once its last protocol item
  leaves. Run `uv run python scripts/relink_requirement_anchors.py` after the
  relabel; it repoints each link at the page its anchor now renders on.
- **Verification travels with the spec (MS-10-008).** An unverified MUST or
  MUST_NOT that changes kind gains its `verification:` in the same change; its
  `verification_debt` marker names the old kind's owner, so spec-lint fails it
  until the clause replaces the marker.
- **The suppression goes with the old kind.** `scripts/relabel_spec_kinds.py`
  applies a `{spec_id: kind}` mapping and strips `missing_story_reference` from
  each item in one pass, preserving every other line byte for byte. The
  protocol-coverage ceiling (`MAX_UNCOVERED_PROTOCOL_SPECS`) then drops too, since
  a spec that leaves the protocol tier leaves that population; lower it to the new
  live count in the same PR.

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

## Spec Item Format Is Field Presence, Not a Class You Pick

(ADR-0101, CONCERN-3506)

`BehavioralSpec` subclasses `StatementSpec` and the fields it adds —
`preconditions`, `steps`, `postconditions` — are all optional, so under Pydantic's
smart union a spec item carrying none of them satisfied the `BehavioralSpec`
branch. Every one of the corpus's items loaded as a `BehavioralSpec`, the large
majority of them with no behavioral field at all. MS-13-001 and MS-13-002 were
therefore phrased over a distinction the loaded model did not preserve.

**What this cost.** `_is_behavioral_file()` in
[`vultron/metadata/specs/docs_render.py`](../vultron/metadata/specs/docs_render.py)
is a bare `isinstance` test, so it classified every spec file as behavioral —
including the files that do not carry the `behavioral` tag. Every published spec
page opened with a `## Behavioral Specifications` heading and its ECA blurb,
applied to the whole corpus, and the non-behavioral bucket was always empty. The
linter's two behavioral guards were vacuous — they worked only because each is
`and`-ed with `bool(spec.steps)` — and the requirements graph labelled every node
`type: "behavioral"`. The measured corpus figures are in ADR-0101, which is where
a dated measurement belongs; do not copy them here (MS-16-002).

**How to apply.** Read the format off the fields, never off the class name in
your head, and write new checks over field presence. A `BehavioralSpec` now
requires at least one of `preconditions`, `steps`, or `postconditions`; supply
none and the item is a `StatementSpec`. That degradation is silent but it is *not*
invisible — the class is observable in the requirements graph node's `type`, in
which docs section the item renders, and in the linter's behavioral guards. If you
mean an item to be behavioral, give it a behavioral field; nothing else records
the intent. When you add a consumer that branches on behavioral-ness, assert the
negative directly — a fixture item with no behavioral field must come back as a
`StatementSpec` — rather than trusting that the union resolves the way the class
hierarchy suggests. And do not reach for the `behavioral` **tag** as the oracle
instead: `render_for_kind()` treats it as an `or` branch, and files hold
behavioral items without carrying it.

### `steps` Carries the Action of an ECA Rule, Not a Claim About Ordering

MS-13-002 used to require `StatementSpec` for any requirement that "does not
depend on step ordering". Read literally that condemns the house idiom of the
behavioral conformance corpus: dozens of `RMB`/`EMB`/`CSB` items are single-step
`BehavioralSpec`s whose one step *is* the required action ("emit CV to announce
the transition"), and a one-element sequence asserts no order. The same applies
to the many items carrying typed `preconditions` and no `steps`: that is the
condition half of an ECA rule, not a format choice half-made.

So do not flag `preconditions`-without-`steps` as a defect. The only shape that
is reliably wrong is the inverse — an *ordered sequence flattened into `statement`
prose* (`MUST execute the following sequence: (1) … (2) …`), which MS-05-001
already forbids and which hides the start state, the ordering and the terminal
conditions from conformance tooling. Note the residual judgement: an inline
`(1) … (2) …` list is sometimes genuinely unordered — `SBT-01-002`'s three
separate top-level trees, one per message-type use case; a set of assertions a
test file must make — and converting one of those to `steps` would assert an order
the requirement does not have. Dispose of such a hit with `lint_suppress`, not by
inventing a sequence.

### An Advisory Warning Is Not Enforcement Once the Corpus Outgrows It

`spec-lint`'s per-item `must_without_verification` warning named exactly the
"MUST with nothing checking it" defect — and fired on MS-13-001 and MS-13-002
themselves for as long as they went unenforced. As a per-item `[WARN]` it did
not help, because well over half the corpus's MUST items had no `verification:`
field, so that one warning produced the large majority of the run's `[WARN]`
lines. A defect class
at that volume is indistinguishable from background noise, and a newly-introduced
instance is invisible.

It is now a per-item rule with a per-kind summary. Every unverified MUST-tier
requirement carries `verification_debt: '#N'`, naming the open issue that owns
verifying it, and `spec-lint` fails any item with neither field (MS-10-006). The
default output is one line per kind — the number of marked requirements,
tallied by owner — with the IDs only under `--list-unverified` (MS-10-005). The
number is computed from the markers, so a backfill lowers it without editing
anything else, and the line still shows each backfill issue's progress.

When you add a per-item advisory, decide up front what happens when it is
routinely true: collapse it to a count plus an opt-in listing, mark each
remaining hit with its owning issue, with a terminal state (see
[A Ratchet Needs an Owner and a Terminal State](#a-ratchet-needs-an-owner-and-a-terminal-state)),
or make it a hard error and
dispose of every existing hit. Do not ship a rule at partial adoption: per the
ISSUE-3480 learning, a requirement half-adopted reads as *no rule here*, which is
worse than one nobody has started.

### A Priority Gate Names a Tier, Not a Keyword

RFC 2119 gives `MUST NOT` the same absolute strength as `MUST`, and `SHOULD NOT`
the same strength as `SHOULD`. Every gate that selects requirements by priority
must therefore select a *tier* (MS-02-003). In the code, that means asking the
shared tier definition on `RFC2119Priority` — `spec.priority.is_must_tier` or
`.tier` (MS-02-004) — never
`spec.priority == RFC2119Priority.MUST`. A static test,
`test/metadata/specs/test_priority_tier_gate.py`, fails on any comparison
against an individual member or a priority string under
`vultron/metadata/specs/` or `scripts/`; its allowlist holds exactly one entry,
SR-11-003's selector, and fails if that entry stops matching, so retiring the
exception also retires the allowlist.

The literal comparison is easy to write and fails silently: nothing errors, and
the prohibitions simply drop out. That happened more than once before MS-02-003:

- `must_without_verification` was scoped to "MUST requirements" by the wording
  of the issue that introduced it (#2466), and a unit test then pinned the
  exclusion. The test read as a deliberate decision but only preserved the
  wording of that AC. So the #2467 protocol-tier backfill reported the tier
  complete while most protocol `MUST_NOT`s had no `verification:` at all
  (#2535, #3612). The count now covers both keywords.
- SR-11-003's story gate and SR-11-004's advisory had the same shape. The
  second now covers `SHOULD_NOT` by selecting "below the MUST tier" rather than
  naming keywords. SR-11-003 is the one recorded exception, still `MUST`-only
  because extending it needs stories that do not exist yet (see its `note:`);
  the exception is written once, in `sr_11_003_gate_applies()` in
  `vultron/metadata/specs/lint.py`, and `scripts/backfill_stories.py` selects
  through that predicate rather than carrying a second copy of it.
- `spec-backstop` got it right (`priority in ("MUST", "MUST_NOT")`), but as a
  second hand-written copy of the tiering, which is the drift MS-02-004's
  single shared definition prevents. It now asks `is_must_tier`.

When a priority-scoped rule is proposed, read "MUST" in its AC as the tier
unless the AC explicitly excludes the negative form *and says why*. If you find
a test that asserts a negative form is excluded, trace it to a decision before
you trust it.

### A Ratchet Needs an Owner and a Terminal State

The MS-10 verification rule (MS-10-006 through MS-10-008) is built so that it can
only end at zero:

1. **The record is per requirement, not a count.** Each unverified MUST or
   MUST_NOT carries its own `verification_debt` marker, so verifying one edits
   only that requirement and two PRs conflict only when they edit the same one.
   The earlier design pinned a per-kind count to its live value, which raced
   every PR in flight (see `notes/testing-pitfalls.md`, "A Two-Sided Count Pin
   Races Every Concurrent PR"). A requirement with both a marker and a
   `verification:` clause fails as stale.
2. **Each marker names an open owning issue.** The marker must name an owner of
   its kind in `VERIFICATION_DEBT_OWNERS`. A PR that closes an owner issue
   (`Closes #N`) while a marker or the table still names it fails, so the
   backfill that finishes an owner also removes its table entry. An owner closed
   by hand is reported within the hour by one tracking issue and never fails
   the build, since no PR caused it (ARCH-18-004;
   `.github/workflows/verification-debt-owners.yml`).
3. **Zero is terminal.** Once no requirement of a kind carries a marker, delete
   that kind's owner entry; any marker of that kind is then a hard error, so the
   kind cannot regrow debt. The growth guard (#4200) keeps new markers out
   while an entry still exists.
4. **A relabel carries its verification with it.** A relabelled requirement's
   marker names the old kind's owner and fails; replace it with a
   `verification:` clause in the same change (MS-10-008).

Any new backlog-style ratchet should follow the same four rules unless it states
why it cannot.

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

`spec-coverage` reports `kind: protocol` IDs only. A `project`- or other-kind ID
never appears in its output, covered or not, so an acceptance criterion reading
"`spec-coverage` shows `<ID>` covered" cannot be met for one (#3565's AC-6
asked this of VM-06-008). Write such a criterion as "a test carries
`@pytest.mark.spec("<ID>")`" and check it with `grep`.

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

## A Spec States Current Understanding, Not Its Own Edit History

`rationale:` and `verification:` are as normative-adjacent as `statement:` —
agents read all three to infer what the project believes. So when a requirement
changes, rewrite its supporting prose to describe the world as it is now.
**Specs do not maintain their history**; `git log`, ADRs and `plan/history/` do.

The failure mode is specific. VM-01-004's rationale narrated its own amendment
("This requirement previously stated that the key *is* the AS2 `type` value…")
and, to make the point, cited the `as_VultronPerson` → `VultronPerson` dual key
as an example of harmless divergence. The registry was later split in two, which
made the type-value key form correct for one of them — but the rationale still
read as a standing endorsement of the divergence, and its verification clause
described a test asserting it. The bug in #2982 therefore looked like intended
design to every agent who checked, for as long as the prose survived.

**How to apply:** after changing a `statement:`, reread its `rationale:` and
`verification:` and delete any clause that only makes sense against the
superseded version — especially a concrete example chosen to illustrate the old
framing. If the history matters, it belongs in the ADR the entry's `adr:` field
points to. And do not describe a verification test that does not exist: write it,
or describe the one that does.

Source: ISSUE-2982

## `protocol` Means RFC Content

`protocol` is for what an RFC would contain: wire messages, the behaviours that
lead to them, and state machines (MS-12-003). The TCP analogy is the test: TCP
fixes what two implementations exchange, not how one implementation structures
its endpoints or stores. A MUST about an internal endpoint is `project` however
firm it reads; EP-02-004 (compare-and-set on the policy PUT) is the worked
example. MS-12-006 scans the `statement` only, so a `verification:` that names a
test file does not by itself make a spec `project`: MS-10-003 and MS-15-001
oblige that path, and no protocol-tier variant of the verification convention
is needed. The detector still scans `verification:` and the roughly ninety
protocol-worded specs #3600 relabeled to `project` on that basis (#3943) have
not yet returned to `protocol`; #4312 fixes both. Those that gain no user story
carry `missing_story_reference`, which raises the MS-12-007 ceiling once, by the
reverted count. #3601 and #2717 own the burn-down.

Source: ISSUE-4195

## Removed Requirements: Never Reuse an ID, Archive the Text

A removed requirement is removed, not deprecated (MS-09-001): `deprecated: true`
in `specs/` is a violation. Its ID is never reused (MS-09-004); a replacement
rule gets a new ID, and citations are repointed (MS-09-003). CM-11-005 was reused
with the opposite force, so every citation of it pointed at a rule it never meant.
The removed text is parked as one file per ID under `plan/retired-specs/`
(MS-09-005), outside `specs/` so it is never loaded into agent context.
Retire with `uv run spec-retire <ID> --why ... --by '#N' [--replacement <ID>]`
(MS-09-006): it moves the text, writes the history entry, and lists the
citations still to repoint. `spec-lint` fails on `deprecated:`/`superseded_by:`
and on a re-declared archived ID (MS-09-007).
Spec-versus-code conflicts found in an implementation PR follow
the material test in
[notes/agentic-workflow.md](agentic-workflow.md) § "Spec Text Conflicts With
Code", and the PR body carries `## Spec amended`.

Source: ISSUE-4195

## A Verification Clause Is a Claim About the Suite

A `verification:` clause tells every later reader how the requirement is known
to hold, and an unbacked clause reads exactly like a backed one. MS-10-009
requires the clause to name a check that exists and that inspects the property
the statement asserts. Five sessions found clauses that did not:

| Requirement | What the clause named | Why it verified nothing |
|---|---|---|
| DEMOCI-11-009 | `mkdocs build --strict` renders the scenario table | Strict mode never sees a link a build-time block prints; the page shipped with nine `.md` links that 404 on the built site, on a green build (#3450) |
| VM-01-004 | A test asserting the actor dual key | The test did not exist, and the stale wording licensed six bogus registry keys (#2982) |
| DR-03-002 | Nothing | No clause, so nobody noticed it named the wrong component (#3827) |
| MS-13-003 | Nothing | No check, half adoption, and the corpus read as having no rule; planning nearly invented a duplicate (#3480) |
| ADR-0099 details 7–8 | The epic's closed children | Graduated to `accepted` with two details unbuilt; a `lint_suppress` in the same commit hid the prose/status mismatch (#3888) |

**How to apply:** for each clause you write or review, ask one question — *if
this requirement were violated, would the named check fail?* A build, lint or
type-check that never examines the constrained artifact fails the question, and
so does a test whose name you have not opened. For a build-time-rendered page,
assert on the built `site/` (`docs-links`, DOCBW-03-007) or on the rendered string
in a unit test. MS-15-001 makes a named path resolve; a named test function is
not yet checked (#4170), so open it. The question is part of `pr-triage`'s spec
conformance phase.

Source: ISSUE-3450, ISSUE-2982, ISSUE-3827, ISSUE-3480, ISSUE-3888

## Audit Passes

### A Resolving Citation Is Not a Correct Citation — Scope `Implements:` by Topic

Every `Implements:` docstring under `vultron/` resolves to *some* requirement,
so an existence-only traceability check cannot see a wrong-topic citation. The
trigger routers cited `TB-01-001` ("the system MUST use pytest") 236 times as
the requirement they implement, because the Testability topic shares the `TB`
prefix a trigger spec once used; `trigger_embargo.py` had 52 `TB-` and zero
`TRIG-` citations and every one of them resolved (#3354).

**How to apply:**

- `TB` (Testability) requirements govern tests. No module under `vultron/` may
  cite one in an `Implements:` docstring; the ratchet that enforces this
  (`test/architecture/test_implements_citations_topic_scoped.py`, SR-04-011, #3829) is
  topic-scoped, not resolution-scoped — it fails on any `TB-NN-NNN` token
  under `vultron/` by file and line, and separately checks that every
  `Implements:` ID under the FastAPI routers resolves in the registry, so a
  typo'd `TRIG` ID cannot replace a wrong `TB` one.
- Repointing is per-file judgment, not a prefix swap. `TRIG-02` splits by
  domain (`-001` report, `-002` embargo, `-004` case, `-005` participant,
  `-006` demo-only), so a blind `TB-02-001` → `TRIG-02-001` mints fresh
  wrong-but-resolving citations in four of five routers.
- Once a registry row carries `spec_ids`, the check becomes an import-time
  assertion over the table rather than a docstring scan.

Source: ISSUE-3354

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

**Applied naively, the rewrite over-reaches.** The same actor is both the
authority (a role) and a concrete node with a URI, an inbox, an outbox, a
DataLayer and a container. A role has no URI or inbox, so renaming an
*infrastructure* reference to `CASE_MANAGER` is the same category error as leaving
an *authority* reference as `CaseActor`. The discriminator:

- **Write "the CASE_MANAGER"** when the subject performs a single-writer authority
  action or holds an authority property: commits or authors canonical ledger
  entries, writes shared EM/CS state, sets participant state at bootstrap, is the
  sole authorized writer, authorizes a commit.
- **Keep "CaseActor"** for infrastructure and identity: its URI or
  `case_actor_id`, its inbox and outbox, HTTP-loopback self-delivery to its own
  inbox, its DataLayer, its container or co-location, delegated-emit store
  scoping (ADR-0073), a code identifier (`CheckIsOwnCaseActorNode`,
  `VultronCaseActor`), the `CaseActor` domain type, or the `case-actor` URL-shape
  anti-pattern a ratchet forbids.
- **Write "the actor enacting `CVDRole.CASE_MANAGER`"** when the text needs an
  actor grounded in the role — for example one that can fail a hosting test,
  which a bare role cannot.

The trap is a requirement that reads like authority but is delivery. The
canonical-ledger self-delivery requirements in `outbox.yaml` sound like an
authority obligation, yet every noun in them (own URI, own inbox, HTTP loopback)
is the concrete actor's plumbing: the commit *authorization* is the role, the
*delivery* of the self-copy is the actor. When in doubt on an
infrastructure-flavoured line, keep `CaseActor`.

A naming sweep is also a cheap way to surface stale premises, because it forces
you to read the rationale the term sits in. Check a rewrite candidate's
`refines:` and `adr:` parents for agreement, not only its wording: CM-20-001/004/
005 claimed to refine CBT-01-003 while their rationale asserted its opposite.
When two entries describe the same fact, make the laggard match the one that
already applied the decision.

Source: ISSUE-1872, ISSUE-3260, ISSUE-3342

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

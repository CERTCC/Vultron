---
status: accepted
date: 2026-09-22
deciders: [adh, Claude Opus 5]
consulted: []
informed: []
---

# ADR-0101: Spec Item Format Is Field Presence, Not a Class Choice; a Bare Item Cannot Be a `BehavioralSpec`

## Context and Problem Statement

MS-13-001 and MS-13-002 tell a spec author which *format* an item must use: a
`BehavioralSpec` when the item describes a sequential, stateful process, a
`StatementSpec` when it states a capability constraint or structural rule.
CONCERN-3506 asked for a check, because nothing enforced either one and the
learning from ISSUE-3480 had shown that an unenforced MUST does not merely go
unchecked — the corpus stops looking like it has the rule at all.

Measuring the corpus found that there was nothing for a check to read.

| Fact | Where |
|---|---|
| `BehavioralSpec` subclasses `StatementSpec` and every field it adds (`preconditions`, `steps`, `postconditions`) is optional | `vultron/metadata/specs/schema.py` |
| `Spec = Union[BehavioralSpec, StatementSpec]`, so under Pydantic's smart union a bare item satisfies the first branch | `vultron/metadata/specs/schema.py` |
| All 3074 items in `specs/` load as `BehavioralSpec`; 2913 of them carry no behavioral field at all | measured on `origin/main` |
| `_is_behavioral_file()` is a bare `isinstance` test, so all 69 spec files classify as behavioral although only 3 carry the `behavioral` tag | `vultron/metadata/specs/docs_render.py` |
| Every rendered spec page therefore opens with `## Behavioral Specifications` and its ECA blurb over the whole corpus; the `regular` bucket is always empty | measured on `origin/main` |
| The two `isinstance(spec, BehavioralSpec)` guards in the linter are vacuous; they work only because each is `and`-ed with `bool(spec.steps)` | `vultron/metadata/specs/lint.py` |
| `_build_graph()` labels every requirements-graph node `type: "behavioral"` | `vultron/metadata/specs/registry.py` |

So "which format did the author choose" is not a property of a loaded spec item.
The only observable property is *which behavioral fields the item carries*, and
the one consumer that trusted the class distinction was already producing a wrong
answer in published documentation.

Two further facts decided how to word the replacement.

**The signal CONCERN-3506 proposed is not clean.** The concern suggested flagging
a `BehavioralSpec` that carries `preconditions` or `postconditions` but an empty
`steps` list, on the grounds that this is a format choice half-made. 41 items are
in that shape, and they are overwhelmingly `RMB`/`EMB`/`CSB` protocol behavioral
items where it is the *intended* Event-Condition-Action idiom:
`notes/behavioral-conformance-specs.md` states that those groups always use
`BehavioralSpec`, with the condition in typed `preconditions` and `steps`
reserved for the cases where ordering is itself normative. `RMB-13-001` — "a
Participant MUST be in RM Accepted before sending RS", precondition "Participant
is in RM Accepted", no steps — is correct as written. The `DEMOMA-19`, `-20`,
`-21` and `-24` cases that ISSUE-3504 fixed were genuine only because MS-13-004
obliges steps *inside a `scenario_start` group*, and that rule already has its
check.

**MS-13-002 is not merely unenforced; it is wrong as worded.** It requires
`StatementSpec` whenever a requirement "does not depend on step ordering". 33
single-step items — `CSB-09-002` "emit CV to announce the transition",
`EMB-01-003` "emit EK to acknowledge receipt", and their siblings — carry `steps`
as the *action* half of an ECA rule, not as an ordering claim. A one-element
sequence asserts no order. Enforcing MS-13-002 literally would demand rewriting
33 correct items and, with them, the ECA convention the behavioral conformance
corpus is built on.

## Decision Drivers

- A requirement phrased over a distinction the schema does not preserve cannot be
  enforced, and cannot be corrected by adding a check.
- An unenforced MUST anti-advertises: at partial adoption the corpus reads as
  having no rule, which is worse than none (the ISSUE-3480 learning).
- Advisory output is not a form of enforcement here. `spec-lint` already emits a
  `must_without_verification` warning for MS-13-001 and MS-13-002 themselves, but
  1190 of 2186 MUST items lack a `verification:` field (5 suppressed), so that
  detector contributes 1185 of the run's 1549 `[WARN]` lines. A new advisory line
  would be invisible.
- The project has no WARN-and-defer category (`completeness-doctrine.md`).
- A second spelling of a derivable fact is a drift channel (MS-16-002, ADR-0098).

## Considered Options

- Make `BehavioralSpec` require behavioral content, so the class distinction
  becomes true and every existing `isinstance` consumer becomes correct.
- Add an `is_behavioral()` predicate over field presence and update each call
  site, leaving the classes indistinguishable.
- Add an explicit `format:` field to every spec item.
- Flag `preconditions`/`postconditions` without `steps`, as CONCERN-3506
  proposed.
- Report a corpus census in the shape of `vultron/metadata/specs/coverage.py`
  and let a human triage.

## Decision Outcome

Chosen option: **make `BehavioralSpec` require behavioral content**. A
`mode="after"` validator rejects a `BehavioralSpec` carrying none of
`preconditions`, `steps`, or `postconditions`; because the branch then fails, the
`Spec` union falls through to `StatementSpec` for a bare item. Format is
therefore *defined* as field presence, and the class records it faithfully.

This is the enforcement of MS-13-002, by construction: a bare invariant can no
longer claim behavioral status, and nothing needs to detect that it did. Both
statements are re-derived to speak of the fields an item carries rather than of a
class the author picks, and MS-13-002 stops demanding that single-step ECA rules
be rewritten.

MS-13-001 keeps a detector, but aimed at its real failure mode — an ordered
sequence flattened into `statement` prose, the anti-pattern
`notes/behavioral-conformance-specs.md` already names and MS-05-001 already
forbids. Scanning for inline enumeration markers on items with no `steps` yields
28 hits, among them `CM-23-002` ("MUST execute the following sequence: (1) …"),
`IO-02-002` ("MUST enforce the following fixed node ordering … (1) parse inbound
payload"), `CLP-10-010`, `CM-16-006`, `CM-16-007`, `CP-05-003` and `SBT-04-001`.

The check flags a *shape*, so the disposition of each hit is a human call: some
are ordered sequences that belong in `steps`, and some are genuine unordered
lists — `SBT-01-002`'s "three separate trees: (1) … (2) … (3) …",
`DEMOMA-12-009`'s list of assertions a test file must make — where converting to
`steps` would falsely assert an order. The mechanism for a knowingly-accepted hit
is the existing one: a named `LintWarningCode` plus per-item `lint_suppress`, not
a ratchet ceiling count. Every current hit is disposed of when the check lands,
so the rule reaches full adoption rather than the half-adoption that made
MS-13-003 invisible.

### Consequences

- Good, because the requirements graph's `type` attribute, the linter's two
  behavioral guards, and the docs renderer all become correct without being
  touched individually — the model stops lying and its consumers stop inheriting
  the lie.
- Good, because every published spec page stops claiming that the entire corpus
  consists of ECA requirements with typed preconditions, ordered steps and
  postconditions.
- Good, because MS-13-002 needs no runtime check at all, so there is no second
  detector to keep in sync with the schema.
- Bad, because a malformed item now fails *both* union branches, and a
  two-branch Pydantic error is harder to read than a one-branch one. Loader
  failure attribution must be preserved deliberately (MS-17,
  `vultron/metadata/AGENTS.md` § "Loader Failure Attribution").
- Bad, because an author who intends a behavioral item but supplies no
  behavioral field silently gets a `StatementSpec` rather than an error. This is
  accepted: the two are indistinguishable in every consumer, so there is no
  observable difference to report.
- Neutral, because the 41 precondition-without-steps items are unaffected. They
  remain `BehavioralSpec`, which is what the ECA idiom intends.

## Validation

The union resolution was validated directly before adopting it: with the
`mode="after"` validator in place, an item carrying no behavioral field resolves
to `StatementSpec`, and items carrying `steps` or `preconditions` resolve to
`BehavioralSpec`. Post-change the corpus is expected to split 2913
`StatementSpec` / 161 `BehavioralSpec`.

Enforcement is by `spec-lint` (SR-04-003) plus the schema itself, both run by
`.github/workflows/spec-check.yml` on every `specs/**` change. A regression test
asserts that a known non-behavioral file renders outside the
`## Behavioral Specifications` section, and that the requirements graph labels a
bare item `statement`.

## Pros and Cons of the Options

### Make `BehavioralSpec` require behavioral content

- Good, because it repairs the distinction at its source, so every consumer is
  fixed once rather than per call site.
- Good, because it needs no data migration — the corpus already carries the
  fields the decision reads.
- Bad, because it changes loader behaviour, so error attribution needs a test.

### An `is_behavioral()` predicate over field presence

- Good, because it cannot change how any file loads.
- Bad, because the classes keep lying, so the next consumer to reach for
  `isinstance` inherits the same defect. The docs renderer is the evidence that
  this happens.
- Bad, because it requires finding every existing call site, and a missed one
  fails silently rather than loudly.

### An explicit `format:` field on every item

- Bad, because it is a second spelling of a fact derivable from the item's own
  fields, and the two can disagree — the drift channel MS-16-002 and ADR-0098
  exist to close.
- Bad, because it is a 3074-item migration with no new information.

### Flag `preconditions`/`postconditions` without `steps`

- Good, because it needs no judgement.
- Bad, because it is wrong: 41 hits, of which the `RMB`/`EMB`/`CSB` majority are
  the intended ECA shape. A check whose output is mostly false positives trains
  authors to suppress it.

### A corpus census, not a gate

- Good, because it makes the corpus legible without blocking anyone.
- Bad, because the project already has an advisory for this defect class and it
  is drowned: 1185 of 1549 `[WARN]` lines. A census would be read once, on the
  day it was written.

## More Information

CONCERN-3506 recorded the concern; the theme-candidate learning behind it is
`plan/incoming/learnings/20260922-3480-an-unenforced-must-is-invisible-to-the-planning-that-needs-it.md`,
which named MS-13-001 and MS-13-002 as suspected siblings of the unenforced
MS-13-003 that ISSUE-3504 fixed. The prediction in that learning — that
unenforced requirements cluster, because whatever left the first one unchecked
left its neighbours unchecked too — held, and the cluster turned out to include
the schema that made all four unenforceable.

The drowned `must_without_verification` advisory is tracked separately as part of
this decision's implementation: its per-item output collapses to a summary plus
an opt-in listing, and an unverified-MUST ceiling follows the never-raise pattern
of `MAX_UNCOVERED_PROTOCOL_SPECS` in
`test/architecture/test_spec_coverage_ratchet.py`.

Generated spec requirements: `specs/meta-specifications.yaml` MS-13-001 and
MS-13-002 are re-derived by this decision; MS-13-003 and MS-13-004 are unchanged.

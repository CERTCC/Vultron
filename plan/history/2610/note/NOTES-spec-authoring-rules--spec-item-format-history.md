---
source: NOTES-spec-authoring-rules--spec-item-format-history
timestamp: '2026-10-14T14:33:11.986416+00:00'
title: 'spec-authoring-rules: spec item format (BehavioralSpec) cost and MS-13-002
  history'
type: note
---

Archived from `notes/spec-authoring-rules.md` by #4498: the section described what the BehavioralSpec smart-union defect cost and claimed the ADR-0101 validator had landed. It has not: a bare item still loads as `BehavioralSpec`, and the fix is open Task #3520 (with #3521 for the flattened-sequence check). The lasting rule (read format off fields; do not flag preconditions without steps) stays in § "Spec Item Format Is Field Presence, Not a Class You Pick".

---

## Removed text

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

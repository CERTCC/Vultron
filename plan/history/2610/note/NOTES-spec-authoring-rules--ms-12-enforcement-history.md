---
source: NOTES-spec-authoring-rules--ms-12-enforcement-history
timestamp: '2026-10-14T14:33:11.563422+00:00'
title: 'spec-authoring-rules: MS-12 enforcement history and MS-12-006 scoping derivation'
type: note
---

Archived from `notes/spec-authoring-rules.md` by #4498: the story of how MS-12 went unenforced (#2601, #3480) and the measured derivation of MS-12-006 are history. The rules (never copy neighbouring kinds; the five MS-12-006 scoping choices; an unenforced MUST anti-advertises) stay in `notes/spec-authoring-rules.md` § "Apply the decision tree, not the neighbouring entries" and § "Why MS-12-006 is scoped the way it is".

---

## Removed text

Do **not** infer a spec's `kind` by copying the entries around it. That heuristic
is what produced the defect behind ISSUE-2601: MS-12 went unenforced from its
adoption until 2026-09, and by then a large fraction of the `kind: protocol`
corpus was carrying `lint_suppress: [missing_story_reference]` instead of a
corrected `kind` — code naming conventions, test-coverage requirements, and
build-file formats all tagged as wire-protocol obligations. `spec-lint` prints
the live carrier total (`[INFO] lint_suppress missing_story_reference: …`); it is
computed from the specs, never committed. Suppressing the story-traceability gate
is almost never the right response to it firing; a spec that cannot be traced to
a user story is usually mis-classified, not story-less. MS-12-006 now makes the
unambiguous cases a hard error, and MS-12-007's PR-only growth guard
(`test_no_pr_adds_a_missing_story_suppression` in
`test/architecture/test_spec_kind_ratchet.py`) fails any PR that adds a carrier,
but neither detects a misclassification whose statement names no code. MS-12-008
holds MS-12-006's own escape hatch, `protocol_kind_with_code_reference`, at no
carrier at all, so a suppression cannot move from one code to the other unseen.

### Why MS-12-006 is scoped the way it is

MS-12-006's rationale defers here, because the three scoping decisions are what
keep it from becoming the problem it was written to solve. Each one was measured
against the live corpus.

**It fires only on specs with no `stories:`.** Scanning every `kind: protocol`
spec looks stricter and is much worse. A protocol spec that traces to a user
story has already demonstrated it is protocol, and its `verification:` field
names a `test/…py` path *because MS-10-003 obliges every MUST to carry one and
MS-15-001 obliges the path to resolve*. Applied to the whole protocol corpus the
detector flags roughly half of it, and the majority of those hits are specs that
are fully SR-11-compliant, and what they name is the test that MS-10-003
obliges, not how the rule is met. Gating on the absence of a story confines the
check to the population where a codebase reference most often means the
statement needs rewording or splitting.

**The token list excludes bare `module`, `class`, and `function`.** Those read as
ordinary domain English in wire requirements — "a machine-readable failure
class", "the same action class", "the actor's function in the CVD process". Left
in, they flag two dozen genuine protocol statements that need no rewording.
`.py`, `vultron/`, `test/`, `scripts/`, `pytest`, `pydantic`, and `py_trees`
carry no such second meaning.
The cost of the omission is a handful of true positives the check will not catch;
those are MS-12-006's acknowledged blind spot, not an oversight.

**The error says reword or split, never relabel.** A code token in a protocol
statement does not make the rule `project`: who must obey it decides that
(MS-12-002). The token means the statement either spells a protocol rule in
this codebase's terms, which is reworded, or also says how this codebase meets
the rule, which is split (MS-12-010). A message that prescribed a kind would
repeat the literal reading ADR-0134 rejected — PR #4520 (#3601) applied it and
moved genuine protocol rules to `project`.

**`foundation` is scanned too.** A `foundation` statement that names this
codebase's code also says how this codebase meets an inherited rule, so it is a
mixed spec: split it (MS-12-010). The suppression code keeps its
`protocol_kind_with_code_reference` name, which specs already carry.

The general lesson, from ISSUE-3480: **an enforced MUST advertises itself through
full compliance in the artifacts; an unenforced one anti-advertises.** A rule at
half adoption reads to the next author as "no rule here" — worse than one at zero
adoption, which at least reads as "not done yet".

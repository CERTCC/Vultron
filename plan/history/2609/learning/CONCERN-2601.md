---
source: CONCERN-2601
timestamp: '2026-09-23T20:45:14.047216+00:00'
title: An unenforced classification rule accumulated 277 suppressions instead of corrections
type: learning
---

## Original concern

SR-11 added bidirectional spec-to-story traceability with a hard-error lint gate
(SR-11-003): `kind:protocol` + `priority:MUST` + no `stories:` → CI failure.

During the 2026-08-25 mapping pass, ~120 specs could not be mapped to any existing user
story — not because stories are missing, but because these specs are genuinely
`kind:project` or `kind:process` and should never have been tagged `kind:protocol`.
They describe code naming conventions, test coverage requirements, BT composition rules,
build-file formats, and internal API contracts — none of which are Vultron protocol
compliance requirements. The right fix is to change their `kind:` field, not to write
user stories for them. Once reclassified, SR-11-003 no longer applies and the
`lint_suppress: [missing_story_reference]` entries can also be removed.

The concern enumerated 121 candidate spec IDs across six categories (code style and
naming, internal API/architecture boundaries, build/workflow/history file formats, test
coverage requirements, vocabulary/data-model internals, and protocol state-machine edge
cases flagged as borderline pending #2598).

## What measurement showed

Two of the concern's premises were wrong, and both errors pointed the same way — the
work is larger and differently shaped than described.

**The count is 277, not ~120.** The concern's figure was a snapshot from the
2026-08-25 pass. The suppression list kept growing afterward. At planning time the
corpus held 310 `missing_story_reference` suppressions, of which 277 are *live*
(`kind:protocol` + `priority:MUST` + no `stories:`) and **33 are already dead** — the
spec is no longer `kind:protocol`, or is not `priority:MUST`, so SR-11-003 cannot fire
for it at all. Those 33 can be deleted with no judgment whatsoever. Of the 121 IDs the
concern named, all still exist and 119 are still `kind:protocol`; only `TRIG-09-002`
had ever been fixed.

**SR-11-003 is green, and that is the problem.** Zero protocol MUSTs fail unsuppressed.
This was never a broken-CI problem; it is a corpus-integrity problem hiding behind a
suppression list that grew unnoticed because nothing measured it.

**The criteria the concern proposed writing already existed.** #2840 set its AC-1 as
"reclassification criteria are recorded, so the ~120-spec pass is mechanical." ADR-0038
established the four-tier portability hierarchy and its classification decision tree,
and MS-12-001 through MS-12-005 codify that tree as five MUST requirements in
`specs/meta-specifications.yaml` — including MS-12-005's normative ordering rule. The
criteria were declared, documented, and normative. Nothing enforced them: `grep MS-12`
across `*.py` and `test/` returned nothing.

## The generalizable finding

This is a second witness for the learning queued as
`20260922-3480-an-unenforced-must-is-invisible-to-the-planning-that-needs-it`, and it
strengthens that entry's claim in a specific way.

Issue #3480 observed that an unenforced MUST *anti-advertises*: a rule at partial
adoption reads to the next author as "no rule here", which is worse than 0% adoption
because 0% at least reads as "not done yet". That instance cost the project a nearly-shipped
duplicate schema field. This instance shows the failure mode's other end: the rule was
not merely invisible to planning, it was invisible to **277 consecutive authoring
decisions**, and each one reached for the available escape hatch (`lint_suppress`)
rather than the unenforced rule. An unenforced rule plus a suppressible gate composes
into a ratchet that turns the wrong way — every spec that trips the gate gets silenced,
and the silence is indistinguishable from a legitimate exemption.

The corollary for planning: the concern itself proposed authoring the criteria, because
from inside the corpus the criteria looked absent. A planner cannot tell "no rule" from
"unenforced rule" by reading artifacts, only by reading the meta-spec corpus directly.
That is exactly the search #3480 prescribes, and it is what found MS-12 here.

**A suppression escape hatch needs a ratchet at the moment it is introduced.** SR-11-003
shipped suppressibility with sound reasoning — "preserves an escape hatch for
implementation-detail MUSTs with no direct story antecedent" — and no ceiling on how
often it could be used. The escape hatch was correct; the missing piece was a pinned,
monotonically decreasing count, which the project already had a pattern for in
`test/architecture/test_spec_coverage_ratchet.py`'s `MAX_UNCOVERED_PROTOCOL_SPECS`.

## Second finding: local enforcement needed three layers, not one

`spec-lint` was already wired into `.pre-commit-config.yaml`, which at first looked
sufficient for local enforcement. It is not: that hook is gated on
`files: ^specs/.*\.yaml$`, so a change to `lint.py` with no spec YAML staged never
triggers it, and `run-linters` does not run `spec-lint` at all. A check that lives only
in `spec-lint` is therefore CI-strong and locally porous. The resolution was three
layers — the check in `spec-lint` (pre-commit, on spec edits), unit tests in
`test/metadata/specs/test_lint.py`, and a corpus ratchet under `test/architecture/`
that runs on every `uv run pytest` regardless of what is staged.

## Disposition

Planned as two Tasks under epic #2578, the domain epic #2840 designates. The concern's
framing — author criteria, relabel ~120 specs — was replaced by enforce-then-relabel.

Two new requirements were added rather than an ADR, because ADR-0038 already decided the
taxonomy and this work only applies it:

- **MS-12-006** — `spec-lint` MUST hard-error on a `kind: protocol` spec whose scanned
  text names an unambiguous codebase construct, suppressible via
  `protocol_kind_with_code_reference`. The detector is deliberately narrow (`.py`;
  `vultron/`, `test/`, `scripts/` paths; `pytest`, `pydantic`, `py_trees`, `module`,
  `class`, `function`) because genuine protocol specs quote wire field names in
  backticks (`case_id`, `log_index`) and a greedy matcher flags them.
- **MS-12-007** — a ratchet MUST pin the suppression count to a ceiling that is never
  raised.

Both carry `verification:` clauses, so neither repeats MS-12's own mistake.

Implementing MS-12-006's detector against the live corpus flags **182** of the 277 and
stays silent on **95**. The 95 are a genuine mix: some are `project`/`process` the
narrow detector misses (`BW-02-002`, `CLP-11-003`, `BT-06-005`), and some are genuinely
`kind:protocol` and were suppressed wrongly, needing stories rather than relabeling
(`CSB-17-009`, the `DUR-04-*` duration rules, `CLP-14-005`, `ENC-03-002`). Conflating
those two is the exact error this concern exists to prevent, so they were split apart
rather than bundled.

`notes/spec-authoring-rules.md` previously advised "check existing entries in the same
spec file for context before writing a new entry." That advice was replaced with the
decision tree itself: at 277 bad labels, the neighbouring entries are the least
reliable source available, and copying them is the mechanism that spread the
misclassification.

**Resolved**: 2026-09-23 — implementation tracked in #3600, #3601.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3599>.
Spec: `specs/meta-specifications.yaml` (MS-12-006, MS-12-007).
Notes: `notes/spec-authoring-rules.md`.

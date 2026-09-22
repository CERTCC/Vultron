---
source: CONCERN-3506
timestamp: '2026-09-22T16:08:27.550874+00:00'
title: MS-13-001 and MS-13-002 spec-format choices are unenforced
type: learning
---

## Concern (as filed)

MS-13 tells a spec author which *format* an item must use, and nothing enforced
the choice:

- **MS-13-001**: a spec item MUST use `BehavioralSpec` format (preconditions,
  `steps[]`, postconditions) when it describes a sequential, stateful process.
- **MS-13-002**: a spec item MUST use `StatementSpec` format when it expresses a
  capability constraint or structural rule that does not depend on step ordering.

Neither ID was cited by any test, so the corpus's format choices were unchecked in
both directions. #3504 was the evidence that an unenforced MUST does not merely go
unchecked — it becomes invisible: MS-13-003 had no ratchet either, six of twelve
scenario groups omitted its marker, and by the time #3480 needed a rule for "which
spec groups specify a demo scenario" the corpus looked like it had *no* rule.

The concern proposed two directions: (1) flag a `BehavioralSpec` carrying
`preconditions` or `postconditions` but an empty `steps` list, or (2) a corpus
census in the shape of `vultron/metadata/specs/coverage.py`.

## What planning found

**The distinction the two requirements constrain does not survive loading.**
`BehavioralSpec` subclasses `StatementSpec` and every field it adds is optional,
so under Pydantic's smart union a bare item satisfies the `BehavioralSpec` branch.
All 3074 items in `specs/` loaded as `BehavioralSpec`, 2913 of them carrying no
behavioral field at all. There was nothing for a ratchet to read.

**One consumer had already inherited the lie.** `_is_behavioral_file()` is a bare
`isinstance` test, so all 69 spec files classified as behavioral although only 3
carry the `behavioral` tag: every rendered spec page opened with
`## Behavioral Specifications` and its ECA blurb applied to the whole corpus, and
the non-behavioral bucket was always empty. The linter's two behavioral guards
were vacuous, and the requirements graph labelled every node `type: "behavioral"`.

**The concern's own direction 1 was the wrong signal.** 41 items carry
`preconditions`/`postconditions` without `steps`, and the `RMB`/`EMB`/`CSB`
majority are the intended ECA form — `RMB-13-001` ("MUST be in RM Accepted before
sending RS") is correct as written. The `DEMOMA` cases #3504 fixed were genuine
only because MS-13-004 obliges steps inside a `scenario_start` group.

**MS-13-002 was also wrong as worded**, not merely unenforced. It required
`StatementSpec` whenever ordering is not part of the requirement, which condemns
33 correct single-step ECA items whose one step is the required action.

**The project's existing detector for this defect class was drowned.**
`must_without_verification` fired on MS-13-001 and MS-13-002 themselves, but 1190
of 2186 MUST items lack a `verification:` field (5 suppressed), so it produced
1185 of spec-lint's 1549 `[WARN]` lines.

## Resolution

**Resolved**: 2026-09-22 — implementation tracked in #3520, #3521, #3522.

ADR-0101 decides that spec item format *is* field presence: a `mode="after"`
validator requires a `BehavioralSpec` to carry at least one of `preconditions`,
`steps`, `postconditions`, so a bare item falls through to `StatementSpec` and the
class records the format faithfully. That is the enforcement of MS-13-002 by
construction, and it repairs the docs-render defect and the vacuous guards at
their source. MS-13-001 keeps a detector, aimed at an ordered sequence flattened
into `statement` prose (28 current hits, each disposed of individually when the
check lands). The drowned advisory gets a never-raise ceiling and a collapsed
summary, wired under the epic that already owns the verification backfill.

All three implementation issues hang under Epic #2578 rather than the
demo-harness epic #3506 inherited, at its `Later` tier.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3519>.
ADR: `docs/adr/0101-spec-item-format-is-field-presence.md`.
Notes: `notes/spec-authoring-rules.md`, `notes/behavioral-conformance-specs.md`.

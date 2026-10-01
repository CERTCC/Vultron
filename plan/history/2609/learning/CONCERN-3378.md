---
source: CONCERN-3378
timestamp: '2026-09-30T20:39:11.368468+00:00'
title: 'G004 logging-f-string exclusion: template-plus-lazy-args is the message shape,
  record fields are the correlation mechanism'
type: learning
---

## Concern

ADR-0094 makes ruff the sole Python linter and excludes `G004`
(`logging-f-string`) from the selected ruleset. Unlike the other exclusions,
`G004` is excluded *despite the project agreeing with it*: f-strings in log calls
are eagerly evaluated, which defeats logging's lazy formatting and pays the
formatting cost even when the record is filtered out.

The reason it is excluded is that the fix is not mechanical. Rewriting
`logger.info(f"case {case.id} closed")` as
`logger.info("case %s closed", case.id)` interacts with the structured-logging
requirements in `specs/structured-logging.yaml`, which govern what a log record
should carry and in what shape. Choosing between `%`-style lazy args, structured
`extra=` fields, and whatever the structured-logging specs actually mandate is a
design question, not a lint cleanup.

The finding count is recorded in ADR-0094 with its measurement date (MS-16-001
forbids restating drifting counts here).

## Why this matters

`notes/lint-tooling.md` sets out four acceptable reasons for a project-wide
`ignore` entry, and explicitly rules out "too many findings to fix right now" —
that is what baselining with `RUF100` is for. `G004` does not fit any of the
three standing categories: it is not a house convention the rule contradicts, not
a cost with no requirement behind it, and not a competing gate. It fits only the
fourth — **a provisional exclusion, which the note requires to cite a tracking
issue so the entry expires when the question is answered.**

Without such an issue, `G004` sits in the `ignore` list as an unexplained-looking
entry that nobody will dare delete, which is precisely the accumulation failure
IMPLTS-07-019 exists to prevent. `PLC0415` is handled correctly this way,
citing #3350; this issue is the same treatment for `G004`.

## What this is not

This is **not** a request to enable `G004` now. The exclusion is correct until
the target log-call shape is decided.

## Suggested resolution path

- Read `specs/structured-logging.yaml` and decide the canonical form for a log
  call that interpolates values: lazy `%`-args, `extra=` structured fields, or
  both in defined circumstances.
- Record that decision wherever the structured-logging requirements live, so the
  rewrite has a target rather than a preference.
- Then enable `G004` and either autofix or baseline the residue per
  `notes/lint-tooling.md`, deleting the `ignore` entry and this citation.

## Reference

- Surfaced while reviewing #3351 (the ADR-0094 planning PR) against
  IMPLTS-07-019
- Decision record: ADR-0094, § "The exclusions and their reasons"
- Policy: `notes/lint-tooling.md`, § "Select families, exclude by exception"
- Specs: `specs/structured-logging.yaml`; IMPLTS-07-019
- Sibling precedent: #3350 (`PLC0415`)

---

**Resolved**: 2026-09-30 — implementation tracked in #3991 (enable `G004`,
rewrite every f-string log call) and #3992 (correlation fields on log records
via boundary context and a `logging.Filter`).

**What was decided.** The two shapes the concern weighed were never
alternatives. Lazy `%`-args decide how the *message text* gets its values;
`extra=`-style record fields decide what *attributes* the record carries beside
the message. Python's `logging` keeps `msg` and `args` apart for three reasons
the project relies on — the template is the event's stable identity, a
formatting fault stays inside logging instead of raising into a BT node, and
rendering is deferred until a handler emits — so the message shape is a literal
template with lazy positional arguments (SL-01-005), enforced by ruff's `G`
family. Correlation fields reach the record through ambient context set once at
the processing boundary and a `logging.Filter` (SL-02-003), never per-call
`extra=`, and an id in the message text does not satisfy SL-02 (SL-02-004).
With that, `G004` is enabled and every site rewritten; no provisional `ignore`
entry remains in the ADR-0094 configuration.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3990>.
Spec: `specs/structured-logging.yaml`.
Notes: `notes/structured-logging.md`, `notes/lint-tooling.md`.

---
title: "Two residual surfaces survive the MS-15-004 guard: 'replaces the old X' docstring asides, and CLP-09-003's uncovered protocol MUST"
type: learning
timestamp: "2026-09-02"
source: ISSUE-3022
signal: concern
---

Two things #3022 surfaced but did not close. Both are candidates for a
`type:Concern` issue.

## 1. "Equivalent to the old `X`" docstring asides keep retired names alive

MS-15-004 resolves a symbol as live if it appears anywhere in the `vultron/` or
`test/` Python text. `vultron/semantic_registry/__init__.py` carries migration
asides of the form "Equivalent to the old ``X`` dict", and each one is enough to
keep `X` resolvable — which is precisely how `USE_CASE_MAP` stayed invisible to
the guard while the spec corpus named it 11 times across 5 files, two of them
`kind: protocol` MUSTs. It was fixed in this PR only because the aside was
removed alongside it.

Still present in that module, and still shielding their symbols:

- `SEMANTICS_TO_ACTIVITY_CLASS` — "Equivalent to the old
  ``SEMANTICS_TO_ACTIVITY_CLASS`` dict" (`semantics_to_activity_class()`)
- `_ACTIVITY_SEMANTICS` — "replaces the old ``_ACTIVITY_SEMANTICS`` set" (module
  docstring); leading underscore means the regex would not match it anyway

Neither is currently cited by any spec, so nothing is stale *today*. The risk is
latent: a future spec citing either would pass the guard.

The tension is real — those asides carry genuine migration value for readers.
Options if this is taken up: move retirement notes to a single "retired symbols"
table outside the scanned trees, or narrow the corpus to AST-visible bindings and
accept the false positives that would create for docstring-only references.

## 2. CLP-09-003 is a protocol MUST with no marker and no test

`CLP-09-003` (`kind: protocol`, MUST) requires "a coverage test MUST enumerate
protocol-significant entries ... and assert each one reaches a commit". No such
test exists, and no `@pytest.mark.spec("CLP-09-*")` marker exists anywhere in
`test/`. Its own rationale is the giveaway: it records that
`validate_report`, `ack_report` and `close_case` produced no canonical ledger
entry on `main` for an unknown span (#998/#1022) *because* commit completeness had
no structural check. The requirement written to fix that gap is itself unverified.

This PR touched CLP-09-003 only to rename `USE_CASE_MAP` → `use_case_map()` in
three fields, leaving the obligation unchanged, and the coverage ratchet stayed
green (uncovered protocol specs went 923 → 919 against a 937 ceiling, since four
markers were added elsewhere). So SR-05-005 was not triggered. Recording it here
rather than silently leaving it: the gap predates the issue and closing it means
writing the enumerate-all-use-cases-to-ledger coverage test, which is its own
piece of work.

Note also that the ratchet ceiling (`MAX_UNCOVERED_PROTOCOL_SPECS = 937`) was
left alone despite the count dropping to 919. Lowering it to the new floor would
tighten the guard but could break in-flight parallel branches sitting between
920 and 937; that is a separate call.

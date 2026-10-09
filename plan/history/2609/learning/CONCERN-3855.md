---
source: CONCERN-3855
timestamp: '2026-09-29T17:37:12.069331+00:00'
title: Wire reference unions accept an empty string as a URI reference (CS-08-001)
type: learning
---

## Concern

The AS2 wire base hierarchy types object references as `as_Object | as_Link | str | ...`. The bare `str` member means a blank string validates as a URI reference and round-trips through `parse_activity`, which CS-08-001 forbids ("if present, then non-empty").

Found while fixing the same shape on `as_Question.anyOf`/`oneOf` in PR #3819 (the `_QuestionOptions` alias now uses `NonEmptyString`). The sibling fields were left as they were because changing the base hierarchy is a repo-wide sweep outside a PR that retires one poll.

## Where

- `vultron/wire/as2/vocab/base/objects/activities/base.py`: `as_Activity.target`, `origin`, `instrument`, `result`
- `vultron/wire/as2/vocab/base/objects/activities/intransitive.py`: `as_Question.closed`
- Any other `as_Object | as_Link | str` reference union across `vultron/wire/as2/vocab/` (grep `as_Link | str`).

## Measured remainder

1 of the 6 reference unions named above is fixed (`_QuestionOptions`); the other 5 plus whatever the grep finds across the vocabulary remain. The fix per field is a one-token change (`str` -> `NonEmptyString` from `vultron/primitives.py`), but the test fallout is unknown, so it needs a full-suite run and probably a ratchet test.

## Suggested shape

- A shared alias for the reference member (e.g. one `as_ObjectRef`-style union carrying `NonEmptyString`) rather than editing each field (CS-08-002).
- A ratchet under `test/architecture/` asserting no wire field admits `""` as a reference.

Source: PR #3819 pr-ship code review (deferred finding `phase8-wire-ref-unions-bare-str-0`).

**Resolved**: 2026-09-29 — implementation tracked in #3876, #3877.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3875>.

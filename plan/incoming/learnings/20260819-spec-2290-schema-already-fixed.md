---
title: "#2290 schema fix (verification field + extra=forbid) was already landed when work began"
type: learning
timestamp: 2026-08-19
source: ISSUE-2290
signal: process-issue
---

Issue #2290 described `verification:` as not a field on `Spec` model and
`extra="forbid"` as absent. By the time work started, both had already been
added in commit `a81b77ab` ("fix(schema): add extra=forbid + formalize 9
undocumented spec fields") without a `Closes #2290` footer.

The remaining work was:

- `llm_export.py:_spec_record` not emitting `verification`
- `lint.py:_check_phantom_paths` not scanning `verification`

The "test asserts no silent key drop" AC was also already satisfied by
`test_statement_spec_extra_field_rejected` (SR-02-022) in test_schema.py.

Lesson: always verify ACs against current `main` before starting; a prior PR
may have partially addressed an issue without a closing footer.

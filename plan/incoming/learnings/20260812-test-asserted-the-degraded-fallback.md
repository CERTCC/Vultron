---
title: Process — a test asserted the ARCH-15 violation as intended behaviour
type: learning
timestamp: 2026-08-12
source: ISSUE-2232
signal: process-issue
---

`test_resolve_participant_state_defaults_when_invalid_rm_type` asserted
`rm == RM.START` for a status whose `rm.state` was the string `"not-an-rm"`,
under the docstring *"Falls back to RM.START when rm_state is not an RM enum
value."*  That is precisely the defect #2264 describes: substituting `RM.START`
for an unreadable status silently resets the participant's RM ladder to its
initial state, after which the next legitimate transition is rejected as
backwards.

The test did not merely fail to catch the bug — it **locked it in**.  Fixing
the code turned a green test red, so the regression suite argued for the
defect.  ARCH-15-001..004 ("Silent `None` Returns and Fake `SUCCESS` Are the
Same Bug") already forbade the behaviour when the test was written.

Two things made it look reasonable:

1. The word *"defaults"* in the test name conflates **absence** with
   **unreadability**.  `RM.START` is the right answer for a participant with no
   recorded status; it is never the right answer for a status that exists but
   cannot be read.  The sibling
   `test_resolve_participant_state_defaults_when_no_statuses` covers the
   legitimate case and still passes unchanged.
2. Asserting the observed behaviour of a defensive `isinstance` fallback feels
   like coverage.  It is really a snapshot of an unreviewed default.

**Signal to watch for in review:** a test whose docstring says "falls back
to", "defaults to", or "tolerates" for *malformed* input, rather than for
*absent* input.  Ask which of the two the fallback is actually serving; if it
is malformed input, ARCH-15 requires a raise or `Status.FAILURE` and the test
is asserting a bug.

Note also that `test_resolve_participant_state_defaults_when_invalid_vfd_type`
was left passing on purpose: the vfd dimension remains lenient because RM is
read first, so a wire-shaped status raises before vfd is reached.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: test that says 'falls back to' for malformed input asserts a bug.
Docs PR: TBD.

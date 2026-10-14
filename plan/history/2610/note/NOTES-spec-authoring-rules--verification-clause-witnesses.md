---
source: NOTES-spec-authoring-rules--verification-clause-witnesses
timestamp: '2026-10-14T14:33:12.892785+00:00'
title: 'spec-authoring-rules: verification clauses that verified nothing (witness
  table)'
type: note
---

Archived from `notes/spec-authoring-rules.md` by #4498: the five witness clauses are already summarised in MS-10-009's rationale. The rule and its one question stay in § "A Verification Clause Is a Claim About the Suite".

---

## Removed text

## A Verification Clause Is a Claim About the Suite

A `verification:` clause tells every later reader how the requirement is known
to hold, and an unbacked clause reads exactly like a backed one. MS-10-009
requires the clause to name a check that exists and that inspects the property
the statement asserts. Five sessions found clauses that did not:

| Requirement | What the clause named | Why it verified nothing |
|---|---|---|
| DEMOCI-11-009 | `mkdocs build --strict` renders the scenario table | Strict mode never sees a link a build-time block prints; the page shipped with nine `.md` links that 404 on the built site, on a green build (#3450) |
| VM-01-004 | A test asserting the actor dual key | The test did not exist, and the stale wording licensed six bogus registry keys (#2982) |
| DR-03-002 | Nothing | No clause, so nobody noticed it named the wrong component (#3827) |
| MS-13-003 | Nothing | No check, half adoption, and the corpus read as having no rule; planning nearly invented a duplicate (#3480) |
| ADR-0099's unknown-key rule (now ARCH-25-007, ARCH-25-008) | The epic's closed children | Graduated to `accepted` with two details unbuilt; a `lint_suppress` in the same commit hid the prose/status mismatch (#3888) |

**How to apply:** for each clause you write or review, ask one question — *if
this requirement were violated, would the named check fail?* A build, lint or
type-check that never examines the constrained artifact fails the question, and
so does a test whose name you have not opened. For a build-time-rendered page,
assert on the built `site/` (`docs-links`, DOCBW-03-007) or on the rendered string
in a unit test. MS-15-001 makes a named path resolve; a named test function is
not yet checked (#4170), so open it. The question is part of `pr-triage`'s spec
conformance phase.

Source: ISSUE-3450, ISSUE-2982, ISSUE-3827, ISSUE-3480, ISSUE-3888

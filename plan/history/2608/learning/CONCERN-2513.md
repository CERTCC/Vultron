---
source: CONCERN-2513
timestamp: '2026-08-27T19:39:00.302951+00:00'
title: no docs-sync signal in build/bugfix/learn — docs drift silently as code changes
type: learning
---

## Concern

The `build`, `bugfix`, and `learn` skills had no explicit step to check whether code
changes required corresponding updates to `docs/`. As a result, the `docs/` directory
drifted silently out of sync with the codebase — features shipped, APIs changed, and
architecture evolved without updating user-facing and developer documentation.

## Resolution

Planned in docs PR <https://github.com/CERTCC/Vultron/pull/2779> and implementation
issue #2780.

Two spec requirements were added to `specs/project-documentation.yaml` (PD-03 group):

- **PD-03-007** (MUST): When an implementation or bug-fix PR changes behavior,
  interfaces, or architecture described in `docs/`, the PR MUST include the
  corresponding `docs/` updates or a linked follow-up `type:Concern` issue.
  Inline update is preferred for edits to existing pages, adding a single new page,
  or rewriting a single existing page. A deferred Concern is acceptable only when
  the required update would simultaneously rewrite multiple `docs/` pages.

- **PD-03-008** (SHOULD): Agents SHOULD invoke the `check-docs-sync` skill after
  implementation is complete and validated but before the PR opens.

Implementation issue #2780 delivers the `check-docs-sync` skill and wires it into
`build`, `bugfix`, and `learn`.

## Design decisions

- Placement in build: after implementation + validation is complete, before PR opens
- Small/large threshold: edits to existing pages + single new page + single page
  rewrite = do now inline; simultaneous complete rewrite of multiple pages = file
  type:Concern
- Strong bias towards in-PR fixes ("always easier to do updates alongside the change")
- `learn` also gets explicit invocation for consistency

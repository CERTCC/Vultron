---
title: Bug #1787 was already fixed on main but left open with no Closes footer
type: learning
timestamp: 2026-07-29
source: ISSUE-1787
signal: process-issue
---

Issue #1787 (CREATE_CASE_PROPOSAL phrase `{target}` slot) described a bug that
had **already been fixed** on `main` before the bugfix session started. The
phrase was changed to `"{actor} proposed a new case"` in commit `f415f83a`
("docs: promote learnings…", 2026-07-28), which merged as part of a docs PR.
The issue's own comment said "Will close when the docs PR merges" — but that PR
carried no `Closes #1787` footer, so the issue stayed OPEN after merge.

This is the AGENTS.md pitfall "Verify Issue ACs Against Current Code Before
Starting" (sources ISSUE-1510, ISSUE-1484) recurring again. The code fix
needed nothing; the real remaining gap was a **missing regression test** (the
phrase could silently regress — see the companion learning on defaultdict
masking).

**How to apply:** When a bugfix issue references a fix that a prior branch/PR
claims to have made, `git log -S "<fix string>" -- <file>` against `origin/main`
before writing any code. If the fix is present, pivot the session to what is
actually missing (usually a regression test) rather than re-applying the fix,
and ensure the closing PR carries `Closes #N`. When a docs/learn PR fixes a bug
as a side effect, it MUST include the `Closes #N` footer for that bug issue.

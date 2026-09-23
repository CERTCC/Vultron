---
title: "The workflow that publishes the site has no spec group, so a requirement about publishing has to be bolted onto the spec for the workflow that reviews"
type: learning
timestamp: "2026-09-23T21:45:00Z"
source: ISSUE-3549
signal: spec-gap
---

`specs/docs-build-workflow.yaml` (DOCBW) opens by pinning its subject:

> DOCBW-01-001: The workflow file MUST be named
> `.github/workflows/docs-build-check.yml`.

and its description says it covers "the GitHub Actions workflow that verifies the
MkDocs site builds cleanly", explicitly distinguishing itself from
`python-app.yml` and `demo-integration.yml`. It does not mention
`deploy_site.yml`, and no other spec group does either. **The workflow that
actually publishes the site is unspecified.**

That became load-bearing in ISSUE-3549. The withheld-artifact gate has to run on
`deploy_site.yml` — that is the whole point, since that workflow is the one that
uploads `site/` to Pages. The requirement had to go somewhere, and the only
plausible home was DOCBW-03, the *Job Structure* group of the reviewing
workflow's spec. So DOCBW-03-006 now reads "Every workflow that builds the site
MUST run the DOCBW-03-005 step, including `.github/workflows/deploy_site.yml`" —
a clause about workflow B living inside a spec whose first requirement declares
its subject to be workflow A.

**The gap.** Publishing is a distinct concern with its own obligations, and none
of them are written down: which branch publishes, what must be true of `site/`
before the upload, what must gate the upload, what happens on a failed deploy,
and which artifacts must be absent. Right now the only one of those that exists
anywhere is the one ISSUE-3549 needed, and it is a guest in another group.

Two consequences, both already visible:

- **A requirement about publishing is unfindable.** An agent asking "what must be
  true before the site is published?" loads DOCBW, reads DOCBW-01-001, and
  correctly concludes the spec is about a different workflow. The one clause that
  answers the question is three groups down, inside *Job Structure*.
- **The asymmetry is now encoded rather than merely present.** After ISSUE-3549 the
  withheld check is required on every site-building workflow, while the `--strict`
  build is required on none (ISSUE-3051). Those two facts belong side by side in a
  publishing spec, where the inconsistency would be obvious. Split across DOCBW-03
  and an open bug, it reads as two unrelated items.

**How to apply.** A requirement whose subject is a file the enclosing spec
declares out of scope is the signal — check the spec's identity requirement
(DOCBW-01-001 here) before adding to a group, not after. When the subject does not
match, the honest options are a new group scoped to the other artifact or a new
topic, not a clause that widens an existing group's subject silently. The
candidate shape here is a `DOCBW-06 Site Publication` group, or a separate topic
covering `deploy_site.yml`, carrying: the publish branch and trigger, the
pre-upload gate set (withheld artifacts, and `--strict` once ISSUE-3051 lands), the
required step ordering relative to `actions/upload-pages-artifact`, and the
`notify-failure` wiring CISEC-05 already requires of it.

Note that the *implementation* side of this is already correct and tested —
`test/ci/test_withheld_gate_in_workflows.py` derives its targets from every
workflow running `mkdocs build`, so coverage does not depend on the spec naming
files. The gap is that the spec's structure does not reflect what the tests
already know.

Corroboration needed: one instance, though it is structural rather than
behavioural, so a second witness is less about frequency than about whether the
same spec keeps accreting out-of-subject clauses. A second witness would be any
other requirement added to a spec group whose topic-level identity clause names a
different artifact. A negative witness would be a maintainer judging that DOCBW's
subject is "docs CI broadly" and DOCBW-01-001 is the clause that is wrong, which
would make this a one-line fix to the identity requirement rather than a missing
group.

Related: [[20260923-3549-a-gate-added-to-the-reviewing-workflow-is-not-a-gate-on-the-shipping-one]]
is the behavioural half — this entry is a candidate explanation for why that
failure mode recurs, since a concern with no spec group has no checklist to be
absent from.
[[20260922-3480-an-unenforced-must-is-invisible-to-the-planning-that-needs-it]]
is the nearer queued entry in kind: both are about a requirement that exists but
is positioned so that the reader who needs it will not encounter it.

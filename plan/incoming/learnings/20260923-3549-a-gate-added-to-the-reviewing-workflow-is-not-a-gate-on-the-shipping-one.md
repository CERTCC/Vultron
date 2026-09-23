---
title: "A gate added to the workflow that reviews is not a gate on the workflow that ships, and the reviewing one is the only one in front of you"
type: learning
timestamp: "2026-09-23T21:40:00Z"
source: ISSUE-3549
signal: theme-candidate
---

ISSUE-3549 exists because `docs/ns/` was published while claiming not to be:
`docs/ns/index.md` carried `draft: true`, a key of the Material *blog* plugin
rather than of MkDocs, so the frontmatter read as a suppression and suppressed
nothing. The issue's own AC-3 is the remedy — "a CI check fails if a `withheld`
artifact appears in `site/`" — and the fix was a checker plus a workflow step.

The step went into `.github/workflows/docs-build-check.yml`. That workflow is
`pull_request` and `workflow_dispatch` only. The workflow that actually publishes
is `deploy_site.yml`: it builds `site/` on a push to `publish` and hands it to
`actions/upload-pages-artifact`. So the first implementation gated the reviewing
path and left the shipping path open — for a defect whose entire consequence is
"the artifact reaches Pages". The gate would have been green on every PR while
the thing it forbids shipped.

Nothing about that was subtle in hindsight. It survived because
`docs-build-check.yml` is the file you are already looking at when you think
"where does a docs check go?" It is the workflow named in the docs-CI spec
(DOCBW-01-001), it is the one whose `paths:` you edit, and it is the one whose
name contains the word *check*. `deploy_site.yml` is not adjacent to any of that.

**The claim.** For any gate, the workflow that *reviews* and the workflow that
*ships* are different files, and the reviewing one is the only one in your
working set. A gate is not a property of a check — it is a property of the set of
paths on which the check runs. So the question that finds the gap is not "does a
check exist?" but **"enumerate every path by which this artifact can reach a
user, and name the check on each."** Asking it of the withheld check produced
`deploy_site.yml` immediately; not asking it produced a complete-looking PR.

Two things make this cheap to get wrong repeatedly. A gate's *absence* on a path
is invisible — there is no failing job to notice, because the job does not exist.
And the reviewing workflow's success is affirmative evidence of the wrong
proposition: it proves the check works, which reads as proof that the check is
installed.

**A second, independent instance already sits in the tracker.** Neither
`docs-build-check.yml` nor `deploy_site.yml` passes `--strict`, so
`mkdocs.yml`'s `validation.nav.omitted_files: warn` and
`validation.links.anchors: warn` cannot fail anything. ISSUE-3051 is that bug,
and its Problem section names `deploy_site.yml:50` explicitly — but the issue is
*titled* and framed around `docs-build-check`, so the publishing half has been
recorded-but-not-headlined since it was filed. Same asymmetry, same direction:
the reviewing workflow is what the finding is about, and the publishing workflow
is a line in the body.

**How to apply.** When adding or reviewing a CI gate, grep for every workflow
that produces the artifact the gate inspects rather than editing the one the
issue mentions — for site checks, `grep -ln 'mkdocs build' .github/workflows/`.
Then write the coverage claim as a test over the workflow set, not as a step in
one file: `test/ci/test_withheld_gate_in_workflows.py` derives its targets from
"every workflow running `mkdocs build`", so a *new* site-building workflow fails
until it carries the gate. A step added by hand to two files does not have that
property, and a spec clause naming two filenames does not either. Ordering
matters for the same reason and is part of the same assertion: the check must
follow the build (it reads `site/`) and precede the upload (after it, the
artifact is already out).

Corroboration needed: one session, with ISSUE-3051 as a same-repo sibling in the
same direction rather than a clean second witness. A second witness would be any
session that adds a check, a lint, or a policy step to a pull-request workflow
while a release, deploy, or publish workflow performing the same build keeps
running without it — or the inverse, a gate correctly installed on the shipping
path first. A negative witness would be a repo where the review and publish paths
genuinely share one reusable workflow, which is the structural fix this entry is
implicitly arguing for.

Related: [[20260921-3450-a-verification-clause-naming-strict-does-not-verify-a-rendered-link]]
is the nearer queued entry and is about the same family of false assurance, one
level down — there a *named tool* does not inspect the property claimed of it;
here a *real, working check* does not run on the path that matters. Both produce
a green signal that answers a question nobody asked.
[[20260918-3399-a-structural-fix-leaves-the-hazard-one-node-upstream]] shares the
shape "the fix landed on the site named in the report and the defect survived at
an adjacent one", but its mechanism is py_trees status semantics inside one
branch, not the enumeration of deployment paths, so it is a family resemblance
rather than corroboration.
[[20260923-3549-the-publishing-workflow-has-no-spec-group]] is the spec-level
half of this entry, and a candidate mechanism for it.

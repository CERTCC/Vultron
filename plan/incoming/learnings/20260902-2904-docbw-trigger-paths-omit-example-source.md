---
title: DOCBW-02-001's trigger-path rationale is factually wrong — the source of ~101 rendered pages is outside the docs workflow's trigger set
type: learning
timestamp: "2026-09-02T00:00:00Z"
source: ISSUE-2904
signal: spec-gap
---

`specs/docs-build-workflow.yaml` DOCBW-02-001 lists the paths that trigger
`docs-build-check.yml` and justifies the list like this:

> These are the files that can break the site build or introduce broken links.

That is not true. ~101 `markdown_exec` blocks under `docs/howto/activitypub/`
are one-liners of the form `print(json2md(some_example()))`; their entire
content is generated at build time by code in
`vultron/wire/as2/vocab/examples/`. `vultron/**` is not in the trigger set.

Issue #2904 is the proof. A single line in
`vultron/wire/as2/vocab/examples/_base.py` broke every one of those pages, and
none of DOCBW-02-001's listed paths was touched — so on the PR that introduced
it, the docs workflow would not even have started.

Note that DOCBW-03-002 already reaches for the right instinct ("the Build Site
step MUST run on every workflow trigger regardless of which paths changed"), but
a step that always runs cannot help when the workflow never fires.

**How to apply:** when a page's content is *computed* rather than written, the
code that computes it is part of that page's source and belongs in the docs
workflow's trigger paths. Before trusting a path-filter rationale, ask which
directories the rendered output actually depends on — for executable docs that
set is larger than `docs/**`.

Filed as #3070. Related but distinct: #3051 (the docs build does not run
`--strict`, so warnings never fail). Fixing either alone leaves a hole:
issue #3051 makes failures fatal but only when the workflow runs, while #3070
makes it run but only matters once failures are fatal.

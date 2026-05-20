---
source: IDEA-582
timestamp: '2026-05-20T13:54:12.117904+00:00'
title: 'Optimize linkchecker.yml: separate build-site and link-check triggers'
type: idea
---

## #582 Optimize linkchecker.yml: separate build-site and link-check triggers

The `.github/workflows/linkchecker.yml` workflow is set to run on any change
to markdown files anywhere, when it was originally intended to ensure that the
mkdocs site (almost entirely contained within `docs/`) (a) Builds successfully
and (b) doesn't have any broken links. The link checker step itself is slow
because it requires crawling the site. We shouldn't try to speed it up, but
we are running it on too many changes (e.g., to `plan/` `specs/` `notes/`
etc.) and should narrow the trigger conditions and separate the build-site step
(always run that to make sure python changes don't break ability to use
embedded python in mkdocs site) versus the link-checker (only needed when
something in `docs/` changes).

**Processed**: 2026-05-20 — design decisions captured in
`specs/docs-build-workflow.yaml` (DOCBW-01 through DOCBW-05) and
`notes/docs-build-workflow.md`.

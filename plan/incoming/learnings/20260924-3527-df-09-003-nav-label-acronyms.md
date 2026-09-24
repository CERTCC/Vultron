---
title: >
  DF-09-003 does not say whether a nav label rendered as generated link text is
  a first use of an acronym
type: learning
timestamp: 2026-09-24T15:30:00+00:00
source: ISSUE-3527
signal: spec-ambiguity
---

DF-09-003 requires acronyms to be expanded at first use on each rendered
`docs/` page. The landing-page generator (`vultron/metadata/docs/landing_pages.py`)
renders each `mkdocs.yml` nav label as link text, followed by the child page's
`description:`. Labels such as "FVV Demo", "FV Demo Protocol" and "Vultron AS
Objects" therefore print an acronym just before the description that expands it.

The review of PR #3629 read that as a DF-09-003 violation. Expanding the label
would lengthen the site navigation, which reuses the same label, so the PR left
the labels as they are.

Open question for `learn`: does DF-09-003 exempt navigation labels and generated
link text, or must the nav label itself carry the expansion? The answer decides
what #3617 does when it generates sub-section listings, and whether the
generator should lint labels against `docs/_acronyms`.

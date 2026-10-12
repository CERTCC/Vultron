---
source: CONCERN-4487
timestamp: '2026-10-12T16:20:35.757667+00:00'
title: the user-story set is stale and has no stories for contributors or maintainers
type: learning
---

## Concern

The 111 user stories in `docs/reference/user_stories/` are the only "why" a requirement can link to, and the set has drifted out of date in four ways. Measured on 2026-10-12:

1. **No stories for the people who build and run the project.** Every story is a CVD participant's ("As a Finder…", "As a Vendor…", "As a Participant…"). Project and process requirements (1,888 of 3,324) have nothing to cite, so for now their reason is their `rationale:` (maintainer decision, 2026-10-12). The option to revisit: write a small set of contributor, maintainer, demo-operator and AI-agent stories and extend story traceability to project and process requirements.
2. **Support levels are stale.** Each story's "Support Level" is marked *as of v0.4.0*. Eleven stories marked Out-of-scope are cited by requirements anyway. Story 006 ("decide if I will/can engage") is cited by 36 requirements and covered by RM accept/decline. Story 054 ("vote/accept new Participants to a case") is cited by 26. Many "Unsupported" stories are cited by 10–36 requirements. A reader of the story pages gets the wrong picture.
3. **Catch-all stories.** Three stories carry most of the links: story 088 ("maintain knowledge of the state of case and what options are available", 156 requirements), story 045 ("produce a shared verified public record of case activity", 133) and story 014 ("negotiate embargo/disclosure schedules…", 127). A link to one of them barely answers "why does this requirement exist?". Splitting them into narrower stories would make the links mean something.
4. **Bounty stories with no requirements.** Stories 055, 056, 057, 084 and 085 are the only stories no requirement cites; all are about bounties. 084 and 085 are Out-of-scope; 055–057 are "Allowed". The scope decision itself belongs to #2563 (bug bounty protocol support); this concern only needs the story pages to agree with that decision once it's made.

These overlap the five protocol story-drafting Ideas under this Epic (#2596–#2600). Plan them together so new protocol stories, contributor stories and the catch-all splits don't collide.

## Questions for planning

- Which stakeholder roles get stories (contributor, maintainer, demo operator, AI agent, deployer)?
- Should support levels be recomputed from current requirement coverage, or retired as a field?
- When splitting a catch-all story, is the old ID retired (no reuse), with each citing requirement re-pointed by hand?
- Does extending traceability to project and process requirements replace the rationale-only rule, or add to it?

**Resolved**: 2026-10-12 — implementation tracked in #4506, #4507, #4514, #4516, #4517 (and the drafting Tasks #4508, #4510, #4512, #4513).
Docs PR: <https://github.com/CERTCC/Vultron/pull/4505>.
Notes: `notes/user-story-catalog.md`.

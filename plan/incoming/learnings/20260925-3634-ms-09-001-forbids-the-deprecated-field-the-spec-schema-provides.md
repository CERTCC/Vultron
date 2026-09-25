---
title: "MS-09-001 says superseded requirements MUST be removed, yet the spec schema carries `deprecated`/`superseded_by` and four spec files use them"
type: learning
timestamp: "2026-09-25T18:30:00Z"
source: ISSUE-3634
signal: spec-contradiction
---

MS-04-005 and MS-09-001 both say a superseded requirement MUST be removed
entirely, "rather than marked deprecated or left in place with an annotation".
But `vultron/metadata/specs/schema.py` defines `deprecated: bool` and a
`superseded_by` field, and `specs/architecture.yaml`, `multi-actor-demo.yaml`,
`semantic-extraction.yaml` and `tech-stack.yaml` all carry `deprecated: true`
entries. spec-lint accepts them without warning.

While retiring linkchecker (#3634), DOCBW-03-003 and the DOCBW-04 group were
first marked deprecated, following that precedent. Only the standards review
caught the MS-09-001 breach, and they were removed before merge.

Open question: which side is authoritative? Either
(a) MS-09 is right: spec-lint should flag `deprecated: true` and the four
files' entries should be removed; or
(b) the schema field is intended: MS-04-005/MS-09-001 should be amended to
permit a deprecated entry with `superseded_by`, for example as a transitional
state.
Until one is chosen, agents will keep following whichever one they read first.

---
source: NOTES-user-story-catalog--decisions-plan-rows
timestamp: '2026-11-04T02:52:36.865620+00:00'
title: 'User story catalog: plan-only decision rows'
type: note
---

**Archived:** 2026-11-04
**Reason:** delivered — these rows decided one-time work (retire the support level, build the matrix, work the gap by area, split 088/045/014) that has landed; the bounty row is an open scope question that #2563 owns, not a lasting rule
**Superseded by:** notes/user-story-catalog.md (now `kind: guidance`), docs/reference/user_stories/ (generated table and traceability matrix)

---

## Decisions (rows archived)

| Question | Decision | Why |
|---|---|---|
| Support level (`as of v0.4.0`) | Retired from every page and from the index legend. The index table and the traceability matrix are generated from the specs' `stories:` fields and show coverage instead | A dated judgment cannot stay true; most of the stories it marks Out-of-scope are cited by requirements today. Coverage is a fact the registry already holds |
| Traceability matrix | Generated and gated by a check mode, like the other committed site artifacts (TRACE-01-001, TRACE-03-003; built in #4506) | Hand editing is how it reached 161 of 801 |
| How the protocol gap is worked | By spec-file area, one Task per area, worklist read from a per-file gap report; reuse an existing story first, add one only when none fits | One agent stays in one area of knowledge, worklists do not overlap, and the same cut the rationale backfill uses (#4483–#4486) means the same context serves both |
| Catch-all stories 088, 045, 014 | Split into narrower stories after the area drafting lands; old IDs stay as superseded pages; every citation is re-pointed by hand | A link that reaches 156 requirements barely answers "why does this one exist?" |
| Bounty stories 055–057, 084, 085 | No change here. Their disposition follows the scope decision in #2563; generated coverage shows them as uncited until then | The scope decision is #2563's to make |

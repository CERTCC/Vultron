---
source: CONCERN-3526
timestamp: '2026-09-24T15:12:05.886113+00:00'
title: Reader-facing docs audited against ADR-0102
type: learning
---

## Summary

`notes/site-information-architecture.md` states how reader-facing documentation should be organized, but nothing is known about how far the existing tree departs from it. One page was read closely during planning and it failed badly — `interoperability.md` argues its case through five block quotations from 2004/2005 research reports and never mentions a coordination portal. Whether that is one page or forty is unmeasured, and no remediation can be scoped until it is.

Audit the reader-facing pages along five dimensions in one pass.

## Surface Symptom vs. Underlying Problem

**Surface symptom.** A few pages read oddly and some sit in the wrong place.

**Underlying problem.** Until this audit exists there is no list, so every remediation task is scoped by guess. The reorganization would then ship as ordering changes while the pages themselves still address the wrong reader — which is the failure that made #3512 look like a navigation problem in the first place.

## Category

- [x] Technical debt

## Severity

medium

## The lenses

Applied in a single pass per page, not several passes:

| Lens | Question |
|---|---|
| Level | What must the reader already know? Assign 100–500. |
| Stakeholder type | Who is this page addressed to — `cvd-practitioner`, `platform-developer`, `process-researcher`, `project-contributor`, or `ALL`? Addressed-to, not about: `roles_influence.md` is *about* vendors and governments and *addressed to* a process researcher. |
| Constituent narrowing | For a page tagged `cvd-practitioner`: does its text narrow to security researchers, vendor PSIRTs, or national CSIRTs/ISACs/ISAOs? Record which. This is the evidence that would justify splitting the type, and it is only observable while someone is reading the page. |
| Register | Who is this page *addressed to*? Does its voice and evidence match its intended reader? |
| Nav enumeration | Does this page belong in the nav, or behind a routing page? |
| Gap | What does this stakeholder type's path need at this point that does not exist? |
| Continuity | Does this page hand off to its neighbours — a transition into what comes next, a back-reference to what it assumed? Record what is missing. **Do not** record repeated openings or re-expanded acronyms as defects: they are required for deep-link arrivals and DF-11-007 forbids removing them. |

## Audit routes; it does not prescribe

Per page, record only what is needed to **route** it: level, stakeholder type, any constituent narrowing, a verdict, a one-line evidence note, and which remediation task owns it. Do **not** write the fix. The remediation task reads its pages properly and fixes them in one session with context loaded — re-deriving the fix at the moment of the edit beats specifying it twice, and a prescription handed between sessions is the lossy handoff the completeness doctrine warns about.

**The exception**: judgments that cannot be made from inside a single page, which a page-local fixer will get wrong. The audit must settle these itself:

- Which of several overlapping pages wins, and what each carries over. Known instance: `reference/terms.md` (87 lines), `reference/glossary.md` (710), `reference/vultron-taxonomy.md` (450) are three concept registries with no stated division of labor.
- Inbound link counts per page. These decide whether a move is cheap — 78 inbound occurrences is what made retiring `behavior_logic/` too expensive in #3281.
- Level violations, which are a property of a *pair* of pages.
- Missing pages, which by definition appear in no file list.

## Scope

- Reader-facing pages only. Project working-record pages declare `project-contributor` and no level per DF-11-003, and are out of scope here.
- **Excludes the pages owned by #3524** (home page, `interoperability.md`, `what-is-vultron.md`, `capability_model/index.md`) — that issue owns them exclusively.
- No edits beyond recording `stakeholder_type` and `level` in frontmatter. Remediation is separate.
- The Continuity lens carries the surviving half of #3512's suggested action step 4. Its third clause — "remove the duplicated openings" — was **rejected** by ADR-0102 and is now forbidden by DF-11-007; see "This overturns one of #3512's own asks" in `notes/site-information-architecture.md`.

## Remediation partitions by page, not by dimension

When this Concern is planned, cut remediation tasks **by page or section**, each owning its files exclusively. Partitioning both analysis and remediation by dimension is the mistake: five dimension-shaped fix tasks leave one page claimed by three of them, one saying rewrite it, one saying move it, one saying merge it away.

`mkdocs.yml` is the one file every structural change touches. One task owns all nav edits at a time; never in parallel.

## Known findings to fold in

Measured during planning, so the audit starts from these rather than rediscovering them:

- All four section landing pages are hand-maintained duplicates of the nav and all four have drifted. `topics/index.md` omits four nav children; `reference/index.md` omits the Protocol Specification, Glossary, Concept Taxonomy, and Quick Reference, and describes the six-kind spec taxonomy retired by ADR-0038; `tutorials/index.md` omits Worked Example; `howto/index.md` omits Demo How-Tos. Fixing these is #3527's job, not this audit's — but they are evidence the landing pages are not maintained routing surfaces.
- `howto/case_object.md` is a 10-line redirect stub occupying the first slot in How-to Guides.
- Reachability is *not* a problem: of 211 unnavved pages all but 3 are deliberate.
- `docs/topics/background/index.md` is 211 lines titled "Vultron Contextualized" — a content essay wearing an index's filename, named in #3512's own evidence. Generation (#3527) cannot resolve it, because it preserves hand-written prose and would preserve all of it. **This audit owns the decision**: what the extracted page is called and what stays on the index, which depends on how the neighbouring `background/` pages divide the same material — the several-overlapping-pages judgment this audit must settle rather than hand to a page-local fixer. An `index.md` orients and routes; anything that is neither belongs on a named page.

## Impact if Ignored

Remediation gets scoped by guess; the reorganization ships as ordering changes and the first-contact failure is unchanged.

## Suggested Action

Run the pass, record `stakeholder_type` and `level` in frontmatter, produce the routing ledger plus the four cross-page findings and the constituent-narrowing tally, then run `plan-issue` on this Concern to cut remediation tasks by page.

## Prior Art

- `notes/site-information-architecture.md` (ADR-0102) — the standard being audited against, including the stakeholder-type and level tables, and the conditions that would split `cvd-practitioner`.
- `notes/documentation-sweeps.md` — DF-10-001: moving a claim is not verifying it. Applies to every merge this audit recommends.
- `lint-docs` already audits per-page style; this audit covers what it cannot see, which is everything above the page.
- `docs/reference/user_stories/traceability.md` — the working routing-page pattern the nav-enumeration lens measures against.

## Reference

Source: #3512
Docs PR: <https://github.com/CERTCC/Vultron/pull/3523>
Spec: `specs/diataxis-requirements.yaml` DF-11
Notes: `notes/site-information-architecture.md`

**Resolved**: 2026-09-24. Implementation is tracked in #3619, #3620, #3621, #3622, #3623, #3624, #3625, #3626, #3627 and #3628.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3618>.

Spec: `specs/diataxis-requirements.yaml`. DF-11-003 is amended to name requirements-traceability records as working record.

Notes: `notes/reader-facing-docs-audit.md`.

Outcome:

- **Audit.** The audit ran in the planning PR. 148 pages were read. Verdicts: 67 ok, 50 revise, 10 relocate, 9 extract, 6 split and 6 merge.
- **Reclassified.** Ten pages turned out to be working record and were reclassified.
- **Frontmatter.** The other 138 were tagged with `stakeholder_type` and `level`.
- **Level shape is inverted.** Only 3 pages sit at 100, and 107 sit at 300 or 400.
- **`cvd-practitioner` stays whole.** No page narrows it to one constituent.
- **Level violations.** There are 24 upward level dependencies. They cluster on `case_ledger_sync.md` and `case_model.md`, because no 300-level introduction to the case model exists.

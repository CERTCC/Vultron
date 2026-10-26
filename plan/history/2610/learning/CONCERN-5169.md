---
source: CONCERN-5169
timestamp: '2026-10-26T15:26:32.637504+00:00'
title: Reader-thread box lands at page end even when the thread links to one section
type: learning
---

## Summary

A thread member can name a section (`page.md#anchor`), but the thread box always renders at the end of the page.
A reader who follows a thread to one glossary section must scroll past unrelated content to find directions onward.

## Surface Symptom vs. Underlying Problem

- **Surface:** the box sits in the wrong place on long pages such as the glossary.
- **Underlying:** the thread model treats a section member as a whole page.
  The link keeps the fragment (`_link` in `threads.py`), but membership, box placement and the box wording ("This page is part of…") all use only the page path.
  DF-11-015 specifies what the box shows but not where it goes, so nothing requires it to be near the section the thread is about.
- **Already correct — leave alone:** the box content (before and after sets, link back to the start page), "the same for every reader" with no script or query string, and footer hiding (DF-11-017).

## Category

- [ ] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [x] Other — documentation site UX

## Severity

medium — every anchored member is affected, and the effect grows with page length; there is no protocol impact.

## Evidence

- `vultron/metadata/docs/thread_box.py` — `on_page_markdown` appends every box after the whole markdown.
- `vultron/metadata/docs/threads.py` — `_link` keeps the fragment; `member_boxes` / `render_box` match on page path only.
- `docs/start/coordinate-cases.md:19` — `page: reference/glossary.md#cvd-roles-and-participants`.

## Impact if Ignored

Threads that point to a section are in effect broken on long pages.
Thread authors learn to avoid anchored members even where a section is the correct stop.

## Suggested Action

**Recommended:** when a member has a fragment, render its box at the end of that section (just before the next heading of the same or higher level).
Members without a fragment keep the page-end box.
Word the box for a section ("This section is part of…").
Add a placement clause to DF-11-015 and a fixture test.

- **Implementation risk:** `on_page_markdown` sees only raw markdown, so locating the heading needs the same slug / `{#id}` resolution as the toc extension.
  Inserting in `on_page_content` (HTML) instead would bypass MkDocs's link rewriting and validation for the box.
  The plan must choose between them.
- **Alternatives considered:**
  - All boxes at the top of the page — a reader who lands on an anchor is already past the top.
  - A short pointer at the anchor that links to the page-end box — adds a second element and still makes the reader jump.

**Resolved**: 2026-10-26 — implementation tracked in #5170.
Placement is manual: the page author places a marker where the box goes; the build fills it and the thread check enforces it.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5171>.
Spec: `specs/diataxis-requirements.yaml` (DF-11-022).
Notes: `notes/site-information-architecture.md`.

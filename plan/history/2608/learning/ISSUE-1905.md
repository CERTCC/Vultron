---
title: "SE-07-006 render test discovered 3 more trailing-dash phrases"
type: learning
timestamp: "2026-08-25T00:00:00Z"
source: ISSUE-1905
signal: concern
---

While implementing the parametrised SE-07-006 behavioural render test (#1905),
`test_event_phrase_render_no_dangling_output` found three additional phrases that
produce trailing em-dashes when called through `event_phrase()`:

| Semantic type | Phrase | event_phrase() output |
|---|---|---|
| OFFER_CASE_PARTICIPANT | `'{actor} offered case participation to {object}'` | `'— offered case participation to —'` |
| OFFER_CASE_OWNERSHIP_TRANSFER | `'{actor} offered case ownership to {object}'` | `'— offered case ownership to —'` |
| ADD_PARTICIPANT_STATUS_TO_PARTICIPANT | `'{actor} updated the participant status for {object}'` | `'— updated the participant status for —'` |

Root cause: `event_phrase()` uses `defaultdict(lambda: "—")`, so any phrase
ending with a slot reference always ends with `"—"`.

These are the same class of bug as #2150 (SUBMIT_REPORT / `{target}`).

Tracked in GitHub issue #2615. All three marked `xfail(strict=True)` in
`test/test_semantic_registry.py` pending a fix.

**Promoted**: 2026-08-27 — archived (already in specs/notes/AGENTS.md or tracked as GitHub issue). Docs PR: <pending>.

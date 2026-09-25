---
source: CONCERN-3241
timestamp: '2026-09-25T15:30:46.685273+00:00'
title: inbox_handler.md cites eight retired module paths as the current API
type: learning
---

## Concern

`docs/reference/inbox_handler.md` (Implementation Checklist, Phases 1–2) cites
module paths that no longer exist. Every path below is checked off as done, so a
reader treats them as the current API surface:

| Cited path | Status |
|---|---|
| `vultron.api.v2.routers.actors.post_actor_inbox` | gone — API v2 retired (ADR-0011) |
| `vultron.api.v2.routers.actors.parse_activity` | gone — now `vultron/adapters/driving/fastapi/routers/actors/_inbox.py` |
| `vultron.activity_patterns.ActivityPattern` | gone — now `vultron/wire/as2/extractor/` |
| `vultron.enums.MessageSemantics` | gone — now `vultron/core/models/events/base.py` |
| `vultron.semantic_map.SEMANTICS_ACTIVITY_PATTERNS` | gone — now `vultron/semantic_registry/` |
| `vultron.behavior_dispatcher.{DispatchEvent,prepare_dispatch_activity,ActivityDispatcher,DirectActivityDispatcher}` | gone — now `vultron/core/dispatcher.py` |

Verified by import:

```text
vultron.api.v2.routers.actors  -> ModuleNotFoundError
vultron.behavior_dispatcher    -> ModuleNotFoundError
```

## Why it matters

This is the primary reference page for the inbox pipeline, and it is the page an
agent or contributor lands on when orienting to message handling. Every path is
wrong, and nothing in the page signals that. `mkdocs build --strict` does not
catch it because these are inline code spans, not links.

## Suggested fix

Repoint each path to its current module. Consider whether the "Implementation
Checklist" section still earns its place at all — an all-checked checklist of
retired module names is a maintenance liability that will drift again.

## Discovery

Surfaced while running `check-docs-sync` for PR #3233 (ISSUE-3217). Out of scope
there: that PR changed the wire parse threshold, not the inbox pipeline's
documented structure, and repointing eight paths plus reassessing a section is a
docs task in its own right. Routed per the upward-reflection checklist (BW-07-009).

**Resolved**: 2026-09-25 — fixed in two docs PRs; no implementation issue created.
The page had already been bannered "Historical design document" on 2026-09-02
(893e5bfa6) and sat outside the published nav as working record (DF-11-003), so the
issue's premises ("nothing in the page signals that", "the primary reference page
for the inbox pipeline") did not hold at filing.

The planning PR (#3703) deleted the all-checked "Development Goals" checklist,
linked the banner to the current pipeline section, and repointed four
`receive_report_demo.py` docstrings that cited the page as "the Vultron prototype
design" to `docs/topics/reference_architecture.md` § "From HTTP delivery to
behavior tree: the inbox pipeline".

The follow-up PR (#3707) then asked whether the page earned its place at all. It did
not: its design reasoning is the decision recorded in ADR-0007 (which predates the
page by a week), the current pipeline is described in the reference-architecture
section above, and everything else on it (a 200-OK acknowledgement, a mapping
`dict`, `DispatchEvent`, handler functions) was superseded implementation detail
that git history already keeps. Rewriting it with current detail would only have
duplicated that section and re-created the drift, so the page was deleted. So was
`docs/reference/code/api/actor_inbox_handler.md`, which was in the published nav and
described the layered activity-type → object-type → handler-registry routing that
ADR-0007 rejected. No redirects were added: the production site's `publish` branch
predates both pages, so no production link can break. Both pages are on the staging
repository's `publish` branch, which is a preview rather than a stable link target.

Docs PRs: <https://github.com/CERTCC/Vultron/pull/3703>,
<https://github.com/CERTCC/Vultron/pull/3707>.

---
title: defaultdict-based phrase tests cannot catch unfillable slot bugs
type: learning
timestamp: "2026-07-29T00:00:00Z"
source: ISSUE-1787-phrase-defaultdict
signal: concern
---

The two SE-07 phrase tests in `test/test_semantic_registry.py`
(`test_every_entry_has_non_empty_phrase`,
`test_phrase_format_map_with_defaults_returns_non_empty`) render each phrase via
`phrase.format_map(defaultdict(lambda: "X"))`. Because a `defaultdict` supplies
a value for **every** slot name, these tests structurally cannot detect the
bug class from issue 1787: a phrase that references a slot the real render
pipeline (`vultron/demo/report.py` `event_phrase()` /
`CaseTimelineEvent.summary`) never populates. The buggy
`"{actor} proposed a case to {target}"` passed both tests while rendering
`"Vendor proposed a case to —"` in production.

The runtime render pipeline only ever fills `actor` (always) and
`object`/`target` (only when a `target_label` resolves). Slots `context`,
`origin`, and `inner_object` are never filled with real data. A naive
"no phrase renders a trailing em-dash" guard is **not** viable: SUBMIT_REPORT,
the three OFFER_* entries, and ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
legitimately end in `{object}`/`{target}` that the renderer fills from
`target_label`. So the correct regression test is per-event and asserts the
specific slot is absent, not a blanket structural rule.

**How to apply:** When adding or auditing a registry `phrase`, confirm every
slot it references is one the render pipeline actually populates for that event
type. Do not rely on the defaultdict SE-07 tests as a slot-correctness guard —
they only prove non-emptiness. For a phrase whose event carries no target
(e.g. `Create(as_CaseProposal)`, where the factory sets no `target`), assert
`"{target}" not in entry.phrase` and add a symptom-level `summary` render test.

**Promoted**: 2026-07-31 — captured in `notes/codebase-structure-fastapi-patterns.md` (phrase defaultdict section). GitHub concern: #1898.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1900>0>0>0>0>.

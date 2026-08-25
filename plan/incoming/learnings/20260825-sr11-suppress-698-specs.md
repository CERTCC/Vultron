---
title: SR-11 backfill — 223 protocol MUST specs still need story mapping
type: learning
timestamp: 2026-08-25T19:00:00Z
source: ISSUE-2585
signal: concern
---

Original state: 698 protocol MUST specs were given `lint_suppress: [missing_story_reference]`
as a pass-through to satisfy the SR-11-003 hard-error gate while traceability was pending.

**Completed 2026-08-25**: mapped 475 of those 698 specs to existing user stories
(story_2022_001 through story_2022_111). The `lint_suppress` entries were replaced with
`stories:` fields on all 475 mapped specs.

**Remaining**: 223 specs retain `lint_suppress: [missing_story_reference]` because no
existing story plausibly covers them. These are implementation-detail specs whose
user-visible behavior is not yet described by any of the 111 current stories.

Primary categories with no-match specs:

- `specs/semantic-extraction.yaml`: all 21 — NLP/tooling internals
- `specs/history-management.yaml`: all 11 — internal ledger implementation detail
- `specs/case-proposal.yaml` CP-0x series: negotiation protocol internals
- `specs/vocabulary-model.yaml` VM series: data model internals
- `specs/participant-case-replica.yaml` PCR-07 series: replica sync internals
- `specs/triggerable-behaviors.yaml` TRIG series: BT trigger internals
- Various response-format and structured-logging specs

**Follow-on work needed**: author new user stories for the 223 remaining specs, or
determine that they are genuinely internal implementation details that need no
story traceability. See the gap list in the issue filed against SR-11.

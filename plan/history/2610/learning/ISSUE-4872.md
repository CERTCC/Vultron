---
title: "MV-11-004 forbids the per-class retired-key guard that RetiredFieldsRecord is and CLP-02-014 requires"
type: learning
timestamp: "2026-10-19T19:30:00Z"
source: ISSUE-4872
signal: spec-contradiction
---

**Trigger.** You are retiring a field on a core type (a rename or a move), or
reading MV-11-004 / SDO-03-005 to decide where a retired key is refused.

**Claim.** MV-11-004 says "core types MUST NOT carry a per-class retired-key
reject-guard (SDO-03-005)". But `RetiredFieldsRecord`
(`vultron/core/models/retired_stored_fields.py`, #4128) is exactly that: a
core-side `model_validator(mode="before")` that refuses a named old key. Five
core records use it, and CLP-02-014 (via #4872 AC-3) applies it to
`CaseLedgerEntry`. The two rules answer different questions. MV-11-004's
rationale is about *received* keys, whose only door is the parse edge.
`RetiredFieldsRecord` answers a *stored-row* question: `extra="forbid"` refuses
the row, but only as a bare "extra inputs" error that never names the rename.
Read literally, though, MV-11-004 forbids the stored-side guard too. The scope
needs settling: either MV-11-004 forbids only guards for wire keys and allows a
shared retirement table for stored rows, or stored renames lose their named
refusal.

**Evidence.** In #4872 the received `eventType` refusal had to go in the wire
list `RETIRED_NAMES`, because the parse edge decides a key before core sees it.
The stored-row refusal stayed in `RetiredFieldsRecord` because AC-3 names it.
`test_no_core_module_names_a_retired_key` enforces the wire-list half by
string matching, so it only works because the snake-case `event_type` key
(core-side) is kept off `RETIRED_NAMES`. The pre-push review on PR #4909 flagged
the conflict.

**Promoted**: 2026-10-30 — MV-11-004 narrowed to received keys; the retired-list
placement moved to MV-11-006, which allows the shared `RetiredFieldsRecord` for stored
rows (`specs/message-validation.yaml`, `notes/wire-core-boundary.md`). Maintainer
decided to drop retired-name tracking on both sides before 1.0: #5573.
Docs PR: <https://github.com/CERTCC/Vultron/pull/5581>.

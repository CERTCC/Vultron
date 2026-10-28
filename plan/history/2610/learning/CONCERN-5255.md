---
source: CONCERN-5255
timestamp: '2026-10-28T14:38:05.440557+00:00'
title: Shorthand mapping, object-ID and response-format requirements were stale or
  mixed protocol and codebase rules
type: learning
---

## Problem

Writing rationales for the core protocol text (#4483) found three requirement statements that are stale or that mix a protocol rule with a codebase-only rule. #4483 forbids changing statements (its AC-4), so they are recorded here.

- **MSM-02-002, MSM-02-004, MSM-02-005 and MSM-02-006 vs MSM-07-003, MSM-07-004, MSM-07-008 and MSM-07-009.** MSM-02 maps the shorthands EA, EC, ER and EJ to the Invite answers (`ACCEPT_INVITE_TO_EMBARGO_ON_CASE`, `REJECT_INVITE_TO_EMBARGO_ON_CASE`), and `vultron/semantic_registry/embargo.py` tags the occasions the same way. But MSM-07-003 and MSM-07-004 say an Invite answer moves no register entry. MSM-07-008 and MSM-07-009 give the EM transitions to the Case Owner's separate decision, `Accept`/`Reject(EmbargoEvent, target=Case)`, which carries no shorthand in the registry. The file description ("EV/EJ/EC onto EP/ER/EA") and the MSM-02 group description repeat the MSM-02 view. So a shorthand whose effect is an EM transition maps to a message that never makes that transition. The learning `plan/incoming/learnings/20261009-4364-em-shorthands-still-map-the-owners-decision-to-the-invite-answer.md` records the same finding, and the EJ row of `docs/topics/behavior_logic/use-cases/embargo-lifecycle.md` repeats the MSM-02 wire form.
- **OID-01-004.** Its example path `vultron.as_vocab.utils.make_id` does not exist. The repository has two ID helpers, `make_id` in `vultron/adapters/utils.py` and `generate_new_id` in `vultron/wire/as2/vocab/base/utils.py`. So the example is stale, and two helpers arguably miss the statement's "shared utility module" intent.
- **RF-03-004 and RF-04-004.** Each is `kind: project`, but each mixes a rule a participant can see (the Offer is the object) with this codebase's shortcut (the Offer is carried inline). The matching Accept rule is split into RF-02-004 (protocol) and RF-02-006 (project), per MS-12-010. These two are not split, and their protocol halves duplicate RF-03-003 and RF-04-003.

## Decision needed

- MSM: should a shorthand's EM effect map to the Case Owner's `Accept`/`Reject(EmbargoEvent, target=Case)`, with the Invite answer as each participant's consent? Or do the shorthands stay Invite answers, with a statement that the EM-moving decision is a separate activity? The docs table follows either answer.
- OID-01-004: name the real helper, and decide whether the two helpers become one.
- RF-03-004 and RF-04-004: split them per MS-12-010, or retire the duplicated protocol halves.

Where: specs/message-semantics-mapping.yaml, specs/object-ids.yaml, specs/response-format.yaml

Governing specs: MSM-02, MSM-07, OID-01, RF-03, RF-04, MS-12-010

**Resolved**: 2026-10-28 — implementation tracked in #5309, #5310, #5311.

Docs PR: <https://github.com/CERTCC/Vultron/pull/5308>.

Spec: `specs/message-semantics-mapping.yaml`, `specs/object-ids.yaml`, `specs/response-format.yaml`.

Decisions: EA/EC/ER/EJ name the Case Owner's decision (ER also the
CASE_MANAGER's abandonment); the formal model covers the case's view of the
embargo and does not model PEC (new MSM-02-010); one ID minter shared by core
and wire; RF-0x-003 hold the protocol rule and RF-03-004/RF-04-004 the
codebase's inline rule; RF-02-003 retired as a duplicate of RF-02-004.

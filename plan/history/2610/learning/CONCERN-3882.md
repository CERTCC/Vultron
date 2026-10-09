---
source: CONCERN-3882
timestamp: '2026-10-06T16:16:32.425585+00:00'
title: Scenario causal-edge consequent_actor is unenforced and its semantics are unspecified
type: learning
---

## Concern

Every scenario narrative under `docs/topics/scenarios/` declares `causal_edges:` with a `consequent_actor` label (DEMOMA-22-004: "the actor that commits the consequent"). Two things about that label surfaced while fixing #2753 and #2754 in PR #3881:

1. **Nothing checks it.** `check_causal_edges` in `test/ci/invariants/common.py` reads `consequent_actor` only to decorate failure messages. `notes/demo-ci-invariants.md` documents it as a "documentary label". So #2753's mislabel (the Vendor's rejection attributed to the Coordinator) sat in the committed oracle undetected, and the issue's impact statement — that a conformance test would check the wrong actor — assumed an enforcement that does not exist. PR #3881 adds a narrow structural check (an invitation response is never attributed to its inviter) but that covers one edge shape only.

2. **Its meaning is ambiguous for delegated emissions.** The CASE_MANAGER commits every entry, so "the actor that commits the consequent" cannot literally be the label. The narratives use the payload actor by convention, but they disagree on delegated invites: `fvcv-handoff.md` labels the Coordinator's invite of Vendor2 `coordinator`, while `fccv-extension.md` and `fvcv-extension.md` label the equivalent CaseActor-emitted invite `case-actor`. The demo asserts that the Vendor2 invite "was emitted as the CaseActor (PCR-08-008)", so `payloadSnapshot.actor` is the CaseActor and `attributedTo` is the Coordinator. Neither DEMOMA-22-004 nor the schema block in `notes/demo-ci-invariants.md` says which the label names.

## Status after PR #3881

Point 2 (semantics) is settled in PR #3881 by the rule the wire format already had (CM-24-001/002, PCR-08-007): `consequent_actor` names the `actor` recorded on the consequent's ledger entry, the literal emitter. For a Case-Actor-emitted activity that is `case-actor`, and the requesting participant is recoverable from the entry's `attributedTo`, not from the label. DEMOMA-22-004 now says so, and the ten `invite_actor_to_case` edges across the nine narratives all carry `case-actor` (pinned by `test_every_invite_edge_is_emitted_by_the_case_actor`).

What remains here is point 1 only: make the label load-bearing. `check_causal_edges` should restrict consequent candidates to entries whose recorded `actor` resolves to the label (replica directory names already come from `strip_id_prefix(actor_id)`, so the URI-to-label mapping in `vultron/demo/helpers/ledger_dump.py` can be reused). That needs a DEMOMA-22-005 amendment and one live demo run per scenario to confirm every label before the check is armed.

## Options

- Decide the semantics (payload `actor` vs. `attributedTo`) and amend DEMOMA-22-004 plus the schema note; re-label the delegated-invite edges accordingly.
- Then make the label load-bearing: `check_causal_edges` restricts consequent candidates to entries whose recorded actor resolves to the label (replica directory names already come from `strip_id_prefix(actor_id)`, so a URI-to-label mapping exists in `vultron/demo/helpers/ledger_dump.py`). Needs a DEMOMA-22-005 amendment and one live demo run per scenario to confirm every label before the check is armed, or CI goes red on labels rather than on ledgers.

Deferred from PR #3881 because it is a spec and harness design change, not a docs fix, and cannot be verified without demo artifacts.

## Source

Discovered during bugfix of #2753 / #2754 (PR <https://github.com/CERTCC/Vultron/pull/3881>). Related learning: `plan/incoming/learnings/20260929-2753-consequent-actor-names-no-defined-actor-for-delegated-entries.md`.

Governing specs: DEMOMA-22-004, DEMOMA-22-005

**Resolved**: 2026-10-06 — implementation tracked in #4248 (one PR, two commits: report-only check, then enforcing check after every scenario's tags are verified).

Docs PR: <https://github.com/CERTCC/Vultron/pull/4249>.

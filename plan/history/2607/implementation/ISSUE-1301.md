---
source: ISSUE-1301
timestamp: '2026-07-13T17:28:14.559500+00:00'
title: update suggest_actor docs for ADR-0026 CaseActor routing
type: implementation
---

## Issue #1301 — docs: update suggest_actor.md sequence diagram and vocab examples for ADR-0026

Updated `docs/howto/activitypub/activities/suggest_actor.md` to reflect the CaseActor-routed suggest-actor protocol per ADR-0026. Added three new vocab example functions (`offer_case_participant`, `accept_case_participant_offer`, `reject_case_participant_offer`) covering the intermediate protocol steps. Fixed a Mermaid diagram bug where the Invitee activation bar rendered unconditionally in the Reject path. PR: <https://github.com/CERTCC/Vultron/pull/1369>

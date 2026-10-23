---
source: ISSUE-1717
timestamp: '2026-07-27T18:56:03.254384+00:00'
title: 'Fix demo VFD timing race: receiver-container waits and wrong-actor bug fixes'
type: implementation
---

## Issue #1717 — Fix: demo VFD broadcast timing race

Fixed the intermittent CI failures across all 6 demo scenarios caused by a timing race where single-shot VFD assertions fired before the receiver container had received the VFD broadcast.

**Changes:**

- Added `wait_for_participant_vfd_state` on receiver container before every `verify_fix_ready`, `verify_fix_deployed`, and `verify_publicly_disclosed` call in all 6 demo scripts
- Fixed wrong-actor bug in `fccv_handoff_demo.py` (AC-2): `receiver_actor_id=c1.id_` → `receiver_actor_id=vendor.id_`
- Fixed same wrong-actor bug in `fcv_demo.py`: `receiver_actor_id=coordinator.id_` → `receiver_actor_id=vendor_in_vendor.id_`
- Patched `wait_for_participant_vfd_state` in `TestPhasePublicationEmWaitOrdering` to prevent ValidationError

PR: <https://github.com/CERTCC/Vultron/pull/1725>

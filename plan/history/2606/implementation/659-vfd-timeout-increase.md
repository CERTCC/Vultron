---
source: 659-vfd-timeout-increase
timestamp: '2026-06-01T19:11:41.913314+00:00'
title: 'fix: increase wait_for_participant_vfd_state timeout to 30 s (#659)'
type: implementation
---

fix: increase wait_for_participant_vfd_state timeout to 30 s to accommodate cross-container async delivery pipeline latency under CI load. Also add DEBUG diagnostic log before AssertionError.

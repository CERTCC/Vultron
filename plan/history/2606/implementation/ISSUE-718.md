---
source: ISSUE-718
timestamp: '2026-06-08T14:28:41.355221+00:00'
title: Shared-inbox adapter explicit fail-fast stub
type: implementation
---

## Issue #718 — Implement ActivityPub shared-inbox fan-out (adapters/driving/shared_inbox.py)

Implemented the immediate fail-fast stub requirement by adding `SharedInboxAdapter` in `vultron/adapters/driving/shared_inbox.py` with a constructor that raises `NotImplementedError` and references OX-11 requirements.

Added unit coverage in `test/adapters/driving/test_shared_inbox.py` to assert instantiation raises with the expected message contract.

PR: [#823](https://github.com/CERTCC/Vultron/pull/823)

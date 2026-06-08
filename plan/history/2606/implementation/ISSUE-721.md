---
source: ISSUE-721
timestamp: '2026-06-08T14:46:45.521557+00:00'
title: Rename HTTP delivery adapters for demo/prod roles
type: implementation
---

## Issue #721 — Rename delivery_queue.py → demo_http_delivery.py and http_delivery.py → prod_http_delivery.py with class renames

Completed adapter/module renaming to make transport roles explicit:

- renamed `vultron/adapters/driven/delivery_queue.py` to `demo_http_delivery.py` and `DeliveryQueueAdapter` to `DemoHttpDeliveryAdapter`
- renamed `vultron/adapters/driven/http_delivery.py` to `prod_http_delivery.py` and added `ProdHttpDeliveryAdapter` as a fail-fast `NotImplementedError` stub
- updated all import sites, tests, specs, and active docs/notes references

PR: <https://github.com/CERTCC/Vultron/pull/828>

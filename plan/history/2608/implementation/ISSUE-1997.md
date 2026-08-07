---
source: ISSUE-1997
timestamp: '2026-08-06T14:33:39.443199+00:00'
title: 'Demo CI: tighten path filter + push-to-main trigger'
type: implementation
---

## Issue #1997 — Demo CI: audit and tighten path filter (DEMOCI-02-003)

Tightened the `demo-integration.yml` path filter to exclude `vultron/metadata/**`
and `vultron/bt/**` (neither affects demo container runtime behavior). Added the
missing `push`-to-main trigger and concurrency group per DEMOCI-05. Removed the
now-redundant `demo-image-cache-warm.yml` workflow (DEMOCI-05-003).

PR: <https://github.com/CERTCC/Vultron/pull/2029>

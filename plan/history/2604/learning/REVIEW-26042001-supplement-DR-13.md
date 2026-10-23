---
title: DR-13 Update cc addressing not supported
type: learning
timestamp: '2026-04-20T00:00:00+00:00'

source: REVIEW-26042001-supplement-DR-13
---

cc addressing has no defined handler semantics. When receiving actor is in cc
of Offer(Report): log WARNING, discard without creating a case.

**Promoted**: 2026-04-28 — captured in `notes/activitystreams-semantics.md`;
requirement in `specs/handler-protocol.yaml` HP-10-001.

---
source: ISSUE-1401
timestamp: '2026-07-15T19:08:47.753503+00:00'
title: Forward Offer content to duplicate-recommendation Note (CM-16-008)
type: implementation
---

## Issue #1401 — Forward Offer.content to duplicate-recommendation Note

Implemented CM-16-008: wire extractor now populates VultronActivity.content;
use case validates and passes offer_content to tree factory;
EmitNoteDuplicateRecommendationToOwnerNode appends it to the Note body.
6 new unit tests added.

PR: <https://github.com/CERTCC/Vultron/pull/1471>

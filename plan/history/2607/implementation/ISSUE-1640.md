---
source: ISSUE-1640
timestamp: '2026-07-24T18:58:22.826150+00:00'
title: 'Fix ResolveCaseActorUrlsNode: read case_actor_service_url from ActorConfig'
type: implementation
---

## Issue #1640 — Fix ResolveCaseActorUrlsNode: read case_actor_service_url from ActorConfig

Fixed co-location assumption bug where CaseActor service URLs were derived from `server_base_url` instead of dedicated `case_actor_service_url` config field. Added field to `ActorConfig`, updated `ResolveCaseActorUrlsNode` to read from config, removed old `server_base_url` data flow, wired Docker Compose for multi-container topology, added comprehensive tests. All 8 acceptance criteria met.

PR: <https://github.com/CERTCC/Vultron/pull/1695>

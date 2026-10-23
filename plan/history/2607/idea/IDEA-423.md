---
source: IDEA-423
timestamp: '2026-07-28T18:13:09.192082+00:00'
title: 'USE-CASE-02: UseCase Protocol generic enforcement with UseCaseResult envelope'
type: idea
---

## Summary

Define a consistent UseCaseResult Pydantic return envelope and enforce it via
mypy across all use-case classes. Currently all execute() methods return None;
this task decides whether and how to introduce a typed result.

## Context

Deferred pending resolution of technical-debt items TECHDEBT-21/22. The
decision may be 'keep None' with a rationale note, which would close this issue.

## Acceptance Criteria

- [ ] Design decision recorded (spec entry or notes update) on whether to
  introduce UseCaseResult or keep execute() -> None
- [ ] If a result envelope is introduced, all use cases return it and mypy
  enforces the return type
- [ ] If the decision is to keep None, this issue is closed with a rationale comment

**Processed**: 2026-07-28 — implementation tracked in #1769.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1768>.
Spec: `specs/use-case-organization.yaml` (UCORG-05).
Notes: `notes/use-case-protocol.md`.
ADR: `docs/adr/0040-use-case-result-envelope.md`.

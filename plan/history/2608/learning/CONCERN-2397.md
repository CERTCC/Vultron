---
source: CONCERN-2397
timestamp: '2026-08-25T17:12:42.105054+00:00'
title: spec-to-story traceability is one-way — specs don't back-reference user stories
type: learning
---

## Concern

Traceability between user stories and spec requirements is one-way: `docs/reference/user_stories/traceability.md` maps stories → specs, but spec YAML files do not back-reference the user stories that motivated them. This means a requirement cannot be traced back to its stakeholder need without consulting the traceability matrix, and the matrix is a manually-maintained document that drifts.

## Surface Symptom vs. Underlying Problem

**Surface symptom:** Spec requirements have no `relationships:` entries of type `satisfies` pointing to user story IDs. The `traceability.md` matrix is the only artifact linking stories to requirements, and it lives outside the spec files themselves.

**Underlying problem:** Without bidirectional traceability, it is not possible to answer "which stakeholder need does this requirement serve?" from the spec alone. This violates the NASA requirements validation criterion for bidirectional traceability to baselined stakeholder expectations. It also means that when a user story is updated or a new story is added, there is no automated way to identify which requirements need review. The traceability matrix is a snapshot that will drift.

## Resolved

2026-08-25 — implementation tracked in #2585. Docs PR: <https://github.com/CERTCC/Vultron/pull/2584>. Spec: `specs/spec-registry.yaml` (SR-11-001 through SR-11-004).

## Design decisions

- **Separate `stories:` field** (not `relationships:`): story IDs are not in the spec registry index, so using `relationships:` would cause hard lint errors from `validate_cross_references()`. A dedicated `stories: list[StoryIdStr]` field with its own Pydantic type avoids this without polluting the cross-reference graph.
- **No rename** of story IDs: renaming `story_2022_NNN` → `STORY-22-NNN` was considered (it would match `SpecIdStr`) but is unnecessary since a separate field with its own `StoryIdStr` type is used.
- **Lint tiers**: `kind: protocol` + `priority: MUST` with no stories → hard error (CI-blocking, suppressible); SHOULD/MAY → advisory warning. Rationale: MUST-level protocol specs are the strongest obligations; SHOULD/MAY story coverage is aspirational.

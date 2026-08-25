---
status: accepted
date: 2026-08-25
deciders: Allen D. Householder
consulted: Claude Sonnet 4.6
informed: CERTCC Vultron team
---

# Use a Dedicated `stories:` Field for Spec-to-Story Traceability (Not `relationships:`)

## Context and Problem Statement

SR-11 requires that `StatementSpec` carry back-references to the user stories
that motivated each requirement, enabling bidirectional traceability between
the spec corpus and `docs/reference/user_stories/`. Two natural attachment
points exist in the schema. Which one should carry story IDs?

## Decision Drivers

- Story IDs (`story_YYYY_NNN`) are not spec IDs — they do not live in the
  spec registry and should not be validated as if they do.
- The existing `relationships:` field's `spec_id` sub-field is validated by
  `validate_cross_references()` against the registry index; a mismatch causes
  a hard lint error.
- Story references must be suppressible per-spec without disabling the broader
  cross-reference graph check.

## Considered Options

- **Reuse `relationships:`** — add story IDs as `Relationship` items whose
  `spec_id` values carry the `story_YYYY_NNN` pattern
- **Dedicated `stories: list[StoryIdStr]`** — a first-class optional field
  on `StatementSpec` with its own constrained type, separate from
  `relationships:`

## Decision Outcome

Chosen option: **dedicated `stories:` field**, because reusing `relationships:`
would produce a hard lint error on every story back-reference: the cross-
reference validator would reject `story_2022_001` as an unknown spec ID, since
story IDs are not in the registry index. A dedicated field bypasses the
cross-reference graph entirely without polluting it.

### Consequences

- Good, because story back-references are type-safe via `StoryIdStr` pattern
  validation without requiring story IDs to enter the spec registry.
- Good, because the `_nonempty_if_present` validator and `lint_suppress`
  mechanism apply uniformly to `stories:` alongside other list fields.
- Good, because the SR-11-003 hard-error gate and SR-11-004 advisory gate
  can target `stories:` specifically without touching `relationships:`.
- Neutral, because `stories:` and `relationships:` are now two distinct
  back-reference mechanisms — implementors must know which to use for which
  kind of reference.

## Validation

`StoryIdStr` pattern enforcement is tested in `test/metadata/specs/test_schema.py`.
The SR-11-003/004 lint gates are tested in `test/metadata/specs/test_lint.py`.
`uv run spec-lint` exits 0 on the live registry.

## More Information

- Issue: #2585 (implementation)
- PR: #2589
- Follow-up: #2605 (this ADR)
- See also: `notes/specs-vs-adrs.md` for the decision-tree that prompted
  writing this record.

Generated spec requirements: `specs/spec-registry.yaml` SR-11-001, SR-11-002

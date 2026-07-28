---
title: "spec rel_type 'related_to' is not a valid enum value"
type: learning
timestamp: "2026-07-23"
source: ISSUE-1652
signal: spec-ambiguity
---

When adding a `relationships` entry to a spec YAML, the `rel_type` field
must be one of the enumerated values validated by `SpecFile`. The value
`related_to` is NOT valid and causes a pydantic `ValidationError` at
`spec-dump` time.

Valid `rel_type` values (as of 2026-07-23):
`implements`, `supersedes`, `extends`, `depends_on`, `conflicts`, `refines`,
`derives_from`, `verifies`, `part_of`, `constrains`, `satisfies`.

When the intent is "this spec is loosely related to another", use `refines`
with a clarifying `note:` field, or omit the relationship altogether if no
normative link exists.

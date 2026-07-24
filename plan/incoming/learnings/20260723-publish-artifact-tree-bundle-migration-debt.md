---
title: publish_artifact_tree.py not fully migrated to bundle pattern
type: learning
timestamp: 2026-07-23
source: ISSUE-1645
signal: concern
---

`publish_artifact_tree.py` was given a `call_out` bundle parameter in #1645, but
its internal caller `publication_tree.py` still passes individual factory kwargs
directly to `_make_artifact_arm`. This means:

- The tree builder has two overlapping APIs (bundle + individual kwargs).
- `test_publish_artifact_tree.py` has 16 pre-existing pyright errors (parameter
  name mismatch: test factories use `n: str` instead of `name: str` as required
  by `CallOutBackendFactory`).

Both issues were pre-existing before #1645 landed, but a clean follow-up task
should:

1. Migrate `publish_artifact_tree.py` to accept a `PublicationArtifactCallOutBundle`
   (or fold its factories into the existing `PublicationCallOutBundle`).
2. Fix the `test_publish_artifact_tree.py` factory signatures to use `name: str`.

---
source: IDEA-560
timestamp: '2026-05-19T18:50:19.199763+00:00'
title: GitHub workflow to build and run demo containers on PRs against main
type: idea
---

## #560 GitHub workflow to build and run demo containers on PRs against main

**Full title**: Idea: GitHub workflow to build and run demo containers on PRs against main

**Summary**: We need integration tests that run the actual demos and look for
demo success when they run. This is important especially for our multi-actor
demos to ensure we don't inadvertently break them with changes.

**Motivation**: Currently we have unit and integration tests that run as
workflows on PRs against main, while these usually prevent the demos from
crashing, they don't ensure that the demos actually complete successfully.
For example we have recently observed demos where the full test suite succeeds
but the demo shows 404 errors (e.g., #557) which causes the demo itself to
fail (the process completes but the logs obviously indicate failure).

**Rough Approach**:

1. Adapt the demo runner script to be less forgiving about exceptions or errors
   observed that are not a deliberate part of the demo. Maybe the script should
   outright crash with a demo failure error so we can catch it more directly.

2. A GitHub workflow that builds and spins up the multi-actor containers and
   runs the demo against them, making sure this is efficient (not rebuilding
   containers when unnecessary, but also not ignoring significant changes that
   would cause main to fail if someone cloned it).

Regardless of approach, any workflow that runs the demos should do its best to
replicate the expected conditions of what we would have a user do if they
`git clone; run-demo`.

**Processed**: 2026-05-19 — design decisions captured in
`specs/demo-ci.yaml` (DEMOCI-01 through DEMOCI-03) and `notes/demo-ci.md`.

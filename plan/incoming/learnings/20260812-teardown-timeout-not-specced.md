---
title: DEMOCI-02-010 does not bound the docker compose down stop timeout
type: learning
timestamp: 2026-08-12
source: ISSUE-2245
signal: spec-gap
---

DEMOCI-02-010 requires `docker compose down -v` in the teardown step but does
not specify a per-container stop grace period. When the vendor container wedged
(#2245), `compose down` inherited Docker's default 10-second SIGTERM window
followed by unbounded SIGKILL retries, consuming the remaining job budget.

Fix added `--timeout 30` (30-second cap per container), which is not backed by
a spec entry. Consider adding a sub-requirement to DEMOCI-02-010 specifying the
maximum stop timeout to bound wedge impact.

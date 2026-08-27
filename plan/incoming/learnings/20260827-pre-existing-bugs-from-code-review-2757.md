---
title: 3 pre-existing bugs surfaced by code review on PR #2775
type: learning
timestamp: 2026-08-27
source: ISSUE-2757
signal: concern
---

The automated code reviewer on PR #2775 identified 3 bugs in files outside the PR diff.
None were introduced by the PR. Each should be tracked as a Bug or Concern issue.

1. **`docs/adr/0076` + `vultron/core/behaviors/status/add_case_status_tree.py:86`**
   ADR-0076's Validation section and the amended ADR-0046 both assert that
   `RequireCaseOwnerApproval` is the out-of-the-box default for the StatusAdoptionGate
   and EmbargoTeardownAuthorizationGate seams. The code still uses `AlwaysSucceed` for
   both. The docstring on `add_case_status_tree.py:86` still reads "Default is
   AlwaysSucceed". An operator reading the ADR believes the conservative posture is
   active by default; the code provides zero protection without explicit configuration.

2. **`vultron/demo/helpers/sync.py:241`** — `verify_replica_state` TOCTOU window:
   `auth_entries` is fetched before `replica_entries`. In a fast-replicating environment,
   the authoritative log can append entry index M+1 between the two fetches and the
   replica can receive it before `replica_entries` is read. Then
   `auth_entry_by_index.get(M+1)` returns `None` and the assertion fires with the
   misleading message "replica is ahead of auth or coverage check is stale" when the
   real cause is a stale auth fetch.

3. **`.agents/skills/bugfix/SKILL.md:54`** — `calve-epics` Mode 1 is invoked at step 2,
   before `orient-agent` at step 3. `calve-epics` must semantically match the bug issue
   against open epics using domain terminology. The spec corpus, glossary, and schedule
   loaded by `orient-agent` are the primary reference for that matching. Running
   `calve-epics` before `orient-agent` means the matching runs without that context.

Note: the actor.py `backend.update()` without `setup()` finding is already tracked in
`plan/incoming/learnings/20260827-code-review-2109-deferred-preexisting.md` item 1.

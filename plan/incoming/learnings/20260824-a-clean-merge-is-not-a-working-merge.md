---
title: A conflict-free merge is where the semantic breakage hides, not where it isn't
type: learning
timestamp: 2026-08-24
source: ISSUE-2238
signal: process-gap
---

Catching `bug/2238-…` up to `main` took three rounds (169 + 19 + 28 commits). Each
time, the conflicts were the cheap part and the **clean** merge was where the
damage was:

| Round | Conflicts | Failures on the conflict-free tree |
|---|---|---|
| 1 | 7 files | **28** unit failures |
| 2 | 2 files | 0 |
| 3 | 7 files | 2 unit failures |

**Why.** Git merges text. When a branch *retires an API*, `main`'s new code cannot
know that, and there is no textual overlap to conflict on — a new caller of a
deleted function merges perfectly and fails at runtime. Every one of the 30
failures was of that shape:

- `SqliteDataLayer(...)` without the now-required `actor_id`
- `record_outbox_item(actor, id)` / `outbox_list_for_actor(actor)` in code `main`
  added, including production (`rm_anomaly.py`, via #2258)
- new tests taking a `dl` fixture this branch replaced with `store_for(actor)`
- new tests running as a non-default actor without `@pytest.mark.executes_as`, so
  they opened the wrong actor's store — **three separate merges, same shape**

**The two worst cases were conflicts that looked resolvable either way:**

1. **A file split hides a change.** `main` moved four nodes from
   `case/nodes/case_setup.py` to a new `case_actor_setup.py`. The conflict is
   reported against the *old* path; the new path merges clean. Taking the
   deletion silently discarded this branch's two-store write in
   `CreateCaseActorServiceNode` — the write that makes a CaseActor a *hosted*
   actor rather than just a row, without which its inbox 404s. It had to be
   re-applied by hand in the new module.
2. **A migration can drop a field while looking like a pure refactor.** `main`
   migrated `FindCaseActorNode` to typed ports and, in the process, dropped the
   `case_id` output this branch had added. Taking `main`'s side wholesale would
   have reverted a real fix (`CheckIsCaseManagerNode` reads `case_id`; without it
   the role gate returns FAILURE and the guard's selector silently skips, so the
   announce fires for nobody). Nothing in the conflict markers said so.

**How to apply.**

- After resolving conflicts, **run the full unit tier before believing the merge**.
  Treat "0 conflicts" as no evidence at all. `git status` clean is not a signal.
- Sweep for the APIs your branch retired, across `vultron/` *and* `test/`, rather
  than waiting for tests to find them. `grep` for each removed name; check the
  hits against `git show origin/main:<file>` to tell "mine" from "theirs".
- For every conflict where one side is a **rename, split, or migration**, diff
  your side's version of the moved code against the new home before taking
  either side. The question is not "which side is newer" but "does the new home
  contain what my side added".
- Separate identifier collisions by **topic, never by find-and-replace**. Both
  ADR renumbers had our citations mentioning the other ADR's subject and vice
  versa. The reliable test is whether `origin/main`'s copy of the file already
  cites that identifier.
- Expect the cost to scale with branch lifetime, not with branch size. This
  branch needed three merges in one session because `main` kept moving; see
  [[adr-number-is-a-claim-on-a-shared-sequence]] for the same lesson about
  identifiers.

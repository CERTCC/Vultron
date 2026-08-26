---
title: An unlanded ADR number is a claim on a sequence main allocates from
type: learning
timestamp: 2026-08-22
source: ISSUE-2238
signal: process-gap
---

The per-actor storage ADR was renumbered **four times** while catching its branch
up to `main`:

- It was ADR-0066. `main` had landed a different ADR-0066, "Outbox Terminal
  State", dated three days earlier.
- It became ADR-0069. `main` then landed a different ADR-0069, "Adopt
  certcc.github.io/Vultron as the Vocabulary Namespace Host" (#2105), during the
  same session.
- It is now ADR-0073.

Each renumber moved ~224 citations across ~124 files, plus the file rename,
`mkdocs.yml` nav, the superseded ADR's pointer, and the generated index.

**Why:** an ADR number is allocated by taking `max(existing) + 1` at authoring
time, but it is not *reserved* until the PR merges. A long-lived branch holds a
claim on a sequence that `main` keeps allocating from, so the claim is
invalidated by any ADR that lands first. Nothing detects the collision: two files
can share a number indefinitely, and `adr-index --write` renders both without
complaint. The pre-commit `adr-index-sync` hook only checks the index matches the
files on disk — it does not check that numbers are unique.

**How to apply:**

- Re-check the ADR number immediately before merging any branch that adds one,
  not only when authoring it. `git ls-tree --name-only origin/main docs/adr/`
  gives the current allocation.
- Separate citations by *topic*, never by mechanical find-and-replace. Both
  collisions had our citations mentioning the other ADR's subject and vice
  versa: several of ours mention the outbox (because per-actor storage is what
  removed `actor_id` from the outbox API), and two comments in `main`'s own
  `outbox_handler.py` were about storage isolation. The reliable test is whether
  `origin/main`'s copy of a file already cites that number.
- A collision can already exist on `main`: `plan/history/2608/learning/
  CONCERN-2106.md` reserves ADR-0069 for a *third* subject, a planned
  `0069-ledger-replication-companion-spec.md`, while `main` has landed 0069 as
  the namespace ADR.
- **Done:** `adr-index` now has that uniqueness check.
  `duplicate_numbers()` reports every number with more than one claimant;
  `--check` fails and names both files, and `--write` *refuses* rather than
  rendering an index with two entries at the same number. Rendering both silently
  is what let four successive collisions go unnoticed until merge. Verified
  against a simulated collision, and covered by four tests in
  `test/metadata/test_adr_index_gen.py`.
- The check does not remove the need to re-check before merge — it converts the
  discovery from "notice it while resolving a conflict" into "pre-commit fails" —
  but it does mean the first commit after a bad allocation is where you find out.

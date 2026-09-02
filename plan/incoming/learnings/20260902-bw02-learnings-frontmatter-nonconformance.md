---
title: "37 of 62 incoming learning files cannot be archived by append-history"
type: learning
timestamp: "2026-09-02T00:00:00Z"
source: ISSUE-2762
signal: tooling-issue
---

Found while correcting BW-02 to match observed practice. The audit turned up the
opposite of what was expected: the spec was right about `timestamp` and the
corpus is broken.

`HistoryEntryFrontmatter._coerce_to_utc()` rejects any timestamp that is not
timezone-aware, and YAML parses a bare `timestamp: 2026-09-01` into a *naive*
datetime. `append-history --from-file` validates the incoming file's frontmatter
through that model before archiving, so a bare-date entry fails at the archive
step. Nothing earlier catches it — not review, not the pre-commit hooks, not CI.

Validating every file in `plan/incoming/learnings/` against the real model:

| Status | Count |
|---|---|
| Archivable today | 25 |
| Rejected (bare date, or missing a required field) | 37 |

(Measured 2026-09-02 against 62 files. The rejected count is stable while the
archivable count grows, because newly-added entries vary in which form they
use — which is itself the point: nothing steers an author toward the form that
works.)

So `learn` cannot currently drain most of its own input queue. The failure is
per-file, so it presents as "this one entry won't archive" rather than as an
obviously systemic problem, which is probably why it accumulated.

Two distinct causes in the 37:

1. **Bare-date `timestamp`** — the dominant form. Fix is mechanical:
   `timestamp: 2026-08-27` → `timestamp: "2026-08-27T00:00:00Z"`. Quote it, so
   YAML yields a string for Pydantic to parse rather than a date.
2. **Missing required fields** — 7 files lack some or all of `title`, `type`,
   `timestamp`, `source`: `2026-08-28-2175-is-leader-defer.md`,
   `20260827-glossary-acs-pre-satisfied.md`,
   `20260831-2067-pr2882-code-review-deferred-findings.md`,
   `20260901-wire-normalize-ratchet-threshold-weakened.md`,
   `20260901-wire-type-map-key-naming-agents-md-wrong.md`,
   `2627-deferred-bugs-dl-read-case.md`,
   `concern-inbox-handler-protocol-violation-requeue.md`. These need a human to
   supply the originating `source`, which cannot be inferred mechanically.

A third hazard, found the same way and fixed in this PR: an unquoted `title:`
whose text *ends* with a colon (`...with no to:`) makes the frontmatter invalid
YAML outright. Titles that contain `:` or end in `:` MUST be quoted. Worth a
lint rule — the existing "Validate notes frontmatter" pre-commit hook covers
`notes/` only, not `plan/incoming/learnings/`.

Recommended follow-up, in order:

- Extend the frontmatter-validation pre-commit hook to `plan/incoming/learnings/`,
  validating through `HistoryEntryFrontmatter` itself so the check and the
  archiver cannot drift. This stops the bleeding before the backlog is cleared.
- Mechanical sweep for cause 1 (36 files).
- Human pass for cause 2 (6 files).

Deliberately not done here: this PR is a bugfix on the embargo path, and
rewriting 37 unrelated learning files in it would bury the actual change. Only
the six files this PR authored were brought into conformance. BW-02-004 now
states the bare-date prohibition explicitly, with a test.

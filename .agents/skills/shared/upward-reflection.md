# Upward-Reflection Checklist

Run this before completing a `build` or `bugfix` session. It is mandatory
(BW-07-001) — a session that records nothing is valid only if you ran the
checklist and every answer was "no".

Answering "yes" does **not** mean "write a learning file." It means "route it."
Most findings have an owner nearer than the next `/learn` batch, and parking one
in the queue means every agent between now and that batch rediscovers it.

## The checklist

Ask each question. For each "yes", take the action in the right-hand column
**in this session**.

| Was there… | Route it to |
|---|---|
| Something that exists but is wrong — fragility, risk, debt, a bug in code you didn't touch | GitHub `type:Concern` issue (`/new-item`) |
| Something that should exist but doesn't | GitHub `type:Idea` issue (`/new-item`) |
| A broken tool, skill, or tracking artefact — bad script, stale issue body, wrong path in a skill | Fix it now, in this session |
| A narrow but true fact about the code that a future agent would trip over | An assertion at the site — regression test, type annotation, or comment |
| A general claim you believe but can't prove from this one instance | `signal: theme-candidate` learning file |
| Behaviour with no spec entry, or a requirement that was unclear or self-contradictory | `signal: spec-gap` / `spec-ambiguity` / `spec-contradiction` learning file |

Only the last two rows write a file.

## Three rules that decide the hard cases

**A closed decision is not a learning (BW-07-008).** If you decided something,
applied it, and shipped it — and nothing is being asked of any future reader —
write nothing. The commit, the diff, and the PR body are the record. "Used
`cast()` to bridge the return type" is a commit message wearing a costume. A
decision only earns a file if it left an open question behind.

**Specificity is fine; unrecognizable triggers are not.** The test is not "how
general is this?" but **"will a future agent recognize they're in this
situation?"** "Pydantic v2 runs `mode='before'` validators in reverse definition
order" is extremely narrow and worth keeping, because someone will one day be
staring at a validator running in the wrong order and will match the symptom. A
finding whose trigger condition nobody will ever recognize is noise no matter
how true it is.

**Prefer an assertion to a document.** For a narrow fact that *is* retrievable,
a test that fails beats a note that explains — the test fires on its own, the
note needs someone to remember to look. If the finding can be encoded as a
regression test, a `Literal`, a lint rule, or a comment on the offending line,
do that instead of writing a file. Fixing the broken script beats describing the
broken script.

## Code-review findings are issues, always (BW-07-009)

Findings in files your change didn't touch — pre-existing bugs, DEFER items,
anything ruled out of scope — **must** be filed as `type:Bug` or `type:Concern`
issues before the session ends. Never a learning file, and never left as a
PR-comment advisory. A learning file can't be assigned, scheduled, or closed, so
a bug report inside one is inert.

The 2026-09-02 audit is the argument for this. Six entries held ~20 findings;
all but four were eventually filed — by *later* sessions doing their own
reviews, never by the learning file. So the queue never was the tracking
mechanism, just a second ledger shadowing it, and the four exceptions fell
through precisely because writing them down had felt like tracking them.

Citing the PR that surfaced the finding is **not** tracking it either. Several
audited entries claimed to be tracked by pointing at a merged PR number; a PR
records what shipped, not what was deferred. Only an issue number discharges a
finding.

## Corroboration

A `theme-candidate` is a claim awaiting a second witness. Two consequences:

- **If your finding corroborates an entry already in the queue, file a
  `type:Concern` issue now** (BW-07-006) — don't add a second learning file. The
  second witness is the moment the claim becomes trustworthy, so it's the moment
  to act. Check the queue before writing: `ls plan/incoming/learnings/`.
- Single-witness entries are promoted by `learn` only with corroboration
  (BW-07-005), and are archived as unreproduced after 30 days without it
  (BW-07-007).

## File format

For the two rows that do write a file: `plan/incoming/learnings/YYYYMMDD-SLUG.md`,
frontmatter `title`, `type: learning`, `timestamp` (tz-aware ISO 8601 UTC),
`source`, and `signal:` (one of `theme-candidate`, `spec-gap`, `spec-ambiguity`,
`spec-contradiction`). No completion summaries (BW-01-001).

Commit the file as part of the originating PR (BW-01-006). When archiving, pass
the signal via `uv run append-history learning --signal <type>`; `--from-file`
preserves the `signal:` frontmatter verbatim.

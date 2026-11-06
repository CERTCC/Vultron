---
title: spec-amendments.sh cannot tell an accidental reversion from an intended amendment, so stale prepared spec text passes every gate
type: learning
timestamp: 2026-11-06T20:05:00Z
source: ISSUE-5967
signal: spec-gap
---

## Trigger

An issue tells you to apply spec text prepared earlier on another branch — a
`prep/*` branch, a reverted commit, a patch in an issue comment — rather than
text you write yourself. The preparing issue closed days ago.

## Claim

No requirement governs how prepared spec text is carried across issues, and no
gate in the pipeline can tell an accidental reversion from an intended
amendment. Applying such a branch wholesale silently reverts every requirement
that landed on `main` after the branch was cut, and the PR documents the
reversions as amendments.

Each gate passes on a reverted corpus, because every gate asks whether the
corpus is *well-formed*, never whether it is *current*:

- `spec-lint --changed-since origin/main` exits 0: the older text was valid
  when it was written, so it is still valid.
- `bash .agents/skills/shared/spec-amendments.sh origin/main` lists a reverted
  requirement exactly as it lists an amended one — `<ID> changed statement` —
  because it diffs two refs and reports which `statement:` and `priority:`
  fields differ. It has no notion of direction.
- `pr-body-guide.md` then requires a `### <ID>` block per listed ID, so an
  agent working from the tool's output writes a Before/After/Reason block that
  faithfully describes the reversion, and a reviewer reading the PR body sees a
  documented amendment.
- `spec-backstop` derives nothing: a spec-only diff has no Python, which it
  reports and which exits 0.

## Reason

The amendment tool answers "what differs between these two refs", which is the
right question when the diff is authored against the current corpus and the
wrong one when it is replayed from an older base. Nothing downstream recovers
the missing question, because the PR body is generated from the tool's answer.

## Evidence

One witness. #5967 applied PAD-18 text prepared on
`prep/5946-pad-18-amendments` (`3b5ccf9e6`). Against `main` that branch's diff
to `specs/parallel-development.yaml` was 227 insertions / 235 deletions, of
which only the hunks at old-file offset 2603 and above were the intended
amendments. The rest would have deleted `PAD-02-041` and `PAD-05-013`, reverted
the whole recalibrated `PAD-05` size-band table and its survey rationale,
renamed `TestReviewCeiling` back in `PAD-15-004`/`-005`, reverted
`needs-decomposition` to `needs-planning` in the `PAD-16` area, and deleted
`PAD-18-032`, which #5945 had added. On the hand-applied result,
`spec-amendments.sh origin/main` reported nine amended IDs; run on the
wholesale application it would have reported those nine plus the reverted ones,
in the same format, with no mark distinguishing them.

The reversion was caught only because the issue body named the hazard and gave
the offset boundary. An agent handed the same branch without that warning would
have had no signal from any tool.

## What would close it

A requirement — probably in `PAD` beside the amendment rules, or in `MS` beside
`MS-09`'s lifecycle rules — that says prepared spec text is applied against the
current corpus, not replayed from its own base, plus a check that can answer
the direction question. The cheapest form of the check is already available to
the tool: compare each listed ID against its text at the **merge base** of the
two refs as well as at the base ref. An ID whose new text equals its merge-base
text, while the base ref's text differs, is a reversion of work that landed
after the branch was cut, not an amendment. That is the same merge-base read
`MS-09-008` already requires of `spec-retire` for the text it archives, so the
primitive exists in the corpus.

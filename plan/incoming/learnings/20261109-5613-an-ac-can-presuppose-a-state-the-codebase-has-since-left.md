---
title: "An AC can presuppose a state the codebase has since left, and the pre-claim gate only asks whether it is satisfied, never whether its premise still holds"
type: learning
timestamp: "2026-11-09T18:40:00Z"
source: ISSUE-5613
signal: theme-candidate
---

## Trigger

You are building an issue written weeks earlier. An AC names a current
condition — a field that is optional, a sentence that reads a certain way, a
behaviour that is opt-in — and that condition no longer holds. The AC is not
*wrong*; the thing it describes has moved. You can satisfy the letter of it and
deliver something nobody wants, or you can notice and report the difference.

`build` Phase 2 step 6's pre-claim gate does not see this. It asks one
question, "is this AC already satisfied on `origin/main`?", and both outcomes
of that question — satisfied, so close the issue; unsatisfied, so claim it —
leave a stale premise unexamined.

## Claim

A premise an AC rests on ages at the same rate as the code, so the pre-claim
check should read each AC twice: once for *is this already done*, and once for
*is what this sentence assumes still true*. The second reading has no
mechanical form (the gate greps for evidence that an AC is satisfied; it
cannot grep for a premise), so it has to be a stated step with an output — the
PR body reporting, per AC, the form in which it was met.

## Evidence

Issue #5613 had six ACs and two of them had moved out from under themselves,
which is what makes this more than one instance:

- **AC-4** asked for "a shape test asserts a scenario without `story=` has no
  entry". When the issue was written the composition migration was in flight
  and `story=` was optional; by build time `@scenario` required it
  (DEMOCI-11-024), so no scenario can lack one. Written literally, the AC
  asks for an optional-story code path to exist so a test can cover it — and
  the first pass did exactly that, adding `story: AssembledStory | None =
  None`. The pre-push review caught it: an optional story lets a future
  scenario drop out of the generated manifest with the drift check still
  green. The right answer was the opposite of the AC's letter — make the field
  required and assert that no spec can be built without one.
- **AC-5** quoted the phrase "until the manifest is built" from
  `notes/demo-scenario-tree.md` and asked for it to be dropped. The phrase was
  no longer in the note; the bullet had been reworded to a different
  precondition belonging to another issue. Only the substantive half of the AC
  (narrow the manual run to a PR editing inside a fragment) could be done.

Both were disclosed per-AC in PR #6136's body with the reason, which is the
output the second reading needs.

## What would confirm it

A second issue where an AC's premise aged out, from a different area — the
shape to look for is a PR body saying "AC-N in a different form than written".
Those lines already exist and are greppable across merged PRs; a count of them
over a quarter would say whether this is a pattern or two accidents in one
issue.

## How to apply it

When building an aged issue, read each AC's assumptions against the current
tree before writing code, not only its satisfaction. When an AC's premise has
moved, do the thing the AC was *for* and state the difference per AC in the PR
body — never implement the stale premise to make the sentence true. A planner
can reduce the exposure by writing an AC as the outcome wanted rather than as
a condition of today's code, and by quoting no text it does not own.

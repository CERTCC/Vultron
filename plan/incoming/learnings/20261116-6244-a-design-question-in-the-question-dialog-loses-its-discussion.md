---
title: >-
  The question dialog hides the text written before it and truncates long text,
  so a design question with trade-offs asked through it reaches the maintainer
  with no discussion
type: learning
timestamp: "2026-11-16T18:00:00Z"
source: ISSUE-6244
signal: theme-candidate
---

**Trigger.** You are about to put a design question with real for and against to
the maintainer, in any interview skill (`grill-me`, `plan-issue`, `learn`).

**Claim.** The question dialog shows only its own question and options: the
explanation written earlier in the same turn is hidden, and long question text and
option previews are cut off. A dialog that says "following the discussion above"
arrives with no discussion, and one that carries the discussion arrives truncated.
Either way the maintainer cannot weigh the options.

**Evidence.** Planning #6246 and #6244 (2026-11-16): the maintainer rejected a
question that skipped the discussion, then one that pointed at it ("I'm telling you
REPEAT THE CONTEXT"), then said the presentation "results in cut off lines" and
asked for plain text.

**How to apply.** Write the problem, each option and its trade-offs in the reply,
and end the turn with one plain-text question. Keep the dialog for choices that fit
in a line or two. Now in `.agents/skills/shared/asking-the-user.md` § 8.

**What would confirm it.** Another interview where a dialog-only design question
draws "what do you mean" or a request for the context.

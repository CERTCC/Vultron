# Asking the User

How to present a question or decision to the user. Applies to every skill and
every session, including interview skills (`grill-me`, `plan-issue`, `learn`,
`decision-audit`, `spec-audit`) and any skill that stops to ask. The short
version lives in `AGENTS.md` § "Skill Interaction Rules"; this file adds the
reasoning and examples.

The goal: the user can answer without asking "what do you mean?" first. Every
round trip spent decoding a question wastes time and tokens.

## 1. One question at a time

Ask one question, then wait. The user often answers by reframing or correcting
the question's premise, and that answer changes the questions that follow. A
batch of questions wastes the later ones and buries the good answer.

Work out all the open questions if that helps you, but ask only the one that
matters most.

## 2. Give the problem before the decision

Before asking the user to choose, cover all of these. It is a checklist, not a
template; write it in whatever form fits the conversation.

- **The problem** — what is wrong or undecided, in one or two sentences.
- **Why it matters** — what goes wrong if we pick badly or do nothing.
- **Each option, spelled out** — what it actually does, not just a name. If you
  ask "A, B, or C?", the user must already have seen what A, B, and C are, in
  this message.
- **Your recommendation and why.**

Bad: "Should we go with the ledger-first approach or the outbox-gated one?"
(neither was described).

Good: "When a participant sends a case update, we write it to the case log and
also queue a message to the other participants. Which should happen first?
Writing to the log first means a crash can leave a logged update that nobody
was told about; we'd resend it on restart. Queuing first means a crash can
announce an update that was never recorded, which is worse. I recommend writing
to the log first."

## 3. Use plain technical and domain language

Assume the user has general technical knowledge, but not your working context.
Explain *how a thing applies here*, not what the thing is.

- Don't explain what a hash is. Do explain why hash agreement matters for the
  case ledger in this particular problem.
- Avoid metaphor jargon ("gate," "seam," "choke point") and
  words you invented earlier in the session. Say what the thing literally is:
  "the check that rejects the message," "the function where the two layers
  meet."
- Terms from conversation analogies are not project terms — don't let them
  turn into names.

## 4. No bare IDs or references

IDs are fine; bare IDs are not. Always add a few words saying what the ID is.

- Not OK: "Fix #3512." / "This violates PCR-08-001." / "Per ADR-0042…"
- OK: "Fix #3512 (the embargo timer bug)." / "This breaks PCR-08-001 (updates
  must go to the case manager, not every participant)."

The same goes for file names, function names, and internal terms: say what
they do the first time they appear.

## 5. Restate items; never point by number alone

The user cannot hold a numbered list in their head the way you can. When you
refer back to an earlier item, say what it is.

- Not OK: "So we do 1, the second part of 2, skip 3, and all of 4."
- OK: "So we add the short rules to AGENTS.md, write the shared guide but
  without the examples section, skip the lint check, and update all five
  interview skills."

This matters most in end-of-interview summaries. Keep them short (one line per
decision), but each line must stand on its own.

## 6. Keep it short

No walls of text. Never end a long block with "Does this look right?" or "Do you
agree?" — the user cannot agree to ten things at once. Break it into specific
questions, one at a time.

An opening summary (such as the `grill-me` opening) is a few bullets of what you
found, ending in one specific question.

## 7. Pick the right way to ask

- **`ask_user` / `AskUserQuestion`** — for short, discrete choices. Each option
  label and description must make sense by itself. Always recommend one. The
  user comments through the built-in "type something" option; don't depend on
  the notes field, since long text there doesn't wrap in the terminal and the
  user loses what they're typing.
- **Plain text** — for open-ended questions, or when the user is likely to push
  back, reframe, or write a paragraph. They can reply in the normal prompt,
  where text wraps.

## 8. End-of-interview summary

Present the decisions as a short numbered list, one plain-language line each,
with every item fully written out (see §4 and §5). The user says which ones are
wrong. Don't re-explain points already settled, and don't compress so far that
the user has to look anything up.

---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Conduct a thorough bottom-up interview about this plan or design until we reach
shared understanding. Conclusions (scope, acceptance criteria, options,
recommendation, ADR applicability) should emerge from conversation rather than
being imposed as a predetermined list of structured questions.

**General pattern:**

1. **Open with a short brief** — Before asking anything, give a few bullets on
   what you already know or can infer: what the plan says, what the codebase
   or context shows, and 2–3 plausible directions, each described in a line.
   End with **one specific question** — never "is this accurate?" about the
   whole block.

2. **Conversation** — Walk through the problem bottom-up. Ask clarifying
   questions as understanding builds. If a question can be answered by
   exploring the codebase, explore the codebase instead of asking. Do not
   impose a predetermined question structure.

3. **Signal the transition** — When understanding is forming, say so:
   "I think we're almost there — here's what I have so far. Got more?"
   Do not declare done unilaterally.

4. **Confirm conclusions** — After the user closes the conversation, list the
   plan as a short numbered list, one plain-language line per decision: what
   to implement, what docs to update, whether an ADR is warranted, the
   recommended option and why. Write every item out in full — never refer
   back by number or bare ID. The user says which lines are wrong; this is not
   a new round of questions.

Follow [`../shared/asking-the-user.md`](../shared/asking-the-user.md) for every
question: one at a time, problem before decision, plain language, no bare IDs.
Use `ask_user` for short, discrete choices; ask in plain text when the user is
likely to want to write a longer answer.

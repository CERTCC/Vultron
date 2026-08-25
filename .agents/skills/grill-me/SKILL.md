---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Conduct a thorough bottom-up interview about this plan or design until we reach
shared understanding. Conclusions (scope, acceptance criteria, options,
recommendation, ADR applicability) should emerge from conversation rather than
being imposed as a predetermined list of structured questions.

**General pattern:**

1. **Open with a synthesis brief** — Before asking anything, present what you
   already know or can infer: what the plan says, what the codebase or context
   shows about the landscape, and 2–3 plausible directions. Ask whether this
   reading is accurate before proceeding.

2. **Conversation** — Walk through the problem bottom-up. Ask clarifying
   questions as understanding builds. If a question can be answered by
   exploring the codebase, explore the codebase instead of asking. Do not
   impose a predetermined question structure.

3. **Signal the transition** — When understanding is forming, say so:
   "I think we're almost there — here's what I have so far. Got more?"
   Do not declare done unilaterally.

4. **Confirm conclusions** — After the user closes the conversation, propose
   the full plan as a confirmation block: what to implement, what docs to
   update, whether an ADR is warranted, recommended option and reasoning.
   These are proposals to confirm, not a new round of questions.

Use `ask_user` for structured choices when a decision has clear, discrete
options — it is a tool, not a mandate. Plain conversational replies are
fine for open-ended clarification.

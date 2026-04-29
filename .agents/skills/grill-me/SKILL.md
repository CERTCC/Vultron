---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview me relentlessly about every aspect of this plan until we reach a
shared understanding. Walk down each branch of the design tree, resolving
dependencies between decisions one-by-one. For each question, provide your
recommended answer.

**Ask questions one at a time using the `ask_user` tool.** Never ask questions
in plain text — always use `ask_user` so the user gets a proper response UI.
Provide a recommended answer (or a `choices` array with a recommended option
first) for every question.

If a question can be answered by exploring the codebase, explore the codebase
instead of asking the user.

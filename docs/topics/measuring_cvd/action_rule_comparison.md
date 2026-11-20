---
stakeholder_type: [process-researcher]
level: 500
page_type: reference
subject: neutral
description: >
  The action rules that move advice gives one vendor, and where the authored action rules agree or disagree with them.
---

# Action Rules Against Move Advice

{% include-markdown "../../includes/not_normative.md" %}

This page compares two kinds of advice for the Coordinated Vulnerability Disclosure (CVD) process.
An **authored action rule** suggests an action to a role at a position, and says why.
[Recommended Action Rules for CVD](../other_uses/action_rules.md) lists them.
**Move advice** puts each open move in a band by its outcome shift for each vendor ([ADR-0200](../../adr/0200-move-advice-puts-moves-in-bands-by-outcome-shift-not-by-one-case-score.md)).
The authored rules are a person's claim, and move advice is the evidence of the chance model.
Neither one is ground truth.
A disagreement marks a wrong rule or a blind spot in the chance model, and only a person can say which ([ADR-0216](../../adr/0216-action-rules-span-cs-rm-em-and-pec-and-authored-rules-are-compared-with-rules-generated-from-move-advice.md)).

Read [Move Bands Against Pathology Cases](move_bands.md) first: it defines the bands, the outcome shift, and the desiderata this page names.

## How to read this page

A **position** is one vendor's report management (RM) state, its compound case state (CS), and the case's embargo management (EM) state.
This page covers every position that a walk of the one-vendor chance model reaches.

A **pattern** names a set of positions.
Its CS part, such as `VFdp..`, matches a case state letter by letter, and a dot matches either letter.
A part such as `RM ACCEPTED, DEFERRED` names the states it matches, and a part that is left out matches any state.
A pattern on this page can also cover combinations of states that no walk reaches, but it never covers a valid position where its row does not hold.

A move's **band for one vendor** is harm-free when the deciding part of the vendor's outcome shift is positive, and unhelpful when it is not.
Move advice reads the history of a position as well as its states.
A desideratum that a history has already met or broken changes by nothing, so two histories that reach one position can give one move two bands.
At such a position this page states a **conditional verdict**: each band, with the desiderata whose state gives it.

The state model forces some steps.
At `vfdP..` the vendor becomes aware next, and beside a public exploit the public does.
A **forced** step happens anyway, so no band can say whether an authored rule serves it, and the comparison shows such a rule as not measured.

The chance model holds no state for a vendor's consent to an embargo (PEC), so no position on this page holds one.
An authored rule with a PEC part is therefore undecided at every position here.

A rule number is the rule's place in the table of authored rules on [Recommended Action Rules for CVD](../other_uses/action_rules.md).

## The generated rules

A **generated rule** groups the positions where move advice always gives a move the same band, whatever desiderata are still open.
Its role is the vendor for an RM or CS move, and for an EM move the role that may make that move, or any role.

{% include-markdown "./_generated_action_rules.md" %}

## The comparison

At each position, the comparison gives each authored rule that matches one of five results:

- An **agreement**: the rule names desiderata, and its move is harm-free for the vendor.
- A **rule disagreement**: the rule names desiderata, and its move is unhelpful for the vendor.
- A **misplaced rule**: the state machines do not allow the rule's move here, or the rule's roles may not make it.
- An **unscored rule**: the rule's action has no band here, because it changes no state, its step is forced, its move is one move advice does not score, or the rule names no desideratum.
- An **unclaimed move**: a move is harm-free for the vendor, and no matching rule names it.

A rule disagreement whose rule cites a blind spot of the chance model names the issue that tracks the blind spot.
The comparison resolves nothing, and it changes neither the authored rules nor the generated rules.

{% include-markdown "./_action_rule_comparison.md" %}

## Rebuilding this page

The tables on this page come from the current move advice and the authored rules.
The command `uv run action-rules-docs --write` rebuilds them, together with the authored-rules table on [Recommended Action Rules for CVD](../other_uses/action_rules.md).
A test fails when a committed table differs from what the command builds.
Nobody edits the tables by hand.

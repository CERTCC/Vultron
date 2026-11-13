---
status: proposed
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-13
revision: 1
deciders: Allen D. Householder
consulted: Claude Opus 5.5; #6450; #5966; ADR-0182; ADR-0190; docs/topics/measuring_cvd/ (process model desiderata, random walk, benchmarking MPCVD)
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# Move Advice Puts Moves in Bands by Outcome Shift, Not by One Case Score

## Context and Problem Statement

The case shadow shows the next moves open in a case, for every participant (ADR-0190 rule 5).
The walk of ADR-0182 gives the expected desiderata outcome from any state of the case.
Thus each move has a change in expected outcome for each vendor and for each desideratum.

One case score would rank the moves, but one score must combine all of these changes into one number.
Each way to combine them can give advice against the case as a whole.
For example, a mean over notified vendors can score "notify vendor 3" as a loss, because the new vendor starts with a low score.
One best move also gives too little: at a given point in a case, many moves are good, and some are clearly better than others.

The question: **how does the shadow sort the open moves, so that the analyst sees the better options and the trade-offs between them, without one number for the case?**

## Decision Drivers

- The advice serves the case as a whole, not one participant.
- The analyst gets options, not one answer.
- A trade-off between participants stays visible. The tool does not decide it in silence.
- No weight between desiderata or between vendors is invented.
- The method uses the chance model and the desiderata that the measures already have (ADR-0182).

## Considered Options

- One case score from an aggregate of the vendor scores (median, mean, maximin, mean then spread, Nash product)
- Bands from a comparison of each move's outcome shifts, scope by scope
- A fixed weight for each desideratum and each vendor

## Decision Outcome

Chosen option: "Bands from a comparison of each move's outcome shifts, scope by scope", because it is the only option that needs no weights and that shows each trade-off instead of hiding it in one number.

1. **The chance value is the reference.**
   For each scope, the chance value is the expected outcome from where the case stands, if each allowed next step is equally likely.
   It is the mean of the values after each open move, solved over the walk of ADR-0182.
2. **A move's outcome shift is one number for each scope.**
   The outcome shift is the change in expected outcome from the chance value, after the move.
   The scopes come from the desiderata themselves: one scope for each vendor in the case, notified or not, and one scope for each case-wide group (embargo and multi-party).
   A scope with no chance value has no outcome shift.
   Thus path preferences, and participants with no vendor path, are not scopes until their preferences have chance values.
3. **One move beats another only in every scope.**
   Move X beats move Y when X does at least as well as Y in every scope and better in at least one.
   Two moves that trade off against each other do not beat each other.
4. **Three bands.**
   A leading move is an open move that no other open move beats.
   A helpful move is not leading, but has a positive outcome shift in at least one scope.
   An unhelpful move has no positive outcome shift in any scope.
   The page shows the unhelpful moves in a collapsed group, and does not hide them.
5. **Two marks, not bands.**
   "Harms none" marks a move with no negative outcome shift in any scope.
   "Leading among yours" marks a coordinator's move that none of the coordinator's other open moves beats, whatever its band.
6. **Each negative shift is shown.**
   Each move shows its negative outcome shifts by scope, for example "vendor 2" or "the case: embargo".
   A harm is relative to the chance value, not a broken desideratum, and the page says so.

If the cases show that adding up the desiderata inside one vendor's scope hides a trade-off that matters, the fallback is one scope for each vendor and desideratum group.

### Consequences

- Good, because the analyst sees several good options, with the trade-offs between them.
- Good, because no weight between vendors or between desiderata is chosen.
- Good, because a move that notifies a vendor helps that vendor's scope, so the tool never advises against it.
- Good, because "harms none" and "beats" use the same test, so a move that harms none can only be beaten by another move that harms none.
- Bad, because with many scopes, most moves do not beat each other, and the leading band can be large.
- Bad, because inside one vendor's scope the desiderata are still added together.
- Neutral, because a participant with no vendor path, such as a reporter, is visible only through the case-wide scopes until path preferences have chance values.

## Validation

The spike #6450 writes the pathology cases as tests first, then runs the bands and the five aggregates against them.
A research page under `docs/topics/measuring_cvd/` gives the results, the depth of the layers in its cases, and the method.
A result that overturns a rule above changes this record.

## Pros and Cons of the Options

### One case score from an aggregate of the vendor scores

- Good, because one number ranks every move, so the page can lead with one move.
- Bad, because each aggregate has a case where it advises against the case as a whole, for example a mean that a new vendor pulls down.
- Bad, because one number cannot show a trade-off between vendors.

### Bands from a comparison of each move's outcome shifts, scope by scope

- Good, because it needs no weights.
- Good, because it gives options, not one answer.
- Bad, because the bands are only as good as the scopes, and a scope with no chance value is not seen.

### A fixed weight for each desideratum and each vendor

- Good, because one number ranks every move.
- Bad, because nothing in the research supports one set of weights, and each set decides an open question in silence.

## More Information

Decided by the maintainer in the planning interview for #6450 on 2026-11-13.
Case scoring for each scope is #6457, the path-preference counts are #6459, and chance values for path preferences are Epic #6461.
The chance model and the desiderata are [ADR-0182](0182-cvd-measures-take-chance-from-the-smallest-model-holding-each-desideratum.md).
The shadow that shows the bands is [ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md).

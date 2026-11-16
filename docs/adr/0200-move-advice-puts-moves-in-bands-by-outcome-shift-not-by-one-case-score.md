---
status: accepted-provisional
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-16
revision: 2
deciders: Allen D. Householder
consulted: Claude Opus 5.5; #6450 (spike results); #5966; ADR-0182; ADR-0190; docs/topics/measuring_cvd/ (process model desiderata, random walk, benchmarking MPCVD)
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# Move Advice Puts Moves in Bands by Outcome Shift, Not by One Case Score

## Context and Problem Statement

The case shadow shows the next moves open in a case, for every participant (ADR-0190 rule 5).
The walk of ADR-0182 gives the expected desiderata outcome from any state of the case.
Thus each move has a change in expected outcome for each vendor.

One case score would rank the moves, but one score must combine the vendors' changes into one number.
Each way to combine them can give advice against the case as a whole.
For example, a mean over notified vendors can score "notify vendor 3" as a loss, because the new vendor starts with a low score.
One best move also gives too little: at a given point in a case, many moves are good, and some are clearly better than others.

The question: **how does the shadow sort the open moves, so that the analyst sees the better options and the trade-offs between them, without one number for the case?**

## Decision Drivers

- A CVD case is a cooperative game: the participants play against the game, not against each other, and they win or lose together.
  Thus the advice prefers a move that serves the case over a move that serves only the participant who makes it.
- The analyst gets options, not one answer.
- A trade-off between vendors stays visible. The tool does not decide it in silence.
- The method chooses no weight between vendors.
- The method uses the chance model, the desiderata and the desiderata weights that the measures already have (ADR-0182).
- An embargo serves the end desiderata, such as a fix deployed before the vul is public. The advice does not prefer an embargo for its own sake.

## Considered Options

- One case score from an aggregate of the vendor scores (median, mean, maximin, mean then spread, Nash product)
- Bands from each move's own outcome shifts, with dominance inside each band
- A fixed weight for each vendor

## Decision Outcome

Chosen option: "Bands from each move's own outcome shifts, with dominance inside each band", because it is the only option that puts no vendors into one number, so it shows each trade-off, and it still puts a move that harms no vendor above a move that harms one.

1. **A scope is one vendor.**
   In this version, there is one scope for each vendor in the case, notified or not.
   A vendor's scope holds the desiderata that are about that vendor: the original twelve, the report-handling desiderata, and the embargo desiderata.
   There is no case-wide scope.
   A harm to the case shows as a harm to each vendor that it touches.
   Move advice does not use the pair desideratum `V_i ≺ F_j`, because the vendors' own desiderata already measure what it protects, and it is backwards in supply-chain cases (#6502).
   A participant with no vendor path is not a scope until it has desiderata of its own and those desiderata have chance values.
   Epic #6461 can add such scopes by an amendment to this record.
2. **The chance value is the reference.**
   For each desideratum, the chance value is the probability that it holds if the case is left to chance from where it stands.
   It is the mean over every allowed next step in the desideratum's smallest model (ADR-0182 rule 2), solved over the walk of ADR-0182.
   The next steps include events that no participant chooses, such as public awareness, a public exploit, or observed attacks.
   Thus each desideratum's chance value does not depend on the number of participants in the case.
   A scope's chance value is the sum of the chance values of its desiderata, each weighted `1 − f_d`, the weight the case scores already use (`vultron/measure/scoring/complete.py`, `reasoning_over_histories.md`).
   Each group of equivalent desiderata counts once in the sum: `E ≺ P` stands for `E ≺ X` and `E ≺ A`, and `Ex_own ≺ P` for `Ex_own ≺ X` and `Ex_own ≺ A`, because each group holds in exactly the same histories.
   If each one counted, an embargo that ends on its own terms would add three times what `F_i ≺ Ex_own` takes away from a vendor with no fix, and the advice would show the end of the embargo as harm-free (#6450).
3. **A move's outcome shift has two parts in each scope.**
   The outcome shift is the expected outcome after the move, minus the chance value.
   The end part covers the end desiderata: all the desiderata of the scope except the embargo desiderata.
   The embargo part covers the embargo desiderata, including `F_i ≺ Ex_own`.
   A move that is not a step in a desideratum's model does not change that desideratum.
4. **Dominance is a partial order, with the ends first.**
   Move X dominates move Y when X's end parts are at least as good as Y's in every scope and better in at least one.
   When the end parts of X and Y are equal in every scope, X dominates Y when X's embargo parts are at least as good as Y's in every scope and better in at least one.
   Two moves that trade off against each other do not dominate each other.
   Thus a move that raises an end desideratum for one vendor and lowers none for any vendor dominates every move that changes only the embargo.
5. **Three bands, each set by the move's own shifts, with the ends first.**
   A move's band does not depend on the other open moves.
   If the move's end part is not zero in some scope, its band comes from its end parts.
   If its end part is zero in every scope, its band comes from its embargo parts, in the same way.
   - A **harm-free move** has a positive part in at least one scope and a negative part in none.
   - A **trade-off move** has a positive part in at least one scope and a negative part in at least one.
   - An **unhelpful move** has a positive part in no scope.

   Thus bands and dominance use the same order, and a move that dominates a harm-free move is also harm-free.
   The sign test is strict: it counts any non-zero part, however small.
   In #6450, a threshold of 0.01 or 0.05 changes the band of only two moves: publication now and an embargo end on its own terms.
   At 0.05, publication now becomes harm-free in each case with a vendor not yet notified, which hides the harm to the vendor with no fix, so no threshold applies.
   A negative embargo part beside a non-zero end part does not change the band, but the page still shows it.
   Any band can be empty.
   The page shows the harm-free band first, then the trade-off band, and collapses the unhelpful band into a group that the analyst can open.
6. **Inside a band, a grade and a mark, but no order.**
   A move's layer is its depth in the dominance order: layer 1 holds the moves that no open move dominates, layer 2 the moves that only layer-1 moves dominate, and so on.
   A **top** move is a harm-free or trade-off move in layer 1.
   In the harm-free and trade-off bands, the page shades each move by its layer with a named sequential colour map, with layer 1 at the dark end, and marks each top move with an icon.
   Moves in the same layer get the same shade, because neither dominates the other.
   A trade-off move that a harm-free move dominates is not top, and the page says that a harm-free move does at least as well on every vendor's end desiderata.
   The unhelpful band has no shade and no mark.
   The page's advice is: choose the darkest move in the highest band that has one.
7. **Leading among yours.**
   A coordinator's harm-free or trade-off move is leading among yours when none of the coordinator's other open moves dominates it.
   The page marks it inside its band.
8. **Each negative shift is shown.**
   Each move shows its negative end and embargo parts by vendor, with their size.
   A negative shift means worse than the chance value.
   It does not mean a broken desideratum, and the page says so.

If the cases show that the sum inside one vendor's scope hides a trade-off that matters, the fallback is one scope for each vendor and desideratum group.
The cases of #6450 do not call for it: the one sum that hides a trade-off is publication now for a vendor whose fix is ready, and both sides of it (`D ≺ P` down, `P ≺ X` and `P ≺ A` up) are in the original group.

### Consequences

- Good, because the analyst sees several good options, with the trade-offs between them.
- Good, because a move's band means the same thing in every case and at every point in a case.
- Good, because the cooperative move comes first: a harm-free move is in a higher band than a trade-off move, and a trade-off move that a harm-free move dominates is not top.
- Good, because no weight between vendors is chosen.
- Good, because a move that dominates a harm-free move is also harm-free, so the top harm-free moves are the best moves that harm no vendor.
- Good, because a move that raises an end desideratum and lowers none dominates every embargo-only move. A vendor's own fix or deployment is not an event in any other vendor's desiderata, so it lowers no end desideratum. Thus, given the choice between a fix and an embargo extension, the advice takes the fix.
- Bad, because the desiderata inside one vendor's scope are added with the rarity weights of ADR-0182. These weights measure how hard a desideratum is to meet by chance, not how much it matters.
- Bad, because with many vendors, most moves do not dominate each other, and layer 1 can be large.
- Bad, because the chance model cannot see that an active embargo protects the end desiderata: each step is equally likely, so an embargo does not make public awareness less likely (#6492). In #6450, a proposed revision of the embargo has a shift of zero for every vendor, so an extension is unhelpful.
- Bad, because the chance model cannot see real pressure to publish, for example after one vendor's fix is ready.
- Bad, because the sign test is strict: a very small shift can decide a band. In #6450, publication now rests on parts near 0.04 and an embargo end on its own terms on a part near 0.009, where the other deciding parts are near 1.5.
- Neutral, because the case cannot yet say which vendor depends on which, so move advice has no supply-chain order (#6501).
- Neutral, because a participant with no vendor path, such as a reporter, is not a scope until its desiderata have chance values (Epic #6461).
- Good, because a move that notifies a vendor raises that vendor's end part and no other part, so it is never unhelpful (P1 of #6450).

## Validation

The spike #6450 wrote the pathology cases as tests first, then ran the bands and the five aggregates against them ([Move Bands Against Pathology Cases](../topics/measuring_cvd/move_bands.md)).
The bands fail one case of one pathology: an embargo extension is unhelpful where it should be harm-free, because the chance model cannot see the embargo's protection (#6492).
Each aggregate fails at least four of the eight pathologies.
The spike changed rule 2, which now counts each group of equivalent desiderata once, and confirmed the strict sign test of rule 5.
A result that overturns a rule above changes this record.

## Pros and Cons of the Options

### One case score from an aggregate of the vendor scores

- Good, because one number ranks every move, so the page can lead with one move.
- Bad, because each aggregate has a case where it advises against the case as a whole, for example a mean that a new vendor pulls down.
- Bad, because one number cannot show a trade-off between vendors.

### Bands from each move's own outcome shifts, with dominance inside each band

- Good, because it chooses no weight between vendors.
- Good, because it gives options, not one answer.
- Good, because each band has a fixed meaning.
- Bad, because the bands are only as good as the scopes, and a participant with no scope is not seen.

### A fixed weight for each vendor

- Good, because one number ranks every move.
- Bad, because nothing in the research supports one set of weights, and each set decides an open question in silence.

## More Information

Decided by the maintainer in the planning interview for #6450 on 2026-11-13 and 2026-11-16.
Case scoring for each scope is #6457, the path-preference counts are #6459, chance values for path preferences are Epic #6461, an embargo's protection in the chance model is #6492, the objections to `V_i ≺ F_j` are #6502, and dependencies between participants are #6501.
The chance model and the desiderata are [ADR-0182](0182-cvd-measures-take-chance-from-the-smallest-model-holding-each-desideratum.md).
The shadow that shows the bands is [ADR-0190](0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md).

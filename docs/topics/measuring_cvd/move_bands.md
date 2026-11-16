---
stakeholder_type: [process-researcher]
level: 500
page_type: explanation
subject: neutral
description: >
  A spike that tests move bands, and five scalar aggregates, against pathology cases written first.
---

# Move Bands Against Pathology Cases

{% include-markdown "../../includes/not_normative.md" %}

This page records a spike for people who study the Coordinated Vulnerability Disclosure (CVD) process.
The spike tests the move bands of [ADR-0200](../../adr/0200-move-advice-puts-moves-in-bands-by-outcome-shift-not-by-one-case-score.md).
It also tests five scalar aggregates, which give one case score, against the same cases.
The method is new, so this page gives the method, the results, and the limits.

Read [Random Walks](random_walk.md) and [Desiderata from the Process Models](process_model_desiderata.md) first.
The chance model and the desiderata weights come from [ADR-0182](../../adr/0182-cvd-measures-take-chance-from-the-smallest-model-holding-each-desideratum.md).

---

## The method

### Scopes and outcome shifts

A **scope** is one vendor in the case, notified or not.
A vendor's scope holds the twelve original desiderata, the report-handling desiderata, and the embargo desiderata, for that vendor.
It does not hold $\evV_i \prec \evF_j$, which relates two vendors.
It does not hold $\evF_i \prec \evP$ either, because the original $\evF \prec \evP$ already holds it for the vendor.
Each group of equivalent desiderata counts once.
For example, $\evE \prec \evP$ stands for $\evE \prec \evX$ and $\evE \prec \evA$, because the three hold in the same histories.

The **chance value** of a desideratum is its expected outcome if the case is left to chance from where it stands.
The walk takes it in the smallest model that holds the desideratum, with the case projected onto that model for the vendor.
A desideratum whose scope the case never enters counts as met.

A move's **outcome shift** is the expected outcome after the move, minus the chance value.
Each scope has two parts:

- the end part, which adds the shifts of every desideratum except the embargo desiderata;
- the embargo part, which adds the shifts of the embargo desiderata.

Each desideratum has the weight $1 - f_d$, where $f_d$ is its chance frequency.

### Bands, layers, and marks

The end parts decide a move's band.
When every end part is zero, the embargo parts decide.
The sign test is strict.

- A **harm-free move** has a positive deciding part in at least one scope and a negative one in none.
- A **trade-off move** has a positive deciding part in at least one scope and a negative one in at least one.
- An **unhelpful move** has a positive deciding part in no scope.

Move X **dominates** move Y when the end parts of X are at least as good as those of Y in every scope, and better in one.
When all end parts are equal, the embargo parts decide in the same way.
A move's **layer** is its depth in the dominance order.
A **top move** is a harm-free or trade-off move in layer 1.
A coordinator's harm-free or trade-off move is **leading among yours** when no other coordinator move dominates it.

### The spike

The spike did these steps in this sequence:

1. It wrote eight pathology cases, P1 to P8, as tests.
2. It committed the tests before it scored any method.
3. It built synthetic joint states of two to four vendors, with mixed readiness, with and without an active embargo.
4. It put the open moves of each state in bands and layers.
5. It scored each move with five scalar aggregates.
6. It recorded the cases that each method fails.

The open moves are the allowed steps of the joint model, except a public exploit and observed attacks.
No participant chooses those two events.
The coordinator's moves are: notify a vendor, publish, and the embargo moves.

An aggregate gives each move one case score.
The score is the aggregate of the notified vendors' scores after the move, as a case score uses the vendors that have a case-state sequence.
A vendor's score is its chance value, with the end part and the embargo part added.
For an aggregate:

- a move is unhelpful when its score is not more than the case score before the move;
- the top moves have the highest score;
- one number shows no harm to a vendor.

The five aggregates are the median, the mean, the minimum (maximin), the mean then the smaller spread, and the product (Nash product).

---

## The cases

The vendors of each case are in this sequence: most advanced first.
A vendor is *unaware* (no report), *unready* (report accepted, no fix), *ready* (fix ready), or *deployed* (fix deployed).
Nothing is public in any case.

| Case | Vendors | Embargo |
|---|---|---|
| ready-unready | 2 | active, and none |
| unready-unready | 2 | active, and none |
| ready-unready-unaware | 3 | active, and none |
| deployed-ready-unready-unaware | 4 | active, and none |
| three coordinator moves | 2 (ready, unready) | active |

The last case shows only three moves: publication now, a proposed embargo revision, and an early end of the embargo.
In it, no move is harm-free.

---

## The pathologies

| Pathology | The advice must show this | For an aggregate |
|---|---|---|
| P1 | A move that notifies a vendor is never unhelpful. Its shift for that vendor is positive. | The same. |
| P2 | When no coordinator move raises an end part, an embargo extension is harm-free and publication now is unhelpful. When publication now raises a ready vendor's end part, it is a trade-off move below every harm-free move. | It does not put publication strictly first among the coordinator's moves. |
| P3 | Each negative shift shows on its move, with its vendor. | The same. |
| P4 | A move that dominates a harm-free move is harm-free. | It is not unhelpful and not below the move it dominates. |
| P5 | A move that ends an embargo early shows a negative shift for each vendor that it touches. | The same. |
| P6 | An unhelpful move gets no top mark and no "leading among yours" mark. The harm-free band can be empty. | The same. |
| P7 | A move that raises an end part and lowers none is above every move that changes only the embargo parts. | Its score is higher. |
| P8 | A trade-off move that a harm-free move dominates is not top. | The same. |

---

## Results

Each cell gives the number of cases that the method fails.
The last row gives the number of cases that give the pathology something to test, of nine.

| Method | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 |
|---|---|---|---|---|---|---|---|---|
| Bands | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Median | 4 | 0 | 9 | 2 | 5 | 2 | 4 | 0 |
| Mean | 4 | 0 | 9 | 2 | 5 | 2 | 4 | 0 |
| Maximin | 4 | 0 | 9 | 4 | 5 | 5 | 6 | 0 |
| Mean then spread | 4 | 0 | 9 | 2 | 5 | 2 | 4 | 0 |
| Nash product | 0 | 0 | 9 | 0 | 5 | 2 | 1 | 0 |
| Cases that test it | 4 | 5 | 9 | 4 | 5 | 9 | 8 | 4 |

The test `test/measure/advice/test_pathologies.py` records the failed cases by name.

### What the bands fail

The bands fail P2 in one case: unready-unready, with an active embargo.
There, the embargo extension is unhelpful, not harm-free.
A proposed revision of the embargo has a shift of zero for every vendor.
The chance model cannot see that an embargo protects the end desiderata (#6492).
Publication now is unhelpful in that case, as P2 requires.

### What the aggregates fail

- **P1.** The mean, the median, the mean then spread, and the maximin each mark a notice to a new vendor as unhelpful, in every case with an unaware vendor.
  The new vendor starts with a low score, so it pulls the aggregate down.
  The Nash product passes P1, because each new vendor's score is more than one.
- **P3 and P5.** One number names no vendor, so no aggregate shows which vendor a move harms.
- **P4 and P7.** Four aggregates put an embargo move above a move that notifies a vendor.
  The mean puts a notice below an early end of the embargo.
  The maximin puts an embargo proposal above a fix, because a fix for one vendor leaves the lowest vendor where it was.
- **P6.** Each aggregate marks a move with no effect as top or as leading among yours, when the other moves are worse than chance.
  The maximin marks a fix as unhelpful and still puts it top.

No method fails P8 in these cases.

---

## The size of the deciding shifts

The table gives the deciding parts of each kind of move, over all nine cases.
The largest deciding parts are near 2.

| Move | Band | Deciding parts |
|---|---|---|
| A vendor deploys its fix | harm-free | end, about 1.46 |
| A vendor's fix is ready | harm-free | end, about 1.86 |
| Notify a vendor | harm-free | end, about 1.45 |
| Propose an embargo | harm-free | embargo, 0.24 to 0.29 |
| Publication now, a ready vendor and no unaware vendor | trade-off | end, +0.040 and −0.042 |
| Publication now, with an unaware vendor | trade-off, top | end, +0.040, −0.042, and +0.46 for the unaware vendor |
| Publication now, no ready vendor | unhelpful | end, −0.042 |
| End the embargo on its own terms, a vendor with no fix | trade-off | embargo, +0.79 and −0.009 |
| End the embargo on its own terms, no vendor with a fix | unhelpful | embargo, −0.009 |
| End the embargo early | unhelpful | embargo, −0.007 to −0.20 |
| Propose an embargo revision | unhelpful | none: all zero |
| Defer or close a report | unhelpful | none: all zero |

Two moves have a deciding part of less than 0.05: publication now and an embargo end on its own terms.
Only these two moves change band under a threshold of 0.01 or 0.05.

- At 0.05, publication now becomes unhelpful when no vendor is unaware.
- At 0.05, publication now becomes harm-free when a vendor is unaware.
  The harm to the unready vendor then does not show.
- At 0.01, an embargo end on its own terms becomes harm-free when a vendor has no fix.

Thus a threshold hides a harm in each case where it changes a band.
The bands keep the strict sign test.

Publication now helps an unaware vendor when the chance model is the reference.
Public awareness makes that vendor aware at once, before any exploit or attack.
A notice raises the same vendor's end part more, by about 1.45, but publication now also gives a small gain to the ready vendor.
Thus neither move dominates the other, and both are top.

### Inside one scope

For a ready vendor, publication now adds a loss on $\evD \prec \evP$ and gains on $\evP \prec \evX$ and $\evP \prec \evA$.
The sum is +0.040.
The three desiderata are all in the original group.
Thus one scope for each vendor and desideratum group does not show this trade-off either.

### Equivalent desiderata

When each of $\evExOwn \prec \evP$, $\evExOwn \prec \evX$, and $\evExOwn \prec \evA$ counts, an embargo end on its own terms adds three times the same gain.
The gain then hides the loss on $\evF_i \prec \evExOwn$ for a vendor with no fix, and the move is harm-free in every case with an embargo.
When each group counts once, the move is a trade-off move with a vendor whose fix is ready, and unhelpful with none.
ADR-0200 now counts each group once.

---

## The depth of the layers

| Case | Layers |
|---|---|
| ready-unready, embargo | 3 |
| ready-unready, no embargo | 3 |
| unready-unready, embargo | 5 |
| unready-unready, no embargo | 4 |
| ready-unready-unaware, embargo | 3 |
| ready-unready-unaware, no embargo | 3 |
| deployed-ready-unready-unaware, embargo | 3 |
| deployed-ready-unready-unaware, no embargo | 3 |
| three coordinator moves | 2 |

Layer 1 holds each vendor's fix or deployment, each notice, and publication now when a vendor is unaware.
The moves with a shift of zero share one layer, because they do not dominate each other.

---

## Limits

- The chance model cannot see that an embargo protects the end desiderata (#6492).
  An embargo extension has no effect, and an embargo end changes only the embargo parts.
- The chance model cannot see real pressure to publish, for example after one vendor's fix is ready.
- The case has no supply-chain order (#6501), so the advice cannot say which vendor's fix the others need.
- The joint model lets the embargo end on its own terms at any time.
  It does not know the end date or the fix status that the terms name.
- The cases are synthetic, and none is public yet.
  No recorded case was tested.
- The desiderata weights measure how hard a desideratum is to meet by chance, not how much it matters.

---

## How to run the spike

The bands are in `vultron/measure/advice/`.
The cases, the pathologies, and the aggregates are in `test/measure/advice/`.
Run `uv run pytest test/measure/advice` to run the spike.

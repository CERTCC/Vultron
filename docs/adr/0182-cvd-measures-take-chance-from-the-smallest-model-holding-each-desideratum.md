---
status: proposed
date: 2026-11-06
created: 2026-11-06
updated: 2026-11-10
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; Epic #5068; Ideas #5072, #5143, #5828, #5142; ADR-0174;
  docs/topics/measuring_cvd/ (random walk, reasoning over histories, benchmarking
  MPCVD, open questions, process model desiderata, reward functions)
informed: []
stakeholder_type: [project-contributor]
---

# CVD Measures Take Chance From the Smallest Model That Holds Each Desideratum

## Context and Problem Statement

The skill coefficient ($\alpha_d$) compares how often a case meets a desideratum with how often chance would meet it ($f_d$).
For the twelve original desiderata, $f_d$ comes from a random walk over the six-event case-state model under the principle of indifference: at each step, every event allowed next is equally likely.

The extended desiderata (Idea #5072) use events from the report management, embargo management and embargo consent models as well, and several of them name individual vendors.
Three further questions need a chance model too:

- **Incomplete sequences** (Idea #5828): a real case's sequence is almost always incomplete, and the existing scorer refuses it.
- **Multi-party cases** (Idea #5143): the public-awareness, exploit and attack events are shared by every participant, so per-vendor histories are not independent.
- **Path preferences** (Idea #5142): short embargoes and answered invitations need a score over a whole history.

A walk over a whole multi-party case does not scale.
Its state space grows combinatorially with the number of participants, and a case can have hundreds of vendors.
Its baselines also change with that number: with more vendor events to pick from at each step, a shared event is picked later by chance, so "vendor $i$ is aware before public awareness" becomes likelier by chance as vendors are added.
Every baseline would then be a function of the participant count, and every comparison would need recomputation.

The question: **what chance model do CVD measures use, so that a baseline is computable, comparable across cases, and independent of how many participants a case has?**

## Decision Drivers

- A baseline must be computable exactly, without a simulated walk that may not converge.
- A baseline must not depend on the number of participants, so one table serves every case.
- The new measures stay comparable with the twelve original desiderata.
- Simple measures over elaborate ones: a measure a reader can recompute by hand beats one that needs a research project to scale.
- The measures stay research material, not normative requirements (Epic #5068).

## Considered Options

- One indifference walk, applied to the smallest model that holds each desideratum's events.
- One indifference walk over the whole case, with baselines tabulated by participant count or approximated for large cases.
- Different chance models for the new pieces: equally likely completions, or protocol acts weighted apart from outside events.

## Decision Outcome

Chosen option: "One indifference walk, applied to the smallest model that holds each desideratum's events", because it is the only option whose baselines are exact, fixed and independent of the participant count, and it keeps the meaning of the original skill coefficient.

1. **One chance model.**
   Every CVD measure takes chance from the indifference walk: at each step, every event allowed next is equally likely, under the rules that link the models (for example, public awareness ends an active embargo, and a fix needs the vendor's report accepted).
2. **The smallest model that holds the desideratum.**
   A desideratum's baseline comes from the smallest model that contains its events.
   A per-vendor desideratum uses one vendor with the case's shared events, and the embargo where it matters.
   A desideratum that relates two vendors uses two vendors.
   A desideratum that must hold for every vendor is checked per vendor, each against the one-vendor baseline, and summarized across vendors.
   These models are small enough to compute exactly, so the baselines form one fixed table.
3. **An incomplete sequence is scored through its completions.**
   Its valid completions are weighted by the probability the same walk gives them from where the case stands.
   The case reports the expected score over those completions, and the best and worst score it can still reach.
   A sequence the event-history layer derived from a ledger with holes never reaches the scorer, because that layer refuses it (ADR-0174).
4. **A multi-party case reports per-vendor scores.**
   The case reports each vendor's score, and their unweighted median and spread.
   The spread is read as how evenly the case served its vendors, not as a statistical sample, because the vendors share events.
   It measures evenness across vendors, not across users: weighting by users or risk stays an open question.
   A two-party case reduces to its one vendor's score.
   A participant with no vendor path is out of scope until it has measures of its own.
5. **Path preferences are simple counts.**
   A preference about the shape of a history is a per-participant count or ratio read from the event history, such as invitations answered before their deadline out of those received.
   A preference about an embargo is a count or ratio for the case, because the embargo belongs to the case, such as the number of embargo revisions.
   No combined reward function is defined.

### Consequences

- Good, because one baseline table serves a case of 2 vendors and a case of 200, with no recomputation.
- Good, because every baseline is exact, so no result depends on how long a simulation ran.
- Good, because the original twelve desiderata keep their meaning, so old and new scores compare.
- Good, because an incomplete case gets a score and a range, instead of a refusal.
- Bad, because skill is measured against "a one-vendor case handled by chance", not against a chance version of this particular case. The pages that report a score must say so.
- Bad, because the unweighted median and spread can mislead when a few vendors carry most of the risk; the measure does not answer the weighting question.
- Neutral, because a participant with no vendor path gets no score, as ADR-0174 already records.

## Validation

The decision is confirmed when the baseline table for the extended desiderata is computed exactly from the small models and published on the desiderata page, and when the incomplete-sequence scorer reports expected, best and worst scores from the same walk.

## Pros and Cons of the Options

### One indifference walk, applied to the smallest model that holds each desideratum's events

- Good, because baselines are exact, fixed and independent of the participant count.
- Bad, because the chance baseline is a one-vendor baseline, not one for the case at hand.

### One indifference walk over the whole case

- Good, because the baseline is chance for this case, with all of its participants.
- Bad, because the state space grows combinatorially with the participant count, and a walk over hundreds of vendors may not converge.
- Bad, because every baseline becomes a function of the participant count, so comparisons need recomputation.

### Different chance models for the new pieces

- Good, because a model that treats protocol acts as choices may fit real cases better.
- Bad, because it breaks comparability with the twelve original desiderata, and each new model needs its own justification and, for frequency weights, a corpus the project does not have.

## More Information

The event-history layer that feeds these measures, and its refusal of a ledger with holes, are [ADR-0174](0174-cvd-measures-read-a-case-ledger-through-a-read-only-event-history.md).
The weighting question, and the example of a case that protects most users while failing an unweighted test, are on the Measuring CVD [Open Questions](../topics/measuring_cvd/open_questions.md) page.

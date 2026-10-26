---
description: >
  Score your own program's closed cases against the chance baseline from the
  Measuring CVD research, and read the result as a skill indicator you can act on.
stakeholder_type: [cvd-practitioner]
level: 300
page_type: how-to
---

# How to Measure Your CVD Program

{% include-markdown "../includes/not_normative.md" %}

This guide shows you how to score the cases your Coordinated Vulnerability Disclosure (CVD) program has handled against the outcomes a case is meant to reach.
The score is the skill coefficient that the [Measuring CVD Foundations](../topics/measuring_cvd/foundations/index.md) derive, applied without the derivation.
It is for whoever owns a disclosure program, a product security team's intake, or a coordination practice, and it needs only the dates you already record for each case.
The result tells you which outcomes your program achieves more often than chance would, and which coordination decisions to change when it does not.

---

## Prerequisites

- You know the six events in a case and the twelve ordering preferences over them, as stated on [What Does *Success* Mean in CVD?](../topics/background/cvd_success.md).
- You have a record of closed or long-running cases with dates for at least some of those events.
- You can compute a ratio and a difference in a spreadsheet.

The six events, with the symbol the rest of this guide uses for each, are Vendor Awareness ($\evV$), Fix Ready ($\evF$), Fix Deployed ($\evD$), Public Awareness ($\evP$), Exploit Public ($\evX$), and Attacks Observed ($\evA$).
The [Case State (CS) model](../topics/process_models/cs/index.md) defines these six events.
The notation $a \prec b$ means that event $a$ occurs before event $b$.
Hover over a symbol to see the name of its event.

---

## Step 1: Choose the orderings you can observe

Pick the ordering preferences whose two events your records date.
The table below lists the twelve preferences and the records each one needs.

| Preference | Needs dates for | Usually available to |
|---|---|---|
| Vendor Awareness before Public Awareness ($\evV \prec \evP$) | Vendor notification, publication | Coordinators, Reporters |
| Vendor Awareness before Exploit Public ($\evV \prec \evX$) | Vendor notification, first public exploit | Coordinators, Reporters |
| Vendor Awareness before Attacks Observed ($\evV \prec \evA$) | Vendor notification, first observed attack | Coordinators, Reporters |
| Fix Ready before Public Awareness ($\evF \prec \evP$) | Fix ready, publication | Vendors, Coordinators |
| Fix Ready before Exploit Public ($\evF \prec \evX$) | Fix ready, first public exploit | Vendors, Coordinators |
| Fix Ready before Attacks Observed ($\evF \prec \evA$) | Fix ready, first observed attack | Vendors, Coordinators |
| Fix Deployed before Public Awareness ($\evD \prec \evP$) | Fix deployed, publication | Deployers, and Vendors that deploy their own fixes |
| Fix Deployed before Exploit Public ($\evD \prec \evX$) | Fix deployed, first public exploit | Deployers, and Vendors that deploy their own fixes |
| Fix Deployed before Attacks Observed ($\evD \prec \evA$) | Fix deployed, first observed attack | Deployers, and Vendors that deploy their own fixes |
| Public Awareness before Exploit Public ($\evP \prec \evX$) | Publication, first public exploit | Anyone who tracks exploit publication |
| Public Awareness before Attacks Observed ($\evP \prec \evA$) | Publication, first observed attack | Anyone who tracks attacks |
| Exploit Public before Attacks Observed ($\evX \prec \evA$) | First public exploit, first observed attack | Anyone who tracks both |

If you are a Vendor, start with $\evF \prec \evP$ and $\evF \prec \evA$.
Those two are what the [published proof of concept](../topics/measuring_cvd/observing_skill.md) measured for Microsoft, so you have a comparison.
If you are a Coordinator, add the three $\evV$ preferences, because notifying Vendors is the event you cause.
If your program does not deploy fixes, and no Deployer in your cases reports deployment, leave out the preferences with $\evD$.
The reason is that only the Deployer usually knows the date of a deployment.

---

## Step 2: Record the event order for each case

For each case, record the date of each event you chose, or mark the event as not yet observed.
Then, for each preference **a** $\prec$ **b**, record whether **a** happened before **b** in that case.

Apply two rules when you record:

- An event that has not been observed counts as later than every event that has.
  A case with a fix ready and no public exploit satisfies $\evF \prec \evX$.
- If the two events happened on the same day and you cannot order them, exclude that case from that preference rather than guess.

!!! info "If your cases run on Vultron"

    A Vultron case already records the dates of these events.
    The case ledger stamps every change to the case ([What a Case Records](../topics/measuring_cvd/what_a_case_records.md)).
    These changes include the fix and deployment of each participant, and the public awareness, exploit, and attack status of the case.
    Read the date of each event from its ledger entry, not from a separate record.
    For some events, the ledger stamp is later than the event, and What a Case Records lists these events.
    Treat the dates of these events as approximate.

Re-score a case when a later event arrives.
A case that satisfied $\evF \prec \evA$ when it closed stops satisfying it if an attack is observed later, so the score of a program is a moving figure and not a closing report.

---

## Step 3: Compute the observed frequency

For each preference, divide the number of cases in which it held by the number of cases you scored for it.
Call the result $f_d^{obs}$, the observed frequency of preference $d$.

If you scored 40 cases for $\evF \prec \evP$ and the fix was ready before publication in 36 of them, then $f_{\evF \prec \evP}^{obs} = 36 / 40 = 0.90$.

---

## Step 4: Look up the chance baseline

The research computes how often each preference would hold if every allowed next event in a case were equally likely, with no coordination at all.
That figure, $f_d$, is the baseline your observation is compared against.
Read it from the table below at the row of the first event and the column of the second.

{% include-markdown "../includes/tab_exp_freq.md" %}

For $\evF \prec \evP$ the baseline is 0.111: a fix would be ready before publication in about one uncoordinated case in nine.
[Reasoning over Possible Histories](../topics/measuring_cvd/reasoning_over_histories.md) shows where the numbers come from.

---

## Step 5: Compute the skill coefficient

For each preference, compute

$$
\alpha_d = \frac{f_d^{obs} - f_d}{1 - f_d}
$$

The coefficient $\alpha_d$ is the share of your observed success that chance does not explain.
It is 1 when the preference holds in every case, 0 when it holds exactly as often as chance predicts, and negative when it holds less often than chance.

Continuing the example, $\alpha_{\evF \prec \evP} = (0.90 - 0.111) / (1 - 0.111) = 0.89$.

---

## Step 6: Read the result

Use the following reading of $\alpha_d$, which follows [Benchmarking CVD](../topics/measuring_cvd/benchmarking.md).

| $\alpha_d$ | Reading |
|---|---|
| Above 0.9 | The program reliably achieves this ordering; the research treats this as a clear indicator of skill |
| Between 0 and 0.9 | Better than chance; compare against your own earlier periods and against sector observations |
| Near 0 | Absence of evidence rather than evidence of absence, especially with fewer than a few dozen cases |
| Below 0 | The ordering holds less often than an uncoordinated process would produce; look for a structural cause |

Two sector figures give you something to compare against.
From published exploit and attack data, the research derives benchmarks of about 0.94 for $\evD \prec \evA$ and about 0.81 for $\evD \prec \evX$, and a program at or above them is doing as well as the ecosystem at large.
Track each $\alpha_d$ over time, both per period and cumulatively, as [Observing CVD in the Wild](../topics/measuring_cvd/observing_skill.md) does, because a single period with few cases swings widely.

---

## Step 7: Act on a low score

Each preference is protected by a coordination decision, so a low $\alpha_d$ points at a decision to revisit.
[What Does *Success* Mean in CVD?](../topics/background/cvd_success.md#acting-on-the-preferences-in-a-case) explains why each pairing holds.

| Low score on | Decision to revisit |
|---|---|
| $\evV \prec \evP$, $\evV \prec \evX$, $\evV \prec \evA$ | Notify Vendors earlier, and notify the upstream Vendors whose components the affected products contain |
| $\evF \prec \evP$, $\evD \prec \evP$ | Propose an embargo at case creation, and hold publication until the fix is ready; see [Embargo Principles](../topics/process_models/em/principles.md) |
| $\evF \prec \evX$, $\evF \prec \evA$, $\evD \prec \evX$, $\evD \prec \evA$ | Shorten the time from Vendor Awareness to Fix Ready; an embargo cannot protect these, because adversaries are not bound by it |
| $\evP \prec \evX$, $\evP \prec \evA$ | Publish when exit criteria are met instead of waiting for every Vendor; see [Early Termination](../topics/process_models/em/early_termination.md) |

For a case still in progress, the [Recommended Action Rules for CVD](../topics/other_uses/action_rules.md) list what each role can do from the case's current state and which event the action causes.

---

## If you coordinate multi-vendor cases

A case with more than one affected Vendor is a Multi-Party Coordinated Vulnerability Disclosure (MPCVD) case.
Score the $\evV$ and $\evF$ preferences once for each affected Vendor, because each Vendor has its own fix path.
Score the $\evD$ preferences once for each Deployer, because each Deployer has its own deployment.
Compare each Vendor score and each Deployer score against the one $\evP$, $\evX$, and $\evA$ of the case.
All participants in the case share the same $\evP$, $\evX$, and $\evA$.
Do not link a Deployer to one Vendor, unless your records show which fix the Deployer deployed.
A Vultron case does not record this link.
Then report the median $\alpha_d$ across the Vendors and the spread of the Vendor scores.
Also report the median $\alpha_d$ across the Deployers and the spread of the Deployer scores.
A high median with a low spread means most Vendors in your cases reached acceptable outcomes.
A high median with a wide spread means a few Vendors are being left behind, which is the fairness problem [Measuring and Benchmarking MPCVD](../topics/measuring_cvd/benchmarking_mpcvd.md) discusses.

---

## What the score does not tell you

- It measures the order of events, not the time between them.
  A fix ready one day before publication and one year before publication score the same.
  [Timing Metrics Within a Case](../topics/measuring_cvd/timing_metrics.md) proposes measures of the time between events.
- The baseline assumes every allowed transition is equally likely.
  Real-world event probabilities depend on history, so treat $\alpha_d$ as a comparison against a stated baseline and not as a probability.
- It does not distinguish your program's skill from your Reporters' skill, your Vendors' skill, or an adversary's inattention.
  The research folds all of these into one word, "skill", on purpose.

---

## Further reading

- [Measuring CVD Foundations](../topics/measuring_cvd/foundations/index.md) — the derivation behind every number in this guide.
- [Discriminating Skill and Luck in Observations](../topics/measuring_cvd/discriminating_skill_and_luck.md) — the skill coefficient and the model that yields it.
- [Benchmarking CVD](../topics/measuring_cvd/benchmarking.md) — why zero is a low bar, and how sector observations become benchmarks.
- [CVD Roles and Their Influence](../topics/other_uses/roles_influence.md) — how vendors, system owners, coordinators, and governments rank the preferences differently.

!!! tip "Going further"

    The score in this guide uses the six events and twelve preferences of the original research.
    [Desiderata from the Process Models](../topics/measuring_cvd/process_model_desiderata.md) proposes more preferences, about report handling, embargoes, and joining.
    [Timing Metrics Within a Case](../topics/measuring_cvd/timing_metrics.md) proposes measures of the intervals between events.
    Both pages are draft research, and neither page has a published baseline yet.

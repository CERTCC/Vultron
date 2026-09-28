---
description: >
  Score your own program's closed cases against the chance baseline from the
  Measuring CVD research, and read the result as a skill indicator you can act on.
stakeholder_type: [cvd-practitioner]
level: 300
---

# How to Measure Your CVD Program

{% include-markdown "../includes/not_normative.md" %}

This guide shows you how to score the cases your Coordinated Vulnerability Disclosure (CVD) program has handled against the outcomes a case is meant to reach.
The score is the skill coefficient that the [Measuring CVD](../topics/measuring_cvd/index.md) research derives, applied without the derivation.
It is for whoever owns a disclosure program, a product security team's intake, or a coordination practice, and it needs only the dates you already record for each case.
The result tells you which outcomes your program achieves more often than chance would, and which coordination decisions to change when it does not.

---

## Prerequisites

- You know the six events in a case and the twelve ordering preferences over them, as stated on [What Does *Success* Mean in CVD?](../topics/background/cvd_success.md).
- You have a record of closed or long-running cases with dates for at least some of those events.
- You can compute a ratio and a difference in a spreadsheet.

The six events, with the letter the rest of this guide uses for each, are Vendor Awareness (**V**), Fix Ready (**F**), Fix Deployed (**D**), Public Awareness (**P**), Exploit Public (**X**), and Attacks Observed (**A**).
The [Case State (CS) model](../topics/process_models/cs/index.md) defines them.

---

## Step 1: Choose the orderings you can observe

Pick the ordering preferences whose two events your records date.
The table below lists the twelve preferences and the records each one needs.

| Preference | Needs dates for | Usually available to |
|---|---|---|
| **V** $\prec$ **P** | Vendor notification, publication | Coordinators, Reporters |
| **V** $\prec$ **X** | Vendor notification, first public exploit | Coordinators, Reporters |
| **V** $\prec$ **A** | Vendor notification, first observed attack | Coordinators, Reporters |
| **F** $\prec$ **P** | Fix ready, publication | Vendors, Coordinators |
| **F** $\prec$ **X** | Fix ready, first public exploit | Vendors, Coordinators |
| **F** $\prec$ **A** | Fix ready, first observed attack | Vendors, Coordinators |
| **D** $\prec$ **P** | Fix deployed, publication | Vendors that deploy their own fixes |
| **D** $\prec$ **X** | Fix deployed, first public exploit | Vendors that deploy their own fixes |
| **D** $\prec$ **A** | Fix deployed, first observed attack | Vendors that deploy their own fixes |
| **P** $\prec$ **X** | Publication, first public exploit | Anyone who tracks exploit publication |
| **P** $\prec$ **A** | Publication, first observed attack | Anyone who tracks attacks |
| **X** $\prec$ **A** | First public exploit, first observed attack | Anyone who tracks both |

If you are a Vendor, start with **F** $\prec$ **P** and **F** $\prec$ **A**.
Those two are what the [published proof of concept](../topics/measuring_cvd/observing_skill.md) measured for Microsoft, so you have a comparison.
If you are a Coordinator, add the three **V** preferences, because notifying Vendors is the event you cause.
Leave out any preference involving **D** unless your program deploys fixes itself, because the date a Deployer applied a fix is rarely known to anyone else.

---

## Step 2: Record the event order for each case

For each case, record the date of each event you chose, or mark the event as not yet observed.
Then, for each preference **a** $\prec$ **b**, record whether **a** happened before **b** in that case.

Apply two rules when you record:

- An event that has not been observed counts as later than every event that has.
  A case with a fix ready and no public exploit satisfies **F** $\prec$ **X**.
- If the two events happened on the same day and you cannot order them, exclude that case from that preference rather than guess.

Re-score a case when a later event arrives.
A case that satisfied **F** $\prec$ **A** when it closed stops satisfying it if an attack is observed later, so the score of a program is a moving figure and not a closing report.

---

## Step 3: Compute the observed frequency

For each preference, divide the number of cases in which it held by the number of cases you scored for it.
Call the result $f_d^{obs}$, the observed frequency of preference $d$.

If you scored 40 cases for **F** $\prec$ **P** and the fix was ready before publication in 36 of them, then $f_{\mathbf{F} \prec \mathbf{P}}^{obs} = 36 / 40 = 0.90$.

---

## Step 4: Look up the chance baseline

The research computes how often each preference would hold if every allowed next event in a case were equally likely, with no coordination at all.
That figure, $f_d$, is the baseline your observation is compared against.
Read it from the table below at the row of the first event and the column of the second.

{% include-markdown "../includes/tab_exp_freq.md" %}

For **F** $\prec$ **P** the baseline is 0.111: a fix would be ready before publication in about one uncoordinated case in nine.
[Reasoning over Possible Histories](../topics/measuring_cvd/reasoning_over_histories.md) shows where the numbers come from.

---

## Step 5: Compute the skill coefficient

For each preference, compute

$$
\alpha_d = \frac{f_d^{obs} - f_d}{1 - f_d}
$$

The coefficient $\alpha_d$ is the share of your observed success that chance does not explain.
It is 1 when the preference holds in every case, 0 when it holds exactly as often as chance predicts, and negative when it holds less often than chance.

Continuing the example, $\alpha_{\mathbf{F} \prec \mathbf{P}} = (0.90 - 0.111) / (1 - 0.111) = 0.89$.

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
From published exploit and attack data, the research derives benchmarks of about 0.94 for **D** $\prec$ **A** and about 0.81 for **D** $\prec$ **X**, and a program at or above them is doing as well as the ecosystem at large.
Track each $\alpha_d$ over time, both per period and cumulatively, as [Observing CVD in the Wild](../topics/measuring_cvd/observing_skill.md) does, because a single period with few cases swings widely.

---

## Step 7: Act on a low score

Each preference is protected by a coordination decision, so a low $\alpha_d$ points at a decision to revisit.
[What Does *Success* Mean in CVD?](../topics/background/cvd_success.md#acting-on-the-preferences-in-a-case) explains why each pairing holds.

| Low score on | Decision to revisit |
|---|---|
| **V** $\prec$ **P**, **V** $\prec$ **X**, **V** $\prec$ **A** | Notify Vendors earlier, and notify the upstream Vendors whose components the affected products contain |
| **F** $\prec$ **P**, **D** $\prec$ **P** | Propose an embargo at case creation, and hold publication until the fix is ready; see [Embargo Principles](../topics/process_models/em/principles.md) |
| **F** $\prec$ **X**, **F** $\prec$ **A**, **D** $\prec$ **X**, **D** $\prec$ **A** | Shorten the time from Vendor Awareness to Fix Ready; an embargo cannot protect these, because adversaries are not bound by it |
| **P** $\prec$ **X**, **P** $\prec$ **A** | Publish when exit criteria are met instead of waiting for every Vendor; see [Early Termination](../topics/process_models/em/early_termination.md) |

For a case still in progress, the [Recommended Action Rules for CVD](../topics/other_uses/action_rules.md) list what each role can do from the case's current state and which event the action causes.

---

## If you coordinate multi-vendor cases

A case with more than one affected Vendor is a Multi-Party Coordinated Vulnerability Disclosure (MPCVD) case.
Score each affected Vendor and product in it as its own case, because each has its own fix path.
Then report the median $\alpha_d$ across them together with its spread.
A high median with a low spread means most Vendors in your cases reached acceptable outcomes.
A high median with a wide spread means a few Vendors are being left behind, which is the fairness problem [Measuring and Benchmarking MPCVD](../topics/measuring_cvd/benchmarking_mpcvd.md) discusses.

---

## What the score does not tell you

- It measures the order of events, not the time between them.
  A fix ready one day before publication and one year before publication score the same.
- The baseline assumes every allowed transition is equally likely.
  Real-world event probabilities depend on history, so treat $\alpha_d$ as a comparison against a stated baseline and not as a probability.
- It does not distinguish your program's skill from your Reporters' skill, your Vendors' skill, or an adversary's inattention.
  The research folds all of these into one word, "skill", on purpose.

---

## Further reading

- [Measuring CVD](../topics/measuring_cvd/index.md) — the derivation behind every number in this guide.
- [Discriminating Skill and Luck in Observations](../topics/measuring_cvd/discriminating_skill_and_luck.md) — the skill coefficient and the model that yields it.
- [Benchmarking CVD](../topics/measuring_cvd/benchmarking.md) — why zero is a low bar, and how sector observations become benchmarks.
- [CVD Roles and Their Influence](../topics/other_uses/roles_influence.md) — how vendors, system owners, coordinators, and governments rank the preferences differently.

---
stakeholder_type: [process-researcher]
level: 500
page_type: explanation
subject: neutral
description: >
  Path preferences as simple counts and ratios read from a case's event history, the 2022 reward-function criteria they come from, and the simulation work they would enable.
---

# Reward Functions

{% include-markdown "../../includes/not_normative.md" %}

In a Coordinated Vulnerability Disclosure (CVD) case, a path preference is a preference about the shape of the case history, not about the order of two events.
For example, a participant should answer an embargo invitation, and an embargo should not be revised many times.
[Desiderata from the Process Models](./process_model_desiderata.md#preferences-about-the-path) lists four path preferences.
This page defines a measure for each of them.

Each measure is a simple count or ratio that a reader can compute from the event history of one case.
The event history is the list of events that the case ledger records, in the order that the CASE_MANAGER admitted them ([What a Case Records](./what_a_case_records.md)).
A measure of a participant's own acts is a count or ratio for each participant.
A measure of an embargo is a count or ratio for the case, because the embargo belongs to the case.

This page defines no combined reward function ([ADR-0182](../../adr/0182-cvd-measures-take-chance-from-the-smallest-model-holding-each-desideratum.md)).
Each count or ratio stays separate, so a reader can see which preference a case met and which it did not.

The page uses the events and symbols of [What a Case Records](./what_a_case_records.md).
The table below repeats these events:

{% include-markdown "./_case_events.md" %}

---

## The path preferences

The table below gives each path preference, its measure, and the events that the measure reads.

| Preference | Measure | For | Events it reads |
|---|---|---|---|
| A participant answers an embargo invitation before its RSVP deadline | Invitations answered before they time out, out of those invitations and the invitations that time out at their RSVP deadline, not counting the invitations that the case's close times out before their deadline | Each participant | The embargo `Invite(EmbargoEvent)`, the participant's `Accept` or `Reject`, the CASE_MANAGER's `Update(EmbargoConsent)`, and the case-close entry |
| A case revises its embargo few times | The number of embargo revisions that the Case Owner activates | The case | The revision proposal's `Invite(EmbargoEvent)` and the Case Owner's `Add(EmbargoEvent)` that activates it |
| An embargo is as short as the fixes allow | The embargo duration, divided by the time until the last vendor's fix is ready | The case | Embargo start ($\evE$), embargo exit ($\evEx$), and fix readiness ($\evF_i$) of each vendor |
| A report is judged correctly | Correct validation decisions out of the decisions whose correctness is known | Each participant | Report validation ($\evVa_i$), the participant's status update to Invalid, and fix readiness ($\evF_i$) |

### Invitations answered before their deadline

An embargo Invite asks a participant to agree to an embargo, and carries an [RSVP deadline](./what_a_case_records.md#clock-decisions-are-stamped-when-the-case_manager-next-acts).
A participant that does not answer by the deadline gives a pocket veto: the invitation times out, and the participant is not a signatory.

The Participant Embargo Consent (PEC) model gives each participant one consent row for each embargo in the embargo register.
An invitation moves the row to `INVITED`.
An answer, an `Accept` or a `Reject` of the Invite, moves the row to `AGREED` or `DECLINED`.
An invitation that passes its RSVP deadline without an answer moves the row to `TIMED_OUT`, in an `Update(EmbargoConsent)` entry of the CASE_MANAGER (CM-28-015).
A row can be invited again after it times out, when a late `Accept` names an embargo that is no longer available (EMB-17-003).
Thus one row can hold more than one invitation.

The measure counts invitations in the event history, not rows at their last status.
The last status of a row is not enough, because a late answer still changes the row.
A late `Accept` moves a `TIMED_OUT` row to `AGREED` when the embargo is still available.

An invitation is answered before its deadline when the participant's answer comes before any timeout of that invitation in the ledger.
The CASE_MANAGER times out each overdue invitation before it processes any other embargo activity for the case, including the late answer itself (CM-28-015, CM-28-028).
Thus a late answer always comes after the `Update(EmbargoConsent)` that timed out its invitation.
A participant can change its answer, and the ledger records each changed answer (CM-13-005).
The measure counts each invitation once, by its first answer.

For participant $i$, the measure is:

$$
\frac{\text{invitations to } i \text{ answered before a timeout}}
     {\text{invitations to } i \text{ answered before a timeout, or timed out at their deadline}}
$$

The ratio does not count the invitations that the case's close timed out.
When the Case Owner closes the case, the CASE_MANAGER times out every invitation that still waits for an answer, without waiting for its RSVP deadline (CM-23-014).
These `Update(EmbargoConsent)` entries come after the case-close entry in the ledger.
Some of these invitations were already past their RSVP deadline, because the CASE_MANAGER times out an invitation only when it next reads the consent rows (CM-28-007).
Thus the measure compares the RSVP deadline of each invitation with the commit stamp of the case-close entry.
An invitation whose deadline is before the close counts as a deadline timeout.
An invitation whose deadline is after the close is not counted, because the participant still had time to answer it.

The ratio also does not count an invitation that stays at `INVITED` because its embargo was rejected, canceled, replaced, or ended before the participant answered.
That participant had no invitation left to answer.

The ratio does not count a Stub Invite to the case.
Its acceptance both joins the case and agrees to an active embargo (CM-11-001), but a case Invite carries no RSVP deadline (CM-23-014).
Thus a Stub Invite can never time out at a deadline, and counting it would only raise the ratio.

A participant with no counted invitations has no ratio.

### Embargo revisions

A revision is a proposal to change the embargo in force, for example to move its end time.
The CASE_MANAGER commits each revision proposal as a ledger entry (EP-09-001).
The participants answer the revision, but their answers are only their own consent.
The Case Owner decides the revision: its `Add(EmbargoEvent)` activates the revision, and the activated revision replaces the embargo in force (EP-09-005).

For the case, the measure is the number of the Case Owner's `Add(EmbargoEvent)` entries that activate a revision while an embargo is in force.
The revision proposals that the Case Owner did not activate are a second, separate count.
Each activation names the proposal that it activates, and the proposal entry names the participant that proposed it.
Thus the count can also be split by the proposing participant.
A relayed copy of a proposal, or a fresh Invite after a late `Accept` (EMB-17-003), is not a new proposal, so the split uses the proposal entry, not every `Invite(EmbargoEvent)`.

A case usually starts with a default embargo ([Default Embargoes](../process_models/em/defaults.md)).
Then the first negotiated embargo is itself a revision, because it replaces the default embargo.
That replacement is the normal path, not churn, so the measure reports it separately and counts the revisions after it.

A low count is the preference.
A count of zero does not mean the case did well, because a case can need a revision to give a trailing vendor more time (VP-14-009).
Thus a reader compares the count with the embargo-duration ratio below.

### Embargo duration against the time until the last fix

An embargo exists to give vendors time to make their fixes ready.
An embargo that lasts much longer than the fixes need delays public awareness for no gain.
An embargo that ends before every vendor's fix is ready leaves a trailing vendor without a fix.

For the case, the measure is:

$$
\frac{t(\evEx) - t(\evE)}{\max_i t(\evF_i) - t(\evE)}
$$

The numerator is the embargo duration: the time from the embargo start to the embargo exit, across every revision.
The denominator is the time from the embargo start until the last vendor's fix is ready.
The denominator uses every vendor with a fix ready, including a vendor that first decided the report was Invalid.

A ratio near 1 is the preference.
A ratio above 1 shows an embargo that lasted longer than the last fix needed.
A ratio below 1 shows an embargo that ended before the last fix was ready.
When the embargo ended on its own terms ($\evExOwn$), the embargo desideratum $\evF_i \prec \evExOwn$ counts each trailing vendor in that case ([Desiderata from the Process Models](./process_model_desiderata.md#every-vendors-fix-before-the-embargo-ends-on-its-own-terms)).

Each time comes from the commit stamp of the ledger entry for the event, with one exception.
For an embargo that ended because its end time was reached (`END_TIME_REACHED`), the end time on the embargo is the actual end, and the commit stamp is only the latest possible end ([What a Case Records](./what_a_case_records.md#clock-decisions-are-stamped-when-the-case_manager-next-acts)).

The ratio is not defined in four conditions:

- The case had no embargo.
- The embargo has not ended yet.
- Every fix was ready before the embargo started, so the denominator is not above zero.
- The case is still open, and a vendor whose report reaches Valid has no fix ready yet.

After the case closes, a vendor whose report reached Valid and that has no fix is a vendor without a fix.
The measure reports each such vendor beside the ratio, and computes the ratio over the vendors with a fix.

### Validation correctness where known

A real vul should reach Valid, and a bogus report should reach Invalid.
The case does not record which vendors the vul affects.
Thus the correctness of a validation decision is known only for some decisions.

The event history shows the correctness of some decisions by itself.
Usually a vendor decides that the report is Valid, accepts it, and later has a fix ready.
That fix readiness shows that the Valid decision was correct.
A vendor can also decide that the report is Invalid, close the report, and later have a fix ready.
The protocol permits this history, because a vendor can report fix readiness from RM Closed as well as from Accepted or Deferred (CSB-18-001).
The fix readiness ($\evF_i$) shows that the vul was real for that vendor, so the Invalid decision was wrong.
Fix readiness is a vendor event, so the ledger alone shows correctness only for vendors.

Other decisions need a judgment from outside the ledger, for example a quorum of participants that agree a vendor's products are affected, or a later public advisory.
A measure counts these decisions only when such a judgment is available, and names its source.

For participant $i$, the measure is:

$$
\frac{\text{decisions of } i \text{ known to be correct}}{\text{decisions of } i \text{ whose correctness is known}}
$$

A participant with no decision of known correctness has no ratio.

---

## Historical foundation: reward functions over RM and EM histories

The preferences above come from criteria for reward functions in the 2022 Vultron technical reports.
These criteria were for histories of the Report Management (RM) and Embargo Management (EM) models, written as strings of a grammar of state transitions.
The same research measured skill over the Case State (CS) model.
The subsections below keep that material as it was written.
No reward-function implementation exists in the codebase.

Further optimization of the Vultron Protocol can be studied with the development of reward functions to evaluate preferences for certain CVD case histories over others.
In [A State-Based Model for Multi-Party Coordinated Vulnerability Disclosure](https://resources.sei.cmu.edu/library/asset-view.cfm?assetid=735513){:target="_blank"}, we provided a method to measure skill (${\alpha}_d$) in CVD based on a partial order over the CVD success criteria that make up the CS process, as outlined in [Defining CVD Success](../background/cvd_success.md).
While not yet a fully-realized reward function, we feel that the ${\alpha}_d$ skill measure has potential as the basis of a reward function for the CS model.

The following sections describe two additional reward functions.

### A Reward Function for Minimizing RM Strings

In [RM Formal Model](../process_models/rm/formal_model.md#rm-transition-function), we described a grammar that generates RM histories.
The state machine can generate arbitrarily long histories because of the cycles in the state machine graph; however, we observed that human Participants in any real CVD case would likely check the amount of churn.
That sort of reliance on human intervention will not scale as well as a more automatable solution might.

As a result, we suggest that future work might produce a reward function that can be used to optimize RM histories.
Such a function would need to include the following:

- a preference for shorter paths over longer ones

- a preference for paths that traverse through $q^{rm} \in A$ over ones that do not

- a preference for Vendor attentiveness.

- a preference for validation accuracy

!!! tip "Notes on Vendor attentiveness"

    The default path for an organization with no CVD capability is effectively ${q^{em} \in S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{c}C}$, which is short (_good!_).
    However, assuming the vulnerability is legitimate, half of the desired CS criteria can never be achieved (_bad!_).
    In other words, $\mathbf{F} \prec \mathbf{P}$, $\mathbf{F} \prec \mathbf{X}$, $\mathbf{F} \prec \mathbf{A}$, $\mathbf{D} \prec \mathbf{P}$, $\mathbf{D} \prec \mathbf{X}$, $\mathbf{D} \prec \mathbf{A}$ are impossible when the Vendor ignores the report.
    No reward function should provide incentive for willful Vendor ignorance.

!!! tip "Notes on validation accuracy"

    Real vulnerabilities should pass through $q^{rm} \in V$, while bogus reports should pass through $q^{rm} \in I$.
    The only RM paths path not involving at least one step through $q^{rm} \in A$ are the following.

    | Path | Description |
    | ---- | ----------- |
    | $q^{rm} \in S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{c} C$ | Ignore an invalid case. |
    | $q^{rm} \in S \xrightarrow{r} R \xrightarrow{v} V \xrightarrow{d} D \xrightarrow{c} C$ | Defer a valid case. |
    | $q^{rm} \in S \xrightarrow{r} R \xrightarrow{i} I \xrightarrow{v} V \xrightarrow{d} D \xrightarrow{c} C$ | Initially ignore an invalid case, then validate, but defer it anyway. |

    To an outside observer, any of these could be interpreted as inattentiveness from an uncommunicative Participant.
    Yet any of these paths might be fine, assuming that (1) the Participant communicates about their RM state transitions, and (2) the $a$ transition was possible but intentionally just not taken.

!!! tip inline end "On the origin of the *CERT/CC Addendum* field in CERT/CC Vulnerability Notes"

    The problem described at left is why the individual Vendor records in CERT/CC Vulnerability Notes contain a *CERT/CC Addendum* field.

These last two imply some capacity for independent validation of reports, which, on the surface, seems poised to add cost or complexity to the process.
However, in any Multi-Party CVD (MPCVD) case with three or more Participants, a consensus or voting heuristic could be applied.
For example, should a quorum of Participants agree that a Vendor's products are affected even if the Vendor denies it, an opportunity exists to capture this information as part of the case.

### A Reward Function for Minimizing EM Strings

Similarly, the EM process also has the potential to generate arbitrarily long histories, as shown in [A Regular Grammar for EM](../process_models/em/index.md).
Again, reliance on humans to resolve this shortcoming may be acceptable for now; however, looking to the future, we can imagine a reward function to be optimized.
The EM reward function might include the following:

- a preference for short paths

- a preference for quick agreement (i.e., the $a$ transition appearing early in the EM history)

- a limit on how long an EM history can get without reaching $q^{em} \in A$ at all (i.e., How many proposal-rejection cycles are tolerable before giving up?)

## Modeling and Simulation

The path preferences above, and the reward-function criteria they come from, are also an instrument for evaluating changes to the protocol itself.
A [reference implementation](../../reference/code/index.md) of the protocol now exists, and its [demo scenarios](../scenarios/index.md) run the coordination logic end to end.
Its [behavior trees](../behavior_logic/index.md) are modular, which makes them ready ground for simulated experiments: a candidate change to the protocol can be run against a population of simulated cases and scored with these measures before it is proposed for adoption.
Nothing of this kind has been built.
The [formal protocol](../../reference/formal_protocol/index.md), the [CS model](../process_models/cs/index.md), and the path preferences above are the pieces such a simulation would assemble.

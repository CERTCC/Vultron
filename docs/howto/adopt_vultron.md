---
description: >
  Take a Coordinated Vulnerability Disclosure program from its current
  practice to one that can coordinate cases through Vultron: name your roles,
  choose a conformance claim, map your intake to the report states, publish
  your embargo defaults, and decide which judgment calls stay yours.
stakeholder_type: [cvd-practitioner]
level: 300
---

# How to Adopt Vultron in Your CVD Program

{% include-markdown "../includes/not_normative.md" %}

Use this guide to prepare a Coordinated Vulnerability Disclosure (CVD) program to coordinate cases through Vultron.
It is for the people who run the program, not the people who build its software; the software steps hand off to the [tracker integration path](../start/connect-your-tracker.md).
You finish with a role profile, a conformance claim for the system you will run, your report workflow mapped onto the protocol's report states, embargo defaults written into your disclosure policy, and a register of the decisions your organization keeps for itself.

---

## Prerequisites

- You know how a case works under Vultron: who owns it, what each participant sees, and what an embargo invitation asks.
  [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) covers this.
- You can describe your current intake: how a report reaches you, who triages it, and what your stages are called.
- You can change, or propose changes to, your organization's vulnerability disclosure policy.
- If your organization already follows the International Organization for Standardization (ISO) standards [ISO/IEC 29147](../reference/iso_crosswalks/iso_29147_2018.md) or [ISO/IEC 30111](../reference/iso_crosswalks/iso_30111_2019.md), have those processes at hand.
  The steps below map onto them, and the [ISO Crosswalk](../reference/iso_crosswalks/index.md) shows where.

---

## Step 1: Name the roles you hold

List the cases your program handled in the last year and note the role you held in each.
Vultron uses the roles the CVD process already uses: Reporter, Vendor, Coordinator, Deployer, CVE Numbering Authority (CNA), and Observer ([§2.2 Roles in the Vultron Protocol Specification](../reference/vultron-spec/introduction.md#22-roles)).

Record every role that appears.
A vendor's product security team is usually a Vendor, sometimes a Reporter, and occasionally a Coordinator for a downstream case.
A national Computer Security Incident Response Team (CSIRT) is usually a Coordinator and often a CNA.
A research team is a Reporter.

If you hold several roles in one case, list them all.
Roles are not exclusive, and your system will hold all of them at once ([§3.5 Participants and Roles](../reference/vultron-spec/introduction.md#35-participants-and-roles)).

You now have a **role profile**: the set of roles your program must be able to play.

## Step 2: Decide whether you will own or host cases

Answer two questions about the cases in your list.

1. Did you open the case, or make the disclosure decisions in it?
   If so, you were the [**Case Owner**](../reference/vultron-spec/introduction.md#22-roles) in that case.
2. Did you run the case on behalf of others, keeping its record and admitting participants?
   If so, you were acting as its [**Case Manager**](../topics/case_lifecycle/case_manager_and_ledger.md).

The answers pick the **capability sets** the system you run must provide ([§12.2 Capability Sets](../reference/vultron-spec/conformance.md#122-capability-sets)).

| Your answer | Capability sets you need |
|---|---|
| You only take part in cases others run | Case Observer |
| You open cases and decide for them | Case Observer + Case Decision |
| You also run cases for others | Case Observer + Case Decision + Case Hosting |

Every participant needs Case Observer; there is no smaller way to take part.
Write the result together with your role profile as a **conformance claim**, in the form the specification uses ([§12.1 Conformance Model Overview](../reference/vultron-spec/conformance.md#121-conformance-model-overview)).
`Case Observer / Vendor` says a vendor's system takes part in cases run by others.
`Case Observer + Case Decision + Case Hosting / Coordinator + CNA` says a coordinator's system opens cases, decides for them, runs them, and assigns CVE IDs.

The claim describes the software you will run, not your organization.
Keep it; Step 7 asks your platform team, or your tracker vendor, to meet it.

## Step 3: Map your intake to the report states

Vultron records where each participant stands on a report as one of the Report Management (RM) states ([Report Management Process Model](../topics/process_models/rm/index.md)).
Your internal stages stay as they are.
Write down which of your stages corresponds to each state.

| RM state | Your stage that corresponds to it |
|---|---|
| Received | A report has arrived and nobody has judged it yet |
| Valid or Invalid | Triage has decided whether the report describes a real vulnerability in something you are responsible for |
| Accepted or Deferred | Prioritization has decided whether to work it now or set it aside |
| Closed | Your work on the report is finished, whatever the outcome |

If a stage of yours spans two states, split the stage in your mapping, not in your process.
If two of your stages fall into one state, that is fine; the protocol carries the state, not the stage.
Only you move your own state, and the other participants learn of the move from your system's message.

The mapping is what your platform team needs from you in Step 7.
The developer-facing version of this exercise, with the messages each transition sends, is [Process Implementation Notes](process_implementation.md).

## Step 4: Write your embargo defaults into your disclosure policy

A case under Vultron begins with an embargo already in force when the report recipient has published a default embargo period and the Reporter proposed nothing else ([Default Embargoes](../topics/process_models/em/defaults.md)).
Publishing your default is therefore the one adoption step that changes how your first case starts.

Add the following to your vulnerability disclosure policy.

1. Your default embargo period, as a duration from the report's arrival.
   If your policy already states a disclosure timeline, that is your default.
2. How you answer a Reporter's proposed terms.
   The protocol's guidance is to accept the terms a Reporter proposes, and to take the shortest proposed embargo as accepted while negotiating a longer one as a revision ([Negotiating Embargoes](../topics/process_models/em/negotiating.md)).
3. When you will not enter an embargo at all: once the vulnerability, an exploit, or attacks are public, and usually once a fix is deployed ([Negotiating Embargoes](../topics/process_models/em/negotiating.md)).

If you are a Reporter, state the terms you will attach to the reports you submit.
A Reporter who submits with no terms has accepted the recipient's published default.

## Step 5: Set your embargo rules

Decide the following before your first invitation arrives, and write the answers next to your policy.

- Who in your organization answers an embargo invitation, and within how many days.
  An invitation that is not answered by its deadline counts as declined, a rule called the [Pocket Veto](../topics/behavior_logic/use-cases/embargo-lifecycle.md) ([§9.4 Deadlines and the Pocket Veto](../reference/vultron-spec/tracking-models.md#94-deadlines-and-the-pocket-veto)), and a declined participant is in the case without receiving its embargoed content.
- Whom you will propose adding to an embargoed case, and whom you will not.
  [Adding Participants to an Embargoed Case](../topics/process_models/em/working_with_others.md) gives the protocol's guidance on who belongs and when to bring them in.
- What you do when an embargo ends early.
  It ends for everyone the moment the vulnerability or an exploit becomes public, so have the advisory and the fix path ready before that day ([Early Termination](../topics/process_models/em/early_termination.md)).

## Step 6: Decide which judgment calls stay yours

Vultron does not judge whether a report is credible, how urgent a case is, whom else to invite, or when an advisory is ready.
Each of these is a **call-out point**: a place where the protocol stops and your organization answers ([Capability Model](../topics/capability_model/index.md)).

For each row below, record who or what answers it in your program: a named person, a written policy, or a tool you already run.

| Decision | Where your program answers it today |
|---|---|
| Is the report credible, and is it valid for us? | Triage |
| How urgent is this case? | Prioritization, for example a Stakeholder-Specific Vulnerability Categorization (SSVC) decision |
| Do we accept these embargo terms, or propose others? | Step 5 |
| Who else belongs in this case? | Coordination |
| Is the advisory ready to publish? | Publication review |
| Do we assign a CVE ID, or ask a CNA to? | Only if you hold the CNA role |

Leave a row blank if no one answers it today; that blank is a gap in your program, and the protocol will ask the question whether or not you have an answer.

You now have a **decision register**.
Give it to your platform team with the mapping from Step 3; each row is a seam where their system asks yours.

## Step 7: Get a system that speaks the protocol

Vultron is a protocol, not a product, so the last step is to obtain software that speaks it and meets your conformance claim from Step 2.

- If a tracker or coordination platform you already use claims Vultron support, ask its maintainers for the conformance claim it makes, and compare it with yours.
- If your own team builds or integrates your tracker, hand them your conformance claim, your state mapping, and your decision register, and point them to [You maintain a vulnerability tracker and want it to talk to your partners](../start/connect-your-tracker.md).
- If you want to see the protocol run before committing, run the reference implementation's demos.
  [Run the FV Demo](../tutorials/fv-demo.md) runs the Finder + Vendor (FV) scenario, in which a Reporter and a Vendor take a case from report to publication, and the reference implementation can act as a test peer for a system your team is building.

!!! note "Work in progress"

    Vultron is **not yet ready for production use**.
    The steps above prepare a program for it and can be taken now; the software step is where you should expect the protocol and its implementations to change under you.

---

## What you have at the end

| Artifact | Produced in | Who uses it |
|---|---|---|
| Role profile | Step 1 | Your platform team; your partners, when they invite you |
| Conformance claim | Step 2 | Your platform team or tracker vendor |
| Report-state mapping | Step 3 | Your platform team; your own triage staff |
| Embargo defaults in your disclosure policy | Step 4 | Reporters, and every case you join |
| Embargo rules | Step 5 | The people who answer invitations |
| Decision register | Step 6 | Your platform team, one call-out point per row |

## Further reading

- [A Case Under Vultron](../topics/case_lifecycle/a_case_under_vultron.md) — what the case looks like from your seat once these steps are done
- [Embargo Principles](../topics/process_models/em/principles.md) — the norms your embargo rules should follow
- [ISO Crosswalk](../reference/iso_crosswalks/index.md) — where each step lands in ISO/IEC 29147, 30111, and TR 5895
- [Interactions Between the Vultron Protocol and SSVC](../reference/ssvc_crosswalk.md) — where a prioritization decision enters a case
- [Vultron Protocol Specification, §12 Conformance](../reference/vultron-spec/conformance.md#12-conformance-n) — the normative definition of capability sets and conformance claims

---
stakeholder_type: [cvd-practitioner]
level: 300
page_type: explanation
description: >
  The events that end an embargo before its agreed time, how a termination
  records why it ended, and what happens when the end time passes.
---

# Early Termination

{% include-markdown "../../../includes/specification_governs.md" %}

Embargoes sometimes terminate before the agreed date and time.
This fact is inconvenient, but it is unavoidable.
It has three main causes:

1. Many people across the world can discover vulnerabilities, and not all Finders become cooperative Reporters.

2. Even among otherwise cooperative CVD Participants, leaks sometimes happen.

3. CVD does not constrain how adversaries discover vulnerabilities, develop exploit code, or use exploit code in attacks.

## Be Prepared for Embargo Termination

Many leaks are unintentional.
They come from miscommunication or from errors in the CVD process of a Participant.
But the effect is the same, whatever the cause.
As a result,

!!! note ""

    Participants SHOULD be prepared with contingency plans in the event of early embargo termination.

## Reasons to Terminate an Embargo Early

Some reasons to terminate an embargo before the agreed date are as follows:

!!! note ""
  
    ???+ note inline end "Formalism"

        $q^{cs} \in \{ \cdot\cdot\cdot P \cdot\cdot, \cdot\cdot\cdot\cdot X \cdot \}$

    Embargoes SHALL terminate immediately when information about the vulnerability becomes public.
    Public information may include reports of the vulnerability or exploit code.

!!! note ""

    ???+ note inline end "Formalism"

        $q^{cs} \in \{ \cdot\cdot\cdot\cdot\cdot A \}$

    Embargoes SHOULD terminate early when there is evidence that the vulnerability is being actively exploited by adversaries.

!!! note ""

    Embargoes SHOULD terminate early when there is evidence that adversaries possess exploit code for the vulnerability.

!!! note ""

    Embargoes MAY terminate early when there is evidence that adversaries are aware of the technical details of the vulnerability.

The list above does not include all acceptable reasons to terminate an embargo early.
The first item uses *SHALL* and the second item uses *SHOULD*.
This difference comes from the reasoning in the [CS model](../cs/cs_model.md), where we describe the transition function of the CS model.

Embargo termination is the set of transitions described in the [EM formal model](formal_model.md#terminate-embargo).
A termination ends the embargo in force and cancels every proposal that is still open.
It does both in one step on the embargo register of the case.
When an embargo terminates, the protocol writes no [embargo consent](../../behavior_logic/use-cases/embargo-lifecycle.md#which-messages-move-consent) for any Participant.

The position of each Participant follows from the register.
With no embargo in force, no Participant is bound by one.
Every consent row for the ended and canceled embargoes stays as it was ([§7.3 Relationship to Embargo Consent in the Vultron Protocol Specification](../../../reference/vultron-spec/tracking-models.md#73-relationship-to-embargo-consent)).
After the embargo of a case terminates, its register takes no further change.
So the case cannot be put under a new embargo.

## Recording Why an Embargo Ended

Every termination records what ended the embargo.
Either the embargo reached its end time (`END_TIME_REACHED`), or it ended early (`EARLY`).
The termination message carries that reason, and every Participant records it.
An early termination may also record why the embargo ended, as one of four kinds of cause:

| Cause | Detail | Who may name it |
|---|---|---|
| `THREAT_SIGNAL` | The signals that ended it: public awareness (`P`), a public exploit (`X`) or observed attacks (`A`) | The Case Manager only |
| `FIX_READY` | The Vendors whose readiness made the quorum | The Case Owner or the Case Manager |
| `FIX_DEPLOYED` | None | The Case Owner or the Case Manager |
| `OTHER` | None; the termination message's human-readable summary gives the account | The Case Owner or the Case Manager |

An embargo that reached its end time has no cause.
An early termination with no cause is valid.
The termination message carries the cause beside the reason.
The Case Manager records both on the entry of the ended embargo in the embargo register of the case.

When the Case Owner names `FIX_READY`, `FIX_DEPLOYED` or `OTHER`, the Case Manager records that cause as the Case Owner gave it.
The Case Manager does not check it, because the decision to end early on a quorum of Vendors is the judgment of the Case Owner.
A Case Owner does not name a threat signal in a termination message, and the Case Manager refuses a message that does.
Instead, the Case Owner reports the threat as a case status update that sets `P`, `X` or `A`.
The Case Manager then ends the embargo with the signals that the case carries.

## When the End Time Passes

An embargo does not end by itself when its end time passes.
The Case Manager ends it with the reason `END_TIME_REACHED`.
This termination runs the same steps as all other terminations.
The Case Manager cancels open proposals, the case leaves the embargo, and the Case Manager tells every Participant.

The Case Manager checks the end time the next time it handles the case, for an incoming message or for one of its own actions.
So no scheduler is necessary.

The Case Manager checks only after it confirms that the sender of the message may send it.
So a message from someone with no standing in the case never causes the Case Manager to end the embargo.
A request to end the embargo early can arrive after its end time.
The Case Manager records that request as `END_TIME_REACHED`, because the embargo had already reached its end.

An outside service can also ask the Case Manager to end the embargo at its end time.
An example is a [Sentinel](../../../reference/glossary.md) that watches embargo timers.
The two requests share one path.
The request that arrives second finds the embargo already ended, and the Case Manager sends nothing more.
The Case Manager refuses a termination that claims the end time was reached before it was.

## Waiting for All Vendors to Reach *Fix Ready* May Be Impractical

???+ note inline end "Fix Ready Definition"

    $$q^{cs} \in VF\cdot\cdot\cdot\cdot$$

It is not necessary for all Vendor Participants to reach *Fix Ready* before publication or embargo termination.
This is especially true in larger MPCVD cases.
At some point, waiting for every Vendor to be ready gives less net benefit than delivering a fix to the population that can deploy it.
No solid formula for this point exists, but factors to consider include

- the market share of the Vendors in *Fix Ready* ($q^{cs} \in VF \cdot \cdot \cdot \cdot$) compared to the Vendors that are not ($q^{cs} \in \cdot f \cdot \cdot \cdot \cdot$)
- the software supply chain for fix delivery to Deployers
- the potential impact to critical infrastructure, public safety/health, or national security

!!! note ""

    Embargoes MAY terminate early when a quorum of Vendor Participants is prepared to release fixes for the vulnerability ($q^{cs}  \in VF\cdot\cdot\cdot\cdot$), even if some Vendors remain unprepared ($q^{cs} \in \cdot f \cdot\cdot\cdot\cdot$).

!!! note ""

    Participants SHOULD consider the software supply chain for the vulnerability in question when determining an appropriate quorum for release.

## Doing It on the Wire

- [How to Revise or Terminate an Embargo](../../../howto/activitypub/activities/manage_embargo.md) — end an active embargo, early or at its agreed time.
- [How to Establish an Embargo](../../../howto/activitypub/activities/establish_embargo.md) — propose and activate an embargo on a case that has not yet had one end.

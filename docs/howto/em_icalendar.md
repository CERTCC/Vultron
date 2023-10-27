# Embargo Management and the iCalendar Protocol

{% include-markdown "../includes/not_normative.md" %}

We are including this page because the ideas outlined here were instrumental to the development of the more general
[Embargo Management process](../topics/process_models/em/index.md) in the main protocol and may remain of use in future implementations.

The embargo negotiation process&mdash;in terms of the proposal, acceptance, rejection, etc.&mdash;is strikingly
parallel to the process of scheduling a meeting in a calendaring system.
To that end, we note the potential application of the [`iCalendar`](https://en.wikipedia.org/wiki/ICalendar) protocol specified in [RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545) to the
[EM process](../topics/process_models/em/index.md) with the semantics described in this section.
While we anticipate that future CVD APIs could adopt an `iCalendar`-compatible syntax like `jCal` ([RFC 7265](https://datatracker.ietf.org/doc/html/rfc7265)), for
this conceptual mapping, we use the basic `iCalendar` syntax from [RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545).

A CVD Case might have an associated `iCalendar` object.
Embargo schedules can be represented as a single `VEVENT` object.

A mapping of EM concepts to `iCalendar` field mappings is provided in the table below.

| Embargo Concept                                                | iCalendar Mapping | EM Msg Type |
|----------------------------------------------------------------|-------------------|-------------|
| Embargo object                                                 | `VEVENT` | -           |
| Embargo ID                                                     | `SUMMARY:<case id> embargo expiration` | -           |
| Embargo End Time and Date                                      | `DSTART = DTEND` (0 duration event) | -           |
| Proposer                                                       | `ORGANIZER` | -           |
| Participant (proposed)                                         | `ATTENDEE;`<br/>`ROLE=OPT-PARTICIPANT;`<br/>`PARTSTAT=NEEDS-ACTION` | _EP_, _EV_  |
| Participant (acknowledge without acceptance)                   | `ATTENDEE;`<br/>`ROLE=OPT-PARTICIPANT;`<br/>`PARTSTAT=TENTATIVE` | _EK_        |
| Participant (accept)                                           | `ATTENDEE;`<br/>`ROLE=OPT-PARTICIPANT;`<br/>`PARTSTAT=ACCEPTED` | _EA_, _EC_  |
| Participant (reject)                                           | `ATTENDEE;`<br/>`ROLE=OPT-PARTICIPANT;`<br/>`PARTSTAT=DECLINED` | _ER_, _EJ_  |
| Details (link to case trackers, etc.)                          | `DESCRIPTION` | -           |
| Embargo Status $q^{em} \in P$                                  | `STATUS:TENTATIVE` | _EP_        |
| Embargo Status $q^{em} \in A$                                  | `STATUS:CONFIRMED` | _EA_, _EC_  |
| Embargo Status $q^{em} \in X$ due to early termination         | `STATUS:CANCELLED` | _ET_        |
| Embargo Status $q^{em} \in N$ due to lack of acceptance quorum | `STATUS:CANCELLED` | _ER_        |
| Other | `CATEGORIES:EMBARGO`<br/>`RSVP: TRUE` | - |

!!! note ""

    Reflecting the non-binding nature of embargoes, each `ATTENDEE` SHOULD be marked as `ROLE=OPT-PARTICIPANT` in the invitation.

!!! note ""

    Vulnerability details MUST NOT appear in the iCalendar data.

!!! note ""  

    A case or vulnerability identifier SHOULD appear in the `VEVENT`
    `SUMMARY` along with the words "embargo expiration."

!!! note ""

    Case or vulnerability identifiers SHOULD NOT carry any information
    that reveals potentially sensitive details about the vulnerability.

!!! note ""

    An embargo proposal SHALL set `RSVP:True` for all attendees.

A Participant response with `ATTENDEE:partstat=TENTATIVE` serves as a
basic acknowledgment that the embargo proposal has been received, but it
does not represent agreement to the proposal.

The `iCalendar` `ATTENDEE:partstat=DELEGATED` value has no semantic equivalent in the EM process.

## Proposing an Embargo

Following the model of inviting a group of attendees to a meeting, a
proposed embargo can be achieved as follows:

1. An `ORGANIZER` sends an embargo invitation, represented by a
    `VEVENT` with `STATUS:TENTATIVE` listing Participants as `ATTENDEE`s
    ($q^{em} \in N \xrightarrow{p} P$).

2. Each `ATTENDEE` has `partstat=NEEDS-ACTION` set on the invitation,
    indicating that they have not yet accepted it.

3. Individual `ATTENDEE`s acknowledge (`partstat=TENTATIVE`), accept
    (`partstat=ACCEPTED`), or decline (`partstat=DECLINED`). Their
    response is sent to the `ORGANIZER`.

4. If the `ORGANIZER` determines that there is a quorum of accepts,
    they mark the `VEVENT` as `STATUS:CONFIRMED`
    ($q^{em} \in P \xrightarrow{a} A$).

5. If the `ORGANIZER` determines that there is no sufficient quorum of
    accepts, they mark the new `VEVENT` as `STATUS:CANCELLED`
    ($q^{em} \in P \xrightarrow{r} N$).

## Embargo Counterproposals

Counterproposals can be achieved in two ways:

1. by declining an initial invitation and then proposing a new one
    ($q^{em} \in P \xrightarrow{r} N \xrightarrow{p} P$)

2. by proposing a new embargo without declining the first one
    ($q^{em} \in P \xrightarrow{p} P$)

Either way, this is analogous to requesting a proposed meeting to be
shifted to a different time or date prior to accepting the original
proposed meeting time. However, following the argument from
[Default Embargoes](../topics/process_models/em/defaults.md),
we suggest that Participants start by (1) accepting the shortest proposed embargo and (2) proposing a
revision to the new embargo instead, which we cover next.

## Proposing a Change to an Existing Embargo

!!! tip inline end "Assumption"

    This process assumes that an existing embargo is represented by a `VEVENT` with`STATUS:CONFIRMED`.

Similar to rescheduling an existing meeting, a proposed change to an
existing embargo can be achieved as follows.

1. A new proposal is made as a `VEVENT` with `STATUS:TENTATIVE` and the
    same `ATTENDEE` list as the existing one
    ($q^{em} \in A \xrightarrow{p} R$).

2. Each `ATTENDEE` on the new invitation has `partstat=NEEDS-ACTION`
    set, indicating that they have not yet accepted the new invitation.

3. Individual `ATTENDEE`s acknowledge (`partstat=TENTATIVE`), accept
    (`partstat=ACCEPTED`), or decline (`partstat=DECLINED`). Their
    response is sent to the `ORGANIZER`.

4. If the `ORGANIZER` determines that there is a quorum of accepts
    ($q^{em} \in R \xrightarrow{a} A$), they

    1. mark the new `VEVENT` as `STATUS:CONFIRMED`

    2. mark the old `VEVENT` as `STATUS:CANCELLED`

5. If the `ORGANIZER` determines that there is no sufficient quorum of
    accepts ($q^{em} \in R \xrightarrow{r} A$), they

    1. mark the new `VEVENT` as `STATUS:CANCELLED`

    2. retain the old `VEVENT` as `STATUS:CONFIRMED`

## Terminating an Existing Embargo

Terminating an existing embargo ($q^{em} \in \{A,R\} \xrightarrow{t} X$)
can be triggered in one of two ways:

- A _normal_ exit occurs when the planned embargo end time has
    expired.

- An _abnormal_ exit occurs when some external event causes the
    embargo to fail, such as when the vulnerability or its exploit has
    been made public, attacks have been observed, etc., as outlined in
    [Early Termination](../topics/process_models/em/early_termination.md).

Translating this into `iCalendar` semantics, we have the following,
which assumes an existing embargo is represented by a `VEVENT` with
`STATUS:CONFIRMED`.

1. _Normal termination_: The `VEVENT` retains its `STATUS:CONFIRMED`
    and passes quietly from the future through the present into the
    past.

2. _Abnormal termination_: The `ORGANIZER` sets the `VEVENT` to
    `STATUS:CANCELLED` and sends it out to the `ATTENDEE` list.

The above is consistent with our premise in
[Early Termination](../topics/process_models/em/early_termination.md): Embargo Termination ($ET$) messages
are intended to have immediate effect.

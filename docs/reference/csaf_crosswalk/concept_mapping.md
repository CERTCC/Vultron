---
description: >
  Each Vultron concept with its counterpart in the Common Security Advisory
  Framework (CSAF) 2.1 draft, the granularity of the match, and the type of
  mapping in each direction.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 400
page_type: reference
subject: neutral
---

# CSAF 2.1 Concept Mapping

{% include-markdown "../../includes/not_normative.md" %}

This page maps each Vultron concept to its counterpart in the Common Security Advisory Framework (CSAF) 2.1 draft.
It is for readers who convert between the two models, or who need to know how much meaning a conversion keeps.
A Vultron concept can map to any part of a CSAF document, not only to `document.involvement`.
The [overview](overview.md) explains how a CSAF document relates to a Vultron case, and the [coverage differences](coverage.md) page lists the concepts with no counterpart.

{% include-markdown "./_csaf_version.md" %}

---

## How to read the tables

Each row has six columns.
**Vultron concept** and **CSAF concept** name the two sides, and the CSAF side gives its location in the document.
**Granularity** tells how many concepts on one side match how many on the other side.
**Vultron → CSAF** and **CSAF → Vultron** give the type of mapping in each direction.
The two directions can differ: a mapping can be fixed in one direction and need judgment in the other.
**Proposed change** says what could change, or why nothing changes.

| Granularity | Meaning |
|---|---|
| One to one | One Vultron concept matches one CSAF concept. |
| One to many | One Vultron concept matches two or more CSAF concepts. |
| Many to one | Two or more Vultron concepts match one CSAF concept. |
| No match | The concept has no counterpart. The [coverage differences](coverage.md) page gives it in full. |

| Mapping type | Meaning |
|---|---|
| Mechanical | A fixed rule gives the result. No judgment is necessary. |
| Derived | A rule calculates the result from two or more facts, or from the state at a ledger position. |
| Interpretive | The result needs judgment or context. |
| None | No mapping exists in this direction. |

A projection is a CSAF document that a participant produces from its copy of a case, as the [overview](overview.md#a-case-can-produce-a-csaf-document) explains.
"Vultron → CSAF" is the direction of a projection.
"CSAF → Vultron" is the direction of a CSAF document that arrives inside a case, and Vultron could read such content as claims ([overview](overview.md#a-csaf-document-can-travel-inside-a-case), [#5131](https://github.com/CERTCC/Vultron/issues/5131){:target="_blank"}).

---

## Parties and roles

A Vultron [participant](../glossary.md#cvd-roles-and-participants) is an actor with one or more roles in one case ([§2.2 Roles](../vultron-spec/introduction.md#22-roles)).
A CSAF entity is a party in one document, with one category.
CSAF states that "the `category` does not control the role": an entity can act in one action and receive in a different action.

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>CSAF concept</th>
<th>Granularity</th>
<th>Vultron → CSAF</th>
<th>CSAF → Vultron</th>
<th>Proposed change</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">`CaseParticipant`</td>
<td markdown="span">Entity, `document.involvement.entities[]`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: CSAF entities also include parties that are never participants, such as an `adversary` or the `public`.</td>
</tr>
<tr markdown="1">
<td markdown="span">[`CVDRole`](../../topics/case_lifecycle/case_model.md#cvdrole) list on a participant</td>
<td markdown="span">Entity `category`, one value</td>
<td markdown="span">Many to one</td>
<td markdown="span">Interpretive</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: a participant with two or more roles becomes one entity, and the projection selects the category that best fits the actions it records.</td>
</tr>
<tr markdown="1">
<td markdown="span">`VENDOR`</td>
<td markdown="span">`vendor`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">`COORDINATOR`</td>
<td markdown="span">`coordinator`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">`REPORTER`</td>
<td markdown="span">`discoverer` ("It is assume [sic] that the discoverer also reports vulnerabilities.")</td>
<td markdown="span">One to one</td>
<td markdown="span">Interpretive</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed: both models put finder and reporter into one role, with opposite names. Vultron retired its `FINDER` role, and the report content or a case note names the finder ([ADR-0078](../../adr/0078-retire-finder-role.md)). Vultron has no structured field for the finder. A projection gives `discoverer` to a `REPORTER` only when the report content or a case note names that participant as the finder. A coordinator that sends the report of a different party is not the discoverer, so it gets the category of its other roles, or `other`.</td>
</tr>
<tr markdown="1">
<td markdown="span">`DEPLOYER`</td>
<td markdown="span">`user`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: a CSAF `user` operates a product, and a Vultron [Deployer](../glossary.md#cvd-roles-and-participants) is a participant that deploys the fix. A `user` that takes no part in the case is not a participant.</td>
</tr>
<tr markdown="1">
<td markdown="span">`OBSERVER`</td>
<td markdown="span">`other`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: both are the role that the other values do not give.</td>
</tr>
<tr markdown="1">
<td markdown="span">`CVE_NUMBERING_AUTHORITY`</td>
<td markdown="span">No match. `reporting_authority` is "an entity that receives or requires a report, e.g. a national CSIRT". A CSIRT is a Computer Security Incident Response Team.</td>
<td markdown="span">No match</td>
<td markdown="span">None</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: a Common Vulnerabilities and Exposures (CVE) Numbering Authority (CNA) assigns identifiers, and a reporting authority receives reports. The two names are similar, but the concepts are different.</td>
</tr>
<tr markdown="1">
<td markdown="span">`CASE_OWNER`, `CASE_MANAGER`</td>
<td markdown="span">No match</td>
<td markdown="span">No match</td>
<td markdown="span">None</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: these roles control who can change the case, and a CSAF document has no such control. See [coverage differences](coverage.md#authority-and-entitlement).</td>
</tr>
<tr markdown="1">
<td markdown="span">Recipient set of a message, calculated from roles and entitlement</td>
<td markdown="span">Entity group, `document.involvement.entity_groups[]`</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: Vultron does not store named groups. A projection makes a group only when the group makes the document shorter, for example the participants with one role, the parties to one embargo version, or the recipients of one message.</td>
</tr>
<tr markdown="1">
<td markdown="span">Actor profile and inbox</td>
<td markdown="span">Entity `contact` (`contact_t`: `details`, `email`, `public_openpgp_key_url`, `url`)</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: a CSAF contact tells how to reach a party, and a Vultron actor identifier is an address for protocol messages. A contact is not an actor identity.</td>
</tr>
<tr markdown="1">
<td markdown="span">Actor Uniform Resource Identifier (URI)</td>
<td markdown="span">Entity ID, `EID-…`, local to the document</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">None</td>
<td markdown="span">Undecided: CSAF could let an entity carry an optional identifier that stays the same in different documents, for example a URI. The TC wants an issuing party to copy an involvement list into a different document without a change in meaning, and a stable identifier would let a reader match an entity in two documents. If nothing changes, a projection mints new `EID-` tokens for each document, and a reader matches entities by name and contact only.</td>
</tr>
</tbody>
</table>

---

## Events and timeline

A Vultron case records each completed act as one or more [case ledger entries](../../topics/case_lifecycle/case_manager_and_ledger.md) ([ADR-0119](../../adr/0119-case-ledger-records-completed-acts.md)).
The payload of each entry is an ActivityStreams 2.0 (AS2) activity ([ADR-0124](../../adr/0124-case-is-a-projection-of-its-ledger.md)).
A CSAF action is one event in the `document.involvement.actions[]` timeline.
The two have the same shape: an actor, recipients, a time, a type, and an optional link to earlier events.

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>CSAF concept</th>
<th>Granularity</th>
<th>Vultron → CSAF</th>
<th>CSAF → Vultron</th>
<th>Proposed change</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Case ledger, all entries</td>
<td markdown="span">`document.involvement.actions[]`, selected events</td>
<td markdown="span">Many to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: different purpose. The ledger records every change, and CSAF records the events that the issuing party selects. A projection filters the ledger.</td>
</tr>
<tr markdown="1">
<td markdown="span">Activity `actor`</td>
<td markdown="span">`acting_entity_refs`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: a received action is a claim about who acted.</td>
</tr>
<tr markdown="1">
<td markdown="span">Activity recipients (`to`)</td>
<td markdown="span">`receiving_entity_refs`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed. CSAF forbids one entity as both actor and recipient of one action (test 6.1.64.4). In Vultron, an organization that finds a vulnerability in its own product can be its own Reporter. As the CSAF note to that test advises, a projection then uses two entities for the organization, or leaves the act out.</td>
</tr>
<tr markdown="1">
<td markdown="span">Activity that refers to an earlier activity, for example `Accept(Offer)` or `inReplyTo`</td>
<td markdown="span">`referenced_action_ids`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">Activity identifier, a URI</td>
<td markdown="span">`action_id`, local to the document</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: a projection mints one `action_id` for each activity that it includes.</td>
</tr>
<tr markdown="1">
<td markdown="span">Two times: the `published` time that the sender claims, and the commit time of the Case Manager (CLP-14-002, CLP-15-005)</td>
<td markdown="span">`date`, one time</td>
<td markdown="span">Many to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: one time is sufficient for a documentation model. A projection uses the claimed `published` time, because that is the time that the sender gives for the act (CLP-15-004).</td>
</tr>
<tr markdown="1">
<td markdown="span">Semantic type of the activity</td>
<td markdown="span">Action `category`</td>
<td markdown="span">Many to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: Vultron has more semantic types than CSAF has categories, so several types share a category. CSAF uses `coordination` for joint work and `notification` for an action with no specific category. The other sections of this page give the mapping of each type.</td>
</tr>
<tr markdown="1">
<td markdown="span">Act on the whole case</td>
<td markdown="span">`dl_vuln_ids`, `product_ids`, `group_ids` on an action</td>
<td markdown="span">One to many</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: a projection leaves out `dl_vuln_ids`, and the action then applies to all vulnerabilities in the document (test 6.2.56.4). An act on one vulnerability only is an argument to split the case ([ADR-0125](../../adr/0125-case-split-child-case-inherits-the-embargo-only.md), proposed).</td>
</tr>
<tr markdown="1">
<td markdown="span">State at a ledger position, for example an invitation with no answer</td>
<td markdown="span">Action `status` other than `completed`</td>
<td markdown="span">One to many</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: different purpose. A ledger entry records a completed act, so the entry of each act becomes a `completed` action. The follow-on entries that an act causes (CLP-07-013) go into that action. A projection derives `outstanding`, `deferred`, and `discontinued` from the state at its ledger position. It does not make `attempted`, because a failed delivery is a fact about the outbox, not about the case. It does not make `planned`, because Vultron does not record intentions.</td>
</tr>
</tbody>
</table>

---

## Report management

Vultron state names tell what already occurred.
`RECEIVED` means that the report arrived.
CSAF status values tell what occurs now.
In CSAF terms, the same fact is an `assessment` that is `in_progress`.
Most differences in this section are a change of tense, not a disagreement.

The [Report Management (RM) states](../../topics/process_models/rm/index.md#rm-states) belong to one participant ([§6 Report Management (RM) State Machine](../vultron-spec/tracking-models.md#6-report-management-rm-state-machine-n)).
In the CSAF rows below, that participant is the actor.
The CSAF design proposal notes a difference in perspective for `deferred`: CSAF records that an actor chose not to act, and RM `DEFERRED` records that a participant put a valid report aside ([#1486, Appendix A.2](https://github.com/oasis-tcs/csaf/issues/1486#issuecomment-5291835024){:target="_blank"}).
In the reading of this crosswalk, the two agree when the participant is the actor of the deferred action.

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>CSAF concept</th>
<th>Granularity</th>
<th>Vultron → CSAF</th>
<th>CSAF → Vultron</th>
<th>Proposed change</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Report submission, `Offer(VulnerabilityReport)`</td>
<td markdown="span">`notification`, `completed`, from the sender to the receiver</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">RM `START`</td>
<td markdown="span">No match</td>
<td markdown="span">No match</td>
<td markdown="span">None</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: the participant has not received the report, so there is no event to record.</td>
</tr>
<tr markdown="1">
<td markdown="span">RM `RECEIVED`</td>
<td markdown="span">`assessment`, `in_progress`</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: a change of tense. The design discussion records receipt as a `confirmation` instead, which "received or accepted" the action that it refers to ([#1486, 6 October 2026](https://github.com/oasis-tcs/csaf/issues/1486#issuecomment-6016287102){:target="_blank"}). The RM `ACCEPTED` row discusses that value.</td>
</tr>
<tr markdown="1">
<td markdown="span">RM `VALID`, RM `INVALID`</td>
<td markdown="span">`assessment`, `completed`</td>
<td markdown="span">Many to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: CSAF records that the assessment occurred, and the result goes in `metrics`, `threats`, or `summary`. A projection writes the result in `summary`. A participant that finds a report invalid can also record a `dispute` of the `notification`.</td>
</tr>
<tr markdown="1">
<td markdown="span">RM `ACCEPTED`</td>
<td markdown="span">`confirmation`, `completed`, which refers to the `notification`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">Undecided: a CSAF `confirmation` means that the actor "received or accepted" the action. Vultron keeps receipt and acceptance as two facts. CSAF could make the two meanings different. If nothing changes, a projection writes in `summary` which of the two a `confirmation` records.</td>
</tr>
<tr markdown="1">
<td markdown="span">RM `DEFERRED`</td>
<td markdown="span">`assessment` or `coordination` by the participant, `deferred`</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">RM `CLOSED`</td>
<td markdown="span">`completed` or `discontinued`, according to the reason</td>
<td markdown="span">One to many</td>
<td markdown="span">Interpretive</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: a participant closes a report after its work is complete, or when it stops work. The projection selects the status from the case context.</td>
</tr>
<tr markdown="1">
<td markdown="span">Participant leaves the case before its work is complete</td>
<td markdown="span">`discontinued` on its open actions</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed.</td>
</tr>
</tbody>
</table>

---

## Embargo

Vultron Embargo Management (EM) keeps each embargo in the case's [embargo register](../../topics/process_models/em/index.md#the-embargo-register), one entry for each version ([§7.1.1 The Embargo Register](../vultron-spec/tracking-models.md#711-the-embargo-register)).
Each participant gives its own [embargo consent](../../topics/behavior_logic/use-cases/embargo-lifecycle.md#which-messages-move-consent) to each version ([ADR-0122](../../adr/0122-per-embargo-participant-consent.md)).
The active embargo has one end time.
CSAF records an embargo as an `embargo` action: "the actor and the receiving entities agree to not disclose the information before the intended disclosure date."
The date is not on the action: "The agreed date is the `disclosure_date` of each vulnerability that `dl_vuln_ids` names."
Vultron also keeps the end of an embargo apart from publication ([Embargo Termination is Not the Same as Publication](../../topics/process_models/em/principles.md#embargo-termination-is-not-the-same-as-publication)), and CSAF uses one date for both.

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>CSAF concept</th>
<th>Granularity</th>
<th>Vultron → CSAF</th>
<th>CSAF → Vultron</th>
<th>Proposed change</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Embargo register entry, one embargo version</td>
<td markdown="span">`embargo` action</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed for the action itself.</td>
</tr>
<tr markdown="1">
<td markdown="span">Embargo end time of the case</td>
<td markdown="span">`vulnerabilities[].disclosure_date`</td>
<td markdown="span">One to many</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">CSAF could let an `embargo` action carry its own end date. If nothing changes, one document holds one date for each vulnerability, so a projection shows only the current embargo version, and earlier dates appear only in `summary` text. See [proposal 1](proposals.md#1-an-embargo-action-carries-its-own-end-date).</td>
</tr>
<tr markdown="1">
<td markdown="span">Revised embargo, EM `REVISE` and the next register entry</td>
<td markdown="span">A new `embargo` action that refers to the earlier `embargo` action</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">CSAF could let an `embargo` action carry its own end date. If nothing changes, the new action changes the `disclosure_date` of the document, and the date of the earlier version is lost. See [proposal 1](proposals.md#1-an-embargo-action-carries-its-own-end-date).</td>
</tr>
<tr markdown="1">
<td markdown="span">Early termination of an embargo, EM `EXITED` before the end time</td>
<td markdown="span">No match</td>
<td markdown="span">No match</td>
<td markdown="span">None</td>
<td markdown="span">None</td>
<td markdown="span">CSAF could record the early end of an embargo. If nothing changes, a projection records the end as a `coordination` action and explains it in `summary`. See [proposal 2](proposals.md#2-an-embargo-can-end-before-its-date).</td>
</tr>
<tr markdown="1">
<td markdown="span">Embargo consent `INVITED`</td>
<td markdown="span">`confirmation` by the invitee, `outstanding`</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">Embargo consent `AGREED`</td>
<td markdown="span">`confirmation`, `completed`, which refers to the `embargo` action</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">Embargo consent `DECLINED`</td>
<td markdown="span">`dispute`, `completed`, which refers to the `embargo` action</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">Embargo consent `TIMED_OUT`, the [pocket veto](../glossary.md#embargo-and-timing)</td>
<td markdown="span">No match</td>
<td markdown="span">No match</td>
<td markdown="span">Interpretive</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: a projection records no action from the invitee, and it explains the time-out in the `summary` of the `embargo` action.</td>
</tr>
<tr markdown="1">
<td markdown="span">Embargo consent `UNINVITED`</td>
<td markdown="span">No match</td>
<td markdown="span">No match</td>
<td markdown="span">None</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: no event occurred.</td>
</tr>
</tbody>
</table>

---

## Case state

The [Case State (CS) model](../../topics/process_models/cs/cs_model.md) has six dimensions ([§8 Case State (CS) Dimensions](../vultron-spec/tracking-models.md#8-case-state-cs-dimensions-n)).
Some dimensions are events between parties, and CSAF records them as actions.
Others are facts about the vulnerability, and CSAF records them in `vulnerabilities[]`, not in `involvement`.
CSAF also carries Stakeholder-Specific Vulnerability Categorization (SSVC) values in `vulnerabilities[].metrics`.
SSVC and Vultron come from the same team at the CERT Coordination Center (CERT/CC), so their mappings are especially close.
The [SSVC crosswalk](../ssvc_crosswalk.md#exploitation) gives the mapping between the CS model and SSVC.

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>CSAF concept</th>
<th>Granularity</th>
<th>Vultron → CSAF</th>
<th>CSAF → Vultron</th>
<th>Proposed change</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Vendor Awareness (V)</td>
<td markdown="span">`notification`, `completed`, to the vendor</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">Fix Readiness (F)</td>
<td markdown="span">`fix_release`, `completed`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed for the mapping. Details of the fix go in `vulnerabilities[].remediations`, which Vultron does not model. CSAF records a fix for each product, and Vultron records F once for each participant. Concern [#5140](https://github.com/CERTCC/Vultron/issues/5140){:target="_blank"} asks whether Vultron could track F for each vendor and product.</td>
</tr>
<tr markdown="1">
<td markdown="span">Fix Deployed (D)</td>
<td markdown="span">`fix_deployment`, `completed`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed for the mapping. Concern [#5140](https://github.com/CERTCC/Vultron/issues/5140){:target="_blank"} asks whether Vultron could track D for each vendor, product, and deployer.</td>
</tr>
<tr markdown="1">
<td markdown="span">Public Awareness (P)</td>
<td markdown="span">`vulnerabilities[].disclosure_date` with a past date</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed. The time of the P event becomes the `disclosure_date`. A `disclosure_date` in the past means that the vulnerability is known to be public.</td>
</tr>
<tr markdown="1">
<td markdown="span">Exploit Public (X) and Attacks Observed (A), together</td>
<td markdown="span">SSVC Exploitation value in `vulnerabilities[].metrics`: *None* for xa, *PoC* (public proof of concept) for Xa, *Active* for A</td>
<td markdown="span">Many to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Derived</td>
<td markdown="span">No change proposed. The value *Active* gives A but does not tell whether an exploit is public, so the reverse mapping leaves X unknown. When the issuing party is aware of active exploitation, the CSAF Vulnerability Report profile says that it SHOULD give it with this metric, as `Active` or `PoC`.</td>
</tr>
<tr markdown="1">
<td markdown="span">Exploit Public (X)</td>
<td markdown="span">`vulnerabilities[].threats[]` with `category` `exploit_status`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: both models keep exploit availability as a fact about the vulnerability, not as an event between parties. The `exploit_status` details are free text, so the reverse mapping needs judgment.</td>
</tr>
<tr markdown="1">
<td markdown="span">Attacks Observed (A)</td>
<td markdown="span">`observation` action, and the `exploitation` action that it can refer to</td>
<td markdown="span">One to many</td>
<td markdown="span">Interpretive</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed. CSAF divides A into two events: the `exploitation` by the attacker and the `observation` by the party that saw it. Vultron never names the attacker, because an attacker is not a participant. A projection records the `observation` and can add an `exploitation` by an `adversary` entity with no name.</td>
</tr>
<tr markdown="1">
<td markdown="span">Time of the first A event</td>
<td markdown="span">`vulnerabilities[].first_known_exploitation_dates[]`</td>
<td markdown="span">One to many</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed. CSAF gives the date for each product, and Vultron gives it for the case.</td>
</tr>
</tbody>
</table>

---

## Content objects

A Vultron case holds reports and notes ([Case Model](../../topics/case_lifecycle/case_model.md)).
The [`VulnerabilityReport`](../activitypub/objects.md#vulnerabilityreport) object has a `content` field that can hold any report format, and CSAF is one of the formats.
A CSAF document holds its vulnerabilities in `vulnerabilities[]`, each with identifiers, notes, references, and product status.

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>CSAF concept</th>
<th>Granularity</th>
<th>Vultron → CSAF</th>
<th>CSAF → Vultron</th>
<th>Proposed change</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">`VulnerabilityReport` `content`</td>
<td markdown="span">A full CSAF document, usually with the Vulnerability Report profile, `csaf_vulnerability_report`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">Vultron could identify CSAF content by its `mediaType`, and it could read the process fields of that content as claims by the sender. A claim changes the case only through a Vultron activity, which can be automatic. If nothing changes, an implementation can still read and use the CSAF content, but the protocol does not say how a claim in it, such as a proposed disclosure date, becomes a Vultron activity. Issue [#5131](https://github.com/CERTCC/Vultron/issues/5131){:target="_blank"} tracks this change.</td>
</tr>
<tr markdown="1">
<td markdown="span">`VulnerabilityRecord` on a case</td>
<td markdown="span">`vulnerabilities[]` with `cve` and `ids`</td>
<td markdown="span">Many to one</td>
<td markdown="span">Interpretive</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Vultron could add a list of vulnerability records to the case, which CM-05-003 already expects. Vultron could also let a `VulnerabilityRecord` carry a CSAF document or a CVE record as its content, with a `mediaType` that identifies the format. The record keeps the identifiers that Vultron uses, and Vultron reads the content as claims. A CSAF document for one vulnerability must also define the products that it refers to (mandatory test 6.1.1, Missing Definition of Product ID), so this change could include a CSAF profile for one vulnerability, without `involvement`, because the case holds the coordination history. If nothing changes, a projection finds the vulnerabilities only in the text of the reports, and it cannot set `dl_vuln_ids` reliably. Issue [#5132](https://github.com/CERTCC/Vultron/issues/5132){:target="_blank"} tracks this change.</td>
</tr>
<tr markdown="1">
<td markdown="span">`VulnerabilityRecord` `name` and `aliases`</td>
<td markdown="span">`vulnerabilities[].cve` and `vulnerabilities[].ids[]`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed. Both models treat identifiers from different systems as aliases for one vulnerability (CM-05-009).</td>
</tr>
<tr markdown="1">
<td markdown="span">`CaseReference`, with tags from the CVE reference vocabulary</td>
<td markdown="span">`vulnerabilities[].references[]` and `document.references[]`, with `category` `external` or `self`</td>
<td markdown="span">Many to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Vultron could add a list of references to the case, which CM-05-004 allows. `CaseReference` exists, but `VulnerabilityCase` has no field for it yet, which is the same gap as vulnerability records ([#5132](https://github.com/CERTCC/Vultron/issues/5132){:target="_blank"}). A projection puts the tag of a reference in its `summary`, because CSAF has no field for it.</td>
</tr>
<tr markdown="1">
<td markdown="span">Note, with no category</td>
<td markdown="span">`notes[]`, with a `category` such as `description`, `details`, `faq`, `general`, `summary`, or `other`</td>
<td markdown="span">One to many</td>
<td markdown="span">Interpretive</td>
<td markdown="span">Mechanical</td>
<td markdown="span">No change proposed: a projection selects the category of each note that it includes.</td>
</tr>
<tr markdown="1">
<td markdown="span">Advisory draft from the [publication pipeline](../../adr/0030-publish-leaf-draft-review-submit-pipeline.md) (ADR-0030)</td>
<td markdown="span">A CSAF document with the Security Advisory or Vulnerability Exploitability eXchange (VEX) profile</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: this is a projection at publication.</td>
</tr>
</tbody>
</table>

---

## Distribution and tracking

A CSAF document controls its own distribution with a Traffic Light Protocol (TLP) label and an optional sharing group, and it tracks its own versions in `document.tracking`.
Vultron controls who sees the case through entitlement and the embargo, and the case ledger gives the version of the case.

<table markdown="1">
<thead markdown="1">
<tr markdown="1">
<th>Vultron concept</th>
<th>CSAF concept</th>
<th>Granularity</th>
<th>Vultron → CSAF</th>
<th>CSAF → Vultron</th>
<th>Proposed change</th>
</tr>
</thead>
<tbody markdown="1">
<tr markdown="1">
<td markdown="span">Entitlement to case content and the embargo</td>
<td markdown="span">`document.distribution.tlp.label`</td>
<td markdown="span">Many to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed: a projection derives its TLP label from its content, its recipient, and the case state, as the [overview](overview.md#tlp-marks-a-projection-not-a-case) explains. The way TLP could appear in Vultron data and logic is an open concern ([#5133](https://github.com/CERTCC/Vultron/issues/5133){:target="_blank"}). If nothing changes, Vultron cannot enforce a received label that is stricter than its own entitlement rules.</td>
</tr>
<tr markdown="1">
<td markdown="span">Case</td>
<td markdown="span">`document.distribution.sharing_group.id`</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed. For a multi-party disclosure, CSAF advises "to use one ID per case". A projection mints one UUID version 4 for each case and uses it again, because CSAF requires a version 4 UUID for a closed sharing group.</td>
</tr>
<tr markdown="1">
<td markdown="span">Projecting participant</td>
<td markdown="span">`document.publisher`</td>
<td markdown="span">One to one</td>
<td markdown="span">Mechanical</td>
<td markdown="span">Interpretive</td>
<td markdown="span">No change proposed.</td>
</tr>
<tr markdown="1">
<td markdown="span">Ledger position of a projection</td>
<td markdown="span">`document.tracking.version` and `revision_history[]`</td>
<td markdown="span">One to one</td>
<td markdown="span">Derived</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: each new projection of the same case is a new revision of one CSAF document, and its revision history names the ledger position.</td>
</tr>
<tr markdown="1">
<td markdown="span">Case state at the ledger position</td>
<td markdown="span">`document.tracking.status`: `draft`, `interim`, or `final`</td>
<td markdown="span">Many to one</td>
<td markdown="span">Interpretive</td>
<td markdown="span">None</td>
<td markdown="span">No change proposed: the status describes the document, not the case. A projection during coordination is usually `interim`, because CSAF expects updates.</td>
</tr>
</tbody>
</table>

---

## Summary

| Principle | Statement |
|---|---|
| Unit of the mapping | A Vultron concept can map to any part of a CSAF document, not only to `involvement`. |
| Direction | A mapping is often mechanical from Vultron to CSAF and interpretive from CSAF to Vultron, because a received document is a claim. |
| Tense | Vultron state names tell what already occurred, and CSAF status values tell what occurs now. |
| Selection | A projection filters the case ledger, and the CSAF timeline holds the events that the issuing party selects. |
| Facts about the vulnerability | Both models keep exploit availability and public status in the vulnerability data, not in the timeline of events. |

## Further reading

- [CSAF 2.1 and Vultron](overview.md) — how a CSAF document relates to a Vultron case.
- [Proposals](proposals.md) — the changes that CSAF and Vultron could make, each with its reason and its cost if nothing changes.
- [Conclusions](conclusion.md) — what the comparison shows, and the issues that track the follow-up work.
- [Coverage differences](coverage.md) — concepts that only one of the two models has.

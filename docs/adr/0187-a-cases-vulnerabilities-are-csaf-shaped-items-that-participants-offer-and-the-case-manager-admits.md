---
status: accepted-provisional
date: 2026-11-10
created: 2026-11-10
updated: 2026-11-11
revision: 2
status_override: "Revision 2 (2026-11-11) was approved by Allen D. Householder in the #5132 planning session, before this record first merged: offers carry the act (#6251) and the reference-as-Link question moved to #6249."
lint_suppress: [phantom_symbol_ref, phantom_path_ref]
deciders: Allen D. Householder
consulted: Claude Opus 5.5
informed: []
stakeholder_type: [project-contributor]
---

# A Case's Vulnerabilities Are CSAF-Shaped Items That Participants Offer and the CASE_MANAGER Admits

## Context and Problem Statement

A case is about one or more vulnerabilities, but the Vultron case object had no place to say which.
The object model named a `VulnerabilityRecord` (an identifier with aliases) and a `CaseReference` (a URL with a title and tags), and the case-management requirements expected a case to hold them, yet no case field, message or tree ever used either.

Three needs met at that gap.
A case created from a CSAF vulnerability report should keep the vulnerabilities and references the report lists (ADR-0184).
A CVE ID is usually assigned during coordination, by a participant that is often not the Case Owner, so the case must learn of identifiers after it exists.
And a later projection of the case into a CSAF document needs a vulnerability list to fill.

Two existing rules also disagreed.
One said a record that carries a CVE ID must conform to the CVE JSON schema.
The other said no actor may interpret a record's identifier.
A record named by a CVE ID with no CVE data behind it, which is exactly what a CSAF report or a fresh CNA assignment yields, broke the first rule, and telling such a record apart broke the second.

## Decision Drivers

- A case can hold several vulnerabilities, so the identifiers that name the same vulnerability need a unit that groups them.
- No identifier namespace is the only one: CVE, CERT/CC VU#, GHSA, CNNVD and vendor IDs are all real.
- What Vultron keeps for a vulnerability should look like what CSAF puts in a vulnerability entry, so a CSAF report maps in and a CSAF projection maps out without translation.
- A participant's statement about the case is a claim until the CASE_MANAGER admits it, as with the other things participants assert.
- Two participants changing different parts of one vulnerability at the same time should not undo each other.
- Names must be easy to tell apart for a reader whose first language is not English.

## Considered Options

- Keep a bare identifier record with aliases, and add a case field for it.
- Put identifiers on the case as flat tags.
- A CSAF-shaped item per vulnerability, offered by participants and admitted by the CASE_MANAGER.

## Decision Outcome

Chosen option: "A CSAF-shaped item per vulnerability, offered by participants and admitted by the CASE_MANAGER", because it is the only option that groups identifiers per vulnerability, keeps every namespace equal, and matches CSAF field for field.

The decision has five parts.

1. **One item per vulnerability, named `VulnerabilityItem`.**
   The object is the case's entry for one vulnerability, the unit that groups its identifiers, its title, its notes and its references.
   CSAF's own schema calls these entries vulnerability information items.
   The former name, `VulnerabilityRecord`, suggested the issuer's external document, and it was hard to tell apart from `VulnerabilityReport`.
2. **The item takes CSAF's identity fields.**
   An item has a CVE ID, a list of identifiers each paired with the name of its tracking system, a title, notes, and references.
   Several identifiers on one item mean the same vulnerability.
   CSAF's per-vulnerability state, such as product status, scores, dates and remediations, is not part of the item.
3. **Identifier values are opaque, and the CVE field is the one typed field.**
   No actor parses an identifier's value or limits identifiers to one namespace.
   The CVE ID has its own field, as in CSAF, and that field may be checked against the CVE ID format because it is CVE-typed on purpose.
   The CVE JSON schema applies only to a CVE record carried as an item's content, never to a CVE ID alone.
4. **A participant offers; the CASE_MANAGER admits or declines.**
   A participant offers the act it proposes: adding a new item or a new reference to the case, or updating an item.
   An admitted offer's recorded change is then exactly the offered act.
   The CASE_MANAGER records the offer, then admits it, applying and recording the change, or declines it, and answers the sender either way.
   A deployment may admit offers automatically.
   The CASE_MANAGER itself fills items and references when it creates a case from a report.
5. **An update changes only the fields it carries.**
   An offered update replaces the fields it supplies and leaves the rest as they were, the partial-update meaning ActivityStreams gives `Update`.
   A full revision is an update that supplies every field.

Removing an item or a reference, relationships between items beyond "same vulnerability", and content documents carried by an item are not decided here.
Whether a reference becomes a kind of link is decided separately, and a link has no identity of its own, so that decision must settle how a reference is offered and listed.

### Consequences

- Good, because a CSAF report's vulnerabilities and references become case items and references with no translation, and a CSAF projection reads them back the same way.
- Good, because a CVE assignment is a one-field update to an existing item, so it neither duplicates the vulnerability nor waits for the Case Owner.
- Good, because the CVE schema rule and the opaque-identifier rule no longer conflict.
- Good, because two admitted updates to different fields of one item both survive.
- Bad, because a list field is replaced whole, so adding one identifier means sending the full revised list.
- Bad, because the rename touches the glossary, the requirements and the CSAF crosswalk.
- Neutral, because every admitted change is a ledger entry like any other case-file change, so replicas learn of items the way they learn of reports.

## Pros and Cons of the Options

### Keep a bare identifier record with aliases, and add a case field for it

- Good, because it is the smallest change.
- Bad, because a CSAF vulnerability's title, notes and references have no place to go.
- Bad, because an alias list cannot say which tracking system an identifier belongs to.
- Bad, because the CVE schema conflict stays.

### Put identifiers on the case as flat tags

- Good, because an identifier really is an opaque label.
- Bad, because a flat list cannot say which labels name the same vulnerability when a case holds several.

### A CSAF-shaped item per vulnerability, offered by participants and admitted by the CASE_MANAGER

- Good, because it groups identifiers per vulnerability and matches CSAF.
- Good, because participants' statements go through the same admit-or-decline step as their other claims.
- Bad, because the CASE_MANAGER's admit step must compare an offered update with the current item.

## More Information

The CSAF 2.1 schema is the source for the item's fields.
Its upstream is <https://github.com/oasis-tcs/csaf>, file `csaf_2.1/json_schema/csaf.json`, and this codebase pins it at commit `29b1e27` (CSD04) under `third_party/csaf/`.
The VXref 0.3 prototype of the FIRST VRDX SIG defines further relationships between vulnerability identifiers, such as superset, subset and overlap, and is the starting point for that later decision.
Its source is <https://github.com/FIRSTdotorg/vrdx-sig-vxref-wip>, schema `vxref/schema/vxref_schema_03.json`.

The review of the wire protocol against ActivityStreams 2.0 (Epic #6238, `notes/as2-vocabulary-alignment.md`) shapes three parts of this decision.
A proposed act travels as an offer of that act (#6251), identity decides between an update and a new object (#6250), and a reference may become a link (#6249).
There, `tag` lets another object refer to an item by reference, while the case's item list holds items by inclusion (#6248).

Source: #5132.

Generated spec requirements: `case-management.yaml` CM-05-008, CM-05-010, CM-05-018 to CM-05-021, and CM-34; `csaf-report-content.yaml` CSAF-03-008 and CSAF-03-009.

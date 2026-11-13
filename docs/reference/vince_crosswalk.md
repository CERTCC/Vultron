---
description: >
  How each field the VINCE API serves maps onto a Vultron case ledger: its
  Vultron counterpart, the type of mapping, the time it takes, and what VINCE
  never exposes.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 400
page_type: reference
subject: neutral
---

# VINCE and Vultron: Field Mapping

This page maps each field of a case in the Vulnerability Information and Coordination Environment (VINCE) onto a Vultron [case](glossary.md#core-cvd-concepts).
The CERT Coordination Center (CERT/CC) runs VINCE.
It is for readers who build or check the VINCE case reader, and for analysts who want to know where a state on the case shadow came from.
The VINCE case reader follows these rows.
Each row has a stable identifier, and every inference the reader makes names the row that produced it.

---

## What a translation returns

The case reader reads one VINCE case and returns a case reading.
A case reading has five parts:

1. a case ledger, in the same shape as a native Vultron [case ledger](../topics/case_lifecycle/case_manager_and_ledger.md);
2. a citation for each ledger entry, which names the VINCE record it came from;
3. the inferences: each entry whose state VINCE implied but did not state, with the row that produced it and a caveat;
4. the untranslated facts: each VINCE fact the reader saw but did not translate, with a reason;
5. the unobservable facts: what the VINCE application programming interface (API) never exposes, for any case.

[ADR-0197](../adr/0197-a-case-reading-reports-its-inferences-and-what-its-source-cannot-observe.md) records this shape.
The analysis reads an unobservable fact as unknown, never as false.

---

## How to read the tables

Each table has five columns.
**Row** is the stable identifier.
**VINCE source** gives the API path and field, relative to the case's API base `case/<vuid>/`.
**Vultron counterpart** gives what the reader writes.
**Type** gives the type of mapping.
**Time** gives the VINCE field that dates the entry.

| Type | Meaning |
|---|---|
| Mechanical | VINCE states the fact, and a fixed rule gives the result. |
| Derived | A fixed rule calculates the result from two or more VINCE facts. |
| Inferred | VINCE implies the result but does not state it. The reader lists the entry as an inference, with the row's caveat. |
| None | No Vultron counterpart exists. The reader returns the fact as untranslated. |

Every time comes from a VINCE record.
The reader never reads a clock.
An act that VINCE gives no time for takes the case's `created` time, and the reader lists it as an inference.

[Report Management (RM)](glossary.md#state-machines-and-status) state belongs to one participant.
No row sets a case-wide RM state.

---

## The case

| Row | VINCE source | Vultron counterpart | Type | Time |
|---|---|---|---|---|
| VINCE-CA-01 | `vuid`, `title`, `summary` | The `VulnerabilityCase`, its name and its summary | Mechanical | `created` |
| VINCE-CA-02 | The case's VINCE web address (URL) | A [case reference](glossary.md#domain-model-cvd-coordination) whose link relation is `issue-tracking` and whose link is the VINCE case URL | Mechanical | `created` |
| VINCE-CA-03 | `status` = `Inactive` | CERT/CC's RM state goes to Closed | Inferred | `modified` |

The caveat for VINCE-CA-03 is: "VINCE marks the case Inactive. The time is the case's last change, which may be later than the closure."
A `status` of `Active` adds no entry.
Any other `status` value is untranslated, with the reason *unknown value*.

---

## Participants and roles

| Row | VINCE source | Vultron counterpart | Type | Time |
|---|---|---|---|---|
| VINCE-PA-01 | The case itself | CERT/CC is a [participant](glossary.md#cvd-roles-and-participants) with the roles Coordinator, Case Owner and Case Manager | Mechanical | `created` |
| VINCE-PA-02 | `vendors/`: one item per vendor | A participant with the role Vendor | Mechanical | `date_added` |
| VINCE-PA-03 | `report/`, contact fields present | A participant with the role Reporter, identified by the shared contact | Mechanical | `date_submitted` |
| VINCE-PA-04 | `report/`, contact fields absent | A participant with the role Reporter, identified by an identity minted from the case and labeled "withheld" | Inferred | `date_submitted` |

VINCE leaves out the contact fields when the reporter did not agree to share them.
The caveat for VINCE-PA-04 is: "The reporter withheld their contact details. The identity is a placeholder."

---

## Report management

Each row sets the RM state of one participant.
A step that skips a state passes through it at the same time, for example Received to Valid to Accepted.

| Row | VINCE source | Vultron counterpart | Type | Time |
|---|---|---|---|---|
| VINCE-RM-01 | `report/date_submitted` | CERT/CC's RM state goes to Received | Mechanical | `date_submitted` |
| VINCE-RM-02 | The case's `created` | CERT/CC's RM state goes to Accepted | Inferred | `created` |
| VINCE-RM-03 | `report/date_submitted` | The Reporter's RM state goes to Accepted | Inferred | `date_submitted` |
| VINCE-RM-04 | `vendors/`: the vendor is on the case | That vendor's RM state goes to Received | Inferred | `date_added` |
| VINCE-RM-05 | `vendors/vuls/`: `status` = `Affected` for any vul | That vendor's RM state goes to Accepted | Inferred | Earliest `statement_date` with `Affected` |
| VINCE-RM-06 | `vendors/vuls/`: `status` = `Not Affected` for every vul | That vendor's RM state goes to Invalid | Inferred | Latest `statement_date` |
| VINCE-RM-07 | `vendors/vuls/`: any other mix, or `Unknown` | That vendor's RM state stays Received | Inferred | None |

The caveats are:

- VINCE-RM-02: "VINCE opens a case when CERT/CC accepts the report. VINCE does not record the acceptance."
- VINCE-RM-03: "A reporter accepts its own report when it submits it."
- VINCE-RM-04: "VINCE lists the vendor on the case. The notification itself is not in the VINCE API."
- VINCE-RM-05: "The vendor marked a vul Affected. VINCE does not record that the vendor accepted the report."
- VINCE-RM-06: "The vendor marked every vul Not Affected."
- VINCE-RM-07: "`Unknown` can mean the vendor said Unknown or did not share its status. The VINCE API does not tell the two apart."

A vendor status value other than `Affected`, `Not Affected` or `Unknown` is untranslated, with the reason *unknown value*.
A statement dated before its vendor's `date_added` is untranslated, with the reason *rule conflict*.

---

## Embargo

VINCE has no concept of [embargo consent](glossary.md#embargo-and-timing).
The coordinator sets a planned publication date, and nobody records an agreement to it.

| Row | VINCE source | Vultron counterpart | Type | Time |
|---|---|---|---|---|
| VINCE-EM-01 | The case's `due_date` | An active embargo, proposed by CERT/CC, that ends at `due_date` | Inferred | `created` |
| VINCE-EM-02 | The case's `due_date`, for each vendor at Received or later | That vendor accepted the embargo | Inferred | The later of `created` and the vendor's `date_added` |

The caveats are:

- VINCE-EM-01: "VINCE records a planned publication date. VINCE does not record when the date was set."
- VINCE-EM-02: "VINCE does not track embargo consent. Vultron infers the vendor's agreement from its place on the case."

A case with no `due_date` has no embargo.

---

## Case state

The [case state](../topics/process_models/cs/cs_model.md) flags for public awareness (P), exploit public (X) and attacks observed (A) come from two sources.
The first source is the reporter's own answers on the report form, which are true from the start of the case.
The second source is CERT/CC's vulnerability note.
Each vendor's vendor awareness (V) follows from that vendor's RM state Received.

| Row | VINCE source | Vultron counterpart | Type | Time |
|---|---|---|---|---|
| VINCE-CS-01 | `report/vul_public` = true | P, stated by the Reporter | Mechanical | `date_submitted` |
| VINCE-CS-02 | `report/exploit_references` not empty | X, stated by the Reporter | Mechanical | `date_submitted` |
| VINCE-CS-03 | `report/vul_exploited` = true | A, stated by the Reporter | Mechanical | `date_submitted` |
| VINCE-CS-04 | `note/published` = true | CERT/CC's participant status states P. CERT/CC is the Case Manager, so the case status states P too | Derived | `note/datefirstpublished` |

Fix ready (F) and fix deployed (D) have no source in the VINCE API.
They are unobservable.

---

## Content

| Row | VINCE source | Vultron counterpart | Type | Time |
|---|---|---|---|---|
| VINCE-CT-01 | `vuls/`: one item per vul, with `name`, `cve` and `description` | A [vulnerability item](glossary.md#domain-model-cvd-coordination), with its Common Vulnerabilities and Exposures (CVE) ID when `cve` is present | Mechanical | `date_added` |
| VINCE-CT-02 | `posts/`: one item per post | A case note, credited to the participant whose organization is the post author's `org` | Mechanical | `created` |
| VINCE-CT-03 | `report/`: the vendor, product and vulnerability description fields | The content of the report | Mechanical | `date_submitted` |
| VINCE-CT-04 | `posts/pinned`, `note/revision`, `note/dateupdated` | None | None | None |

A post whose author's organization matches no participant is untranslated, with the reason *no counterpart*.

---

## Not read

The reader does not read `csaf/`.
VINCE builds that document from the same records the rows above read, so it adds no fact.

---

## Unobservable

The VINCE API serves no record of these facts, for any case.
The reader declares them in every case reading, and the analysis reads each one as unknown.

| Fact | Why it is unobservable |
|---|---|
| Fix ready (F), fix deployed (D) | No VINCE field records them. |
| A vendor was notified, a vendor viewed the case | VINCE records these in its case activity log, which only the coordinator web pages show. |
| CERT/CC's own RM steps after the case opens, other than closure | The case activity log holds them. |
| A message, a task or a publish event in the case activity log | The case activity log holds them. |
| When `due_date` was set or changed | VINCE stores only the case's last `modified` time. |

---

## Untranslated reasons

| Reason | Meaning |
|---|---|
| Unknown value | The field holds a value no row names. |
| No counterpart | The fact has no Vultron counterpart. |
| Rule conflict | The inputs of a row contradict each other. |
| No time | The fact has no time, and no row names a time for it. |

---

## Further reading

- [ADR-0191](../adr/0191-an-outside-system-reaches-the-core-through-a-read-only-case-reader-port.md) decides the read-only case reader port.
- [ADR-0190](../adr/0190-shadow-mode-is-a-standalone-read-only-advisor-that-translates-a-case-on-request.md) decides the case shadow.
- The [VINCE API documentation](https://certcc.github.io/VINCE-docs/VINCE-API/){:target="_blank"} describes the endpoints.

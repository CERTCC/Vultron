---
status: accepted-provisional
date: 2026-11-12
created: 2026-11-12
updated: 2026-11-12
revision: 1
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
---

# A Redacted Marker Builds a Preview and Appears Nowhere Else

## Context and Problem Statement

A JSON or Pydantic model cannot tell three states of a field apart.
An absent field means the sender does not know the value, or it does not apply.
A `null` field exists and has no value.
A redacted field has a value the sender is deliberately withholding from this recipient.

The idea of an explicit redaction marker, such as `{"type": "Redacted", "summary": "Embargo pending"}` in place of a value, dates from a time when any object could travel as a partial stub.
Since then the stub form was narrowed to the case alone, and the case stub is planned to become the case's ActivityStreams `preview`: a limited view of an object, shown to a recipient not yet entitled to the whole of it.
The case is the first object with a preview; a report, a reserved vul record or a draft advisory may follow.

**Where may a redaction marker appear, and is it the same thing as hiding a participant's identity?**

## Decision Drivers

- An invitee decides whether to join a case from the invitation alone, so it gains from knowing that a value exists but is withheld, as against not existing yet.
- Telling a recipient that a value exists is itself a disclosure: "an exploit is known, details withheld" is often the sensitive fact.
- A full domain object validates its required fields at construction, and a stored case is the authority for the case.
- The case ledger is hash-chained and its entries reach every active participant alike, so one participant cannot be sent a different copy of an entry.
- A participant whose identity is hidden must still be reachable by the others.

## Considered Options

- A marker allowed in any field of any object.
- A marker allowed only in the fields of a preview, as one way to build the preview.
- No marker: a preview leaves every withheld field out.
- Redaction as the mechanism for keeping a participant anonymous.

## Decision Outcome

Chosen option: "A marker allowed only in the fields of a preview, as one way to build the preview", because it lets an invitee learn that a withheld value exists while a full object, and so every stored case, keeps strict types and never holds a marker.

A sender builds a preview from the full object and makes one of three choices for each field: show the value, redact it, or leave it out.
Leaving a field out says nothing, and is the default.
Redacting a field says that it has a value, so a sender redacts only where the recipient needs that fact.
A receiver refuses a marker anywhere other than a preview's field.

Anonymity is a different concept and is not built on this marker.
A redaction leaves a visible gap where a value exists, and the gap is usually filled once the recipient is admitted.
An anonymized participant is given a working stand-in identity, an alias a Coordinator relays through, that the others can address.
Because the case and its ledger are shared, the alias is what the case holds, and the real identity stays with the Coordinator outside the case.

### Consequences

- Good, because a recipient can tell "this case has no score yet" from "this case has a score you cannot see yet".
- Good, because full objects keep their field types, so no handler or stored record has to cope with a marker in place of a value.
- Good, because the default of leaving a field out discloses nothing a sender did not choose to disclose.
- Bad, because a field of a full object cannot be withheld while the rest of the object is sent; that need, where it exists, is met by an alias or by keeping the value outside the case.
- Bad, because every preview type must declare which of its fields may carry the marker.

## Validation

A receiver test confirms that a marker in a full object's field, or as an activity's own object, is refused, naming the position.
A receiver test confirms that a marker in a preview's field parses as the marker, not as `null`.

## Pros and Cons of the Options

### A marker allowed in any field of any object

- Good, because a sender could withhold one field of a full object it otherwise shares.
- Bad, because every field of every domain type would widen to "a value or a marker", including required ones, which weakens construction-time validation.
- Bad, because a marker could reach the CASE_MANAGER's canonical case and every replica of it.
- Bad, because the shared hash-chained ledger cannot carry a different redaction for each recipient, so the marker would hide the value from the whole case anyway.

### A marker allowed only in the fields of a preview

- Good, because a preview is already a limited view that is never the object, so a marker never becomes part of a real object.
- Good, because the recipient can be told that a withheld value exists.
- Neutral, because it needs a preview to exist; the case stub is the only one today.

### No marker: a preview leaves every withheld field out

- Good, because it adds no wire term.
- Bad, because a recipient cannot tell a withheld value from one that does not exist yet.

### Redaction as the mechanism for keeping a participant anonymous

- Good, because it would reuse one mechanism.
- Bad, because a redacted identity cannot be addressed, so the others could not reach the participant.
- Bad, because anonymity is permanent for its audience, while redaction is lifted when the recipient is admitted.

## More Information

Planned in #4568; the case preview is #6244, wider previews are #6257, and pseudonymous reporting is #2562.
The marker is declared as a Vultron extension term under the rule #5743 writes.

Generated spec requirements: `message-validation.yaml` MV-12-001 through MV-12-005.

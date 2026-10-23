## Annex C — Notation Reference [I]

The conventions this specification uses for state names and case-state notation are stated at [§1.4 Document Conventions](introduction.md#14-document-conventions).
This annex collects the mathematical and diagram notation used in the formal treatment, and the notation for writing a Wire Activity.

{% include-markdown "../notation.md" start="<!-- notation-math-start -->" end="<!-- notation-math-end -->" heading-offset=1 %}

### Wire Activity Notation

A [Wire Activity](../glossary.md#messaging-and-protocol) is an ActivityStreams 2.0 (AS2) activity of a given shape.
This specification and the documentation write one as `Verb(Object)[field=Value]`.

- **Verb.** The activity's own AS2 `type` comes first: `Offer`, `Accept`, `Add`.
- **Object in parentheses.** The parentheses hold the type of the activity's `object`: `Offer(VulnerabilityReport)` is an `Offer` whose `object` is a `VulnerabilityReport`.
- **Nesting.** When the object is itself an activity, the parentheses hold that activity in the same notation: `Accept(Offer(VulnerabilityReport))` is an `Accept` whose `object` is an `Offer` of a `VulnerabilityReport`.
- **Bracketed fields.** Brackets after an activity name its other fields that tell occasions apart, each as `field=Value`, with a comma between two of them.
  The brackets qualify the activity they follow: in `Add(CaseStatus)[target=VulnerabilityCase]` the `target` is the `Add`'s, and in `Accept(Invite(Event)[context=VulnerabilityCase])` the `context` is the `Invite`'s.
  A value is the type the field holds, or a literal value such as a state name.
  Written without its brackets, as `Invite(Event)`, an activity names every occasion of that shape; a field that tells no occasions apart is described in the surrounding text, not in the notation.
- **Type names.** Each name is a `type` value as it appears on the wire, never the name of a class in an implementation.
  Where a receiver accepts an AS2 type or the Vultron type that extends it, the notation writes the AS2 type: `Invite(Event)` names an embargo invitation whether its object is sent with `type` `Event` or `EmbargoEvent`.
  Where a receiver accepts only the Vultron type, the notation writes that type: `Create(EmbargoEvent)`.
- **No addressing.** The notation describes the activity's shape, not where it goes.
  Recipients, roles and the sender are never written in it; an occasion table gives them in its "Send to" and "Sent by" columns ([Message Types](../messages/index.md)).

A Wire Activity is the shape a sender puts on the wire.
It does not name a formal protocol message: the [Protocol Shorthand](../glossary.md#messaging-and-protocol), such as `RS` or `EP`, does.

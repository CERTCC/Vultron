# Vultron AS Activity Guides

{% include-markdown "../../../includes/not_normative.md" %}

These guides show how to carry out each Vultron protocol task with ActivityStreams (AS)
activities. The wire vocabulary is ActivityStreams 2.0 (AS2). Each one states its
prerequisites, gives the activities to send in order, and says how to confirm the task
landed. They assume you are implementing or operating a Vultron actor, not learning the
protocol for the first time.

Two neighboring sections carry the material these guides deliberately leave out. The
wire format of every activity — fields, discriminators, and a rendered
example — is in [Message Types](../../../reference/messages/index.md).
The reasoning behind the verb choices is in
[Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md).
A full mapping of Vultron to ActivityStreams is in the
[Vultron ActivityStreams Ontology](../../../reference/ontology/vultron_as.md).

If you want a guided first pass rather than a task recipe, start with
[Tutorials](../../../tutorials/index.md).

---

## Report and case lifecycle

<div class="grid cards" markdown>

- :material-message-alert: [How to Report a Vulnerability](./report_vulnerability.md)
- :material-text-box-check: [How to Acknowledge a Report](./acknowledge.md)
- :material-briefcase-plus: [How to Initialize a Case](./initialize_case.md)
- :material-briefcase-edit: [How to Advance a Case Through Report Management](./manage_case.md)
- :material-message-plus: [How to Post a Status Update or a Case Note](./status_updates.md)

</div>

---

## Participants and roles

<div class="grid cards" markdown>

- :fontawesome-solid-person-circle-plus: [How to Suggest an Actor for a Case](./suggest_actor.md)
- :fontawesome-solid-people-arrows: [How to Invite an Actor to a Case](./invite_actor.md)
- :fontawesome-solid-person-circle-check: [How to Seat a Participant on an Existing Case](./initialize_participant.md)
- :fontawesome-solid-people-group: [How to Manage a Case Roster](./manage_participants.md)
- :fontawesome-solid-user-shield: [How to Delegate a Role to Another Participant](./role_delegation.md)

</div>

---

## Embargoes and faults

<div class="grid cards" markdown>

- :material-calendar-start: [How to Establish an Embargo](./establish_embargo.md)
- :material-calendar-edit: [How to Revise or Terminate an Embargo](./manage_embargo.md)
- :material-lightning-bolt-circle: [How to Report a Protocol Fault](./error.md)

</div>

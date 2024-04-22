# Activities

{% include-markdown "../../../includes/not_normative.md" %}

Activities are the core of the ActivityPub protocol. They are used to
represent actions that are performed by actors. The ActivityStreams
vocabulary defines a number of activities, and we extend these with specific
activities that are used in the Vultron AS vocabulary. So far, we have found the
ActivityStreams vocabulary to be sufficient for our needs, so our extensions
are limited to specifying the types of activities, actors, and objects that
are used in the Vultron protocol.

A full mapping of Vultron to ActivityStreams is available in the
[Vultron ActivityStreams Ontology](../../../reference/ontology/vultron_as.md).

!!! note "Design Goals"

    Our goal in each of these activity definitions is to

    - Avoid creating new activity types when an existing activity type can be used.
    - Avoid creating defined activity types with the same objects and targets to avoid
    confusion. Each activity type / object / target combination should have a
    single meaning within the protocol.

For documentation purposes, we have divided the Vultron AS activities by user flow.
Each of these user flows shows the activities that are used to perform a specific
task. The user flows are:

<div class="grid cards" markdown>

- :material-message-alert: [Reporting a Vulnerability](./report_vulnerability.md)
- :material-text-box-check: [Acknowledging a Report](./acknowledge.md)
- :material-briefcase-plus: [Initializing a Case](./initialize_case.md)
- :material-briefcase-edit: [Managing a Case](./manage_case.md)
- :fontawesome-solid-person-circle-plus: [Suggest Actor for Case](./suggest_actor.md)
- :fontawesome-solid-people-arrows: [Inviting an Actor to a Case](./invite_actor.md)
- :fontawesome-solid-person-circle-check: [Initializing a Participant](./initialize_participant.md)
- :fontawesome-solid-people-group: [Managing Participants](./manage_participants.md)
- :material-calendar-start: [Establishing an Embargo](./establish_embargo.md)
- :material-calendar-edit: [Managing an Embargo](./manage_embargo.md)
- :material-message-plus: [Status Updates](./status_updates.md)
- :fontawesome-solid-arrow-right-to-city: [Transferring Case Ownership](./transfer_ownership.md)
- :material-lightning-bolt-circle: [Error Handling](./error.md)

</div>

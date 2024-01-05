# Activities

Activities are the core of the ActivityPub protocol. They are used to
represent actions that are performed by actors. The ActivityStreams
vocabulary defines a number of activities, and we extend these with specific
activities that are used in the Vultron AS vocabulary. So far, we have found the
ActivityStreams vocabulary to be sufficient for our needs, so our extensions
are limited to specifying the types of activities, actors, and objects that
are used in the Vultron protocol.

A full mapping of Vultron to ActivityStreams is available in the
[Vultron ActivityStreams Ontology](../../../reference/ontology/vultron_as.md).

{== TODO this really needs to be organized by user flow ==}

!!! note "Design Goals"

    Our goal in each of these activity definitions is to

    - Avoid creating new activity types when an existing activity type can be used.
    - Avoid creating defined activity types with the same objects and targets to avoid
    confusion. Each activity type / object / target combination should have a
    single meaning within the protocol.

{% include-markdown "./_report_vulnerability.md" heading-offset=1 %}

{% include-markdown "./_initialize_case.md" heading-offset=1 %}
{% include-markdown "./_manage_case.md" heading-offset=1 %}
{% include-markdown "./_transfer_ownership.md" heading-offset=1 %}

{% include-markdown "./_suggest_actor.md" heading-offset=1 %}
{% include-markdown "./_invite_actor.md" heading-offset=1 %}
{% include-markdown "./_initialize_participant.md" heading-offset=1 %}
{% include-markdown "./_manage_participants.md" heading-offset=1 %}

{% include-markdown "./_establish_embargo.md" heading-offset=1 %}
{% include-markdown "./_manage_embargo.md" heading-offset=1 %}

{% include-markdown "./_status_updates.md" heading-offset=1 %}

{% include-markdown "./_acknowledge.md" heading-offset=1 %}

{% include-markdown "./_error.md" heading-offset=1 %}

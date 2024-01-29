# Initializing a Case

{% include-markdown "../../../includes/not_normative.md" %}

The process of initializing a case involves creating the case and then adding at least one
report, at least one participant, and any notes to the case.

```mermaid
flowchart LR
    subgraph as:Create
        CreateCase
    end
    subgraph as:Add
        AddReportToCase
        AddParticipantToCase
        AddNoteToCase
    end
    CreateCase --> AddReportToCase
    CreateCase --> AddParticipantToCase
    CreateCase --> AddNoteToCase
```

!!! tip "Combining steps"

    It is not always necessary for these steps to be performed individually.
    It would be reasonable to create a case with the report and appropriate
    participants and notes all in the initial case object. We have broken
    these steps out individually to make it easier to understand the
    process.

{% include-markdown "./_create_case.md" heading-offset=1 %}
{% include-markdown "./_add_report_to_case.md" heading-offset=1 %}
{% include-markdown "./_add_participant_to_case.md" heading-offset=1 %}
{% include-markdown "./_add_note_to_case.md" heading-offset=1 %}

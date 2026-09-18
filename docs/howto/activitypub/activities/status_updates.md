# Status Updates and Comments

{% include-markdown "../../../includes/not_normative.md" %}

This section covers activities used to update the status of a
case, or to add a comment to a case.

Each of these follows the same two-step shape: `as:Create` mints the object, and
`as:Add` attaches it. A status update to a participant can lead to a status
update to the case, and a note can lead to a status update on either.

!!! tip inline end "See also"

    Descriptions of the [`CaseStatus`](../../../reference/activitypub/objects.md#casestatus) and
    [`ParticipantStatus`](../../../reference/activitypub/objects.md#participantstatus), and [`CaseParticipant`](../../../reference/activitypub/objects.md#caseparticipant)
    objects can be found in the [Objects](../../../reference/activitypub/objects.md) section.
    `as:Note` is described there as well.

For the activity-graph diagram, why the Create/Add split exists, and when an
implementation may collapse the two into a single `as:Create` carrying a
`target`, see
[Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md).

## Create Status

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_case_status, json2md

print(json2md(create_case_status()))
```

## Add Status to Case

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_case, json2md

print(json2md(add_status_to_case()))
```

## Create Participant Status

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_participant_status, json2md

print(json2md(create_participant_status()))
```

## Add Status to Participant

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_status_to_participant, json2md

print(json2md(add_status_to_participant()))
```

## Create Note

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import create_note, json2md

print(json2md(create_note()))
```

## Add Note to Case

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import add_note_to_case, json2md

print(json2md(add_note_to_case()))
```

## Demo

!!! example "Try it: `vultron-demo status-updates`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo status-updates
    ```

    Or with Docker Compose:

    ```bash
    DEMO=status-updates docker compose -f docker/docker-compose.yml run --rm demo
    ```

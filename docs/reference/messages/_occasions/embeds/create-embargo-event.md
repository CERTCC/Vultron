<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create embargo event"

    Carries the new embargo in full, its start and end times included. It follows the case's genesis entry.

    - **When…** the Case Manager has created a case and, with it, an embargo such as the default embargo
    - **Send:** `Create(Event)`
    - **Send to:** a participant
    - **Sent by:** not handled
    - **Reference:** [Create embargo event](../../em.md#create-embargo-event)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            create_embargo_event,
            json2md,
        )

        print(json2md(create_embargo_event()))
        ```

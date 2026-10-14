<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create embargo event"

    Mints the embargo event that carries the proposed terms. It precedes the Invite that proposes them.

    - **When…** a Participant has drafted embargo terms it is about to propose
    - **Send:** `Create(Event)[context=VulnerabilityCase|VulnerabilityReport]`
    - **Sent by:** the case owner
    - **Reference:** [Create embargo event](../../em.md#create-embargo-event)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            create_embargo_event,
            json2md,
        )

        print(json2md(create_embargo_event()))
        ```

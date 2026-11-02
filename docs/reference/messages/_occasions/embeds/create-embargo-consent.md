<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Create embargo consent"

    Carries the new consent row in full: the embargo it answers, the participant it belongs to and its state.

    - **When…** the CASE_MANAGER creates a participant's consent row for an embargo, such as the UNINVITED row a proposal writes
    - **Send:** `Create(EmbargoConsent)`
    - **Send to:** a participant
    - **Sent by:** internal to the CASE_MANAGER
    - **Reference:** [Create embargo consent](../../em.md#create-embargo-consent)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            create_embargo_consent,
            json2md,
        )

        print(json2md(create_embargo_consent()))
        ```

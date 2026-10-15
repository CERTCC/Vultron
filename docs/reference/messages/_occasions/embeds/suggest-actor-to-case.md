<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Suggest actor to case"

    Recommends an actor to the Case Manager for the case named by the target.

    - **When…** a Participant suggests an actor that the case should include
    - **Send:** `Offer(Actor)[target=VulnerabilityCase]`
    - **Sent by:** a participant
    - **Reference:** [Suggest actor to case](../../general.md#suggest-actor-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            recommend_actor,
            json2md,
        )

        print(json2md(recommend_actor()))
        ```

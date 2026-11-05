<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Accept actor recommendation"

    Accepts the recommender's suggestion, with `inReplyTo` naming it. The Case Manager sends it once the Case Owner approves, or at once when the suggested actor is already invited or has joined.

    - **When…** the Case Manager tells a recommender that the actor it suggested will be invited
    - **Send:** `Accept(Offer(Actor)[target=VulnerabilityCase])`
    - **Send to:** a participant
    - **Sent by:** the case manager
    - **Reference:** [Accept actor recommendation](../../general.md#accept-actor-recommendation)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            accept_actor_recommendation,
            json2md,
        )

        print(json2md(accept_actor_recommendation()))
        ```

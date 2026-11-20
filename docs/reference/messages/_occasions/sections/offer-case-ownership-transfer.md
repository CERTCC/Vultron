<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Offer case ownership transfer { #offer-case-ownership-transfer }

Offers the case to the actor named by the target, on the Case Owner's behalf: `attributedTo` names the owner and `inReplyTo` the owner's own Offer. This is the offer the new owner accepts or rejects. It carries the owner's `endTime`, if any.

=== "Details"

    - **When…** the CASE_MANAGER offers the case to the actor the Case Owner named
    - **Send:** `Offer(VulnerabilityCase)`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("offer_case_ownership_transfer"))
    ```

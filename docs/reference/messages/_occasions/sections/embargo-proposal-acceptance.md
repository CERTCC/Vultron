<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Embargo Proposal Acceptance (EA) { #embargo-proposal-acceptance }

Activates the proposal for the case. Any other open proposal stays open as a revision.

=== "Details"

    - **When…** the Case Owner decides to activate a proposed embargo for a case with no active embargo
    - **Send:** `Accept(EmbargoEvent)[target=VulnerabilityCase]`
    - **Send to:** the case manager
    - **Sent by:** the case owner
    - **Distinguished by:** EM state `PROPOSED`
    - **Seen in:** [How to Establish an Embargo](../../../../howto/activitypub/activities/establish_embargo.md)
    - **Formal definition:** [Embargo Proposal Acceptance (EA)](../../../formal_protocol/messages.md#em-message-types)
    - **Mapping status:** [collapse](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        activate_embargo,
        json2md,
    )

    print(json2md(activate_embargo()))
    ```

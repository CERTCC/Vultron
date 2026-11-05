<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Create embargo consent { #create-embargo-consent }

Carries the new consent row in full: the embargo it answers, the participant it belongs to and its state.

=== "Details"

    - **When…** the Case Manager creates a participant's consent row for an embargo, such as the UNINVITED row a proposal writes
    - **Send:** `Create(EmbargoConsent)`
    - **Send to:** a participant
    - **Sent by:** internal to the case manager
    - **Mapping status:** [none](../../index.md#mapping-status)

    Each participant learns of it from the case ledger, so it is addressed to nobody.

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        create_embargo_consent,
        json2md,
    )

    print(json2md(create_embargo_consent()))
    ```

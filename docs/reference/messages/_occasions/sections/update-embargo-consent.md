<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Update embargo consent { #update-embargo-consent }

Carries the changed consent row in full. A Case Manager with an embargo stake of its own records a change of its own consent this way, never as a Reject of the Invite.

=== "Details"

    - **When…** the Case Manager changes a participant's consent row, such as an invitation timing out, the rows carried over at activation or a change of its own consent
    - **Send:** `Update(EmbargoConsent)`
    - **Send to:** a participant
    - **Sent by:** internal to the case manager
    - **Mapping status:** [none](../../index.md#mapping-status)

    Each participant learns of it from the case ledger, so it is addressed to nobody.

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        update_embargo_consent,
        json2md,
    )

    print(json2md(update_embargo_consent()))
    ```

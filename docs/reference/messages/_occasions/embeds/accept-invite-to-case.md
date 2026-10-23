<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Accept invite to case"

    Accepts the Stub Invite. The actor joins the case at RM Received.

    - **When…** an invited actor agrees to join the case
    - **Send:** `Accept(Invite(Actor)[target=VulnerabilityCaseStub])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Reference:** [Accept invite to case](../../case_management.md#accept-invite-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            accept_invite_to_case,
            json2md,
        )

        print(json2md(accept_invite_to_case()))
        ```

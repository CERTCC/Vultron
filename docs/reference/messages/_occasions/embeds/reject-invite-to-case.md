<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject invite to case"

    Rejects the Stub Invite, which closes the invitee's participant record.

    - **When…** an invited actor declines to join the case
    - **Send:** `Reject(Invite(Actor)[target=VulnerabilityCaseStub])`
    - **Sent by:** the invitee
    - **Reference:** [Reject invite to case](../../case_management.md#reject-invite-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_invite_to_case,
            json2md,
        )

        print(json2md(reject_invite_to_case()))
        ```

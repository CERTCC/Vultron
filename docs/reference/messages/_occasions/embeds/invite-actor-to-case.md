<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Invite actor to case"

    Sends a Stub Invite carrying the case stub and the embargo terms the invitee would agree to.

    - **When…** the Case Manager invites an actor to join the case
    - **Send:** `Invite(Actor)[target=VulnerabilityCaseStub]`
    - **Send to:** a participant
    - **Sent by:** not yet checked
    - **Reference:** [Invite actor to case](../../case_management.md#invite-actor-to-case)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            rm_invite_to_case,
            json2md,
        )

        print(json2md(rm_invite_to_case()))
        ```

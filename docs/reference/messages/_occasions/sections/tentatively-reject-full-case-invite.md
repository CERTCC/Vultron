<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Tentatively reject Full-Case Invite { #tentatively-reject-full-case-invite }

Tentatively rejects the Full-Case Invite, which records RM Invalid. It carries the sender's own ledger position.

=== "Details"

    - **When…** a Participant asked by a Full-Case Invite judges the case invalid
    - **Send:** `TentativeReject(Invite(Actor)[target=VulnerabilityCase])`
    - **Send to:** the case manager
    - **Sent by:** the invitee
    - **Seen in:** [How to Manage a Case Roster](../../../../howto/activitypub/activities/manage_participants.md)
    - **Formal definition:** [Report Invalid (RI)](../../../formal_protocol/messages.md#rm-message-types)
    - **Mapping status:** [expansion](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        tentative_reject_full_case_invite,
        json2md,
    )

    print(json2md(tentative_reject_full_case_invite()))
    ```

<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Read case ledger entry { #read-case-ledger-entry }

States the last ledger entry the sender has applied. The Case Manager resends every Invite the sender has not answered and, for an active participant, records the position as the sender's acknowledged position and replays every entry after it.

=== "Details"

    - **When…** a Participant checks that its ledger is current, such as after a restart
    - **Send:** `Read(CaseLedgerEntry)`
    - **Send to:** the case manager
    - **Sent by:** a participant
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        read_case_ledger_entry,
        json2md,
    )

    print(json2md(read_case_ledger_entry()))
    ```

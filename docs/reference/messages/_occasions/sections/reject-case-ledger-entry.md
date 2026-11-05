<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Reject case ledger entry { #reject-case-ledger-entry }

Tells the Case Manager that the entry's previous hash does not match the sender's ledger tail, and the Case Manager replays every entry after the last accepted hash. This negative acknowledgment serves the purpose of the formal EK and CK messages.

=== "Details"

    - **When…** a received ledger entry does not chain onto the Participant's own ledger
    - **Send:** `Reject(CaseLedgerEntry)`
    - **Send to:** the case manager
    - **Sent by:** an active participant, including one that has left the case
    - **Mapping status:** [evolved](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import (
        reject_case_ledger_entry,
        json2md,
    )

    print(json2md(reject_case_ledger_entry()))
    ```

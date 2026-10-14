<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

!!! info "Reject case ledger entry"

    Tells the Case Manager that the entry's previous hash does not match the sender's ledger tail, and the Case Manager replays every entry after the last accepted hash. This negative acknowledgment serves the purpose of the formal EK and CK messages.

    - **When…** a received ledger entry does not chain onto the Participant's own ledger
    - **Send:** `Reject(CaseLedgerEntry)`
    - **Sent by:** an active participant
    - **Reference:** [Reject case ledger entry](../../ledger_replication.md#reject-case-ledger-entry)

    ??? example "Example activity"

        ```python exec="true" idprefix=""
        from vultron.wire.as2.vocab.examples.vocab_examples import (
            reject_case_ledger_entry,
            json2md,
        )

        print(json2md(reject_case_ledger_entry()))
        ```

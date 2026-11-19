<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Add case ledger entry { #add-case-ledger-entry }

Fans out the newly committed ledger entry to each active participant, as an Add to the case's ledger that names the committed act in inReplyTo: the positive acknowledgment of that act.

=== "Details"

    - **When…** the CASE_MANAGER has committed a case event to the case ledger
    - **Send:** `Add(CaseLedgerEntry)`
    - **Send to:** a participant
    - **Sent by:** the CASE_MANAGER
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("add_case_ledger_entry"))
    ```

<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Read case ledger { #read-case-ledger }

States the sender's position in the case's ledger: its last entry, or index -1 when it holds none. The CASE_MANAGER resends every Invite the sender has not answered and, for an active participant, records the position as the sender's acknowledged position and replays every entry after it, the whole ledger for index -1.

=== "Details"

    - **When…** a Participant checks that its ledger is current, such as after a restart, or holds a case but none of its entries
    - **Send:** `Read(OrderedCollection)[context=VulnerabilityCase]`
    - **Send to:** the CASE_MANAGER
    - **Sent by:** a participant
    - **Mapping status:** [none](../../index.md#mapping-status)

=== "Example activity"

    ```python exec="true" idprefix=""
    from vultron.wire.as2.vocab.examples.vocab_examples import render_example

    print(render_example("read_case_ledger"))
    ```

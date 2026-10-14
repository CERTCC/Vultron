<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

## Announce case ledger entry { #announce-case-ledger-entry }

Fans out the newly committed ledger entry to each active participant.

- **When…** the Case Manager has committed a case event to the case ledger
- **Send:** `Announce(CaseLedgerEntry)`
- **Sent by:** the case manager
- **Mapping status:** [none](../../index.md#mapping-status)

```python exec="true" idprefix=""
from vultron.wire.as2.vocab.examples.vocab_examples import (
    announce_case_ledger_entry,
    json2md,
)

print(json2md(announce_case_ledger_entry()))
```

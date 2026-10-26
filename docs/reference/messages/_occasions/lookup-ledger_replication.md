<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| the Case Manager has committed a case event to the case ledger | `Announce(CaseLedgerEntry)` | a participant | the case manager | — | [Announce case ledger entry](../ledger_replication.md#announce-case-ledger-entry) |
| a received ledger entry does not chain onto the Participant's own ledger | `Reject(CaseLedgerEntry)` | the case manager | an active participant, including one that has left the case | — | [Reject case ledger entry](../ledger_replication.md#reject-case-ledger-entry) |
| a Participant checks that its ledger is current, such as after a restart | `Read(CaseLedgerEntry)` | the case manager | an active participant | — | [Read case ledger entry](../ledger_replication.md#read-case-ledger-entry) |

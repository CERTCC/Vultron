**Case Actor** — the actor that holds the [CASE_MANAGER](../case_lifecycle/case_manager_and_ledger.md) role for this case; it writes every canonical ledger entry and fans it out to the participants.
  In the demo it runs on the dedicated `case-actor` container, but its authority comes from the role, not from where it runs.

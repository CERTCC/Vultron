# Acknowledging a Report

A recipient acknowledges a submitted report by sending
`Read(Offer(VulnerabilityReport))` — the `RmReadReport` activity, a subclass of
`as:Read`.
Use it when you want to confirm that a report arrived without yet declaring it
valid or invalid.
If you are ready to declare a verdict, send `RmValidateReport` (`as:Accept`) or
`RmInvalidateReport` (`as:TentativeReject`) instead; either one implies the
report was read.

- For the full wire reference, including the mapping to the formal `RK` message
  and the cumulative hash-chain acknowledgement used for ledger-replicated
  state, see
  [Faults and Acknowledgements](../../../reference/messages/faults_and_acknowledgements.md).
- For why Vultron uses `as:Read` rather than `as:View` or `as:Listen`, and why
  acknowledgement and validity are separate claims, see
  [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md).

## Demo

!!! example "Try it: `vultron-demo acknowledge`"

    Run this workflow end-to-end with the unified demo CLI:

    ```bash
    vultron-demo acknowledge
    ```

    Or with Docker Compose:

    ```bash
    DEMO=acknowledge docker compose -f docker/docker-compose.yml run --rm demo
    ```

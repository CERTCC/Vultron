# How to Acknowledge a Report

Use this guide when you have received a report and want to tell the sender it
arrived, without yet declaring it valid or invalid.
The acknowledgement is `RmReadReport`, a subclass of `as:Read`.
You finish with the sender informed and your own Report Management (RM) state
unchanged at `RECEIVED`.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- A report you have received, at `RM.RECEIVED`.
- The sender's actor URI.

---

## Decide whether to acknowledge at all

An acknowledgement carries no verdict, so it is worth sending only while you have
no verdict to send.

- If you are still triaging, send `RmReadReport`.
- If you are ready to accept the report, send `RmValidateReport` (`as:Accept`)
  instead. Validating implies reading.
- If you are ready to reject it, send `RmInvalidateReport`
  (`as:TentativeReject`) instead. The same implication holds.

Sending `RmReadReport` immediately before a verdict adds a message without adding
information.

---

## Send the acknowledgement

1. Send `RmReadReport` to the sender's inbox, with the original
   `RmSubmitReport` activity as its `object`.
2. Leave your RM state at `RECEIVED`. Acknowledgement is not a transition.

!!! warning "The prototype's emit path disagrees about this object"

    `AckReportPattern` — what a receiver dispatches on — requires the nested form
    `Read(Offer(VulnerabilityReport))` given above, and so does
    [Report Management (RM) Messages](../../../reference/messages/rm.md)
    (MSM-01-008).
    The prototype's own `rm_read_report_activity` factory instead builds
    `Read(VulnerabilityReport)`, carrying the bare report, which matches no
    pattern.
    Until #3439 settles which shape is authoritative, send the nested form and
    expect the prototype's emitted acknowledgements to differ.

---

## Verify

The sender holds a `RmReadReport` from you, and your RM state is still
`RECEIVED`.
No `CaseLedgerEntry` is written, because report submission is not
ledger-replicated.

---

## See it end to end

!!! example "Try it: `vultron-demo acknowledge`"

    ```bash
    vultron-demo acknowledge
    ```

    Or with Docker Compose:

    ```bash
    DEMO=acknowledge docker compose -f docker/docker-compose.yml run --rm demo
    ```

    The scenario runs all three paths: acknowledge only, acknowledge then
    validate, and acknowledge then invalidate.

---

## Further reading

- [Faults and Acknowledgements](../../../reference/messages/faults_and_acknowledgements.md)
  — the wire format, the mapping to the formal `RK` message, and the cumulative
  hash-chain acknowledgement that covers ledger-replicated state
- [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md) —
  why Vultron uses `as:Read` rather than `as:View` or `as:Listen`, and why
  acknowledgement and validity are separate claims
- [How to Report a Vulnerability](report_vulnerability.md) — the exchange this
  acknowledgement sits inside

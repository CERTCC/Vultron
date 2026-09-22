# How to Acknowledge a Report

Use this guide when you have received a report and want to tell the sender it arrived, without yet declaring it valid or invalid.
Report Acknowledgement (RK) is implemented in ActivityStreams as `Read(Offer(VulnerabilityReport))` — an `as:Read` whose object is the report's original `Offer`.
You finish with the sender informed and your own Report Management (RM) state unchanged at `RECEIVED`.

---

## Prerequisites

{% include-markdown "./_demo_prerequisites.md" %}

- A report you have received, at `RM.RECEIVED`.
- The sender's actor Uniform Resource Identifier (URI).

---

## Decide whether to acknowledge at all

An acknowledgment carries no verdict, so it is worth sending only while you have no verdict to send.

- If you are still triaging, send the acknowledgment, `Read(Offer(VulnerabilityReport))`.
- If you are ready to accept the report, send Report Valid (RV), `Accept(Offer(VulnerabilityReport))`, instead.
  Declaring the report valid implies you read it.
- If you are ready to reject it, send Report Invalid (RI), `TentativeReject(Offer(VulnerabilityReport))`, instead.
  The same implication holds.

Sending `Read(Offer(VulnerabilityReport))` immediately before a verdict adds a message without adding information.

---

## Send the acknowledgment

1. Send `Read(Offer(VulnerabilityReport))` to the sender's inbox, with the original `Offer(VulnerabilityReport)` activity as its `object`.
2. Leave your RM state at `RECEIVED`.
   Acknowledgment is not a transition.

The nested form is what a receiver dispatches on: `AckReportPattern` requires it, [Report Management (RM) Messages](../../../reference/messages/rm.md) documents it (MSM-01-008), and `rm_read_report_activity` builds it.
A bare `Read(VulnerabilityReport)` carrying the report itself matches no pattern.

---

## Verify

The sender holds a `Read(Offer(VulnerabilityReport))` from you, and your RM state is still `RECEIVED`.
No `CaseLedgerEntry` is written, because report submission is not ledger-replicated.

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

    The scenario runs all three paths: acknowledge only, acknowledge then validate, and acknowledge then invalidate.

---

## Further reading

- [Faults and Acknowledgements](../../../reference/messages/faults_and_acknowledgements.md) — the wire format, the mapping to the formal `RK` message, and the cumulative hash-chain acknowledgment that covers ledger-replicated state
- [Activity Vocabulary Design](../../../topics/activity_vocabulary_design.md) — why Vultron uses `as:Read` rather than `as:View` or `as:Listen`, and why acknowledgment and validity are separate claims
- [How to Report a Vulnerability](report_vulnerability.md) — the exchange this acknowledgment sits inside

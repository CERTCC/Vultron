<!-- Generated from SEMANTIC_REGISTRY — do not edit; edit the occasions and run `uv run msm-occasions --write` -->

| When… | Send | Send to | Sent by | Distinguished by | Details |
|---|---|---|---|---|---|
| a Reporter has written up a vulnerability and is about to submit the report | `Create(VulnerabilityReport)` | an actor outside any case | any actor (usually: finder, reporter) | — | [Create report](../rm.md#create-report) |
| a Reporter submits a vulnerability report to a Vendor or Coordinator | `Offer(VulnerabilityReport)` | an actor outside any case | any actor (usually: reporter) | — | [Report Submission (RS)](../rm.md#report-submission) |
| a report receiver has read a submitted report | `Read(Offer(VulnerabilityReport))` | an actor outside any case | the addressee of the vulnerability report (usually: vendor, coordinator) | — | [Report Acknowledgment (RK)](../rm.md#report-acknowledgment) |
| a report receiver judges the report valid | `Accept(Offer(VulnerabilityReport))` | the case manager | a participant (usually: vendor, coordinator) | — | [Validate report](../rm.md#report-valid) |
| a report receiver judges the report invalid | `TentativeReject(Offer(VulnerabilityReport))` | the case manager | a participant (usually: vendor, coordinator) | — | [Invalidate report](../rm.md#report-invalid) |
| a report receiver closes the report | `Reject(Offer(VulnerabilityReport))` | the case manager | a participant (usually: vendor, coordinator) | — | [Close report](../rm.md#report-closed) |
| a Participant accepts the case for further action | `Join(VulnerabilityCase)` | the case manager | a participant | — | [Report/Case Accepted (RA)](../rm.md#report-accepted) |
| a Participant defers further action on the case | `Ignore(VulnerabilityCase)` | the case manager | a participant | — | [Report/Case Deferred (RD)](../rm.md#report-deferred) |

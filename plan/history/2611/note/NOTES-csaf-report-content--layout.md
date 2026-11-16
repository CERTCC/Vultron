---
source: NOTES-csaf-report-content--layout
timestamp: '2026-11-16T18:31:35.498338+00:00'
title: Layout
type: note
---

**Archived:** 2026-11-16
**Reason:** delivered — vultron/wire/csaf/reader.py, vultron/core/models/report_claims.py and StoreReportClaimsRecordsNode implement it; layout listed in docs/reference/codebase/ARCHITECTURE.md

---

## Layout

- **CSAF lives at the wire edge.** The pinned local copy of the schemas, the
  generated models and the CSAF reader go in a `vultron.wire.csaf` package. Core
  receives a format-neutral `report_claims` model in `vultron.core.models`, with
  non-optional fields for what was read (ADR-0032), so a later CVE JSON or OSV
  reader fills the same type.
- **A report's files are typed; nothing it attaches refuses it.**
  `VulnerabilityReport.attachment` is a `list[ReportAttachment] | None`. A file is
  an `AttachedDocument`, `AttachedImage`, `AttachedAudio` or `AttachedVideo`, which
  own those wire `type` values while the `as_` classes declare themselves aliases,
  so no import order decides the owner. Anything else AS2 allows (a `Note`, a
  `Link`, a bare URI) is an untyped `OtherAttachment`, kept as received, because a
  report is never refused over the form of an attachment (CSAF-02-006). A single
  attachment sent without a list is read as a list of one. A received report keeps
  its attachments through `dl.save` and `dl.read`. It stays `None` when nothing is
  attached, because `[]` would put a key on the wire the sender never sent. Only a
  `Document` is read.
- **The reading reaches core on the event.** The extractor calls
  `vultron.wire.csaf.reader.read_report_attachments` and puts one `ClaimsReading`
  per recognized CSAF 2.1 attachment on `SubmitReportReceivedEvent.claims_readings`;
  `StoreReportClaimsRecordsNode` stores each one as a `ReportClaimsRecord`.
- **Persistence is a record of its own.** `ReportClaimsRecord`
  (`vultron.core.models.report_claims`) is keyed by report id and the SHA-256 of
  the document's content, because the parser mints a fresh id for a `Document`
  sent without one, and
  holds the reading, `received_at` and one `ClaimOutcome` per value path of
  `ReportClaims.value_paths()`, all `display-only` at receipt, plus the
  case-split and candidate-parties signals (CSAF-04-006, CSAF-04-007). The
  report object stays exactly as received (VM-08-002).
- **Only the side that creates the case marks outcomes.** The receiver's record
  keeps every value `display-only`; the CASE_MANAGER writes its own record, in
  its own store, with the `applied` and `overridden` outcomes of the case it
  built (`StoreCaseInputClaimsRecordsNode`), keyed on that case, so a second
  proposer's case for the same report keeps its own record. A record never says
  a value shaped
  a case it did not shape: an `auto_create_case` receiver that proposes nothing,
  or a proposal the CASE_MANAGER declines, leaves no `applied` value anywhere.

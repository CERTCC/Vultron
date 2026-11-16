---
source: NOTES-csaf-report-content--sending-csaf-04-009-csaf-04-010
timestamp: '2026-11-16T18:31:36.531285+00:00'
title: Sending (CSAF-04-009, CSAF-04-010)
type: note
---

**Archived:** 2026-11-16
**Reason:** delivered — csaf_document_text in vultron/core/models/report_claims.py and nodes/submit_report.py

---

## Sending (CSAF-04-009, CSAF-04-010)

- **The edge reads, core judges.** The route turns the body's JSON object into
  a core `SubmittedCsafDocument`, and the use case refuses its faults before any
  write, because core may not import wire (ARCH-01-001, ADR-0032).
- **Make the attached text once.** `csaf_document_text` is the only source of
  the JSON text, and it refuses text no UTF-8 body can carry or no receiver
  reads before the schema check runs, so an oversized document is never
  parsed and a refusal never echoes unencodable input (CSAF-04-009).
- **The sender skips recognition.** The sender says the object is CSAF 2.1,
  so the trigger schema-checks it as it stands; a wrong `$schema` or
  `csaf_version` is a schema error, never a silent pass.
- **A stated embargo end survives P, X or A.** The mapping drops every embargo
  end when the document sets P, X or A; the trigger keeps one the Reporter
  stated, because the terms are the Reporter's to propose and the receiver
  decides (EP-04-020).

---
title: "CSAF Documents in Reports: Implementation Plan"
status: active
kind: plan
tracks:
  - "#5911"
description: >
  How this codebase carries, checks and reads a CSAF 2.1 document attached to a
  VulnerabilityReport: the module layout, the two-stage parse with generated
  models, the receiver-local record, the pinned local copy of the schemas and the
  job that watches the draft. The protocol rules are CSAF-01 to CSAF-03 and
  ADR-0184; this note is the build plan for CSAF-04 and CSAF-05.
related_specs:
  - specs/csaf-report-content.yaml
  - specs/embargo-policy.yaml
  - specs/message-validation.yaml
  - specs/case-management.yaml
related_notes:
  - notes/wire-core-boundary.md
  - notes/ci-workflow-authoring.md
  - notes/datalayer-design.md
relevant_packages:
  - vultron.wire
  - vultron.core.models
---

# CSAF Documents in Reports: Implementation Plan

The rules are in `specs/csaf-report-content.yaml` and ADR-0184. This note is the
build plan; when the tasks land, move its lasting rules into a `guidance` note
and archive it.

## Layout

- **CSAF lives at the wire edge.** The pinned local copy of the schemas, the
  generated models and the CSAF reader go in a `vultron.wire.csaf` package. Core
  receives a format-neutral `report_claims` model in `vultron.core.models`, with
  non-optional fields for what was read (ADR-0032), so a later CVE JSON or OSV
  reader fills the same type. The planned-test probes name these two modules
  (`test/architecture/test_csaf_report_content_planned.py`).
- **A report's attachments need a core type.** `parse_activity` already turns a
  report's `attachment` into a list of wire `as_Document` objects, held in the
  untyped `attachment` field of the core `VulnerabilityReport`. Give the report a
  typed attachment list of a core document type before reading it, and check that
  a stored report keeps its attachments through `dl.save` and `dl.read`.
- **Persistence is a new record.** The receiver-local record of CSAF-04-004 is a
  new stored type, approved for this work in the #5131 planning session. Keep it
  apart from the report object, which stays exactly as received (VM-08-002).

## Two-stage parse

1. **Stage 1, the full model.** Validate the attachment's JSON against the
   generated root model. The verdict is `schema-valid` or `schema-invalid` with
   each error path (CSAF-04-001, CSAF-04-002).
2. **Stage 2, the claims model.** A hand-written model of only the fields
   CSAF-03 reads. Build it from the stage-1 object when stage 1 passes, or read
   field by field from the raw JSON when it fails, skipping what cannot be read
   (CSAF-04-003).

Rules for stage 2:

- **Read only what was sent.** The generated models fill the schema's
  `default` values, which the sender never stated (CSAF-02-005). Build stage 2
  from `model_fields_set` (or `exclude_unset=True`), never from the full dump.
- **"Now" is the receiver's time of receipt**, not the Offer's `published`, which
  is the sender's claimed time (CLP-15-003). A `disclosure_date` equal to that
  time counts as past (CSAF-03-003).
- **Mapping SSVC.** The value sits in `vulnerabilities[].metrics[].content.ssvc_v2`,
  an SSVC `SelectionList`; read the selection whose decision point is
  Exploitation. Reuse `SSVC_2_Exploitation` in `vultron/core/scoring/ssvc_2.py`.
- **Explicit fields first.** Compare each CSAF value with the Offer and report
  field for the same thing before applying it, and record the outcome
  (CSAF-02-003, CSAF-04-004).

## Generating the models

Measured on CSD04 with `datamodel-code-generator` 0.90 during planning:

- The schema references CVSS v2, v3 and v4 (FIRST), the SSVC `SelectionList`
  (CERT/CC) and CSAF's extension schema by URL. Rewrite those `$ref`s to the
  pinned local copy; the CSAF repository itself keeps copies under
  `csaf_2.1/referenced_schema/`.
- CSAF's extension meta-schema references the JSON Schema 2020-12 meta-schemas.
  Keep local copies of those too, so regeneration needs no network (CSAF-05-002).
- The output must be a package directory (`--output <dir>`), because the
  references are modular. The result is about 3,600 lines and 181 classes, with a
  root class `CommonSecurityAdvisoryFramework`.
- The models need `email-validator` (`pydantic[email]`) at runtime. Both new
  dependencies were approved in the planning session: the generator as a dev
  tool, `email-validator` at runtime.
- Against the Technical Committee's test documents, the models accepted all 498
  valid documents and rejected only 21 of the 316 built to fail a mandatory test.
  That is why the verdict says schema-valid, never valid CSAF.

## Following the draft

- **One pin.** Record the source repository, commit and draft stage once beside
  the pinned local copy, and test that `docs/reference/csaf_crosswalk/_csaf_version.md`
  names the same commit (CSAF-05-001).
- **The draft cannot be told from the document.** Every CSAF 2.1 draft uses the
  same `$schema` value, so a document written to a newer draft is checked against
  the pin and may read as schema-invalid; stage 2 still reads it.
- **The watch job compares models, not commits.** It regenerates the models from
  upstream in the runner and diffs them with the committed ones, plus the profile
  text (`csaf_2.1/prose/edit/src/profiles.md`) and the mandatory-test list
  (`csaf_2.1/test/validator/data/testcases.json`). It opens one typed issue,
  found again by a marker, and does nothing while that issue is open
  (CSAF-05-005, CSAF-05-006). A workflow's own `GITHUB_TOKEN` can file the
  issue, but the issue type needs `.github/scripts/ensure-issue-type.sh`, and the
  job needs `notify-failure` ([ci-workflow-authoring](ci-workflow-authoring.md)).
- **Watch the embargo proposal.** If the Technical Committee adopts the
  crosswalk's proposal that an `embargo` action carries its own end date, the
  embargo-end mapping (CSAF-03-001) should prefer that date to `disclosure_date`.
- **The corpus stays outside the suite.** An optional script runs the generated
  models over a local clone's `csaf_2.1/test/validator/data/` when the pin moves
  (CSAF-05-004).

## Signals

- **Case split.** Recorded when the vulnerabilities disagree (CSAF-04-006). The
  Case Owner acts through the existing split trigger, never the receiver.
- **Candidate parties.** Vendor names come from `product_tree` branches of
  category `vendor` above the products in `product_status.known_affected`
  (CSAF-04-007). Turning a name into an actor needs a directory that does not
  exist yet; the party-discovery monitor (BT-20-003) or a human does it, through
  `suggest-actor-to-case`.

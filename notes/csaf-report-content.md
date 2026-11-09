---
title: "CSAF Documents in Reports: Implementation Plan"
status: active
kind: plan
tracks:
  - "#6091"
  - "#6092"
  - "#6093"
  - "#6094"
  - "#6101"
  - "#5911"
  - "#6100"
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
  - vultron.metadata
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
  reader fills the same type.
- **A report's attachments are core files.** `VulnerabilityReport.attachment` is a
  `list[AttachedFile] | None`: `AttachedDocument`, `AttachedImage`, `AttachedAudio`
  or `AttachedVideo`, which own those wire `type` values while the `as_` classes
  declare themselves aliases, so no import order decides the owner. A received
  report keeps its attachments through `dl.save` and `dl.read`. It stays `None`
  when nothing is attached, because `[]` would put a key on the wire the sender
  never sent. Any other attachment (a `Note`, a `Link`, a bare URI) is refused at
  parse; widen `AttachedFile` if a sender needs one. Only a `Document` is read.
- **The reading reaches core on the event.** The extractor calls
  `vultron.wire.csaf.reader.read_report_attachments` and puts one `ClaimsReading`
  per recognized CSAF 2.1 attachment on `SubmitReportReceivedEvent.claims_readings`;
  `StoreReportClaimsRecordsNode` stores each one as a `ReportClaimsRecord`.
- **Persistence is a record of its own.** `ReportClaimsRecord`
  (`vultron.core.models.report_claims`) is keyed by report id and the SHA-256 of
  the document's content, because the parser mints a fresh id for a `Document`
  sent without one, and
  holds the reading, `received_at` and one `ClaimOutcome` per value path of
  `ReportClaims.value_paths()`, all `display-only` at receipt. Case creation
  (#6091) marks a value `applied` or `overridden` with `with_outcome()` and saves
  the record; the report object stays exactly as received (VM-08-002).

## Two-stage parse

1. **Stage 1, the full model.** Validate the attachment's JSON against the
   generated root model. The verdict is `schema-valid` or `schema-invalid` with
   each error path (CSAF-04-001, CSAF-04-002).
2. **Stage 2, the claims model.** A hand-written model of only the fields
   CSAF-03 reads, plus the display-only TLP label, acknowledgments and involved
   parties (CSAF-04-004). One field reader serves both cases: it reads the
   stage-1 object's `exclude_unset` dump when stage 1 passes, and the raw JSON
   when it fails, skipping what cannot be read (CSAF-04-003).

Rules for stage 2:

- **Read only what was sent.** The generated models fill the schema's
  `default` values, which the sender never stated (CSAF-02-005). Build stage 2
  from `model_fields_set` (or `exclude_unset=True`), never from the full dump.
- **"Now" is the receiver's time of receipt**, not the Offer's `published`, which
  is the sender's claimed time (CLP-15-003). A `disclosure_date` equal to that
  time counts as past (CSAF-03-003). Read it from `ReportClaimsRecord.received_at`.
- **Mapping SSVC.** The value sits in `vulnerabilities[].metrics[].content.ssvc_v2`,
  an SSVC `SelectionList`; read the selection whose decision point is
  Exploitation (namespace `ssvc`, key `E`). The wire reader copies the selected
  value key (`N`, `P` or `A`) into `VulnerabilityClaims.exploitation` as a plain
  string, and skips the field when the metrics state more than one value; core
  maps it onto `SSVC_2_Exploitation` in
  `vultron/core/scoring/ssvc_2.py`: wire may import only core models and
  states (ARCH-22-001), so `vultron.wire.csaf` never imports `scoring`.
- **Explicit fields first.** Compare each CSAF value with the Offer and report
  field for the same thing before applying it, and record the outcome
  (CSAF-02-003, CSAF-04-004).

## Generating the models

The pinned local copy, the pin record and the generated models are in place; later
tasks reuse them rather than add a second path.

- **Import the models from `vultron.wire.csaf.models`.** The root is
  `CommonSecurityAdvisoryFramework`. They are generated, then `ruff`-fixed and
  formatted, and `mypy` and `pyright` skip the package; never edit it by hand
  (CSAF-05-003).
- **Read the pin through `vultron.metadata.csaf.pin.load_pin()`.** The copy
  and its record sit in `third_party/csaf/`, outside `vultron/`, because they
  are third-party files and nothing reads them at runtime. The record
  (`pin.json`) maps each referenced schema's URL to its path in the copy and
  holds each file's SHA-256, so a hand edit to the copy fails a test; the copy
  keeps the upstream repository's paths, so an upstream checkout lines up with
  it file for file.
- **Keep a licence file beside each source.** Each source directory under
  `third_party/csaf/schemas/` has a `LICENSE` or `NOTICE` file, which the pin
  record does not list; a test fails on a pinned file with none beside or above
  it. A new source added when the pin moves needs one, and an entry in
  `LICENSE.md`.
- **Generate from any source with `render_models(source, pin)`** in
  `vultron.metadata.csaf.regenerate`, or `uv run csaf-models` with `--source`,
  `--pin`, `--output` and `--check`. It returns the package as text, so the
  draft-watch job (#6094) can generate from an upstream checkout and diff without
  writing. A URL the pin does not map, or a relative reference to a file it does
  not list, raises `UnpinnedReferenceError`; the generator runs with remote
  references refused, so nothing is ever fetched.
- **Pydantic drops some schema constraints.** No `pattern` on a URL or UUID field,
  no `min_length` on a URL, so a `purls` entry is not checked against its
  `^pkg:` pattern. Stage 1 can pass a document the schema rejects there, which is
  one more reason the verdict says schema-valid, never valid CSAF (CSAF-04-002).
- **The models need `email-validator`** (`pydantic[email]`) at runtime, for
  `EmailStr` fields.
- **The Technical Committee's test documents stay outside the suite.**
  `uv run csaf-corpus --clone <dir>` reports per-group accept and reject counts
  over a clone's test documents when the pin moves (CSAF-05-004). Planning
  measured all 498 valid documents accepted and only 21 of the 316 built to fail
  a mandatory test rejected.

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

## Signals

- **Case split.** Recorded when the vulnerabilities disagree (CSAF-04-006). The
  Case Owner acts through the existing split trigger, never the receiver.
- **Candidate parties.** Vendor names come from `product_tree` branches of
  category `vendor` above the products in `product_status.known_affected`
  (CSAF-04-007). Turning a name into an actor needs a directory that does not
  exist yet; the party-discovery monitor (BT-20-003) or a human does it, through
  `suggest-actor-to-case`. Comparing a vendor name with the receiving actor's own
  `name` needs no directory, so that is how "a vendor other than the receiver"
  is decided.

## Retiring the planned-test probes

Each probe in `test/architecture/test_csaf_report_content_planned.py` XPASSes
once a test elsewhere under `test/` carries its spec ID in a
`@pytest.mark.spec` marker. The issue that writes that behavioral test is the
one whose build turns the probe red, so delete the probe in the same change. A
probe never keys on a module or field name, so no task can flip a probe that
another task owns.

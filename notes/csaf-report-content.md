---
title: "CSAF Documents in Reports: Implementation Plan"
status: active
kind: plan
tracks:
  - "#6090"
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
  Exploitation. The wire reader copies the selected value into `report_claims`
  as a plain string, and core maps it onto `SSVC_2_Exploitation` in
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
- **The watch job compares models, not commits.** `.github/workflows/csaf-draft-watch.yml`
  runs `uv run csaf-draft-watch` (`vultron/metadata/csaf/draft_watch/`) over
  checkouts of the pinned commit and the upstream head. It generates models from
  both schema sets with `description`, `$comment` and `examples` dropped, so a
  reworded description opens nothing, and diffs the profile text and the
  mandatory-test IDs. A `$ref` the pin does not map is reported, never raised. It
  opens one Task, found again by the `csaf-draft-watch` label, and writes nothing
  while that issue is open (CSAF-05-005, CSAF-05-006).
- **A new read field goes in `READ_FIELDS`.** The issue names the fields this
  codebase reads that the change touches (CSAF-05-007), from `READ_FIELDS` in
  `vultron/metadata/csaf/draft_watch/fields.py`. A task that reads another CSAF
  field adds its document path there, or the watch cannot say when upstream
  changes it; a test fails on a path the pinned schema does not have.
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

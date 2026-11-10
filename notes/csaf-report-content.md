---
title: "CSAF Documents in Reports: Implementation Plan"
status: active
kind: plan
tracks:
  - "#6093"
  - "#6094"
  - "#6101"
  - "#5911"
  - "#6100"
description: >
  How this codebase carries, checks and reads a CSAF 2.1 document attached to a
  VulnerabilityReport: the module layout, the two-stage parse with generated
  models, the receiver-local record and signals, how the CASE_MANAGER fills a new
  case from the CSAF report its proposal carries, the pinned local copy of the
  schemas and the job that watches the draft. The protocol rules are CSAF-01 to
  CSAF-03 and ADR-0184; this note is the build plan for CSAF-02 to CSAF-05.
related_specs:
  - specs/csaf-report-content.yaml
  - specs/embargo-policy.yaml
  - specs/message-validation.yaml
  - specs/case-management.yaml
  - specs/case-proposal.yaml
related_notes:
  - notes/bt-pitfalls.md
  - notes/wire-core-boundary.md
  - notes/ci-workflow-authoring.md
  - notes/datalayer-design.md
  - notes/case-proposal.md
relevant_packages:
  - vultron.wire
  - vultron.metadata
  - vultron.core.models
  - vultron.core.services
  - vultron.core.behaviors
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

## Filling the case (CSAF-02, CSAF-03)

- **One mapping.** `case_inputs_from_claims(claims, *, reference_time, stated)`
  in `vultron.core.services.report_case_inputs` is the only CSAF-03 mapping; the
  submit-report trigger (#6092) reuses it with its own "now". `StatedReportFields`
  carries the Offer's and report's values, which always win (CSAF-02-003).
- **The CASE_MANAGER reads the carried Offer.** The proposer and the
  CASE_MANAGER are two roles of one coordinating function, so the CSAF document
  on the Offer a `Create(CaseProposal)` carries (CP-01-008) is still the initial
  report (CSAF-02-002). The extractor reads that Offer's report into
  `CreateCaseProposalReceivedEvent.claims_readings`, with the report's own name
  and summary; a proposal with no inline Offer fills nothing (CP-01-021).
  `ResolveReportCaseInputsNode` and `CreateCaseFromProposalNode` run on the
  new-case arm only, so a proposal that resolves to an existing case changes
  nothing (EP-04-029). A proposer that fills the values itself and carries them
  on the proposal is allowed, not built.
- **"Now" is the CASE_MANAGER's receipt of the proposal**, the act's instant, not
  the Offer's `published` (CLP-15-003) and not the receiver's receipt, which no
  message carries. A `disclosure_date` equal to it counts as past (CSAF-03-003).
  The Offer's `proposedEmbargo` is measured from the same instant
  (`sender_embargo_proposal_inputs`), so one clock decides between the two.
- **A `proposedEmbargo` that is no longer terms states nothing.** One already
  ended, or about another subject, is read as no proposal: it neither shapes the
  case nor sets the document's date aside (CSAF-02-003).
- **The first document fills.** A report with several
  `csaf_vulnerability_report` documents fills the case from the first; the
  others stay display only, so two documents never compete for one input.
- **P/X/A are the case's first status**, built at construction, not a
  transition. X starts with P (the pX to PX invariant). A case that starts with
  P, X or A gets no embargo (EP-04-020), so it takes no embargo end, not even a
  stated one, and its future disclosure dates stay display only, neither applied
  nor overridden.
- **A CSAF embargo end is a sender proposal.** With no `proposedEmbargo` on the
  Offer, the node seeds `sender_proposed_embargo` with an `EmbargoEvent` whose id
  derives from the proposal (`csaf_proposed_embargo_id`), so it competes with the
  owner's actor default by shortest-wins and redelivery names the same event.
  `BTBridge` scopes both sender keys and `report_case_inputs` to the execution
  (`managed_keys`), because an output port outlives its run: unscoped, a later
  proposal stating no terms took the previous report's embargo (BT-09).

## Sending (CSAF-04-009, CSAF-04-010)

- **The edge reads, core judges.** The submit-report route reads the body's
  `csaf_document` with `read_submitted_csaf_document`, and the core request
  carries the resulting `SubmittedCsafDocument`, so core never imports wire
  (ARCH-01-001). The use case refuses through `submitted_csaf_violations`
  before it stores anything; `run_trigger` turns the `VultronValidationError`
  into a 422 with one `details` entry per fault.
- **The sender skips recognition.** The sender says the object is CSAF 2.1,
  so the trigger schema-checks it as it stands; a wrong `$schema` or
  `csaf_version` is a schema error, never a silent pass.
- **A stated embargo end survives P, X or A.** The mapping drops every embargo
  end when the document sets P, X or A; the trigger keeps one the Reporter
  stated, because the terms are the Reporter's to propose and the receiver
  decides (EP-04-020).

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
- **Mapping SSVC.** The value sits in `vulnerabilities[].metrics[].content.ssvc_v2`,
  an SSVC `SelectionList`; read the selection whose decision point is
  Exploitation (namespace `ssvc`, key `E`). The wire reader copies the selected
  value key (`N`, `P` or `A`) into `VulnerabilityClaims.exploitation` as a plain
  string, and skips the field when the metrics state more than one value; core
  maps it onto `SSVC_2_Exploitation` in
  `vultron/core/scoring/ssvc_2.py`: wire may import only core models and
  states (ARCH-22-001), so `vultron.wire.csaf` never imports `scoring`.

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
- **The watch job compares models, not commits.**
  `.github/workflows/csaf-draft-watch.yml` runs `uv run csaf-draft-watch`
  (`vultron/metadata/csaf/draft_watch/`) over checkouts of the pinned commit and
  the upstream head. It generates models from both schema sets with
  `description`, `$comment` and `examples` dropped, so a reworded description
  opens nothing, and diffs the profile text and the mandatory-test IDs. A `$ref`
  the pin does not map is reported, never raised. It opens one Task, found again
  by the `csaf-draft-watch` label, and writes nothing while that issue is open
  (CSAF-05-005, CSAF-05-006).
- **A new read field goes in `READ_FIELDS`.** The issue names the fields this
  codebase reads that the change touches (CSAF-05-007), from `READ_FIELDS` in
  `vultron/metadata/csaf/draft_watch/fields.py`. A task that reads another CSAF
  field adds its document path there, or the watch cannot say when upstream
  changes it; a test fails on a path the pinned schema does not have.
- **Watch the embargo proposal.** If the Technical Committee adopts the
  crosswalk's proposal that an `embargo` action carries its own end date, the
  embargo-end mapping (CSAF-03-001) should prefer that date to `disclosure_date`.

## Signals

- **Signals are the receiver's, at receipt.** `StoreReportClaimsRecordsNode`
  computes both with `claims_signals` against the act's instant and the
  receiving actor's `name`, for a document of any category: a signal changes
  no case data, so CSAF-02-002's category limit does not reach it.
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

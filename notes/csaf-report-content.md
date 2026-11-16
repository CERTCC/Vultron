---
title: "CSAF Documents in Reports: Implementation Rules"
status: active
kind: guidance
description: >
  Rules for changing how this codebase reads a CSAF 2.1 document attached to a
  VulnerabilityReport: the two-stage parse and what stage 2 may read, scoping the
  sender keys a proposal seeds, regenerating the models from the pinned schemas,
  and keeping the draft watch's read fields current. The protocol rules are
  CSAF-01 to CSAF-05 and ADR-0184.
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

# CSAF Documents in Reports: Implementation Rules

The normative rules are in `specs/csaf-report-content.yaml` and ADR-0184. This note
holds the code-level traps they do not carry.

## Scope a Proposal's Sender Keys to the Execution

`BTBridge` scopes the sender keys a CSAF proposal seeds, and `report_case_inputs`,
to the one execution (`managed_keys`). An output port outlives its run, so an
unscoped key carries into the next proposal: one that stated no terms took the
previous report's embargo (BT-09).

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

Reuse the pinned local copy, the pin record and the generated models; do not add a
second path to any of them.

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
  draft-watch job can generate from an upstream checkout and diff without
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
  over a clone's test documents when the pin moves (CSAF-05-004). Stage 1 accepts
  most documents built to fail a mandatory test, because the mandatory tests are
  not schema checks.

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
- **An upstream end date for an `embargo` action would change the mapping.** If
  the Technical Committee adopts it, the embargo-end mapping (CSAF-03-001) prefers
  that date to `disclosure_date`; #5137 tracks the question.

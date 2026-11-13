# Third-Party Files

Each directory here holds a **pinned local copy** of files that other projects
publish. They are not this project's code, so they sit outside `vultron/`.

- **Each file keeps its own licence.** A `LICENSE` or `NOTICE` file next to the
  files names their source and carries the licence they are published under.
  The root `LICENSE.md` lists them under "Third Party Software in this
  Repository".
- **Never edit these files by hand.** Each copy is byte for byte as published,
  and a test compares it with the digests in its pin record.
- **Refresh a copy only by moving its pin.** Take the files from the new
  upstream revision, update the pin record, and regenerate whatever is built
  from them.

## `csaf/`

The CSAF 2.1 draft's JSON schemas and every schema they reference (CSAF-05-002).

- `pin.json` is the pin record: the upstream repository, commit and draft
  stage, each referenced schema's URL mapped to its path under `schemas/`, and
  each file's SHA-256 digest. `vultron.metadata.csaf.pin.load_pin()` reads it.
- `schemas/` keeps the upstream paths, with one licence file per source:

  | Source | Files | Licence file |
  |---|---|---|
  | OASIS CSAF TC | `schemas/csaf_2.1/json_schema/` | `NOTICE` (OASIS IPR Policy, Non-Assertion Mode) |
  | FIRST | `schemas/csaf_2.1/referenced_schema/first/` | `LICENSE` (BSD-3-Clause) |
  | CERT/CC SSVC | `schemas/csaf_2.1/referenced_schema/certcc/` | `LICENSE` (MIT (SEI)-style) |
  | JSON Schema | `schemas/json-schema.org/` | `LICENSE` (BSD-3-Clause) |

- `uv run csaf-models` generates `vultron/wire/csaf/models/` from this copy, and
  `uv run csaf-models --check` fails when the models no longer match it
  (CSAF-05-003). Nothing reads these files at runtime.
- The scheduled `CSAF Draft Watch` workflow opens one issue when the draft's
  head changes what the models depend on (CSAF-05-005). It never moves the pin.

## `jsonld/`

The JSON-LD context documents that Vultron wire messages and actor profiles cite
(VM-10-011).

- `pin.json` is the pin record: each context's URL mapped to its filename, and
  each file's SHA-256 digest. `vultron.metadata.wire_context.pin.load_pin()`
  reads it.
- The four context files sit directly under `jsonld/`, with one NOTICE file per
  source:

  | Source | Files | Notice file |
  |---|---|---|
  | W3C ActivityStreams 2.0 | `activitystreams.jsonld` | `NOTICE-W3C` (W3C Software and Document License) |
  | W3C Security Vocabulary | `data-integrity-v2.jsonld`, `multikey-v1.jsonld` | `NOTICE-W3C-SECURITY` (W3C Software and Document License) |
  | W3C Controlled Identifiers | `cid-v1.jsonld` | `NOTICE-W3C-CID` (W3C Software and Document License) |

- `vultron/metadata/wire_context/pin.py` provides the loader that extracts terms
  from these contexts, both top-level and type-scoped. Nothing reads these files
  at runtime; they supply the term list for the VM-10-007 check.
- No watch job: the versioned contexts never change at their URLs, and AS2
  changes rarely and only by addition.

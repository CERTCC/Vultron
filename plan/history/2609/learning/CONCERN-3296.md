---
source: CONCERN-3296
timestamp: '2026-09-17T17:01:21.081503+00:00'
title: spec-lint reports a malformed spec YAML as a raw traceback that never names
  the file
type: learning
---

## Symptom

A syntax error in any `specs/*.yaml` makes `spec-lint` exit with an unhandled
`yaml.scanner.ScannerError` and a ~30-line PyYAML/Cython traceback. The location
it reports identifies the *string* it was parsing, not the file:

```text
yaml.scanner.ScannerError: mapping values are not allowed in this context
  in "<unicode string>", line 404, column 43
```

With many files in `specs/`, "line 404" alone does not locate the error, and the
traceback frames are all inside `yaml/_yaml.pyx`, so nothing in the output names
the offending spec.

## Reproduction

Add a plain (unquoted) scalar containing `": "` to any spec entry — the most
likely way to hit this, since prose in a `statement:` or `verification:` field
naturally wants a colon. Then `PYTHONPATH= uv run spec-lint`.

## Root cause

`vultron/metadata/specs/registry.py` `load_registry()` walks
`spec_dir.glob("*.yaml")` and calls `yaml.load(yaml_path.read_text(), ...)` then
`SpecFile.model_validate(raw)` with no guard around either. Three facts combine:

1. `yaml.scanner.ScannerError` is not a `ValueError`, so the caller's
   `except (ValidationError, ValueError)` in `lint.py` never sees it.
2. Passing `read_text()` (a `str`) rather than a named stream is why PyYAML's
   mark reads `<unicode string>` — it has no filename to report.
3. The `model_validate` call on the next line has the same gap. It *is* caught,
   so it prints `[FATAL]` with no traceback, but reports only a positional path
   (`groups.0.specs.0.kind`) and the model name — no file, no requirement ID.
   This is the *more* common fault, since it is what an invalid `kind`,
   `priority`, or `rel_type` produces, and `notes/spec-authoring-rules.md`
   already documents three variants of it.

## What planning found

The wrapper that fixes this had already been written in the same package —
independently, more than once, in different message shapes. The docstring of
`vultron/metadata/adr/loader.py::load_adr_post` diagnoses this exact failure:
"without this wrapper they escape the documented contract and crash `spec-lint`
and the pre-commit hooks with a raw traceback instead of a clean,
file-attributed error." It fixed it for ADRs only. The history entry loaders
have their own copies; the notes and spec loaders have none. So an author's
error output depends on which directory they edited rather than on what they got
wrong — and no hand-written copy reads PyYAML's `problem_mark`, so each names
the file and then gives a `<unicode string>` position next to it.

The work is therefore extract-and-adopt, not new design.

## Scope decisions (confirmed with the maintainer)

- Fix in `load_registry`, not in the linter — many consumers load the registry
  (`spec-dump`, `spec-coverage`, the docs renderer, `test/conftest.py`, the
  coverage ratchet), and `spec-dump` is the first command `AGENTS.md` tells an
  agent to run. A linter-only fix leaves it emitting the bare traceback.
- Extract one shared helper and adopt it at every loader site, replacing the
  hand-written copies rather than adding another.
- Collect-all rather than fail-fast, per EH-07-001: the loader rejects the
  corpus as a unit, so reporting one file at a time gains the caller nothing.
- No ADR — an uncontested convention whose rationale the project had already
  written down in `adr/loader.py`.

## Requirements written

- `specs/meta-specifications.yaml` MS-17-001/002/003 — attribution as
  `path:line:col`, no traceback escape, one shared helper.
- `specs/spec-registry.yaml` SR-03-008/009 and a `verification` on SR-04-002
  recording that a traceback does not satisfy its existing "invalid YAML
  structure" hard-error clause.
- `specs/notes-frontmatter.yaml` NF-03-006 — the same rule for the notes loader.

## Left out of scope

`test/conftest.py` wraps `load_registry` in a bare `except Exception: return`,
so a malformed spec corpus silently disables spec-ID marker validation for the
whole test session, while its docstring claims it only skips when no spec files
exist. Different subsystem with its own reasoning; folding it in would have made
the PR's story harder to read.

**Resolved**: 2026-09-17 — implementation tracked in #3324.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3323>.
Notes: `vultron/metadata/AGENTS.md` (new), `notes/spec-authoring-rules.md`.

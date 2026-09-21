# AGENTS.md — vultron/metadata

> For project-wide conventions, see the root [AGENTS.md](../../AGENTS.md).

This package is the project's own tooling layer: it reads the repository's
metadata files and validates them. It backs the `spec-dump`, `spec-lint`,
`spec-coverage`, `adr-index`, `demo-scenarios`, `append-history`, and
`show-history` console entry points, plus several pre-commit hooks.

Nothing here is protocol code. The audience for its output is a human or an
agent who just edited a metadata file and got it wrong, so **error messages
are the product**.

## Subpackages

| Subpackage | Reads | Validates against |
|---|---|---|
| `specs/` | `specs/*.yaml` | `SpecFile` (schema.py) |
| `notes/` | `notes/*.md` frontmatter | `NotesFrontmatter` |
| `adr/` | `docs/adr/*.md` frontmatter | `AdrFrontmatter` |
| `history/` | `plan/history/**/*.md`, `plan/incoming/learnings/*.md` | `HistoryEntryFrontmatter` |
| `msm/` | a constant mapping table + the wire `SEMANTIC_REGISTRY` | — |
| `demo_scenarios/` | the `@scenario` registry in `vultron/demo/scenario/` | — |
| `docs/` | `git log` over `docs/`, for the what's-new page | — |

Shared helpers live in `base.py`: `repo_root()` (every loader needs it and none
may assume the caller's cwd) and `MkDocsYamlLoader` (a `SafeLoader` that
tolerates `mkdocs.yml`'s `!ENV` and `!!python/name:` tags). Do not re-derive
either — `repo_root` had five near-identical private copies before #3450.

## Generate vs. Check

Two subpackages own committed generated artifacts, and both split the same way:
**generate what is derivable, check what is prose.** `adr/index_gen.py`
regenerates `docs/adr/index.md` but only checks the MkDocs nav, whose labels are
hand-written; `demo_scenarios/` regenerates the CI matrix and two scenario
tables but leaves the spec enumerations and nav to completeness checks. Each is
wired into pre-commit as a `--check` hook (`adr-index-sync`,
`demo-scenarios-sync`). A generated file that is committed but ungated is a
hand-edited file with extra steps.

One trap specific to build-time rendering: MkDocs rewrites `.md` links with a
treeprocessor on **its own** `Markdown` instance, and `markdown-exec` converts a
block's output on a child instance that does not carry it. A `.md` target
printed from an exec block reaches the built HTML verbatim and 404s, and
`mkdocs build --strict` stays silent because it never saw the link. Emit
built-site URLs (`fv/`) from a renderer, not source paths.

## Loader Failure Attribution (MS-17)

Every loader here has the same shape: walk a directory, parse each file, then
validate the parsed data against a Pydantic model. Both steps can fail, and
**both must name the file that failed** — as `path:line:col` when the parser
supplies a position (MS-17-001).

Route both steps through the shared helper in `file_loading.py`; do not write
a new wrapper (MS-17-003). That helper does not exist yet — #3324 creates it and
converts every loader, and its AC-5 lists the sites still carrying hand-written
copies.

Three traps make this easy to get wrong:

1. **A YAML error is not a `ValueError`.** `yaml.scanner.ScannerError` derives
   from `Exception`, so a caller guarding `except (ValidationError, ValueError)`
   — the contract the loaders document — does not catch it. It escapes as a
   traceback in which no frame names the offending file (MS-17-002). Only
   `specs/lint.py` guards that pair at all: `coverage.py`, `render.py` (which
   backs `spec-dump`), `docs_render.py` and `llm_export.py` call `load_registry`
   with no guard, and `test/conftest.py` wraps it in `except Exception: return`,
   so most callers surface even less than the traceback does.

2. **Passing text instead of a stream costs you the filename.** PyYAML takes the
   name for its position mark from the stream it is given. Hand it
   `path.read_text()` and every error reads `in "<unicode string>", line N` — a
   position attributed to a source that is not on disk. Read the position off
   the exception's `problem_mark` and pair it with the path yourself; naming the
   file and then printing PyYAML's own mark next to it contradicts itself.

3. **A Pydantic error names the model, not the file.** A validation failure
   reports a positional path into the parsed structure (`groups.0.specs.0.kind`)
   and the model's class name. Across a directory of files that locates nothing,
   so the validate step needs attribution just as much as the parse step does —
   and it is the more common failure, because it is what an invalid `kind`,
   `priority`, or `rel_type` value produces.

A loader that walks a set of files reports **every** failing file, not just the
first (SR-03-009). These loaders reject the corpus as a unit, so stopping at the
first fault makes the tool report less than it knows; see EH-07-001 for the
general principle and `history/incoming.py` for the shape.

## Spec-First References Need a Lint Suppression

`spec-lint` hard-errors when a spec `statement` or `verification` names a file
that does not exist (MS-15-001) or a `SCREAMING_SNAKE_CASE` symbol absent from
the **Python sources** under `vultron/` and `test/` (MS-15-004 — the scan is
`rglob("*.py")`, so a token that appears only in markdown does not resolve it).
This is deliberate — a MUST pointing at missing infrastructure is a
stale-premise landmine.

When a requirement is written *before* the code it governs, that check fires on
the new requirement. Use the documented opt-out on that entry:

```yaml
    lint_suppress:
    - phantom_path_ref     # statement names a file yet to be created
    - phantom_symbol_ref   # statement names a symbol yet to be defined
```

Remove the suppression in the PR that creates the file, so the reference goes
back under the check. Only `statement`, `verification`, and behavioral
step/condition text are scanned; `rationale` is exempt by design, because it
narrates history and legitimately names things that were removed.

## Changing a Linter Check

A check that validates spec prose against a textual scan of the source tree can
be blinded by its own prose: naming a symbol in the check's docstring or error
message puts that token back into the scanned corpus, so the guard resolves it
as live and stops flagging the defect it exists to catch. Assert the negative
directly, and prefer file-scoped exclusions over package-scoped ones. Full
write-up: [`notes/spec-authoring-rules.md`](../../notes/spec-authoring-rules.md)
§ "A Grep-Corpus Guard Can Resolve Its Own Documentation".

## Related

- `notes/spec-authoring-rules.md` — field enums, lint traps, coverage ratchet
- `notes/specs-vs-adrs.md` — whether a rule belongs in a spec at all
- `notes/history-management.md` — `append-history` and `plan/history/` layout
- `notes/notes-frontmatter.md` — the notes frontmatter schema
- `specs/spec-registry.yaml` (SR), `specs/meta-specifications.yaml` (MS),
  `specs/notes-frontmatter.yaml` (NF), `specs/history-management.yaml` (HM)

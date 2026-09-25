# AGENTS.md — vultron/metadata

> For project-wide conventions, see the root [AGENTS.md](../../AGENTS.md).

This package is the project's own tooling layer: it reads the repository's
metadata files and validates them. It backs the `spec-dump`, `spec-lint`,
`spec-coverage`, `adr-index`, `demo-scenarios`, `append-history`,
`show-history`, `bundle-fit`, `pr-size`, `wire-context`, `docs-withheld`,
`docs-links`, `docs-legacy-urls`, `glossary-index`, `learnings-index`, and
`spec-backstop` console entry points, plus several pre-commit hooks.

Two exceptions to "reads the repository's metadata files". `planning/` reads a
GitHub GraphQL payload piped in on **stdin** rather than files on disk, so its
selection logic stays pure and testable without the network. The shell script
that fetches the payload owns the query
(`.agents/skills/shared/query-epic-subissues.sh`). And `docs/withheld.py`,
`docs/links.py` and `docs/legacy_urls.py` read the **built** `site/` tree, so
they only run after `mkdocs build` — they are the tools here whose input is a
build product rather than a source file, and all three fail rather than passing
when that input is missing (`docs/built_site.py`; DOCBW-03-005, DOCBW-03-007,
DOCBW-03-008, DF-09-009).

Nothing here is protocol code. The audience for its output is a human or an
agent who just edited a metadata file and got it wrong, so **error messages
are the product**.

## Subpackages

| Subpackage | Reads | Validates against |
|---|---|---|
| `specs/` | `specs/*.yaml`; a branch diff and the source it touches (`backstop/`) | `SpecFile` (schema.py) |
| `notes/` | `notes/*.md` frontmatter | `NotesFrontmatter` |
| `adr/` | `docs/adr/*.md` frontmatter | `AdrFrontmatter` |
| `history/` | `plan/history/**/*.md`, `plan/incoming/learnings/*.md` | `HistoryEntryFrontmatter` |
| `msm/` | a constant mapping table + the wire `SEMANTIC_REGISTRY` | — |
| `demo_scenarios/` | the `@scenario` registry in `vultron/demo/scenario/` | — |
| `docs/` | `git log` over `docs/`, for the what's-new page; `docs/reference/glossary.md` (`glossary_index.py`); the built `site/` tree (`withheld.py`, `links.py`, `legacy_urls.py`, via `built_site.py`); every `docs/**/*.md` page's `stakeholder_type`/`level` (`page_frontmatter.py`, DF-11) | `PageFrontmatter`, `WorkingRecordFrontmatter` (`page_schema.py`); publication axis: DOCBW-03-005; reference axis: DOCBW-03-007; continuity axis: DOCBW-03-008 |
| `planning/` | an Epic's sub-issue GraphQL payload on stdin | — (selection rules: PAD-15) |

Shared helpers live in three places — `base.py`, `markdown_tables.py`, and
`file_loading.py` (see [Loader Failure Attribution](#loader-failure-attribution-ms-17)).
**Do not re-derive any of them** — see the `repo_root` history below for what
that costs.

`base.py` — cross-subpackage primitives:

| Helper | What it is |
|---|---|
| `repo_root()` | every loader needs it and none may assume the caller's cwd |
| `MkDocsYamlLoader` | a `SafeLoader` tolerating `mkdocs.yml`'s `!ENV` and `!!python/name:` tags |
| `mkdocs_config()` | the parsed `mkdocs.yml` |
| `nav_paths()` | every document path reachable from the nav, flattened. The ADR nav check, the docs-frontmatter check and the scenario-narrative nav check read it; it was `adr/index_gen._iter_nav_paths` until #3451 |
| `not_in_nav_spec()` | the `not_in_nav` patterns, matched as MkDocs matches them (gitignore lines via `pathspec`); a hand-rolled glob here would disagree with the build |
| `nav_exclusion_fault()` | why a page that must stay out of the nav is misplaced (navved, or matched by no `not_in_nav` pattern), or `None`. The ADR check and the docs-frontmatter check share it (#3528) |

`markdown_tables.py` — the structural reader for every ratchet over
hand-written markdown: `iter_sections()` (heading-scoped, so a rule can exempt a
change-history section) and `iter_tables()` (pipe tables with their heading and
line number). It absorbs the hazards a hand-rolled regex gets wrong — fenced code
including *indented* fences, delimiter rows, escaped pipes. Three consumers grew
their own regex before #3451; if you are about to write `re.compile(r"^\|")`,
use this instead.

`repo_root` had six near-identical copies before #3450. Five were private
`_find_repo_root`; the sixth, `specs/registry.py:find_repo_root`, was public and
so survived the first sweep. All six are now aliases of the shared helper, kept
only because other modules and tests import them by their old names. **A grep for
the private spelling will not find a public duplicate** — search for the behaviour
(`pyproject.toml` walked upward), not the name.

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

Route both steps through `file_loading.py`; do not write a new wrapper
(MS-17-003). A ratchet (`test/architecture/test_metadata_loader_attribution.py`)
fails on any module here, other than that one, that re-raises a caught exception
as a path-prefixed `ValueError` — the shape every hand-written copy took.

| Helper | Use it for |
|---|---|
| `load_yaml(path, root=, loader=)` | a whole YAML file (`specs/*.yaml`) |
| `load_frontmatter(path, root=)` | a markdown file's frontmatter block |
| `loads_frontmatter(text)` | the no-path form, for content not yet on disk |
| `validate(Model, data, path=, root=, prefix=, key_lines=)` | the Pydantic half; `key_lines` locates the failure at its key's line |
| `FailureCollector` | report **every** failing file, not the first (SR-03-009) |

All raise `MetadataLoadError`, a `ValueError` subclass carrying `path`, `line`,
`column` and `detail` (MS-17-004); `FailureCollector.raise_if_any()` raises
`MetadataLoadErrors`, whose `failures` holds each one. Neither derives from
`VultronError` — that hierarchy is the protocol's, and a second ratchet keeps
`vultron/errors.py` out of this package. Pass `root=` so the path displays
repository-relative; a path outside it displays as given.

What the helper absorbs, so you know not to re-solve it:

1. **A YAML error is not a `ValueError`.** `yaml.scanner.ScannerError` derives
   from `Exception`, so a caller guarding `except (ValidationError, ValueError)`
   — the contract the loaders document — would not catch it, and it would
   escape as a traceback in which no frame names the offending file
   (MS-17-002). The helper re-raises it as `MetadataLoadError`. Callers that
   do not guard at all (`coverage.py`, `render.py`, `docs_render.py`,
   `llm_export.py`) still surface a traceback, but its message now names the
   file.

2. **Passing text instead of a stream costs you the filename.** PyYAML takes the
   name for its position mark from the stream it is given; hand it
   `path.read_text()` and every mark reads `"<unicode string>"`. The helper
   reads the position off `problem_mark` and pairs it with the real path, and
   PyYAML's own rendering of the mark never reaches the message. It also adds a
   cause hint for the faults PyYAML words unhelpfully (`CAUSE_HINTS`) — the
   unquoted `": "` in a plain scalar above all.

3. **A Pydantic error names the model, not the file.** A validation failure
   reports a positional path into the parsed structure (`groups.0.specs.0.kind`)
   and the model's class name. Across a directory that locates nothing, so
   `validate()` attributes it to the file too.

A loader that walks a set of files reports **every** failing file, not just the
first (SR-03-009). These loaders reject the corpus as a unit, so stopping at the
first fault makes the tool report less than it knows; see EH-07-001 for the
general principle, and `load_registry` or `history/incoming.py` for the shape.

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

# AGENTS.md — vultron/metadata

> For project-wide conventions, see the root [AGENTS.md](../../AGENTS.md).

This package is the project's own tooling layer: it reads the repository's
metadata files and validates them. It backs every `vultron.metadata.*` entry
in `pyproject.toml` `[project.scripts]` (`spec-dump`, `spec-backstop`,
`targeted-tests`, `append-history`, and the rest), plus pre-commit hooks.

Two exceptions to "reads the repository's metadata files". `planning/` reads a GitHub
payload piped in on **stdin** rather than files on disk, so its logic stays pure and
testable without the network. The caller fetches the payload
(`.agents/skills/shared/query-epic-subissues.sh`; `gh pr view` for `pr_body_lint.py`).
And `docs/withheld.py`, `docs/links.py` and `docs/legacy_urls.py` read the **built**
`site/` tree, so they only run after `mkdocs build` — they are the tools here whose
input is a build product rather than a source file, and all three fail rather than
passing when that input is missing (`docs/built_site.py`; DOCBW-03-005, DOCBW-03-007,
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
| `msm/` | the `occasions` and `page` on each `SEMANTIC_REGISTRY` entry, and the include directives of every `docs/` page; derives mapping status, "Sent by", section headings and "Seen in"; generates `msm/occasions.yaml` and `docs/reference/messages/_occasions/` (tables, sections, how-to embeds) (`occasions.py`) | `OccasionTable` (`_mapping.py`) |
| `demo_scenarios/` | the `@scenario` registry and the branch-point table in `vultron/demo/scenario/`; the committed recordings' case ids (`export_tree.py`) | — |
| `docs/` | `git log` over `docs/`, for the what's-new page; `docs/reference/glossary.md` (`glossary_index.py`); the built `site/` tree (`withheld.py`, `links.py`, `legacy_urls.py`, `path_boxes.py` — the `docs-path-boxes` check that every page renders its reading-path boxes, DF-11-023 — via `built_site.py`); each page's rendered HTML at build time (`anchor_ids.py`, an `on_page_content` hook under `hooks:` in `mkdocs.yml` — registers exec-emitted ids as anchor targets for `--strict`, #3735); the assembled `full.md` Markdown at build time (`full_page_links.py`, an `on_page_markdown` hook under `hooks:` — rewrites the Protocol Specification's same-section `page.md#fragment` links to in-page `#fragment` links on its single-page edition only, #4092); every `docs/**/*.md` page's `stakeholder_type`/`level`/`page_type`/`subject` (`page_frontmatter.py`, DF-11); each nav section's pages' `subject`, so no section mixes protocol and implementation pages (`nav_subjects.py`, `docs-nav-subjects`, DF-11-020/025); each `docs/start/` page's `thread:` (`threads.py` — the `docs-threads` check, the start-page listing `docs-site` splices and the reading-path box fragments it writes under `docs/start/_paths/`, which pages place by hand with `include-markdown`, DF-11-013–016, DF-11-022/023; `thread_order.py` — the `docs-thread-order` check that no member uses a term a later member introduces, reusing `level_order.py`'s scan, DF-11-024); the include directives naming the normative and specification-governs banners, against the normative set and protocol-design pages it declares (`normative_banner.py`, DF-12-006/007); the paragraphs of every target page, for the advisory cross-page copy report `lint-docs` reads (`duplicates.py`, `docs-duplicates`, SG-43, DF-10-002); the requirement registry, for the Requirements Catalog placement table, row lookup and link targets (`requirement_catalog.py`, DF-12-001/002/005) and the page an exec block prints on (`exec_page.py`, an `on_pre_page` hook under `hooks:`); the listed specification fragments, for RFC 2119 keywords in prose (`rfc2119_keywords.py`, DF-12-004); built-site URLs for links a renderer prints come from `site_urls.py`; `notes/nav-usability/suite.yaml`, a nav's labels and a built `site/`, for the agent usability test that gates a nav change (`nav_usability/`, ADR-0136) | `PageFrontmatter`, `WorkingRecordFrontmatter`, `ThreadDeclaration` (`page_schema.py`); publication axis: DOCBW-03-005; reference axis: DOCBW-03-007; continuity axis: DOCBW-03-008 |
| `planning/` | an Epic's sub-issue GraphQL payload on stdin; a branch diff (`size_bands.py`, `targeted_tests.py`); a PR body file or `gh pr view` payload (`pr_body_lint.py`); the theme catalog block in `notes/epic-themes.md` (`themes.py`) and `gh label list` (`theme_labels.py`, the `theme-labels` sync); every open Issue's labels, type, parents and Schedule (`theme_fit/`, the `theme-fit` check) | `ThemeCatalog` (selection rules: PAD-15; local test gate: PAD-18; PR body rules: PAD-20; themes: PAD-02-014–021) |

Shared helpers live in three places — `base.py`, `markdown_tables.py`, and
`file_loading.py` (see [Loader Failure Attribution](#loader-failure-attribution-ms-17)).
**Do not re-derive any of them** — see the `repo_root` history below for the cost.

`base.py` — cross-subpackage primitives:

| Helper | What it is |
|---|---|
| `repo_root()` | every loader needs it and none may assume the caller's cwd |
| `MkDocsYamlLoader` | a `SafeLoader` tolerating `mkdocs.yml`'s `!ENV` and `!!python/name:` tags |
| `mkdocs_config()` | the parsed `mkdocs.yml` |
| `nav_paths()` | every document path reachable from the nav, flattened. The ADR nav check, the docs-frontmatter check and the scenario-narrative nav check read it; it was `adr/index_gen._iter_nav_paths` until #3451 |
| `not_in_nav_spec()` | the `not_in_nav` patterns, matched as MkDocs matches them (gitignore lines via `pathspec`); a hand-rolled glob here would disagree with the build |
| `iter_tree_texts()`, `markdown_files()` | `(path, text)` for each file matching a pattern under some directories, unreadable files skipped. The PD-10 spec YAML line guard (`line_length.py`, also at the package root; its Python doc-line guard runs ruff's `W505` instead) and the MS-10-010 test index read through it. `markdown_files()` is every sorted `*.md` under one directory, not descending what its predicate prunes: use it, not `sorted(rglob("*.md"))` plus a filter, since a repository-wide `rglob` walks all of `.git` and `.venv` first |
| `gh_issue_state()`, `gh_issue_missing()`, `gh_lookup_failure()`, `GH_LOOKUP_ERRORS`, `issue_number()` | one issue's state through `gh issue view`, whether a failed lookup means "no such issue", the failure as text with `gh`'s stderr, and what a lookup can raise. The `verification_debt` owner check (`specs/verification.py`) and the ratchet-baseline owner report (`ratchet_owners.py`, ARCH-18-004) both read owners through them; a lookup that raises is reported, never passed |
| `nav_exclusion_fault()` | why a page that must stay out of the nav is misplaced (navved, or matched by no `not_in_nav` pattern), or `None`. The ADR check and the docs-frontmatter check share it (#3528) |

`markdown_tables.py` — the structural reader for every ratchet over
hand-written markdown: `iter_sections()` (heading-scoped, so a rule can exempt a
change-history section) and `iter_tables()` (pipe tables with their heading and
line number), plus `fenced_lines()`, the one fence reader. It absorbs the
hazards a hand-rolled regex gets wrong — fenced code at *any* indentation
(admonitions and content tabs nest a fence at four spaces, which strict
CommonMark would misread as indented code; #3685), closers that must match the
opener's run length and character, delimiter rows, escaped pipes. Three
consumers grew their own regex before #3451 and `landing_pages` kept a fourth
until #3685; if you are about to write `re.compile(r"^\|")` or
`re.compile(r"^\s*(```|~~~)")`, use this instead.

`repo_root` had six near-identical copies before #3450. Five were private
`_find_repo_root`; the sixth, `specs/registry.py:find_repo_root`, was public and
so survived the first sweep. All six are now aliases of the shared helper, kept
only because other modules and tests import them by their old names. **A grep for
the private spelling will not find a public duplicate** — search for the behaviour
(`pyproject.toml` walked upward), not the name.

## Generate vs. Check

Three subpackages own committed generated artifacts, and all split the same way:
**generate what is derivable, check what is prose.** `adr/index_gen.py`
regenerates `docs/adr/index.md` but only checks the hand-labelled nav;
`demo_scenarios/` regenerates the CI matrix, two scenario tables and the tree
index, leaving spec enumerations and nav to checks; `msm/occasions.py` regenerates
the occasion YAML and fragments, not page prose. Each is a `--check` hook
(`adr-index-sync`, `demo-scenarios-sync`, `demo-tree-sync`, `msm-occasions-sync`)
comparing byte for byte via `generated_files.py`; an ungated one is hand-edited.
`docs/landing_pages.py` (`docs-site-sync`) splits per page: a nav group's
`index.md` declares `contents: generated | routing | rendered`, and a routing
index is *checked* to link every member of its section, not written (#3617).
No fourth shape or default: an undeclared group index is a fault on purpose.

One trap specific to build-time rendering: MkDocs rewrites `.md` links with a
treeprocessor on **its own** `Markdown` instance, and `markdown-exec` converts a
block's output on a child instance that does not carry it. A `.md` target
printed from an exec block reaches the built HTML verbatim and 404s, and
`mkdocs build --strict` stays silent because it never saw the link. Emit
built-site URLs (`rv/`) from a renderer, not source paths.

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
| `load_yaml(path, root=, loader=)` | a whole YAML file (`specs/*.yaml`); no `loader` parses with `SAFE_LOADER` (libyaml when present, about 10x faster) and re-parses a fault in Python so its error reads unchanged; pass one only for its own errors |
| `load_frontmatter(path, root=)` | a markdown file's frontmatter block |
| `loads_frontmatter(text)` | the no-path form, for content not yet on disk |
| `validate(Model, data, path=, root=, prefix=, key_lines=, positions=)` | the Pydantic half; `key_lines` locates the failure at its key's line, `positions` (from `yaml_node_positions(text)`) at the failing node's line and column |
| `FailureCollector` | report **every** failing file, not the first (SR-03-009): these loaders reject the corpus as a unit, so stopping early reports less than the tool knows (EH-07-001 is the general principle; `load_registry` and `history/incoming.py` show the shape) |

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
step/condition text are scanned; `rationale` is exempt, because the problem it
states (MS-10-012) may be a removed thing that must not return.

A story-less `protocol` or `foundation` spec whose `statement` names a `.py`
file, a `vultron/`, `test/` or `scripts/` path, or `pytest`, `pydantic` or
`py_trees` is a hard error (MS-12-006; `verification:` is not scanned, #3943).
Naming code does not decide a kind (MS-12-002): reword or split (MS-12-010),
never relabel; suppress only a genuinely incidental reference. A `foundation`
spec needs an `as2`/`activitypub`/`http` tag (MS-12-009).

## Changing a Linter Check

A check that validates spec prose against a textual scan of the source tree can
be blinded by its own prose: naming a symbol in the check's docstring or error
message puts that token back into the scanned corpus, so the guard resolves it
as live and stops flagging the defect it exists to catch. Assert the negative
directly, and prefer file-scoped exclusions over package-scoped ones. Full
write-up: [`notes/spec-authoring-rules.md`](../../notes/spec-authoring-rules.md)
§ "A Grep-Corpus Guard Can Resolve Its Own Documentation".

A per-item advisory that is routinely true is not enforcement — mark each remaining hit
with its owning issue and check items one at a time, printing a per-kind count computed
from the markers (`specs/verification.py`, MS-10-005..008); never pin a committed count
to its live value. Select by tier, never by keyword: `priority.is_must_tier`, not
`== RFC2119Priority.MUST` (MS-02-004; `test_priority_tier_gate.py` fails it).

## Related

- `notes/spec-authoring-rules.md` — field enums, lint traps, coverage guard
- `notes/specs-vs-adrs.md` — whether a rule belongs in a spec at all
- `notes/history-management.md` — writing and reading rules for `plan/history/`;
  the entry format and layout are in `specs/history-management.yaml` (HM)
- `.agents/skills/shared/notes-writing-guide.md` — note kinds, `tracks:`, how to write
- `specs/spec-registry.yaml` (SR), `specs/meta-specifications.yaml` (MS),
  `specs/notes-frontmatter.yaml` (NF), `specs/history-management.yaml` (HM)

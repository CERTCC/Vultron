---
title: "A grep-corpus guard resolves its own documentation: the phantom-symbol check had to exclude lint.py to see the symbol it was built for"
type: learning
timestamp: "2026-09-02"
source: ISSUE-3022
signal: design-question
---

MS-15-004 (`_check_phantom_symbols` in `vultron/metadata/specs/lint.py`) rejects
a backticked all-caps-with-underscore token in a spec `statement` or
`verification` when it appears nowhere in the `vultron/` or `test/` Python text.
Resolution is textual on purpose — a spec may legitimately name a symbol that
only appears in a docstring — but that looseness bites in one specific way.

**The trap**: writing the check's own docstring, which names
`SEMANTICS_ACTIVITY_PATTERNS` while explaining the case it exists to catch, put
that token back into the corpus. The guard then resolved it as live and went
blind to the exact defect it had just been written for. Verified directly:
`'SEMANTICS_ACTIVITY_PATTERNS' in _SourceScan(Path('.')).symbols` was `True`
after the docstring was added.

**Fix**: exclude `vultron/metadata/specs/lint.py` and `test/metadata/specs/` from
the symbol corpus.

**The second trap, found by the first fix**: the exclusion was initially written
as the whole `vultron/metadata/specs/` package, which immediately produced two
false positives — `SHOULD_NOT` (an `RFC2119Priority` member defined in
`schema.py`) and `SCREAMING_SNAKE_CASE` (a token *shape* named in MS-15-004's own
statement). The linter package holds both prose and real spec-cited definitions;
only the prose-heavy file may be excluded.

Note the two exclusion sets are deliberately different and must stay so:

| Set | Excludes | Why |
|---|---|---|
| `_PHANTOM_ID_ALLOWLIST_DIRS` | `test/metadata/specs` only | A stale spec ID *cited by the linter* is a real defect — `vultron/metadata/specs/` must stay scanned, and this check correctly caught `MS-15-004` before its spec entry existed. |
| `_SYMBOL_CORPUS_EXCLUDED_PATHS` | `vultron/metadata/specs/lint.py` + `test/metadata/specs` | Those name symbols as examples, not as code the specs describe. |

**How to apply**: any lint check that validates spec prose against a *textual*
scan of the source tree can be defeated by its own documentation and error
messages. When adding one, assert the negative directly — a test that a symbol
named only inside the linter is still rejected — rather than assuming the corpus
excludes it. `test_lint_phantom_symbol_linter_own_source_excluded_from_corpus`
is that assertion. Prefer file-scoped exclusions over package-scoped ones, since
a package usually mixes prose with real definitions.

Related: [[20260831-spec-corpus-marker-design]] — the marker+ratchet precedent
for preferring a self-enforcing structural guard over an enumeration that drifts.

---
title: "mkdocs-bibtex inline-citation mode produces false-positive warnings from @-prefixed tokens in code and Turtle files"
type: learning
timestamp: "2026-07-22T00:00:00Z"
source: ISSUE-1581
---

`mkdocs-bibtex` ships with `enable_inline_citations: true` by default. When
enabled it applies the regex `(?<!\\)(?<![\[\w])@(?P<key>[\w:-]+)(?![^\[\]]*\])`
to every page's fully-expanded markdown, including content injected by
`include-markdown`. This silently matches bare `@word` tokens in fenced code
blocks, inline code spans, Turtle/OWL ontology directives (`@prefix`, `@base`),
and URL fragments (e.g. YouTube channel handles).

The Vultron docs use `[@key]` pandoc syntax exclusively for real citations;
inline-citation mode provides no value and generates noise.

**Fix**: set `enable_inline_citations: false` under the `bibtex:` plugin block
in `mkdocs.yml`. One-line config change; no code or doc content changes needed.

**Detection**: `uv run mkdocs build 2>&1 | grep "Inline reference to unknown key"`.
If the output is non-empty, inline-citation mode is active and triggering false
positives.

**Scope of false positives found**:

- Code decorators in prose (`@pytest.mark.*`, `@dataclass`, `@context`, `@v4`,
  `@main`) — in both inline code spans and fenced blocks
- Turtle ontology `@prefix` / `@base` directives (five ontology reference pages
  each include a raw `.ttl`/`.owl` file via `include-markdown`)
- YouTube URL fragment (`@petterogren7535` in ADR-0002)

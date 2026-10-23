---
source: ISSUE-1581
timestamp: '2026-07-22T13:53:24.742907+00:00'
title: Disable bibtex inline citations to eliminate false-positive @-key warnings
type: implementation
---

Fixed #1581. The mkdocs-bibtex plugin's inline-citation regex matched bare @word patterns in code blocks and Turtle ontology directives, emitting 18 spurious WARNING lines per build. Set enable_inline_citations: false in mkdocs.yml under the bibtex: plugin. All real citations use [@key] pandoc syntax; inline mode was unused. One-line config change; zero tests needed (verification is uv run mkdocs build producing no bibtex warnings). PR: <https://github.com/CERTCC/Vultron/pull/1582>

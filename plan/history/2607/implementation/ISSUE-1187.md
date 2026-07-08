---
source: ISSUE-1187
timestamp: '2026-07-08T15:38:58.546786+00:00'
title: 'FUZZ-08a-bis: Add factory-fn placement field to all fuzzer node catalog entries'
type: implementation
---

## Issue #1187 — FUZZ-08a-bis: Add factory-fn placement field to all fuzzer node catalog entries

Added the `factory-fn placement` field to every non-ProtocolInternal catalog entry across all four fuzzer node domain files (75 nodes in report-management alone, plus 14 in embargo, 1 in messaging, 3 N/A in vul-discovery).

Key decisions:

- Nodes with existing factory functions in `vultron/core/behaviors/` map directly with ordering hints (create_validate_report_tree, create_prioritize_subtree)
- Nodes without existing factory functions use `FUTURE: vultron.core.behaviors.<module>.create_<name>_tree` with tracking issue references (#1246–#1255)
- ProtocolInternal nodes (terminal success placeholders) get `N/A`
- Simulation-only nodes (DiscoverVulnerabilityBt) get `N/A`
- Reclassified 11+ Composer→Actuator nodes per ADR-0024 Actuator amendment
- Fixed stale "four shapes" count references in ADR-0024 and bt-fuzzer-nodes.md

Resolved merge conflict caused by PR #1243 (issue #1240) reclassifying 9 Sentinel→Retriever nodes; updated factory-fn descriptions to match.

PR: <https://github.com/CERTCC/Vultron/pull/1261>

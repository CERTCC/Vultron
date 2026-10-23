---
source: CONCERN-1188
timestamp: '2026-06-26T15:05:39.754128+00:00'
title: 'FUZZ-08a over-applied N/A: automation potential and call-out point shape are
  orthogonal'
type: learning
---

## Summary

PR #1179 (FUZZ-08a) assigned `call-out point shape: N/A` to ~35 nodes that
have "High automation potential." The implicit reasoning was: if a node can be
fully automated, it does not need an agent shape. This conflates two
orthogonal concepts.

## Category

Classification Error / Documentation Gap

## Severity

Medium

## Evidence

Of the 43 N/A nodes across the four catalog files, only ~5 are correctly N/A:

- 2 terminal placeholders (`NoThreatsFound`, `NoVulFound`) — AlwaysSucceed
  fallback leaves with no real decision logic
- 3 simulation-only vul-discovery nodes not ported to new architecture

The remaining ~38 nodes were assigned N/A because their `automation potential`
is High, but they clearly require an external seam:

- Conditions that query metadata flags, registries, or external APIs
  (`IdAssigned`, `MitigationDeployed`, `AllPublished`, `EmbargoTimerExpired`,
  `HaveExploit`, and many more) — these are **Retrievers** or **Sentinels**
- Actions that call external services (`RequestId`, `AssignId`, `Publish`,
  `InjectParticipant/Vendor/Coordinator/Other`) — **Retrievers** or **Composers**
- Integration hooks that trigger site-specific side-effects (`OnDefer`,
  `OnAccept`, `OnEmbargoAccept/Reject/Exit`, `PreCloseAction`) — possibly
  **Composers**, possibly correctly N/A depending on interpretation

## Root Cause

The ADR-0024 agent shape taxonomy describes **the seam structure** (how input
enters and output exits the call-out point), not whether that exchange is done
by a human or an automated system. A Retriever backed by a REST API is still
a Retriever. The catalog update conflated "automatable" with "no shape needed."

## Impact if Ignored

FUZZ-08a-bis (#1187) will add factory-fn placement data to nodes whose shapes
are wrong. FUZZ-08b (#1151) and FUZZ-08d-08g will then build the wrong
abstraction seams — e.g., treating a Retriever as having no blackboard output
contract, or skipping injection seams for nodes that will need them.

## Suggested Action

Reclassify all N/A nodes in the four catalog files. For each N/A entry, apply
the ADR-0024 shape decision tree independently of automation potential:

- Binary condition monitoring an external state → Sentinel
- Reads a query, returns structured facts from external source → Retriever
- Reads context, produces an artifact or side-effect → Composer
- Reads situation, writes a recommendation/judgment → Evaluator
- Truly no call-out point (terminal leaf, structural composite) → ProtocolInternal

This reclassification should be done as part of or before FUZZ-08a-bis (#1187)
so that factory-fn placement is assigned to nodes with the correct shape.

Additionally, rename the ambiguous "N/A" labels:

- `automation potential: N/A` → `TerminalPlaceholder`
- `call-out point shape: N/A` → `ProtocolInternal`

**Resolved**: 2026-06-26 — implementation tracked in #1193.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1192>.
Spec: `specs/behavior-tree-integration.yaml` (BT-16-005, BT-18-005).
Notes: `notes/bt-fuzzer-nodes.md` (entry format updated).

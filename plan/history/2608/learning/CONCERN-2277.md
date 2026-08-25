---
source: CONCERN-2277
timestamp: '2026-08-17T20:02:22.878778+00:00'
title: Restated counts in spec cross-references drift silently
type: learning
---

## Concern

Numeric and enumerative prose that is *repeated across sibling requirements*
drifts silently. The spec registry linter checks structure (ids, kinds,
priorities, cross-reference targets) but nothing checks that two requirements
telling the same story tell the same story.

Concrete instance, found while doing ISSUE-2266: DEMOMA-16-001 declared four
universal event types, and the phrase "the four universal types (DEMOMA-16-001)"
was copied into **nine** sibling statements (DEMOMA-16-002 … -16-011) plus
DEMOCI-04-004 and DEMOCI-06-002 in a second spec file. Promoting `engage_case`
to the fifth universal type therefore required 12 coordinated edits to keep
MUST-level statements factually true.

The failure mode is spec-vs-spec drift: there is no test that can fail — a
reader picks whichever statement they read first.

## Resolution

The broader principle: long-lived docs (specs, notes, AGENTS.md) must never
state ephemeral counts that will drift out of sync. When cross-referencing
another spec item, omit the count and cite the source by ID.

**Resolved**: 2026-08-17 — implemented in PR #2349.

Docs PR: <https://github.com/CERTCC/Vultron/pull/2349>.
Spec: `specs/meta-specifications.yaml` (MS-16-001).
Notes: `notes/specs-vs-adrs.md` (new section "Never State Ephemeral Counts").

---
status: accepted
date: 2026-07-21
deciders: Vultron maintainers
consulted: Audio review of the Vultron specification corpus, July 2026
---

# Replace Six-Kind Spec Taxonomy with Four-Tier Portability Hierarchy

## Context and Problem Statement

The specification corpus uses a six-kind taxonomy (`domain`, `pattern`,
`general`, `language`, `implementation`, `dev-process`) intended to form a
portability hierarchy. The taxonomy is structurally sound in concept but is
inconsistently applied in practice:

- ~48 specs labeled `domain` reference Python constructs (BT nodes, factory
  functions, module paths) that are specific to this implementation, not the
  Vultron protocol.
- `pattern` conflates language-agnostic architectural principles with
  BT-specific mechanisms that only apply to this codebase.
- `general` spans transferable architectural principles (idempotency, health
  endpoints) and project process rules (CI security, spec authoring
  conventions) with no clear separation.

The consequence: an independent implementer attempting to build a
Vultron-compatible system in Rust, Go, or Java cannot easily identify which
specs apply to them without mentally filtering implementation noise from every
tier.

A secondary problem is that no mechanical decision rule exists for classifying
new specs, so the ambiguity compounds over time.

## Decision Drivers

- Independent implementers need a concise, implementation-agnostic set of
  specs they can adopt without encountering Python- or BT-specific guidance.
- A mechanical classification test is needed so specs route consistently and
  the taxonomy does not degrade again.
- The existing six kinds map onto four natural abstraction layers; renaming
  and consolidating preserves intent while removing ambiguity.

## Considered Options

- **A — Keep six kinds, reclassify contaminated specs only.** The kind names
  stay; only misclassified individual specs are corrected.
- **B — Rename `domain` → `protocol`, keep the other five, reclassify
  contaminated specs.** Minimal schema change; the most important ambiguity
  (`domain` being used for both protocol and implementation content) is fixed.
- **C — Replace six kinds with four: `protocol`, `architecture`, `project`,
  `process`.** Rename and consolidate across the full taxonomy, then reclassify
  contaminated specs.

## Decision Outcome

Chosen option: **C — four kinds**.

Option A preserves a name (`domain`) that has demonstrably attracted
misclassification because it is ambiguous between "CVD domain semantics" and
"domain layer of this codebase." Option B fixes the worst ambiguity but leaves
the `pattern`/`general` overlap unresolved. Option C resolves all ambiguities
with a clean four-tier model and a mechanical decision tree, at the cost of a
larger one-time migration.

### The Four Tiers

| Kind | Meaning |
|---|---|
| `protocol` | Required for Vultron compliance — any implementation in any language must satisfy this. Covers wire behavior, state machine invariants, behavioral contracts, message semantics, and protocol rules. |
| `architecture` | Implementation-independent structural guidance — transferable across languages and frameworks, but not required for Vultron compliance per se. Covers hexagonal boundaries, event-driven dispatch, port/adapter patterns, fail-fast principles. |
| `project` | Specific to this codebase — Python paths, BT nodes, py_trees, pydantic, factory names, module organization, endpoint conventions. |
| `process` | How we run this project — CI config, GitHub workflow, agent conventions, docs standards, spec authoring rules. |

### Portability Stack

The four tiers form a subset ordering:

```text
protocol ⊆ architecture ⊆ project ⊆ process
```

Portability use cases:

| Goal | Tiers needed |
|---|---|
| Implement Vultron in any language | `protocol` |
| Understand the reference architecture | `protocol` + `architecture` |
| Contribute to this Python codebase | `protocol` + `architecture` + `project` |
| Contribute to this project (including process) | all four |

### Classification Decision Tree

When adding a new spec, stop at the first matching question:

1. **Is this about how we run the project** — CI config, GitHub workflow,
   agent conventions, docs standards, spec authoring rules?
   → `process`

2. **Does this reference a language construct, library, file path, class,
   function, module, or codebase-specific mechanism?**
   (py_trees, pydantic, `vultron/`, `.py`, pytest, BT nodes, etc.)
   → `project`

3. **Would an independent implementer need to satisfy this to be considered
   Vultron-compliant**, regardless of language or framework?
   (wire behavior, state machine invariants, behavioral contracts,
   message semantics, protocol rules)
   → `protocol`

4. **None of the above** — structural or behavioral constraint that is
   implementation-independent but not required for Vultron compliance.
   → `architecture`

The ordering matters: process is checked first because it is the most
obviously non-system content; project is checked second because a
codebase-specific reference immediately disqualifies `protocol` or
`architecture`; the compliance test distinguishes `protocol` from
`architecture`.

### Migration Map

| Old kind | New kind | Notes |
|---|---|---|
| `domain` | `protocol` | Rename; ~48 contaminated specs reclassified to `project` |
| `pattern` | `architecture` or `project` | BT/py_trees refs → `project`; everything else → `architecture` |
| `general` | `protocol`, `architecture`, or `process` | Wire-observable specs → `protocol`; CISEC/MS/PD/DF → `process`; ID/OB/HP-07 → `architecture` |
| `language` | `project` | Mechanical 1:1 rename |
| `implementation` | `project` | Mechanical 1:1 rename |
| `dev-process` | `process` | Mechanical 1:1 rename |

### Consequences

- Good, because an independent implementer can filter to `protocol` and get a
  complete, implementation-agnostic set of requirements with no noise.
- Good, because the decision tree is mechanical — new specs route consistently
  without case-by-case debate.
- Good, because `protocol` replaces `domain`, removing the ambiguity that
  caused the contamination in the first place.
- Good, because merging `language` + `implementation` → `project` and
  `general` + `dev-process` → `process` (with splits) reduces the number of
  tiers from six to four without losing information.
- Bad, because the migration touches every spec file — all YAML files must be
  updated and the `SpecKind` enum, docs renderer, lint rules, and test suite
  must be updated in lockstep.
- Bad, because all existing cross-references in docs pages keyed by kind slug
  (`/reference/specs/domain/`, etc.) must be updated or redirected.

## Validation

- The `SpecKind` enum in `vultron/metadata/specs/schema.py` is updated to
  the four new values; the portability use-case docstring is rewritten to
  match this ADR.
- `test/metadata/specs/test_kind_page_coverage.py` continues to enforce
  that every `SpecKind` value has a corresponding docs page — the four new
  pages replace the six old ones.
- Lint rules that previously enforced kind validity are updated to accept
  only the four new values.
- The spec authoring guide (`specs/meta-specification.yaml` MS group and
  `specs/README.md`) is updated to document the decision tree.

## More Information

- The audio review (July 2026) that prompted this decision identified
  PD-09-004 and PD-09-005 as examples of project-management content leaking
  into normative specs, and BT-06-001 (`createVFDMachine`, `createPXAEngine`)
  as examples of implementation identifiers misclassified as `domain`.
- ADR-0009 (hexagonal architecture) — the architectural constraints that
  populate the `architecture` tier.
- `specs/meta-specification.yaml` — spec authoring conventions; the
  classification decision tree should be added to the MS group.

Generated spec requirements: `specs/meta-specification.yaml` MS group
(decision tree as a new spec group) and `specs/spec-registry.yaml` SR-02-005
(updated kind enum definition).

---
title: "SR.6.1\u2013SR.6.3 \u2014 Spec Migration to YAML (Priority 460)"
type: implementation
timestamp: '2026-04-27T00:00:00+00:00'
source: LEGACY-2026-04-27-sr-6-1-sr-6-3-spec-migration-to-yaml-priority-46
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 8134
legacy_heading: "SR.6.1\u2013SR.6.3 \u2014 Spec Migration to YAML (Priority\
  \ 460)"
date_source: git-blame
---

## SR.6.1–SR.6.3 — Spec Migration to YAML (Priority 460)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:8134`
**Canonical date**: 2026-04-27 (git blame)
**Legacy heading**

```text
SR.6.1–SR.6.3 — Spec Migration to YAML (Priority 460)
```

**Completed**: SR.6.1 (migration script), SR.6.2 (migrate all specs),
SR.6.3 (linter validation)

### What was done

1. **Schema change**: Made `rationale` optional (`NonEmptyStr | None = None`)
   in `StatementSpec` since many existing specs lack rationale text. Updated
   lint.py guard and added tests.

2. **Migration script** (`tools/migrate_spec_md_to_yaml.py`): Parses
   `specs/*.md` requirement files and outputs `specs/*.yaml` with:
   - Multi-line statement support (continuation lines)
   - Relationship extraction (refines, derives-from, supersedes, etc.)
   - Sub-bullet text collection (rationale, implementation notes)
   - Dash-prefix ID transformation (CI-SEC→CISEC, DEMO-MA→DEMOMA,
     UC-ORG→UCORG, IMPL-TS→IMPLTS)

3. **Migration run**: All 51 spec .md files successfully converted to YAML.

4. **Duplicate ID fixes**: Found and fixed two duplicate IDs in source
   markdown:
   - `CS-13-001` in code-style.md → second instance renumbered to CS-15-001
   - `SR-08-005` in spec-registry.md → second instance renumbered to
     SR-08-007

5. **Dash-prefix ID rename** (project-wide): Renamed all references in .py
   and .md files:
   - CI-SEC → CISEC (test/ci/, docs/adr/, specs/)
   - DEMO-MA → DEMOMA (integration_tests/, vultron/demo/, specs/, notes/)
   - UC-ORG → UCORG (specs/)
   - IMPL-TS → IMPLTS (specs/, plan/)

6. **Linter passes** with exit 0. Remaining WARN (no tags) and ERROR
   (broken cross-refs to deprecated CS-01-002/003/006, ADR-00, IDEM-01-001)
   are pre-existing data issues, not migration bugs.

### Files created

- `tools/migrate_spec_md_to_yaml.py`
- All `specs/*.yaml` files (51 files)

### Files modified

- `vultron/metadata/specs/schema.py` (rationale optional)
- `vultron/metadata/specs/lint.py` (None guard for rationale)
- `test/metadata/specs/test_schema.py` (rationale None tests)
- `specs/code-style.yaml` (CS-13-001 → CS-15-001 dedup + IMPLTS rename)
- `specs/spec-registry.yaml` (SR-08-005 → SR-08-007 dedup)
- Multiple .py and .md files (dash-prefix ID renames)

### Remaining SR.6 tasks

- SR.6.4: Update skills/prompts/agent instructions for .yaml paths
- SR.6.5: Update README.md/AGENTS.md references
- SR.6.6: Delete original .md requirement files

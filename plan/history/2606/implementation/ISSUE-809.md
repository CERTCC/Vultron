---
source: ISSUE-809
timestamp: '2026-06-10T17:37:28.640162+00:00'
title: Add hierarchy invariant tests for CoreObject and wire-branch subclasses
type: implementation
---

## Issue #809 — Add hierarchy invariant tests for CoreObject and wire-branch subclasses

Created test module `test/architecture/test_hierarchy_invariants.py` with 7 tests that
enforce structural invariants for the core (domain) and wire (ActivityStreams) object
hierarchies.

### Tests implemented

1. **test_all_core_vocabulary_are_core_object_subclasses**: Validates all CORE_VOCABULARY
   entries are CoreObject subclasses (ARCH-12-003)
2. **test_core_object_uses_vultron_base_not_as_base**: Ensures core classes don't inherit
   from as_Base (wire-layer concern)
3. **test_no_core_object_has_to_camel_alias_generator**: Detects wire-specific
   serialization config (alias_generator=to_camel) on core classes — SKIPPED (known
   ADR-0017 migration violation)
4. **test_all_vocabulary_are_as_base_subclasses**: Validates wire VOCABULARY classes
   inherit from as_Base (ARCH-12-003) — SKIPPED (known ADR-0017 migration violation)
5. **test_all_vocabulary_inherit_transitive_vultron_base**: Ensures both branches share
   VultronBase root (ARCH-12-002)
6. **test_core_vocabulary_does_not_reference_as2_namespace_directly**: Placeholder for
   AS2 namespace separation verification
7. **test_core_object_base_model_config_is_lenient**: Validates CoreObject uses lenient
   config (ARCH-12-004)

### Results

- 5 tests pass, 2 skipped (documenting known violations from issue #800)
- Full test suite: 3145 passed, 14 skipped, 219 deselected
- Black, flake8, mypy, pyright all clean
- All acceptance criteria met

### Specification references

- `specs/architecture.yaml`: ARCH-12-003, ARCH-12-004, ARCH-12-007
- `docs/adr/0017-domain-wire-object-separation.md`: ADR reference for two-branch hierarchy

**Completed**: 2026-06-10 — PR <https://github.com/CERTCC/Vultron/pull/885>

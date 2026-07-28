# PR Triage — Reference

Detailed criteria for each triage phase, the artifact schema, and the comment
format. Referenced from SKILL.md.

---

## Spec Conformance Criteria

When checking changed code against loaded specs, focus on the spec IDs most
relevant to the changed file paths:

| Changed path prefix | Primary specs to load |
|---|---|
| `vultron/wire/as2/` | `architecture.yaml` (ARCH-14), `code-style.yaml` (CS-08) |
| `vultron/core/behaviors/` | `behavior-tree-integration.yaml`, `behavior-tree-node-design.yaml` |
| `vultron/core/use_cases/` | `behavior-tree-integration.yaml` (BT-06, BT-15), `inbox-orchestration.yaml` |
| `vultron/core/models/` | `architecture.yaml` (ARCH-10, ARCH-12), `code-style.yaml` (CS-20) |
| `vultron/adapters/` | `outbox.yaml`, `architecture.yaml` (ARCH-14) |
| `vultron/demo/` | `behavior-tree-integration.yaml` (BT demo patterns) |
| `docs/`, `notes/`, `specs/` | `project-documentation.yaml` |
| `plan/history/` | `history-management.yaml` (HM-01–HM-05) |

For each spec ID mentioned in the linked issue or PR body, confirm the
corresponding requirement is met in the diff.

---

## AGENTS.md Rule Checklist

Check the diff for violations of these non-negotiable rules. Emit **FAIL** for
confirmed violations.

### Naming

- [ ] Domain class names use CVD-domain vocabulary, not wire-format parallels
- [ ] `vul` (not `vuln`) as the abbreviation for vulnerability
- [ ] Wire layer classes in `vultron/wire/as2/vocab/objects/` use `as_` prefix
- [ ] Core domain classes do NOT use `as_` prefix
- [ ] Use-case classes follow Received/Svc/\_trigger naming conventions

### Type Safety and Validation

- [ ] No `Optional[str]` fields that accept empty strings — use `NonEmptyString`
  or `OptionalNonEmptyString`, or add a validator
- [ ] No new `Any` usages without justification
- [ ] Pydantic v2 style (`model_validator`, `field_validator`) throughout
- [ ] Fail-fast domain objects: required fields not typed as `X | None`
  in concrete subclasses (ARCH-10-001)
- [ ] Protocol fields stay in sync with concrete implementations (CS-20-001)
- [ ] `TypeGuard` discriminators use only Protocol-declared fields (CS-20-002)

### BT Integration (if `behaviors/` or `use_cases/` changed)

- [ ] BT nodes do NOT call use-case classes from `update()` (no BT→UC→BT chain)
- [ ] BT nodes do NOT import from use-case modules
- [ ] `update()` stays under ~20–30 lines; large nodes decomposed into subtrees
- [ ] Protocol-significant behavior lives in BT leaf nodes, not in `execute()`
- [ ] `execute()` does NOT call `dl.save()` / `dl.create()` / `dl.update()` directly
- [ ] Received-side BTs commit the triggering activity BEFORE applying protocol effects
- [ ] Guarded-commit BTs are role-gated (CaseActor identity check before commit)
- [ ] No new `CommitCaseLedgerEntryNode` calls bypassing `BTBridge`

### ActivityStreams / Wire Layer (if `wire/as2/` changed)

- [ ] `SEMANTICS_ACTIVITY_PATTERNS`: specific patterns ordered before general ones
- [ ] `rehydrate()` called before pattern matching
- [ ] Outbound activities use factory functions in `vultron.wire.as2.factories`
- [ ] `as_VulnerabilityCase` (wire) vs `VulnerabilityCase` (core) — correct prefix in each layer

### Use Cases (if `use_cases/` changed)

- [ ] Received-side use cases do NOT spoof another actor's identity
- [ ] Trigger-side `execute()` delegates SM transitions to `BTBridge`, not inline
- [ ] No `case_addressees()` on the participant sender side (PCR-08-001/02)

### Adapters (if `adapters/` changed)

- [ ] Stub adapter files raise `NotImplementedError`, not silent no-op
- [ ] `create_app()` does NOT mutate module-level singletons
- [ ] Actor IDs are full URIs

### Module Organization

- [ ] No flat `nodes.py` in BT areas (must use `nodes/` subpackage)
- [ ] New submodules after a split stay under 500 lines
- [ ] Subpackage `__init__.py` re-exports all public names (including request models)

---

## ADR Check Criteria

Architectural signals that warrant an ADR (per `notes/specs-vs-adrs.md`
MS-11-001–MS-11-006):

- Introducing a new layer or cross-layer dependency direction
- Changing the public API or persistence schema
- Adding a new adapter type (driving or driven)
- Changing how BT execution is orchestrated (e.g., concurrency model)
- Adopting a new protocol pattern with broad reuse implications
- Reversing or superseding a previous architectural decision

**Check procedure:**

1. `gh pr diff <number> -- docs/adr/` — did the PR add or modify an ADR?
2. `cat docs/adr/index.md` — does an existing ADR cover the area changed?
3. If the PR's approach contradicts an existing ADR without a new ADR: **FAIL**.
4. If the change has architectural signals but no ADR: **IMPROVE** with a
   suggested title for the ADR.

---

## Notes and Docs Currency Criteria

### Domain-to-notes mapping

| Changed domain | Potentially relevant notes files |
|---|---|
| `wire/as2/` | `activitystreams-semantics.md`, `vocabulary-registry.md` |
| `core/behaviors/` | `bt-integration.md` |
| `core/use_cases/` | `bt-integration.md`, `event-driven-control-flow.md` |
| `core/models/case` | `case-state-model.md`, `case-communication-model.md` |
| `adapters/` | `architecture-adapters.md`, `architecture-hexagonal.md` |
| `core/ports/` | `architecture-hexagonal.md` |
| Embargo logic | `participant-embargo-consent.md`, `embargo-lifecycle.md` |
| Case ledger | `case-ledger-authority.md` |
| Inbox processing | `inbox-orchestration.md` |
| Participant routing | `case-communication-model.md` |

### Check procedure

1. Identify relevant notes from the table above.
2. For each relevant note: was it modified in the PR diff? If not: **IMPROVE**.
3. For each `notes/*.md` file **modified** in the PR: validate frontmatter.
4. If any modified note has `status: superseded`, flag that it should have
   been moved to `archived_notes/` instead of edited.
5. If `docs/` was modified: confirm `uv run mkdocs build --strict` passed
   (check CI or note it as pending).

---

## Integration Test Detection

Emit a finding (captured as `needs_integration_tests: true` in `pr_metadata`)
if the PR modifies any of:

- `demo/` — any demo script or orchestration file
- `integration_tests/` — any integration test file
- `adapters/` — driving or driven adapters
- `vultron/core/behaviors/` — behavior tree logic
- `vultron/core/use_cases/` — use-case implementations
- `vultron/wire/as2/extractor.py` — semantic extraction

`pr-execute` reads this flag from `pr_metadata` to decide whether to run the
full suite.

---

## Triage Artifact Schema

File: `.claude/pr-{number}-triage.json`

```json
{
  "schema_version": "1.0",
  "pr_number": 1234,
  "timestamp": "2026-01-01T00:00:00Z",
  "pr_metadata": {
    "title": "...",
    "head_ref": "task/1234-slug",
    "base_ref": "main",
    "linked_issues": [100, 101],
    "changed_files": ["vultron/core/behaviors/foo.py"],
    "ci_status": "failing",
    "domains": ["core/behaviors"],
    "needs_integration_tests": true
  },
  "findings": [
    {
      "id": "phase5-missing-nonemptystring-0",
      "phase": 5,
      "phase_name": "spec-conformance",
      "severity": "FAIL",
      "description": "Field `summary` typed as Optional[str] — must use OptionalNonEmptyString (CS-20-001)",
      "decision_outcome": "fix-now",
      "file": "vultron/core/models/case/case.py",
      "line": 42,
      "spec_ids": ["CS-20-001"],
      "adr_refs": [],
      "notes": null
    }
  ],
  "triage_comment_url": "https://github.com/CERTCC/Vultron/pull/1234#issuecomment-..."
}
```

### Finding ID Rules

- Format: `phase{N}-{kebab-description}-{index}`
- Index is a zero-based integer suffix that guarantees uniqueness within the run
- Description is a kebab-case slug of the finding (≤ 5 words)
- Examples: `phase7-bt-node-imports-usecase-0`, `phase11-ci-black-fail-0`
- Execute and verify use `finding_id` as the stable cross-artifact key

### Decision Outcome Values

| Value | When to use |
|---|---|
| `fix-now` | Trivial fix OR non-trivial but same family |
| `fix-now-expand-scope` | Non-trivial, same family, expands PR scope meaningfully |
| `new-issue-ask` | Non-trivial, distant cousin — execute files issue then asks user |
| `new-issue-no-ask` | Requires separate design effort — execute files issue and continues |

---

## Triage Comment Format

```markdown
## PR Triage: #<number> — <title>

**Linked issues**: #N (<title>)
**Changed files**: <count> files — <domains>
**CI status**: ✅ passing / ❌ failing / ⏳ pending
**Needs integration tests**: yes / no

---

### Findings

| # | Phase | Severity | Description | Outcome |
|---|---|---|---|---|
| phase5-missing-nonemptystring-0 | spec-conformance | ❌ FAIL | Field `summary` must use OptionalNonEmptyString | fix-now |
| phase9-bt-integration-note-stale-0 | notes-currency | ⚠️ IMPROVE | `notes/bt-integration.md` not updated | fix-now |
| phase8-unused-import-0 | code-review | ⚠️ IMPROVE | Unused import in `behaviors/foo.py:12` | fix-now |

**Total**: 2 FAIL · 1 IMPROVE · 0 NEW-ISSUE

---

*Triage artifact: `.claude/pr-<number>-triage.json`*
*Next step: run `/pr-execute` or `/pr-ship` to apply fixes.*
```

Severity emoji: ❌ FAIL · ⚠️ IMPROVE · 🎫 NEW-ISSUE

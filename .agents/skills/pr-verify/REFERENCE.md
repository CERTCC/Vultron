# PR Verify — Reference

---

## Verify Comment Format

```markdown
## PR Verify: #<number> — <title>

**Overall verdict**: ✅ READY-TO-MERGE / ❌ GAPS-FOUND / 🔀 CONFLICTS-FOUND / ⏳ PENDING-CI / ⏳ PENDING-MERGE-CHECK
**CI status**: ✅ passing / ❌ failing / ⏳ pending
**Merge state**: ✅ MERGEABLE (CLEAN) / 🔀 CONFLICTING (DIRTY) / ⚠️ BEHIND / 📝 DRAFT / ⏳ UNKNOWN — base `<base_ref>`
**Base sync in execute**: ✅ merged @ `def5678` (<N> conflicts resolved) / ✅ already current / ❌ not performed
**Integrity check**: ✅ all <N> findings accounted for / ❌ INCOMPLETE-EXECUTE (<M> of <N> results found)

---

### 🔀 Merge Conflicts — Blocking

This PR conflicts with `<base_ref>` and cannot be merged. Conflicting paths:

- `vultron/core/models/case/case.py`
- `uv.lock`

Re-run `/pr-execute` (Phase 4 syncs and resolves), or resolve manually with
`bash .agents/skills/shared/sync-with-main.sh <base_ref>`, then
`git add <paths> && git commit --no-edit && git push`.

*Omit this section when merge state is clear.*

---

### Finding Verdicts

| Finding | Severity | Outcome | Verdict |
|---|---|---|---|
| phase5-missing-nonemptystring-0 | ❌ FAIL | fixed @ `abc1234` | ✅ CONFIRMED |
| phase8-unused-import-0 | ⚠️ IMPROVE | fixed @ `abc1234` | ✅ CONFIRMED |
| phase9-distant-refactor-0 | 🎫 NEW-ISSUE | filed as #999 | 📋 NOTED |
| phase11-preexisting-test-fail-0 | ❌ FAIL | skipped — pre-existing Bug #1001 | 📋 NOTED |

---

### Deferred Items — Your Decision Needed

The following findings were filed as issues during execute but not folded into
this PR. Please decide whether to fold them in before merge:

| Finding | Issue | Recommendation |
|---|---|---|
| phase8-extract-helper-0 | #1000 | Leave for issue — low effort ratio |

---

*Artifacts cleaned up.* / *Artifacts preserved — re-run `/pr-execute` to address gaps.*
```

### Verdict Emoji Key

| Symbol | Meaning |
|---|---|
| ✅ CONFIRMED | Fix present at HEAD; commit ref valid |
| ❌ UNRESOLVED | Commit ref found but HEAD does not show the fix |
| ❌ MISSING-COMMIT | Commit ref not found on branch |
| 📋 NOTED | filed/skipped/deferred-ask — no code check; issue confirmed open |
| ⚠️ INCOMPLETE-EXECUTE | Finding count mismatch; execute likely interrupted |
| ⚠️ UNVERIFIED-CI-FAILING | CI still failing after execute's push; fix may be correct but cannot be confirmed |
| 🔀 MERGE-CONFLICT | `mergeable: CONFLICTING`, `mergeStateStatus: DIRTY`, or conflict markers found at HEAD |
| ⏳ MERGE-STATE-UNKNOWN | GitHub had not computed mergeability after polling |
| ⚠️ BRANCH-BEHIND | `mergeStateStatus: BEHIND` — base advanced and the repo requires up-to-date branches |
| ⚠️ UNSYNCED-EXECUTE | `execute.merge_state` missing or `synced: false` — execute never confirmed mergeability |
| 📝 PR-IS-DRAFT | PR is still a draft (check for a lingering `needs-rebase` label) |
| 🔒 BLOCKED-BY-POLICY | `mergeStateStatus: BLOCKED` — missing required review/check; reported, not verdict-blocking |

### Overall Verdict Rules

Evaluated top to bottom; first match wins.

| # | Verdict | Condition |
|---|---|---|
| 1 | `CONFLICTS-FOUND` | MERGE-CONFLICT flagged |
| 2 | `GAPS-FOUND` | Any FAIL finding UNRESOLVED or MISSING-COMMIT; or INCOMPLETE-EXECUTE; or any UNVERIFIED-CI-FAILING |
| 3 | `PENDING-MERGE-CHECK` | MERGE-STATE-UNKNOWN flagged |
| 4 | `PENDING-CI` | All findings CONFIRMED but CI not yet complete (still running/pending) |
| 5 | `READY-TO-MERGE` | All FAIL findings CONFIRMED; CI green; live `mergeable == MERGEABLE`; no INCOMPLETE-EXECUTE, UNVERIFIED-CI-FAILING, UNSYNCED-EXECUTE, BRANCH-BEHIND, or PR-IS-DRAFT |
| 6 | `GAPS-FOUND` | Anything else — name the blocking flag in the comment |

Conflicts outrank finding gaps (row 1 above row 2) because they are the coarser
failure: nothing about the PR can land until the branch merges, so that is the
headline the user needs.

### Retry Guidance by Verdict

| Verdict | Next step | Artifacts |
|---|---|---|
| `READY-TO-MERGE` | Merge | Cleaned up |
| `PENDING-CI` | Re-run `/pr-verify` after CI finishes | Preserved |
| `PENDING-MERGE-CHECK` | Re-run `/pr-verify` in a minute — GitHub is still computing | Preserved |
| `CONFLICTS-FOUND` | Delete the execute artifact, re-run `/pr-execute` (Phase 4 resolves) | Preserved |
| `GAPS-FOUND` | Fix manually, or delete the execute artifact and re-run `/pr-execute` | Preserved |

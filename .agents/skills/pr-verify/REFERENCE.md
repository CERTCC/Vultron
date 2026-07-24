# PR Verify — Reference

---

## Verify Comment Format

```markdown
## PR Verify: #<number> — <title>

**Overall verdict**: ✅ READY-TO-MERGE / ❌ GAPS-FOUND / ⏳ PENDING-CI
**CI status**: ✅ passing / ❌ failing / ⏳ pending
**Integrity check**: ✅ all <N> findings accounted for / ❌ INCOMPLETE-EXECUTE (<M> of <N> results found)

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

### Overall Verdict Rules

| Verdict | Condition |
|---|---|
| `READY-TO-MERGE` | All FAIL findings CONFIRMED; CI green; no INCOMPLETE-EXECUTE; no UNVERIFIED-CI-FAILING |
| `GAPS-FOUND` | Any FAIL finding UNRESOLVED or MISSING-COMMIT; or INCOMPLETE-EXECUTE; or any UNVERIFIED-CI-FAILING |
| `PENDING-CI` | All findings CONFIRMED but CI not yet complete (still running/pending) |

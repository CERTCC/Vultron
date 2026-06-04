# Shared Skill Scripts

Reusable shell scripts referenced by multiple skills. Each script is
self-contained and executable.

| Script | Purpose | Usage |
|---|---|---|
| `sync-check.sh` | Verify worktree is synced to `origin/main` | `bash .agents/skills/shared/sync-check.sh` |
| `claim-issue.sh` | Sync + create branch + assign + post claim comment | `bash .agents/skills/shared/claim-issue.sh <N> <prefix> <slug>` |
| `add-to-project.sh` | Add issue to Project #24 with Schedule | `bash .agents/skills/shared/add-to-project.sh <N> [Now\|Next\|Later\|Someday]` |
| `query-now-epics.sh` | List open Epics with Schedule=Now | `bash .agents/skills/shared/query-now-epics.sh` |

## Constants (CERTCC/Vultron)

| Name | Value |
|---|---|
| Repo node ID | `R_kgDOIn77fA` |
| Project #24 ID | `PVT_kwDOAjf0s84BZnre` |
| Schedule field ID | `PVTSSF_lADOAjf0s84BZnrezhUlFOM` |
| Schedule: Now | `1e84189c` |
| Schedule: Next | `9fca00b2` |
| Schedule: Later | `e2149d3e` |
| Schedule: Someday | `fcffa79d` |
| Task issue type ID | `IT_kwDOAjf0s84AcFLo` |
| Bug issue type ID | `IT_kwDOAjf0s84AcFLq` |
| Epic issue type ID | `IT_kwDOAjf0s84B_E1A` |
| Idea issue type ID | `IT_kwDOAjf0s84B_EoA` |
| Concern issue type ID | `IT_kwDOAjf0s84B_2VT` |

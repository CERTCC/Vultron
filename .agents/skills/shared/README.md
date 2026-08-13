# Shared Skill Resources

Shared scripts and reference documents referenced by multiple skills.

## Reference Documents

| File | Purpose | Loaded by |
|---|---|---|
| `completeness-doctrine.md` | Project quality standard: what "done" means, finding severity taxonomy (FAIL/IMPROVE/DEFER), scope expansion rules | `orient-agent` Step 3 — in context for every workflow |
| `pr-body-guide.md` | PR body templates and formatting rules | `build`, `bugfix`, `plan-issue` |
| `upward-reflection.md` | Mandatory end-of-session signal checklist (spec-gap, spec-ambiguity, etc.) and learning-file format | `build` Phase 8, `bugfix` Phase 3 |

## Scripts

| Script | Purpose | Usage |
|---|---|---|
| `sync-check.sh` | Verify worktree is synced to `origin/main` | `bash .agents/skills/shared/sync-check.sh` |
| `claim-issue.sh` | Sync + create branch + assign + post claim comment | `bash .agents/skills/shared/claim-issue.sh <N> <prefix> <slug>` |
| `add-to-project.sh` | Add issue to Project #24 with Schedule | `bash .agents/skills/shared/add-to-project.sh <N> [Focus\|Now\|Next\|Later\|Someday]` |
| `query-now-epics.sh` | List open Epics with Schedule=Now | `bash .agents/skills/shared/query-now-epics.sh` |
| `board-id.sh` | Resolve any board node/field/option/issue-type ID **by name** (TTL-cached) | `bash .agents/skills/shared/board-id.sh <category> [<Name>]` |
| `freshen-branch.sh` | Rebase-free freshening onto `origin/main` **before the first push** | `bash .agents/skills/shared/freshen-branch.sh` |
| `sync-with-main.sh` | Merge the base branch into an **already-pushed** PR branch; leaves conflicts for the caller | `bash .agents/skills/shared/sync-with-main.sh [<base-branch>]` |
| `merge-state.sh` | Report a PR's mergeability, polling past GitHub's transient `UNKNOWN` | `bash .agents/skills/shared/merge-state.sh [<pr-number>]` |

## freshen vs sync — pick by whether the branch is pushed

Both bring a task branch current with its base, but they are not
interchangeable:

| | `freshen-branch.sh` | `sync-with-main.sh` |
|---|---|---|
| When | Before the first push (`create-pr` Phase 2) | After a PR exists (`pr-execute` Phase 4) |
| How | Cherry-picks onto a fresh base — rewrites history | Merge commit — preserves pushed SHAs |
| Push | Normal push (branch not yet public) | Normal push (no `--force` ever needed) |
| On conflict | Aborts cleanly, exit `1` — caller opens a draft PR with `needs-rebase` | Leaves the merge in progress, exit `1` — caller resolves and commits |

Using `freshen-branch.sh` on a pushed branch would require a force-push, which
orphans reviewers' line comments and invalidates any `commit_ref` already
recorded in the PR pipeline artifacts.

## Board IDs — never hardcode them

GitHub board IDs (repo node ID, project node ID, Schedule field/option IDs,
issue-type IDs) are **server-generated and mutable** — editing a ProjectV2
single-select field's options rotates every option ID. Any value pasted into a
skill drifts stale and silently mis-schedules issues (this has bitten us
before).

**Resolve them at runtime by name** via `board-id.sh`, which fetches from the
live board and caches to `board-ids.json` with a 24h TTL (override with the
`BOARD_ID_TTL` env var in seconds; `--refresh` forces a re-fetch). No skill
should contain a raw ID.

| What you need | Command |
|---|---|
| Repo node ID | `bash .agents/skills/shared/board-id.sh repo` |
| Project #24 node ID | `bash .agents/skills/shared/board-id.sh project` |
| Schedule field ID | `bash .agents/skills/shared/board-id.sh schedule-field` |
| A Schedule option ID | `bash .agents/skills/shared/board-id.sh schedule Now` (or `Focus`/`Next`/`Later`/`Someday`/`Completed`) |
| An issue-type ID | `bash .agents/skills/shared/board-id.sh issue-type Epic` (or `Task`/`Bug`/`Feature`/`Idea`/`Concern`) |
| Whole cache as JSON | `bash .agents/skills/shared/board-id.sh --dump` |

The only stable, human-meaningful facts (the bootstrap inputs, hardcoded in
`board-id.sh` alone) are `owner=CERTCC`, `repo=Vultron`, and project number
`24`. Everything opaque is derived from those.

`board-ids.json` is a regenerable cache: it is committed so first-run/offline
use works, but if it is ever wrong, `bash .agents/skills/shared/board-id.sh
--refresh --dump` rebuilds it and every consumer picks up the new values at
once — no per-skill edits.

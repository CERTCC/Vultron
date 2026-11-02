# Shared Skill Resources

Shared scripts and reference documents referenced by multiple skills.

## Reference Documents

| File | Purpose | Loaded by |
|---|---|---|
| `completeness-doctrine.md` | Project quality standard: what "done" means, finding severity taxonomy (FAIL/IMPROVE/DEFER), scope expansion rules | `orient-agent` Step 3 — in context for every workflow |
| `issue-creation-requirements.md` | The fields every new issue needs (type, reason, one theme with its `Theme:` line, a same-theme parent Epic) and the script gate that enforces them; lookup commands and defaults | `create-issue`, `manage-github-issue`, `create-epic` |
| `pr-body-guide.md` | PR body templates and formatting rules | `build`, `bugfix`, `plan-issue` |
| `bundling.md` | Normative definition of a bundle: the two selection stages, the three fit signals and their authorities, and how one bundle becomes one PR (PAD-15) | `propose-bundle`, `build`, `bugfix`, `plan-issue` |
| `asking-the-user.md` | How to present a question or decision to the user: one at a time, problem before decision, plain language, no bare IDs, restate rather than point by number, which tool to use | `AGENTS.md` (every session), `grill-me`, `plan-issue`, `learn`, `decision-audit`, `spec-audit`, `bugfix`, `process-concerns`, `review-priorities` |
| `sizing.md` | What the `size:` labels mean, estimate vs. measurement, who applies each, and why `size:XL` is a review-coverage warning (PAD-05). Band values come from `pr-size`, never prose | `plan-issue`, `update-plan`, `build`, `bugfix` |
| `weighing-decision-records.md` | How far to trust a decision record whose body you read: settled versus challengeable, and why a stale code reference is not a challenge (ADR-0127, ADR-0043) | `deepen-context` Step 2, whose exception table names every skill that loads it |
| `pre-review-self-check.md` | The four-item check the author runs on a finished diff (affected-text sweep, failure-path pass, branch coverage, reuse check) and the reviewer runs as review prompts; results go under `Self-check:` in the PR body (PAD-07-009) | `build` Phase 5, `bugfix` Phase 4, `pr-triage` Phase 8 |
| `upward-reflection.md` | Mandatory end-of-session checklist and the routing table that sends each finding to a GitHub issue, an in-session fix, an assertion at the site, or a learning file | `build` Phase 8, `bugfix` Phase 3, `pr-execute` Phase 3 |

## Scripts

| Script | Purpose | Usage |
|---|---|---|
| `sync-check.sh` | Verify worktree is synced to `origin/main` | `bash .agents/skills/shared/sync-check.sh` |
| `claim-issue.sh` | Sync, have GitHub create the linked claim branch (the lock: a `null` `linkedBranch` means already claimed, PAD-04-001), then `announce-claim.sh` each member (an Epic member is only commented on: its assignee means an epic run). Extra members are claimed onto the one branch named for `<N>`; all numbers are validated, and checked with `epic-hold.sh`, before anything is mutated. Exit 3 = held by an epic run | `bash .agents/skills/shared/claim-issue.sh [--epic-run <EPIC>] <N> <prefix> <slug> [<OTHERS>...]` |
| `announce-claim.sh` | The one claim announcement: assign `@me`, comment, and set `Status = In Progress` for non-Epics (PAD-04-002, PAD-04-005, PAD-04-006). Called by `claim-issue.sh` and `claim-epic.sh` | `bash .agents/skills/shared/announce-claim.sh <N> <message>` |
| `epic-hold.sh` | Exit 3 if `<N>` is a Task or Feature whose nearest Epic is claimed by an epic run other than `<EPIC_RUN>` (PAD-19-002/003) | `bash .agents/skills/shared/epic-hold.sh <N> [<EPIC_RUN>]` |
| `claim-epic.sh` | Claim an Epic for an epic run (`work-epic-tasks`): refuse if already assigned, else `announce-claim.sh` (PAD-19-001, PAD-19-008) | `bash .agents/skills/shared/claim-epic.sh <EPIC>` |
| `release-epic.sh` | End an epic run: unassign the Epic and post the summary comment (PAD-19-004) | `bash .agents/skills/shared/release-epic.sh <EPIC> <summary>` |
| `query-epic-subissues.sh` | Emit an Epic's assignees and its leaf sub-issues with the eligibility fields plus `issueType` and the Project #24 `Schedule` tier. Pipe into the `bundle-fit` console script, which applies fit and owns the rules | `bash .agents/skills/shared/query-epic-subissues.sh <EPIC> \| PYTHONPATH= uv run bundle-fit` |
| `label-id.sh` | Print a label's node ID (exit 1 if it does not exist), so the issue-creating scripts pass labels inside the create mutation | `bash .agents/skills/shared/label-id.sh <OWNER/NAME> <label>` |
| `add-to-project.sh` | Add issue to Project #24 with Schedule | `bash .agents/skills/shared/add-to-project.sh <N> [Focus\|Now\|Next\|Later\|Someday]` |
| `set-board-field.sh` | Put an issue on Project #24 and set its `Schedule` or `Status` | `bash .agents/skills/shared/set-board-field.sh <N> <schedule\|status> <option>` |
| `sync-epic-schedules.sh` | Raise open descendants of scheduled Epics to their Epic's Schedule tier (raise-only, from Someday/unset/off-board; reports children above the Epic, at Later, or at a non-tier value). Dry run unless `--apply` | `bash .agents/skills/shared/sync-epic-schedules.sh [--apply] [--tiers "Focus Now Next"] [<EPIC>...]` |
| `query-now-epics.sh` | List open Epics with Schedule=Now | `bash .agents/skills/shared/query-now-epics.sh` |
| `board-id.sh` | Resolve any board node/field/option/issue-type ID **by name** (TTL-cached) | `bash .agents/skills/shared/board-id.sh <category> [<Name>]` |
| `freshen-branch.sh` | Rebase-free freshening onto `origin/main` **before the first push** | `bash .agents/skills/shared/freshen-branch.sh` |
| `sync-with-main.sh` | Merge the base branch into an **already-pushed** PR branch; leaves conflicts for the caller | `bash .agents/skills/shared/sync-with-main.sh [<base-branch>]` |
| `merge-state.sh` | Report a PR's mergeability, polling past GitHub's transient `UNKNOWN` | `bash .agents/skills/shared/merge-state.sh [<pr-number>]` |
| `spec-amendments.sh` | List requirements whose `statement:` or `priority:` the branch changed or removed (parsed-YAML compare). Exit 1 means the PR body needs `## Spec amended` | `bash .agents/skills/shared/spec-amendments.sh [<base>] [<head>]` |
| `graph-freshness.sh` | Check this worktree's graphify graph is present and fresh before relying on it; exit 1 means use grep/code search | `bash .agents/skills/shared/graph-freshness.sh [max-commits-behind]` |

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

GitHub board IDs (repo node ID, project node ID, Schedule and Status field/option IDs,
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
| Status field ID | `bash .agents/skills/shared/board-id.sh status-field` |
| A Status option ID | `bash .agents/skills/shared/board-id.sh status "In Progress"` (or `Backlog`/`Ready`/`In Review`/`Done`; case-insensitive) |
| An issue-type ID | `bash .agents/skills/shared/board-id.sh issue-type Epic` (or `Task`/`Bug`/`Feature`/`Idea`/`Concern`) |
| Whole cache as JSON | `bash .agents/skills/shared/board-id.sh --dump` |

The only stable, human-meaningful facts (the bootstrap inputs, hardcoded in
`board-id.sh` alone) are `owner=CERTCC`, `repo=Vultron`, and project number
`24`. Everything opaque is derived from those.

`board-ids.json` is a regenerable cache: it is committed so first-run/offline
use works, but if it is ever wrong, `bash .agents/skills/shared/board-id.sh
--refresh --dump` rebuilds it and every consumer picks up the new values at
once — no per-skill edits.

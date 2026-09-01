# Issue Creation Requirements

Every new issue created via `manage_github_issue.sh` **must** supply three fields.
Missing any one causes the script to exit non-zero.

## Required fields

| Field | Flag | Why |
|---|---|---|
| **Issue type** | `--issue-type-id ID` | Determines the issue's workflow lane (Task, Bug, Idea, Concern). Without it the issue has no type and is invisible to type-filtered views. |
| **Parent epic** | `--parent N` | Routes the issue into the epic forest so it appears in sprint planning and prioritisation. An orphaned issue is invisible to capacity planning. |
| **Milestone** | `--milestone N` | Anchors the issue to a delivery target. Without it the issue floats outside every milestone filter. |

## Lookup commands

```bash
# Issue type IDs (Task, Bug, Idea, Concern, Epic)
bash .agents/skills/shared/board-id.sh issue-type Task

# Open epics (pick the best-fit parent)
gh issue list --repo CERTCC/Vultron --state open --limit 200 \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Epic") | "#\(.number): \(.title)"'

# Open milestones with numbers
gh api repos/CERTCC/Vultron/milestones \
  --jq '.[] | "\(.number): \(.title)"'
```

## Determining the right values

- **Issue type**: infer from the work — implementation tasks → `Task`, regressions → `Bug`,
  exploratory captures → `Idea` or `Concern`.
- **Parent epic**: use `calve-epics` Mode 1 to find the best-fit open Epic; if none
  matches, run Mode 2 to propose a new one. Never leave an issue without a parent.
- **Milestone**: inherit from the source issue (the Idea/Concern/Bug being planned or fixed)
  when one exists; otherwise pick the milestone whose scope best matches the work.
  "Project Health" (milestone 25) is the default for tooling and process improvements.

## Exemptions

Epics are created via `create_epic.sh`, which bypasses this guard (Epics are
legitimately root-level and do not have a parent issue). No other exemptions exist.

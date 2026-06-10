# Dev Status Skill — Reference

Exact queries used by the `dev-status` skill.

## GitHub Issue Type IDs (CERTCC/Vultron)

| Type | ID |
|---|---|
| Task | `IT_kwDOAjf0s84AcFLo` |
| Bug | `IT_kwDOAjf0s84AcFLq` |
| Feature | `IT_kwDOAjf0s84AcFLs` |
| Idea | `IT_kwDOAjf0s84B_EoA` |
| Epic | `IT_kwDOAjf0s84B_E1A` |
| Concern | `IT_kwDOAjf0s84B_2VT` |

Re-query if the repo is transferred or recreated:

```bash
gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issueTypes(first:20) { nodes { id name } }
  }
}'
```

## Query: Open Issues by Type

> ⚠️ **Do NOT read `docs/reference/codebase/CONCERNS.md` to count or assess
> concerns.** That file is a raw codebase-scan artifact managed by the
> `acquire-codebase-knowledge` and `process-concerns` skills. Its entries may
> already be reflected in GitHub Concern issues, partially processed, or
> outdated. The authoritative concern count is always the number of open
> GitHub Issues of type **Concern**.

```bash
# Open Idea issues
gh issue list --repo CERTCC/Vultron \
  --limit 200 \
  --json number,title,issueType \
  --jq '[.[] | select(.issueType.name == "Idea")] | length'

# Open Bug issues
gh issue list --repo CERTCC/Vultron \
  --limit 200 \
  --json number,title,issueType \
  --jq '[.[] | select(.issueType.name == "Bug")] | length'

# Open Concern issues
gh issue list --repo CERTCC/Vultron \
  --limit 200 \
  --json number,title,issueType \
  --jq '[.[] | select(.issueType.name == "Concern")] | length'
```

For the full list (not just count), omit `| length` and add
`"\(.number): \(.title)"` projection.

## Query: Triage Count (Schedule=Someday, no Epic parent)

```bash
# Get all project items with Schedule=Someday
gh api graphql --jq '
  [ .data.node.items.nodes[]
    | select(
        .content.state == "OPEN" and
        ( .fieldValues.nodes[]
          | select(.field.name == "Schedule")
          | .name
        ) == "Someday"
      )
    | .content.number
  ] | length
' -f query='{
  node(id: "PVT_kwDOAjf0s84BZnre") {
    ... on ProjectV2 {
      items(first: 200) {
        nodes {
          content { ... on Issue { number state } }
          fieldValues(first: 10) { nodes {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name field { ... on ProjectV2SingleSelectField { name } }
            }
          }}
        }
      }
    }
  }
}'
```

## Query: Ready-to-Build Count

1. Find the first open Epic with `Schedule=Now` on Project #24 (lowest board
   position = highest priority).
2. Query its open leaf sub-issues with no open blockers:

```bash
# Step 1: get Now-Epic numbers in board order
gh api graphql --jq '
  [ .data.node.items.nodes[]
    | select(
        .content.state == "OPEN" and
        .content.issueType.name == "Epic" and
        ( .fieldValues.nodes[]
          | select(.field.name == "Schedule")
          | .name
        ) == "Now"
      )
    | .content.number
  ][]
' -f query='{
  node(id: "PVT_kwDOAjf0s84BZnre") {
    ... on ProjectV2 {
      items(first: 100) {
        nodes {
          content {
            ... on Issue { number state issueType { name } }
          }
          fieldValues(first: 10) { nodes {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name field { ... on ProjectV2SingleSelectField { name } }
            }
          }}
        }
      }
    }
  }
}'

# Step 2: for each Epic, query sub-issues; for each sub-issue N, check leaf + blockers
gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: <EPIC_N>) {
      subIssues(first: 50) {
        nodes {
          number state
          blockedBy(first: 10) { nodes { number state } }
          subIssues(first: 1) { totalCount }
          labels(first: 10) { nodes { name } }
        }
      }
    }
  }
}'
# An issue is "ready" if:
#   - state: OPEN, no stale-claim label, no assignee
#   - all blockedBy nodes have state: CLOSED (or blockedBy is empty)
#   - subIssues.totalCount == 0 (leaf issue, not a parent task)
```

## Query: Open Pull Requests

```bash
gh pr list --repo CERTCC/Vultron \
  --state open \
  --json number,title \
  --jq 'length'
```

For the full list with review status and CI state:

```bash
gh pr list --repo CERTCC/Vultron \
  --state open \
  --json number,title,reviewDecision,statusCheckRollup \
  --jq '.[] | "\(.number): \(.title) [review=\(.reviewDecision // "NONE")] [ci=\(.statusCheckRollup // [] | map(.conclusion) | unique | join(","))]"'
```

Use `pr-comprehensive-fix` when any PR has failing checks or pending review
comments. When all PRs are green and approved, the count is still shown but
the row skill column should list `pr-comprehensive-fix` (it handles review
preparation too).

## Query: BUILD_LEARNINGS Entry Count

```bash
grep -c '^### ' plan/BUILD_LEARNINGS.md 2>/dev/null || echo 0
```

Returns the number of dated entry headers. Zero means the file contains only
the preamble — no actionable entries.

## Report Template

```text
## Vultron Status — {date}

| Queue                 | Count | Skill                |
|-----------------------|-------|----------------------|
| BUILD_LEARNINGS       |  {n}  | learn                |
| Ideas (open)          |  {n}  | plan-issue           |
| Bugs (open)           |  {n}  | bugfix               |
| Concerns (open)       |  {n}  | process-concerns     |
| Open PRs              |  {n}  | pr-comprehensive-fix |
| Triage (Someday)      |  {n}  | review-priorities    |
| Ready to build        |  {n}  | build                |

Now: {epic_titles}

**Next up**: {skill} — {reason}
```

`{epic_titles}` lists the titles of all open `Schedule=Now` Epics on Project #24.
When all counts are zero and BUILD_LEARNINGS is empty, replace the "Next up"
line with:

```text
**All queues clear.** Nothing actionable at this time.
```

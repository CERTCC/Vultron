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

## Query: Unscheduled Issues

```bash
gh issue list --repo CERTCC/Vultron \
  --limit 200 \
  --label "group:unscheduled" \
  --json number,title \
  --jq 'length'
```

## Query: Ready-to-Build Count

1. Read `plan/PRIORITIES.md` to identify the top-priority group label
   (e.g., `group:architecture-hardening`).
2. Query open leaf issues in that group with no open blockers:

```bash
# Step 1: list open issues with the top-priority group label
gh issue list --repo CERTCC/Vultron \
  --limit 200 \
  --label "<top-priority-group-label>" \
  --json number,title \
  --jq '.[].number'

# Step 2: for each issue N, check blockers via GraphQL
gh api graphql -f query='{
  repository(owner:"CERTCC", name:"Vultron") {
    issue(number: N) {
      blockedBy(first: 50) { nodes { number state } }
      subIssues(first: 1) { totalCount }
    }
  }
}'
# An issue is "ready" if:
#   - all blockedBy nodes have state: CLOSED (or blockedBy is empty)
#   - subIssues.totalCount == 0 (leaf issue, not a parent task)
```

## Query: BUILD_LEARNINGS Entry Count

```bash
grep -c '^### ' plan/BUILD_LEARNINGS.md 2>/dev/null || echo 0
```

Returns the number of dated entry headers. Zero means the file contains only
the preamble — no actionable entries.

## Query: PRIORITIES.md Staleness

```bash
git log --format="%cr" --max-count=1 -- plan/PRIORITIES.md
```

Returns a human-readable relative time (e.g., `3 days ago`, `2 weeks ago`).
Warn in the report if the value exceeds 14 days.

To get the age in days for threshold comparisons:

```bash
git log --format="%ct" --max-count=1 -- plan/PRIORITIES.md \
  | xargs -I{} python3 -c "
import time; age=(time.time()-{})/86400; print(f'{age:.0f}')
"
```

## Report Template

```text
## Vultron Status — {date}

| Queue                 | Count | Skill             |
|-----------------------|-------|-------------------|
| BUILD_LEARNINGS       |  {n}  | learn             |
| Ideas (open)          |  {n}  | ingest-idea       |
| Bugs (open)           |  {n}  | bugfix            |
| Concerns (open)       |  {n}  | process-concerns  |
| Unscheduled issues    |  {n}  | review-priorities |
| Ready to build        |  {n}  | build             |

PRIORITIES.md last updated: {relative_time}{staleness_warning}

**Next up**: {skill} — {reason}
```

`{staleness_warning}` is omitted when age ≤ 14 days; otherwise append
`⚠️ consider running review-priorities`.

When all counts are zero and BUILD_LEARNINGS is empty, replace the "Next up"
line with:

```text
**All queues clear.** Nothing actionable at this time.
```

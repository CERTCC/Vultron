---
name: new-concern
description: >
  Create a single GitHub Concern-type issue from a freeform description.
  Runs a grill-me interview to flesh out category, severity, evidence, impact,
  and suggested action, then creates the issue using the concern.md template
  format with the group:unscheduled and concern labels. Use when a developer
  spots a concern that isn't in the current CONCERNS.md scan, or wants to
  capture a concern immediately without running process-concerns.
---

# Skill: New Concern

Capture a single technical concern as a properly formed GitHub `type:Concern`
issue. Interview the user with `grill-me` to flesh out every field, then
create the issue.

## Constants

```text
REPO           = CERTCC/Vultron
REPO_NODE_ID   = R_kgDOIn77fA
CONCERN_TYPE   = IT_kwDOAjf0s84B_2VT
```

---

## Workflow

### Phase 0 — Describe the Concern

Ask the user to describe the concern in freeform (via `ask_user` with
`allow_freeform: true`):

> Describe the concern you want to capture. What's the problem, risk, or
> fragile area?

Store the raw description as the starting point for the interview.

### Phase 1 — Situation Awareness

Before writing anything, list all **open Concern-type issues** to check for a
near-duplicate:

```bash
gh issue list \
  --repo CERTCC/Vultron \
  --state open \
  --json number,title,issueType \
  --jq '.[] | select(.issueType.name == "Concern") | "#\(.number): \(.title)"'
```

If an existing issue appears to cover the same subject (by title similarity),
surface it to the user via `ask_user`:

> Issue #N — "<existing title>" — already tracks a similar concern. Should I
> update that issue instead of creating a new one?

Choices:

1. **Update the existing issue (Recommended)**
2. **Create a new issue anyway**

If the user chooses to update, skip to **Phase 3 (Update)** with the existing
issue number.

### Phase 2 — Grill-Me Interview

Invoke the `grill-me` skill. Walk through each field of the concern template
one at a time using `ask_user`, providing a recommendation based on the
user's initial description and any codebase exploration:

1. **Category** — Which best fits: Top risk, Technical debt, Security,
   Performance / scaling, Fragile / high-churn area, or Other?
2. **Severity** — high, medium, or low?
3. **Evidence** — Which files, modules, or lines make this visible?
   (Explore the codebase to suggest candidates before asking.)
4. **Impact if Ignored** — What breaks, degrades, or becomes harder?
5. **Suggested Action** — Recommended fix, mitigation, or next step?
6. **Title** — Synthesize a short, descriptive title from the answers.

Answer questions from codebase exploration where possible; only ask the user
when the answer is not determinable from code.

### Phase 3 — Build Issue Body

Construct the issue body using the concern template format:

```markdown
## Summary

<one or two sentences from the freeform description, refined during interview>

## Category

- [x] <checked item from interview>
- [ ] Top risk
- [ ] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [ ] Other

## Severity

<high / medium / low from interview>

## Evidence

<file paths from interview, one per bullet>

- `path/to/file.py`

## Impact if Ignored

<from interview>

## Suggested Action

<from interview>
```

### Phase 4 — Create or Update Issue

#### Creating a new issue

```bash
TITLE_JSON=$(printf '%s' "${TITLE}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
BODY_JSON=$(printf '%s' "${BODY}" \
  | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")

# Ensure labels exist before applying them
gh label create "group:unscheduled" \
  --repo CERTCC/Vultron \
  --description "Not yet scheduled in PRIORITIES.md" \
  --color "#e4e669" 2>/dev/null || true

gh label create "concern" \
  --repo CERTCC/Vultron \
  --description "Technical risk, debt, or fragile area" \
  --color "#d93f0b" 2>/dev/null || true

ISSUE_NUMBER=$(gh api graphql -f query="
mutation {
  createIssue(input: {
    repositoryId: \"${REPO_NODE_ID}\"
    title: ${TITLE_JSON}
    body: ${BODY_JSON}
    issueTypeId: \"${CONCERN_TYPE}\"
  }) {
    issue { number url }
  }
}" --jq '.data.createIssue.issue.number')

gh issue edit "${ISSUE_NUMBER}" \
  --repo CERTCC/Vultron \
  --add-label "group:unscheduled,concern"

echo "Created concern issue #${ISSUE_NUMBER}"
```

#### Updating an existing issue (if user chose update in Phase 1)

Rebuild the body with the latest interview data and update:

```bash
gh issue edit "${ISSUE_NUMBER}" \
  --repo CERTCC/Vultron \
  --body "$(cat body.md)"

gh issue comment "${ISSUE_NUMBER}" \
  --repo CERTCC/Vultron \
  --body "♻️ Updated with new detail — $(date +%Y-%m-%d)."
```

### Phase 5 — Confirm

Print a one-line confirmation:

```text
✅ Concern issue #<N> — "<title>" — <created|updated>.
   <URL>
```

---

## Constraints

- Do **not** write to `specs/`, `notes/`, `AGENTS.md`, or open a PR.
- Do **not** assign a `size:` label or parent issue.
- Always check for existing open Concern issues before creating a new one.
- Use `ask_user` for all user-facing questions; never ask in plain text.
- Answer questions from codebase exploration where possible rather than
  asking the user.

## Checklist

- [ ] User described concern in freeform
- [ ] Open Concern issues loaded; near-duplicate check performed
- [ ] If near-duplicate found, user chose create-new or update-existing
- [ ] All template fields resolved via grill-me interview
- [ ] Issue body built from concern template format
- [ ] Issue created (with `group:unscheduled` + `concern` labels) or
      updated (with refresh comment)
- [ ] Confirmation URL printed

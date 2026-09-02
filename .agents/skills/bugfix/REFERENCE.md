# Bugfix Skill — Reference

Background patterns, templates, and decision guidance for the bugfix skill.
Load when the main SKILL.md refers you here for a specific topic.

---

## Sibling Scan Pattern

After establishing the root cause, search for the same structural pattern
in peer locations before locking scope. The fix-one-miss-the-siblings failure
mode is a backlog inflation mechanism: the same bug recurs in sibling locations
and each instance requires a separate investigation cycle, PR, and review.

**What counts as a sibling location?**

- Files in the same directory that implement the same pattern (e.g., all
  `*_demo.py` scenario files, all `*_tree.py` BT files in one BT subdirectory)
- Handlers that implement the same protocol step for different message types
- Actors or participant roles that mirror each other structurally (e.g.,
  Finder-Vendor vs. Coordinator-Vendor flows)

**How to scan:**

```bash
# Find files sharing the same naming pattern
find vultron/ -name "<pattern>" -type f

# Grep for the same structural element
grep -rn "<root-cause signature>" vultron/ test/

# Graph query for peer nodes
graphify query "<root-cause concept>"
```

**What to do with hits:**

- If a sibling hit is small and clearly within scope: fix it in the same PR.
- If it requires its own investigation: file a new Bug issue (see Escalation).
- Either way: document all hits in the Phase 3 briefing and in the PR description.

---

## Escalation Pattern

When analysis surfaces additional related issues beyond the confirmed scope,
file each as a new Bug-type GitHub issue. Do not pursue them in the current run.

```bash
BUG_TYPE_ID=$(bash .agents/skills/shared/board-id.sh issue-type Bug)
# Inherit parent from the issue being fixed so the escalated bug is
# visible in the epic tree (no:parent-issue orphans break prioritisation).
PARENT_ARG="--parent ${ISSUE_NUMBER}"
.agents/skills/manage-github-issue/manage_github_issue.sh \
  --title "<short bug title>" \
  --body "$(cat <<'EOF'
## Symptoms

<one sentence describing observed vs. expected behavior>

## Root cause (hypothesis)

<what was observed during analysis of #N>

## Components involved

- `path/to/module.py`

## Source

Discovered during analysis of #N.
EOF
)" \
  --issue-type-id "${BUG_TYPE_ID}" \
  ${PARENT_ARG}
```

Reference newly filed issues in the PR description:

```text
Fixes #<N>.
Closes #<NNN> (sibling instance discovered during analysis and fixed here).
```

---

## Bug Archive Format

```text
TYPE    = implementation
SOURCE  = ISSUE-<N>
TITLE   = <short bug title>
BODY    = issue #<N> — <title>

          Symptoms: <one sentence describing observed vs expected behaviour>

          Root cause: <concise technical explanation>

          Fix: <what was changed and why>

          Components changed:
          - path/to/file.py
          - test/path/to/test_file.py

          PR: <PR_URL>
```

---

## Decision Log

| Question | Decision | Rationale |
|----------|----------|-----------|
| Should the agent investigate before or after asking the user? | Investigate first | The reporter is not omniscient; treating them as an oracle wastes interaction rounds and produces worse root-cause analysis than independent investigation |
| When should the sibling scan run? | Phase 2d, before presenting findings | The agent has just articulated the root cause and can search for the pattern most effectively at this point; findings feed directly into the Phase 3 briefing |
| Should Phase 2 questions be removed entirely? | Yes | One `ask_user` after investigation replaces four before; the user gets better information and fewer interruptions |
| When a deeper issue surfaces during investigation, what happens? | File new Bug issues; confirm narrowed scope at Phase 3 | Keeps the current run focused while ensuring discovered issues are not lost |
| What if the bug is already fixed on main? | Close with reference comment; do not proceed | Prior PRs may have fixed the bug without a `Closes #N` footer; always check before writing code |

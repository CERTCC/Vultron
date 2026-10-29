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
```

**What to do with hits:**

- If a sibling hit is small and clearly within scope: fix it in the same PR.
- If it requires its own investigation: file a new Bug issue (see Escalation).
- Either way: document all hits in the Phase 3 briefing and in the PR description.

---

## Escalation Pattern

When analysis surfaces additional related issues beyond the confirmed scope,
file each as a new Bug-type GitHub issue. Do not pursue them in the current run.
This is for genuinely separate defects. A sibling of *this* bug that the fix
leaves undone is not separate: fix it here, or hold the PR (unattended DEFER is
unavailable, `completeness-doctrine.md` Gate 1).

Invoke `create-issue` for each, with type `Bug`, reason
`opened-as separate-defect`, and these drafted fields:

```text
## Symptoms

<one sentence describing observed vs. expected behavior>

## Root cause (hypothesis)

<what was observed during analysis of #N>

## Components involved

- `path/to/module.py`

## Source

Discovered during analysis of #N.
```

Do not copy the parent Epic of the bug being fixed. `create-issue` judges the
new bug's theme from its own content and routes it to a same-theme Epic: a
defect found while fixing one bug often belongs to a different outcome.

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
| Should Phase 2 questions be removed entirely? | Yes | One plain-text briefing after investigation replaces four questions before; the user gets better information and fewer interruptions |
| How is the Phase 3 briefing presented? | As a plain-text message ending in one question, not `ask_user` | The user often redirects here and needs room to write; the `ask_user` notes field doesn't wrap, and text printed just before a question box can be hidden by it |
| When a deeper issue surfaces during investigation, what happens? | File new Bug issues; confirm narrowed scope at Phase 3 | Keeps the current run focused while ensuring discovered issues are not lost |
| What if the bug is already fixed on main? | Close with reference comment; do not proceed | Prior PRs may have fixed the bug without a `Closes #N` footer; always check before writing code |

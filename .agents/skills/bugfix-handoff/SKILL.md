---
name: bugfix-handoff
description: >
  Captures all work-in-progress context when a bugfix session is interrupted
  and posts a structured handoff comment to the GitHub issue, then pushes the
  branch. Use when a bugfix agent must stop before fully resolving the bug —
  session ending, agent looping, developer leaving, or any other interruption
  that requires handing off to a future worker. Immediately halts all
  resolution work and shifts to documentation.
---

# Skill: Bugfix Handoff

**You are being interrupted. Stop all resolution work immediately.**

Your only job now is to document everything so the next agent can
pick up where you left off. Do not attempt any further fixes, tests,
or investigations after this skill is invoked.

## Phase 1 — Halt and Assess

1. Stop any ongoing implementation, testing, or investigation.
2. Note which bugfix phase you were in and what you were doing at the
   moment of interruption.
3. Run `git status` to see what is uncommitted.

## Phase 2 — Commit WIP

If there are any uncommitted changes, stage and commit them with a
clear WIP marker:

```bash
git add -A
git commit -m "wip: interrupted handoff — <short description>

[WIP] This commit captures in-progress work at session interrupt time.
The bug is NOT fixed. See the issue comment for handoff notes.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

If the working tree is clean, skip this step.

## Phase 3 — Draft Handoff Comment

Using the template in [REFERENCE.md](REFERENCE.md), draft a comment
that documents everything a cold-start agent would need. Write the
comment to a temp file:

```bash
cat > /tmp/bugfix-handoff-comment.md << 'EOF'
<your filled-in comment here>
EOF
```

See REFERENCE.md for the full template and field guidance. Include
partial, uncertain, or speculative information — a wrong hypothesis
on record is more useful than silence.

## Phase 4 — Post to GitHub and Push

```bash
# Post the handoff comment
gh issue comment <N> --repo CERTCC/Vultron \
  --body-file /tmp/bugfix-handoff-comment.md

# Push the branch (including the WIP commit if any)
git push -u origin <branch-name>
```

Then confirm to the user:

- The branch that was pushed and the WIP commit SHA (if any)
- The URL of the handoff comment
- A 2–3 sentence summary of where things stand

## Constraints

- Do **NOT** attempt further bug resolution after this skill is invoked.
- Do **NOT** open a PR — the fix is incomplete.
- Do **NOT** run linters or tests unless their output was already
  in-flight and you need to capture it for the handoff notes.
- Do **NOT** wait for perfect information — document what you have now.

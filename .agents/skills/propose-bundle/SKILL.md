---
name: propose-bundle
description: >
  Given an Epic number, queries its open leaf issues, applies eligibility and
  fit (workflow, Schedule tier, size budget), and proposes a bundle the user
  can confirm or trim. Use before running /build, /bugfix, or /plan-issue when
  you want to review and trim the candidate set first.
---

# Skill: Propose Bundle

Takes an Epic number, finds its buildable leaf issues, and presents a proposed
bundle the user can confirm or trim before passing to an executing skill.

A bundle is an ordered set of 1–5 issues worked in **one PR that closes every
member**. `.agents/skills/shared/bundling.md` is the normative definition of
what a bundle is, how fit is decided, and how one is executed — read it before
proposing anything. This skill makes no changes; it is read-only.

## Usage

```text
/propose-bundle <EPIC_NUMBER> [build|bugfix|plan-issue]
```

The optional second argument forces the target workflow. Omitted, the
highest-priority candidate picks it.

## Workflow

1. Query the Epic's leaf sub-issues and apply both selection stages:

   ```bash
   bash .agents/skills/shared/query-epic-subissues.sh <EPIC_NUMBER> \
     | PYTHONPATH= uv run bundle-fit [--workflow <WORKFLOW>]
   ```

   The tool owns the mechanical rules — eligibility, then fit over
   `issueType`, the Project #24 `Schedule` tier, and the `size:` weight budget.
   Do not re-derive them by hand and do not select from the raw query output;
   see `bundling.md` for the rule table and its authorities.

2. If the tool reports no bundle, report why, using its own two lists — the
   candidates *held back by fit* and those *not workable yet* are different
   findings and a human acts on them differently:

   > Epic #N has no bundle. Held back by fit: (list). Not workable yet: (list).

   A bundle empty because every candidate was `Someday` is a scheduling
   answer, not a dead end — say so.

3. Apply the grain check yourself. `bundle-fit` emits coherence *hints*, never
   a verdict. State the single design idea the proposed members share **in one
   sentence**. If a member needs a different sentence, drop it and say why. If
   no sentence covers two members, note that the Epic may need `calve-epics`.

4. Present the result: the tool's report, your one-sentence design idea, any
   member you dropped, and the command to run:

   ```text
   Proposed /<workflow> bundle for Epic #<N> — <Epic title>:
     1. #<N1> [<type> <size> Schedule=<tier> weight=<w>] <title>
     2. #<N2> ...

   Shared design idea: <one sentence>.
   Size: <weight>/<budget>.

   Run: /<workflow> <N1> <N2> ...
   ```

5. Report what was held back, preserving the tool's two stages and its
   per-candidate reasons — never collapse "would exceed the size budget" or
   "targets a different skill" into an eligibility reason.

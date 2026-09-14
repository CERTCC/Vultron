---
name: propose-bundle
description: >
  Given an Epic number, queries its unblocked open leaf issues and proposes
  a bundle of up to 5 for the user to pass to the build skill. Use before
  running /build when you want to review and trim the candidate set first.
---

# Skill: Propose Bundle

Takes an Epic number, finds its buildable leaf issues, and presents a
proposed bundle the user can confirm or trim before passing to `/build`.

## Usage

```text
/propose-bundle <EPIC_NUMBER>
```

## Workflow

1. Query the Epic's leaf sub-issues:

   ```bash
   bash .agents/skills/shared/query-epic-subissues.sh <EPIC_NUMBER>
   ```

2. Filter candidates. A valid candidate must:
   - `state == OPEN`
   - no assignees
   - no `stale-claim` label
   - all `blockedBy` entries have `state == CLOSED` (or none)
   - `subIssues.totalCount == 0` (leaf, not a nested Epic)

3. If no candidates remain, report:
   > Epic #N has no buildable leaf issues. Blocked or assigned issues:
   > (list them with reason)

4. Select up to **5** candidates in priority order (GitHub ordering from
   the query reflects project priority). Present them as a numbered list:

   ```text
   Proposed bundle for Epic #<N> — <Epic title>:
     1. #<N1> <title>
     2. #<N2> <title>
     ...

   Run: /build <N1> <N2> ...
   ```

   If there are more than 5 candidates, note how many were left out:
   > (N more candidates available for the next bundle)

5. Also report any issues excluded from the top 5 and why:
   - **blocked** — list open blockers
   - **assigned** — already claimed
   - **stale-claim** — has stale-claim label
   - **has children** — not a leaf issue

That's it. This skill makes no changes — it is read-only.

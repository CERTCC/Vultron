# Create PR — Reference

## Conflict PR template

Use when Phase 2 rebase aborts with unresolvable conflicts. Push the un-rebased
branch as-is, then open a draft PR with this body template:

```bash
gh pr create --repo CERTCC/Vultron \
  --head "$(git branch --show-current)" \
  --base main \
  --title "<title> [NEEDS REBASE]" \
  --body "<!-- needs-rebase -->
> ⚠️ **This PR requires manual conflict resolution before it can be merged.**
>
> The \`create-pr\` skill attempted an automatic rebase on \`origin/main\`
> but encountered conflicts it could not resolve:
>
> **Conflicting files:**
> <list each conflicting file>
>
> **Nature of each conflict:**
> <one line per file: what both sides changed>
>
> **To resolve:**
> \`\`\`bash
> git fetch origin main
> git rebase origin/main
> # resolve conflicts in the files listed above
> git rebase --continue
> git push --force-with-lease
> \`\`\`
> Then convert this draft PR to ready for review.

<original PR body below>

<body>" \
  --draft \
  --label "needs-rebase"
```

Tell the user the draft PR URL and what needs resolving. Return the draft PR URL.

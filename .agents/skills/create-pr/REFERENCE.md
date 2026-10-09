# Create PR — Reference

## Conflict PR template

Use when the Phase 2 freshen (cherry-pick onto `origin/main`) aborts with
unresolvable conflicts. After Phase 3 passes, push the un-freshened branch
as-is, then open a draft PR with this body template:

```bash
gh pr create --repo CERTCC/Vultron \
  --head "$(git branch --show-current)" \
  --base main \
  --title "<title> [NEEDS REBASE]" \
  --body "<!-- needs-rebase -->
> ⚠️ **This PR requires manual conflict resolution before it can be merged.**
>
> The \`create-pr\` skill tried to freshen this branch onto \`origin/main\`
> but encountered conflicts it could not resolve:
>
> **Conflicting files:**
> <list each conflicting file>
>
> **Nature of each conflict:**
> <one line per file: what both sides changed>
>
> **To resolve** (merge, do not rebase — this branch is now published, PAD-11-001):
> \`\`\`bash
> bash .agents/skills/shared/sync-with-main.sh main
> # resolve conflicts in the files listed above, then:
> git add <resolved files> && git commit --no-edit
> git push
> \`\`\`
> Then convert this draft PR to ready for review.

<original PR body below>

<body>" \
  --draft \
  --label "needs-rebase"
```

Tell the user the draft PR URL and what needs resolving. Return the draft PR URL.

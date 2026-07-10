# Plan Issue — Idea path

## Grill-Me Interview (additional questions beyond shared base)

After resolving the shared base questions (scope, AC clusters, ADR
determination), also cover:

1. **Spec scope** — What requirements should be captured in `specs/`?
2. **Design decisions** — What alternatives were considered? Which is recommended?
3. **Notes scope** — What implementation guidance should be documented in `notes/`?

## Docs Output

- `specs/<topic>.yaml` — Add or amend requirements (optional)
- `notes/<topic>.md` — Add design decisions or implementation guidance (optional)
- ADR in `docs/adr/` if ADR determination recommended one

## Archive and Close

After implementation issues are created, archive and close the source Idea issue.

**History entry:**

```text
TYPE    = idea
TITLE   = <short idea title>
SOURCE  = IDEA-<ISSUE_NUMBER>
BODY    = Full original idea text
          + "**Processed**: YYYY-MM-DD — implementation tracked in #<IMPL_NUMBER>."
          + "Docs PR: <PR_URL>." (if docs PR was opened)
          + "Spec: `specs/${SPEC_FILE}`." (if spec was written)
          + "Notes: `notes/${NOTES_FILE}`." (if notes were written)
```

Post resolution comment and close:

```bash
gh issue comment "${ISSUE_NUMBER}" --repo CERTCC/Vultron \
  --body "✅ Planned.

$([ -n "${PR_URL}" ] && echo "- Docs PR: ${PR_URL}")
$(for n in "${IMPL_NUMBERS[@]}"; do echo "- Implementation issue: #${n}"; done)
$([ -n "${SPEC_FILE}" ] && echo "Spec: \`specs/${SPEC_FILE}\`.")
$([ -n "${NOTES_FILE}" ] && echo "Notes: \`notes/${NOTES_FILE}\`.")"

# Only close directly when no docs PR was opened.
# When a PR exists, Closes #N in the PR body closes the issue on merge.
if [ -z "${PR_URL}" ]; then
  gh issue close "${ISSUE_NUMBER}" --repo CERTCC/Vultron
fi
```

**History source**: `IDEA-<N>`
**History type**: `idea`

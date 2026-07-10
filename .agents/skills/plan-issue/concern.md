# Plan Issue — Concern path

## Grill-Me Interview (additional questions beyond shared base)

After resolving the shared base questions (scope, AC clusters, ADR
determination), also cover:

1. **Root cause** — What is actually broken, risky, or missing?
2. **Impact** — What fails or degrades if left unaddressed?
3. **Options** — 2–3 ways to address this concern.
4. **Recommended approach** — Which option and why.
5. **Spec/notes gaps** — Does this concern reveal missing requirements or
   design decisions? Which file(s) should be added or changed?
6. **AGENTS.md gap** — Is there a recurring implementation pitfall to capture?

## Docs Output

- `specs/<topic>.yaml` — Add or amend requirements (optional)
- `notes/<topic>.md` — Add design decisions or implementation guidance (optional)
- `AGENTS.md` — Append pitfall entry to **Common Pitfalls** section if a
  recurring agent gap was identified (optional)
- ADR in `docs/adr/` if ADR determination recommended one

## Archive and Close

After implementation issues are created, archive and close the source Concern issue.

**History entry:**

```text
TYPE    = learning
TITLE   = <short concern title>
SOURCE  = CONCERN-<ISSUE_NUMBER>
BODY    = Full original concern body
          + "**Resolved**: YYYY-MM-DD — implementation tracked in #<N>
            [, #<M> ...]."
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
if [ -z "${PR_URL}" ]; then
  gh issue close "${ISSUE_NUMBER}" --repo CERTCC/Vultron
fi
```

**History source**: `CONCERN-<N>`
**History type**: `learning`

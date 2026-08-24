# Plan Issue — Idea path

## Grill-Me Interview

**Opening brief** — Before asking anything, synthesize what Phase 3
research reveals about this idea. Present:

- What the issue says
- What the current codebase and specs show about the landscape this idea
  lands in — existing patterns, adjacent work, open questions
- Your read on what the idea is trying to achieve
- 2–3 plausible directions for implementing or scoping it

**Conversation** — Walk through the idea bottom-up. Ask clarifying
questions as understanding builds. The following topics should emerge
naturally from the discussion — do not ask them as sequential structured
questions:

- What requirements should be captured in `specs/`
- What alternatives were considered and which is recommended
- What implementation guidance belongs in `notes/`
- Scope, acceptance criteria, and ADR applicability

Signal the transition with "I think we're almost there — here's what I
have so far. Got more?" rather than declaring done unilaterally.

**Confirm conclusions** — After the conversation closes, propose the full
plan: what to implement, which docs to update, whether an ADR is warranted.
These are proposals to confirm, not new questions.

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

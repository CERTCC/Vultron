# Plan Issue — Concern path

## Grill-Me Interview

**Opening brief** — Before asking anything, synthesize what Phase 3
research reveals about this concern. Present:

- What the issue says
- Whether the concern still applies as written, has narrowed/shifted, or
  appears to have already been addressed by subsequent work
- Your read on what is actually broken, risky, or missing right now
- 2–3 plausible directions for addressing (or recharacterizing) it

**"Nothing there" path** — If the concern appears stale or already
resolved, say so explicitly rather than running the full ceremony: "I'm
not finding an actionable problem here because [reason]. However, I
noticed [X] nearby that could be recharacterized as [narrower/different
concern]." Offer: (a) close as resolved, (b) recharacterize and continue,
(c) override and proceed anyway. Confirm before abandoning work.

**Conversation** — Walk through the concern bottom-up. Ask clarifying
questions as understanding builds. The following topics should emerge
naturally from the discussion — do not ask them as sequential structured
questions:

- The actual root cause and what is broken, risky, or missing
- Impact if left unaddressed
- Options to address it and which is recommended
- Whether this reveals missing specs, notes, or design decisions
- Whether a recurring agent pitfall belongs in `AGENTS.md`
- Scope, acceptance criteria, and ADR applicability

Signal the transition with "I think we're almost there — here's what I
have so far. Got more?" rather than declaring done unilaterally.

**Confirm conclusions** — After the conversation closes, propose the full
plan: what to implement, which docs to update, whether an ADR is warranted.
These are proposals to confirm, not new questions.

## Docs Output

- `specs/<topic>.yaml` — Add or amend requirements (optional)
- `notes/<topic>.md` — Add design decisions or implementation guidance (optional)
- `AGENTS.md` — If a recurring agent gap was identified (optional), route it per
  `notes/agents-md-structure.md`: write-up in the nearest `notes/` or
  per-directory `AGENTS.md`, and at most an extended cell in root's **Common
  Pitfalls** index. Root is at its 400-line budget — trim as you add; appending
  fails `test/metadata/test_agents_md_size_ratchet.py`.
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

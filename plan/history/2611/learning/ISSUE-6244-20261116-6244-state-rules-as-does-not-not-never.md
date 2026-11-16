---
title: >-
  A rule written with "never" commits the project's future design; write "does
  not", which states what holds now
type: learning
timestamp: "2026-11-16T18:10:00Z"
source: ISSUE-6244
signal: theme-candidate
---

**Trigger.** You are writing a prohibition into an ADR, a spec statement, a note
or an issue body.

**Claim.** "A receiver never fetches it" reads as a commitment that no later
decision may revisit; "a receiver does not fetch it" states the current rule and
leaves the next decision free. The maintainer prefers the present-tense form unless
the prohibition is meant to be permanent.

**Evidence.** Planning #6244 (2026-11-16): choosing the option for telling the
stub Invite from the full-case Invite, the maintainer added "be careful with the
word 'never', favor 'does not'".

**How to apply.** Default to "does not" / "is not" in decision records, spec
statements, notes and issue bodies; keep "never" for a permanent prohibition the
maintainer has decided. Now in `.agents/skills/shared/notes-writing-guide.md` and
the ADR template's authoring comment. Spec statements use RFC 2119 `MUST NOT`,
which this does not change.

**What would confirm it.** The maintainer asks for a "never" to be softened in a
later review.

**Already closed**: 2026-11-16 — already in .agents/skills/shared/asking-the-user.md § 8 / notes-writing-guide.md and the ADR template.
Docs PR: https://github.com/CERTCC/Vultron/pull/6528.

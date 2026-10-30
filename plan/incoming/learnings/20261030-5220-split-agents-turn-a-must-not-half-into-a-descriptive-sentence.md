---
title: >-
  Agents splitting compound requirements turn a MUST NOT half into a plain
  "It never ..." sentence, which passes the keyword count but drops the duty
type: learning
timestamp: '2026-10-30T15:00:00+00:00'
source: ISSUE-5220
signal: theme-candidate
---

## Trigger

You are reviewing, or writing, the split of a compound requirement whose old
text paired a MUST with a MUST NOT ("MUST open under the canonical URI, and MUST
NOT use a short ID"). The new statement has one keyword, `spec-lint
--list-compound` is clean, and a second sentence reads as a fact: "It never
opens one under a short ID."

## Claim

When the one-keyword rule (MS-03-001, MS-03-007) is the only thing checked, a
split tends to keep the main MUST and turn the other half into description, not
into its own ID. The keyword guard cannot see the lost duty, and the meaning
table hides it, because the words are still there.

## Evidence

In #5220 (PR #5539), five parallel split agents produced about a dozen
statements like this (ARCH-13-003, ARCH-20-009, ARCH-25-028, HP-08-008,
BTND-10-004 and others). A scan for keyword-less sentences containing
*never*, *not* or *only* found them, and each was folded back into the MUST
sentence as "MUST X, never Y".

The same review missed the positive form. A later review of the PR found
required duties written as plain facts: "It checks this atomically with the
write" (DL-02-003), "The docstring also names the category ..." (BT-16-007),
"It refuses ... in the same way" (TRIG-10-005), and qualifiers such as
placement or order that had sat inside the MUST clause (HP-01-012, HP-08-006).
The negative-word scan could not see them.

## What would confirm it

A second slice of #5228 (#5217–#5224) showing the same pattern, with the agents
told nothing about it.

## How to apply

After any split sweep, list every sentence of each touched statement that has no
RFC 2119 keyword. Compare each with the old text. A sentence that held a duty
inside the old MUST or SHOULD clause has lost that duty. The duty can be a
prohibition (*never*, *not*, *no*, *only*). It can also be a positive half that
uses a duty verb (*goes*, *takes*, *names*, *runs*, *persists*, *checks*,
*refuses*, *fires*), or a qualifier of the main duty (when, where, how, in
what order). Fold each one back into the keyword sentence, or give it its own ID.
Keep a keyword-less sentence only when it defines a term, gives an example, or
restates another requirement it cites. If confirmed, the check could become a
`spec-lint --changed-since` warning.

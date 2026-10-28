---
source: CONCERN-5270
timestamp: '2026-10-28T13:56:39.690904+00:00'
title: Embargo pages use glossary aliases and undefined terms
type: learning
---

## Problem

The glossary (`docs/reference/glossary.md`) lists "aliases to avoid" for many embargo terms.
The embargo pages use several of those aliases, some in normative text.
They also use terms the glossary does not define.
A reader who checks the glossary gets a different name, and sometimes a different meaning, from the one on the page.

The mismatches were found while checking glossary terms during the STE readability pass over the remaining embargo pages (see the linked PR).
That pass did not change any term names, because doing so is a terminology decision, not a readability edit.

For each item, decide whether the glossary is stale (update the glossary) or the pages are (update the pages).

## Name mismatches

| # | Page wording | Glossary says | Where the pages use it |
|---|---|---|---|
| 1 | "default embargo" | alias to avoid for Actor Default and Protocol Default | `topics/process_models/em/defaults.md` (title "Default Embargoes", normative SHALL/SHOULD text), `negotiating.md`, `working_with_others.md`, `em/index.md`, `behavior_logic/use-cases/embargo-lifecycle.md` |
| 2 | "embargo period" / "default embargo period" | alias to avoid for Embargo | `em/defaults.md` (including normative text), `negotiating.md`, `working_with_others.md` |
| 3 | "embargo record" | alias to avoid for Embargo Event | `embargo-lifecycle.md` |
| 4 | "current embargo" | alias to avoid for Active Embargo | `embargo-lifecycle.md` |
| 5 | "embargo stance" | alias to avoid for Embargo Consent | `embargo-lifecycle.md` |
| 6 | "embargo state" | alias to avoid for EM | `negotiating.md` (normative: "the embargo state is *None*"), `behavior_logic/em_bt.md` |
| 7 | "respond-by instant" | "respond-by deadline" is an alias to avoid for RSVP Deadline; no page says "RSVP Deadline" | `embargo-lifecycle.md` |
| 8 | "case manager", "case owner" (lowercase) | Case Manager / CASE_MANAGER; protocol prose should say "the CASE_MANAGER" | `embargo-lifecycle.md` (about 45 "case manager", 17 "case owner"); `howto/activitypub/activities/establish_embargo.md` step 1 says "Case Manager" while the rest of the page says CASE_MANAGER |
| 9 | "Case Actor" and "CaseActor" both in prose | Case Actor (and ADR-0088 prefers CASE_MANAGER in protocol text) | `tutorials/other_demos.md`; its mermaid diagrams use `CaseActor` |
| 10 | "Signatory" used as a term (about 21 times; heading "The Case Owner Is a Signatory from the Start" in `em/defaults.md`) | no Signatory entry; the concept sits inside Embargo Consent and Embargo Adherence, and no page says "Embargo Adherence" | EM pages |
| 11 | "newly invited Participant" | "invited participant" is an alias to avoid for Inert Participant | `working_with_others.md` (normative text). Probably harmless: it describes the invitee, not the Inert state. |

## Possible meaning mismatches

These need a human judgment, not just a rename.

- **Embargo Event vs `EmbargoEvent`.** The glossary entry "Embargo Event" is a record of an end date and initiator "used to track embargo history".
  The pages always write `EmbargoEvent` and treat it as the embargo terms object itself (for example "the revised `EmbargoEvent`").
  The glossary has no entry under the code name.
- **Embargo Initialization seeding.** The glossary says seeding includes only the `AGREED` row of the Case Owner.
  `em/defaults.md` also seeds `AGREED` for a Reporter whose submission accepted the terms.
- **"embargo terms".** The glossary lists it as an alias to avoid for EmbargoPolicy, but the glossary's own Case Owner row and the pages use it to mean the terms of an embargo. The alias entry looks wrong.

## Acceptance

- Each item above is resolved: the glossary entry or the page wording is changed so that they agree, or the item is recorded as intended with a reason.
- The two meaning mismatches are checked against the specs (`spec-dump --topic` for embargo/EM) before either side changes.
- Normative text changes only with the matching spec text.

**Resolved**: 2026-10-28. Implementation is tracked in #5286 (glossary corrections) and #5287 (page and protocol spec wording, blocked by #5286).

Decisions: "default embargo" is an accepted umbrella term for the embargo a case begins with, from an actor default or, failing that, the protocol default. Name the source only where the text is about that split. The three meaning mismatches are glossary defects. Wording-only edits to protocol spec text are allowed when the requirement and its box change together. "newly invited Participant" is recorded as intended.

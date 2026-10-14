---
source: NOTES-message-type-reference--diataxis-these-pages-are-an-extraction-not-a-new-surface
timestamp: '2026-10-12T19:36:03.593627+00:00'
title: 'Diátaxis: these pages are an extraction, not a new surface'
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — the how-to/reference/explanation split of `docs/howto/activitypub/activities/` landed (#2999, #3001, #3002, #3003); the lasting rules stay in `notes/message-type-reference.md` § "Keep the three quadrants apart"
**Superseded by:** `docs/topics/activity_vocabulary_design.md`, `docs/reference/messages/`, DF-01-003

---

## Diátaxis: these pages are an extraction, not a new surface

`docs/howto/activitypub/activities/` was a **partial collapse** — it ran against
DF-01-003 (pages SHOULD NOT combine multiple Diátaxis content types; where a
combined view is unavoidable, the parts MUST be separated and each MUST link to
the canonical page of its own type). Those pages neither separated nor linked, so
they did not qualify for the escape clause. Each page mixed three quadrants, and
each quadrant went to its own tree:

| Content | Actual quadrant | Destination | Status |
|---|---|---|---|
| Design rationale, why-this-verb, alternatives weighed, activity-graph diagrams | Explanation | `docs/topics/activity_vocabulary_design.md` | done (#3002) |
| AS2 encoding facts, rendered JSON examples | Reference | `docs/reference/messages/` | done (#2999, #3001, #3003) |
| Task sequences and the `vultron-demo <scenario>` runs | How-to | stays, retitled "How to …" | done (#3003) |

The How-to half is not just the retitled remainder. Each guide now carries
prerequisites, an ordered activity sequence with conditional branches, a table of
what to verify, and links out to its Reference and Explanation counterparts — and
nothing else. The wire examples left with the `_*.md` partials that rendered them —
copies of reference content, which is what made them a collapse. A how-to step may
show the activity it sends again once that example is the *same* fragment the
reference section renders (ADR-0128): one source rendered in two places, separated
and linking to its canonical page, is DF-01-003's escape clause, not a collapse.

`ledger_replication.md` was retired rather than reshaped, because every sentence
on it described a pattern or a factory and none of it named an action a reader
takes — ledger fan-out is automatic. Apply that test rather than the page's
directory when deciding whether a how-to page has a task in it.

The Explanation half landed as a single page rather than several, because the
rationale is one argument: ActivityStreams supplies the verbs, so every Vultron
choice is either a verb selection, a decision not to mint a type, or a decision
that a distinction the wire draws has no protocol counterpart. Splitting it per
source page would have separated claims that only make sense together. Domain
rationale that already had a home was cross-linked rather than duplicated —
default-embargo reasoning to `topics/process_models/em/defaults.md`,
ledger-buffering reasoning to `topics/case_lifecycle/case_ledger_sync.md`, and
the Actor/`CaseParticipant` distinction to `reference/activitypub/objects.md`.

Four signals identified the collapse, and they generalize to any tree suspected of
one:

- **Noun-phrase titles in the how-to tree.** "Status Updates and Comments" and
  "Acknowledging Other Messages" name a subject, not a task, where DF-04-003
  requires "How to [Action]".
- **No imperatives and no steps.** A page with nothing for the reader to do is not
  in the Action half of the compass whatever directory it sits in.
- **A page that passes the bath test.** `acknowledge.md` was almost entirely
  design rationale, which is Explanation by definition.
- **A normativity disclaimer.** Nearly every page carried
  `{% include-markdown "not_normative.md" %}`, which is an author saying the
  content is discursive. The banners came off in #3003 for exactly that reason:
  a task guide has nothing to disclaim.

The banner signal inverts where you would expect it to. The two pages *without*
it, `error.md` and `acknowledge.md`, had the least task-shaped content of any —
so read its absence as no evidence either way, not as evidence of task shape.

So the reference pages are the Reference half of un-blurring an existing
collapse. Treating them as a fourth parallel surface would deepen the collapse
instead of resolving it.

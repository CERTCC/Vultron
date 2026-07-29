---
name: calve-epics
description: >
  The judgment procedure for shaping the epic roadmap on Project #24 —
  routing new issues onto the epic that matches them, calving a new epic off
  an over-accumulated theme, and periodically recrystallizing a muddled epic
  forest (fusing redundant epics, ejecting cross-grain items, splitting
  overgrown ones). Owns the glacier/iceberg model and the routing-vs-calving
  distinction; delegates the mechanics to `create-epic` and
  `manage-github-issue`. Invoked by `update-plan` (and available to
  `plan-issue` and `review-priorities`) — not usually run directly.
---

# Skill: Calve Epics

This skill is the single home for the *judgment* involved in shaping the epic
roadmap. Other skills call it whenever they need to decide where an issue
belongs or whether the epic structure itself needs to change. It owns the
model and the decision rules; it delegates every mechanical mutation to
`create-epic` (make an epic + wire leaves + schedule) and `manage-github-issue`
(parent/sub-issue wiring). Keeping the judgment in one place means callers
never duplicate calving logic.

## How the roadmap actually evolves: the glacier and the icebergs

The project tracks large bodies of related work on Project #24 as **epics**,
each tagged with a rough horizon — Now, Next, Later, or Someday (with a Focus
tier for what is actively in flight). Work matures on that board the way ice
moves through a glacier, and it is worth holding this picture literally rather
than flattening it into jargon.

Far-out bodies of work behave like **glaciers**. A glacier is a broad,
still-vague area — "production hardening," "architecture improvements",
"documentation" — that slowly accumulates related ideas the way a glacier
accumulates snowfall. New issues drift toward whichever glacier they
thematically match and pile up there. This accumulation looks like a problem
— glaciers grow into junk drawers that mix urgent items with things that can
wait years — but it is the intake mechanism working correctly. The glacier is
*supposed* to collect loosely-related snowfall; that is its job.

The important, high-skill act is **calving**: recognizing that a region of a
glacier has accumulated enough coherent mass to break off as an **iceberg** —
a body of work concrete and self-consistent enough to actually schedule and
build. The crucial point is that **the line along which a glacier calves is
drawn by architectural judgment, not by scheduling convenience.** The split
is not made because a chunk is the right size for a sprint or because a
deadline looms. It is made because a set of pieces turns out to realize a
single coherent design idea. Cutting a glacier along a merely convenient line
— by size, by date, by superficial theme — produces plausible-looking work
units that are subtly wrong, split across the grain of the actual design.

The metaphor extends, and each extension names a real event: sometimes a new
idea lands directly on an already-schedulable iceberg rather than on a
glacier; sometimes two icebergs turn out to belong together and **fuse**;
sometimes an iceberg accumulates enough new material that it needs to be
**split** again. All of these are ordinary parts of the process, not signs
that something has gone wrong.

## Two activities, two levels of judgment

Two distinct activities live inside this picture, and they require very
different things. **This skill keeps them separate on purpose.**

- **Routing** — when an issue arrives, deciding which glacier or iceberg it
  belongs to. This is classification against existing categories. It happens
  frequently and does not require holding the whole design in mind, so an
  agent may do it (asking a human only when the match is ambiguous).

- **Calving** — deciding *where and when* to break off a schedulable unit, or
  to fuse, split, or otherwise re-shape epics. This is architectural
  judgment. It is infrequent, and it cannot be handed to anyone who does not
  hold the whole design in mind. **The agent may propose a calving line; a
  human must confirm it before any epic is created, closed, or re-shaped.**

If you remember one rule: **route freely, calve only with a human.**

## Mode 1 — Route an issue onto the forest

Input: one or more leaf issue numbers that currently have no parent (or whose
parent is wrong). Goal: land each on the epic that matches it.

1. **Load the forest.** List open epics with their Schedule tier (see
   *Reading the board* below). Read each candidate epic's summary and, when
   the match is not obvious, its existing children — you are matching against
   what the epic *is about*, not its title alone.

2. **Match by grain, not by keyword.** Ask which epic's design idea this issue
   advances. A protocol-correctness bug belongs with protocol correctness even
   if its title mentions a demo scenario; a prod-only concern belongs with
   productionization even if it surfaced during demo work.

3. **Decide autonomy by ambiguity:**
   - **Exactly one clearly-matching epic** → parent it there automatically via
     `manage-github-issue` (`--sub-issue`). No need to ask.
   - **Zero plausible epics** → this is a calving signal, not a routing
     failure. Leave the issue at root and record it as a candidate for Mode 2.
     Do **not** invent an epic on your own.
   - **Two or more plausible epics** → ask the user with `AskUserQuestion`,
     presenting the candidates with a one-line rationale each. Route to their
     choice.

4. **Inherit the horizon.** A routed issue should adopt its epic's Schedule
   tier rather than defaulting to Someday, so routing a Next-tier correctness
   gap onto a Next-tier epic does not silently bury it. Set the issue's
   Schedule to match its new parent (see *Reading the board*). A true orphan
   left at root stays Someday.

## Mode 2 — Calve a new iceberg (human-gated)

Trigger: a region of a glacier — or a pile of root-level orphans from Mode 1 —
has accumulated enough coherent mass to become schedulable, OR routing keeps
failing because the right home does not exist yet.

1. **Draw the candidate line by design, not size.** Identify the single
   coherent design idea the pieces realize. Write it as one sentence. If you
   cannot, you do not have an iceberg yet — say so and stop.

2. **Never cut on convenience.** Do not calve because a set is "about the right
   size", because a deadline looms, or because several issues share a
   superficial keyword. Those cuts run across the grain.

3. **Propose, then wait.** Present the proposed iceberg to the user with
   `AskUserQuestion`: the one-sentence design idea, the leaf issues it would
   contain, and the Schedule tier you recommend. Ask whether the fracture line
   is along-grain. **Do not create the epic until the user confirms.**

4. **On confirmation, delegate the mechanics.** Invoke `create-epic` with the
   agreed title, body (lead with the one-sentence design idea), leaf issue
   numbers, and Schedule. `create-epic` owns epic-type creation, sub-issue
   wiring, board placement, and the `needs-decomposition` label — do not
   reimplement any of that here.

## Mode 3 — Recrystallize a muddled forest (human-gated)

Trigger: run periodically, or when routing repeatedly struggles because the
epics themselves are muddled — redundant umbrellas, epics mixing prod-only and
buildable-soon work, grab-bag epics with no coherent identity, an iceberg that
has grown two design ideas and needs splitting, or a **tier inversion**
(`check-priority-status` reports an issue blocked by something in a strictly
later tier — a Now item gated by a Someday item, a Focus item gated by a Next
item, etc.).

This is an anneal pass over the **not-yet-active** region only. Treat epics at
Now/Focus as frozen: you may *add* children to them, but do not re-tier or
re-shape them. Everything at Next/Later/Someday is moldable.

Recognized events (each requires human confirmation before any mutation):

- **Fuse** two epics that are the same glacier split in two: pick one to keep,
  re-parent the other's children onto it, close the redundant one with a
  comment pointing to the survivor.
- **Eject cross-grain material**: move children that flow against an epic's
  design idea to the epic that matches them (or calve a new one via Mode 2).
- **Split** an overgrown iceberg that now holds two design ideas into two.
- **Dissolve a grab-bag**: route each child to a design-coherent home, then
  close the emptied shell with a comment recording where its children went.
- **Resolve a tier inversion**: an issue blocked by something in a strictly
  later tier is scheduled ahead of the work it depends on. Diagnose which way
  the grain actually runs, then pick the fix: re-parent the dependent onto the
  blocker's epic (Mode 1 routing) if it simply landed on the wrong glacier;
  re-tier one of the two if the horizons are just mis-set; or, if the dependent
  and its blocker turn out to be one coherent design idea artificially split,
  calve them together into a single iceberg (Mode 2). Never fix an inversion by
  re-tiering a Now/Focus epic — those are frozen; move the *later* item earlier
  or re-parent instead.

Procedure:

1. Build the current picture: every open epic, its Schedule tier, its parent
   (sub-epics exist), and its open children. Diagnose where the grain and the
   current cuts disagree.
2. Propose the target crystals to the user as a small set of decision forks
   (`AskUserQuestion`), each naming the design idea of a proposed epic and what
   moves into it. Confirm tiers explicitly.
3. On confirmation, execute: create new epics via `create-epic`, re-parent via
   `manage-github-issue`, close emptied epics with `gh issue close --reason
   "not planned"` and a comment explaining the consolidation. Verify at the end
   that no non-epic issue is left orphaned and that the root-epic set reads
   cleanly.

## Reading the board

Do not hardcode Project #24 field/option IDs — they have drifted from values
baked into older skills, and a `Focus` tier now exists that older docs omit.
Query them live.

```bash
# Project + Schedule field/option IDs (live)
gh api graphql -f query='
query($owner:String!){
  organization(login:$owner){
    projectV2(number:24){
      id
      fields(first:30){ nodes{ ... on ProjectV2SingleSelectField {
        id name options{ id name } } } }
    }
  }
}' -f owner=CERTCC \
| jq '{projId: .data.organization.projectV2.id,
       schedule: (.data.organization.projectV2.fields.nodes[]
                  | select(.name=="Schedule"))}'
```

```bash
# Open epics with their Schedule tier
gh project item-list 24 --owner CERTCC --format json --limit 300 \
| jq -r '.items[] | select(.content.type=="Issue")
         | [( .content.number|tostring), (.schedule // "-"), .content.title]
         | @tsv'
# Cross-reference issueType via GraphQL to keep only Epic-type items.
```

To read an issue's current parent and an epic's open children, use the
`parent` and `subIssues` fields on the GraphQL `Issue` type.

## Delegation contract

- **This skill decides.** It never contains epic-creation or sub-issue-wiring
  mechanics of its own.
- `create-epic` — creates the Epic (correct issue type), wires leaves, places
  on the board, applies `needs-decomposition`. Call it in Modes 2 and 3.
- `manage-github-issue` — idempotent parent/sub-issue wiring for existing
  issues. Call it for all routing and re-parenting.
- Callers (`update-plan`, `plan-issue`, `review-priorities`) invoke *this*
  skill for the judgment and let it fan out to the two above.

## Constraints

- Route freely; calve, fuse, split, and dissolve only with human confirmation.
- Cut by design grain, never by size, date, or superficial theme.
- Treat Now/Focus epics as frozen: add children only, never re-tier or
  re-shape them.
- Do not create an epic when a single coherent design idea cannot be stated in
  one sentence.
- Query board field/option IDs live; do not trust hardcoded constants.

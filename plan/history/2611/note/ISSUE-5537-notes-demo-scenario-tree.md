---
source: ISSUE-5537-notes-demo-scenario-tree
timestamp: '2026-11-03T01:23:07.335649+00:00'
title: 'Archived from notes/demo-scenario-tree.md: the per-family byte-identity measurements
  and the composition Task order'
type: note
---

Superseded sections removed from `notes/demo-scenario-tree.md` by #5537, which
retired the interim `@scenario` path declarations. The note now states the
story form as the rule, so these per-family accounts of how byte identity was
reached no longer inform work that has not been done (NF-08).

## § "Composition" — the per-family setup-offset measurements

> **Byte identity is decided before the case opens.** With the cast and the
> tree-wide seed fixed, five of the twelve sibling pairs that share a prefix
> were already byte-identical, where none was before (#5532). The seven that
> were not all paired `rcvcv` or `rcvv-embargo` with a narrower sibling, and
> the cause was setup length, measured in #5534: the shared prefix was already
> isomorphic and drew the *same* ids — actor ids come from container slugs, so
> seeding draws no uuid — and differed only by a constant offset of 360 ms
> (`rcvcv`, two extra containers) or 160 ms (`rcvv-embargo`, one), about
> sixteen reads of the 10 ms stepping clock per extra container. Only writes
> read the clock, so where a poll or a verification sits does not matter; how
> many actor and peer records are written before `create_case` does. Seeding
> the character actors in the step that invites them, after the branch point,
> took both offsets to zero and made every checked pair of that family
> byte-identical. The two-coordinator pair came in the same way: its C2 is a
> character actor, so its opening seeds the same three containers `rcv`'s
> does, and every checked pair of the coordinator-first subtree is
> byte-identical (#5535). The vendor-first half measured the same way — `rv`
> at two containers, `rvv` at three and the `rvcv` pair at four, 120 ms and
> 160 ms apart — and its opening seeds the two every one of the four uses, so
> the Coordinator joins the `rvcv` pair's stories as an unseated container
> like any character actor although it sits in a fixed cast slot: what decides
> is whether *every* sibling uses it, not which slot it is in (#5536). A
> family joins `COMPOSED_FAMILIES` when its scenarios share one authored
> opening *and* that opening writes the same records in every one of them
> (DEMOCI-11-018).

The surviving rule is the general one, kept in the note: only a write reads
the recording clock, so a shared opening seeds only the containers every one
of its siblings uses.

## § "Composition" — the `{rcv-embargo, rcvv-embargo}` account

> The pair that proved them is `{rcv-embargo, rcvv-embargo}`: it shares four
> steps, so its prefix reaches ledger entry 33, past the embargo activation,
> where `PendingAssertionStore.pending_for_subject` used to read the clock to
> check expiry on a thread racing the owner's accept trigger, and where the
> process-global store those entries live in carried the previous scenario's
> asks into the next run. The two came out 80 ms apart in a whole-tree run and
> identical in solo runs until the lookup started taking its instant from the
> act that calls for it and the registry joined the per-run resets (#5591);
> the coordinator-first subtree is one family of seven now, with every pair
> checked. The vendor-first half parts at ledger entry 15 or 22, well ahead of
> that stretch, so it needed neither (#5536).

## § "Shared-prefix check" — the isomorphism description

> - Each recording's ids are relabeled by first appearance and its timestamps
>   dropped; the entries must then be equal up to the branch point, references
>   between objects included.
> - Byte identity is not required yet: siblings still place their shared steps
>   by hand, so the order can differ even where the logic matches. The
>   addresses no longer can — one cast and one seed (DEMOCI-11-020,
>   DEMOCI-11-025). A composed family tightens to byte identity, which then
>   holds by construction; name it in `COMPOSED_FAMILIES`
>   (`vultron/demo/recordings/prefix.py`).

## § "Task order" — the composition sequence

> 1. Composition, one PR per step, in this order: the story runner, piloted on
>    `rcv` and `rcv-reject` (#5533); the rest of the
>    "Coordinator invites Vendor" subtree, `rcvcv`, `rcv-embargo` and
>    `rcvv-embargo` (#5534); the two-coordinator subtree, `rccv-*` (#5535); the
>    vendor-first half, `rv`, `rvv` and `rvcv-*` (#5536, done); then retiring
>    `path=` and hand-placed `reach_step` (#5537).

## § preamble and the hand-placed step-mark description

> The `@scenario(path=...)` declarations are the interim form. Composition
> (§ "Composition") writes a branching story once and retires each family's
> declarations as it lands.

The step-mark description it carried:

> - The check reads where each branch point falls from the step marks. A
>   scenario calls `harness.reach_step(branch_point, choice, by=actor_id)`
>   where it makes the decision, before another role's steps that run ahead of
>   the choice's trigger; inside a phase it calls the module-level
>   `reach_step`. A shared helper takes a hook instead
>   (`before_answer=step_reporter(...)` on the invite chain).

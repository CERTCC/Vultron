---
title: Demo Scenario Tree — Names, Index, Prefix Check, Composition, Starting Points
status: active
kind: plan
tracks:
  - "#4747"
  - "#5303"
  - "#5344"
  - "#5345"
  - "#5346"
  - "#5347"
  - "#5348"
  - "#5349"
  - "#5613"
  - "#5649"
  - "#5650"
  - "#5651"
  - "#5652"
  - "#6025"
  - "#6026"
  - "#6028"
  - "#6194"
description: >
  Design for the remaining scenario-tree work (#4726): the letter-grammar names
  and how a rename keeps old URLs, the generated tree index the demo UI reads,
  the byte-identical shared-prefix check over recordings, how integration tests
  start from named points on the tree, how a branching story is written as
  composition on one fixed cast, and the Task order. The branch-point table and
  the story-derived path declarations are built; their rules live in
  demo-scenario-registry.md.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/testability.yaml
  - specs/case-proposal.yaml
related_notes:
  - notes/architecture-ratchet-corpus.md
  - notes/demo-scenario-registry.md
  - notes/demo-interactive-ui.md
  - notes/demo-scenario-authoring.md
  - notes/demo-future-ideas.md
  - notes/testing-pitfalls.md
  - notes/ci-workflow-authoring.md
relevant_packages:
  - vultron/demo/helpers
  - vultron/demo/scenario
  - vultron/demo/recordings
  - vultron/metadata/demo_scenarios
  - test/architecture
  - test/core/use_cases/received
  - ui/src/data
---

# Demo Scenario Tree — Names, Index, Prefix Check, Composition, Starting Points

Vocabulary: the **Demo** section of `CONTEXT.md` (scenario tree, branch point,
choice, ending, scenario, recording). Decision records: ADR-0098 and ADR-0104,
both amended 2026-10-15; ADR-0098 amended again 2026-10-30. Requirements:
DEMOCI-11-013 through DEMOCI-11-025, DEMOCI-11-034, DEMOCI-11-035, and
DEMOCI-11-054 through DEMOCI-11-072.
Parent Epic: #4747.

---

## The tree is declared in code

The branch-point table (`vultron/demo/scenario/branch_points.py`) and the
choices of each scenario's story (§ "Composition") are the tree;
`scenario_tree()` in
`registry/discovery.py` merges the paths and discovery fails unless every scenario is one
ending (DEMOCI-11-013, DEMOCI-11-014). The declaration rules are in
[demo-scenario-registry.md](demo-scenario-registry.md) § "The path and the
branch-point table". Read the tree there, not from a copy here.

- **Open consideration: silence scenarios** (#2053, #2056) may need a
  non-trigger wait or a demo-only clock trigger to show a timeout running out.
  Decide that when one of them is designed, and amend DEMOCI-11-013 then.
- **Future scenarios fit as new choices.** Two-reporter, split and merge
  scenarios (#3671, #4243, #4244) add actors and cases mid-path, which is why
  recordings are keyed by actor and case.
- **Open consideration: Vendor self-report** (#2591, #3667). The root branch
  point is the Reporter's, so a Vendor that finds the vul itself is not one of
  its choices. It is either a second root or the Vendor acting as the Reporter;
  decide when that scenario is designed. Its name begins with `v` either way.
- **Siblings share bytes, not only logic.** The steps before a branch point
  are one copy of the code for all its siblings, so their recordings agree
  byte for byte up to it (§ "Shared-prefix check"). The shared-prefix test
  fails when they drift; fix the order in the shared fragment without changing
  a verdict (DEMOMA-17-002), then regenerate the recordings.
- **Regenerate every scenario together, in one process.** One seed and one
  cast mean a run draws the same ids in every scenario, so a single fresh
  recording beside stale siblings fails the pairwise check even when nothing
  drifted. The daily freshness check runs `export-demo-recordings` with no
  `--scenario` (`demo-recordings.yml`), so that is the form whose output is
  committed. A per-scenario run now gives the same bytes as the whole-tree
  one, so it is usable for looking: what made the two disagree was a
  scenario's position in the process, and both causes are closed — a
  pending-assertion lookup read the stepping clock, and the store that holds
  those entries is process-global and was not dropped between runs, so the
  first scenario of a process stamped `rcv-embargo`'s
  `activate_embargo_on_case` entry 80 ms later than any later one (#5591).
  **Anything else that survives a scenario run brings the dependence back**:
  a process-global store a run writes must be dropped in
  `vultron.demo.recordings.runner._scenario_nodes`, beside the DataLayer, the
  py_trees blackboard and the pending-assertion registry.

## Names

Names keep the letter grammar: the leading letters spell the roles that join, in
order, and a suffix names the outcome (DEMOCI-11-015). The letter set is `r`,
`v`, `c` and `d` (Deployer, for `rcvd`), gaining one letter per new role. The
grammar is a convention kept in review, with no check: some joins happen in
scripted steps no choice records (`rcvv-embargo`'s late Vendor2 invite), so a
check would need the recordings, which is more upkeep than demo names are worth.
Path-generated names were rejected: inserting a branch
point upstream would rename every scenario below it, and a name is the stem of
the module, harness, narrative page, `scenario_start` marker and CI entry.

Write the two-party scenario `rv` in lowercase everywhere, labels and prose
included: uppercase `RV` is the Report Valid message shorthand, and the docs
acronym list keeps only that meaning.

A renamed scenario keeps its spec group ID and its old narrative-page URL, via
a `mkdocs-redirects` entry in `mkdocs.yml`. It gets **no sub-command alias**: an
alias table is a second list of names (DEMOCI-11-011), so update the
instructions and docs instead (#4736).

## Tree index

Built: `uv run export-demo-tree` writes `ui/src/data/scenario_tree.json`
(DEMOCI-11-016); its shape is in the exporter's docstring
(`vultron/metadata/demo_scenarios/export_tree.py`). Two rules for work on it:

- **Case keys come from the recordings.** Each recording is listed under the
  `caseId`s its entries carry, so a recording refresh that changes a case id
  needs a re-export too; the `demo-tree-sync` hook and the drift test say so.
- **Choices follow the table's order**, not discovery order, so adding a
  scenario never reorders the siblings the presenter sees.

## Shared-prefix check

**Every two registered scenarios are compared byte for byte up to the branch
point where their paths part** (DEMOCI-11-017, DEMOCI-11-018). The test is
`TestSharedPrefixes` in `test/demo_unit/test_recordings.py`, over the committed
recordings.

- **Every pair, no exemption table.** `shared_prefixes()`
  (`vultron/demo/recordings/prefix.py`) returns all `C(n, 2)` pairs of
  registered scenarios and each one is compared. A pair that is not
  byte-identical over its shared prefix is a defect in the shared code, not a
  pair to hold out: a list of exempt pairs makes the ones nobody listed the
  ones nobody checks.
- **A pair that parts at the root compares nothing.** The root branch point is
  the Reporter's and is decided before the case exists, so two scenarios that
  part there share zero ledger entries. Those pairs are still compared, and
  they pass on an empty prefix; the pairs that part later are what the check
  rests on. A test records per pair that each pair parting after the root does
  compare entries, so a collapse of the step marks to zero cannot leave the
  whole suite green over nothing.
- **Byte identity holds by construction, and the conditions are strict.** One
  copy of the shared code, one fixed cast and one tree-wide seed
  (DEMOCI-11-020, DEMOCI-11-025) make both recordings draw the same ids and
  read the clock the same number of times. What that requires of a shared
  stretch is in § "Composition".
- A container slot is not only an address. The proposer's container sets its
  default case roles (CP-01-013), which is why only the three fixed-role slots
  declare any: a case owner holds the same roles in every sibling, or the first
  entry already differs.
- The check reads where each branch point falls from the step marks, and the
  marks come only from the runner: `run_story` calls
  `harness.reach_step(branch_point, choice, by=actor_id)` as it passes each
  `choose(...)` item, so no scenario or fragment places one and no step is
  marked twice (DEMOCI-11-019). The recorder commits the marks as `steps.json`
  beside each recording and refuses a run that leaves a declared step
  unmarked. `test/architecture/test_scenario_reports_every_step.py` is the
  ratchet that keeps the runner the only source.
- The harness also checks the `by` actor holds the branch point's role; the
  rule is in [demo-scenario-registry.md](demo-scenario-registry.md) §
  "The path and the branch-point table".

## Composition

A branching story is written once: shared steps up to a branch point, then one
continuation per choice (DEMOCI-11-019, ADR-0098). Every registered scenario is
a story, and a story is the only way one places itself on the tree — the
registry takes no path parameter, so the path cannot be stated a second time
(DEMOCI-11-024). The tree has two halves, each with its own nested prefixes:
the coordinator-first subtree, whose Reporter tells a Coordinator, and the
vendor-first half, whose Reporter tells a Vendor.

- **An author writes a story from four names.** `vultron/demo/helpers/story/`
  holds them:
  `choose(branch point, choice, by=<cast name>)` declares one decision,
  `story(...)` concatenates named prefixes, choices and fragments into one flat
  sequence, `StoryState` is what a fragment runs against, and `run_story(name,
  plot, open_cast)` plays it inside `scenario_harness`. Prefer adding a
  fragment to extending the API — with one exception, the artifacts a family
  carries between its own steps (below). The package exports one more,
  `fragment_name`, which nothing a story writes calls: it is how the plot
  manifest records a step (next bullet).
- **A story item is a named module-level callable, or it is refused.**
  `fragment_name` records a fragment as `module.qualname`, so a lambda, a
  closure, a `functools.partial`, a callable instance, and any fragment a
  factory binds at module level (its qualname carries `<locals>`) raise
  `DemoStoryError` instead of reaching the manifest (DEMOCI-11-034). The
  reason is the diff: a name that moves when an unrelated enclosing function
  is renamed makes every later manifest diff unreadable, which is the one
  thing the artifact exists to keep legible. Write a parameterized helper as
  a call *inside* a named fragment, the way the invite chain already does.
- **A family's own artifacts are props, not state fields.** `StoryState` names
  what every story has: the case, the report, the Offer, the delivered
  Invites. What one family passes between its own steps is a
  `StoryProp[T](name, type_)` declared beside the fragments that share it,
  written with `state.keep(prop, value)` and read with `state.kept(prop)`
  (#5534). A per-family subclass is not an option, because a fragment is typed
  `Callable[[StoryState], None]` and a `Callable[[Subclass], None]` is not
  assignable to it; a field per family would put every family's artifacts on
  every story. `keep` type-checks on the way in, so `kept` never hands back a
  `None` and no reader checks for one. Do not reach for `state._case` and its
  siblings: every accessor on the state raises rather than hand out a `None`,
  and that is the property the fragments rely on. The embargo pair carries its
  embargo ids this way (`PROPOSED_EMBARGO`, `REVISED_EMBARGO`,
  `VENDOR2_SIGNED`) and `rcvcv` carries the note its late joiners reply to
  (`TIMELINE_ANSWER`), as does the vendor-first reply note. A case whose owner
  changed mid-story is the one artifact a prop does not serve, because
  fragments read the case through `state.case`: it has a setter beside
  `open_case`, `restate_case`, which replaces the case without re-arming the
  dump and **refuses a different id** — no act of a scenario changes a case's
  id, an ownership transfer moving `attributed_to` and leaving the id alone
  (CM-21-024), so a different one means the fragment read the wrong record and
  taking it would leave the story on one case while the armed dump and the
  followed ledger belong to another (#5535).
- **One prop per step, not one rewritten prop.** `rcvv-embargo` revises the
  embargo twice, and the second step keeps a *second* prop rather than
  overwriting the first. Overwriting would leave the previous id in place when
  a revision failed, and the steps that presuppose the new one would run
  against the old embargo instead of stopping.
- **A missing prop stops the story, as a missing step mark does.** A fragment
  reads what an earlier one made through an accessor that raises, so a failed
  act shows up as a `DemoStoryError` in the fragment that depended on it.
  `run_story` treats that exactly as `_mark_step` treats an unmakeable mark:
  on a run that has already recorded a failure it records it inside a
  `demo_gate` and stops the story, so the first failure stays the headline and
  the dependents are skipped; on a clean run it raises, because then the story
  really is mis-assembled. That is the flat-sequence form of the nesting the
  hand-placed scenarios used — `rcv-embargo` ran its termination, publication
  and closure inside one `demo_gate` on the revised embargo (DEMOCI-01-007).
- **A prop is a gate only once something reads it.** Keeping one carries no
  guarantee: a prop kept by the roster gate and read by nobody left both
  owner-decision continuations running after a timed-out roster, which is the
  gate the hand-placed form got from nesting them inside it — the suite stayed
  green, because every test of the keeping side passed (#5535). Make the read
  structural rather than remembered: a continuation whose precondition is
  another step's act takes that step's prop as a **required** parameter and
  reads it first, so it cannot be assembled without being told what it depends
  on. Then test the pair end to end, through `run_story` with the real gates,
  because the failure lives between the two halves and no test of either half
  alone can see it. The rule is a gate, not a convention:
  `test/architecture/test_story_props_have_readers.py` fails a prop with no
  keep site or no read site (DEMOMA-22-014), a construction that is no
  module-level constant (DEMOMA-22-018), and a reading parameter that gained a
  default or admits `None` (DEMOMA-22-016). Only the *reading* parameter is
  required — the keep side stays optional (DEMOMA-22-017), because
  `invitee_joins_the_case` keeps one only for a joiner some later act
  presupposes and is a plain `demo_check` for the rest. A step handed a prop
  must still do one of the two with it: dropping the `state.kept(...)` and
  leaving the required keyword is the same gap written the other way round,
  and the per-prop arms miss it whenever another step reads the same prop
  (DEMOMA-22-021).
- **Fragments and named prefixes.** A story fragment is one step of a story,
  a callable taking the `StoryState`. A named prefix is a `Story` several
  scenarios start with. Both live in `vultron/demo/helpers/` when more than
  one scenario uses them, and in the scenario's own module when only it tells
  that step. Name a prefix for every shared stretch, and **nest them**, each
  built from the one before: assembling siblings from fragments alone lets one
  of them slip in a step before the branch point. The coordinator-first
  subtree's named prefixes are `REPORTER_TELLS_THE_COORDINATOR` ⊂
  `COORDINATOR_INVITES_VENDOR` ⊂ `VENDOR_JOINS_THE_CASE` ⊂
  `REPORTER_ASKS_THE_VENDOR` (`coordinated_story/`),
  `VENDOR_JOINS_THE_CASE` ⊂ `REPORTER_PROPOSES_EMBARGO`
  (`coordinated_embargo_story.py`) and `REPORTER_TELLS_THE_COORDINATOR` ⊂
  `C1_INVITES_C2` (`two_coordinator_story.py`), one per branch point the
  subtree parts at. The vendor-first half's are `REPORTER_TELLS_THE_VENDOR` ⊂
  `THE_VENDOR_ANSWERS_THE_REPORTER` (`vendor_story/`) ⊂
  `THE_VENDOR_INVITES_A_COORDINATOR` (`vendor_coordinator_story.py`). The root
  one is the report submission and the owner's triage, which every scenario of
  a half tells identically, so a sub-family that parts earlier than its
  siblings splits the shortest prefix rather than writing a second copy of the
  opening (#5535).
- **A read-only check may sit inside a shared stretch; an act may not.** `rv`
  tells `THE_VENDOR_ANSWERS_THE_REPORTER`'s two steps with its own M1 and M2
  replica checks between them, so it starts with the shorter prefix and places
  the note fragment itself. A poll and a verification write nothing, so they
  advance no stepping clock, and the four vendor-first recordings still agree
  to the branch point. Keeping a scenario's own checks where they were is also
  what leaves its verdict and its milestone order untouched (DEMOMA-17-002).
  An *act* placed the same way would move the bytes,
  and the byte-identity check would catch it. **A read that reads the clock
  is not read-only for this purpose** and would move the bytes too: under the
  recording clock a read costs a 10 ms tick, so slipping one into a shared
  stretch shifts every later timestamp and digest, and on a racing thread it
  shifts them by a different amount on each run. `PendingAssertionStore`'s
  lookups were the one such read reached from a shared stretch; they now take
  the instant from the act whose check they are (#5591), which is the shape a
  read that needs a time should take — a new clock read inside a read path is
  a defect, not a measurement problem.
  Other read paths still read it — the decision-tree builders (#5649), five
  guard nodes (#5650), the sync cooldown checks (#5651) and the inbound
  extraction edge (#5652) — so a stretch that reaches one of those is not
  byte-stable yet even though it is deterministic today.
- **A decision both halves make gets its own module, not a family's.** The
  owner-keep-case choice — keep the case and approve the joiner's suggestion,
  or hand the case over and let the new owner invite — appears in the
  coordinator-first pair and in the vendor-first one, with a different cast
  each time. Its two continuations therefore live in
  `owner_decision_story/`, taking the owner, the joiner and the newcomer as
  `Part(name, label)` values read off the running story, never a family's
  cast constants; a family's module names only the parts each plays
  (DEMOMA-13-012, DEMOMA-14-017, #5535).
- **A scenario assembles its story.** Its module keeps its name-derived file
  (DEMOCI-11-003) and its `main()`, and states its `STORY` as one sequence: a
  named prefix, then `choose(...)` items and fragments. The whole story reads
  top to bottom in one file.
- **The path is read off the choices.** `@scenario(story=STORY)` derives the
  path from `Story.path`, so the tree index (DEMOCI-11-016) follows the code
  with no new sync step. `run_story` records each step mark as it passes a
  `choose`, so nothing places a `reach_step` by hand and the invitee's
  decision is placed by a fragment boundary rather than by a hook on a shared
  helper (DEMOCI-11-019).
- **One opener serves every family.** The reset, the seeding and the seating a
  family's opening does are the same three steps whichever family it is, so
  they are written once in `story_cast.py` (`CastSeat`, `open_story_cast`,
  `story_open_cast`) and each family supplies only its seats, in its
  `seed_containers_*` return order, and that seeder as a closure. A second
  family copying the first one's opener is what DEMOMA-17-003 forbids, and the
  seat order is load-bearing: the opener binds each session to the seat's own
  container, so a seeder returning a different number of actors raises rather
  than seating one actor on another's client (#5536).
- **A fragment takes the cast, not a container.** The cast and the tree-wide
  seed are fixed (DEMOCI-11-020, DEMOCI-11-025), so a fragment is handed the
  cast's `ActorSession`s under the names the story seats them under, and names
  no container of its own. It reads the case off the state; the fragment that
  opens one calls `state.open_case(...)`, which arms the ledger dump and
  follows the ledger in one step (DEMOMA-23-003).
- **The shared fragments address roles, not a scenario's own names.** A
  family's fragments read the cast under the family's role names, so one copy
  of each serves every scenario: `rcvcv`'s C1 and V1 are seated as
  `coordinator` and `vendor`, while `c1` and `v1` stay their names on the
  command line, in `ROLES` and as the devlogs directories the invariant
  harness loads (DEMOMA-19-018). The dump therefore takes
  `(devlogs name, cast name)` pairs rather than one name for both. Renaming a
  scenario's `ROLES` instead would move its CLI flags and its devlogs.
- **A character actor is seeded by the step that brings it in.** The shared
  opening seeds only the containers every sibling uses; a scenario's further
  containers are reset with the rest and left as `UnseatedContainer`s, which
  the fragment that invites each one reads with `state.container(name)`, seeds
  through the scenario's own `seed_containers_*` (idempotent, so the already
  seeded come back unchanged), and then `state.seat(name, session)`s. This is
  not tidiness: it is what makes byte identity hold (below).
- **An invitee's choice falls between the Invite and the answer.** Its role is
  read from the inert participant the Invite seats (CM-17-003), so a
  `vendor-join` choose placed before the Invite fails the deciding-role check,
  and one placed after the answer puts the answer inside the shared prefix.
  That is why the invite chain has two halves —
  `invite_and_await_delivery` then `answer_case_invite` — with the choose
  between them, and why `StoryState.delivered_invite` may hand back `None`:
  the answer owns the skip in its own gate, as the whole chain does
  (EDF-06-005).
- **A mark is a dependent step too.** A choose placed after an act reads its
  actor's role from what that act wrote, so a failed act leaves the mark
  unmakeable — a failed invite *trigger* seats no inert participant, and the
  Vendor then holds no role to check. `_mark_step` therefore marks inside a
  `demo_gate` and stops the story when the run has already recorded a failure,
  so the failed act stays the headline instead of being reported as a role
  defect; with a clean accumulator the mark still raises, because then the
  declaration really is wrong (DEMOCI-01-003, EDF-06-005).
- **Clear process-global registries between runs.** One seed means the second
  scenario in a process redraws the first one's ids, so a runner that plays
  more than one story must reset them — `reset_pending_assertion_stores()` is
  the one that bit, because a pending ask keyed on the redrawn case id
  suppressed the same ask in the next story (#5591).
- **Byte identity is decided before the case opens.** Only a write reads the
  recording clock, so where a poll or a verification sits does not matter; how
  many actor and peer records a story writes before `create_case` does. Each
  one is about sixteen reads of the 10 ms stepping clock, so one extra
  container seeded in a shared opening moves every later timestamp and digest
  by a constant offset and the siblings cease to be byte-identical. **A shared
  opening therefore seeds only the containers every one of its siblings uses**;
  the rest are reset with it and seeded by the step that brings each actor in
  (see the character-actor bullet above). What decides is whether *every*
  sibling uses a container, not which cast slot it sits in: the Coordinator of
  the `rvcv` pair joins as an unseated container although its slot is fixed.
- **No read on a shared stretch may read the recording clock, and no store a
  run writes may survive it.** These are the two conditions beyond a shared
  authored opening, and both are stated here rather than restated elsewhere:
  `prefix.py`'s module docstring and DEMOCI-11-018's rationale cite this
  section (DF-10-001). The longest shared prefix in the tree is
  `{rcv-embargo, rcvv-embargo}`'s, which reaches ledger entry 36, past the
  embargo activation, and it is the stretch that will find a new violation of
  either rule first: a clock read on a thread racing a trigger moves the two
  recordings apart by a varying amount, and a process-global store a run
  writes carries one scenario's rows into the next. A store a run writes is
  dropped in `vultron.demo.recordings.runner._scenario_nodes`, beside the
  DataLayer, the py_trees blackboard and the pending-assertion registry.
- **Key a composed view on the scenario and the case, never the case alone.**
  One seed also means every scenario draws the *same* case id, which is what
  lets siblings record identical bytes for a shared opening (DEMOCI-11-025) and
  is why `scenario_tree.json` nests its `recordings` map under the scenario
  name. A view that indexed recordings by case id would merge all eleven.
- **Specs stay whole stories.** Each scenario's spec group and its DEMOMA-16
  list of required semantic types describe the whole story, written by hand,
  so the run is checked against the spec, not against the code. Each group
  names the shared opening its story starts with in one line (DEMOMA-12-017,
  DEMOMA-12-018, DEMOMA-27-004, DEMOMA-19-024, DEMOMA-20-013,
  DEMOMA-21-015, DEMOMA-13-012, DEMOMA-14-017). Give a shared
  stretch its own spec group only when one change to it must be edited in
  several scenario groups.
- **Verdicts do not move, and a recording alone does not show it.** A change that
  extracts or merges demo code is a consolidation, so no scenario's pass or fail may
  change in it (DEMOMA-17-002). What a scenario passes or fails on is its protocol
  acts *and* its checks, and a recording holds only the acts: a `demo_check` moved out
  of its `demo_gate`, or a wait that reads another actor's replica, leaves the
  recording byte-identical (#5596). The evidence is therefore the base-versus-head
  comparison below, over both traces. Read a ledger diff for what it says about acts:
  giving a joining coordinator the RM triage a vendor gets adds an `engage_case` entry
  and drops a participant status at closure. A shared join helper therefore takes
  `triages=`: a vendor judges the report it was invited over, a coordinator joining to
  coordinate does not.
- **A demo PR is checked by recording base and head, not by the committed files.** On
  a PR that changes `vultron/demo/`, `demo-verdict.yml` records every registered
  scenario in-process at both commits and compares each scenario's two runs
  (DEMOCI-11-054, DEMOCI-11-055). Nothing is committed, so no PR regenerates a
  recording (#3901) and a stale committed recording does not matter. Core-only PRs are
  not consolidations; the daily `demo-recordings.yml` run covers their drift.
- **The two commits are the merge base and the head, each recorded by its own code.**
  The base branch's tip is not one of them: a tip that moved ahead would attribute
  `main`'s own verdict changes to this PR. The base side runs in a `git worktree` at
  the merge base, under that commit's own `uv sync --dev --frozen`, because recording
  it with the head's installed code compares the head with itself and reports every
  scenario unchanged. The head's code then reads both written sides and compares them.
- **Two traces, because each is blind to what the other sees.** The normalized ledger
  shows an added act, a changed note text or a changed argument. The check tree shows
  every `demo_step`, `demo_check` and `demo_gate` the run entered, nested as it ran,
  with its kind, label, outcome and the cast members whose containers it read
  (DEMOCI-11-056, DEMOCI-11-057). Capture it at runtime, where the three context
  managers and the recorder's routed client are the only paths, not by reading the
  source: a static pass cannot resolve which actor `state.session(owner.name)` is, and
  that subject is what EDF-06-002 constrains.
- **Compare the verdict, an allow-list of fields, never a cleaned copy.** Each ledger
  entry is projected onto `VERDICT_FIELDS` in `vultron/demo/recordings/traces.py`:
  which act, at which position, by whom, to whom, with which result, states, roles
  and content (DEMOCI-11-058, DEMOCI-11-059). Ids in it are relabelled by first
  appearance, one mapping across ledger and check labels, and a quoted timestamp
  reads as a placeholder (DEMOCI-11-070, DEMOCI-11-071). A list of noise fields is
  the wrong shape: it failed on the first PR that drew ids another way, because the
  signatures cover the raw ids and `proofValue` was not on it (#6194). A field joins
  the list only if a change in it is a change in what the scenario did. A test walks
  every model a ledger entry can carry and fails on a field classified neither in nor
  out of the verdict, so a new field forces that decision (DEMOCI-11-072). A cast
  actor's URI is left spelled out: it is derived from a fixed container address
  (DEMOCI-11-020), so it never shifts, and a diff that still names `actor1` is one a
  person can read. **Leaving times out costs coverage**: a time the protocol
  *derives* is left out with the clock's, so an embargo's `startTime` and `endTime`
  and an invite's `rsvpDeadline` do not count, and an embargo name that quotes them
  reads the same. No kept field a scenario writes carries either window today, so a
  change to the default embargo window or the RSVP window compares equal, and the
  gate is not a check on those constants.
- **A deliberate verdict change takes the `demo-verdict-change` label.** It belongs in
  its own change (DEMOMA-17-004); the label passes the job, and the job still prints
  the diff to its summary, so the opt-out shows what it admits (DEMOCI-11-063,
  DEMOCI-11-064). The two halves are declared separately: `compare-demo-runs` takes
  `--allow-difference`, which prints every difference and exits zero, and the job
  passes that flag exactly when the pull request carries the label. A difference exits
  4 rather than 1, so an opt-out keyed on "non-zero" cannot excuse a crashed recorder
  as a deliberate change. The comparison fails on an empty scenario set
  (DEMOCI-11-062, DF-09-009).
- **The label is a trigger, not just a condition, and the `CI gate` carries the same
  two types.** `demo-verdict.yml` adds `labeled` and `unlabeled` to its
  `pull_request` types, so applying the label turns the job green and removing it
  turns the job red again, neither needing a hand re-run. The second direction is the
  one that matters: an opt-out that survives its own removal admits every later
  difference too. `ci-gate.yml` needs both types for the same reason — it judges once
  per pull-request event and is the one required check, so an event it misses leaves
  its earlier verdict standing over a check that has since turned red, and the
  ruleset admits the merge. The rule generalizes: the gate's types cover every other
  pull-request workflow's, which `test/ci/test_ci_gate.py` pins. A label a workflow's
  own `GITHUB_TOKEN` applies raises no event, so the size label re-runs neither
  ([ci-workflow-authoring](ci-workflow-authoring.md)).
- **The job's verdict is the command's exit status, propagated.** It decides nothing
  itself: 4 is a difference, 3 an empty scenario set, 1 a crashed recorder, and a job
  that re-derived any of the three from the log would be a second place for them to be
  confused. It owns only which two commits to record, whether the label is on, and
  writing the comparison's output to its step summary — on the failing arm as well,
  since the diff a reader needs is on exactly the run that failed.
- **The plot manifest catches a reorder for free.** It lists each story's choices and
  fragment names, read without running anything, and drift-fails on any change in
  order (DEMOCI-11-034, DEMOCI-11-035). `TestSharedPrefixes` compares two *committed*
  recordings with each other, so a reordered shared fragment moves both alike and
  still passes it. `demo-verdict.yml` is what catches the reorder a PR makes. Running
  the comparison by hand is for reading a difference before pushing, most of all in a
  PR that edits *inside* a fragment: that is the one change the manifest cannot see,
  while a reorder drift-fails the manifest instead. On the base commit run `uv run
  compare-demo-runs --write /tmp/runs/base`, on the head `--write /tmp/runs/head`,
  then `uv run compare-demo-runs --base /tmp/runs/base --head /tmp/runs/head`. **Two
  directories, outside the repository**: one name in both positions makes the head
  write overwrite the base and the comparison compare a directory with itself, which
  reports every scenario unchanged — the silent pass of #5589 again, so the command
  refuses it. It reads both traces, so it needs no clean tree and overwrites no
  committed file. Step-mark drift stays the scheduled `demo-recordings` run's
  business: a mark can move to a
  different ledger tail with the ledger unchanged, and the comparison *compares*
  neither the marks nor the committed files. It does still **read** the marks — a run
  that leaves none, or leaves them out of its declared path's order, fails
  `record_scenario` outright (exit 1, a crashed recorder), so that is the one kind of
  step-mark defect the comparison does report.
- **The plot renders as a story a domain expert can read.** How to write a
  fragment's opening sentence, and what a new scenario's narrative page must end
  with, are in `demo-scenario-registry.md` § "What the decorator carries" and
  § "The generate-vs-check split" (DEMOCI-11-065 to DEMOCI-11-069). Both the
  rendering and the hand-written narrative stay: the narrative is written without
  the code so that it can contradict it, and a rendering of the code can only
  agree (#2204).

## Test starting points

The multi-actor integration tests start from the same tree (TB-15). A **named
starting point** is a declared step on a scenario path: the point the runner
marks for the shared-prefix check (DEMOCI-11-017), so the harness that builds a
point stops a run there.

- **Build once, copy per test.** Once per session the harness runs a path up to
  the point, in-process, and saves each actor's store; every test loads its own
  copy (TB-15-001, TB-15-002). Sibling tests that replay the same prefix pay for
  it again and test it again, on every CI run.
- **Seed it like the recordings.** Build with the recordings' seeded id source
  and clock (#3901), so every copy is identical across runs (TB-15-003).
- **Each step is tested once.** The test that moves the case from one starting
  point to the next is the only one that runs that step; every other test runs
  only its own acts (TB-15-002).
- **The rebuild check follows the same rule.** It proves a point rebuilds from
  its ledger when the point is built, then replays only each test's own entries
  onto the rebuilt point (TB-15-004, TB-15-005).
- **Finer states are declared steps, not new branch points.** Embargo
  negotiation states the tests need ("Vendor1 proposed a revision", "the
  CASE_MANAGER agreed") are steps on the embargo paths. They add no choice and
  no scenario, so the branch-point table stays the tree's only choices
  (DEMOCI-11-013).
- **A state no story reaches** (a diverged replica, a forced commit failure)
  loads the nearest point and applies the test's own change, rather than building
  a case outside the ledger (TB-15-006).
- **The copy is a SQLite `backup`, not `clone_for_actor`.** `clone_for_actor`
  opens a different actor's empty store. Every in-memory store is named
  `<base>-<slug>` from the configured base and the actor slug (`vultron-<slug>`
  by default), so a saved point needs a name of its own, copied into each test's
  freshly named store (#5345).
- **Make one act cheap first.** In #5344's profile one received act reread the
  case 90 times (743 reads of 73 records); that per-act cost is paid on every
  step, starting points or not. `_pending_announce_index` already reads only
  the outbox rows queued since its last snapshot (#4906).

## Task order

1. Test starting points: #5344 (one act cheap) and #5345 (the harness, which
   stops a run at a step mark), then the pilot #5346, then the migrations
   #5347 and #5348, and last #5349.
2. The clock-reading read paths that keep a shared stretch from being
   byte-stable: #5649, #5650, #5651 and #5652. The plot manifest they follow is
   committed.

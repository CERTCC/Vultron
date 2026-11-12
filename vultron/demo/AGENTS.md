# AGENTS.md — vultron/demo/

> For project-wide conventions see the root [AGENTS.md](../../AGENTS.md).
> This file covers rules specific to demo scripts and multi-actor scenario code.

Full write-ups live in
[`notes/demo-scenario-authoring.md`](../../notes/demo-scenario-authoring.md); the
causal-gating rules are in
[`notes/event-driven-control-flow.md`](../../notes/event-driven-control-flow.md) and
[`notes/demo-ci-diagnostics.md`](../../notes/demo-ci-diagnostics.md). The rules below
are the enforceable form, and one idea is behind most of them: a demo exists to prove
the protocol works, so every shortcut that makes a scenario pass by doing the protocol's
job *for* it turns the demo from evidence into decoration.

---

## Common Pitfalls — demo layer

### Puppeteer Actors via Trigger Endpoints, Never Spoof via Inbox Injection

Drive actor behavior through real HTTP trigger endpoints. **Puppeteering** = trigger
the actor so it decides and acts (exercises the BT). **Spoofing** = forge the
resulting activity as if it had already decided (skips the BT). If the trigger
endpoint you need does not exist, build the full stack (endpoint → service → BT)
*first*. Reports too, in every demo: `reporter_submits_report` (#4675).
[demo-scenario-authoring](../../notes/demo-scenario-authoring.md) § "Puppeteer
Actors via Trigger Endpoints". (ISSUE-1535)

### Never Carry One Actor's Mail to Another Actor's Inbox

A scenario demo MUST NOT POST an activity into *another* actor's inbox, including
via `post_to_inbox_and_wait`: carrying the mail leaves the outbox→delivery→inbox
path unexercised, so demo CI proves nothing end-to-end. Poll the effect instead
(`wait_for_case_on_container`, `find_case_invite_for_actor`,
`wait_for_received_activity`, DL-06-006); a reliably-timing-out poll is a delivery
bug, not a workaround. **No self-delivery exception** either. Scope, the
exchange-demo exemption and the routing reason:
[demo-scenario-authoring](../../notes/demo-scenario-authoring.md) § "Never Carry One
Actor's Mail to Another Actor's Inbox" and
[ownership-transfer](../../notes/ownership-transfer.md) § "The Accepting Actor's
Replica Updates via the CASE_MANAGER's Announce". (#3980, CONCERN-1635, ISSUE-2719)

### A Scenario Declares Itself Once; Every Consumer Is Generated

A scenario module declares itself, and nothing else anywhere does:

- `@scenario(name, label, participants, feature, in_pr_set, story)` on `main()`, from
  `scenario/registry/`. `story` is **required** and is the only thing that places the
  scenario on the tree: its path is read off the story's `choose(...)` items, which name
  `scenario/branch_points.py` entries, and there is no path parameter to state it a
  second time (DEMOCI-11-019, DEMOCI-11-024). Every table, `.github/demo-scenarios.json`
  and `scenario/plots.json` are generated from it (`demo-scenarios --write`, gated by
  `demo-scenarios-sync`): never hand-edit one, change the decorator. Script, harness and
  narrative paths are **derived** from `name` (`<name_>_demo.py` or a `<name_>_demo/`
  package, `test_<name_>_invariants.py`, `<name>.md`; hyphens become underscores) —
  rename to match, never add an override (DEMOCI-11-003).
- `ROLES: list[ActorRole]` (`helpers/actor_roles.py`), one frozen role per actor
  **in `main()` parameter order**, and `CLI_HELP: str`. These generate the
  scenario's `--<role>-url` / `--<role>-id` options and its `--help`; each address
  comes off the role's cast slot, read by the family's shared client factory, so a
  scenario module declares no `*_BASE_URL` constant of its own. So **never add a
  `@main.command` block to `cli.py`** (DEMOCI-11-045), and mind the quiet drift
  direction the `main()`-signature ratchet catches: a keyword no role declares gets
  no option, keeps its default, and runs against the wrong container without failing.

A scenario specified but not yet built goes in `notes/demo-future-ideas.md`, never
the registry (DEMOCI-11-010); its recording is generated, never hand-edited.
[demo-scenario-registry](../../notes/demo-scenario-registry.md) has the write-up.

### Extract Before Reuse: No Copy-Paste from Existing Scenario Files

Before the **second** use of a pattern from an existing scenario file, extract it
to `vultron/demo/helpers/` — never copy a function body, polling loop, or
verification block into a new scenario; copy-paste propagates latent bugs with the
valid patterns (#1632). A once-only pattern may stay inline with a comment marking
it for extraction. MUST-level per DEMOMA-17-001 (specialising CS-22-001); the
rationale and the four-step application are in
[demo-scenario-authoring](../../notes/demo-scenario-authoring.md) § "Extract Before
Reuse". Siblings go further: a family writes its shared opening **once**, as a named
prefix of story fragments (`helpers/story/`) each scenario assembles its story from
(DEMOCI-11-019, [demo-scenario-tree](../../notes/demo-scenario-tree.md)
§ "Composition", #5533, ISSUE-1652).

### Gate Each Step on Its Cause, Not on Its Position in the Script

A scenario reads "A, and then B"; the protocol means "A, **therefore** B". Where
those differ you have a race, because triggers return 202 and the effect commits
later, in a background task, on another container. Several of Epic #2136's
sub-issues were this one defect in different scenarios.

1. **Gate on the committed effect, read where it commits** — from the committing
   actor's own client (EDF-06-002).
2. **Never gate on a synchronously-available proxy** — it proves the cause
   *started* (EDF-06-003, bug #2134).
3. **Discover a caused object by its properties, not its cause's ID** — a forwarded
   activity has a new identity; scan by discriminator via `run_case_invite_chain`
   (EDF-06-004, DEMOMA-17-001, #2178).
4. **Use `demo_gate` for a precondition, `demo_check` for a verification**
   (DEMOCI-01-007, EDF-06-005) — see the next rule.
5. **Put the gate in `vultron/demo/helpers/`** — scenario modules MUST NOT define
   their own polling loops. That is how the #2178 fix landed in one handoff scenario
   and not its sibling, until #5535 put both on one copy (DEMOMA-22-008).
6. **Label irreducibly temporal waits as such** at the call site — liveness
   probes, embargo deadlines, transport backoff (EDF-06-006).
7. **Raising a timeout is not a fix.** Either the observable is wrong (1–3) or the
   effect can be *lost* rather than delayed, in which case the protocol must
   buffer it (ADR-0037, ADR-0059) and a demo guard papers over a production bug.
8. **Test gates against the real context manager**, and read a run's checks by
   `walk()`ing what `recording_checks()` recorded (`utils/check_tree.py`, #6127);
   for one kind's labels use `test.demo._helpers.recorded_labels(kind)` (#6155).
   Stubbing one out with `contextlib.nullcontext` makes the assertion propagate and
   the test pass while proving nothing — how the missing `engage-case` gate escaped.
9. **Two milestones in a row assert two different things**, each label describing
   only its own block, and the holding test compares the halves' reads *each way*,
   keyed on the container and the actor read rather than the helper name — a
   subset adds nothing (#5602;
   [demo-scenario-authoring](../../notes/demo-scenario-authoring.md) § "Two
   Milestones in a Row Assert Two Different Things").
10. **Nest the step that reads a value inside the block that produces it.** A
    `None`/`""` pre-init is allowed only when every later read is guarded — the one
    part a check enforces (#3038, `test_demo_step_no_unbound_ratchet.py`). Name each
    nested statement with its own `demo_check`/`demo_step` *unless the callee opens
    one*: an outer block around a self-checking helper never fails.

Full reasoning: EDF-06, DEMOMA-22, ADR-0058, and
[`event-driven-control-flow`](../../notes/event-driven-control-flow.md) § "Temporal
Sequence vs. Causal Sequence". (CONCERN-2181)

### Never Wrap a Causal Wait in `demo_check` (and Never Leave One Bare)

A `wait_for_*` call that is a precondition for the next step MUST be wrapped in
`demo_gate` — not `demo_check`, and not left bare. `demo_check` records the timeout
and **continues**, so the next step runs on state that was never established. A
**bare** call raises `AssertionError` past the harness's failure accumulator:
earlier `demo_check` failures are lost and downstream steps get no structured skip.
Bare calls look like gates and are not. **How to decide:** would the next step
operate on wrong or incomplete state if this wait timed out? **Yes** →
`demo_gate`. **No** → `demo_check`, labelled as temporal per EDF-06-006.
Anti-patterns and the diagnostic workflow:
[demo-ci-diagnostics](../../notes/demo-ci-diagnostics.md) § "Async Race Window
Patterns". EDF-06-005, EDF-06-006. (CONCERN-2325)

### Event-Phrase Lookups MUST Use `lookup_entry()`, Not a Local Phrase Dict

Display-layer code maps `MessageSemantics` → phrase via `lookup_entry(semantics)
.phrase` from `vultron.semantic_registry`, never a local `dict[str, str]` that drifts
as the enum grows; only `{actor}`, `{object}` and `{target}` are filled (CONCERN-1675,
[activitystreams-semantics](../../notes/activitystreams-semantics.md)).

### Every Scenario Runs on the Fixed Cast

`vultron/demo/helpers/cast.py` declares one role-neutral container per cast slot, with
one address and one actor id per slot in every scenario (DEMOCI-11-020). Slots 0–2 are
the first Reporter, Vendor and Coordinator a scenario seats; 3 and up take their role
from the act that seats them (DEMOCI-11-021). Only slots 1 and 2 declare
`VULTRON_ACTOR__DEFAULT_CASE_ROLES`, because only they own a case and a case is owned
as a role (CP-01-013, DEMOCI-11-032). Seat a new part in a free slot; a wider scenario
grows `CAST_SIZE`. [demo-scenario-authoring](../../notes/demo-scenario-authoring.md)
§ "Every Scenario Runs on the Fixed Cast" (#5532).

### Exchange Demos: Discover the Canonical Case from the DataLayer

After `validate-report` the BT proposes the report and the CaseActor creates the
**canonical** `VulnerabilityCase` (ADR-0041). Do NOT call `create_case_activity` in
exchange demo setup: that makes a second, vendor-local case with no `ReportCaseLink`.
Find the canonical one with `wait_for_initialized_case(client, report_id)`, keyed on
the report. [case-proposal](../../notes/case-proposal.md) § "Exchange Demo:
Discovering the Canonical Case". (ISSUE-1994)

### The Ledger Dump Belongs in the Failure Path, Not After the Last Phase

Forensic artifacts matter most in the run that fails, so a dump placed after the
last phase never runs when it counts (#2239: `devlogs/` empty, invariant harness
dead on artifact download).

- `run_story()` enters `scenario_harness("<demo-name>")` for every scenario: it
  resets the accumulator, always dumps on the way out, and asserts success last.
- The dump is armed as soon as a case exists, by `state.open_case(...)`, which
  also follows the canonical ledger — both exactly once.
- Do not re-add `try/finally: assert_demo_success()` in `main()` — a second owner
  of the accumulator asserts before the dump runs.
- Keep the dump step thin, delegating to `helpers.ledger_dump.dump_case_ledgers()`.
  The manifest is not optional, and a dump failure must never replace the scenario's
  exception; the step and per-family wrapper are in the note. DEMOCI-10, DEMOMA-23,
  [demo-ci-invariants](../../notes/demo-ci-invariants.md). (ISSUE-2239)

### Demo Devlog Race: Wait for Replica Before Dumping

After any phase that commits a new canonical ledger entry, poll until the replica
acknowledges the sender's tail hash before writing the devlog, or the dump misses
entries still in `Announce(CaseLedgerEntry)` fan-out (DEMO-DEVLOG-RACE,
[demo-ci-diagnostics](../../notes/demo-ci-diagnostics.md) § "Demo Devlog Race").

### BT Demo `main()` Must Be Callable With No Arguments

`[project.scripts]` entry points call `main()` with no arguments. Use
`def main(args=None)` and fall back to `_parse_args()` when `args is None`, so both
the console script and `cli.py`'s click sub-group work. Test the real console script
with `PYTHONPATH= uv run <script>`.
[demo-scenario-authoring](../../notes/demo-scenario-authoring.md) § "BT Demo `main()`"
(ISSUE-1568).

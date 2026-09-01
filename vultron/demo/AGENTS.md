# AGENTS.md — vultron/demo/

> For project-wide conventions see the root [AGENTS.md](../../AGENTS.md).
> This file covers rules specific to demo scripts and multi-actor scenario code.

Full write-ups live in
[`notes/demo-scenario-authoring.md`](../../notes/demo-scenario-authoring.md);
the causal-gating rules are in
[`notes/event-driven-control-flow.md`](../../notes/event-driven-control-flow.md)
and [`notes/demo-ci-diagnostics.md`](../../notes/demo-ci-diagnostics.md). The
rules below are the enforceable form.

A demo exists to prove the protocol works. Every shortcut that makes a scenario
pass by doing the protocol's job *for* it turns the demo from evidence into
decoration — that is the single idea behind most of these rules.

---

## Common Pitfalls — demo layer

### Puppeteer Actors via Trigger Endpoints, Never Spoof via Inbox Injection

Drive actor behavior through real HTTP trigger endpoints. **Puppeteering** =
trigger the actor so it decides and acts (exercises the BT). **Spoofing** = forge
the resulting activity as if it had already decided (skips the BT). If the trigger
endpoint you need does not exist, build the full stack (endpoint → service → BT)
*first*. See
[`notes/demo-scenario-authoring.md`](../../notes/demo-scenario-authoring.md)
§ "Puppeteer Actors via Trigger Endpoints". (ISSUE-1535)

### Never Carry One Actor's Mail to Another Actor's Inbox

A scenario demo MUST NOT POST an activity into *another* actor's inbox —
including via `post_to_inbox_and_wait`. Delivery is the transport's job; carrying
the mail means the outbox→delivery→inbox path is never exercised and demo CI
proves nothing end-to-end. Poll the effect instead
(`wait_for_case_on_container`, `find_case_invite_for_actor`,
`wait_for_object_stored`). A reliably-timing-out poll is a delivery bug to
investigate, not a workaround to write.

Scope: `vultron/demo/scenario/`. Exchange demos under `vultron/demo/exchange/`
drive one backend directly and use `post_to_inbox_and_wait` as their normal
mechanism.

**The CONCERN-1653 self-delivery exception is retired** — under ADR-0053 the
ownership-transfer Accept routes through the CaseActor and every replica updates
automatically. Do not re-add a self-delivery call to make a replica update; fix
the routing. See
[`notes/ownership-transfer.md`](../../notes/ownership-transfer.md) § "Retired
Demo Workaround: Accept Self-Delivery". (CONCERN-1635, ISSUE-2719)

### Extract Before Reuse: No Copy-Paste from Existing Scenario Files

Before the **second** use of a pattern from an existing scenario file, extract it
to `vultron/demo/helpers/` — do not copy a function body, polling loop, or
verification block into a new scenario. Copy-paste propagates latent bugs
alongside valid patterns (#1632 after PR #1629). A once-only pattern may stay
inline with a comment marking it for extraction.

MUST-level per `specs/multi-actor-demo.yaml` DEMOMA-17-001 (specialising the
project-wide SHOULD, CS-22-001). Rationale and the four-step application in
[`notes/demo-scenario-authoring.md`](../../notes/demo-scenario-authoring.md)
§ "Extract Before Reuse". (ISSUE-1652)

### Gate Each Step on Its Cause, Not on Its Position in the Script

A scenario reads "A, and then B"; the protocol means "A, **therefore** B". Where
those differ you have a race, because triggers return 202 and the effect commits
later, in a background task, on another container. Seven of Epic #2136's nineteen
sub-issues were this one defect in different scenarios.

1. **Gate on the committed effect, read where it commits** — from the committing
   actor's own client (EDF-06-002).
2. **Never gate on a synchronously-available proxy** — it proves the cause
   *started* (EDF-06-003, bug #2134).
3. **Discover a caused object by its properties, not its cause's ID** — a
   forwarded activity has a new identity; use a discriminator scan such as
   `find_case_invite_for_actor` (EDF-06-004, bug #2178).
4. **Use `demo_gate` for a precondition, `demo_check` for a verification**
   (DEMOCI-01-007, EDF-06-005).
5. **Put the gate in `vultron/demo/helpers/`** — scenario modules MUST NOT define
   their own polling loops. That is how the #2178 fix landed in
   `fvcv_handoff_demo.py` but not `fccv_handoff_demo.py` (DEMOMA-22-002,
   DEMOMA-17-001).
6. **Label irreducibly temporal waits as such** at the call site — liveness
   probes, embargo deadlines, transport backoff (EDF-06-006).
7. **Raising a timeout is not a fix.** Either the observable is wrong (1–3) or the
   effect can be *lost* rather than delayed, in which case the protocol must
   buffer it (ADR-0037, ADR-0059) and a demo guard papers over a production bug.

**Testing gates:** exercise the real context manager. Patching
`demo_check`/`demo_gate` out with `contextlib.nullcontext` makes the assertion
propagate and the test pass while proving nothing — exactly how the missing gate
before `engage-case` escaped notice.

Full reasoning: EDF-06, DEMOMA-22, ADR-0058, and
[`notes/event-driven-control-flow.md`](../../notes/event-driven-control-flow.md)
§ "Temporal Sequence vs. Causal Sequence". (CONCERN-2181)

### Never Wrap a Causal Wait in `demo_check` (and Never Leave One Bare)

A `wait_for_*` call that is a precondition for the next step MUST be wrapped in
`demo_gate` — not `demo_check`, and not left bare.

- `demo_check` records the timeout and **continues**, so the next step runs on
  state that was never established.
- A **bare** call raises `AssertionError` directly, bypassing the harness's
  failure accumulator: earlier `demo_check` failures are lost and downstream steps
  get no structured skip. Bare calls look like gates but are not.

**How to decide:** would the next step operate on wrong or incomplete state if
this wait timed out? **Yes** → `demo_gate`. **No** → `demo_check`, labelled as
temporal per EDF-06-006.

Anti-pattern examples and the full diagnostic workflow:
[`notes/demo-ci-diagnostics.md`](../../notes/demo-ci-diagnostics.md) § "Async Race
Window Patterns". Normative: EDF-06-005, EDF-06-006. (CONCERN-2325)

### Event-Phrase Lookups MUST Use `lookup_entry()`, Not a Local Phrase Dict

Display-layer code maps `MessageSemantics` → phrase via
`lookup_entry(semantics).phrase` from `vultron.semantic_registry`, never a local
`dict[str, str]`. A parallel table drifts silently as the enum grows; a missing
`SemanticEntry.phrase` is a construction-time `TypeError` (SE-07-003). Only
`{actor}`, `{object}` and `{target}` are ever filled. See
[`notes/activitystreams-semantics.md`](../../notes/activitystreams-semantics.md)
§ "Event-Phrase Lookups". (CONCERN-1675)

### Docker Compose Service Names Are Not Actor Names

Service names in `docker/docker-compose-multi-actor.yml` are compose routing
labels, not CVD roles — a service named `vendor` need not house a Vendor actor.
Reuse the existing four services with role-alias `VULTRON_*_BASE_URL` bindings
rather than adding services to get a new actor name; this keeps the CI startup
count constant. See
[`notes/demo-scenario-authoring.md`](../../notes/demo-scenario-authoring.md)
§ "Docker Compose Service Names Are Not Actor Names". (ISSUE-1216, ISSUE-1786)

### Exchange Demos: Discover the Canonical Case from the DataLayer

After `validate-report`, the BT fires `ProposeReportCaseToActorNode` and the
CaseActor creates the **canonical** `VulnerabilityCase` (ADR-0041). Do NOT call
`create_case_activity` in exchange demo setup — that makes a second, vendor-local
case with no `ReportCaseLink` and no participants. Find the canonical case by
scanning `GET /datalayer/VulnerabilityCases/` for the entry with
`case_participants` populated. See
[`notes/case-proposal.md`](../../notes/case-proposal.md) § "Exchange Demo:
Discovering the Canonical Case". (ISSUE-1994)

### The Ledger Dump Belongs in the Failure Path, Not After the Last Phase

Forensic artifacts matter most in the run that fails, so a dump placed after the
last phase never runs when it counts (#2239: `devlogs/` empty, invariant harness
dead on artifact download).

- Wrap the whole body of `run_<name>_demo()` in
  `with scenario_harness("<demo-name>") as harness:` — it resets the accumulator,
  always dumps on the way out, and calls `assert_demo_success()` last.
- Register the dump as soon as a case exists:
  `harness.dump_with(lambda: _phase_dump_case_ledgers(...))`.
- Do not re-add `try/finally: assert_demo_success()` in `main()` — a second owner
  of the accumulator asserts before the dump runs.
- Keep `_phase_dump_case_ledgers` thin; delegate to
  `helpers.ledger_dump.dump_case_ledgers()`. The manifest is not optional, and a
  dump failure must never replace the scenario's exception.

DEMOCI-10, DEMOMA-23, and
[`notes/demo-ci-invariants.md`](../../notes/demo-ci-invariants.md). (ISSUE-2239)

### Demo Devlog Race: Wait for Replica Before Dumping

After any phase that commits a new canonical ledger entry, poll until the replica
acknowledges the sender's tail hash before writing the devlog — otherwise the
dump misses entries still in `Announce(CaseLedgerEntry)` fan-out. Pattern in
[`notes/demo-ci-diagnostics.md`](../../notes/demo-ci-diagnostics.md) § "Demo
Devlog Race". (DEMO-DEVLOG-RACE)

### BT Demo `main()` Must Be Callable With No Arguments

`[project.scripts]` entry points call `main()` with no arguments. Use
`def main(args=None)` and fall back to `_parse_args()` when `args is None`, so
both the console script and `cli.py`'s click sub-group work. Test the real
console script with `PYTHONPATH= uv run <script>`. See
[`notes/demo-scenario-authoring.md`](../../notes/demo-scenario-authoring.md)
§ "BT Demo `main()`". (ISSUE-1568)

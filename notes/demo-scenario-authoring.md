---
title: Demo Scenario Authoring Rules
status: active
description: >
  How to write a multi-actor demo scenario without faking the protocol:
  puppeteer actors through trigger endpoints rather than spoofing via inbox
  injection, never carry one actor's mail to another's inbox, extract helpers
  before the second use, keep console-script entry points callable with no
  arguments, and treat docker service names as routing labels rather than actor
  identities.
related_specs:
  - specs/multi-actor-demo.yaml
  - specs/event-driven-control-flow.yaml
  - specs/code-style.yaml
related_notes:
  - notes/event-driven-control-flow.md
  - notes/demo-ci-diagnostics.md
  - notes/demo-ci-invariants.md
  - notes/fv-demo.md
  - notes/case-proposal.md
  - notes/ownership-transfer.md
  - notes/devcontainer-tooling.md
relevant_packages:
  - vultron/demo
---

# Demo Scenario Authoring Rules

Migrated out of `vultron/demo/AGENTS.md`, which keeps the one-line rules and
points here for the reasoning and examples.

The through-line: a demo exists to prove the protocol works. Every shortcut that
makes a scenario pass by doing the protocol's job *for* it converts the demo from
evidence into decoration.

---

## Puppeteer Actors via Trigger Endpoints, Never Spoof via Inbox Injection

Always drive actor behavior through **real HTTP trigger endpoints** (e.g.
`POST /{actor_id}/trigger/accept-actor-recommendation`). Never construct and POST
activities directly to actor inboxes to fake an approval or state change.

**Why:** Inbox injection bypasses the BT evaluation layer entirely and creates
demos that exercise the wrong code path. The distinction:

- **Puppeteering** = sending a trigger that causes the actor to decide and act
  (validates the behavior tree path)
- **Spoofing** = forging the resulting activity as if the actor had already
  decided (skips the BT entirely)

**How to apply:** Before writing any demo step where one actor "responds" to
another, check whether the trigger endpoint for that response exists. If it
doesn't, implement the full hexagonal stack (trigger endpoint → service layer →
BT) first, then write the demo step. Working around a missing endpoint by
injecting the response directly means the demo proves nothing about the actual
behavior tree path.

See also [notes/fv-demo.md](fv-demo.md) § "Puppeteering Constraint".

Source: ISSUE-1535

---

## Never Carry One Actor's Mail to Another Actor's Inbox

Scenario demos MUST NOT POST an activity to an actor's inbox on behalf of another
actor. This includes helper functions such as `post_to_inbox_and_wait`.

**Why:** Delivering an activity to an inbox is the transport layer's job, not the
demo's. When a demo calls
`post_to_inbox_and_wait(vendor_client, vendor_id, invite)` it is acting as a
surrogate mail carrier — putting a message into Vendor's inbox as if it arrived
from the network. This is a form of spoofing: the real
outbox→delivery→inbox path is never exercised, so demo CI proves nothing about
whether the protocol actually works end-to-end.

The distinction that matters:

- **Triggering** = POST to an actor's *trigger endpoint* to cause it to emit an
  activity (`POST /actors/{id}/trigger/invite-actor-to-case`). The actor decides
  and sends. Correct.
- **Mail-carrying** = POST an activity directly to another actor's *inbox* from
  outside that actor's own delivery path (`POST /actors/{id}/inbox/`). The demo
  bypasses the real transport. Wrong.

**Root cause of the pattern:** The inbox endpoint returns 202 immediately
(`BackgroundTasks`) before the activity is fully processed. Naive polling after a
trigger timed out, so mail-carrying was added as a workaround.

The fix is not a longer timeout — it is observing the *right thing*. Choose the
observable per EDF-06-002 and EDF-06-003 (the committed state of the actor that
produces the effect, read from its own container) and express it with
`demo_gate`. See [notes/event-driven-control-flow.md](event-driven-control-flow.md)
§ "Temporal Sequence vs. Causal Sequence".

**How to apply:**

1. After triggering an actor to emit an activity, do **not** manually deliver
   that activity to any inbox. Poll the expected side-effect directly:
   - `wait_for_case_on_container` — a case replica arrived.
   - `find_case_invite_for_actor` — an invite arrived.
   - `wait_for_object_stored` — an arbitrary object arrived in a DataLayer.
2. If a poll times out reliably in CI, the underlying delivery path needs
   investigation (retry parameters, health checks, container startup order) — not
   a workaround in the demo script.

**Scope — scenario demos, not exchange demos.** `vultron/demo/exchange/` drives a
single backend directly and uses `post_to_inbox_and_wait` as its normal
mechanism; there is no second container for the transport to cross. This rule
governs `vultron/demo/scenario/`, where actors live in separate containers and
the delivery path is the thing under test.

**Retired exception — ownership-transfer self-delivery.** CONCERN-1653 previously
carved out an exception for an actor self-delivering to its *own* inbox after
`accept-case-ownership-transfer`. That workaround no longer exists: under
ADR-0053 the Accept routes through the CaseActor and reaches every replica
automatically. See [notes/ownership-transfer.md](ownership-transfer.md)
§ "Retired Demo Workaround: Accept Self-Delivery".

Source: CONCERN-1635, amended by CONCERN-2181

---

## Extract Before Reuse: No Copy-Paste from Existing Scenario Files

Before writing a **second use** of a pattern from an existing scenario file,
extract it to `vultron/demo/helpers/` first. Do not copy-paste a function body, a
polling loop, a verification block, or any other logical unit from an existing
scenario file into a new one.

**Why:** Every demo scenario written by copying the previous one propagates
latent bugs alongside valid patterns. Issue #1632 documented residual duplication
remaining after PR #1629 reactively extracted five helper modules. Copy-paste is
the root cause; extraction-first prevents the problem from recurring.

**How to apply:**

1. Before writing a new scenario step, grep `vultron/demo/helpers/` for an
   existing helper that covers the same pattern.
2. If one exists, import and call it. Do not inline a copy.
3. If none exists and this is the second occurrence of the pattern, extract it to
   the appropriate `helpers/` module first, then call it from both places.
4. A pattern that appears only once may stay inline, but add a comment marking it
   as a candidate for extraction when a second use arises.

This rule applies to scenario files in `vultron/demo/scenario/`. Exchange demos
under `vultron/demo/exchange/` are lower-level and may duplicate less when a full
helper would add more abstraction than value.

Normative: `specs/multi-actor-demo.yaml` DEMOMA-17-001 — a MUST-level
specialisation of the project-wide SHOULD rule CS-22-001 in
`specs/code-style.yaml`.

Source: ISSUE-1652

---

## BT Demo `main()` Must Be Callable With No Arguments

`[project.scripts]` entry points invoke `main()` with **no arguments**. Demo
modules that define `def main(args):` — where `args` is a required positional
parsed by an `if __name__ == "__main__"` block — fail immediately with
`TypeError: main() missing 1 required positional argument` when invoked via
`uv run <script>`.

**Fix:** give `main` an `args=None` default and fall back to `_parse_args()`:

```python
def main(args=None) -> None:
    if args is None:
        args = _parse_args()
    ...
```

This preserves the path used by `vultron/demo/cli.py`'s click sub-group (which
passes a `SimpleNamespace` via `_bt_args()`) while also being callable with zero
arguments from a console script.

**Always test the actual console script** (`PYTHONPATH= uv run <script>`) — not
just the module import — and clear the devcontainer's `PYTHONPATH=/app`
contamination. See [notes/devcontainer-tooling.md](devcontainer-tooling.md).

Source: ISSUE-1568

---

## Docker Compose Service Names Are Not Actor Names

The service names in `docker/docker-compose-multi-actor.yml` (`vendor`,
`coordinator`, `vendor2`, `case-actor`) were chosen to match the roles in the
first demo scenarios and do not need to match the CVD actor roles housed within
them. When designing a new multi-actor scenario:

- The **service name** is a docker-compose routing label. Reuse existing service
  names by remapping them to new semantic roles via `--env-file` or environment
  variable overrides — there is no requirement that a service named `vendor`
  contains a Vendor actor.
- The **actor name** (`VULTRON_*_BASE_URL` env var bindings, actor IDs seeded at
  startup) is the meaningful identity. Choose actor names to reflect their CVD
  role in the scenario, not the docker service name.
- Avoid adding new services just to get a new actor name. In multi-actor
  scenarios (FCCV, FVCV-handoff), the existing four services are reused with
  role-alias environment variable bindings; this keeps the CI service startup
  count constant.

**Future direction**: the service names may eventually be renamed to neutral
labels (`actor1`–`actor4`) so the compose file is scenario-agnostic (ISSUE-1786).
Until then, use the existing services with role-alias bindings.

Source: ISSUE-1216, plan/incoming/learnings/20260722-fccv-handoff-container-remapping.md

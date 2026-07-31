# AGENTS.md — vultron/demo/

> For project-wide conventions see the root [AGENTS.md](../../AGENTS.md).
> This file covers rules specific to demo scripts and multi-actor scenario code.

---

## Common Pitfalls — demo layer

### Puppeteer Actors via Trigger Endpoints, Never Spoof via Inbox Injection

When building multi-actor demo scripts, always drive actor behavior through
**real HTTP trigger endpoints** (e.g., `POST /{actor_id}/trigger/accept-actor-recommendation`).
Never construct and POST activities directly to actor inboxes to fake an
approval or state change.

**Why:** Inbox injection bypasses the BT evaluation layer entirely and creates
demos that exercise the wrong code path. The distinction:

- **Puppeteering** = sending a trigger that causes the actor to decide and act
  (validates the behavior tree path)
- **Spoofing** = forging the resulting activity as if the actor had already
  decided (skips the BT entirely)

**How to apply:** Before writing any demo step where one actor "responds" to
another, check whether the trigger endpoint for that response exists. If it
doesn't, implement the full hexagonal stack (trigger endpoint → service layer
→ BT) first, then write the demo step. Working around a missing endpoint by
injecting the response directly means the demo proves nothing about the
actual behavior tree path.

<!-- Source: ISSUE-1535 -->

---

### BT Demo `main()` Must Be Callable With No Arguments (Console-Script Entry Points)

`[project.scripts]` entry points invoke `main()` with **no arguments**. Demo
modules that define `def main(args):` — where `args` is a required positional
parsed by an `if __name__ == "__main__"` block — will fail immediately with
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
passes a `SimpleNamespace` via `_bt_args()`) while also being callable with
zero arguments from a console script.

**Always test the actual console script** (`PYTHONPATH= uv run <script>`) — not
just the module import — and clear `PYTHONPATH=/app` devcontainer contamination
(see root `AGENTS.md` § "PYTHONPATH=/app contaminates imports").

<!-- Source: ISSUE-1568 -->

---

### Extract Before Reuse: No Copy-Paste from Existing Scenario Files

Before writing a **second use** of a pattern from an existing scenario file,
extract it to `vultron/demo/helpers/` first. Do not copy-paste a function body,
a polling loop, a verification block, or any other logical unit from an
existing scenario file into a new one.

**Why:** Every demo scenario written by copying the previous one propagates
latent bugs alongside valid patterns. Issue #1632 documented residual
duplication remaining after PR #1629 reactively extracted five helper modules.
Copy-paste is the root cause; extraction-first prevents the problem from
recurring.

**How to apply:**

1. Before writing a new scenario step, grep `vultron/demo/helpers/` for an
   existing helper that covers the same pattern.
2. If one exists, import and call it. Do not inline a copy.
3. If none exists and this is the second occurrence of the pattern, extract it
   to the appropriate `helpers/` module first, then call it from both places.
4. A pattern that appears only once may stay inline, but add a comment marking
   it as a candidate for extraction when a second use arises.

This rule applies to scenario files in `vultron/demo/scenario/`. Exchange demos
under `vultron/demo/exchange/` are lower-level and may duplicate less when a
full helper would add more abstraction than value.

See `specs/multi-actor-demo.yaml` DEMOMA-17-001 for the normative requirement
(a MUST-level specialisation of the project-wide SHOULD rule CS-22-001 in
`specs/code-style.yaml`).

<!-- Source: ISSUE-1652 -->

---

### Ownership-Transfer Trigger: Always Self-Deliver the Accept to the Accepting Actor's Inbox

When the accepting actor triggers `accept-case-ownership-transfer`, the
trigger-side BT (`AcceptCaseOwnershipTransferTriggerBT`) queues the
`Accept(Offer(VulnerabilityCase))` activity addressed only to the **offering**
actor. The accepting actor's own DataLayer replica is therefore **not** updated
by that path.

After queuing the trigger, the demo script **MUST** also POST the Accept
activity to the accepting actor's own inbox so that
`AcceptCaseOwnershipTransferReceivedUseCase` runs locally and updates
`case.attributed_to` on the accepting actor's replica.

```python
# ✅ Correct — trigger first, then self-deliver
accept_result = post_to_trigger(
    client=accepting_client,
    actor_id=accepting_actor_id,
    behavior="accept-case-ownership-transfer",
    body={"offer_id": offer_id},
)
accept_activity = as_TransitiveActivity.model_validate(accept_result["activity"])
post_to_inbox_and_wait(accepting_client, accepting_participant_id, accept_activity)

# ❌ Wrong — skips local replica update; attributed_to never changes on accepting actor
accept_result = post_to_trigger(
    client=accepting_client,
    actor_id=accepting_actor_id,
    behavior="accept-case-ownership-transfer",
    body={"offer_id": offer_id},
)
# missing: extract accept_activity and post_to_inbox_and_wait(...)
```

**Why:** PR #1590 silently deleted this self-delivery step in a commit that
appeared to only change a field accessor. The omission only surfaced under
the CI integration test — functional tests passed because the offering actor's
replica updated correctly via the normal outbox delivery path. The demo CI
integration tests (`test/ci/invariants/`) are the authoritative runtime
enforcement for this invariant.

See `vultron/demo/scenario/fvcv_handoff_demo.py` and
`vultron/demo/scenario/fccv_handoff_demo.py` for the correct pattern.

<!-- Source: CONCERN-1653 -->

---

### Never Carry One Actor's Mail to Another Actor's Inbox

Demo scripts MUST NOT POST an activity to an actor's inbox on behalf of
another actor. This includes helper functions such as `post_to_inbox_and_wait`.

**Why:** Delivering an activity to an inbox is the transport layer's job, not
the demo's. When a demo calls `post_to_inbox_and_wait(vendor_client, vendor_id,
invite)` it is acting as a surrogate mail carrier — putting a message into
Vendor's inbox as if it arrived from the network. This is a form of spoofing:
the real outbox→delivery→inbox path is never exercised, so demo CI proves
nothing about whether the protocol actually works end-to-end.

The distinction that matters:

- **Triggering** = POST to an actor's *trigger endpoint* to cause it to emit
  an activity (`POST /actors/{id}/trigger/invite-actor-to-case`). The actor
  decides and sends. Correct.
- **Mail-carrying** = POST an activity directly to another actor's *inbox*
  from outside that actor's own delivery path (`POST /actors/{id}/inbox/`).
  The demo bypasses the real transport. Wrong.

**Root cause of the pattern:** The inbox endpoint returns 202 immediately
(`BackgroundTasks`) before the activity is fully processed. Naive polling
after a trigger timed out, so mail-carrying was added as a workaround. The
correct fix is to use a polling helper with a sufficient timeout — the real
HTTP delivery path (`HttpDeliveryAdapter`) with its retry/backoff will
complete; the demo just needs to wait long enough.

**How to apply:**

1. After triggering an actor to emit an activity, do **not** manually deliver
   that activity to any inbox. Instead, poll the expected side-effect directly:
   - Use `wait_for_case_on_container` to verify a case replica arrived.
   - Use `find_case_invite_for_actor` to verify an invite arrived.
   - Use `wait_for_object_stored` to verify an arbitrary object arrived in a DataLayer.
2. If a poll times out reliably in CI, the underlying delivery path needs
   investigation (retry parameters, health checks, container startup order)
   — not a workaround in the demo script.

**Exception — self-delivery (CONCERN-1653):** A demo script MAY call
`post_to_inbox_and_wait` when an actor needs to deliver an activity to its
*own* inbox to update its own replica — for example, after triggering
`accept-case-ownership-transfer`, the accepting actor must self-deliver the
resulting `Accept` activity so that `AcceptCaseOwnershipTransferReceivedUseCase`
runs locally. This is not mail-carrying: the actor is posting to its own inbox,
not acting as a surrogate for the transport layer.

The rule this section prohibits is **cross-actor delivery**: a demo using
*Actor A's* credentials to POST a message into *Actor B's* inbox. That is the
pattern to eliminate; CONCERN-1653's self-delivery pattern is orthogonal and
remains correct.

<!-- Source: CONCERN-1635 -->

---

### Event-Phrase Lookups MUST Use `lookup_entry()`, Not a Local Phrase Dict

Any display-layer code that maps a `MessageSemantics` value to a human-readable
phrase MUST use `lookup_entry(semantics).phrase` from
`vultron.semantic_registry`, not a local `dict[str, str]` parallel table.

**Why:** A local dict keyed by `MessageSemantics` values will silently drift
as new semantics are added to the enum. `SemanticEntry.phrase` is mandatory
(SE-07-003), so a missing phrase is a `TypeError` at registry construction
time — not a silent fallback at render time.

**How to apply:** Import `from vultron.semantic_registry import lookup_entry`
and render with `lookup_entry(semantics).phrase.format_map(defaultdict(lambda: "—", slots))`.
Use the fallback humanizer (`event_type.replace("_", " ")`) only for event
types not in the registry (e.g., data from a future protocol version).

<!-- Source: CONCERN-1675 -->

---

### Docker Compose Service Names Are Not Actor Names

The service names in `docker/docker-compose-multi-actor.yml` (`vendor`,
`coordinator`, `vendor2`, `case-actor`) were chosen to match the roles in the
first demo scenarios and do not need to match the CVD actor roles housed
within them. When designing a new multi-actor scenario:

- The **service name** is a docker-compose routing label. Reuse existing
  service names by remapping them to new semantic roles via `--env-file` or
  environment variable overrides — there is no requirement that a service
  named `vendor` contains a Vendor actor.
- The **actor name** (`VULTRON_*_BASE_URL` env var bindings, actor IDs seeded
  at startup) is the meaningful identity. Choose actor names to reflect their
  CVD role in the scenario, not the docker service name.
- Avoid adding new services just to get a new actor name. In multi-actor
  scenarios (FCCV, FVCV-handoff), the existing four services are reused with
  role-alias environment variable bindings; this keeps the CI service
  startup count constant.

**Future direction**: the service names may eventually be renamed to neutral
labels (`actor1`–`actor4`) so the compose file is scenario-agnostic. Until
then, use the existing services with role-alias bindings.

<!-- Source: ISSUE-1216, plan/incoming/learnings/20260722-fccv-handoff-container-remapping.md -->

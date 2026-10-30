---
description: >
  Run any of the multi-actor demo scenarios, from the two-party Reporter + Vendor
  (rv) baseline to the five-party coordination cases, across isolated
  participant containers with Docker Compose.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 300
page_type: tutorial
subject: implementation
---

# Tutorial: Running the Multi-Actor Container Demos

In this tutorial, we will run a multi-actor demo scenario end to end with Docker Compose.
By the end of this tutorial, we will have:

- started a fleet of isolated Vultron actor containers, each representing a distinct Coordinated Vulnerability Disclosure (CVD) participant,
- chosen a scenario and watched its actors exchange messages across container boundaries, and
- read the structured output that tells us which step ran, which check passed, and which causal gate held.

!!! info "What we will learn"

    These scenarios use **trigger-based puppeteering**.
    The demo runner calls trigger endpoints on each actor's own container, so each actor's behavior tree and outbox logic run end to end.
    Each actor makes its own decisions, and activities flow from the sender's outbox to the receiver's inbox over HTTP across the Docker network.
    No messages are injected by hand.
    This is the full Vultron Protocol in action, not a simulation.

---

## Prerequisites

You need the following tools installed before we begin:

{% include-markdown "./_docker_prerequisites.md" %}

You do **not** need Python installed locally; the containers include everything required.

---

## Step 1 — Clone the repository

First, let's get a local copy of the Vultron project:

```bash
git clone https://github.com/CERTCC/Vultron.git
cd Vultron
```

!!! tip

    If you already have a local clone, `cd` into the repository root and run `git pull` to make sure you are up to date.

---

## Step 2 — Create the environment file

Before running any `docker compose` command, create a local `.env` file from the provided example:

```bash
cp docker/.env.example docker/.env
```

This sets the Docker Compose project name, which the container, network, and volume names are derived from.

---

## Step 3 — Choose a scenario

Every scenario is selected by the `DEMO` environment variable.
The table below is rendered from the scenario registry at build time, so the `DEMO` values it lists are exactly the ones the demo runner accepts.

```python exec="true" idprefix=""
from vultron.metadata.demo_scenarios.render import render_page

print(render_page("container_demos"))
```

Each scenario is self-contained.
The demo runner resets every container's state, seeds the actor records and their peer registrations, runs the workflow, verifies the final state, and exits.
The [Demo Scenario Narratives](../topics/scenarios/index.md) explain what each scenario demonstrates and why its steps happen in the order they do.

### The cast

Every scenario runs on the same containers, called the cast.
Their names say nothing about CVD roles, because one container plays different parts in different scenarios.

| Container | Part it plays |
|:----------|:--------------|
| `actor0` | The first Reporter the scenario seats, in every scenario |
| `actor1` | The first Vendor the scenario seats, in every scenario |
| `actor2` | The first Coordinator the scenario seats, in every scenario |
| `actor3` | A second Vendor in `rvv`, `rvcv-*` and `rcvv-embargo`; a second Coordinator in `rccv-*` |
| `actor4` | The Vendor that is also a Deployer, in `rcvcv` |
| `case-actor` | The Case Actor, which manages each case and holds its canonical ledger |

The first three containers always play the same part, so `actor2` is the Coordinator that receives the report in `rcv` and the Coordinator that owns the case in `rcvcv`.
A scenario that seats no Coordinator leaves `actor2` idle: `rv` runs a Reporter and a Vendor only.

`actor3` and `actor4` are character actors.
Their CVD role comes from the act that brings them into the case — the role the invitation offers them — and not from any container setting.
That is why one container can be a Vendor in one scenario and a Coordinator in another.

Fixing the cast this way lets any pair of scenarios that start the same way record the same bytes for their shared opening.
That is how the demo tooling proves a branch point is the only place a pair of them differ.

---

## Step 4 — Run the scenario

From the repository root, run the compose stack with `DEMO` set to the value you chose:

```bash
DEMO=rcv docker compose -f docker/docker-compose-multi-actor.yml \
    up --abort-on-container-exit --exit-code-from demo-runner
```

If you leave `DEMO` unset, the runner executes the `rv` scenario.
[Run the `rv` Demo](rv-demo.md) walks through that run milestone by milestone.

{% include-markdown "./_first_run_build.md" %}
Once the images exist, compose:

1. starts the whole cast (`actor0` through `actor4`, and `case-actor`), whether or not the chosen scenario uses every container,
2. waits until every actor container passes its `/health/ready` probe,
3. starts `demo-runner`, which resets state, seeds actors, drives the workflow, verifies each milestone, and exits, and
4. stops the whole stack when `demo-runner` exits, propagating its exit code.

Every scenario uses `case-actor`: it hosts the Case Actor that manages each case and holds its canonical ledger.

!!! success "Success indicator"

    Every scenario ends with its own banner, `<SCENARIO> DEMO COMPLETE ✓`, followed by a note on what it demonstrated.
    A default `rv` run, for example, ends with:

    ```text
    rv DEMO COMPLETE ✓  (VFDPxa full lifecycle)
    ```

    A non-zero exit code from `demo-runner` means a step or check failed; see Step 5.

---

## Step 5 — Read the output

Each step of a scenario is wrapped in a `demo_step`, `demo_check`, or `demo_gate` context manager that prints a structured lifecycle marker:

| Symbol | Meaning                                                    |
|:-------|:-----------------------------------------------------------|
| 🚥    | A workflow step has started                                |
| 🟢    | The step completed successfully                            |
| 🔴    | The step raised an exception                               |
| 📋    | A verification check has started                           |
| ✅    | The verification check passed                              |
| ❌    | The verification check failed                              |
| 🚧    | A causal gate (a precondition for later steps) has started |
| 🔓    | The gate's precondition held                               |
| 🔒    | The gate failed; the steps that depend on it were skipped  |

Watch for `🔴`, `❌`, and `🔒` markers to diagnose a failure.
A gate waits for evidence that an earlier step's effect has been committed by the actor that owns it, rather than for a fixed delay, so a `🔒` names the protocol effect that never arrived.

To examine the logs of one container after a run:

```bash
docker compose -f docker/docker-compose-multi-actor.yml logs actor1
```

To watch one actor's [case ledger](../reference/vultron-spec/introduction.md#23-protocol-objects-and-messages) while a scenario runs, tail its ledger stream.
Look up the host port Docker assigned to the actor's container, then open the stream with the case's id:

```bash
docker compose -f docker/docker-compose-multi-actor.yml port actor1 7999
curl -N "http://localhost:<port>/api/v2/actors/actor1/demo/cases/<case-id>/log/stream"
```

The stream first replays every ledger entry the actor holds for that case, then sends each new entry as the actor records it.
Each event's `id:` is the entry's `logIndex`, and its `data:` is the entry as JavaScript Object Notation (JSON), the same form `…/log` returns.
Add `?since=<logIndex>` to skip the entries you have already seen.
When the server shuts down, the stream sends a final `event: close`.
The stream and the `…/log` endpoints exist only in prototype mode, and they are demo tooling: participants never use them to replicate a ledger.

---

## Step 6 — Clean up

{% include-markdown "./_cleanup_volumes.md" %}

---

## Running scenarios from the integration test script

The integration test script builds the images, runs one scenario, checks the exit code, and removes all volumes automatically:

```bash
# From the repository root:
./integration_tests/demo/run_multi_actor_integration_test.sh rv
./integration_tests/demo/run_multi_actor_integration_test.sh rcv
./integration_tests/demo/run_multi_actor_integration_test.sh rvcv-handoff
```

A passing run ends with the script's own summary line:

```text
[multi-actor-integration] SUCCESS: scenario 'rv' passed.
```

!!! tip

    The integration test script uses `PROJECT_NAME=vultron-it` by default so its containers do not conflict with a running development stack.
    Override `PROJECT_NAME` to run scenarios in parallel:

    ```bash
    PROJECT_NAME=vultron-it-two   DEMO=rv   \
        ./integration_tests/demo/run_multi_actor_integration_test.sh
    PROJECT_NAME=vultron-it-three DEMO=rcv \
        ./integration_tests/demo/run_multi_actor_integration_test.sh
    ```

---

## What we accomplished

We have:

- started a multi-container Vultron stack and run a multi-actor CVD workflow across isolated participant containers,
- observed trigger-based puppeteering, where each actor's own behavior tree and outbox logic drive the workflow end to end, and
- read the step, check, and gate markers that show what the protocol did at each stage.

---

## Next steps

- **Follow one run in detail** — [Run the `rv` Demo](rv-demo.md) explains each phase and milestone of the default scenario.
- **Understand what each scenario shows** — the [Demo Scenario Narratives](../topics/scenarios/index.md) describe every scenario's case in CVD terms, step by step.
- **Read the message-level trace** — the [`rv` Demo Protocol Reference](../reference/rv-demo-protocol.md) lists every activity the `rv` run exchanges and the ledger entries it produces.
- **Explore the single-container demos** — see [Run the Receive-Report Demo](receive_report_demo.md) and [Running the Other Demos](other_demos.md) to step through individual protocol exchanges.
- **Read the scenario source** — the scripts are in `vultron/demo/scenario/`; the shared helpers are in `vultron/demo/helpers/`.
- **Consult the Docker README** — `docker/README.md` documents port mappings, environment variable overrides, and manual seed commands for debugging individual containers.

{% include-markdown "../start/_paths/contribute/tutorials__container_demos.md" %}

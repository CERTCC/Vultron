---
description: >
  Run any of the multi-actor demo scenarios, from the two-party Finder + Vendor
  (FV) baseline to the five-party coordination cases, across isolated
  participant containers with Docker Compose.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 300
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

- [Docker](https://docs.docker.com/get-docker/){:target="_blank"} (version 20.10 or later)
- [Docker Compose](https://docs.docker.com/compose/install/){:target="_blank"} (version 2.x; included with Docker Desktop)
- Git (to clone the repository)

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

---

## Step 4 — Run the scenario

From the repository root, run the compose stack with `DEMO` set to the value you chose:

```bash
DEMO=fcv docker compose -f docker/docker-compose-multi-actor.yml \
    up --abort-on-container-exit --exit-code-from demo-runner
```

If you leave `DEMO` unset, the runner executes the `fv` scenario.
[Run the FV Demo](fv-demo.md) walks through that run milestone by milestone.

Docker builds the images on the first run, which takes a few minutes.
Subsequent runs reuse the cached images and start immediately.
Once the images exist, compose:

1. starts the actor containers (`finder`, `vendor`, `coordinator`, `case-actor`, `actor5`, and `actor6`), whether or not the chosen scenario uses them all,
2. waits until every actor container passes its `/health/ready` probe,
3. starts `demo-runner`, which resets state, seeds actors, drives the workflow, verifies each milestone, and exits, and
4. stops the whole stack when `demo-runner` exits, propagating its exit code.

!!! success "Success indicator"

    Every scenario ends with its own banner, `<SCENARIO> DEMO COMPLETE ✓`, followed by a note on what it demonstrated.
    A default `fv` run, for example, ends with:

    ```text
    FV DEMO COMPLETE ✓  (VFDPxa full lifecycle)
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
docker compose -f docker/docker-compose-multi-actor.yml logs vendor
```

---

## Step 6 — Clean up

Named Docker volumes persist the SQLite databases between runs.
Remove all volumes after a session to start fresh next time:

```bash
docker compose -f docker/docker-compose-multi-actor.yml down -v
```

---

## Running scenarios from the integration test script

The integration test script builds the images, runs one scenario, checks the exit code, and removes all volumes automatically:

```bash
# From the repository root:
./integration_tests/demo/run_multi_actor_integration_test.sh fv
./integration_tests/demo/run_multi_actor_integration_test.sh fcv
./integration_tests/demo/run_multi_actor_integration_test.sh fvcv-handoff
```

A passing run ends with the script's own summary line:

```text
[multi-actor-integration] SUCCESS: scenario 'fv' passed.
```

!!! tip

    The integration test script uses `PROJECT_NAME=vultron-it` by default so its containers do not conflict with a running development stack.
    Override `PROJECT_NAME` to run scenarios in parallel:

    ```bash
    PROJECT_NAME=vultron-it-two   DEMO=fv   \
        ./integration_tests/demo/run_multi_actor_integration_test.sh
    PROJECT_NAME=vultron-it-three DEMO=fcv \
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

- **Follow one run in detail** — [Run the FV Demo](fv-demo.md) explains each phase and milestone of the default scenario.
- **Understand what each scenario shows** — the [Demo Scenario Narratives](../topics/scenarios/index.md) describe every scenario's case in CVD terms, step by step.
- **Read the message-level trace** — the [FV Demo Protocol Reference](../reference/fv-demo-protocol.md) lists every activity the FV run exchanges and the ledger entries it produces.
- **Explore the single-container demos** — see [Run the Receive-Report Demo](receive_report_demo.md) and [Running the Other Demos](other_demos.md) to step through individual protocol exchanges.
- **Read the scenario source** — the scripts are in `vultron/demo/scenario/`; the shared helpers are in `vultron/demo/helpers/`.
- **Consult the Docker README** — `docker/README.md` documents port mappings, environment variable overrides, and manual seed commands for debugging individual containers.

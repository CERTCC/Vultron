# Tutorial: Running the Multi-Actor Container Demos

In this tutorial, we will run the three multi-actor container demo scenarios
end-to-end using Docker Compose. By the end of this tutorial, we will have:

- started a fleet of isolated Vultron API containers, each representing a
  distinct CVD participant,
- watched those actors exchange vulnerability-disclosure messages
  automatically across container boundaries, and
- observed how the Vultron Protocol handles two-party, three-party, and
  multi-vendor coordination workflows.

!!! info "What we will learn"

    These scenarios use **trigger-based puppeteering** — the demo runner
    calls trigger endpoints on each actor's own container so that the actor's
    behavior tree and outbox logic are exercised end-to-end. Each actor makes
    its own decisions; activities flow from sender outbox to receiver inbox
    over HTTP across the Docker network. No messages are injected manually.
    This is the full Vultron Protocol in action, not a simulation.

---

## Prerequisites

We need the following tools installed before we begin:

- [Docker](https://docs.docker.com/get-docker/){:target="_blank"} (version
  20.10 or later)
- [Docker Compose](https://docs.docker.com/compose/install/){:target="_blank"}
  (version 2.x; included with Docker Desktop)
- Git (to clone the repository)

We do **not** need Python installed locally; the containers include everything
required.

---

## The three scenarios

| Scenario       | DEMO value     | Actors                                               |
|:---------------|:---------------|:-----------------------------------------------------|
| Two-actor      | `two-actor`    | Finder + Vendor + CaseActor                          |
| Three-actor    | `three-actor`  | Finder + Vendor + Coordinator + CaseActor            |
| Multi-vendor   | `multi-vendor` | Finder + Vendor + Coordinator + Vendor2 + CaseActor  |

Each scenario is self-contained: the demo runner resets all container state,
seeds actor records and peer registrations, runs the workflow, verifies final
state, and exits.

---

## Step 1 — Clone the repository

First, let's get a local copy of the Vultron project:

```bash
git clone https://github.com/CERTCC/Vultron.git
cd Vultron
```

!!! tip

    If you already have a local clone, `cd` into the repository root and run
    `git pull` to make sure you are up to date.

---

## Step 2 — Run the two-actor scenario

The **two-actor** scenario (D5-2) is the simplest: a Finder discovers a
vulnerability and submits a report to a Vendor, who validates it, engages the
case, adds the Finder as a participant, and exchanges notes with them. The
CaseActor is co-located in the Vendor container.

From the repository root, run:

```bash
docker compose -f docker/docker-compose-multi-actor.yml \
    up --abort-on-container-exit demo-runner
```

Docker builds the images on the first run (this takes a few minutes) and then:

1. Starts `finder`, `vendor`, `coordinator`, `case-actor`, and `vendor2`
   containers (all five are defined in the compose file; only `finder` and
   `vendor` participate in this scenario).
2. Waits until every container passes its `/health/ready` probe.
3. Starts `demo-runner`, which resets state, seeds actors, runs the workflow,
   verifies the result, and exits.

A successful run ends with:

```text
[multi-actor-integration] SUCCESS: scenario 'two-actor' passed.
```

### What the two-actor demo does

| Step | Actor     | Action                                               |
|:-----|:----------|:-----------------------------------------------------|
| 1    | Finder    | Submits a `VulnerabilityReport` to Vendor's inbox    |
| 2    | Vendor    | Validates the report (trigger: `validate-report`)    |
| 3    | Vendor    | Case engagement cascades automatically (RM → ACCEPTED)|
| 4    | Vendor    | Adds Finder as a case participant                    |
| 5    | Finder    | Posts a question note to the case                    |
| 6    | Vendor    | Replies; case forwards reply to Finder's inbox       |
| ✅   | Vendor    | Case DataLayer holds 2 participants and 2 notes      |

---

## Step 3 — Run the three-actor scenario

The **three-actor** scenario (D5-3) adds a dedicated Coordinator and a
separate CaseActor container. The Coordinator acts as the authoritative case
manager, inviting participants and negotiating an embargo.

```bash
DEMO=three-actor docker compose -f docker/docker-compose-multi-actor.yml \
    up --abort-on-container-exit demo-runner
```

### What the three-actor demo does

| Step | Actor       | Action                                               |
|:-----|:------------|:-----------------------------------------------------|
| 1    | Finder      | Submits a report to Coordinator's inbox              |
| 2    | Coordinator | Creates the authoritative case on CaseActor          |
| 3    | Coordinator | Adds the report to the case                          |
| 4    | Coordinator | Invites Finder; Finder accepts                       |
| 5    | Coordinator | Proposes an embargo; Finder accepts                  |
| 6    | Coordinator | Invites Vendor; Vendor accepts                       |
| 7    | Vendor      | Accepts the active embargo                           |
| ✅   | CaseActor   | Case holds 3 participants; embargo EM state = ACTIVE |

---

## Step 4 — Run the multi-vendor scenario

The **multi-vendor** scenario (D5-4) extends D5-3 with case ownership
transfer. Vendor initially holds the case; Coordinator takes over and then
invites a second Vendor (Vendor2) to join.

```bash
DEMO=multi-vendor docker compose -f docker/docker-compose-multi-actor.yml \
    up --abort-on-container-exit demo-runner
```

### What the multi-vendor demo does

| Step  | Actor       | Action                                                    |
|:------|:------------|:----------------------------------------------------------|
| 1     | Finder      | Submits a report to Vendor's inbox                        |
| 2     | Vendor      | Validates the report (trigger: `validate-report`)         |
| 3     | Vendor      | Creates the case on CaseActor (`attributed_to` = Vendor)  |
| 4     | Vendor      | Links the report to the case                              |
| 5     | Vendor      | Invites Finder; Finder accepts                            |
| 6     | Vendor      | Proposes an embargo; Finder and Vendor accept it          |
| 7     | Vendor      | Offers case ownership to Coordinator; Coordinator accepts |
| 8     | Coordinator | Invites Vendor2; Vendor2 accepts                          |
| 9     | Coordinator | Delivers embargo proposal to Vendor2; Vendor2 accepts     |
| ✅    | CaseActor   | 3 participants; Coordinator is owner; embargo ACTIVE       |

---

## Step 5 — Read the output

Each demo step is wrapped in a `demo_step` or `demo_check` context manager
that prints structured lifecycle markers:

| Symbol | Meaning                                  |
|:-------|:-----------------------------------------|
| 🚥    | A workflow step has started              |
| 🟢    | The step completed successfully          |
| 🔴    | The step raised an exception             |
| 📋    | A verification check has started         |
| ✅    | The verification check passed            |
| ❌    | The verification check failed            |

Watch for `🔴` or `❌` markers to diagnose failures. The compose
`--abort-on-container-exit` flag stops the entire stack when `demo-runner`
exits, so a failed scenario terminates cleanly.

To examine logs from a specific container after a run:

```bash
docker compose -f docker/docker-compose-multi-actor.yml logs vendor
```

---

## Step 6 — Clean up

Named Docker volumes persist the SQLite databases between runs. Remove all
volumes after a session to start fresh next time:

```bash
docker compose -f docker/docker-compose-multi-actor.yml down -v
```

---

## Running all three scenarios in sequence

The integration test script builds the images, runs a selected scenario,
verifies the exit code, and removes all volumes automatically:

```bash
# From the repository root:
./integration_tests/demo/run_multi_actor_integration_test.sh two-actor
./integration_tests/demo/run_multi_actor_integration_test.sh three-actor
./integration_tests/demo/run_multi_actor_integration_test.sh multi-vendor
```

Or via the Makefile targets:

```bash
make integration-test-multi-actor    # two-actor
make integration-test-three-actor    # three-actor
make integration-test-multi-vendor   # multi-vendor
```

!!! tip

    The integration test script uses `PROJECT_NAME=vultron-it` by default so
    its containers do not conflict with a running development stack. Override
    `PROJECT_NAME` to run multiple scenarios in parallel:

    ```bash
    PROJECT_NAME=vultron-it-two   DEMO=two-actor   \
        ./integration_tests/demo/run_multi_actor_integration_test.sh
    PROJECT_NAME=vultron-it-three DEMO=three-actor \
        ./integration_tests/demo/run_multi_actor_integration_test.sh
    ```

---

## What we accomplished

We have:

- started a multi-container Vultron stack and run three complete CVD
  workflows, each involving a different set of protocol participants,
- observed trigger-based puppeteering where each actor's behavior tree and
  outbox logic drives the workflow end-to-end, and
- seen how Vultron handles two-party coordination, coordinator-mediated
  three-party coordination, and multi-vendor case ownership transfer.

---

## Next steps

- **Explore the single-container demos** — see
  [Tutorial: Run the Receive-Report Demo](receive_report_demo.md) and
  [Tutorial: Running the Other Demos](other_demos.md) to step through
  individual protocol activities in detail.
- **Read the scenario source** — the scripts are in
  `vultron/demo/scenario/`; shared utilities are in `vultron/demo/utils.py`.
- **Understand the protocol** — browse
  [How-to: ActivityPub Activities](../howto/activitypub/activities/index.md)
  for per-activity walkthroughs of the messages exchanged in these scenarios.
- **Consult the Docker README** — `docker/README.md` documents port
  mappings, environment variable overrides, and manual seed commands for
  debugging individual containers.

---
description: >
  Step through a complete Coordinated Vulnerability Disclosure (CVD) case with
  the Reporter + Vendor (rv) scenario, from report submission through fix
  readiness, public disclosure, embargo teardown, and case closure.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 300
page_type: tutorial
subject: protocol
---

# Tutorial: Run the `rv` Demo

{% include-markdown "../includes/test_bench.md" %}

In this tutorial, we will run the **`rv` demo** end to end with Docker Compose.
The `rv` scenario models a Coordinated Vulnerability Disclosure (CVD) case between a Reporter, who reports the vulnerability, and a Vendor, who maintains the affected software.
It is the default scenario of the multi-actor stack and the simplest place to see a whole case go by.

By the end of this tutorial, we will have:

- started the multi-actor Vultron stack, in which two of the actor containers take part in this scenario,
- watched the Reporter and the Vendor exchange ActivityStreams messages across container boundaries, driven by trigger-based puppeteering, and
- followed the case through seven verified milestones, from report submission to case closure.

!!! info "What we will learn"

    The `rv` demo runs a case from report submission through case creation, note exchange, fix readiness, public disclosure, embargo teardown, and closure.
    The demo runner calls trigger endpoints on each actor's own container, so each actor's behavior tree and outbox logic run end to end.
    Activities flow from the sender's outbox to the receiver's inbox over HTTP across the Docker network.
    This is the full Vultron Protocol, not a simulation.

---

## Prerequisites

You need the following tools installed before we begin:

{% include-markdown "./_docker_prerequisites.md" %}

You do **not** need Python installed locally; the containers include everything required.

This tutorial assumes you know what a CVD case is and who its participants are.
If you do not, start with [What Is Vultron?](../topics/background/what-is-vultron.md).

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

## Step 3 — Run the demo

From the repository root, run:

```bash
docker compose -f docker/docker-compose-multi-actor.yml \
    up --abort-on-container-exit --exit-code-from demo-runner
```

The `rv` scenario is the **default**, so no `DEMO` environment variable is required.
[Running the Multi-Actor Container Demos](container_demos.md) shows how to select the others.

{% include-markdown "./_first_run_build.md" %}

Once the images exist, the compose stack starts all of its actor containers and waits for each one to pass its health check.
Three of them take part in this scenario: `reporter` plays the Reporter, `vendor` plays the Vendor, and `case-actor` hosts the **Case Actor**.
The Case Actor is the actor that holds the CASE_MANAGER role for the case and writes its ledger; see [The CASE_MANAGER and the Case Ledger](../topics/case_lifecycle/case_manager_and_ledger.md) for what that role does.
The other containers stay idle, and the demo runner confirms at the end of Phase 2 that the dedicated `case-actor` container holds the case.

The demo runner then:

1. resets every container's state and seeds the actor records,
2. steps through the six phases below, logging each step and verifying each milestone, and
3. exits with code `0` on success or non-zero on failure.

!!! success "Success indicator"

    Look for this line at the end of the output:

    ```text
    rv DEMO COMPLETE ✓  (VFDPxa full lifecycle)
    ```

    The banner names the lifecycle the scenario walks.
    The case state the checks verify ends at `VFdPxa`: a vendor-only participant stops at fix ready, because deploying a fix is a Deployer's step (see Phase 4).

---

## What happens: six phases, seven milestones

The demo progresses through six phases, and the runner verifies seven milestones (M1–M7) along the way.
The milestones are numbered by protocol meaning, and Phase 2 verifies M2 before Phase 3 verifies M3, so the milestones appear in the log in numeric order.

The sections below say what to look for in each phase.
The [`rv` scenario narrative](../topics/scenarios/rv.md) explains why the case moves this way, and the [`rv` Demo Protocol Reference](../reference/rv-demo-protocol.md) lists every message exchanged.

### Phase 1 — Report submission and case activation (M1)

The Reporter submits a vulnerability report to the Vendor.
The Vendor's behavior tree proposes a case to its Case Actor, which creates the case, seats the Vendor as Case Owner and the Reporter in its `REPORTER` role, and activates the Vendor's default embargo.
The Case Actor then delivers a copy of the case to both participants.
The Vendor validates the report and engages the case, which moves its [Report Management (RM)](../topics/process_models/rm/index.md) state from `RECEIVED` through `VALID` to `ACCEPTED`.

Notice the two causal gates (`🚧`) in this phase: the runner does not validate until the case copy has landed in the Vendor's own store, and does not engage until the Vendor's `RM.VALID` has been committed.

**M1 verified when:** both containers hold a case record with at least three participants (Vendor, Reporter, Case Actor) and an active embargo, and the Reporter holds its copy of the case.

### Phase 2 — Replica synchronization verification (M2)

Every change to the case is written to the case ledger by the Case Actor and fanned out to every participant.
The runner waits until the Reporter's copy holds every ledger entry the Vendor's copy holds, then compares the two: same participants, same active embargo, same ledger tail hash.

Notice that no new protocol step happens in this phase.
It is a read-only check that the fan-out worked.

**M2 verified when:** the Reporter's copy of the case matches the Vendor's.

### Phase 3 — Notes exchange (M3)

The Reporter asks a question by adding a note to the case, and the Vendor replies with a second note.
Each note goes to the Case Actor, which records it in the ledger and fans the entry out, so both participants end up holding both notes.

**M3 verified when:** the Vendor's container holds the authoritative final case state, including both notes.

### Phase 4 — Fix lifecycle (M4–M5)

The runner triggers the Vendor to report that its fix is ready.
The Vendor's [Case State (CS)](../topics/process_models/cs/cs_model.md) vendor-path dimensions advance from `vfd` to `VFd`: vendor aware and fix ready, fix not yet deployed.

Notice that the demo does **not** report a fix deployed.
Deployment is a Deployer's step, and this scenario has no Deployer, so the Vendor stops at `VFd`.
Both M4 and M5 therefore check for fix ready; M5 confirms the state held after the Reporter's copy caught up.

**M4 verified when:** both copies show the Vendor's case state includes `F` (fix ready).

**M5 verified when:** both copies still show `VFd`, the Vendor's final vendor-path state.

### Phase 5 — Publication and embargo teardown (M6)

The Vendor reports that the vulnerability is publicly disclosed, which sets its public-path state to `Pxa`.
The Case Actor sees a public-awareness report from the Case Owner and terminates the embargo, moving the [Embargo Management (EM)](../topics/process_models/em/index.md) state to `EXITED`; see [Early Termination](../topics/process_models/em/early_termination.md) for why publication ends an embargo.
The Reporter then reports its own public awareness.

**M6 verified when:** both copies show `CS.VFdPxa` and `EM.EXITED`, and the Vendor's participant record is public-aware.

### Phase 6 — Case closure (M7)

The Reporter closes its participation first.
The demo waits until the Case Actor has recorded the Reporter's departure.
The Vendor then closes its participation.
Because the Vendor is the Case Owner, the Case Actor closes the case: it advances the Vendor and then itself to `RM.CLOSED`, and its own `RM.CLOSED` entry marks the case fully closed.
The Case Owner leaves last because the Case Actor records nothing a participant sends after the case is fully closed.
A participant that has closed receives the entries that record its own closure and nothing after them, so neither copy holds every closure: the Reporter's copy does not learn that the Vendor left, and the Vendor's copy does not receive the Case Actor's own closure.

**M7 verified when:** the Case Actor's ledger records both departures before the case is fully closed, every participant is `RM.CLOSED` in the Case Actor's own store, and each copy ends at its own participant's closure.

---

## Reading the activity log

The demo runner logs all activity to stdout with structured markers.
Use the milestone lines as anchor points when reading the output.

| Marker | What it means |
|:-------|:--------------|
| `✅ M1:` | Required participants (Vendor, Reporter, Case Actor), `EM.ACTIVE`, and the Reporter holds a case copy |
| `✓ M2:` | Reporter DataLayer synchronized (Ledger Fanout verified) |
| `✅ M3:` | Vendor container holds the authoritative final case state |
| `✅ M4:` | Both copies show CS includes `F` (fix ready) |
| `✅ M5:` | Both copies show CS includes `F` (fix ready); the Vendor stops at `VFd` |
| `✅ M6:` | Both copies show `CS.VFdPxa` and `EM.EXITED`; the Vendor is public-aware |
| `✅ M7:` | Every departure recorded before the case is fully closed; all participants `RM.CLOSED` in the Case Actor's store; each copy ends at its own closure |

Between milestones, look for these log line prefixes:

| Prefix | Meaning |
|:-------|:--------|
| `🚥 <description>` | A demo step is starting |
| `🟢 <description>` | A demo step completed successfully |
| `🔴 <description>` | A demo step failed (see Troubleshooting) |
| `📋 <description>` | A demo check is starting |
| `✅ <description>` | A demo check passed |
| `❌ <description>` | A demo check failed (see Troubleshooting) |
| `🚧 <description>` | A causal gate is waiting for an earlier effect to be committed |
| `🔓 <description>` | The gate's precondition held |
| `🔒 <description>` | The gate failed; its dependent steps were skipped |

A successful run ends with:

```text
================================================================================
rv DEMO COMPLETE ✓  (VFDPxa full lifecycle)
================================================================================
```

---

## Troubleshooting

### The demo-runner exits immediately with an error

The actor containers may not have finished starting up.
Verify that every actor service is healthy:

```bash
docker compose -f docker/docker-compose-multi-actor.yml \
    ps reporter vendor coordinator case-actor actor5 actor6
```

All of them should show `healthy` status.
If any service shows `starting` or `unhealthy`, wait a moment and retry.

### A milestone check fails with `❌`, or a gate fails with `🔒`

Read the failure message for the check or gate that failed.
Then check the demo-runner and actor logs for errors:

```bash
docker compose -f docker/docker-compose-multi-actor.yml logs demo-runner
docker compose -f docker/docker-compose-multi-actor.yml logs vendor
docker compose -f docker/docker-compose-multi-actor.yml logs reporter
```

Look for `ERROR` or `500` status lines that correspond to the failing step.

### Docker images are stale after a code change

Force a rebuild:

```bash
docker compose -f docker/docker-compose-multi-actor.yml \
    build --no-cache demo-runner
```

### An actor container exits saying its store must be reset

The SQLite database in that container's volume was written by an older version whose stored shape has since changed.
Vultron does not migrate stored data, so it refuses to open the old store.
Remove the volumes, then run the demo again:

```bash
docker compose -f docker/docker-compose-multi-actor.yml down -v
```

### The demo fails partway through and leaves volumes dirty

Clean up volumes before retrying:

```bash
docker compose -f docker/docker-compose-multi-actor.yml down -v
```

---

## Step 4 — Clean up

{% include-markdown "./_cleanup_volumes.md" %}

---

## What we accomplished

We have:

- cloned the Vultron repository and started the multi-actor Vultron stack,
- run a complete CVD case between a Reporter and a Vendor, from report submission through fix readiness, public disclosure, embargo teardown, and closure, and
- observed the seven milestones (M1–M7) logged and verified by the demo runner in real time.

---

## Next steps

- **Run the other container scenarios** — see [Running the Multi-Actor Container Demos](container_demos.md) to run RCV, RVCV-handoff, and the other multi-actor workflows.
- **Understand why the case moved this way** — the [`rv` scenario narrative](../topics/scenarios/rv.md) explains each step in CVD terms and names the ledger entry it produces.
- **Understand the message-level protocol** — the [`rv` Demo Protocol Reference](../reference/rv-demo-protocol.md) documents every ActivityStreams activity exchanged during this demo and the ledger entries it produces.
- **Read the scenario source** — the demo script is at `vultron/demo/scenario/rv_demo.py`; shared helpers are in `vultron/demo/helpers/`.
- **Explore the single-container demos** — see [Run the Receive-Report Demo](receive_report_demo.md) and [Running the Other Demos](other_demos.md) to step through individual protocol activities.

{% include-markdown "../start/_paths/coordinate-cases/tutorials__rv-demo.md" %}

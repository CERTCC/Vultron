# Tutorial: Running the Other Demos

In this tutorial, we will run the remaining Vultron demo sub-commands
end-to-end using Docker Compose. By the end of this tutorial, we will
have explored:

- case initialization and participant management,
- actor invitation, suggestion, and ownership transfer,
- embargo establishment and lifecycle management,
- acknowledgement, status updates, and notes, and
- the full Report Management (RM) case lifecycle.

!!! info "What we will learn"

    Each demo sub-command exercises a focused slice of the Vultron
    protocol. This tutorial introduces all of them except
    `receive-report`, which is covered in
    [Tutorial: Run the Receive-Report Demo](receive_report_demo.md).

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

If you have not yet cloned the repository and started the demo container, follow
[Tutorial: Run the Receive-Report Demo](receive_report_demo.md) first —
Steps 1 and 2 of that tutorial get us to a running container shell.

---

## Step 1 — Start the demo container

From the repository root, start the demo container:

```bash
docker compose -f docker/docker-compose.yml run --rm demo
```

After the images are built and the API server is healthy, we should see a
container shell prompt:

```text
root@<container-id>:/app#
```

All commands in the remaining steps are run inside this container shell.

---

## Step 2 — Case initialization

### initialize-case

```bash
vultron-demo initialize-case
```

This demo walks through the steps a vendor takes to open a new
`VulnerabilityCase` after receiving a report: create the case, add the
vendor as participant and case owner, link the report to the case, and add
the finder as a participant.

See
[Initialize a Case](../howto/activitypub/activities/initialize_case.md)
for the full activity-by-activity walkthrough.

### initialize-participant

```bash
vultron-demo initialize-participant
```

This demo demonstrates adding new participants to an existing case. A
coordinator and a finder are each created as `CaseParticipant` objects and
added to the case. Notice how the participant list grows after each addition.

See
[Initialize a Participant](../howto/activitypub/activities/initialize_participant.md)
for details.

---

## Step 3 — Actor management

### invite-actor

```bash
vultron-demo invite-actor
```

This demo shows two invitation outcomes: the case owner invites a
coordinator who **accepts** (and is added to the case), then invites
a second coordinator who **rejects** (and is not added). Notice the log
lines showing the `RmInviteToCase` (Invite) and the corresponding
`RmAcceptInviteToCase` / `RmRejectInviteToCase` activities.

See
[Invite an Actor to a Case](../howto/activitypub/activities/invite_actor.md)
for background.

### suggest-actor

```bash
vultron-demo suggest-actor
```

This demo shows a finder *suggesting* a coordinator to the case owner.
Two paths are demonstrated: the vendor **accepts** the suggestion (and
sends an invitation to the coordinator) and the vendor **rejects** the
suggestion (no invitation is sent).

See
[Suggest an Actor for a Case](../howto/activitypub/activities/suggest_actor.md)
for the corresponding activity descriptions.

### manage-participants

```bash
vultron-demo manage-participants
```

This demo combines the full participant lifecycle: invite → accept →
create participant → add to case → update participant status → remove
from case. A second path shows the rejection outcome. Each step is logged
so we can follow the state changes.

See
[Manage Participants](../howto/activitypub/activities/manage_participants.md)
for details.

### transfer-ownership

```bash
vultron-demo transfer-ownership
```

This demo shows case ownership transfer: the current owner (vendor) offers
the case to a coordinator, who either **accepts** (the case `attributed_to`
field is updated to the coordinator) or **rejects** (ownership remains with
the vendor).

See
[Transfer Case Ownership](../howto/activitypub/activities/transfer_ownership.md)
for the corresponding activity descriptions.

---

## Step 4 — Embargo management

### establish-embargo

```bash
vultron-demo establish-embargo
```

This demo exercises embargo negotiation. A participant proposes an embargo
period; the case owner either **accepts** (activating the embargo on the
case, EM state = `ACTIVE`) or **rejects** (no change to EM state).

See
[Establish an Embargo](../howto/activitypub/activities/establish_embargo.md)
for background.

### manage-embargo

```bash
vultron-demo manage-embargo
```

This demo continues from an active embargo. Two paths are shown:

1. **Activate and terminate**: coordinator proposes → vendor accepts →
   embargo activated → vendor terminates (removes) the embargo.
2. **Reject and repropose**: coordinator proposes → vendor rejects →
   coordinator proposes a revised embargo → vendor accepts → activated.

See
[Manage an Embargo](../howto/activitypub/activities/manage_embargo.md)
for details.

---

## Step 5 — Acknowledgement, status, and notes

### acknowledge

```bash
vultron-demo acknowledge
```

This demo shows how a vendor uses `RmReadReport` (as:Read) to acknowledge
receipt of a report without committing to an outcome. Three paths are
demonstrated:

1. **Acknowledge only** — ack, then notify finder.
2. **Acknowledge then validate** — ack → validate → notify finder.
3. **Acknowledge then invalidate** — ack → invalidate → notify finder.

See
[Acknowledge a Report](../howto/activitypub/activities/acknowledge.md)
for the corresponding activity descriptions.

### status-updates

```bash
vultron-demo status-updates
```

This demo shows three types of case record updates:

1. **Notes** — vendor creates a `Note` and adds it to the case.
2. **Case status** — vendor creates a `CaseStatus` and adds it to the case.
3. **Participant status** — vendor creates a `ParticipantStatus` and adds
   it to a case participant.

See
[Status Updates](../howto/activitypub/activities/status_updates.md)
for details.

---

## Step 6 — Full RM case lifecycle

### manage-case

```bash
vultron-demo manage-case
```

This demo exercises the Report Management (RM) state machine from
submission through closure. Three paths are shown:

1. **Engage path** — submit → validate → create case → engage → close.
2. **Defer and re-engage path** — submit → validate → create case →
   defer → re-engage → close.
3. **Invalidate path** — submit → invalidate → close report.

Notice the RM state transitions logged at each step.

See
[Manage a Case](../howto/activitypub/activities/manage_case.md) for
the corresponding activity descriptions and state machine reference.

---

## Step 7 — Run all demos in sequence

To run every demo in the standard order, use the `all` sub-command:

```bash
vultron-demo all
```

The `all` sub-command stops and reports failure on the first demo that
raises an exception. On full success, a summary table is printed:

```text
==================================================
Demo Summary
==================================================
  receive-report                        ✅ PASS
  initialize-case                       ✅ PASS
  ...
  manage-participants                   ✅ PASS
==================================================
  12/12 demos passed
==================================================
```

---

## Step 8 — Exit the container

When we are finished, type `exit` to leave the container shell:

```bash
exit
```

Stop the API server with:

```bash
docker compose -f docker/docker-compose.yml down
```

---

## What we accomplished

We have:

- run all 11 remaining Vultron demo sub-commands covering the major
  protocol workflows,
- observed how the Vultron Protocol handles case initialization, actor
  management, embargo negotiation, and the RM state machine, and
- run the complete demo suite in one shot using `vultron-demo all`.

---

## Next steps

- **Understand the protocol** — browse
  [How-to: ActivityPub Activities](../howto/activitypub/activities/index.md)
  for per-activity walkthroughs of everything we just observed.
- **Explore the demo scripts** — all demo source files are in
  `vultron/demo/`; shared utilities are in `vultron/demo/utils.py`.
- **Read the demo README** — `vultron/demo/README.md` describes the demo
  architecture and available sub-commands.

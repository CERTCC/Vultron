---
description: >
  Start the case shadow tool with one command, open its dashboard, and read
  where one case stands: each participant's states, the desiderata met or
  broken, and the moves open from here.
stakeholder_type: [cvd-practitioner, platform-developer]
level: 200
page_type: how-to
subject: implementation
---

# How to Run the Case Shadow Tool

{% include-markdown "../includes/not_normative.md" %}

This guide shows you how to start the case shadow tool and read one case on its dashboard.
The case shadow tool is a read-only advisor: it reads one case through one case reader, shows where the case stands, and sends nothing to anyone.
It is for a Coordinated Vulnerability Disclosure (CVD) coordinator who wants Vultron's view of a case beside the system that holds the case.

---

## Prerequisites

- Docker with the Compose plugin, to run the tool as a container.
- Or a checkout of this repository with `uv`, to run the tool on your own machine.

---

## Step 1: Start the dashboard

From the `docker/` directory of the repository, run:

```bash
docker compose up shadow
```

Then open <http://127.0.0.1:8501> in a browser on the same machine.
The service publishes its port on the loopback interface only, so no other machine on your network can open the page.
The container has no volume, so nothing it reads outlives it.
The tool holds a case only in memory, and it removes its temporary files when it stops, so it leaves no copy of a case on the host.

To run the tool without Docker, run `uv run vultron-shadow` from the repository root.
It listens on `127.0.0.1:8501`; `--port` changes the port.

The tool writes its log to standard error, at `INFO` and above; `--log-level DEBUG` adds a record for each ledger entry it reads.
A log record names the case, its activity and actor ids, and the case's tracker reference, such as its Vulnerability Information and Coordination Environment (VINCE) case URL.
The tool removes the case's content, such as a title, a description, or a contact name, from each log record.
It removes a whole value, or a whole line of a value, wherever a record quotes it.
You can share the log records to report a problem.

---

## Step 2: Choose a source

The **Source** menu at the side of the page sets where the tool reads a case from.
The page opens on **Recorded demo cases**.
Choose another source at any time; the tool does not restart.
When you choose another source, or type another node, the page drops the case you entered and its standing, so a case from one source never shows as if another source sent it.

| Source | What the tool reads |
|---|---|
| **Recorded demo cases** | Vultron case-ledger files, such as the committed demo recordings. |
| **VINCE** | Cases in VINCE, through its connector. See [Step 5](#step-5-read-a-case-from-vince). |
| **A running Vultron node** | A case's ledger on a running Vultron node, followed live. See [Read a case from a running Vultron node](#read-a-case-from-a-running-vultron-node). |

---

## Step 3: Read a recorded case

The recorded demo cases are Vultron case-ledger files: the JSON Lines files a Case Manager's case ledger is written to.
The Compose service reads the committed demo recordings under `ui/src/recordings/`, and the **Case** box lists them.
Pick one, such as `rcvv-embargo/case-actor.jsonl`.

To read your own ledger files, set `VULTRON_SHADOW__LEDGER_DIR` to the directory that holds them, and name a case by its file's path relative to that directory.
The tool opens no file outside that directory.
With `VULTRON_SHADOW__LEDGER_DIR` unset, as in a `uv run vultron-shadow` run, the tool reads only files under the directory you start it in, named by their path relative to it.

A Vultron ledger needs no translation, so its **Not translated**, **Inferred**, and **Not observable** panels are empty.

### Read a case from a running Vultron node

The tool can also read a case's ledger from a running Vultron node in prototype run mode.
Choose **A running Vultron node** in the **Source** menu, then fill in two fields:

| Field | Value |
|---|---|
| **Node API root** | The node's API root, such as `http://case-actor:7999/api/v2`. The tool refuses a URL that has a user name, a password, a query, or a fragment. |
| **Case Manager actor id** | The Case Manager on that node whose ledger the tool reads, such as `case-actor`. The tool refuses an id that names no actor. |

The tool fills in both fields from `VULTRON_SHADOW__NODE_URL` and `VULTRON_SHADOW__NODE_ACTOR_ID` when they are set, and you can type other values.
If the tool refuses a value, the menu shows why, and the tool sends no request.
Type the case's id on that node in the **Case** box.
The tool then follows the case live: the page shows the case's new standing each time the node adds an entry to the case's ledger.
The case narrative gains a line for that entry and keeps every line before it.
The tool sends the node only `GET` requests of the case's demo ledger event-stream endpoint.
When the connection drops, the tool connects again and asks only for the entries after the last one it received.
A node that is not in prototype run mode does not serve that endpoint, so the tool shows an error that names the node and the case.

If the node sends an entry that is not a valid ledger entry, the page shows an error that names the entry.
The page keeps the case's last accepted standing below the error.
When the node stops, or the tool cannot connect to it again, the page marks that standing as no longer live.

To follow a case on the demo stack, start the stack in `docker/docker-compose-multi-actor.yml` as `docker/README.md` describes.
Then start the tool with `docker compose up shadow`, choose **A running Vultron node**, and type `http://case-actor:7999/api/v2` and `case-actor`.
The `shadow` service joins the demo stack's network, so it reaches the Case Manager by its service name.
It still has no volume, and it still publishes its port on the loopback interface only.

---

## Step 4: Read the scoreboard

The page shows the case as it stands at its last ledger entry.

- The top row shows the case's embargo state and its public state: whether the public is aware, whether an exploit is public, and whether attacks are observed.
- **Participants** lists each participant with its roles, its report state, and, for a Vendor, its case state and a count of the desiderata met (✅), broken (❌), and still open (⏳), and of those it cannot know (❔) when the source cannot observe an event.
- **Desiderata** lists each of the twelve desiderata in words, with one column for each Vendor.
- **Move advice** puts each open move in one of three bands, by the method that [Move Bands Against Pathology Cases](../topics/measuring_cvd/move_bands.md) tests.
  A move's band is set by its end desiderata, or by its embargo desiderata when it changes no end desideratum.
  A **Harm-free** move raises at least one Vendor above the chance value and lowers none.
  A **Trade-off** move raises one Vendor at another's cost.
  An **Unhelpful** move raises no Vendor; its band is closed until you open it.
- In the harm-free and trade-off bands, each move's row is shaded by its layer, with layer 1 the darkest.
  Layer 1 holds the moves that no other open move beats, and each move in a lighter layer is beaten by a move in a darker one.
  A ⭐ marks a top move: a harm-free or trade-off move in layer 1.
  A 👉 marks a coordinator's move that none of the coordinator's other moves beats.
  Choose the darkest move in the highest band that has one.
- **Harms by vendor** lists each Vendor that a move leaves below the chance value, in its end or its embargo desiderata, with how far below.
  A harm-free move can still harm a Vendor's embargo desiderata when its end desiderata decide its band.
  A negative value means worse than the chance value, not a broken desideratum.
  A trade-off move that a harm-free move beats says so under **Dominated by**.
- **Moves with no band** lists each other move a participant can make, with the reason it has no band.
  The tool never adds the Vendors' values into one score, and never ranks the moves by one.

A ledger with a missing entry shows the missing entry instead of a standing, because a measure over a history with a gap is wrong.

Below the scoreboard, **Case narrative** tells who did what, when, and which states it changed, with one line for each ledger entry in ledger order.
The tool reads each line from the ledger; nobody writes it by hand.

- **#** is the entry's log index.
- **Time** is the time the actor's activity claims, and **Committed** shows the Case Manager's commit stamp only where it differs.
- **Actor**, **Activity** and **Object** name who acted, the phrase for the entry's semantic type, and what the activity names.
- **State changes** lists each state the entry moved: a participant's report state (RM) and its fix path and deployment (VFD), and the case's embargo state (EM) and public state (PXA).
  A `?` in a VFD or PXA state is an event the source never records, which the page reads as unknown.
- **Notes**, when shown, says what the tool could not read in an entry.

---

## Step 5: Read a case from VINCE

VINCE reaches the tool through a connector: an installed package that implements a case reader.
The VINCE connector is installed with the tool.
The **Source** menu always lists **VINCE**, and you can choose it only when these environment variables are set in the shell that starts the tool:

| Variable | Value |
|---|---|
| `VULTRON_VINCE__BASE_URL` | Your own VINCE API base URL. |
| `VULTRON_VINCE__API_TOKEN` | Your own VINCE API credential. |

Without them, the menu marks **VINCE** as not set up, and choosing it says which variables to set.
The page has no field for the credential: the tool reads it only from the environment, never from the page or a configuration file.
The Compose service passes each variable through from your shell by name, so no value is written to any file.
You see only the cases your own credential can see in VINCE.

To read another outside system instead, install its connector package and set `VULTRON_SHADOW__CONNECTOR` to the connector's entry-point name.
The **Source** menu then offers that system in place of VINCE.

Development work, including Coding Agent sessions, uses a test VINCE instance with test credentials, never production VINCE.

The **Not translated** panel lists each fact the connector read and could not translate, with the reason.
The **Not observable** panel lists what the outside system never records; read each one as unknown, not as false.
Its **Reads as unknown** column names the case-state events each fact covers.
Each desideratum that orders one of those events shows as unknown (❔), never as met or broken.
Each move whose change in outcome rests on one of those events goes under **Moves with no band**, with that reason.

---

## Related

- [Configuration reference](../reference/configuration.md) lists the `shadow:` and `vince:` settings.
- [Measuring Your CVD Program](measure_your_cvd_program.md) explains the desiderata the dashboard scores.

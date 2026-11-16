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

To run the tool without Docker, run `uv run vultron-shadow` from the repository root.
It listens on `127.0.0.1:8501`; `--port` changes the port.

---

## Step 2: Read a Vultron case

With no connector set, the tool reads Vultron case-ledger files: the JSON Lines files a Case Manager's case ledger is written to.
The Compose service reads the committed demo recordings under `ui/src/recordings/`, and the **Case** box lists them.
Pick one, such as `rcvv-embargo/case-actor.jsonl`.

To read your own ledger files, set `VULTRON_SHADOW__LEDGER_DIR` to the directory that holds them, and name a case by its file's path relative to that directory.
The tool opens no file outside that directory.
With `VULTRON_SHADOW__LEDGER_DIR` unset, as in a `uv run vultron-shadow` run, the **Case** box takes any file path.

A Vultron ledger needs no translation, so its **Not translated**, **Inferred**, and **Not observable** panels are empty.

---

## Step 3: Read the scoreboard

The page shows the case as it stands at its last ledger entry.

- The top row shows the case's embargo state and its public state: whether the public is aware, whether an exploit is public, and whether attacks are observed.
- **Participants** lists each participant with its roles, its report state, and, for a Vendor, its case state and a count of the desiderata met (✅), broken (❌), and still open (⏳).
- **Desiderata** lists each of the twelve desiderata in words, with one column for each Vendor.
- **Open moves** lists each move a participant can make from here, and its effect for each Vendor: how many desiderata it makes likelier (▲) or less likely (▼) to be met than leaving the case to chance.
  The tool never adds the Vendors' effects into one score.

A ledger with a missing entry shows the missing entry instead of a standing, because a measure over a history with a gap is wrong.

---

## Step 4: Read a case from an outside system

An outside system, such as the Vulnerability Information and Coordination Environment (VINCE), reaches the tool through a connector: an installed package that implements a case reader.
To read through one, install its package and set these environment variables in the shell that starts the tool:

| Variable | Value |
|---|---|
| `VULTRON_SHADOW__CONNECTOR` | The connector's entry-point name. |
| `VULTRON_VINCE__BASE_URL` | Your own VINCE API base URL. |
| `VULTRON_VINCE__API_TOKEN` | Your own VINCE API credential. |

The Compose service passes each of these variables through from your shell by name, so no value is written to any file.
The credential is read only from the environment, never from a configuration file.
You see only the cases your own credential can see in VINCE.

Development work, including Coding Agent sessions, uses a test VINCE instance with test credentials, never production VINCE.

The **Not translated** panel lists each fact the connector read and could not translate, with the reason.
The **Not observable** panel lists what the outside system never records; read each one as unknown, not as false.

---

## Related

- [Configuration reference](../reference/configuration.md) lists the `shadow:` and `vince:` settings.
- [Measuring Your CVD Program](measure_your_cvd_program.md) explains the desiderata the dashboard scores.

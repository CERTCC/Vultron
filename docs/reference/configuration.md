---
description: >
  The settings a Vultron reference implementation node reads from config.yaml
  and VULTRON_* environment variables, generated from the configuration model.
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: reference
subject: implementation
---

# Node Configuration Reference

{% include-markdown "../includes/not_normative.md" %}

This page lists every setting a node of the Vultron reference implementation reads at startup, with the `config.yaml` key and the environment variable for each one.
It covers the API server process, `vultron.adapters.driving.fastapi.main:app`, whether it runs in a container or directly under `uvicorn`.
The settings tables and the example file are generated from the configuration model in `vultron/config/` when the site is built, so they list the settings, types and defaults that the build itself uses.

---

## Configuration sources

A node builds its configuration from three sources: environment variables, a configuration file written in YAML Ain't Markup Language (YAML), and the defaults.
A source higher in the table overrides a source below it, one setting at a time (CFG-02-004).

| Source | Where it is read from | When it applies |
|---|---|---|
| Environment variables | `VULTRON_*` variables in the server process environment | Each variable that is set overrides the same setting from the file |
| Configuration file | The YAML file named by `VULTRON_CONFIG`, or `config.yaml` in the working directory when `VULTRON_CONFIG` is unset | Each key present in the file overrides the default |
| Defaults | The configuration model | Every setting has one, so a node starts with no file and no variables (CFG-02-005) |

`VULTRON_CONFIG` holds a file path, relative to the working directory or absolute (CFG-02-002).
When `VULTRON_CONFIG` names a file that does not exist, the node refuses to start and reports the path (CFG-02-006).
When `VULTRON_CONFIG` is unset and no `config.yaml` exists in the working directory, the node starts on defaults and environment variables alone (CFG-02-007).

A node reads its configuration once and keeps it for the life of the process.
A change to the file or to the environment takes effect when the server restarts.

---

## Environment variable names

Every environment variable name is `VULTRON_` followed by the setting's YAML key path in upper case (CFG-03-001).
A double underscore, `__`, separates a section from the key inside it (CFG-03-002).

| YAML key | Environment variable |
|---|---|
| `mode` | `VULTRON_MODE` |
| `server.base_url` | `VULTRON_SERVER__BASE_URL` |
| `actor.case_actor_service_url` | `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` |

A single underscore inside a key stays a single underscore: `ledger.staleness_window_days` is `VULTRON_LEDGER__STALENESS_WINDOW_DAYS`.

---

## Value formats

An environment variable always carries a string, so a setting whose type is not a string has a text form for the environment.

| Type | In `config.yaml` | In an environment variable |
|---|---|---|
| string, URL | A YAML string | The text itself |
| integer, number | A YAML number | The number as text, for example `300` or `0.25` |
| boolean | `true` or `false` | `true` or `false` |
| duration | An ISO 8601 duration string, for example `PT72H` or `P7D` | The same ISO 8601 string; a bare number of seconds is refused |
| list | A YAML sequence | A JSON array, for example `["vendor", "coordinator"]` |
| unset | `null`, or the key left out | No form: a variable left out of the environment leaves the setting at its file value or default |

A value that does not match its setting's type or bounds stops the node at startup with an error that names the setting (CFG-04-006).

---

## Settings

Each table below lists one section of `config.yaml`.
The Type column gives the accepted values and any numeric bounds, and the Default column gives the value the node uses when neither the file nor the environment sets one.

```python exec="true" idprefix=""
from vultron.metadata.docs.config_reference import render_settings_tables

print(render_settings_tables())
```

`actor.case_actor_service_url` has no default, and a node that receives reports needs it.
Without it, the node cannot ask the CaseActor service to open a case for a report it receives (CP-08-001).
The proposal flow that uses it is described in [Propose Case](../topics/behavior_logic/use-cases/propose-case.md).

---

## Example configuration file

The file below sets every setting to its default, in the YAML form the node reads.
A file that sets only some keys is equivalent to this one with the remaining keys left at these values.

```python exec="true" idprefix=""
from vultron.metadata.docs.config_reference import render_default_config_block

print(render_default_config_block())
```

---

## What is out of scope

This page covers the node configuration model only.
The demo tooling reads a separate set of variables that are not node settings (CFG-04-007).

| Variable | Read by | Purpose |
|---|---|---|
| `VULTRON_SEED_CONFIG` | The demo seeding command, `vultron-demo seed` | Path to the seed file that names the local actor and its peers |
| `VULTRON_ACTOR_ID`, `VULTRON_ACTOR_NAME`, `VULTRON_ACTOR_TYPE` | The demo seeding command | The bootstrap identity of the local actor |
| `VULTRON_API_BASE_URL` | The demo seeding command | The API server the seeding command writes the actor records to |
| `DEMO` | The Docker Compose demo runner | The demo scenario to run |

The Docker Compose files set node settings per container as environment variables; `docker/README.md` in the repository lists the values each container receives.

## Further reading

- [Run the Receive-Report Demo](../tutorials/receive_report_demo.md) — starts a node with Docker Compose, or directly under `uvicorn` with `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` set.
- [Running the Multi-Actor Container Demos](../tutorials/container_demos.md) — runs one node per participant, each configured through its container's environment.

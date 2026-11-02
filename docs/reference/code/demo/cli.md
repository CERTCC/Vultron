---
stakeholder_type: [project-contributor]
---

# Demo CLI

The unified Vultron demo CLI provides a single entry point for all demo
scripts via the `vultron-demo` command (DC-01-001 through DC-01-005).

## Usage

```shell
vultron-demo --help
vultron-demo receive-report
vultron-demo trigger
vultron-demo all
vultron-demo vultrabot cvd
```

A demo that opens a case takes the CaseActor's identity from `VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL` only.
When the variable is unset, it stops with an error that names the variable.
The `demo` service in `docker/docker-compose.yml` sets it to the server's own API base, `http://localhost:7999/api/v2`.

## Module Reference

::: vultron.demo.cli
    options:
        heading_level: 3

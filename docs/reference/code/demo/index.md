# Demo Package

The `vultron.demo` package contains the unified demo CLI and all individual
Vultron workflow demo scripts.

## Modules

| Module | Description |
|--------|-------------|
| [`vultron.demo.cli`](cli.md) | Click-based unified demo CLI entry point |
| [`vultron.demo.utils`](utils.md) | Shared utilities for all demo scripts |
| [Demo Scripts](demos.md) | Individual workflow demos |

## Running the Demos

### Via the unified CLI

```shell
# Show available sub-commands
vultron-demo --help

# Run a single demo
vultron-demo receive-report

# Run all demos in sequence
vultron-demo all

# Run behaviour-tree demos
vultron-demo vultrabot pacman
vultron-demo vultrabot robot
vultron-demo vultrabot cvd
```

### Via Docker Compose

```shell
cd docker
docker compose up api-dev demo
```

Set the `DEMO` environment variable to run a specific demo non-interactively:

```shell
DEMO=receive-report docker compose up demo
```

### Directly

Each demo script retains its own `__main__` entry point:

```shell
python -m vultron.demo.receive_report_demo
```

## See Also

- [Demo Tutorial](../../../tutorials/receive_report_demo.md)
- [Demo CLI Specification](../../../../specs/demo-cli.md)
- [Demo README](../../../../vultron/demo/README.md)

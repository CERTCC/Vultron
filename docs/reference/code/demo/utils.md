---
stakeholder_type: [project-contributor]
---

# Demo Utilities

`vultron.demo.utils` provides the shared context managers, HTTP client, and
setup/teardown helpers used by all demo scripts (DC-02-001).

## Key Components

- **`demo_step`** / **`demo_check`** / **`demo_gate`** — context managers for structured demo logging.
  `demo_gate` also skips the steps nested inside it when its precondition fails, so a dependent step must sit inside the gate body rather than after it.
- **`check_tree`** — `recording_checks()` and `CheckRecorder`, which record each of those three blocks as one node of a run's check tree, with its kind, label, outcome and the cast members whose containers it read (DEMOCI-11-056, DEMOCI-11-057).
  The capture is off by default, so a demo run outside a recorder behaves exactly as before.
  It is imported from `vultron.demo.utils.check_tree` rather than from the package, so it does not appear in the module reference below.
- **`DataLayerClient`** — HTTP client for the Vultron DataLayer REST API
- **`demo_environment`** — context manager that sets up and tears down a clean
  DataLayer state around each demo run
- **`setup_clean_environment`** — resets the DataLayer and returns the three
  default demo actors (Reporter, Vendor, Coordinator)
- **`check_server_availability`** — polls the health endpoint until the API
  server is ready

## Module Reference

::: vultron.demo.utils
    options:
        heading_level: 3

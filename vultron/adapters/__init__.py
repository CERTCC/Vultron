"""
Adapters layer for the Vultron hexagonal architecture.

This package contains thin translation layers that connect the core domain
to external systems. No domain logic, no AS2 parsing, no semantic extraction
should live here — only translation and dispatch.

Sub-packages:

- ``driving/`` — Driving (left-side) adapters that trigger the core.
  Examples: HTTP inbox, CLI, MCP server.

- ``driven/`` — Driven (right-side) adapters that the core calls out to.
  Examples: activity store, delivery queue, HTTP delivery.

- ``connectors/`` — Connector plugins for outside systems (trackers,
  coordination platforms). Each plugin implements the core ports it serves,
  such as the read-only ``CaseReader``, and translates only.

See ``notes/architecture-adapters.md`` for adapter-layer design details.
"""

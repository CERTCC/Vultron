"""
Driving adapters (left-side / primary adapters).

These adapters receive external requests and translate them into core
use-case calls. They trigger the application — the core does not know
about them.

Modules:

- ``cli.py``        — Command-line interface adapter.
- ``fastapi/``      — FastAPI HTTP adapter (routers, inbox/outbox handlers, app).
- ``mcp_server.py`` — MCP server adapter for AI agent tool calls.
- ``shared_inbox.py`` — Shared-inbox endpoint for federated delivery.
"""

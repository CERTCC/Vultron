"""
MCP server driving adapter — stub.

Exposes Vultron use-case callables as MCP (Model Context Protocol) tools so
that AI agents can invoke them directly without going through the HTTP API.

Future implementation will register one MCP tool per use-case callable
defined in ``core/use_cases/`` and handle authentication / authorization
at the adapter boundary.

See ``plan/PRIORITIES.md`` PRIORITY 1000 (Agentic AI readiness) for the
design rationale.
"""

"""
Connector adapters (outside-system integrations).

A connector plugin integrates one outside system, such as an issue tracker
or a coordination platform. Its directions are the core ports it implements
for outside systems (ADR-0191, ARCH-05-004): today the one port is the
read-only ``CaseReader`` (``vultron/core/ports/case_reader.py``). A connector
translates only; case logic stays in core (ARCH-05-002).

Modules:

- ``base.py``    — ``ConnectorPlugin`` (a name), ``CONNECTOR_PORTS`` and
  ``ports_implemented_by``, which reports the core ports a plugin implements.
- ``loader.py``  — Entry-point–based plugin discovery and registration.

Sub-packages:

- ``example/`` — A reference implementation (a VINCE case reader) showing
  how to implement a connector plugin.
"""

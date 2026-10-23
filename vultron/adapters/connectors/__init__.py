"""
Connector adapters (bidirectional — tracker and third-party integrations).

Connectors translate between external system events and Vultron domain
events. Unlike driving/driven adapters, connectors may both receive events
from and push events to external systems (e.g., issue trackers, mailing
lists, vulnerability databases).

Modules:

- ``base.py``    — ``ConnectorPlugin`` Protocol defining the plugin interface.
- ``loader.py``  — Entry-point–based plugin discovery and registration.

Sub-packages:

- ``example/`` — Reference implementations (Jira, VINCE) showing how to
  implement a connector plugin.
"""

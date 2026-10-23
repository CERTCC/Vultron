"""
Connector plugin loader — stub.

Discovers and registers ``ConnectorPlugin`` implementations via Python
entry points under the ``vultron.connectors`` group.

Future implementation will use ``importlib.metadata.entry_points`` to
enumerate installed plugins, validate them against the ``ConnectorPlugin``
Protocol, and make them available to the adapter layer at startup.

Example ``pyproject.toml`` entry for a third-party plugin::

    [project.entry-points."vultron.connectors"]
    my_tracker = "my_package.connectors:MyTrackerConnector"
"""

"""
Connector plugin loader — stub.

Discovers and registers connector plugins via Python entry points under the
``vultron.connectors`` group (ARCH-05-003).

Future implementation (#5610) will use ``importlib.metadata.entry_points``
to enumerate installed plugins, ask
:func:`~vultron.adapters.connectors.base.ports_implemented_by` which core
ports each implements, refuse one that implements none with an error naming
its entry point (ARCH-05-006), and make the rest available to the adapter
layer at startup.

Example ``pyproject.toml`` entry for a third-party plugin::

    [project.entry-points."vultron.connectors"]
    my_tracker = "my_package.connectors:MyTrackerCaseReader"
"""

"""
Activity store driven adapter — stub.

Concrete implementation of the ``core/ports/activity_store.py`` port
interface for persisting and fetching ActivityStreams activities.

The current TinyDB-backed implementation lives in
``vultron/api/v2/datalayer/``. This module is reserved for the relocation
of that implementation into the driven adapter layer as part of the
PRIORITY 70 DataLayer refactor.

See ``plan/PRIORITIES.md`` PRIORITY 70 and
``notes/architecture-ports-and-adapters.md`` for details.
"""

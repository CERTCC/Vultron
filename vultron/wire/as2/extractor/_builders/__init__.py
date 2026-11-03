"""Private domain-object builder helpers for the Vultron extractor.

Converts raw AS2 wire objects to core domain model instances.  All
functions here are internal implementation details of
``vultron.wire.as2.extractor``; callers should use ``extract_intent``
from ``_extract.py`` (or the ``vultron.semantic_registry.extract_event``
convenience wrapper) rather than calling these builders directly.

The builders are grouped by concern: ``fields`` (id, type and timestamp
readers), ``statuses`` (status objects), ``objects`` (the other per-type
builders), ``object_kwargs`` (the activity snapshot and dispatch) and
``semantic_kwargs`` (the kwargs particular semantics add).
"""

from vultron.wire.as2.extractor._builders.fields import termination_of
from vultron.wire.as2.extractor._builders.objects import proposed_embargo_from

__all__ = ["proposed_embargo_from", "termination_of"]

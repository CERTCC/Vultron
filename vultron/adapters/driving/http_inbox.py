"""
HTTP inbox driving adapter — stub.

Translates FastAPI inbox POST requests into core use-case calls by routing
through the wire/as2 parsing and semantic extraction pipeline.

Pipeline (future implementation):

1. Deserialize raw JSON → AS2 types  (``wire/as2/parser.py``)
2. Rehydrate URI references           (``wire/as2/rehydration.py``)
3. Extract MessageSemantics           (``wire/as2/extractor.py``)
4. Dispatch to use-case callable      (``core/use_cases/``)
5. Return HTTP 202 Accepted

The current HTTP inbox lives in ``vultron/api/v2/routers/actors.py``.
This module is reserved for the future relocation of that logic into the
adapter layer as part of the hexagonal architecture refactor (PRIORITY 60+).
"""

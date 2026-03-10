"""
Delivery queue driven adapter — stub.

Concrete implementation of the ``core/ports/delivery_queue.py`` port
interface for enqueuing outbound ActivityStreams activities.

Future implementation will back the queue with an in-process asyncio
queue (development) or a durable message broker (production).

The current placeholder outbox stub lives in
``vultron/api/v2/backend/actor_io.py``. This module is reserved for the
real implementation as part of the OUTBOX-1 work.

See ``plan/IMPLEMENTATION_PLAN.md`` Phase OUTBOX-1 for task details.
"""

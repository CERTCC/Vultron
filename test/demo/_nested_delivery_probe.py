#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Probe: does an in-process delivery chain finish when it outgrows the pool?

Run as ``python -m test.demo._nested_delivery_probe``, never collected.  A
deadlock here cannot be undone in-process: a ``TestClient`` whose app is stuck
never closes, so the test that asks the question runs this in a child process
and reads its exit status (#6190).

The chain models what the rv demo does.  Each hop's inbox route queues a
background task that delivers to the next hop through
:class:`~vultron.demo.in_process.InProcessRouter`.  A ``TestClient`` POST
returns only once the target app *and its background tasks* finish, so every
hop still waiting holds the thread it posts from.  The probe shrinks the
portal loop's default AnyIO thread pool below the chain's depth: a router that
borrows its threads from that pool stops with every borrowed thread waiting on
a hop that needs one more.

Exit status: 0 when the last hop is reached, 1 when the chain stalls.
"""

import os
import sys
import threading
from typing import NoReturn

import anyio.to_thread
from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from vultron.demo.in_process import InProcessRouter

BASE = "http://hops.example"

#: Hops in the chain, and the default-pool threads the probe leaves the loop.
#: The depth only has to exceed the pool; both stay small so the probe is fast.
DEPTH = 6
POOL_TOKENS = 2

#: How long the chain gets to finish.  It takes well under a second idle.
WAIT_SECONDS = 15.0


def _chain_app(router: InProcessRouter, reached: threading.Event) -> FastAPI:
    app = FastAPI()

    @app.post("/hop/{n}/inbox/", status_code=202)
    async def hop(n: int, background: BackgroundTasks) -> dict[str, int]:
        if n == 0:
            reached.set()
        else:
            background.add_task(
                router.emit,
                f"urn:probe:hop:{n}",
                "{}",
                [f"{BASE}/hop/{n - 1}"],
            )
        return {"hop": n}

    return app


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.stderr.flush()
    # A stalled app never lets its TestClient close, so leave without it.
    os._exit(1)


def main() -> int:
    """Run the chain; return 0 if its last hop is reached in time."""
    router = InProcessRouter()
    reached = threading.Event()
    client = TestClient(_chain_app(router, reached), base_url=BASE)
    client.__enter__()
    router.register(BASE, client)

    async def _shrink_pool() -> None:
        limiter = anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens = POOL_TOKENS

    assert client.portal is not None
    client.portal.call(_shrink_pool)

    poster = threading.Thread(
        target=client.post, args=(f"/hop/{DEPTH}/inbox/",), daemon=True
    )
    poster.start()
    poster.join(WAIT_SECONDS)
    if poster.is_alive():
        # Still waiting on the chain: a stall.
        _fail(
            f"delivery chain of {DEPTH} hops stalled with a pool of"
            f" {POOL_TOKENS} threads"
        )
    if not reached.is_set():
        # The chain returned, but a hop was dropped (emit logs and drops a
        # failed delivery), so the last hop was never reached.
        _fail(
            f"delivery chain of {DEPTH} hops returned without reaching hop 0"
        )
    client.__exit__(None, None, None)
    return 0


if __name__ == "__main__":
    sys.exit(main())

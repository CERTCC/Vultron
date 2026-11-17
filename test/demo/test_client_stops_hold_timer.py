#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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
"""The demo ``client`` fixture leaves no hold timer running (#6148).

The fixture is module-scoped, so the app it starts outlives every test in
the module, and the root conftest disposes the actor stores after each one.
A hold timer left running reads those stores from the app's loop thread
while they are closed, which segfaults the worker.
"""

from fastapi.testclient import TestClient

from vultron.adapters.driving.fastapi.sender_sequence_holds import (
    running_sender_sequence_hold_timers,
)


def test_the_demo_client_has_stopped_the_hold_timer_before_any_test(
    client: TestClient,
):
    assert running_sender_sequence_hold_timers() == []

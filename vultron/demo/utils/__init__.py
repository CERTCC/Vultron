"""
Shared utilities for Vultron demo scripts.

Provides context managers, HTTP client helpers, and common setup/teardown
functions used across all demo scripts (DC-02-001).
"""

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

from vultron.demo.utils.case_actor import (
    CASE_ACTOR_SLUG,
    bound_case_actor_client,
    case_actor_id_for_report,
    case_actor_id_on,
    configured_case_actor_id,
    seed_case_actor,
)
from vultron.demo.utils.client import (
    BASE_URL,
    DataLayerClient,
    case_references_report,
    logfmt,
    postfmt,
    ref_id,
    reset_datalayer,
)
from vultron.demo.utils.environment import (
    check_server_availability,
    demo_environment,
    discover_actors,
    init_actor_ios,
    seed_actor,
    seed_exchange_actors,
    seed_peer,
    setup_clean_environment,
    setup_demo_logging,
)
from vultron.demo.utils.failures import (
    assert_demo_success,
    demo_check,
    demo_failures,
    demo_gate,
    demo_step,
    reset_demo_failures,
)
from vultron.demo.utils.inbox import (
    post_to_inbox_and_wait,
    post_to_trigger,
    read_stored_of_types,
    verify_object_stored,
)
from vultron.demo.utils.received import (
    RECEIVED_ACTIVITY_RECORD_TYPE,
    get_offer_from_datalayer,
    log_case_state,
    not_received_error,
    read_received_activities,
    read_received_activity,
    received_activity_in,
    received_activity_or_none,
    require_received_activity,
    served_field,
    verify_received_activity_stored,
)

__all__ = [
    "BASE_URL",
    "CASE_ACTOR_SLUG",
    "DataLayerClient",
    "RECEIVED_ACTIVITY_RECORD_TYPE",
    "assert_demo_success",
    "bound_case_actor_client",
    "case_actor_id_for_report",
    "case_actor_id_on",
    "case_references_report",
    "check_server_availability",
    "configured_case_actor_id",
    "demo_check",
    "demo_environment",
    "demo_failures",
    "demo_gate",
    "demo_step",
    "discover_actors",
    "get_offer_from_datalayer",
    "init_actor_ios",
    "log_case_state",
    "logfmt",
    "not_received_error",
    "post_to_inbox_and_wait",
    "post_to_trigger",
    "postfmt",
    "read_received_activities",
    "read_received_activity",
    "read_stored_of_types",
    "received_activity_in",
    "received_activity_or_none",
    "ref_id",
    "require_received_activity",
    "reset_datalayer",
    "reset_demo_failures",
    "seed_actor",
    "seed_case_actor",
    "seed_exchange_actors",
    "seed_peer",
    "served_field",
    "setup_clean_environment",
    "setup_demo_logging",
    "verify_object_stored",
    "verify_received_activity_stored",
]

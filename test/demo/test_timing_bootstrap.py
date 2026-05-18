"""Temporary timing test for bootstrap timing debugging."""

import time
import types
import pytest
import cProfile
import pstats
import io

from test.demo.conftest import _TestASGIRouter, create_isolated_actor_app
from test.demo._helpers import make_testclient_call
import vultron.demo.scenario.two_actor_demo as demo
from vultron.demo.utils import DataLayerClient


@pytest.fixture
def bootstrap_setup():
    router = _TestASGIRouter()
    owner_iso = create_isolated_actor_app(
        base_url="http://owner-bt.test", router=router
    )
    participant_iso = create_isolated_actor_app(
        base_url="http://part-bt.test", router=router
    )
    with owner_iso.client as owner_tc:
        with participant_iso.client as participant_tc:
            for iso in (owner_iso, participant_iso):
                emitter = getattr(iso.app.state, "emitter", None)
                if hasattr(emitter, "_http_fallback"):
                    emitter._http_fallback = router
            yield owner_iso, participant_iso, owner_tc, participant_tc


@pytest.mark.integration
def test_timing_steps(bootstrap_setup):
    owner_iso, participant_iso, owner_tc, participant_tc = bootstrap_setup
    owner_base = owner_iso.base_url + "/api/v2"
    part_base = participant_iso.base_url + "/api/v2"
    owner_id = f"{owner_base}/actors/owner-timing"
    part_id = f"{part_base}/actors/part-timing"

    # Create actors
    owner_tc.post(
        "/api/v2/actors/",
        json={"id": owner_id, "name": "Owner", "type": "Organization"},
    )
    participant_tc.post(
        "/api/v2/actors/",
        json={"id": part_id, "name": "Participant", "type": "Organization"},
    )
    owner_tc.post(
        "/api/v2/actors/",
        json={"id": part_id, "name": "Participant", "type": "Organization"},
    )
    participant_tc.post(
        "/api/v2/actors/",
        json={"id": owner_id, "name": "Owner", "type": "Organization"},
    )

    # Build DataLayerClient wrappers
    owner_dc = DataLayerClient(base_url=owner_base)
    part_dc = DataLayerClient(base_url=part_base)
    object.__setattr__(
        owner_dc,
        "call",
        types.MethodType(make_testclient_call(owner_tc, owner_base), owner_dc),
    )
    object.__setattr__(
        part_dc,
        "call",
        types.MethodType(
            make_testclient_call(participant_tc, part_base), part_dc
        ),
    )

    owner_actor = demo.get_actor_by_id(owner_dc, owner_id)
    part_actor = demo.get_actor_by_id(part_dc, part_id)

    # Submit report
    _report, offer = demo.finder_submits_report(
        vendor_client=owner_dc, finder=part_actor, vendor=owner_actor
    )

    # Profile validate report
    pr = cProfile.Profile()
    pr.enable()
    t = time.time()
    owner_actor_fresh = demo.get_actor_by_id(owner_dc, owner_id)
    demo.vendor_validates_report(
        vendor_client=owner_dc, vendor=owner_actor_fresh, offer_id=offer.id_
    )
    elapsed = time.time() - t
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(20)
    print(f"\nValidate report: {elapsed:.3f}s")
    print(s.getvalue())

"""The dashboard's badges and labels: every state has a badge, every
event a label, and an actor reads by its name (#6366).
"""

from test.shadow.dashboard.view._support import NAMES, VENDOR
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.baselines import EventKind
from vultron.measure.ledger import UNNAMED_ACTOR
from vultron.measure.standing import DesideratumStatus
from vultron.shadow.dashboard import view


def test_every_state_and_status_has_a_badge():
    assert set(view.RM_BADGES) == set(RM)
    assert set(view.EM_BADGES) == set(EM)
    assert set(view.DESIDERATUM_BADGES) == set(DesideratumStatus)
    assert set(view.EVENT_LABELS) == set(CSEvent)
    assert set(view.DESIDERATUM_EVENT_LABELS) == set(EventKind)


def test_an_actor_with_no_name_reads_by_its_uri_or_as_unnamed():
    assert view.actor_label(VENDOR, NAMES) == "Vendor"
    assert view.actor_label("https://example.org/actors/reporter", {}) == (
        "Reporter"
    )
    assert view.actor_label(
        "urn:uuid:1e7a421f-b727-4c1d-9a3e-0f6b2c9d8e71", {}
    ) == (UNNAMED_ACTOR)

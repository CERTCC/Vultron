"""
Fixtures for test/core/behaviors/case tests.

Imports VulnerabilityCase (and related wire-layer types) as a side effect so
that the global vocabulary registry is populated before any test in this
directory runs.  Without this import the registry may be empty when tests run
in isolation, causing TinyDB's record_to_object() to fall back to returning a
raw Document instead of a deserialized domain object.

Shared fixtures for receive-report case-tree tests are also defined here so
that multiple tree test files can reuse them without redefinition.
"""

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase,
)

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.vultron_types import VultronCaseActor
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


@pytest.fixture
def datalayer():
    """In-memory SQLite data layer for testing."""
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def actor_id():
    """Vendor (receiver) actor ID."""
    return "https://example.org/actors/vendor"


@pytest.fixture
def reporter_actor_id():
    """Reporter actor ID."""
    return "https://example.org/actors/reporter"


@pytest.fixture
def actor(datalayer, actor_id):
    """Create vendor actor in the DataLayer with an outbox."""
    obj = VultronCaseActor(id_=actor_id, name="Vendor Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def reporter_actor(datalayer, reporter_actor_id):
    """Create reporter actor in the DataLayer."""
    obj = VultronCaseActor(id_=reporter_actor_id, name="Reporter Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def report(datalayer):
    """Create test VulnerabilityReport."""
    obj = VulnerabilityReport(
        id_="https://example.org/reports/CVE-2024-001",
        name="Test Vulnerability Report",
        content="Buffer overflow in component X",
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def reporter_accepted_status(datalayer, reporter_actor_id, report):
    """Pre-create the reporter's RM.ACCEPTED report-phase status record.

    SubmitReportReceivedUseCase creates this record before the tree runs.
    """
    status = ParticipantStatus(
        id_=_report_phase_status_id(
            reporter_actor_id, report.id_, RM.ACCEPTED.value
        ),
        context=report.id_,
        attributed_to=reporter_actor_id,
        rm_state=RM.ACCEPTED,
    )
    datalayer.create(status)
    return status


@pytest.fixture
def vendor_received_status(datalayer, actor_id, report):
    """Pre-create the vendor's RM.RECEIVED report-phase status record.

    CreateReportReceivedUseCase or AckReportReceivedUseCase creates this
    record before the tree runs.
    """
    status = ParticipantStatus(
        id_=_report_phase_status_id(actor_id, report.id_, RM.RECEIVED.value),
        context=report.id_,
        attributed_to=actor_id,
        rm_state=RM.RECEIVED,
    )
    datalayer.create(status)
    return status


@pytest.fixture
def offer(datalayer, report, actor_id, reporter_actor_id):
    """Create test Offer activity (reporter submits report to vendor)."""
    obj = rm_submit_report_activity(
        report=report,
        actor=reporter_actor_id,
        to=actor_id,
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def bridge(datalayer):
    """BT bridge for tree execution (includes TriggerActivityAdapter)."""
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    return BTBridge(
        datalayer=datalayer, trigger_activity=TriggerActivityAdapter(datalayer)
    )

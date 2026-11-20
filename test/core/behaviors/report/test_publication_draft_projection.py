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
"""The publication draft step drafts the case's public CSAF projection.

The DETERMINISTIC ``DraftAdvisoryArtifact`` backend cuts the case with the
public profile and renders it, with ``tracking.status`` ``final``, through
the ``case_projection_port`` the run places on the blackboard (ADR-0219,
BT-20-004).
"""

import json
from collections.abc import Iterator
from typing import Any

import py_trees
import pytest
from py_trees.common import Status

from test.support.act_runner import run_tree
from test.support.call_out import tick_call_out
from test.support.case_projection import (
    CASE_ID,
    COORDINATOR,
    JOINED_ONLY_UNRENDERED,
    JOINED_ONLY_VALUES,
    publication_draft_run,
    store_projected_replica,
)
from test.support.csaf_schema import schema_errors
from vultron.adapters.driven import case_projection as projection_adapters
from vultron.adapters.driven.case_projection import CsafProjectionAdapter
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.datalayer_sqlite.engine import fresh_memory_url
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out import unwrap_call_out
from vultron.core.behaviors.call_out.bundles.publication import (
    DraftAdvisoryArtifactByProjection,
)
from vultron.core.behaviors.report.advisory_review import (
    DRAFT_ARTIFACT_KEY,
    REVIEW_DECISION_KEY,
    AdvisoryReviewDecision,
)
from vultron.core.behaviors.report.publication_tree import (
    create_publication_tree,
)
from vultron.core.behaviors.report.publish_artifact_tree import (
    create_publish_artifact_tree,
)
from vultron.core.models.case_projection_profile import PUBLIC_PROFILE
from vultron.core.models.ledger_position import LedgerPosition
from vultron.errors import VultronWiringError


class _Capture(py_trees.behaviour.Behaviour):
    """Record the draft and the review decision once the tree has run."""

    def __init__(self, seen: dict[str, Any]) -> None:
        super().__init__(name="CaptureDraft")
        self._seen = seen

    def update(self) -> Status:
        storage = py_trees.blackboard.Blackboard.storage
        for key in (DRAFT_ARTIFACT_KEY, REVIEW_DECISION_KEY):
            self._seen[key] = storage.get(f"/{key}")
        return Status.SUCCESS


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    py_trees.blackboard.Blackboard.storage.clear()
    with SqliteDataLayer(
        fresh_memory_url("publication-draft"), actor_id=COORDINATOR
    ) as store:
        yield store
    py_trees.blackboard.Blackboard.storage.clear()


def _run(
    dl: SqliteDataLayer, tree: py_trees.behaviour.Behaviour, port: object
) -> tuple[Any, dict[str, Any]]:
    seen: dict[str, Any] = {}
    root = py_trees.composites.Sequence(
        name="Run", memory=False, children=[tree, _Capture(seen)]
    )
    bridge = BTBridge(datalayer=dl, case_projection_port=port)  # type: ignore[arg-type]
    result = run_tree(bridge, root, COORDINATOR, case_id=CASE_ID)
    return result, seen


def _draft(seen: dict[str, Any]) -> dict[str, Any]:
    text = seen[DRAFT_ARTIFACT_KEY]
    assert isinstance(text, str)
    document: dict[str, Any] = json.loads(text)
    return document


@pytest.mark.spec("CSAF-06-012")
@pytest.mark.spec("CSAF-06-004")
@pytest.mark.spec("BT-20-004")
def test_the_publication_tree_drafts_a_schema_valid_public_projection(
    dl: SqliteDataLayer,
) -> None:
    store_projected_replica(dl)

    result, seen = _run(
        dl, create_publication_tree(case_id=CASE_ID), CsafProjectionAdapter()
    )

    assert result.status == Status.SUCCESS, result.feedback_message
    draft = _draft(seen)
    assert schema_errors(draft) == []
    document = draft["document"]
    assert document["category"] == "csaf_base"
    assert document["tracking"]["status"] == "final"
    assert document["distribution"]["tlp"]["label"] == (
        PUBLIC_PROFILE.distribution.value
    )
    assert f"/{PUBLIC_PROFILE.name}/" in document["tracking"]["id"]


@pytest.mark.spec("CSAF-06-012")
@pytest.mark.parametrize(
    "value",
    [
        JOINED_ONLY_VALUES["content"],
        JOINED_ONLY_VALUES["report"],
        *JOINED_ONLY_UNRENDERED.values(),
    ],
)
def test_the_public_draft_holds_none_of_the_joined_only_content(
    dl: SqliteDataLayer, value: str
) -> None:
    """The draft is the public cut: no value only the joined profile
    includes appears in it."""
    store_projected_replica(dl)

    _, seen = _run(
        dl,
        create_publish_artifact_tree(case_id=CASE_ID),
        CsafProjectionAdapter(),
    )

    assert value not in seen[DRAFT_ARTIFACT_KEY]


@pytest.mark.spec("CSAF-06-002")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "CSAF-06-002: the public draft's default credit names the REPORTER"
        " participants, which the public profile omits, because CSAF-06-009"
        " makes them the default at every call site. Tracked by #6706."
    ),
)
def test_the_public_draft_names_no_reporter_participant(
    dl: SqliteDataLayer,
) -> None:
    store_projected_replica(dl)

    _, seen = _run(
        dl,
        create_publish_artifact_tree(case_id=CASE_ID),
        CsafProjectionAdapter(),
    )

    assert JOINED_ONLY_VALUES["reporter_name"] not in seen[DRAFT_ARTIFACT_KEY]


@pytest.mark.spec("BT-23-013")
def test_the_deterministic_defaults_write_the_draft_and_the_review(
    dl: SqliteDataLayer,
) -> None:
    """No stand-in writes a key: the defaults give the draft and a review
    that asks for no revision, so the revision arm is skipped on the gate's
    read of a written record, not on a missing one."""
    store_projected_replica(dl)

    result, seen = _run(
        dl,
        create_publish_artifact_tree(case_id=CASE_ID),
        CsafProjectionAdapter(),
    )

    assert result.status == Status.SUCCESS
    assert isinstance(seen[DRAFT_ARTIFACT_KEY], str)
    decision = seen[REVIEW_DECISION_KEY]
    assert isinstance(decision, AdvisoryReviewDecision)
    assert decision.needs_revision is False


@pytest.mark.spec("CSAF-06-004")
def test_the_draft_takes_its_category_from_the_shared_selection(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_projected_replica(dl)
    asked: list[object] = []

    def selection(preview: object) -> str:
        asked.append(preview)
        return "csaf_base"

    monkeypatch.setattr(projection_adapters.csaf, "csaf_category", selection)

    _run(
        dl,
        create_publish_artifact_tree(case_id=CASE_ID),
        CsafProjectionAdapter(),
    )

    (preview,) = asked
    assert getattr(preview, "id_", None) == CASE_ID


def test_the_default_draft_backend_is_the_projection() -> None:
    tree = create_publish_artifact_tree(case_id=CASE_ID)

    assert isinstance(
        unwrap_call_out(tree.children[0]), DraftAdvisoryArtifactByProjection
    )


def test_a_missing_projection_port_is_a_wiring_error(
    dl: SqliteDataLayer,
) -> None:
    """No fallback draft: the run fails as an internal error."""
    store_projected_replica(dl)

    result, seen = _run(
        dl, create_publish_artifact_tree(case_id=CASE_ID), None
    )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "case_projection_port" in result.feedback_message
    assert seen == {}


def test_a_case_the_store_does_not_hold_fails_the_draft(
    dl: SqliteDataLayer,
) -> None:
    """The backend could not draft: an *error*, which fails the run as an
    internal error, not a refusal, and no draft is written (ADR-0183)."""
    result, seen = _run(
        dl,
        create_publish_artifact_tree(case_id=CASE_ID),
        CsafProjectionAdapter(),
    )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "drafting the public projection" in result.feedback_message
    assert seen == {}


def test_a_replica_it_cannot_project_fails_the_draft_as_an_error(
    dl: SqliteDataLayer,
) -> None:
    """A replica without the entry at its position cannot be dated, so the
    draft is an *error*, not a refusal."""
    case = store_projected_replica(dl)
    case.ledger_position = LedgerPosition(log_index=9, entry_hash="09" * 32)
    dl.save(case)

    result, seen = _run(
        dl,
        create_publish_artifact_tree(case_id=CASE_ID),
        CsafProjectionAdapter(),
    )

    assert result.status == Status.FAILURE
    assert result.internal_error is True
    assert "ledger index 9" in result.feedback_message
    assert seen == {}


@pytest.mark.parametrize("missing", ["/datalayer", "/actor_id"])
def test_a_run_without_its_store_or_actor_is_a_wiring_error(
    missing: str,
) -> None:
    with publication_draft_run():
        py_trees.blackboard.Blackboard.storage.pop(missing)
        backend = DraftAdvisoryArtifactByProjection("Draft")

        with pytest.raises(VultronWiringError, match="DataLayer or actor_id"):
            tick_call_out(backend)
    py_trees.blackboard.Blackboard.storage.clear()

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

"""Unit tests for the precondition guards in the fix-lifecycle helpers.

verify_fix_ready requires CVDRole.VENDOR (DEMOMA-15-001).
verify_fix_deployed requires CVDRole.DEPLOYER (VENDOR-only actors do not pass,
DEMOMA-15-002).
verify_stops_at_fix_ready requires CVDRole.VENDOR and not CVDRole.DEPLOYER
(DEMOMA-15-004), and asserts the absence of a fix-deployed state on both
replicas (DEMOMA-15-005).

These tests exercise the guard in isolation using mocked _fetch_participant
calls, without spinning up a FastAPI server.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from vultron.core.states.cs import CS_d
from vultron.demo.helpers.milestones import (
    verify_fix_deployed,
    verify_fix_ready,
    verify_stops_at_fix_ready,
)
from vultron.enums.roles import CVDRole

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VENDOR_ACTOR_ID = "http://vendor:7999/api/v2/actors/vendor"
_COORDINATOR_ACTOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
_DEPLOYER_ACTOR_ID = "http://deployer:7999/api/v2/actors/deployer"
_CASE_ID = "urn:uuid:test-case-0001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_participant_mock(roles: list[CVDRole]) -> MagicMock:
    """Return a mock as_CaseParticipant with the given case_roles."""
    p = MagicMock()
    object.__setattr__(p, "case_roles", roles)
    return p


# ---------------------------------------------------------------------------
# Tests for verify_fix_ready
# ---------------------------------------------------------------------------


class TestVerifyFixReadyVendorGuard:
    """DEMOMA-15-001: verify_fix_ready raises when actor is not a VENDOR."""

    def test_non_vendor_actor_raises_assertionerror(self):
        """Passing a Coordinator actor ID raises AssertionError."""
        participant = _make_participant_mock([CVDRole.COORDINATOR])

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_ready(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _COORDINATOR_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert _COORDINATOR_ACTOR_ID in msg
        assert "CVDRole.VENDOR" in msg

    def test_non_vendor_error_includes_actual_roles(self):
        """AssertionError message includes the actor's actual roles."""
        participant = _make_participant_mock(
            [CVDRole.COORDINATOR, CVDRole.CASE_MANAGER]
        )

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_ready(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _COORDINATOR_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert "CVDRole.VENDOR" in msg

    def test_vendor_actor_does_not_raise_guard(self):
        """A VENDOR actor passes the guard (state check proceeds normally)."""
        participant = _make_participant_mock([CVDRole.VENDOR])

        with (
            patch(
                "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
                return_value=participant,
            ),
            patch(
                "vultron.demo.helpers.milestones.lifecycle._check_participant_vf_state_in"
            ),
            patch(
                "vultron.demo.helpers.milestones.lifecycle._check_participant_rm_state_in"
            ),
        ):
            # Should not raise
            verify_fix_ready(
                MagicMock(),
                MagicMock(),
                _CASE_ID,
                _VENDOR_ACTOR_ID,
            )

    def test_missing_participant_raises(self):
        """If the actor is not found in the case, AssertionError is raised."""
        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=None,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_ready(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _VENDOR_ACTOR_ID,
                )

        assert _VENDOR_ACTOR_ID in str(exc_info.value)

    def test_case_owner_only_raises_assertionerror(self):
        """CASE_OWNER alone raises AssertionError (the CI regression scenario)."""
        participant = _make_participant_mock([CVDRole.CASE_OWNER])

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_ready(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _VENDOR_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert _VENDOR_ACTOR_ID in msg
        assert "CVDRole.VENDOR" in msg

    def test_vendor_with_case_owner_passes_guard(self):
        """VENDOR + CASE_OWNER (the real demo scenario after the fix) passes."""
        participant = _make_participant_mock(
            [CVDRole.VENDOR, CVDRole.CASE_OWNER]
        )

        with (
            patch(
                "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
                return_value=participant,
            ),
            patch(
                "vultron.demo.helpers.milestones.lifecycle._check_participant_vf_state_in"
            ),
            patch(
                "vultron.demo.helpers.milestones.lifecycle._check_participant_rm_state_in"
            ),
        ):
            verify_fix_ready(
                MagicMock(),
                MagicMock(),
                _CASE_ID,
                _VENDOR_ACTOR_ID,
            )


# ---------------------------------------------------------------------------
# Tests for verify_fix_deployed
# ---------------------------------------------------------------------------


class TestVerifyFixDeployedDeployerGuard:
    """DEMOMA-15-001: verify_fix_deployed requires CVDRole.DEPLOYER.

    VENDOR-only actors do not pass — a VENDOR without DEPLOYER can never
    reach VFD (CSB-15-002), so accepting VENDOR here would produce a
    confusing state-check failure instead of a clear role-check failure.
    """

    def test_coordinator_raises_assertionerror(self):
        """Passing a Coordinator actor ID raises AssertionError."""
        participant = _make_participant_mock([CVDRole.COORDINATOR])

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_deployed(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _COORDINATOR_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert _COORDINATOR_ACTOR_ID in msg
        assert "CVDRole.DEPLOYER" in msg

    def test_non_deployer_error_includes_actual_roles(self):
        """AssertionError message includes the actor's actual roles."""
        participant = _make_participant_mock([CVDRole.REPORTER])

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_deployed(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _COORDINATOR_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert "CVDRole.DEPLOYER" in msg

    def test_vendor_only_raises_assertionerror(self):
        """VENDOR-only actor raises AssertionError (CSB-15-002: stops at VFd)."""
        participant = _make_participant_mock([CVDRole.VENDOR])

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_deployed(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _VENDOR_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert _VENDOR_ACTOR_ID in msg
        assert "CVDRole.DEPLOYER" in msg

    def test_case_owner_only_raises_assertionerror(self):
        """CASE_OWNER alone raises AssertionError."""
        participant = _make_participant_mock([CVDRole.CASE_OWNER])

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_deployed(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _VENDOR_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert _VENDOR_ACTOR_ID in msg
        assert "CVDRole.DEPLOYER" in msg

    def test_missing_participant_raises(self):
        """If the actor is not found in the case, AssertionError is raised."""
        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=None,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_deployed(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _DEPLOYER_ACTOR_ID,
                )

        assert _DEPLOYER_ACTOR_ID in str(exc_info.value)

    def test_deployer_only_passes_guard(self):
        """DEPLOYER-only actor passes the guard (state check proceeds normally)."""
        participant = _make_participant_mock([CVDRole.DEPLOYER])

        with (
            patch(
                "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
                return_value=participant,
            ),
            patch(
                "vultron.demo.helpers.milestones.lifecycle._check_participant_d_state_in"
            ),
        ):
            verify_fix_deployed(
                MagicMock(),
                MagicMock(),
                _CASE_ID,
                _DEPLOYER_ACTOR_ID,
            )

    def test_vendor_and_deployer_passes_guard(self):
        """VENDOR+DEPLOYER actor passes the guard — the V2 case in RCVCV."""
        participant = _make_participant_mock(
            [CVDRole.VENDOR, CVDRole.DEPLOYER]
        )

        with (
            patch(
                "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
                return_value=participant,
            ),
            patch(
                "vultron.demo.helpers.milestones.lifecycle._check_participant_d_state_in"
            ),
        ):
            verify_fix_deployed(
                MagicMock(),
                MagicMock(),
                _CASE_ID,
                _DEPLOYER_ACTOR_ID,
            )


class TestVerifyFixReadyDeployerGuard:
    """verify_fix_ready raises for DEPLOYER-only actor (no VENDOR)."""

    def test_deployer_only_raises_assertionerror(self):
        """DEPLOYER-only actor raises AssertionError in verify_fix_ready.

        verify_fix_ready uses _assert_vendor_role which requires CVDRole.VENDOR.
        A DEPLOYER-only actor does not hold VENDOR and must be rejected.
        """
        participant = _make_participant_mock([CVDRole.DEPLOYER])

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_fix_ready(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _DEPLOYER_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert "CVDRole.VENDOR" in msg


# ---------------------------------------------------------------------------
# Tests for verify_stops_at_fix_ready (DEMOMA-15-004)
# ---------------------------------------------------------------------------


class TestVerifyStopsAtFixReadyGuard:
    """DEMOMA-15-004: the ceiling claim needs VENDOR and not DEPLOYER.

    The helper asserts a participant stops at VFd, which is true of a
    VENDOR without DEPLOYER (CSB-15-002) and not of one that has a deploy
    path: for a DEPLOYER the same read says only "it has not deployed yet",
    which a later deployment falsifies.
    """

    @pytest.mark.spec("DEMOMA-15-004")
    def test_non_vendor_raises_assertionerror(self):
        """A Coordinator makes no fix-path claim at all."""
        participant = _make_participant_mock([CVDRole.COORDINATOR])

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_stops_at_fix_ready(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _COORDINATOR_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert _COORDINATOR_ACTOR_ID in msg
        assert "CVDRole.VENDOR" in msg

    @pytest.mark.spec("DEMOMA-15-004")
    def test_vendor_that_is_also_a_deployer_raises_assertionerror(self):
        """A DEPLOYER has a deploy path, so it does not stop at VFd."""
        participant = _make_participant_mock(
            [CVDRole.VENDOR, CVDRole.DEPLOYER]
        )

        with patch(
            "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
            return_value=participant,
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_stops_at_fix_ready(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _DEPLOYER_ACTOR_ID,
                )

        msg = str(exc_info.value)
        assert _DEPLOYER_ACTOR_ID in msg
        assert "CVDRole.DEPLOYER" in msg

    @pytest.mark.spec("DEMOMA-15-005")
    def test_vendor_only_actor_is_read_on_both_replicas(self):
        """Both replicas are read for the absent fix-deployed transition."""
        participant = _make_participant_mock([CVDRole.VENDOR])
        receiver, reporter = MagicMock(), MagicMock()

        with (
            patch(
                "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
                return_value=participant,
            ),
            patch(
                "vultron.demo.helpers.milestones.lifecycle._check_participant_not_fix_deployed"
            ) as d_check,
        ):
            verify_stops_at_fix_ready(
                receiver,
                reporter,
                _CASE_ID,
                _VENDOR_ACTOR_ID,
            )

        assert [call.args[0] for call in d_check.call_args_list] == [
            receiver,
            reporter,
        ]

    @pytest.mark.spec("DEMOMA-15-005")
    def test_a_vendor_with_no_d_dimension_passes(self):
        """The claim is the absence of ``D``, not a ``d`` reading (#5602).

        A participant holding no DEPLOYER role carries no ``d`` dimension, so
        its D state reads as absent. Asserting ``d`` instead would fail on
        every vendor the milestone is actually about.
        """
        participant = _make_participant_mock([CVDRole.VENDOR])
        object.__setattr__(
            participant, "participant_status", SimpleNamespace(d=None)
        )

        with (
            patch(
                "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
                return_value=participant,
            ),
            patch(
                "vultron.demo.helpers.verification.states._fetch_participant",
                return_value=participant,
            ),
        ):
            verify_stops_at_fix_ready(
                MagicMock(),
                MagicMock(),
                _CASE_ID,
                _VENDOR_ACTOR_ID,
            )

    @pytest.mark.spec("DEMOMA-15-005")
    def test_a_vendor_that_did_deploy_fails(self):
        """A recorded ``D`` is what the milestone exists to refuse."""
        participant = _make_participant_mock([CVDRole.VENDOR])
        object.__setattr__(
            participant,
            "participant_status",
            SimpleNamespace(d=SimpleNamespace(state=CS_d.D)),
        )

        with (
            patch(
                "vultron.demo.helpers.milestones.lifecycle._fetch_participant",
                return_value=participant,
            ),
            patch(
                "vultron.demo.helpers.verification.states._fetch_participant",
                return_value=participant,
            ),
        ):
            with pytest.raises(AssertionError) as exc_info:
                verify_stops_at_fix_ready(
                    MagicMock(),
                    MagicMock(),
                    _CASE_ID,
                    _VENDOR_ACTOR_ID,
                )

        assert "fix-deployed" in str(exc_info.value)

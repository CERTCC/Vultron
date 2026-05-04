"""Unit tests for VultronParticipant role-management API (PRM-05-001–PRM-05-004)."""

import logging

import pytest

from vultron.core.models.participant import VultronParticipant
from vultron.core.states.roles import CVDRole

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACTOR = "https://example.org/actors/alice"
_CONTEXT = "https://example.org/cases/case-001"


def _make_participant(
    roles: list[CVDRole] | None = None,
) -> VultronParticipant:
    return VultronParticipant(
        attributed_to=_ACTOR,
        context=_CONTEXT,
        case_roles=roles or [],
    )


# ---------------------------------------------------------------------------
# roles property
# ---------------------------------------------------------------------------


class TestRolesProperty:
    """Tests for VultronParticipant.roles read-only property (PRM-01-001)."""

    def test_roles_returns_list(self):
        """roles property returns a list."""
        p = _make_participant()
        assert isinstance(p.roles, list)

    def test_roles_empty_when_no_roles(self):
        """roles is empty for a fresh participant."""
        p = _make_participant()
        assert p.roles == []

    def test_roles_reflects_case_roles(self):
        """roles property mirrors case_roles content."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        assert CVDRole.VENDOR in p.roles

    def test_roles_is_a_copy(self):
        """Mutating the returned list does not affect the participant."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        returned = p.roles
        returned.append(CVDRole.COORDINATOR)
        assert CVDRole.COORDINATOR not in p.roles

    def test_roles_returns_list_of_cvdrole(self):
        """roles property items are CVDRole instances."""
        p = _make_participant(roles=[CVDRole.FINDER, CVDRole.REPORTER])
        for role in p.roles:
            assert isinstance(role, CVDRole)


# ---------------------------------------------------------------------------
# has_role() (PRM-01-002)
# ---------------------------------------------------------------------------


class TestHasRole:
    """Tests for VultronParticipant.has_role() (PRM-05-003)."""

    def test_has_role_present_returns_true(self):
        """has_role() returns True when the role is held (PRM-05-003a)."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        assert p.has_role(CVDRole.VENDOR) is True

    def test_has_role_absent_returns_false(self):
        """has_role() returns False when the role is not held (PRM-05-003b)."""
        p = _make_participant()
        assert p.has_role(CVDRole.VENDOR) is False

    def test_has_role_after_add(self):
        """has_role() returns True after add_role() adds the role."""
        p = _make_participant()
        p.add_role(CVDRole.COORDINATOR)
        assert p.has_role(CVDRole.COORDINATOR) is True

    def test_has_role_after_remove(self):
        """has_role() returns False after remove_role() removes the role."""
        p = _make_participant(roles=[CVDRole.COORDINATOR])
        p.remove_role(CVDRole.COORDINATOR)
        assert p.has_role(CVDRole.COORDINATOR) is False


# ---------------------------------------------------------------------------
# add_role() (PRM-02-001 through PRM-02-003, PRM-05-001)
# ---------------------------------------------------------------------------


class TestAddRole:
    """Tests for VultronParticipant.add_role() (PRM-05-001)."""

    def test_add_role_new(self):
        """add_role() adds a new role to the participant (PRM-05-001a)."""
        p = _make_participant()
        p.add_role(CVDRole.VENDOR)
        assert CVDRole.VENDOR in p.roles

    def test_add_role_role_count_increases(self):
        """add_role() increases the role count when adding a new role."""
        p = _make_participant()
        p.add_role(CVDRole.VENDOR)
        assert len(p.roles) == 1

    def test_add_role_idempotent_no_exception(self):
        """add_role() is idempotent: re-adding does not raise (PRM-05-001b)."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        p.add_role(CVDRole.VENDOR)  # must not raise

    def test_add_role_idempotent_no_duplicate(self):
        """add_role() idempotent re-add leaves exactly one copy (PRM-05-001b)."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        p.add_role(CVDRole.VENDOR)
        assert p.roles.count(CVDRole.VENDOR) == 1

    def test_add_role_idempotent_logs_info(self, caplog):
        """add_role() logs at INFO when re-adding an existing role (PRM-05-001b)."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        with caplog.at_level(logging.INFO):
            p.add_role(CVDRole.VENDOR)
        assert "already present" in caplog.text

    def test_add_role_raise_when_present(self):
        """add_role(raise_when_present=True) raises KeyError (PRM-05-001c)."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        with pytest.raises(KeyError):
            p.add_role(CVDRole.VENDOR, raise_when_present=True)

    def test_add_role_raise_when_present_false_no_raise(self):
        """add_role(raise_when_present=False) does not raise (default)."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        p.add_role(CVDRole.VENDOR, raise_when_present=False)  # no exception

    def test_add_role_multiple_distinct_roles(self):
        """add_role() can add multiple distinct roles."""
        p = _make_participant()
        p.add_role(CVDRole.FINDER)
        p.add_role(CVDRole.REPORTER)
        assert CVDRole.FINDER in p.roles
        assert CVDRole.REPORTER in p.roles
        assert len(p.roles) == 2


# ---------------------------------------------------------------------------
# remove_role() (PRM-02-004 through PRM-02-006, PRM-05-002)
# ---------------------------------------------------------------------------


class TestRemoveRole:
    """Tests for VultronParticipant.remove_role() (PRM-05-002)."""

    def test_remove_role_present(self):
        """remove_role() removes a role that is held (PRM-05-002a)."""
        p = _make_participant(roles=[CVDRole.VENDOR])
        p.remove_role(CVDRole.VENDOR)
        assert CVDRole.VENDOR not in p.roles

    def test_remove_role_reduces_count(self):
        """remove_role() reduces role count by one."""
        p = _make_participant(roles=[CVDRole.VENDOR, CVDRole.COORDINATOR])
        p.remove_role(CVDRole.VENDOR)
        assert len(p.roles) == 1
        assert CVDRole.COORDINATOR in p.roles

    def test_remove_role_idempotent_no_exception(self):
        """remove_role() is idempotent: removing absent role does not raise (PRM-05-002b)."""
        p = _make_participant()
        p.remove_role(CVDRole.VENDOR)  # must not raise

    def test_remove_role_idempotent_logs_info(self, caplog):
        """remove_role() logs at INFO when removing an absent role (PRM-05-002b)."""
        p = _make_participant()
        with caplog.at_level(logging.INFO):
            p.remove_role(CVDRole.VENDOR)
        assert "not present" in caplog.text

    def test_remove_role_raise_when_missing(self):
        """remove_role(raise_when_missing=True) raises KeyError (PRM-05-002c)."""
        p = _make_participant()
        with pytest.raises(KeyError):
            p.remove_role(CVDRole.VENDOR, raise_when_missing=True)

    def test_remove_role_raise_when_missing_false_no_raise(self):
        """remove_role(raise_when_missing=False) does not raise (default)."""
        p = _make_participant()
        p.remove_role(CVDRole.VENDOR, raise_when_missing=False)  # no exception

    def test_remove_role_does_not_affect_other_roles(self):
        """remove_role() only removes the specified role."""
        p = _make_participant(roles=[CVDRole.VENDOR, CVDRole.DEPLOYER])
        p.remove_role(CVDRole.VENDOR)
        assert CVDRole.DEPLOYER in p.roles
        assert CVDRole.VENDOR not in p.roles

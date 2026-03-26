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

"""
Tests for VultronPerson, VultronOrganization, VultronService, and
VultronActorMixin (EP-01-001).
"""

import unittest

from vultron.wire.as2.enums import as_ActorType
from vultron.wire.as2.vocab.objects.embargo_policy import EmbargoPolicy
from vultron.wire.as2.vocab.objects.vultron_actor import (
    VultronActorMixin,
    VultronOrganization,
    VultronPerson,
    VultronService,
)

ACTOR_ID = "https://example.org/actors/vendor"
INBOX = "https://example.org/actors/vendor/inbox"


def _make_policy() -> EmbargoPolicy:
    return EmbargoPolicy(
        actor_id=ACTOR_ID,
        inbox=INBOX,
        preferred_duration_days=90,
        minimum_duration_days=45,
        maximum_duration_days=180,
        notes="Prefer 90 days.",
    )


class TestVultronPersonBasics(unittest.TestCase):
    """VultronPerson retains Person type and supports embargo_policy."""

    def test_as_type_is_person(self):
        p = VultronPerson(as_id="https://example.org/users/alice")
        self.assertEqual(as_ActorType.PERSON, p.as_type)

    def test_embargo_policy_defaults_to_none(self):
        p = VultronPerson(as_id="https://example.org/users/alice")
        self.assertIsNone(p.embargo_policy)

    def test_embargo_policy_inline_object(self):
        policy = _make_policy()
        p = VultronPerson(
            as_id="https://example.org/users/alice",
            embargo_policy=policy,
        )
        assert isinstance(p.embargo_policy, EmbargoPolicy)
        self.assertEqual(policy.as_id, p.embargo_policy.as_id)
        self.assertEqual(90, p.embargo_policy.preferred_duration_days)

    def test_embargo_policy_reference_string(self):
        policy_id = "https://example.org/policies/alice-ep"
        p = VultronPerson(
            as_id="https://example.org/users/alice",
            embargo_policy=policy_id,
        )
        self.assertEqual(policy_id, p.embargo_policy)

    def test_is_instance_of_mixin(self):
        p = VultronPerson()
        self.assertIsInstance(p, VultronActorMixin)

    def test_json_round_trip_no_policy(self):
        p = VultronPerson(
            name="Alice", as_id="https://example.org/users/alice"
        )
        j = p.to_json()
        self.assertIn("Person", j)
        self.assertNotIn("embargo_policy", j)

    def test_json_round_trip_with_inline_policy(self):
        policy = _make_policy()
        p = VultronPerson(
            name="Alice",
            as_id="https://example.org/users/alice",
            embargo_policy=policy,
        )
        j = p.to_json()
        self.assertIn("Person", j)
        self.assertIn("embargoPolicy", j)
        self.assertIn("EmbargoPolicy", j)


class TestVultronOrganizationBasics(unittest.TestCase):
    """VultronOrganization retains Organization type and supports
    embargo_policy."""

    def test_as_type_is_organization(self):
        org = VultronOrganization(as_id="https://example.org/orgs/vendor")
        self.assertEqual(as_ActorType.ORGANIZATION, org.as_type)

    def test_embargo_policy_defaults_to_none(self):
        org = VultronOrganization(as_id="https://example.org/orgs/vendor")
        self.assertIsNone(org.embargo_policy)

    def test_embargo_policy_inline_object(self):
        policy = _make_policy()
        org = VultronOrganization(
            as_id="https://example.org/orgs/vendor",
            embargo_policy=policy,
        )
        assert isinstance(org.embargo_policy, EmbargoPolicy)
        self.assertEqual(90, org.embargo_policy.preferred_duration_days)

    def test_is_instance_of_mixin(self):
        org = VultronOrganization()
        self.assertIsInstance(org, VultronActorMixin)


class TestVultronServiceBasics(unittest.TestCase):
    """VultronService retains Service type and supports embargo_policy."""

    def test_as_type_is_service(self):
        svc = VultronService(as_id="https://example.org/services/bot")
        self.assertEqual(as_ActorType.SERVICE, svc.as_type)

    def test_embargo_policy_defaults_to_none(self):
        svc = VultronService(as_id="https://example.org/services/bot")
        self.assertIsNone(svc.embargo_policy)

    def test_is_instance_of_mixin(self):
        svc = VultronService()
        self.assertIsInstance(svc, VultronActorMixin)


class TestVultronActorTypePreservation(unittest.TestCase):
    """Subclass types remain distinct and don't override each other."""

    def test_person_and_org_have_different_types(self):
        p = VultronPerson()
        org = VultronOrganization()
        self.assertNotEqual(p.as_type, org.as_type)

    def test_person_type_is_not_service(self):
        p = VultronPerson()
        svc = VultronService()
        self.assertNotEqual(p.as_type, svc.as_type)


if __name__ == "__main__":
    unittest.main()

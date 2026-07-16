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

"""Tests for SqliteDataLayer list_objects() method.

Covers: empty results, returning saved objects by type, type filtering,
typed-object return (not raw dicts), and semantic-class coercion for activities.
Fixtures (dl) come from conftest.
"""

from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite

# ---------------------------------------------------------------------------
# list_objects() tests
# ---------------------------------------------------------------------------


class TestListMethod:
    """dl.list_objects(type_key) returns fully rehydrated typed domain objects."""

    def test_list_empty_for_unknown_type(self, dl):
        """list() returns empty for a type with no stored records."""
        result = dl.list_objects("NoSuchType")
        assert result == []

    def test_list_returns_saved_objects(self, dl):
        """list() returns all objects of the requested type."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        r1 = VulnerabilityReport(name="CVE-1", content="Body 1")
        r2 = VulnerabilityReport(name="CVE-2", content="Body 2")
        dl.save(r1)
        dl.save(r2)

        results = dl.list_objects("VulnerabilityReport")

        assert len(results) == 2
        ids = {obj.id_ for obj in results}
        assert r1.id_ in ids
        assert r2.id_ in ids

    def test_list_filters_by_type(self, dl):
        """list() only returns objects of the requested type, not others."""
        from vultron.wire.as2.vocab.base.objects.object_types import as_Note
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        report = VulnerabilityReport(name="CVE-FILTER", content="Body")
        note = as_Note(content="Unrelated note")
        dl.save(report)
        dl.save(note)

        reports = dl.list_objects("VulnerabilityReport")
        notes = dl.list_objects("Note")

        assert len(reports) == 1
        assert reports[0].id_ == report.id_
        assert len(notes) == 1
        assert notes[0].id_ == note.id_

    def test_list_returns_typed_objects_not_dicts(self, dl):
        """list() returns domain model instances, not raw dict records."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        report = VulnerabilityReport(name="CVE-TYPED", content="Body")
        dl.save(report)

        results = dl.list_objects("VulnerabilityReport")

        assert len(results) == 1
        assert isinstance(results[0], VulnerabilityReport)

    def test_list_returns_semantic_class_for_activities(self, dl):
        """list() applies semantic coercion so activities get their subtype."""
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCaseStub,
        )

        actor = as_Service(name="Coordinator")
        invitee = as_Service(name="Vendor")
        stub = VulnerabilityCaseStub(id_="https://example.org/cases/list-test")
        invite = rm_invite_to_case_activity(
            invitee,
            target=stub,
            actor=actor.id_,
        )
        dl.save(actor)
        dl.save(invitee)
        dl.save(invite)

        results = dl.list_objects("Invite")

        assert len(results) == 1
        assert isinstance(results[0], as_Invite)

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

"""What the example generator's determinism rests on (#5776).

``test/architecture/test_vocab_examples_current.py`` proves only that the
committed files equal a fresh generation.  That would still hold if the id
source were one global seeded sequence — and then adding an example would
shift every id drawn after it, which is the "88 files changed to alter 18"
problem #5776 was filed for.  So the two properties the design is chosen for
are pinned here instead:

- the ids an example draws depend on its scope name and the draw's position in
  that scope, and on nothing else that happened before or after;
- an id that stands in for a *minted* id is shaped like one (version 4), not
  like an id derived from what an activity answers (version 5).

The all-or-nothing and one-file-per-row guarantees of the generator's tables
are pinned here too, because neither is visible to the currency check: a
generated *file set* stays correct when two rows claim one name.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

from vultron.core.models._helpers import (
    install_id_source,
    new_object_id,
    now_utc,
)
from vultron.errors import VultronIdSourceInstalledError
from vultron.wire.as2.vocab.examples._base import (
    EXAMPLE_TIMESTAMP,
    _example_scope,
    example_uuid,
)
from vultron.wire.as2.vocab.examples.vocab_examples import (
    EXAMPLES,
    INLINE_OBJECTS,
    build_examples,
    check_tables,
    example_filename,
)


def _ids_drawn(scope: str, count: int) -> list[str]:
    """The first *count* ids ``new_object_id`` mints inside *scope*."""
    with _example_scope(scope):
        return [new_object_id() for _ in range(count)]


class TestScopedIds:
    """The id source is derived per scope, not seeded over one sequence."""

    def test_the_same_scope_draws_the_same_ids_every_time(self) -> None:
        assert _ids_drawn("alpha", 3) == _ids_drawn("alpha", 3)

    def test_two_scopes_draw_different_ids(self) -> None:
        assert set(_ids_drawn("alpha", 3)).isdisjoint(_ids_drawn("beta", 3))

    def test_one_scope_draws_distinct_ids(self) -> None:
        drawn = _ids_drawn("alpha", 5)
        assert len(set(drawn)) == 5

    def test_another_scope_entered_first_moves_nothing(self) -> None:
        """Insertion stability: this is why the source is not seeded.

        Under one shared seeded sequence, drawing for ``beta`` before
        ``alpha`` would shift every id ``alpha`` gets, so adding one example
        would rewrite every example generated after it.
        """
        expected = _ids_drawn("alpha", 3)
        _ids_drawn("beta", 7)
        assert _ids_drawn("alpha", 3) == expected

    def test_a_draw_depends_only_on_its_position_in_its_scope(self) -> None:
        """The second id of a scope is the same however many follow it."""
        assert _ids_drawn("alpha", 2)[1] == _ids_drawn("alpha", 9)[1]

    def test_a_stand_in_id_is_shaped_like_a_minted_one(self) -> None:
        """Version 4, as ``new_object_id`` promises (OID-01-001/004).

        A version-5 id in the published corpus would read as an id *derived*
        from what an activity answers, a different protocol concept, to an
        implementer copying the example.
        """
        assert example_uuid("anything").version == 4
        assert all(
            id_.rsplit(":", 1)[-1][14] == "4" for id_ in _ids_drawn("alpha", 4)
        )


def _assert_the_install_is_released() -> None:
    """The minter draws fresh ids again, and the install slot is free."""
    assert new_object_id() != _ids_drawn("alpha", 1)[0]
    marker = uuid.UUID(int=0, version=4)
    with install_id_source(lambda: marker):
        assert new_object_id() == f"urn:uuid:{marker}"


class TestScopeInstallsItsIdSource:
    """The ids come through the minter's install, not a ``uuid`` patch.

    OID-01-012: nothing but the system id source may replace the ``uuid``
    module's draw, because a patch reaches every caller of it, py_trees
    included (ADR-0185).
    """

    def test_the_uuid_module_draw_is_untouched_inside_the_scope(self) -> None:
        real = uuid.uuid4
        with _example_scope("alpha"):
            assert uuid.uuid4 is real
            assert uuid.uuid4() != uuid.uuid4()

    def test_the_minter_draws_the_scope_ids(self) -> None:
        with _example_scope("alpha"):
            drawn = new_object_id()
        assert drawn == f"urn:uuid:{example_uuid('alpha/1')}"

    def test_the_system_source_is_back_after_the_scope(self) -> None:
        with _example_scope("alpha"):
            pass
        _assert_the_install_is_released()

    def test_the_system_source_is_back_after_a_raise(self) -> None:
        with pytest.raises(RuntimeError), _example_scope("alpha"):
            raise RuntimeError("boom")
        _assert_the_install_is_released()

    def test_a_scope_inside_another_install_is_refused(self) -> None:
        """Two streams of ids in one block would take each other's ids."""
        with install_id_source(uuid.uuid4):
            with pytest.raises(VultronIdSourceInstalledError):
                with _example_scope("alpha"):
                    pass

    def test_a_scope_inside_a_scope_is_refused(self) -> None:
        with _example_scope("alpha"):
            with pytest.raises(VultronIdSourceInstalledError):
                with _example_scope("beta"):
                    pass


class TestPinnedClock:
    """The clock reads one fixed moment inside the scope, and is restored."""

    def test_every_read_inside_the_scope_is_the_fixed_moment(self) -> None:
        with _example_scope("alpha"):
            assert now_utc() == EXAMPLE_TIMESTAMP
            assert now_utc() == EXAMPLE_TIMESTAMP

    def test_the_fixed_moment_is_in_the_past(self) -> None:
        """A pinned example must not state a future ``published``."""
        assert datetime.now(UTC) > EXAMPLE_TIMESTAMP

    def test_the_real_clock_is_back_after_the_scope(self) -> None:
        with _example_scope("alpha"):
            pass
        assert now_utc() > EXAMPLE_TIMESTAMP + timedelta(days=1)


class TestGeneratorTables:
    """One row, one file; and a regeneration is all-or-nothing."""

    def test_the_shipped_tables_pass_their_own_check(self) -> None:
        check_tables()

    def test_every_row_writes_its_own_file(self) -> None:
        names = [
            example_filename(builder, filename)
            for builder, filename in EXAMPLES
        ] + [filename for _, _, filename in INLINE_OBJECTS]
        assert len(names) == len(set(names))

    def test_every_inline_row_names_a_built_example(self) -> None:
        built = {builder.__name__ for builder, _ in EXAMPLES}
        assert {b.__name__ for b, _, _ in INLINE_OBJECTS} <= built

    def test_build_examples_returns_one_model_per_row(self) -> None:
        built = build_examples()
        assert len(built) == len(EXAMPLES) + len(INLINE_OBJECTS)
        assert all(isinstance(v, BaseModel) for v in built.values())

    def test_an_inline_row_pointing_at_a_non_model_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The raise happens before any file is written.

        ``build_examples`` is the whole build; ``main`` writes only after it
        returns, so a bad row leaves the committed tree as it was rather than
        half-rewritten at the row that failed.
        """
        builder = EXAMPLES[0][0]
        monkeypatch.setattr(
            "vultron.wire.as2.vocab.examples.vocab_examples.INLINE_OBJECTS",
            ((builder, "type_", "nonsense.json"),),
        )
        with pytest.raises(TypeError, match="is not a model"):
            build_examples()

    def test_two_rows_claiming_one_file_are_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        builder = EXAMPLES[0][0]
        monkeypatch.setattr(
            "vultron.wire.as2.vocab.examples.vocab_examples.EXAMPLES",
            ((builder, "same.json"), (builder, "same.json")),
        )
        with pytest.raises(ValueError, match="write one file"):
            check_tables()

    def test_an_inline_row_with_no_example_row_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        builder = INLINE_OBJECTS[0][0]
        monkeypatch.setattr(
            "vultron.wire.as2.vocab.examples.vocab_examples.EXAMPLES",
            (),
        )
        monkeypatch.setattr(
            "vultron.wire.as2.vocab.examples.vocab_examples.INLINE_OBJECTS",
            ((builder, "object_", "orphan.json"),),
        )
        with pytest.raises(ValueError, match="EXAMPLES does not"):
            check_tables()

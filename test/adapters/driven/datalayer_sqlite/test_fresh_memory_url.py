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
"""Tests for ``fresh_memory_url`` (DL-07-004, DL-07-013, TB-06-003)."""

import pytest

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    fresh_memory_url,
)
from vultron.adapters.driven.datalayer_sqlite.engine import (
    open_memory_store_slugs,
)
from vultron.core.models.case import VulnerabilityCase

_ACTOR_ID = "http://vendor/api/v2/actors/vendor"
_CASE_ID = "urn:uuid:12345678-1234-1234-1234-123456789abc"


def _memory_template(base: str) -> str:
    return f"sqlite:///file:{base}?mode=memory&cache=shared&uri=true"


def _case() -> VulnerabilityCase:
    return make(
        VulnerabilityCase,
        id_=_CASE_ID,
        name="Test case",
        attributed_to=_ACTOR_ID,
    )


@pytest.mark.spec("DL-07-004", "TB-06-003")
def test_a_row_saved_through_one_call_is_unreadable_through_the_next():
    with SqliteDataLayer(
        fresh_memory_url("scenario"), actor_id=_ACTOR_ID
    ) as first:
        first.save(_case())
        assert first.read(_CASE_ID) is not None

        with SqliteDataLayer(
            fresh_memory_url("scenario"), actor_id=_ACTOR_ID
        ) as second:
            assert second.read(_CASE_ID) is None


@pytest.mark.spec("DL-07-013")
@pytest.mark.parametrize("purpose", ["suggest", "suggest-copy"])
def test_no_other_deployment_lists_a_fresh_store(purpose: str):
    # A real deployment whose base is the helper's leading word, so the
    # listing is shown to work and the fresh store is shown absent from it.
    deployment = _memory_template("fresh")
    with (
        SqliteDataLayer(deployment, actor_id=_ACTOR_ID) as hosted,
        SqliteDataLayer(
            fresh_memory_url(purpose), actor_id=_ACTOR_ID
        ) as fresh,
    ):
        hosted.save(_case())
        fresh.save(_case())

        assert open_memory_store_slugs(deployment) == {"vendor"}
        for base in (
            "vultron",
            "app7",
            "fresh~",
            f"fresh-{purpose}",
            f"fresh~{purpose}",
        ):
            assert open_memory_store_slugs(_memory_template(base)) == set()
        assert open_memory_store_slugs("sqlite:///:memory:") == set()


def test_each_call_names_a_different_in_memory_store():
    urls = {fresh_memory_url("scenario") for _ in range(3)}

    assert len(urls) == 3
    assert all("mode=memory" in url for url in urls)


def test_the_purpose_is_carried_in_the_name():
    assert "~my-purpose?" in fresh_memory_url("my-purpose")


@pytest.mark.parametrize(
    "purpose", ["", "with/slash", "with space", "at@sign", "tilde~"]
)
def test_a_purpose_that_is_not_a_slug_is_refused(purpose: str):
    with pytest.raises(ValueError, match="purpose must be a non-empty slug"):
        fresh_memory_url(purpose)

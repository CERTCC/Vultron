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


"""Tests of :mod:`vultron.demo.scenario.rcvcv_demo.cli` (DEMOMA-19, #5534).

The generated ``rcvcv`` sub-command, the registered ``main()`` entry point and
the registry entry it declares (DEMOCI-11-011, DEMOCI-11-019).
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import vultron.demo.scenario.rcvcv_demo as demo
from vultron.demo.cli import main as cli_main
from vultron.demo.scenario.rcvcv_demo import cli as rcvcv_cli
from vultron.demo.scenario.registry import registered_scenarios

#: Clear the process-global failure accumulator around every test.
pytestmark = pytest.mark.usefixtures("fresh_demo_failures")


# ---------------------------------------------------------------------------
# The CLI sub-command and the registry entry (DEMOCI-11-011, DEMOCI-11-019)
# ---------------------------------------------------------------------------


@pytest.fixture
def help_text() -> str:
    """``vultron-demo rcvcv --help`` as the generated sub-command renders it."""
    result = CliRunner().invoke(cli_main, ["rcvcv", "--help"])
    assert result.exit_code == 0, result.output
    return result.output


class TestRcvcvCliCommand:
    """The generated ``rcvcv`` sub-command offers one option per container."""

    @pytest.mark.parametrize(
        "option",
        [
            "--skip-health-check",
            "--reporter-url",
            "--c1-url",
            "--v1-url",
            "--c2-url",
            "--v2-url",
            "--case-actor-url",
            "--reporter-id",
            "--c1-id",
            "--v1-id",
            "--c2-id",
            "--v2-id",
        ],
    )
    def test_the_option_is_offered(self, help_text: str, option: str):
        """One URL and one id option per container, plus the health skip."""
        assert option in help_text

    def test_main_builds_one_client_per_container_and_runs_the_story(self):
        """``main()`` names its containers and passes their clients on."""
        clients = {
            name: MagicMock(name=name, base_url=f"http://{name}:7999/api/v2")
            for name in ("reporter", "c1", "v1", "c2", "v2", "case-actor")
        }

        with (
            patch.object(
                rcvcv_cli, "story_clients", return_value=clients
            ) as built,
            patch.object(rcvcv_cli, "run_rcvcv_demo") as run,
        ):
            demo.main(
                skip_health_check=True,
                c1_url="http://elsewhere:7999/api/v2",
                reporter_id="urn:test:reporter",
                c1_id="urn:test:c1",
                v1_id="urn:test:v1",
                c2_id="urn:test:c2",
                v2_id="urn:test:v2",
            )

        members = built.call_args.args[1]
        assert [(m.role, m.label) for m in members] == [
            ("reporter", "Reporter"),
            ("c1", "C1"),
            ("v1", "V1"),
            ("c2", "C2"),
            ("v2", "V2"),
        ]
        assert [m.url for m in members] == [
            None,
            "http://elsewhere:7999/api/v2",
            None,
            None,
            None,
        ]
        assert built.call_args.kwargs["skip_health_check"] is True

        kwargs = run.call_args.kwargs
        assert kwargs["reporter_client"] is clients["reporter"]
        assert kwargs["c1_client"] is clients["c1"]
        assert kwargs["v1_client"] is clients["v1"]
        assert kwargs["c2_client"] is clients["c2"]
        assert kwargs["v2_client"] is clients["v2"]
        assert kwargs["case_actor_client"] is clients["case-actor"]
        assert kwargs["c2_id"] == "urn:test:c2"


@pytest.fixture
def spec():
    """The one registry entry named ``rcvcv``."""
    entries = [s for s in registered_scenarios() if s.name == "rcvcv"]
    assert len(entries) == 1, entries
    return entries[0]


class TestRcvcvRegistryEntry:
    """The registry is the sole declaration that ``rcvcv`` exists."""

    def test_the_entry_describes_the_five_party_suggestion_scenario(
        self, spec
    ):
        """Every field is rendered into the generated scenario tables."""
        assert spec.label == "RCVCV"
        assert spec.participants == "Reporter + C1 + V1 + C2 + V2"
        assert spec.feature == "Actor-suggestion flow (ADR-0026)"
        assert spec.in_pr_set is True

    def test_the_path_is_read_off_the_story(self, spec):
        """The registry holds the path this scenario's story chooses.

        Compared against the story object rather than against a literal, which
        ``test_story.py``'s path test pins separately: together they say the
        registered path is both derived and the intended one.
        """
        assert spec.path == demo.STORY.path

    def test_the_derived_paths_point_at_this_module_and_its_harness(
        self, spec
    ):
        """Every artifact path derives from the name (DEMOCI-11-003)."""
        assert spec.demo_path == "vultron/demo/scenario/rcvcv_demo/"
        assert (
            spec.harness_path == "test/ci/invariants/test_rcvcv_invariants.py"
        )

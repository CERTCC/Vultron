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

"""Regression tests for ISSUE-2239: an escaping assertion must not destroy the
scenario's case-ledger artifacts.

Before the fix, ``_phase_dump_case_ledgers`` was the last plain statement in
every ``run_*_demo()``.  An exception escaping any earlier phase — for example
one of the unguarded ``wait_for_case_participants`` calls — skipped the dump
entirely.  ``main()``'s ``finally: assert_demo_success()`` still raised, so the
demo job failed with an **empty** ``devlogs/`` directory; the separate
invariant-harness job then died on artifact download and reported nothing about
the protocol.

Two guarantees are asserted here:

1. A scenario that dies *after* the case exists still dumps every ledger it had
   (``TestDumpRunsAfterMidPhaseFailure``).
2. A scenario that dies *before* the case exists still produces a dump manifest,
   so the case-log artifact always exists and the invariant harness reports a
   real result rather than an artifact-download error
   (``TestManifestWrittenWhenScenarioDiesEarly``).

See ``specs/demo-ci.yaml`` DEMOCI-10 and ``specs/multi-actor-demo.yaml``
DEMOMA-23.
"""

import importlib
import inspect
import json
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from test.support.case_owner import CASE_OWNER_ID
from vultron.demo.helpers.ledger_dump import DUMP_MANIFEST_FILENAME
from vultron.demo.utils import reset_demo_failures
from vultron.errors import DemoFailureError

#: What the scenario does before a case exists, as a name on its own module.
#: A scenario still written as phases opens with ``_phase_report_submission``;
#: one written as composition (#5533) opens with the shared cast opening its
#: story runs against, which is the first thing that can die.
_PHASE_ONE = "_phase_report_submission"
_CAST_ONE = "open_coordinated_cast"

# (module path, run function name, devlogs sub-directory name, first step)
SCENARIOS: list[tuple[str, str, str, str]] = [
    ("vultron.demo.scenario.rv_demo", "run_rv_demo", "rv", _PHASE_ONE),
    ("vultron.demo.scenario.rvv_demo", "run_rvv_demo", "rvv", _PHASE_ONE),
    ("vultron.demo.scenario.rcv_demo", "run_rcv_demo", "rcv", _CAST_ONE),
    (
        "vultron.demo.scenario.rcv_reject_demo",
        "run_rcv_reject_demo",
        "rcv-reject",
        _CAST_ONE,
    ),
    (
        "vultron.demo.scenario.rcvcv_demo",
        "run_rcvcv_demo",
        "rcvcv",
        _PHASE_ONE,
    ),
    (
        "vultron.demo.scenario.rccv_extension_demo",
        "run_rccv_extension_demo",
        "rccv-extension",
        _PHASE_ONE,
    ),
    (
        "vultron.demo.scenario.rvcv_extension_demo",
        "run_rvcv_extension_demo",
        "rvcv-extension",
        _PHASE_ONE,
    ),
    (
        "vultron.demo.scenario.rccv_handoff_demo",
        "run_rccv_handoff_demo",
        "rccv-handoff",
        _PHASE_ONE,
    ),
    (
        "vultron.demo.scenario.rvcv_handoff_demo",
        "run_rvcv_handoff_demo",
        "rvcv-handoff",
        _PHASE_ONE,
    ),
]


def _client_kwargs(run_fn) -> dict[str, MagicMock]:
    """Build a MagicMock for every ``*_client`` parameter of *run_fn*."""
    return {
        name: MagicMock()
        for name in inspect.signature(run_fn).parameters
        if name.endswith("_client")
    }


@pytest.fixture(autouse=True)
def _clean_failure_accumulator():
    """Isolate the module-level demo failure accumulator between tests."""
    reset_demo_failures()
    yield
    reset_demo_failures()


class TestManifestWrittenWhenScenarioDiesEarly:
    """A scenario that dies before the case exists still produces an artifact."""

    @pytest.mark.parametrize(
        "module_path, run_name, demo_name, first_step",
        SCENARIOS,
        ids=[demo_name for _, _, demo_name, _ in SCENARIOS],
    )
    def test_manifest_written_when_first_phase_raises(
        self,
        module_path: str,
        run_name: str,
        demo_name: str,
        first_step: str,
        tmp_path,
        monkeypatch,
    ) -> None:
        module: ModuleType = importlib.import_module(module_path)
        run_fn = getattr(module, run_name)
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        with patch.object(
            module,
            first_step,
            side_effect=RuntimeError("phase 1 exploded"),
        ):
            with pytest.raises((RuntimeError, DemoFailureError)):
                run_fn(**_client_kwargs(run_fn))

        manifest = tmp_path / demo_name / DUMP_MANIFEST_FILENAME
        assert manifest.exists(), (
            f"{run_name} produced no dump manifest, so the case-log artifact "
            "would be empty and the invariant harness would fail on artifact "
            "download instead of reporting an invariant result"
        )

        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["demoName"] == demo_name
        assert payload["ledgerFileCount"] == 0
        # The manifest is the evidence that the demo ran; without it the
        # harness cannot tell "nobody ran the demo" from "the demo produced
        # nothing".
        assert payload["reason"]


class TestDumpRunsAfterMidPhaseFailure:
    """A scenario that dies after the case exists still dumps its ledgers."""

    def test_rvv_dumps_ledgers_when_a_later_phase_raises(
        self, tmp_path, monkeypatch
    ) -> None:
        module = importlib.import_module("vultron.demo.scenario.rvv_demo")
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        case = module.as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/issue-2239",
        )
        # rvv phase 1 returns (reporter, vendor, vendor_in_vendor, vendor2,
        # report, offer, case, reply_note).
        phase_one_result = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            case,
            MagicMock(),
        )

        with (
            patch.object(
                module,
                "_phase_report_submission",
                return_value=phase_one_result,
            ),
            patch.object(module, "get_actor_by_id", return_value=MagicMock()),
            patch.object(
                module,
                "_phase_sync_verification",
                side_effect=RuntimeError("wait_for_case_participants timeout"),
            ),
            patch.object(module, "_phase_dump_case_ledgers") as dump,
        ):
            with pytest.raises((RuntimeError, DemoFailureError)):
                run_fn = module.run_rvv_demo
                run_fn(**_client_kwargs(run_fn))

        assert dump.called, (
            "run_rvv_demo skipped the case-ledger dump when a phase raised; "
            "the forensic artifacts the invariant harness needs were lost"
        )
        assert dump.call_args.kwargs["case"] is case

    def test_dump_failure_does_not_mask_the_phase_exception(
        self, tmp_path, monkeypatch
    ) -> None:
        """A broken dump must not replace the exception that caused the failure."""
        module = importlib.import_module("vultron.demo.scenario.rvv_demo")
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))

        case = module.as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/issue-2239-mask",
        )
        phase_one_result = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            case,
            MagicMock(),
        )

        with (
            patch.object(
                module,
                "_phase_report_submission",
                return_value=phase_one_result,
            ),
            patch.object(module, "get_actor_by_id", return_value=MagicMock()),
            patch.object(
                module,
                "_phase_sync_verification",
                side_effect=RuntimeError("the real cause"),
            ),
            patch.object(
                module,
                "_phase_dump_case_ledgers",
                side_effect=OSError("devlogs volume is read-only"),
            ),
        ):
            with pytest.raises(RuntimeError, match="the real cause"):
                run_fn = module.run_rvv_demo
                run_fn(**_client_kwargs(run_fn))

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

"""Ratchet: VALID_SCENARIOS in the integration test script must match CI.

When a new demo scenario is added to .github/workflows/demo-integration.yml
(per DEMOCI-02-003), the shell script's VALID_SCENARIOS list must be updated
in the same PR.  This test catches the drift that triggered issue #1585.

Source of truth: the DEMO=<name> values in demo-integration.yml.
Checked artifact: VALID_SCENARIOS in run_multi_actor_integration_test.sh.
"""

import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).parents[2]
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "demo-integration.yml"
_INTEGRATION_SCRIPT = (
    _REPO_ROOT
    / "integration_tests"
    / "demo"
    / "run_multi_actor_integration_test.sh"
)

# Matches lines like:   DEMO=fvcv-extension \
_CI_DEMO_RE = re.compile(r"^\s+DEMO=([a-z][a-z0-9-]+)\s", re.MULTILINE)

# Matches the assignment line:  VALID_SCENARIOS="fv fvv fvcv-extension fvcv-handoff"
_VALID_SCENARIOS_RE = re.compile(r'^VALID_SCENARIOS="([^"]+)"')


def _ci_scenarios() -> set[str]:
    """Return the set of scenario names run by demo-integration.yml."""
    text = _CI_WORKFLOW.read_text()
    return {m.group(1) for m in _CI_DEMO_RE.finditer(text)}


def _script_scenarios() -> set[str]:
    """Return the set of scenario names declared in VALID_SCENARIOS."""
    for line in _INTEGRATION_SCRIPT.read_text().splitlines():
        m = _VALID_SCENARIOS_RE.match(line)
        if m:
            return set(m.group(1).split())
    raise AssertionError(
        f"Could not find VALID_SCENARIOS assignment in {_INTEGRATION_SCRIPT}"
    )


class TestIntegrationScriptScenarios:
    """VALID_SCENARIOS must stay in sync with the CI workflow."""

    def test_ci_workflow_exists(self):
        assert _CI_WORKFLOW.exists(), f"CI workflow not found: {_CI_WORKFLOW}"

    def test_integration_script_exists(self):
        assert (
            _INTEGRATION_SCRIPT.exists()
        ), f"Integration script not found: {_INTEGRATION_SCRIPT}"

    def test_valid_scenarios_matches_ci(self):
        """VALID_SCENARIOS must equal the DEMO= values in demo-integration.yml.

        Failure here means a new scenario was added to CI without updating the
        script (or vice versa).  Fix both files in the same PR per DEMOCI-02-003.
        """
        ci = _ci_scenarios()
        script = _script_scenarios()
        assert script == ci, (
            f"VALID_SCENARIOS in run_multi_actor_integration_test.sh {sorted(script)!r} "
            f"does not match DEMO= values in demo-integration.yml {sorted(ci)!r}.\n"
            f"In script but not CI: {sorted(script - ci)!r}\n"
            f"In CI but not script: {sorted(ci - script)!r}\n"
            "Update both files in the same PR (DEMOCI-02-003)."
        )

    def test_ci_workflow_is_valid_yaml(self):
        """demo-integration.yml must parse as valid YAML."""
        text = _CI_WORKFLOW.read_text()
        result = yaml.safe_load(text)
        assert isinstance(
            result, dict
        ), "Expected a YAML mapping at the top level"

    def test_at_least_one_scenario_in_ci(self):
        """CI must define at least one scenario (guards against empty parse)."""
        ci = _ci_scenarios()
        assert len(ci) >= 1, "No DEMO= lines found in demo-integration.yml"

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

"""``child_env()`` puts this checkout first on a child's ``PYTHONPATH`` (#5456)."""

import os

from test.support.child_env import REPO_ROOT, child_env


def test_child_env_orders_repo_root_then_extras_then_inherited(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PYTHONPATH", "/other/checkout")

    env = child_env(tmp_path)

    assert env["PYTHONPATH"].split(os.pathsep) == [
        str(REPO_ROOT),
        str(tmp_path),
        "/other/checkout",
    ]


def test_child_env_drops_an_empty_inherited_pythonpath(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "")

    assert child_env()["PYTHONPATH"] == str(REPO_ROOT)


def test_child_env_keeps_the_rest_of_the_environment(monkeypatch):
    monkeypatch.setenv("CHILD_ENV_PROBE", "kept")

    assert child_env()["CHILD_ENV_PROBE"] == "kept"

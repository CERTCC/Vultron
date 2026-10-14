#!/usr/bin/env python3
"""A stand-in ``gh`` for testing the claim scripts without the network.

Installed as ``gh`` on ``PATH`` by ``test_claim_scripts.py``. Every call is
appended to ``$FAKE_GH_LOG`` as one JSON argv list. The reply comes from the
first rule in ``$FAKE_GH_RULES`` whose ``match`` substrings all occur in the
space-joined argv: ``{"match": [...], "stdout": "...", "exit": 0}``.

``createLinkedBranch`` is not rule-driven: it behaves like GitHub, creating the
branch in the bare repo ``$FAKE_GH_ORIGIN`` and answering ``linkedBranch: null``
when the name already exists. ``--jq`` is applied with the real ``jq``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def _field(argv: list[str], key: str) -> str:
    for i, arg in enumerate(argv):
        if arg == "-f" and argv[i + 1].startswith(f"{key}="):
            return argv[i + 1].split("=", 1)[1]
    raise SystemExit(f"fake gh: no -f {key}=")


def _linked_branch(argv: list[str]) -> str:
    origin = os.environ["FAKE_GH_ORIGIN"]
    ref = f"refs/heads/{_field(argv, 'name')}"
    exists = (
        subprocess.run(
            ["git", f"--git-dir={origin}", "show-ref", "--quiet", ref],
            check=False,
        ).returncode
        == 0
    )
    if not exists:
        subprocess.run(
            [
                "git",
                f"--git-dir={origin}",
                "update-ref",
                ref,
                _field(argv, "oid"),
            ],
            check=True,
        )
    linked = None if exists else {"id": "LB_fake"}
    return json.dumps(
        {"data": {"createLinkedBranch": {"linkedBranch": linked}}}
    )


def main() -> int:
    argv = sys.argv[1:]
    with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
        log.write(json.dumps(argv) + "\n")

    joined = " ".join(argv)
    if "createLinkedBranch" in joined:
        stdout, code = _linked_branch(argv), 0
    else:
        with open(os.environ["FAKE_GH_RULES"], encoding="utf-8") as fh:
            rules = json.load(fh)
        for rule in rules:
            if all(m in joined for m in rule["match"]):
                stdout, code = rule.get("stdout", ""), rule.get("exit", 0)
                break
        else:
            print(f"fake gh: no rule for {argv}", file=sys.stderr)
            return 99

    if "--jq" in argv and code == 0:
        expr = argv[argv.index("--jq") + 1]
        stdout = subprocess.run(
            ["jq", "-r", expr],
            input=stdout,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    sys.stdout.write(stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())

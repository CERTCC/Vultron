#!/usr/bin/env python
"""This module provides
# TODO replace me
"""
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University


import os
import re

from vultron.case_states.hypercube import CVDmodel
from vultron.case_states.patterns.explanations import explain

_DISCLAIMER = "This file is auto-generated. Do not edit."


def _bullet(s):
    """Return a markdown bullet for use inside a table cell"""
    return f"&bull;&nbsp;{s}<br/>"


def _h2(s):
    return f"## {s}\n"


def _comment(s):
    return f"<!-- {s} -->\n"


def _fname(s):
    # replace uppercase characters with _lowercase
    s = re.sub(r"([A-Z])", r"_\1_", s).lower()
    return f"state_{s}.md"


def _enum2title(x):
    return x.name.replace("_", " ").title()


def print_readme(model_dir="../../docs/case_states"):
    sg = CVDmodel()

    fpath = os.path.join(model_dir, "index.md")
    with open(fpath, "w") as fp:
        fp.write(f"{_comment(_DISCLAIMER)}\n")

        fp.write("# Case States\n")
        fp.write(
            "This directory contains a description of each state in the case model.\n"
        )
        fp.write("\n")
        fp.write("## States\n")
        fp.write("\n")

        # table header
        fp.write(
            "| State | Vendor Status | Fix Status | Deployment Status | Public Status | Exploit Status | Attacks Status |\n"
        )
        fp.write("| --- | --- | --- | --- | --- | --- | --- |\n")

        for state in sg.states():
            explanation = "| ".join((_enum2title(x) for x in explain(state)))
            fp.write(f"| [{state}]({_fname(state)}) | {explanation} |\n")
        fp.write("\n")


def print_model(model_dir="../../docs/reference/case_states"):
    # create a graph
    sg = CVDmodel()

    for state in sg.states:
        filename = _fname(state)
        filepath = os.path.join(model_dir, filename)
        print(filepath)

        with open(filepath, "w") as fp:
            fp.write(f"{_comment(_DISCLAIMER)}\n")

            fp.write(f"# {state}\n")

            info = sg.state_info(state)

            fp.write("| Key | Value |\n")
            fp.write("| --- | --- |\n")
            fp.write(f"| State | {info['state']} |\n")
            fp.write(f"| Score | {info['score']:.2f} |\n")

            fp.write("| VFD |")
            for item in info["vfd"]:
                fp.write(_bullet(_enum2title(item)))
            fp.write("|\n")

            fp.write("| PXA |")
            for item in info["pxa"]:
                fp.write(_bullet(_enum2title(item)))
            fp.write("|\n")

            for category in [
                "explain",
                "info",
                "actions",
                "zeroday_type",
            ]:
                fp.write(f"| {category.title()} |")
                for item in info[category]:
                    fp.write(_bullet(_enum2title(item)))
                fp.write("|\n")

            fp.write("| Predecessors |")
            if not len(info["predecessors"]):
                fp.write(_bullet("None"))
            else:
                for p in info["predecessors"]:
                    link = f"[{p}]({_fname(p)})"
                    fp.write(_bullet(link))
            fp.write("|\n")

            fp.write("| Successors<br/>(prefer higher scores) |")
            if not len(info["successors"]):
                fp.write(_bullet("None"))
            else:
                for s in info["successors"]:
                    link = (
                        f"[{s}]({_fname(s)}) (score={sg.score_state(s):.2f})"
                    )
                    fp.write(_bullet(link))
            fp.write("|\n")

            fp.write("| Possible Sequences To This State |")
            paths = list(sg.paths_to(state))
            if len(paths) == 0:
                fp.write(_bullet("None"))
            else:
                for path in paths:
                    transitions = sg.transitions_in_path(path)
                    links = []
                    for transition, step in zip(transitions, path):
                        (start, end) = step
                        link = f"[**{transition}**]({_fname(end)})"
                        links.append(link)
                    fp.write(_bullet(" &rarr; ".join(links)))
            fp.write("| \n")

            fp.write("| Possible Sequences From This State |")
            paths = list(sg.paths_from(state))
            if len(paths) == 0:
                fp.write(_bullet("None"))
            else:
                for path in paths:
                    transitions = sg.transitions_in_path(path)
                    links = []
                    for transition, step in zip(transitions, path):
                        (start, end) = step
                        link = f"[**{transition}**]({_fname(end)})"
                        links.append(link)
                    fp.write(_bullet(" &rarr; ".join(links)))
            fp.write("|\n")


def main():
    outdir = "../../docs/reference/case_states"

    # check if parent dir exists
    parent_dir = os.path.abspath(os.path.dirname(outdir))
    if not os.path.exists(parent_dir):
        raise Exception(f"Parent directory {parent_dir} does not exist")

    os.makedirs(outdir, exist_ok=True)

    print_readme(model_dir=outdir)
    print_model(model_dir=outdir)


if __name__ == "__main__":
    main()

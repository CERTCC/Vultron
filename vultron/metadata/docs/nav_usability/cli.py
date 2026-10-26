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
"""The ``nav-usability`` command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vultron.metadata.docs.nav_usability.results import (
    Results,
    TaskResult,
    load_results,
    save_results,
    tally,
)
from vultron.metadata.docs.nav_usability.suite import SUITE_PATH, load_suite
from vultron.metadata.docs.nav_usability.tree import (
    nav_hash,
    nav_tree,
    render_tree,
    score_tree_answers,
    tree_prompt,
)
from vultron.metadata.docs.nav_usability.walk import (
    DEFAULT_CLICK_BUDGET,
    Walk,
    score_walk,
    walk_prompt,
)
from vultron.metadata.file_loading import (
    MetadataLoadError,
    MetadataLoadErrors,
)


def _config_text(path: Path) -> str:
    return path.read_text("utf-8")


def _cmd_tree(args: argparse.Namespace) -> None:
    text = _config_text(args.config)
    print(f"nav hash: {nav_hash(text)}")
    print(render_tree(nav_tree(text, args.docs)))


def _cmd_prompt(args: argparse.Namespace) -> None:
    suite = load_suite(args.suite)
    nodes = nav_tree(_config_text(args.config), args.docs)
    print(tree_prompt(suite, args.persona, nodes))


def _cmd_score(args: argparse.Namespace) -> None:
    suite = load_suite(args.suite)
    text = _config_text(args.config)
    nodes = nav_tree(text, args.docs)
    if args.results.is_file():
        results = load_results(args.results)
        if results.nav_hash != nav_hash(text):
            raise SystemExit(
                f"{args.results} holds results for nav {results.nav_hash}, "
                f"not {nav_hash(text)}; start a new results file"
            )
    else:
        results = Results(
            nav=args.nav,
            nav_hash=nav_hash(text),
            source=args.source,
            model=args.model,
        )
    answers = json.loads(args.answers.read_text("utf-8"))["answers"]
    scored = score_tree_answers(suite, args.persona, nodes, answers, args.run)
    results.results = [
        r
        for r in results.results
        if not (
            r.stage == 1 and r.persona == args.persona and r.run == args.run
        )
    ] + scored
    save_results(args.results, results)
    for r in scored:
        print(f"{r.task} {r.outcome.value} {' > '.join(r.label_path)}")


def _cmd_walk(args: argparse.Namespace) -> None:
    walk = Walk(args.session)
    if args.start:
        print(walk.start(args.start, args.budget))
    elif args.go is not None:
        print(walk.go(args.go))
    elif args.found:
        print(walk.finish("found"))
    elif args.give_up:
        print(walk.finish("gave-up"))
    else:
        raise SystemExit("walk needs one of --start, --go, --found, --give-up")


def _cmd_walk_prompt(args: argparse.Namespace) -> None:
    suite = load_suite(args.suite)
    print(
        walk_prompt(
            suite,
            args.persona,
            args.site,
            args.sessions,
            args.tasks.split(","),
            args.budget,
        )
    )


def _cmd_score_walks(args: argparse.Namespace) -> None:
    suite = load_suite(args.suite)
    results = load_results(args.results)
    scored: list[TaskResult] = []
    for session in sorted(args.sessions.glob("*.json")):
        state = Walk(session).state()
        if state.finished is None:
            raise SystemExit(
                f"{session} is unfinished; the walk has no outcome"
            )
        scored.append(score_walk(suite, session.stem, state, args.run))
    keys = {(r.task, r.run) for r in scored}
    results.results = [
        r
        for r in results.results
        if not (r.stage == 2 and (r.task, r.run) in keys)
    ] + scored
    save_results(args.results, results)
    for r in scored:
        print(f"{r.task} {r.outcome.value} in {r.clicks} click(s): {r.answer}")


def _cmd_tally(args: argparse.Namespace) -> None:
    verdict = tally(
        load_results(args.baseline), load_results(args.proposed), args.stage
    )
    print(
        f"stage {args.stage}: baseline {verdict.baseline_success}/{verdict.total}, "
        f"proposed {verdict.proposed_success}/{verdict.total}"
    )
    print(f"worse: {', '.join(verdict.worse) or 'none'}")
    print(f"better: {', '.join(verdict.better) or 'none'}")
    print(f"stalls at home: {', '.join(verdict.stalls) or 'none'}")
    print("PASS" if verdict.passed else "FAIL")
    if not verdict.passed:
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nav-usability",
        description="The agent usability test that gates a nav change.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def nav_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", type=Path, default=Path("mkdocs.yml"))
        p.add_argument("--docs", type=Path, default=Path("docs"))

    tree = sub.add_parser("tree", help="print the nav hash and label tree")
    nav_args(tree)
    tree.set_defaults(func=_cmd_tree)

    prompt = sub.add_parser(
        "prompt", help="print a persona's Stage 1 briefing"
    )
    nav_args(prompt)
    prompt.add_argument("--suite", type=Path, default=SUITE_PATH)
    prompt.add_argument("--persona", required=True)
    prompt.set_defaults(func=_cmd_prompt)

    score = sub.add_parser("score", help="score Stage 1 answers")
    nav_args(score)
    score.add_argument("--suite", type=Path, default=SUITE_PATH)
    score.add_argument("--persona", required=True)
    score.add_argument("--answers", type=Path, required=True)
    score.add_argument("--results", type=Path, required=True)
    score.add_argument("--nav", required=True)
    score.add_argument("--source", required=True)
    score.add_argument("--model")
    score.add_argument("--run", type=int, default=1)
    score.set_defaults(func=_cmd_score)

    walk = sub.add_parser("walk", help="take one Stage 2 step")
    walk.add_argument("--session", type=Path, required=True)
    walk.add_argument("--start", type=Path, metavar="SITE")
    walk.add_argument("--budget", type=int, default=DEFAULT_CLICK_BUDGET)
    walk.add_argument("--go", type=int, metavar="LINK")
    walk.add_argument("--found", action="store_true")
    walk.add_argument("--give-up", action="store_true")
    walk.set_defaults(func=_cmd_walk)

    walk_prompt_p = sub.add_parser(
        "walk-prompt", help="print a persona's Stage 2 briefing"
    )
    walk_prompt_p.add_argument("--suite", type=Path, default=SUITE_PATH)
    walk_prompt_p.add_argument("--persona", required=True)
    walk_prompt_p.add_argument("--site", type=Path, required=True)
    walk_prompt_p.add_argument("--sessions", type=Path, required=True)
    walk_prompt_p.add_argument("--tasks", required=True, help="T01,T02,...")
    walk_prompt_p.add_argument(
        "--budget", type=int, default=DEFAULT_CLICK_BUDGET
    )
    walk_prompt_p.set_defaults(func=_cmd_walk_prompt)

    score_walks = sub.add_parser(
        "score-walks", help="score finished Stage 2 sessions into results"
    )
    score_walks.add_argument("--suite", type=Path, default=SUITE_PATH)
    score_walks.add_argument("--sessions", type=Path, required=True)
    score_walks.add_argument("--results", type=Path, required=True)
    score_walks.add_argument("--run", type=int, default=1)
    score_walks.set_defaults(func=_cmd_score_walks)

    tally_p = sub.add_parser("tally", help="compare two navs' results")
    tally_p.add_argument("--baseline", type=Path, required=True)
    tally_p.add_argument("--proposed", type=Path, required=True)
    tally_p.add_argument("--stage", type=int, choices=(1, 2), default=1)
    tally_p.set_defaults(func=_cmd_tally)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (MetadataLoadError, MetadataLoadErrors) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":  # pragma: no cover
    main()

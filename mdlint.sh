#!/usr/bin/env sh

#
# Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
# - see Contributors.md for a full list of Contributors
# - see ContributionInstructions.md for information on how you can Contribute to this project
# Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
# licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
# with this Software or contact permission@sei.cmu.edu for full terms.
# Created, in part, with funding and support from the United States Government
# (see Acknowledgments file). This program may include and/or can make use of
# certain third party source code, object code, documentation and other files
# (“Third Party Software”). See LICENSE.md for more details.
# Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
# U.S. Patent and Trademark Office by Carnegie Mellon University
#

# Usage: ./mdlint.sh [file-or-glob ...]
#
# With arguments, lint and --fix only those files or globs. With none, lint
# every Markdown file in the repository. Either way the exclusions below apply
# on top of the root config's `ignores`: agent worktrees under
# .claude/worktrees/ belong to other sessions, and every plan/history/ entry,
# at any depth, is a write-once record (HM-01-005, #2952, #6232).

if [ "$#" -eq 0 ]; then
    set -- "**/*.md"
fi

markdownlint-cli2 --fix --config .markdownlint-cli2.yaml "$@" "#**/node_modules/**" "#.venv/**" "#.git/**" "#wip_notes/**" "#graphify-out/**" "#.claude/worktrees/**" "#**/plan/history/**"

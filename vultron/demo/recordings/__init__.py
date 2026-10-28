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

"""Record every registered demo scenario's case ledgers for the demo UI.

A **recording** is the case ledger a scenario writes when it runs.  Log Replay
in ``ui/`` imports the recordings, so what the audience sees is what Vultron
did (``notes/demo-interactive-ui.md``, decision 2).

Only the CaseActor's ledger, the canonical one, is committed.  Every replica
holds byte-identical copies of the canonical entries (CLP-07-013), so storing
them adds nothing.  Each run still checks that claim: a replica entry that
differs from the canonical entry at its ``logIndex`` fails the recording.

Each scenario runs in this process, through its own ``main()``:

- **Topology.**  Each container slot the scenario's ``ROLES`` name becomes one
  in-process app (:mod:`vultron.demo.in_process`), at the URL the Docker demo
  runner gives that slot.  The URLs and each container's
  ``VULTRON_ACTOR__DEFAULT_CASE_ROLES`` are read from
  ``docker/docker-compose-multi-actor.yml``, so a recording uses the same
  container layout as the Docker demo.  Configuration is process-wide here,
  so the per-container case roles are applied where a proposer states them
  (CP-01-013).
- **Determinism.**  The run's ids and clock are replaced by
  :func:`vultron.demo.determinism.deterministic_run`, seeded with the scenario
  name, and each outbox batch delivers its rows one at a time, so two runs
  give byte-identical recordings.

Output goes to ``ui/src/recordings/<scenario>/case-actor.jsonl``.

Pull requests do not regenerate the recordings, so a recording may lag
``main`` for a few days.  The scheduled ``demo-recordings`` workflow runs
``--report-changes`` on ``main``, and while any recording is out of date it
keeps one "Refresh the demo recordings" Task open (exit status 3).  A PR
whose change needs current recordings, a UI change for example, regenerates
them itself.

The package is grouped by concern: :mod:`.topology` reads the container
layout, :mod:`.runner` hosts the nodes and runs a scenario, :mod:`.ledgers`
reads the run's ledger dump and checks the replicas, :mod:`.layout` owns the
committed files, and :mod:`.cli` is the ``export-demo-recordings`` command.

Usage::

    uv run export-demo-recordings                 # every scenario
    uv run export-demo-recordings --scenario rv   # one scenario
    uv run export-demo-recordings --check         # the recorded set only
    uv run export-demo-recordings --report-changes  # exit 3 if any changed
"""

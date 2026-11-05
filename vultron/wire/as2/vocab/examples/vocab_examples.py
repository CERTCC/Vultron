#!/usr/bin/env python
"""
Provides tools for generating examples of Vultron ActivityStreams objects.

Used within the Vultron documentation to provide examples of Vultron ActivityStreams objects.

When run as a script, this module generates a set of example objects and writes them to
``docs/reference/examples/``.  Re-run this generator whenever a new example function is
added or an existing wire object changes shape so that the committed JSON files stay
in sync with the current vocabulary.

To regenerate from the repo root::

    uv run python vultron/wire/as2/vocab/examples/vocab_examples.py

The generator is deterministic: every id it derives and every timestamp it
stamps comes from a fixed name or from ``EXAMPLE_TIMESTAMP``, so two runs over
an unchanged tree write identical bytes and a change to one example rewrites
only that example's file (``_example_scope``, #5776).

The test ``test/architecture/test_vocab_examples_current.py`` fails when the
committed files drift from what this generator produces, in their file list or
in their values.
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from vultron.wire.as2.vocab.examples._base import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples._base import (  # noqa: F401
    _CASE_ACTOR,
    _COORDINATOR,
    ACTOR_FUNCS,
    _example_scope,
    case,
    case_actor,
    coordinator,
    finder,
    gen_report,
    obj_to_file,
    vendor,
)
from vultron.wire.as2.vocab.examples.actor import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.actor import (  # noqa: F401
    accept_actor_recommendation,
    accept_case_participant_offer,
    offer_case_participant,
    recommend_actor,
    reject_actor_recommendation,
    reject_case_participant_offer,
    request_invite_actor_to_case,
)
from vultron.wire.as2.vocab.examples.case import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.case import (  # noqa: F401
    accept_case_ownership_transfer,
    accept_case_participant_role,
    add_report_to_case,
    announce_case,
    close_case,
    create_case,
    defer_case,
    engage_case,
    forward_case_participant_role,
    offer_case_ownership_transfer,
    offer_case_participant_role,
    populated_case,
    propose_case_ownership_transfer,
    reengage_case,
    reject_case_ownership_transfer,
    reject_case_participant_role,
    undo_case_ownership_transfer,
    update_case,
)
from vultron.wire.as2.vocab.examples.case_proposal import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.case_proposal import (
    accept_case_proposal,
    create_case_proposal,
    reject_case_proposal,
)
from vultron.wire.as2.vocab.examples.embargo import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.embargo import (
    abandon_embargo_proposal,
    accept_embargo,
    accept_embargo_revision,
    activate_embargo,
    activate_embargo_revision,
    announce_embargo,
    announce_embargo_termination,
    create_embargo_consent,
    create_embargo_event,
    embargo_event,
    notify_embargo_termination,
    propose_embargo,
    propose_embargo_revision,
    reject_embargo,
    reject_embargo_proposal,
    reject_embargo_revision,
    reject_embargo_revision_proposal,
    relay_embargo_proposal,
    remove_embargo,
    undo_embargo_invite,
    update_embargo_consent,
    withdraw_from_embargo,
)
from vultron.wire.as2.vocab.examples.fault import (
    create_processing_fault,
    refusal_notice,
)
from vultron.wire.as2.vocab.examples.note import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.note import (  # noqa: F401
    add_note_to_case,
    note,
    remove_note_from_case,
)
from vultron.wire.as2.vocab.examples.participant import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.participant import (  # noqa: F401
    accept_full_case_invite,
    accept_invite_to_case,
    add_coordinator_participant_to_case,
    add_finder_participant_to_case,
    add_vendor_participant_to_case,
    case_participant,
    coordinator_participant,
    create_participant,
    finder_participant,
    invite_to_case,
    invite_to_full_case,
    reject_full_case_invite,
    reject_invite_to_case,
    remove_participant_from_case,
    rm_invite_to_case,
    tentative_reject_full_case_invite,
    update_participant,
    vendor_participant,
)
from vultron.wire.as2.vocab.examples.report import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.report import (
    close_report,
    create_report,
    invalidate_report,
    read_report,
    submit_report,
    validate_report,
)
from vultron.wire.as2.vocab.examples.status import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.status import (
    add_attacks_observed_to_case,
    add_attacks_observed_to_participant,
    add_exploit_public_to_case,
    add_exploit_public_to_participant,
    add_fix_deployment_to_participant,
    add_fix_readiness_to_participant,
    add_public_awareness_to_case,
    add_public_awareness_to_participant,
    add_status_to_case,
    add_status_to_participant,
    add_vendor_awareness_to_participant,
    case_status,
    participant_status,
)
from vultron.wire.as2.vocab.examples.sync import *  # noqa: F403  # CS-03-001
from vultron.wire.as2.vocab.examples.sync import (
    announce_case_ledger_entry,
    read_case_ledger_entry,
    reject_case_ledger_entry,
)

#: Every example the generator writes, in the order it writes them, as
#: ``(builder, filename)``.  A filename of ``None`` means the builder's own
#: name with a ``.json`` suffix, which is the usual case; the few entries that
#: name a file do so because the docs page refers to it under that name.
#:
#: One table rather than sixty copies of "build it, write it" (CS-22-001): a
#: new example is one row, and :func:`check_tables` refuses two rows that
#: would claim one filename — ``rm_invite_to_case`` and ``invite_to_case``
#: both wrote ``invite_to_case.json``, so the first of them was generated and
#: thrown away on every run.
EXAMPLES: tuple[tuple[Callable[[], BaseModel], str | None], ...] = (
    # the actors, and the report and case every other example refers to
    (finder, None),
    (vendor, None),
    (coordinator, None),
    (gen_report, "vulnerability_report.json"),
    # the report workflow
    (create_report, None),
    (submit_report, None),
    (read_report, None),
    (validate_report, None),
    (invalidate_report, None),
    (close_report, None),
    # the case workflow
    (create_case, None),
    (add_report_to_case, None),
    (add_vendor_participant_to_case, None),
    (add_finder_participant_to_case, None),
    (engage_case, None),
    (close_case, None),
    (defer_case, None),
    (reengage_case, None),
    (update_case, None),
    (add_note_to_case, None),
    (remove_note_from_case, None),
    # case ownership transfer
    (propose_case_ownership_transfer, None),
    (offer_case_ownership_transfer, None),
    (accept_case_ownership_transfer, None),
    (reject_case_ownership_transfer, None),
    (undo_case_ownership_transfer, None),
    # actor recommendation (the GI actor-suggestion handshake)
    (recommend_actor, None),
    (accept_actor_recommendation, None),
    (reject_actor_recommendation, None),
    (request_invite_actor_to_case, None),
    # participants and invitations
    (create_participant, None),
    (update_participant, None),
    (case_participant, None),
    (invite_to_case, None),
    (accept_invite_to_case, None),
    (reject_invite_to_case, None),
    (invite_to_full_case, None),
    (accept_full_case_invite, None),
    (tentative_reject_full_case_invite, None),
    (reject_full_case_invite, None),
    (remove_participant_from_case, None),
    # case and participant status
    (case_status, None),
    (add_status_to_case, None),
    (participant_status, None),
    (add_status_to_participant, None),
    # embargo lifecycle
    (embargo_event, None),
    (create_embargo_event, None),
    (propose_embargo, None),
    (relay_embargo_proposal, None),
    (accept_embargo, None),
    (reject_embargo, None),
    (reject_embargo_proposal, None),
    (abandon_embargo_proposal, None),
    (activate_embargo, None),
    (announce_embargo, None),
    (withdraw_from_embargo, None),
    (remove_embargo, None),
    (undo_embargo_invite, None),
    (create_embargo_consent, None),
    (update_embargo_consent, None),
    (propose_embargo_revision, None),
    (accept_embargo_revision, None),
    (reject_embargo_revision, None),
    (reject_embargo_revision_proposal, None),
    (activate_embargo_revision, None),
    (notify_embargo_termination, None),
    (announce_embargo_termination, None),
    # case announcement (ANNOUNCE_VULNERABILITY_CASE — after Accept(Invite))
    (announce_case, None),
    # role delegation (ADR-0039) — distinct from the actor-suggestion handshake
    (offer_case_participant_role, None),
    (forward_case_participant_role, None),
    (accept_case_participant_role, None),
    (reject_case_participant_role, None),
    # case proposal (pre-case bootstrap, ADR-0023)
    (create_case_proposal, None),
    (accept_case_proposal, None),
    (reject_case_proposal, None),
    # ledger replication (SYNC substrate, ADR-0077)
    (announce_case_ledger_entry, None),
    (reject_case_ledger_entry, None),
    (read_case_ledger_entry, None),
    # one example per occasion (MSM-08-003, ADR-0128): each collapsed
    # occasion shows its own distinguishing value
    (add_vendor_awareness_to_participant, None),
    (add_fix_readiness_to_participant, None),
    (add_fix_deployment_to_participant, None),
    (add_public_awareness_to_participant, None),
    (add_exploit_public_to_participant, None),
    (add_attacks_observed_to_participant, None),
    (add_public_awareness_to_case, None),
    (add_exploit_public_to_case, None),
    (add_attacks_observed_to_case, None),
    # fault reporting
    (create_processing_fault, None),
    (refusal_notice, None),
)

#: The inline objects written as files of their own, as
#: ``(activity example, attribute, filename)``.  The docs show a case and a
#: participant record on their own pages, and each must be the very object the
#: activity carried, so it is read off that activity's one built instance —
#: :func:`build_examples` builds each row of :data:`EXAMPLES` once and these
#: rows read from the result, never from a second call.  Every builder named
#: here is therefore also a row of :data:`EXAMPLES`, which
#: :func:`check_tables` pins.
INLINE_OBJECTS: tuple[tuple[Callable[[], BaseModel], str, str], ...] = (
    (create_case, "object_", "vulnerability_case.json"),
    (add_vendor_participant_to_case, "object_", "vendor_participant.json"),
    (add_finder_participant_to_case, "object_", "finder_participant.json"),
)


def example_filename(
    builder: Callable[[], BaseModel], filename: str | None
) -> str:
    """The file a row of :data:`EXAMPLES` is written to."""
    return filename or f"{builder.__name__}.json"


def check_tables() -> None:
    """Refuse a table that would write one file twice, before any write.

    The defect this guards is the one #5776 found: ``rm_invite_to_case`` and
    ``invite_to_case`` both wrote ``invite_to_case.json``, so whichever ran
    first was generated and thrown away on every run, and no gate could see
    it — the generated *file set* stayed correct, so the currency check's
    file-set comparison passed.

    Also pins what :data:`INLINE_OBJECTS` rests on: each of its builders is a
    row of :data:`EXAMPLES`, so the inline object is read off that row's one
    built instance rather than from a second call.
    """
    names = [
        example_filename(builder, filename) for builder, filename in EXAMPLES
    ]
    names += [filename for _, _, filename in INLINE_OBJECTS]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ValueError(
            "two example rows write one file, so one of them would be "
            f"generated and overwritten: {repeated}"
        )
    scopes = [builder.__name__ for builder, _ in EXAMPLES]
    repeated_scopes = sorted(
        {scope for scope in scopes if scopes.count(scope) > 1}
    )
    if repeated_scopes:
        raise ValueError(
            "two example rows share an id scope, so their ids would "
            f"collide: {repeated_scopes}"
        )
    known = set(scopes)
    orphans = sorted(
        builder.__name__
        for builder, _, _ in INLINE_OBJECTS
        if builder.__name__ not in known
    )
    if orphans:
        raise ValueError(
            "an INLINE_OBJECTS row names a builder that EXAMPLES does not, "
            f"so its object cannot be read off a built activity: {orphans}"
        )


def _build(builder: Callable[[], BaseModel]) -> BaseModel:
    """Build one example inside an id scope named for it.

    Every id the example mints and every stamp it reads is derived from the
    builder's name, so two runs of the generator write the same bytes and a
    change to one example leaves the other files alone (#5776).
    """
    with _example_scope(builder.__name__):
        return builder()


def build_examples() -> dict[str, BaseModel]:
    """Every example to write, keyed by filename, built before anything is.

    Building first and writing after is what makes a regeneration
    all-or-nothing: a builder that raises leaves the committed tree as it
    was, instead of a tree half-rewritten at whichever row failed, where the
    currency check then reports the rows that did change rather than the
    cause.
    """
    check_tables()
    built: dict[str, BaseModel] = {}
    by_builder: dict[str, BaseModel] = {}
    for builder, filename in EXAMPLES:
        example = _build(builder)
        by_builder[builder.__name__] = example
        built[example_filename(builder, filename)] = example
    for builder, attribute, filename in INLINE_OBJECTS:
        inline = getattr(by_builder[builder.__name__], attribute)
        if not isinstance(inline, BaseModel):
            raise TypeError(
                f"{builder.__name__}().{attribute} is not a model, so "
                f"{filename} cannot be written from it: {inline!r}"
            )
        built[filename] = inline
    return built


def main(outdir=None):
    if outdir is None:
        outdir = Path(__file__).parents[5] / "docs" / "reference" / "examples"
    else:
        outdir = Path(outdir)
    print(f"Generating examples to: {outdir}")

    examples = build_examples()

    # ensure the output directory exists
    outdir.mkdir(parents=True, exist_ok=True)

    for filename, example in examples.items():
        obj_to_file(example, str(outdir / filename))


if __name__ == "__main__":
    main()

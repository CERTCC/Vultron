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

"""A run's verdict, the form two runs are compared in (DEMOCI-11-058 to -072).

The recording clock ticks 10 ms on every read and every id is drawn from one
seeded generator, so a shifted clock or one extra draw moves every later
timestamp, digest, signature and id without changing what the scenario did.
These tests hold the line between that and a real change, in both
directions: id, time and signature churn compares equal, and a changed note
text, an added or reordered act, a changed act type, state or role, and a
changed check label or outcome each compare different.
"""

import importlib
import json
import pkgutil
import re
import typing
from collections.abc import Iterator, Mapping
from dataclasses import replace

import pytest
from pydantic import BaseModel

import vultron.core.models
import vultron.wire.as2.vocab
from test.support.act_clock import ACT_AT
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.demo.recordings.traces import (
    CHECKS_FILENAME,
    LEDGER_FILENAME,
    TIMESTAMP_PLACEHOLDER,
    VERDICT_FIELDS,
    ScenarioRun,
    normalize_run,
    prune_runs,
    read_runs,
    write_run,
)
from vultron.demo.utils.check_tree import (
    CheckKind,
    CheckNode,
    CheckOutcome,
)
from vultron.errors import DemoRecordingError
from vultron.wire.as2.vocab.base.registry import VOCABULARY, WIRE_TYPE_MAP

CASE_ID = "urn:uuid:ed045a61-5ca4-4c92-b278-3dff7bb2199f"
ACTIVITY_ID = "urn:uuid:04d8febf-f9aa-5967-a17f-54e8c633ea16"
VENDOR = "http://actor1:7999/api/v2/actors/actor1"
CASE_ACTOR = "http://case-actor:7999/api/v2/actors/case-actor"

#: A second draw of the same two ids, as a run with one extra draw before them
#: would make: different values, same order of first appearance.
OTHER_CASE_ID = "urn:uuid:11111111-1111-4111-8111-111111111111"
OTHER_ACTIVITY_ID = "urn:uuid:22222222-2222-4222-8222-222222222222"

#: A SHA-256 digest as a ledger entry carries one.
_DIGEST_VALUE = re.compile(r'"[0-9a-f]{64}"')


def _entry(
    index: int,
    *,
    case_id: str = CASE_ID,
    activity_id: str = ACTIVITY_ID,
    published: str = "2026-01-01T00:00:00.560000+00:00",
    note: str = "first contact",
    digest: str = "a" * 64,
    signature: str = "zFirstSignature",
    act: str = "Create",
    rm_state: str = "RECEIVED",
    role: str = "vendor",
) -> dict[str, object]:
    """One ledger entry, in the shape the recorder writes one.

    The payload carries a proof, and so does the activity it embeds, as a
    signed act does: a signature covers the raw ids, so it changes whenever
    an id does.
    """
    return {
        "id": f"{case_id}/log/{index}",
        "type": "CaseLedgerEntry",
        "published": published,
        "receivedAt": published,
        "caseId": case_id,
        "logIndex": index,
        "logObjectId": case_id,
        "semanticType": "create_case",
        "payloadSnapshot": {
            "id": activity_id,
            "type": act,
            "published": published,
            "actor": CASE_ACTOR,
            "to": [VENDOR],
            "content": note,
            "senderSequence": index + 1,
            "ledgerPosition": {"logIndex": index - 1, "entryHash": digest},
            "object": {
                "id": case_id,
                "type": "Offer",
                "actor": VENDOR,
                "proof": _proof(signature, published),
            },
            "target": {
                "id": case_id,
                "type": "CaseParticipant",
                "attributedTo": VENDOR,
                "caseRoles": [role, "case_owner"],
                "participantStatuses": [
                    {
                        "id": f"{case_id}/status/{index}",
                        "type": "ParticipantStatus",
                        "published": published,
                        "rmState": rm_state,
                        "proof": _proof(signature, published),
                    }
                ],
            },
            "proof": _proof(signature, published),
        },
        "prevLogHash": "0" * 64,
        "entryHash": digest,
    }


def _proof(signature: str, created: str) -> dict[str, object]:
    """A Data Integrity proof, as a signed activity carries one."""
    return {
        "type": "DataIntegrityProof",
        "cryptosuite": "eddsa-jcs-2022",
        "verificationMethod": f"{CASE_ACTOR}#main-key",
        "proofPurpose": "assertionMethod",
        "created": created,
        "proofValue": signature,
    }


def _reversed_keys(value: object) -> object:
    """*value* with every mapping's keys in reverse order, at every depth."""
    if isinstance(value, dict):
        return {
            key: _reversed_keys(item) for key, item in reversed(value.items())
        }
    if isinstance(value, list):
        return [_reversed_keys(item) for item in value]
    return value


def _ledger(*entries: object) -> str:
    return "".join(f"{json.dumps(entry)}\n" for entry in entries)


CHECKS = (
    CheckNode(
        kind=CheckKind.GATE,
        label=f"case {CASE_ID} reached RM.VALID",
        outcome=CheckOutcome.PASSED,
        reads=("actor1",),
        children=(
            CheckNode(
                kind=CheckKind.CHECK,
                label="the Vendor holds the case",
                outcome=CheckOutcome.PASSED,
                reads=("actor1",),
            ),
        ),
    ),
)


def _run(
    ledger: str | None = None, checks: tuple[CheckNode, ...] = CHECKS
) -> ScenarioRun:
    return ScenarioRun(
        "rv",
        ledger=_ledger(_entry(0), _entry(1)) if ledger is None else ledger,
        checks=checks,
    )


BASE = _run()


class TestWhatComparesEqual:
    @pytest.mark.spec("DEMOCI-11-059")
    def test_a_shifted_clock_compares_equal(self):
        shifted = _run(
            _ledger(
                _entry(0, published="2026-03-04T09:17:21.110000+00:00"),
                _entry(
                    1,
                    published="2026-03-04T09:17:21.120000+00:00",
                    digest="b" * 64,
                ),
            )
        )
        assert normalize_run(shifted) == normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-070")
    def test_an_extra_id_draw_compares_equal(self):
        redrawn = _run(
            _ledger(
                _entry(
                    0,
                    case_id=OTHER_CASE_ID,
                    activity_id=OTHER_ACTIVITY_ID,
                ),
                _entry(
                    1,
                    case_id=OTHER_CASE_ID,
                    activity_id=OTHER_ACTIVITY_ID,
                ),
            ),
            checks=(
                replace(
                    CHECKS[0],
                    label=f"case {OTHER_CASE_ID} reached RM.VALID",
                ),
            ),
        )
        assert normalize_run(redrawn) == normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-059")
    def test_redrawn_ids_and_their_signatures_compare_equal(self):
        """The shape of PR #6182's diff (#6194): ids drawn another way, so
        every signature over them changes, on the payload and on the
        activity it embeds, and nothing the scenario did changes."""
        redrawn = _run(
            _ledger(
                *(
                    _entry(
                        index,
                        case_id=OTHER_CASE_ID,
                        activity_id=OTHER_ACTIVITY_ID,
                        signature=f"zOtherSignature{index}",
                    )
                    for index in (0, 1)
                )
            ),
            checks=(
                replace(
                    CHECKS[0],
                    label=f"case {OTHER_CASE_ID} reached RM.VALID",
                ),
            ),
        )
        assert normalize_run(redrawn) == normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-059")
    def test_a_new_derived_field_compares_equal_without_an_edit(self):
        """An allow-list, not a noise list: a field nobody has named yet, such
        as a new digest or signature, is left out of the verdict as it
        stands, so it cannot trip the comparison the way ``proofValue``
        did."""

        def with_derived(index: int, value: str) -> dict[str, object]:
            entry = _entry(index)
            entry["contentDigest"] = value
            snapshot = entry["payloadSnapshot"]
            assert isinstance(snapshot, dict)
            snapshot["signature"] = {"value": value, "keyId": value}
            return entry

        assert normalize_run(
            _run(_ledger(with_derived(0, "x"), with_derived(1, "y")))
        ) == normalize_run(
            _run(_ledger(with_derived(0, "p"), with_derived(1, "q")))
        )

    @pytest.mark.spec("DEMOCI-11-058")
    def test_the_order_fields_are_written_in_compares_equal(self):
        """A serializer writing fields in another order changes no act."""
        flipped = _run(_ledger(*(_reversed_keys(_entry(i)) for i in (0, 1))))
        assert normalize_run(flipped) == normalize_run(BASE)


class TestWhatComparesDifferent:
    @pytest.mark.spec("DEMOCI-11-060")
    def test_a_changed_note_text_compares_different(self):
        changed = _run(_ledger(_entry(0), _entry(1, note="second contact")))
        assert normalize_run(changed) != normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-060")
    def test_an_added_entry_compares_different(self):
        added = _run(_ledger(_entry(0), _entry(1), _entry(2)))
        assert normalize_run(added) != normalize_run(BASE)
        assert len(normalize_run(added).ledger) == 3

    @pytest.mark.spec("DEMOCI-11-058")
    def test_a_reordered_act_compares_different(self):
        base = _run(_ledger(_entry(0), _entry(1, act="Accept")))
        swapped = _run(_ledger(_entry(0, act="Accept"), _entry(1)))
        assert normalize_run(swapped) != normalize_run(base)

    @pytest.mark.spec("DEMOCI-11-060")
    def test_a_changed_act_type_compares_different(self):
        changed = _run(_ledger(_entry(0), _entry(1, act="Reject")))
        assert normalize_run(changed) != normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-060")
    def test_a_changed_state_compares_different(self):
        changed = _run(_ledger(_entry(0), _entry(1, rm_state="VALID")))
        assert normalize_run(changed) != normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-060")
    def test_a_changed_role_compares_different(self):
        changed = _run(_ledger(_entry(0), _entry(1, role="coordinator")))
        assert normalize_run(changed) != normalize_run(BASE)

    @pytest.mark.spec("DEMOCI-11-060")
    @pytest.mark.parametrize(
        ("field", "before", "after"),
        [
            ("result", CASE_ID, OTHER_ACTIVITY_ID),
            ("cc", [VENDOR], [CASE_ACTOR]),
            ("removalActivity", None, ACTIVITY_ID),
            (
                "embargoRegister",
                [{"status": "ENDED", "termination": {"reason": "EXPIRED"}}],
                [{"status": "ENDED", "termination": {"reason": "CANCELLED"}}],
            ),
            (
                "object",
                {
                    "type": "Organization",
                    "embargoPolicy": {"preferredDuration": "P90D"},
                },
                {
                    "type": "Organization",
                    "embargoPolicy": {"preferredDuration": "P7D"},
                },
            ),
        ],
        ids=[
            "result",
            "audience",
            "removal",
            "register-termination",
            "embargo-policy",
        ],
    )
    def test_a_changed_act_detail_compares_different(
        self, field: str, before: object, after: object
    ):
        """What an act resulted in, whom it also went to, a participant's
        removal, how an embargo ended and the embargo terms an actor states
        are all part of the verdict."""

        def run(value: object) -> ScenarioRun:
            entries = [_entry(0), _entry(1)]
            snapshot = entries[1]["payloadSnapshot"]
            assert isinstance(snapshot, dict)
            if value is not None:
                snapshot[field] = value
            return _run(_ledger(*entries))

        assert normalize_run(run(after)) != normalize_run(run(before))

    @pytest.mark.spec("DEMOCI-11-060")
    def test_a_changed_check_label_compares_different(self):
        moved = _run(checks=(replace(CHECKS[0], label="the Vendor answered"),))
        assert normalize_run(moved).ledger == normalize_run(BASE).ledger
        assert normalize_run(moved).checks != normalize_run(BASE).checks

    @pytest.mark.spec("DEMOCI-11-058")
    def test_a_changed_check_outcome_compares_different(self):
        failed = _run(
            checks=(
                replace(
                    CHECKS[0],
                    children=(
                        replace(
                            CHECKS[0].children[0],
                            outcome=CheckOutcome.FAILED,
                        ),
                    ),
                ),
            )
        )
        assert normalize_run(failed).ledger == normalize_run(BASE).ledger
        assert normalize_run(failed).checks != normalize_run(BASE).checks


def _subclasses(cls: type[BaseModel]) -> list[type[BaseModel]]:
    """*cls* and every class below it that ``vultron`` defines.

    A test module's own model (a probe ``CoreObject`` subclass) can never be
    on a ledger, and counting it would make this guard depend on which test
    modules ran first in the same process (#4729).
    """
    found, pending = [cls], [cls]
    while pending:
        for sub in pending.pop().__subclasses__():
            if not sub.__module__.startswith("vultron."):
                continue
            found.append(sub)
            pending.append(sub)
    return found


def _models_in(annotation: object) -> Iterator[type[BaseModel]]:
    """The models a field annotation names, through unions and containers."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
        return
    for argument in typing.get_args(annotation):
        yield from _models_in(argument)


def _ledgerable_models() -> set[type[BaseModel]]:
    """Every model a ledger entry can carry.

    A ledger entry's payload is an activity.  Many of an activity's fields
    are typed ``Any`` (``object``, ``target``, ``result``), so the walk does
    not start from the activity alone: it starts from every class a ``type``
    value names, in the core and the wire vocabularies, which is every
    object a ledger entry can serialize.  From there it follows the fields'
    annotations to the case, its participants and their statuses, the
    embargo register, an actor's embargo policy and how an embargo ends.
    """
    for package in (vultron.core.models, vultron.wire.as2.vocab):
        for module in pkgutil.walk_packages(
            package.__path__, f"{package.__name__}."
        ):
            importlib.import_module(module.name)
    seen: set[type[BaseModel]] = set()
    pending: list[type[BaseModel]] = [
        *_subclasses(VultronActivity),
        VulnerabilityCase,
        CaseLedgerEntry,
        *CORE_VOCABULARY.values(),
        *VOCABULARY.values(),
        *WIRE_TYPE_MAP.values(),
    ]
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        for field in model.model_fields.values():
            for named in _models_in(field.annotation):
                pending.extend(_subclasses(named))
    return seen


def _is_mapping(annotation: object) -> bool:
    """Whether *annotation* names a ``dict`` or ``Mapping``, through unions."""
    origin = typing.get_origin(annotation) or annotation
    if isinstance(origin, type) and issubclass(origin, Mapping):
        return True
    return any(_is_mapping(arg) for arg in typing.get_args(annotation))


def _wire_names(models: set[type[BaseModel]]) -> set[str]:
    """The serialized name of every field of *models*."""
    return {
        field.serialization_alias or field.alias or name
        for model in models
        for name, field in model.model_fields.items()
    }


#: The fields a ledger entry can carry that are not in its verdict, each with
#: why.  With :data:`VERDICT_FIELDS` this classifies every field, so a new
#: field fails ``test_every_ledgerable_field_is_classified`` until someone
#: decides which side it is on (DEMOCI-11-072).
_OUTSIDE_THE_VERDICT = frozenset(
    {
        # Minted by the clock, or derived from a time it minted.
        "deleted",
        "endTime",
        "published",
        "receivedAt",
        "rsvpDeadline",
        "startTime",
        "updated",
        # Hash-chain digests, and the position pointer that carries one.
        "entryHash",
        "genesisHash",
        "ledgerPosition",
        "prevLogHash",
        # Transport counters and the replication term.
        "expectedSenderSequence",
        "senderSequence",
        "term",
        # Where an actor is reached and the keys it signs with: fixed by the
        # cast's addresses (DEMOCI-11-020), or derived from keys.
        "assertionMethod",
        "controller",
        "endpoints",
        "inbox",
        "outbox",
        "publicKeyMultibase",
        # Lookup indexes derived from fields the verdict already holds.
        "actorParticipantIndex",
        "pendingEmbargoProposalIndex",
        # The JSON-LD context, the same on every object.
        "@context",
    }
)

#: Mapping-typed verdict fields whose keys are field names, not data: the
#: projection walks into them as it does into a model.
_FIELD_NAMED_MAPPINGS = frozenset(
    {
        # The activity an entry records, stored as its serialized dict.
        "payloadSnapshot",
    }
)

#: A field name that holds a state, a role, a status or a consent: a field a
#: verdict must never leave out (DEMOCI-11-072).
_VERDICT_SHAPED = re.compile(
    r"(?i)state|role|status|consent|engagement|joined"
)


class TestWhatTheVerdictHolds:
    @pytest.mark.spec("DEMOCI-11-070")
    def test_ids_are_relabelled_by_first_appearance(self):
        first = json.loads(normalize_run(BASE).ledger[0])
        assert first["caseId"] == "urn:uuid:id-1"
        assert first["id"] == "urn:uuid:id-1/log/0"
        assert first["payloadSnapshot"]["id"] == "urn:uuid:id-2"

    @pytest.mark.spec("DEMOCI-11-070")
    def test_one_mapping_covers_the_ledger_and_the_check_labels(self):
        normalized = normalize_run(BASE)
        assert "urn:uuid:id-1" in normalized.ledger[0]
        assert normalized.checks[0].startswith(
            "gate case urn:uuid:id-1 reached RM.VALID -> passed"
        )

    @pytest.mark.spec("DEMOCI-11-060")
    def test_the_casts_actor_uris_are_left_as_they_are(self):
        """The cast is fixed (DEMOCI-11-020), so its ids never shift, and a
        diff that still names actor1 is a diff a person can read."""
        first = json.loads(normalize_run(BASE).ledger[0])
        assert first["payloadSnapshot"]["actor"] == CASE_ACTOR
        assert first["payloadSnapshot"]["to"] == [VENDOR]

    @pytest.mark.spec("DEMOCI-11-059")
    def test_times_digests_proofs_and_counters_are_left_out(self):
        first = json.loads(normalize_run(BASE).ledger[0])
        snapshot = first["payloadSnapshot"]
        for left_out in ("published", "receivedAt", "prevLogHash"):
            assert left_out not in first
        for left_out in ("published", "proof", "senderSequence"):
            assert left_out not in snapshot
        assert "ledgerPosition" not in snapshot
        assert "proof" not in snapshot["object"]
        [status] = snapshot["target"]["participantStatuses"]
        assert "published" not in status
        assert "proof" not in status

    @pytest.mark.spec("DEMOCI-11-071")
    def test_a_timestamp_quoted_in_a_kept_string_reads_as_a_placeholder(self):
        quoted = _run(
            _ledger(_entry(0, note="ends 2026-01-04T00:00:00.510000+00:00"))
        )
        snapshot = json.loads(normalize_run(quoted).ledger[0])[
            "payloadSnapshot"
        ]
        assert snapshot["content"] == f"ends {TIMESTAMP_PLACEHOLDER}"

    @pytest.mark.spec("DEMOCI-11-060")
    def test_the_verdict_fields_are_kept_as_they_are(self):
        first = json.loads(normalize_run(BASE).ledger[0])
        snapshot = first["payloadSnapshot"]
        assert first["logIndex"] == 0
        assert first["semanticType"] == "create_case"
        assert snapshot["type"] == "Create"
        assert snapshot["content"] == "first contact"
        assert snapshot["target"]["caseRoles"] == ["vendor", "case_owner"]
        assert snapshot["target"]["participantStatuses"] == [
            {
                "id": "urn:uuid:id-1/status/0",
                "rmState": "RECEIVED",
                "type": "ParticipantStatus",
            }
        ]

    @pytest.mark.spec("DEMOCI-11-072")
    def test_every_ledgerable_field_is_classified(self):
        """The cost of an allow-list is that a field counts only once it is
        named.  So every field a ledger entry can carry is classified, in
        the verdict or outside it, and a new one fails here until someone
        decides, rather than silently going uncompared."""
        fields = _wire_names(_ledgerable_models())
        assert {"rmState", "caseRoles", "status", "termination"} <= fields, (
            "the walk did not reach the case, its participants and the "
            "embargo register; the guard checks nothing"
        )
        unclassified = fields - VERDICT_FIELDS - _OUTSIDE_THE_VERDICT
        assert not unclassified, (
            "fields a ledger entry can carry are neither in VERDICT_FIELDS "
            f"nor named as outside the verdict: {sorted(unclassified)}"
        )

    @pytest.mark.spec("DEMOCI-11-072")
    def test_no_state_or_role_field_is_left_out(self):
        """Keyed on a field's shape, not on a list of names (#5535)."""
        left_out = {
            name
            for name in _OUTSIDE_THE_VERDICT
            if _VERDICT_SHAPED.search(name)
        }
        assert not left_out, (
            f"a state, role, status or consent field is left out: {left_out}"
        )

    @pytest.mark.spec("DEMOCI-11-072")
    def test_the_walk_reaches_what_activities_carry(self):
        """``object``, ``target`` and ``result`` are typed ``Any``, so an
        annotation walk from the activity alone misses what they carry: a
        note, an actor and its embargo policy, a case stub."""
        names = {model.__name__ for model in _ledgerable_models()}
        assert {
            "VultronNote",
            "VultronOrganization",
            "EmbargoPolicy",
            "VulnerabilityRecord",
        } <= names

    @pytest.mark.spec("DEMOCI-11-072")
    def test_no_verdict_field_is_a_mapping(self):
        """``_project`` keeps a mapping's keys only when they are verdict
        fields, so a field holding a mapping keyed by data (ids, actor URIs)
        would compare as ``{}`` whatever it held."""
        mappings = {
            field.serialization_alias or field.alias or name
            for model in _ledgerable_models()
            for name, field in model.model_fields.items()
            if _is_mapping(field.annotation)
        }
        assert "payloadSnapshot" in mappings, "the walk found no mapping"
        mappings -= _FIELD_NAMED_MAPPINGS
        assert not mappings & VERDICT_FIELDS, (
            "a verdict field holds a mapping keyed by data, which the "
            f"projection would empty: {sorted(mappings & VERDICT_FIELDS)}"
        )

    def test_the_two_lists_do_not_overlap(self):
        assert not VERDICT_FIELDS & _OUTSIDE_THE_VERDICT

    @pytest.mark.spec("DEMOCI-11-059")
    def test_no_hash_chain_digest_of_a_real_entry_survives(self):
        """Keyed on a digest's shape, not on the field names.

        A renamed digest field keeps its 64-character hex value, so a rename
        that put it in the verdict would fail here (#5535).
        """
        entry = CaseLedgerEntry(
            case_id=CASE_ID,
            log_index=0,
            log_object_id=CASE_ID,
            semantic_type="create_case",
            payload_snapshot={"id": ACTIVITY_ID, "type": "Create"},
            prev_log_hash="0" * 64,
            entry_hash="a" * 64,
            received_at=ACT_AT,
            published=ACT_AT,
        )
        line = json.dumps(
            entry.model_dump(by_alias=True, exclude_none=True, mode="json")
        )
        assert re.search(_DIGEST_VALUE, line), "the fixture holds no digest"

        [normalized] = normalize_run(_run(f"{line}\n")).ledger

        assert not re.search(_DIGEST_VALUE, normalized), (
            "a hash-chain digest is in the verdict; a digest field must not "
            "be in VERDICT_FIELDS"
        )

    def test_a_ledger_line_that_is_not_an_entry_is_refused(self):
        with pytest.raises(DemoRecordingError, match="ledger line 2"):
            normalize_run(_run('{"logIndex": 0}\nnot json\n'))

    def test_a_ledger_line_that_is_not_an_object_is_refused(self):
        with pytest.raises(DemoRecordingError, match="not a ledger entry"):
            normalize_run(_run("[1, 2]\n"))


class TestWrittenRuns:
    def test_a_written_run_reads_back(self, tmp_path):
        write_run(BASE, tmp_path)
        assert read_runs(tmp_path) == {"rv": BASE}

    def test_only_the_two_traces_are_written(self, tmp_path):
        directory = write_run(BASE, tmp_path)
        assert sorted(path.name for path in directory.iterdir()) == sorted(
            (CHECKS_FILENAME, LEDGER_FILENAME)
        )

    def test_a_directory_of_runs_reads_back_by_name(self, tmp_path):
        write_run(BASE, tmp_path)
        write_run(replace(BASE, scenario="rvv"), tmp_path)
        assert sorted(read_runs(tmp_path)) == ["rv", "rvv"]

    def test_a_half_written_run_is_refused(self, tmp_path):
        (tmp_path / "rv").mkdir()
        (tmp_path / "rv" / LEDGER_FILENAME).write_text("{}\n")
        with pytest.raises(DemoRecordingError, match="incomplete"):
            read_runs(tmp_path)

    def test_an_unreadable_check_tree_is_refused(self, tmp_path):
        write_run(BASE, tmp_path)
        (tmp_path / "rv" / CHECKS_FILENAME).write_text("{oops")
        with pytest.raises(DemoRecordingError, match="not readable"):
            read_runs(tmp_path)

    @pytest.mark.parametrize("text", ["", "  \n"], ids=["zeroed", "blank"])
    def test_a_run_with_an_empty_ledger_is_refused(self, tmp_path, text):
        """A recorded run can never have an empty ledger, so two zeroed
        artifacts must not compare equal: that would be the gate passing over
        nothing rather than over no change."""
        write_run(BASE, tmp_path)
        (tmp_path / "rv" / LEDGER_FILENAME).write_text(text)
        with pytest.raises(
            DemoRecordingError, match=r"of 'rv' in .* empty ledger"
        ):
            read_runs(tmp_path)

    def test_a_check_tree_that_is_valid_json_but_no_tree_names_itself(
        self, tmp_path
    ):
        """`tree_from_json` raises `DemoRecordingError`, not `ValueError`, so
        this escaped naming neither the scenario nor the directory."""
        write_run(BASE, tmp_path)
        (tmp_path / "rv" / CHECKS_FILENAME).write_text('{"nodes": []}')
        with pytest.raises(
            DemoRecordingError, match=r"of 'rv' in .* not read"
        ):
            read_runs(tmp_path)

    def test_a_directory_holding_neither_trace_is_skipped(self, tmp_path):
        """A cache directory or a nested CI artifact is not a scenario, and
        must not take the whole comparison down naming itself as one."""
        write_run(BASE, tmp_path)
        (tmp_path / ".cache").mkdir()
        (tmp_path / ".cache" / "something").write_text("x")
        assert sorted(read_runs(tmp_path)) == ["rv"]

    def test_pruning_drops_the_runs_not_kept(self, tmp_path):
        write_run(BASE, tmp_path)
        write_run(replace(BASE, scenario="rvv"), tmp_path)
        (tmp_path / ".cache").mkdir()

        assert prune_runs(tmp_path, keep={"rv"}) == ["rvv"]

        assert sorted(read_runs(tmp_path)) == ["rv"]
        assert (tmp_path / ".cache").is_dir(), "pruning touched a non-run"

    def test_pruning_a_directory_that_does_not_exist_removes_nothing(
        self, tmp_path
    ):
        assert prune_runs(tmp_path / "missing", keep=set()) == []

    def test_a_path_that_is_not_a_directory_is_refused(self, tmp_path):
        with pytest.raises(DemoRecordingError, match="not a directory"):
            read_runs(tmp_path / "missing")

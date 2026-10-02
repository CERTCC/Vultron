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

"""A ``CasePersistence`` that holds writes back and commits them as one.

``EmbargoLifecycle.initialize_creation_embargo`` changes the case, the
participants' consent records and, for a contested creation, a revision's
``EmbargoEvent`` (EP-04-002, EP-04-003, CM-14-003).  Saved one at a time, a
failure part-way left the case past ``EM.NONE`` with the rest undone, and the
once-per-case guard then refused the rerun that would have finished it
(EP-04-012, #4142).  The shared consent helpers save each participant they
touch and re-read participants another helper has just changed, so the
operation runs them against this store instead: every write is staged, every
read sees what was staged, and :meth:`StagedCasePersistence.flush` hands the
whole set to the underlying store's ``save_many`` — one atomic transaction
(the CM-21-004 precedent).

A query the staging cannot answer faithfully — a listing, a search, a store
switch, a delete — is refused while anything is staged rather than answered
from the underlying store as if the staged writes were not there.
"""

from collections.abc import Iterable

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.protocol_pair import ProtocolPair
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import StorableRecord
from vultron.errors import VultronAlreadyExistsError, VultronError


class StagedPersistenceError(VultronError):
    """An operation the staging store cannot carry out faithfully."""


class StagedCasePersistence:
    """Stage writes over *inner*; :meth:`flush` commits them in one call.

    Staged objects are copied in and copied out, so a caller sees the
    store's usual contract: a read returns its own copy, and a change is
    kept only once it is saved.  Flush order is the order each object was
    first staged; a later save of the same id replaces its content in place.
    """

    def __init__(self, inner: CasePersistence) -> None:
        self._inner = inner
        self._staged: dict[str, PersistableModel] = {}

    # -- staging ------------------------------------------------------------

    @property
    def staged(self) -> list[PersistableModel]:
        """Copies of the staged objects, in flush order."""
        return [obj.model_copy(deep=True) for obj in self._staged.values()]

    def flush(self) -> None:
        """Commit every staged object through one ``save_many``, then clear.

        Nothing staged means nothing is written.  Should ``save_many`` raise,
        the staged set is kept; that the store then holds none of it rests
        on the adapter's ``save_many`` being atomic (CM-21-004).
        """
        if not self._staged:
            return
        self._inner.save_many(list(self._staged.values()))
        self._staged.clear()

    def _require_nothing_staged(self, operation: str) -> None:
        if self._staged:
            raise StagedPersistenceError(
                f"cannot {operation} with {len(self._staged)} staged"
                " write(s) pending: the answer would ignore them"
            )

    # -- CasePersistence ----------------------------------------------------

    @property
    def actor_id(self) -> str:
        return self._inner.actor_id

    def clone_for_actor(self, actor_id: str) -> CasePersistence:
        raise StagedPersistenceError(
            f"cannot switch to actor {actor_id!r}'s store: its writes would"
            " bypass the staged commit"
        )

    def create(self, record: StorableRecord | PersistableModel) -> None:
        if isinstance(record, StorableRecord):
            raise StagedPersistenceError(
                f"cannot stage raw record {record.id_!r}; stage the model"
            )
        if record.id_ in self._staged or (
            self._inner.read(record.id_) is not None
        ):
            raise VultronAlreadyExistsError(
                f"{record.type_} {record.id_!r} already exists"
            )
        self.save(record)

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None:
        staged = self._staged.get(object_id)
        if staged is not None:
            return staged.model_copy(deep=True)
        return self._inner.read(object_id, raise_on_missing=raise_on_missing)

    def read_case(
        self, case_id: str, raise_on_missing: bool = False
    ) -> VulnerabilityCase | None:
        if case_id not in self._staged:
            return self._inner.read_case(
                case_id, raise_on_missing=raise_on_missing
            )
        # A staged object shadows the store's, case or not (as ``read``).
        staged = self._staged[case_id]
        if isinstance(staged, VulnerabilityCase):
            return staged.model_copy(deep=True)
        if raise_on_missing:
            raise ValueError(
                f"Object at {case_id!r} is not a VulnerabilityCase"
            )
        return None

    def save(self, obj: PersistableModel) -> None:
        self._staged[obj.id_] = obj.model_copy(deep=True)

    def save_many(self, objs: list[PersistableModel]) -> None:
        for obj in objs:
            self.save(obj)

    def list_objects(self, type_key: str) -> Iterable[PersistableModel]:
        self._require_nothing_staged(f"list {type_key!r} objects")
        return self._inner.list_objects(type_key)

    def find_case_by_report_id(
        self, report_id: str
    ) -> VulnerabilityCase | None:
        self._require_nothing_staged("find a case by report id")
        return self._inner.find_case_by_report_id(report_id)

    def find_actor_by_short_id(self, short_id: str) -> PersistableModel | None:
        self._require_nothing_staged("find an actor by short id")
        return self._inner.find_actor_by_short_id(short_id)

    def find_case_by_short_id(self, short_id: str) -> VulnerabilityCase | None:
        self._require_nothing_staged("find a case by short id")
        return self._inner.find_case_by_short_id(short_id)

    def find_protocol_pair(
        self,
        case_id: str,
        request_event_type: str,
        object_id: str,
        reply_event_types: frozenset[str],
    ) -> ProtocolPair:
        self._require_nothing_staged("find a protocol pair")
        return self._inner.find_protocol_pair(
            case_id, request_event_type, object_id, reply_event_types
        )

    def delete(self, table: str, id_: str) -> bool:
        raise StagedPersistenceError(
            f"cannot stage a delete of {table} {id_!r}: save_many writes only"
        )

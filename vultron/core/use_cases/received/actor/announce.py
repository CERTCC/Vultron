"""Use cases for case actor/participant invitation and suggestion activities."""

import logging
from typing import Any, NamedTuple, cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.announce_case_received_tree import (
    create_announce_vulnerability_case_received_tree,
)
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.ledger_gap_buffer import (
    LedgerGapBuffer,
    get_ledger_gap_buffer,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.models._helpers import _as_id
from vultron.core.participants.authority import (
    has_local_participant_roster,
    resolve_case_manager_id,
)
from vultron.core.predicates.roles import has_case_manager_role
from vultron.core.use_cases._helpers import (
    _established_link_actor_id,
    _find_case_actor_id,
    resolve_receiving_actor_id,
)
from vultron.core.use_cases.received.sync import drain_gap_buffer

logger = logging.getLogger(__name__)


def _announced_case_manager_id(case_obj: Any) -> str | None:
    """Return the CASE_MANAGER named by the *announced payload's* own roster.

    The trust anchor of last resort for PCR-07-003.  At first replica seeding
    the case is not in the local store yet, so there is no local roster to read
    — and ADR-0088 removed the ``Service``-hosting scan that used to stand in
    for one, because hosting location is not evidence of authority
    (ARCH-24-004).  What remains is the announced case's own participant list,
    which carries the CASE_MANAGER inline from the moment a replica is seeded
    (CP-09-004).

    **This is a weak check, deliberately kept rather than dropped.** The roster
    is supplied by the sender, so a wholly fabricated case naming the sender as
    its own CASE_MANAGER still passes; nothing available at first contact can
    refute it. What it does catch is the realistic case the local check used to
    catch — an actor replaying or forwarding a *legitimate* case whose roster
    names somebody else as the authority. Callers MUST prefer the local roster
    when the case is already seeded, since that one is locally derived and this
    one is not.

    Bare ID strings in the roster are skipped, not dereferenced: Vultron cannot
    resolve a URI in another actor's message (see ``notes/stub-objects.md``), and
    fetching one on the sender's say-so would hand it the choice of what we read.
    In practice the ``Announce`` projection built by
    ``TriggerActivityAdapter.announce_vulnerability_case`` carries the roster as
    bare IDs (``read_case`` does not expand ``case_participants``), so on that
    path this function answers ``None`` and the first-contact decision rests on
    the ``ReportCaseLink`` anchor alone.  CP-09-004 mandates inline participants
    for ``Create(VulnerabilityCase)``, not for this projection; #3274 tracks the
    residual gap.

    The **first** CASE_MANAGER named by the roster is decisive, even when it
    carries no ``attributed_to``.  Skipping past it to a later self-declared
    participant would let a sender bury the real authority behind an
    unresolvable entry and be believed about the next one.
    """
    participants = getattr(case_obj, "case_participants", None) or []
    for participant in participants:
        if isinstance(participant, str):
            continue
        roles = getattr(participant, "case_roles", None) or []
        if has_case_manager_role(list(roles)):
            return _as_id(getattr(participant, "attributed_to", None))
    return None


class _AuthorityVerdict(NamedTuple):
    """Who this receiver expects to hear from about a case, and on what basis."""

    #: The actor this receiver expects, or ``None`` when it has no opinion.
    expected: str | None
    #: True when this receiver holds a locally-derived replica of the case.
    seeded: bool
    #: True when *expected* came from a locally recorded ``ReportCaseLink``
    #: rather than from the case's participant roster.  Only affects wording.
    from_link: bool = False

    def admits(self, sender_id: str | None) -> bool:
        """Whether *sender_id* may seed or update the case."""
        if self.seeded:
            # Fail closed: no expectation means no attribution, and an update we
            # cannot attribute must not be applied.
            return self.expected == sender_id
        # First seeding is permissive when nothing local or announced answers,
        # because accepting is the point.
        return self.expected is None or self.expected == sender_id

    @property
    def basis(self) -> str:
        """Plain-language name for where :attr:`expected` came from.

        Distinguishes the link anchor from the roster because the two can
        disagree — after a CASE_MANAGER handoff (CP-08-003) a stale bootstrap
        link still names the *old* authority, and reporting that as "the
        resolved CASE_MANAGER" sends a reader looking in the wrong place.
        """
        if self.from_link:
            return "bootstrap-recorded authority"
        return "resolved CASE_MANAGER" if self.seeded else "expected authority"


def _authority_verdict(
    dl: CasePersistence, case_id: str, case_obj: Any
) -> _AuthorityVerdict:
    """Resolve who may seed or update *case_id* (PCR-07-003, PCR-03-001).

    Whose account of "the authority" is trusted turns on whether this receiver
    has a replica of its own, and the two accounts must not be mixed — the
    sender supplies the announced roster, so letting it speak about a case we
    already hold would let an imposter name itself the authority and overwrite
    the stored record (``SeedAnnouncedCaseNode`` *saves* on the existing-case
    path).

    The branch is on **holding a locally-derived roster**
    (:func:`~vultron.core.participants.authority.has_local_participant_roster`),
    not on the case row being present and not on whether a lookup happened to
    answer.  All three readings are wrong in a different direction:

    - *Whether a lookup answered* is what reopens the overwrite.  A real replica
      can resolve ``None`` — its roster may name no CASE_MANAGER, or that
      participant may carry no ``attributed_to`` — and treating that as "no
      local opinion" lets the announced roster decide (#3273 AC-4).
    - *Whether the case row is present* fails the other way.  The FastAPI
      ingress adapter pre-stores an inbound activity's nested objects before
      dispatch, so on the HTTP path the row is always present — it is this very
      announce, echoed back.  Reading it as local evidence made the legitimate
      CASE_MANAGER's *first* announce fail closed against itself, which is the
      bootstrap window CM-02-012 exists to rule out.
    - *Holding a resolvable roster* is the signal that means what the guard
      needs: this receiver has an opinion it derived itself.

    For a case we do not hold, the locally recorded anchor comes first: a
    completed ``ReportCaseLink`` carries the address this receiver itself
    reached the authority at during bootstrap (CBT-01-006), which the sender
    cannot forge. Only with no local record at all does the announced roster get
    a say — see :func:`_announced_case_manager_id` for what that can and cannot
    catch.
    """
    local_case = dl.read_case(case_id)
    if local_case is not None and has_local_participant_roster(local_case, dl):
        # Pass the case we already read rather than resolving from the id again.
        link_anchor = _established_link_actor_id(dl, case_id)
        if link_anchor is not None:
            return _AuthorityVerdict(link_anchor, True, from_link=True)
        return _AuthorityVerdict(resolve_case_manager_id(local_case, dl), True)

    expected = _find_case_actor_id(dl, case_id) or _announced_case_manager_id(
        case_obj
    )
    return _AuthorityVerdict(expected, False)


def _link_report_case_links(dl: CasePersistence, case) -> None:
    """Attach any matching ``ReportCaseLink`` records to the announced case."""
    for report_ref in case.vulnerability_reports:
        report_id = _as_id(report_ref)
        if report_id is None:
            continue

        link = dl.read(VultronReportCaseLink.build_id(report_id))
        if not isinstance(link, VultronReportCaseLink):
            continue
        if link.case_id == case.id_:
            continue

        dl.save(link.model_copy(update={"case_id": case.id_}))
        logger.info(
            "AnnounceVulnerabilityCase: linked report '%s' to case '%s'",
            report_id,
            case.id_,
        )


class AnnounceVulnerabilityCaseReceivedUseCase:
    """Seed the local DataLayer with a full VulnerabilityCase from the case owner.

    Per MV-10-003, the invitee creates the case if it does not already exist.
    Per MV-10-004, if the case already exists locally, the announcement is
    accepted without overwriting the existing record (idempotent).
    """

    def __init__(
        self,
        dl: CasePersistence,
        request: AnnounceVulnerabilityCaseReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        gap_buffer: LedgerGapBuffer | None = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._sync_port = sync_port
        self._gap_buffer = gap_buffer

    def execute(self) -> None:
        request = self._request
        activity = request.activity
        if activity is None:
            logger.warning(
                "AnnounceVulnerabilityCase: no activity on event '%s' — skipping",
                request.activity_id,
            )
            return

        # The case object is the object_ field of the announce activity.
        case_obj = getattr(activity, "object_", None)
        if case_obj is None:
            logger.warning(
                "AnnounceVulnerabilityCase: no case object in activity '%s'"
                " — skipping",
                request.activity_id,
            )
            return

        if getattr(case_obj, "type_", None) != "VulnerabilityCase":
            logger.warning(
                "AnnounceVulnerabilityCase: object in activity '%s' is not a"
                " VulnerabilityCase (%s) — skipping",
                request.activity_id,
                type(case_obj).__name__,
            )
            return

        case_id = _as_id(case_obj)
        if case_id is None:
            logger.warning(
                "AnnounceVulnerabilityCase: case object has no id in"
                " activity '%s' — skipping",
                request.activity_id,
            )
            return

        verdict = _authority_verdict(self._dl, case_id, case_obj)
        if not verdict.admits(request.actor_id):
            # See the note in `vultron/core/behaviors/store_scope.py`: an actor id
            # is a public delivery address, and CodeQL reads it as a secret only
            # because `VultronReportCaseLink.trusted_case_actor_id` is one of the
            # fields `_find_case_actor_id` can reach it from.
            logger.warning(
                "AnnounceVulnerabilityCase: actor '%s' is not the %s ('%s') for"
                " case '%s' — rejected (CBT-05-004, PCR-03-001, PCR-07-003)",
                request.actor_id,
                verdict.basis,
                verdict.expected,  # codeql[py/clear-text-logging-sensitive-data]
                case_id,
            )
            return

        tree = create_announce_vulnerability_case_received_tree(
            case_id=case_id,
            case_obj=case_obj,
            request=request,
        )
        bridge = BTBridge(datalayer=self._dl)
        result = bridge.execute_with_setup(
            tree=tree,
            # The *receiving* actor, not the sender (BT-17-005): an
            # inbound activity is applied to the receiver's own replica,
            # so the tree must execute in the receiver's store.
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        if result.status != Status.SUCCESS:
            logger.warning(
                "AnnounceVulnerabilityCaseReceivedBT did not succeed"
                " for case '%s': %s",
                case_id,
                BTBridge.get_failure_reason(tree),
            )
            return

        # The case (and therefore its deterministic per-case genesis hash) is
        # now seeded locally.  Any Announce(CaseLedgerEntry) that arrived during
        # the pre-genesis window was parked in the actor-local gap buffer rather
        # than dropped (SYNC-15-004, #2186); drain it now so the ledger converges
        # without waiting on the reject → replay round-trip (SYNC-15-005, #2180).
        gap_buffer = self._gap_buffer
        if gap_buffer is None and request.receiving_actor_id:
            gap_buffer = get_ledger_gap_buffer(request.receiving_actor_id)
        if gap_buffer is not None and gap_buffer.depth(case_id) > 0:
            drain_gap_buffer(
                cast(CaseOutboxPersistence, self._dl),
                case_id,
                resolve_receiving_actor_id(
                    self._dl, request.receiving_actor_id
                ),
                gap_buffer,
                self._sync_port,
            )

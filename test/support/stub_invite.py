"""Store a stub Invite the way the CASE_MANAGER's own store holds one (CM-11-006).

The inert invitee record is born from the stub Invite that names it: its status
id and every time on it derive from that Invite's id and ``published``.  A test
that runs the CASE_MANAGER's birth node on its own therefore records the Invite
first, as the emit node does in the real tree.
"""

from datetime import UTC, datetime

from vultron.core.ports.case_persistence import CasePersistence
from vultron.wire.as2.factories import rm_invite_to_case_activity

#: The time every helper-built stub Invite claims, whole seconds (ADR-0103).
STUB_PUBLISHED = datetime(2026, 10, 9, 12, 0, 0, tzinfo=UTC)


def store_stub_invite(
    dl: CasePersistence,
    *,
    case_id: str,
    issuer_id: str,
    invitee_id: str,
    roles: list[str] | None = None,
    invite_id: str | None = None,
    published: datetime = STUB_PUBLISHED,
) -> str:
    """Save a stub Invite from *issuer_id* to *invitee_id*; return its id."""
    invite = rm_invite_to_case_activity(
        invitee_id,
        case_id,
        roles=roles or ["vendor"],
        actor=issuer_id,
        to=[invitee_id],
        id_=invite_id or f"{case_id}/invitations/stub-{invitee_id[-6:]}",
        published=published,
    )
    dl.save(invite)
    return invite.id_

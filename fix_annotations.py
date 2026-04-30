"""Fix remaining Activity class name references in type annotations."""

import re

# All Activity class names to replace in type annotations
ACTIVITY_CLASSES = [
    "RmCreateReportActivity",
    "RmSubmitReportActivity",
    "RmReadReportActivity",
    "RmValidateReportActivity",
    "RmInvalidateReportActivity",
    "RmCloseReportActivity",
    "AddReportToCaseActivity",
    "AddStatusToCaseActivity",
    "CreateCaseActivity",
    "CreateCaseStatusActivity",
    "AddNoteToCaseActivity",
    "UpdateCaseActivity",
    "RmEngageCaseActivity",
    "RmDeferCaseActivity",
    "RmCloseCaseActivity",
    "OfferCaseOwnershipTransferActivity",
    "AcceptCaseOwnershipTransferActivity",
    "RejectCaseOwnershipTransferActivity",
    "RmInviteToCaseActivity",
    "RmAcceptInviteToCaseActivity",
    "RmRejectInviteToCaseActivity",
    "AnnounceVulnerabilityCaseActivity",
    "EmProposeEmbargoActivity",
    "EmAcceptEmbargoActivity",
    "EmRejectEmbargoActivity",
    "ChoosePreferredEmbargoActivity",
    "ActivateEmbargoActivity",
    "AddEmbargoToCaseActivity",
    "AnnounceEmbargoActivity",
    "RemoveEmbargoFromCaseActivity",
    "CreateParticipantActivity",
    "CreateStatusForParticipantActivity",
    "AddStatusToParticipantActivity",
    "AddParticipantToCaseActivity",
    "RemoveParticipantFromCaseActivity",
    "RecommendActorActivity",
    "AcceptActorRecommendationActivity",
    "RejectActorRecommendationActivity",
    "AnnounceLogEntryActivity",
    "RejectLogEntryActivity",
]

VULTRON_ACTIVITY_IMPORT = (
    "from vultron.core.models.vultron_types import VultronActivity\n"
)
VULTRON_ACTIVITY_MODULE = "vultron.core.models.vultron_types"


def find_last_import_end(content):
    """Find char position after last import statement."""
    last_import_end = 0
    pos = 0
    n = len(content)
    while pos < n:
        rest = content[pos:]
        if rest.startswith("from ") or rest.startswith("import "):
            eol = content.find("\n", pos)
            if eol == -1:
                eol = n
            line = content[pos:eol]
            if "(" in line and ")" not in line:
                paren_close = content.find(")", eol)
                if paren_close == -1:
                    paren_close = n
                next_nl = content.find("\n", paren_close)
                if next_nl == -1:
                    next_nl = n
                last_import_end = next_nl + 1
                pos = next_nl + 1
            else:
                last_import_end = eol + 1
                pos = eol + 1
        else:
            eol = content.find("\n", pos)
            if eol == -1:
                break
            pos = eol + 1
    return last_import_end


def fix_file(filepath):
    with open(filepath) as f:
        content = f.read()

    original = content

    # Fix return type annotations: -> XxxActivity: -> VultronActivity:
    for cls in ACTIVITY_CLASSES:
        # Match in return type annotations: ") -> XxxActivity:" or ") -> XxxActivity\n"
        # and in generic type params: "Tuple[..., XxxActivity]"
        content = re.sub(
            r"\b" + re.escape(cls) + r"\b", "VultronActivity", content
        )

    # Fix ChoosePreferredEmbargoActivity constructor call without object_=
    # This was left untransformed; manually replace it
    content = content.replace(
        "ChoosePreferredEmbargoActivity(", "choose_preferred_embargo_activity("
    )

    # Add VultronActivity import if it's used but not imported
    if "VultronActivity" in content:
        if (
            VULTRON_ACTIVITY_MODULE not in content
            and "import VultronActivity" not in content
        ):
            ins_pos = find_last_import_end(content)
            content = (
                content[:ins_pos] + VULTRON_ACTIVITY_IMPORT + content[ins_pos:]
            )

    # Add choose_preferred_embargo_activity to factory imports if needed but missing
    if "choose_preferred_embargo_activity(" in content:
        if (
            "choose_preferred_embargo_activity"
            not in content.split("from vultron.wire.as2.factories import")[0]
            + "x"
        ):
            # Check if it's in the factory import block
            fac_import_match = re.search(
                r"(from vultron\.wire\.as2\.factories import \()([^)]+)(\))",
                content,
                re.DOTALL,
            )
            if (
                fac_import_match
                and "choose_preferred_embargo_activity"
                not in fac_import_match.group(2)
            ):
                # Add to the import block
                existing_imports = fac_import_match.group(2)
                # Find where to insert (alphabetically)
                new_entry = "    choose_preferred_embargo_activity,\n"
                # Find insertion point within the import block
                lines = existing_imports.split("\n")
                inserted = False
                for i, line in enumerate(lines):
                    stripped = line.strip().rstrip(",")
                    if (
                        stripped
                        and stripped > "choose_preferred_embargo_activity"
                    ):
                        lines.insert(i, new_entry.rstrip("\n"))
                        inserted = True
                        break
                if not inserted:
                    # Append before closing paren
                    lines.append(new_entry.rstrip("\n"))
                new_imports = "\n".join(lines)
                content = (
                    content[: fac_import_match.start(2)]
                    + new_imports
                    + content[fac_import_match.end(2) :]
                )

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Fixed: {filepath}")
    else:
        print(f"No changes: {filepath}")


import sys

files = sys.argv[1:]
for f in files:
    try:
        fix_file(f)
    except Exception as e:
        import traceback

        print(f"ERROR {f}: {e}")
        traceback.print_exc()

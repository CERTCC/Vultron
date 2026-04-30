"""
Transform Activity class constructor calls to factory function calls.
"""

import re
import sys

# Map class name -> factory function name
CLASS_TO_FACTORY = {
    "RmCreateReportActivity": "rm_create_report_activity",
    "RmSubmitReportActivity": "rm_submit_report_activity",
    "RmReadReportActivity": "rm_read_report_activity",
    "RmValidateReportActivity": "rm_validate_report_activity",
    "RmInvalidateReportActivity": "rm_invalidate_report_activity",
    "RmCloseReportActivity": "rm_close_report_activity",
    "AddReportToCaseActivity": "add_report_to_case_activity",
    "AddStatusToCaseActivity": "add_status_to_case_activity",
    "CreateCaseActivity": "create_case_activity",
    "CreateCaseStatusActivity": "create_case_status_activity",
    "AddNoteToCaseActivity": "add_note_to_case_activity",
    "UpdateCaseActivity": "update_case_activity",
    "RmEngageCaseActivity": "rm_engage_case_activity",
    "RmDeferCaseActivity": "rm_defer_case_activity",
    "RmCloseCaseActivity": "rm_close_case_activity",
    "OfferCaseOwnershipTransferActivity": "offer_case_ownership_transfer_activity",
    "AcceptCaseOwnershipTransferActivity": "accept_case_ownership_transfer_activity",
    "RejectCaseOwnershipTransferActivity": "reject_case_ownership_transfer_activity",
    "RmInviteToCaseActivity": "rm_invite_to_case_activity",
    "RmAcceptInviteToCaseActivity": "rm_accept_invite_to_case_activity",
    "RmRejectInviteToCaseActivity": "rm_reject_invite_to_case_activity",
    "AnnounceVulnerabilityCaseActivity": "announce_vulnerability_case_activity",
    "EmProposeEmbargoActivity": "em_propose_embargo_activity",
    "EmAcceptEmbargoActivity": "em_accept_embargo_activity",
    "EmRejectEmbargoActivity": "em_reject_embargo_activity",
    "ChoosePreferredEmbargoActivity": "choose_preferred_embargo_activity",
    "ActivateEmbargoActivity": "activate_embargo_activity",
    "AddEmbargoToCaseActivity": "add_embargo_to_case_activity",
    "AnnounceEmbargoActivity": "announce_embargo_activity",
    "RemoveEmbargoFromCaseActivity": "remove_embargo_from_case_activity",
    "CreateParticipantActivity": "create_participant_activity",
    "CreateStatusForParticipantActivity": "create_status_for_participant_activity",
    "AddStatusToParticipantActivity": "add_status_to_participant_activity",
    "AddParticipantToCaseActivity": "add_participant_to_case_activity",
    "RemoveParticipantFromCaseActivity": "remove_participant_from_case_activity",
    "RecommendActorActivity": "recommend_actor_activity",
    "AcceptActorRecommendationActivity": "accept_actor_recommendation_activity",
    "RejectActorRecommendationActivity": "reject_actor_recommendation_activity",
    "AnnounceLogEntryActivity": "announce_log_entry_activity",
    "RejectLogEntryActivity": "reject_log_entry_activity",
}

# Activities where to=[x] -> to=x (single item)
SINGLE_TO = {"rm_submit_report_activity"}


def find_matching_paren(text, start):
    """Find the index of the matching closing paren starting from position `start` (which is '(')."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def find_next_comma_or_end(text, start):
    """Find the next comma at depth 0, or the end of text."""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            return i
        i += 1
    return len(text)


def convert_to_single(args_str):
    """Convert to=[x] -> to=x in args string (only for single-item lists)."""
    pattern = re.compile(r"\bto\s*=\s*\[([^\[\]]*?)\]")

    def replace_to(m):
        inner = m.group(1).strip()
        if "," not in inner:
            return f"to={inner}"
        return m.group(0)

    return pattern.sub(replace_to, args_str)


def transform_args(args_str, factory_name):
    """
    Transform the arguments string from XxxActivity format to factory format.
    - Remove 'object_=' keyword, making the value the first positional arg
    - For rm_submit_report_activity: convert to=[x] to to=x
    """
    obj_pattern = re.compile(r"\bobject_\s*=\s*")
    m = obj_pattern.search(args_str)
    if not m:
        return args_str

    val_start = m.end()
    val_end = find_next_comma_or_end(args_str, val_start)
    object_value = args_str[val_start:val_end].strip().rstrip(",").strip()

    before_obj = args_str[: m.start()]
    after_obj = args_str[val_end:]
    after_obj = after_obj.lstrip(",")

    remaining_args = before_obj + after_obj

    if factory_name in SINGLE_TO:
        remaining_args = convert_to_single(remaining_args)

    remaining_args = remaining_args.strip().strip(",").strip()

    if remaining_args:
        new_args = object_value + ",\n" + remaining_args
    else:
        new_args = object_value

    return new_args


def transform_call(text, class_name, factory_name):
    """Find and transform all constructor calls of class_name in text."""
    result = text
    pattern = re.compile(r"\b" + re.escape(class_name) + r"\s*\(")
    offset = 0
    while True:
        m = pattern.search(result, offset)
        if not m:
            break
        open_paren_pos = m.end() - 1
        close_paren_pos = find_matching_paren(result, open_paren_pos)
        if close_paren_pos == -1:
            offset = m.end()
            continue

        args_str = result[open_paren_pos + 1 : close_paren_pos]

        if "object_=" in args_str:
            new_args_str = transform_args(args_str, factory_name)
        else:
            offset = m.end()
            continue

        new_call = factory_name + "(" + new_args_str + ")"
        result = result[: m.start()] + new_call + result[close_paren_pos + 1 :]
        offset = m.start() + len(new_call)

    return result


def collect_factories_used(text):
    """Find which factory functions are actually used in the transformed text."""
    used = set()
    for factory in CLASS_TO_FACTORY.values():
        if re.search(r"\b" + re.escape(factory) + r"\s*\(", text):
            used.add(factory)
    return used


def find_last_import_end_char(content):
    """
    Find the character position (end) of the last import statement.
    Handles multiline imports (from x import (...)).
    Returns the index just after the last '\n' of the last import statement.
    """
    # We'll scan character by character to properly track multiline imports
    last_import_end = 0
    pos = 0
    n = len(content)

    while pos < n:
        # Skip to start of line (we're at a line start already in this loop)
        line_start = pos

        # Check if this line starts an import
        # Look for 'from ' or 'import ' at the start of the line
        rest = content[pos:]

        if rest.startswith("from ") or rest.startswith("import "):
            # Find the end of this import statement
            # Check for multiline (with backslash or open paren)
            # Find end of line
            eol = content.find("\n", pos)
            if eol == -1:
                eol = n
            line = content[pos:eol]

            if "(" in line and ")" not in line:
                # Multi-line import with parentheses
                # Find the closing )
                paren_close = content.find(")", eol)
                if paren_close == -1:
                    paren_close = n
                # Find the newline after )
                next_nl = content.find("\n", paren_close)
                if next_nl == -1:
                    next_nl = n
                last_import_end = next_nl + 1
                pos = next_nl + 1
            elif line.endswith("\\"):
                # Backslash continuation - find the last non-backslash line
                cur = eol + 1
                while cur < n:
                    next_eol = content.find("\n", cur)
                    if next_eol == -1:
                        next_eol = n
                    cur_line = content[cur:next_eol]
                    if not cur_line.endswith("\\"):
                        last_import_end = next_eol + 1
                        pos = next_eol + 1
                        break
                    cur = next_eol + 1
                else:
                    last_import_end = n
                    pos = n
            else:
                last_import_end = eol + 1
                pos = eol + 1
        else:
            # Skip to next line
            eol = content.find("\n", pos)
            if eol == -1:
                break
            pos = eol + 1

    return last_import_end


def transform_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    original = content

    # Step 1: Apply constructor call transformations
    for class_name, factory_name in CLASS_TO_FACTORY.items():
        if class_name in content:
            content = transform_call(content, class_name, factory_name)

    # Step 2: Collect which factories are now used
    used_factories = collect_factories_used(content)

    # Step 3: Remove old imports from vultron.wire.as2.vocab.activities.*
    # Handle multi-line imports
    import_pattern_multi = re.compile(
        r"^from vultron\.wire\.as2\.vocab\.activities\.[^\s]+ import \(\n(?:[^)]*\n)*\)\n",
        re.MULTILINE,
    )
    content = import_pattern_multi.sub("", content)

    # Handle single-line imports
    single_import_pattern = re.compile(
        r"^from vultron\.wire\.as2\.vocab\.activities\.[^\s]+ import [^\n]+\n",
        re.MULTILINE,
    )
    content = single_import_pattern.sub("", content)

    # Step 4: Add factory imports if needed
    if used_factories:
        sorted_factories = sorted(used_factories)
        factory_import = (
            "from vultron.wire.as2.factories import (\n"
            + "".join(f"    {f},\n" for f in sorted_factories)
            + ")\n"
        )
        # Find insertion point: after the last import block
        ins_pos = find_last_import_end_char(content)
        content = content[:ins_pos] + factory_import + content[ins_pos:]

    # Step 5: Handle model_validate calls
    for class_name in CLASS_TO_FACTORY:
        mv_pattern = class_name + ".model_validate("
        if mv_pattern in content:
            content = content.replace(
                mv_pattern, "VultronActivity.model_validate("
            )

    # Step 6: Add VultronActivity import if needed
    if (
        "VultronActivity.model_validate(" in content
        and "VultronActivity" not in content.split("model_validate")[0][-200:]
    ):
        if "from vultron.core.models.vultron_types import" not in content:
            ins_pos = find_last_import_end_char(content)
            content = (
                content[:ins_pos]
                + "from vultron.core.models.vultron_types import VultronActivity\n"
                + content[ins_pos:]
            )

    # Step 7: Handle type annotations still using old class names
    # e.g., "-> RmSubmitReportActivity:" in function signatures
    # These need the class to be imported - but we removed those imports.
    # Per instructions, we should leave type hints for model_validate as VultronActivity
    # For other type annotations, they'll need to be updated too.
    # Let's check what remains and handle them.

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Transformed: {filepath}")
    else:
        print(f"No changes: {filepath}")


if __name__ == "__main__":
    files = sys.argv[1:]
    for filepath in files:
        try:
            transform_file(filepath)
        except Exception as e:
            print(f"ERROR processing {filepath}: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()

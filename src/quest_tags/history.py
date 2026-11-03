"""The record of which outcome each quest tag is at in one playthrough: conversations/<world_id>/tag_outcomes.json

The record never stores text, only the outcome number and when Mantella first saw each outcome true.
See docs/quest_tags_1_user_edits.md, Part 1.
"""
import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from src import utils

FILE_NAME = "tag_outcomes.json"

# Only one writer at a time: NPC Initiative and NPC Event checks run at the same time as conversations
_write_lock = threading.Lock()


@dataclass(frozen=True)
class OutcomeChange:
    tag: str
    old: int | None  # None: the tag wasn't in the record yet
    new: int


def record_path(conversation_folder_path: str, world_id: str) -> str:
    return os.path.join(conversation_folder_path, world_id, FILE_NAME)


def load(path: str) -> dict[str, dict] | None:
    """The tags in the record, or None when this playthrough has no record yet"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            tags: dict[str, dict] = json.load(f).get("tags", {})
        # Records written before tag names were read with straight apostrophes may hold `risaad’s_caravan`
        return {utils.normalize_apostrophes(tag): entry for tag, entry in tags.items()}
    except Exception as e:
        logging.warning(f"Quest tags: could not read {path}, treating it as missing. Error: {e}")
        return None


def save(path: str, tags: dict[str, dict]):
    write_json(path, {"tags": tags})


def write_json(path: str, data: dict):
    """Write a new file first, then swap it in, so a crash never leaves a half-written file"""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    handle, temp_path = tempfile.mkstemp(dir=folder, prefix=os.path.basename(path), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        _replace(temp_path, path)
    except Exception:
        os.remove(temp_path)
        raise


def _replace(source: str, target: str, attempts: int = 5):
    """os.replace, retried briefly: Windows refuses it while another reader (an NPC being loaded, a virus scanner) has the target open"""
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.05)


def apply_outcomes(tags: dict[str, dict] | None, outcomes: dict[str, int | None], now: int) -> tuple[dict[str, dict], list[OutcomeChange]]:
    """Apply one set of answers to the record (Part 1, "Updating the record").

    Args:
        tags: the record's tags, or None for the first check in this playthrough
        outcomes: each tag's outcome from the game's answers; None when unknown
        now: the current Unix time
    Returns:
        The updated tags, and the tags whose outcome changed
    """
    updated = {tag: {"current": entry["current"], "seen": dict(entry["seen"])} for tag, entry in (tags or {}).items()}
    changes: list[OutcomeChange] = []
    for tag, new in outcomes.items():
        if new is None:
            continue
        entry = updated.get(tag)
        if entry is None:
            # The first check, or a tag added by a later CSV update: already true before tracking started
            updated[tag] = {"current": new, "seen": {str(new): 0} if new else {}}
            changes.append(OutcomeChange(tag, None, new))
            continue
        old = entry["current"]
        if new == old:
            continue
        seen: dict[str, int] = entry["seen"]
        if new > old:
            seen[str(new)] = now
        else:
            # Usually an older save: forget everything above the new outcome
            for slot in [s for s in seen if int(s) > new]:
                del seen[slot]
            if new:
                seen.setdefault(str(new), now)
        entry["current"] = new
        changes.append(OutcomeChange(tag, old, new))
    return updated, changes


def update(path: str, outcomes: dict[str, int | None], now: int) -> tuple[dict[str, dict], list[OutcomeChange], bool]:
    """Load, apply and save under one lock. Returns the tags, the changes, and whether this was the first check"""
    with _write_lock:
        tags = load(path)
        is_first_check = tags is None
        if is_first_check and all(outcome is None for outcome in outcomes.values()):
            return {}, [], False  # No usable answers yet: nothing is written until there are
        updated, changes = apply_outcomes(tags, outcomes, now)
        if changes or is_first_check:
            save(path, updated)
        return updated, changes, is_first_check


def current_outcomes(tags: dict[str, dict] | None) -> dict[str, tuple[int, int]]:
    """Tag -> (outcome, time first seen) for every tag that is at an outcome other than 0"""
    result: dict[str, tuple[int, int]] = {}
    for tag, entry in (tags or {}).items():
        current = entry.get("current", 0)
        if current:
            result[tag] = (current, int(entry.get("seen", {}).get(str(current), 0)))
    return result

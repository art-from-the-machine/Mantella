"""File handling for the Tag Editor tab, kept apart from the UI so it can be tested on its own.

See docs/tag_editor.md, "Where your changes are saved". In short:
- only personal files are ever written; base and mod files are never touched
- only the cells that changed are written, into the personal file that already has the tag, or else `tag_editor.csv`
- a file is read fresh just before it's written, and copied to `<name>.csv.bak` first
"""
import os
import re
import shutil
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd

import src.utils as utils
from src.bio_template_manager import LAYER_PERSONAL, OUTCOME_SLOTS, TAG_COLUMNS, _split_static_and_dynamic, effective_tags, file_encoding, split_tags

TAG_EDITOR_FILE = "tag_editor.csv"
BACKUP_SUFFIX = ".bak"

# Seconds are shown so an event nobody touched keeps its exact timestamp when the tag is saved again
EVENT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_EVENT_DATE_INPUT_FORMATS = (EVENT_DATE_FORMAT, "%Y-%m-%d %H:%M", "%Y-%m-%d")
_MIN_TIMESTAMP_DIGITS = 9

# (layer, file, value), as BioTemplateManager.sources keeps them
Source = Tuple[str, str, str]


def personal_folder(save_folder: str, game_folder: str = "Skyrim") -> str:
    """The personal bio templates folder, the same one BioTemplateManager loads last"""
    return os.path.join(save_folder, "data", game_folder, "bio_templates")


# --- Description and dynamic events ---

def split_description(description: str) -> Tuple[str, List[Tuple[int, str]]]:
    """The ordinary text (goes into the bio) and the dynamic events (go into the memory timeline)"""
    return _split_static_and_dynamic(description or "")


def clean_event_text(text: str) -> str:
    """An event has to be one line, so line breaks become spaces"""
    return re.sub(r"\s*[\r\n]+\s*", " ", str(text or "")).strip()


def join_description(text: str, events: List[Tuple[int, str]]) -> str:
    """Put the ordinary text and the events back into one description: the text, then one `- <ts>: <text>` line per event, oldest first"""
    lines: List[str] = []
    text = (text or "").strip()
    if text:
        lines.append(text)
    for timestamp, event_text in sorted(events, key=lambda event: event[0]):
        event_text = clean_event_text(event_text)
        if event_text:
            lines.append(f"- {int(timestamp)}: {event_text}")
    return "\n".join(lines)


def format_event_date(timestamp: int) -> str:
    """Unix seconds as a date in local time. A timestamp Windows can't show as a date (e.g. before 1970) stays a number"""
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime(EVENT_DATE_FORMAT)
    except (OSError, OverflowError, ValueError):
        return str(int(timestamp))


def parse_event_date(text: str) -> int:
    """A date in local time as Unix seconds, or a plain number of seconds. Raises ValueError with a readable message.

    A plain number is only taken as seconds with 9 or more digits (from 1973 on), so a year like `2026`
    or `20261106` isn't silently read as a moment in 1970.
    """
    value = str(text or "").strip()
    if value.isascii() and value.isdigit() and len(value) >= _MIN_TIMESTAMP_DIGITS:
        return int(value)
    for date_format in _EVENT_DATE_INPUT_FORMATS:
        try:
            parsed = datetime.strptime(value, date_format)
        except ValueError:
            continue
        try:
            return int(parsed.timestamp())
        except (OSError, OverflowError, ValueError):
            raise ValueError(f"'{value}' can't be used as a date. Use a date from 1970 on")
    raise ValueError(f"'{value}' isn't a date. Write it like 2026-11-06 14:30")


def parse_timestamp(text: str) -> int:
    """The Timestamp box or column: a whole number of seconds since 1970, exactly as saved in the file"""
    value = str(text or "").strip()
    if value.isascii() and value.isdigit():
        return int(value)
    raise ValueError(f"'{value}' isn't a timestamp. Write a whole number of seconds, like 1762435800")


def _date_matches(date: str, timestamp: int) -> bool:
    """Whether a date text shows this timestamp. The exact text is checked first: in the hour repeated when clocks
    go back, reading the shown date back gives a different moment"""
    if date == format_event_date(timestamp):
        return True
    try:
        return parse_event_date(date) == timestamp
    except ValueError:
        return False


def event_timestamp(date: str, timestamp: str) -> int:
    """The timestamp to save for one event row of [date, timestamp, text]. The Timestamp is saved as it is, so an
    event nobody touched keeps its exact moment. The date is only read when the Timestamp is empty.
    Raises ValueError when neither can be read, or when they show different moments"""
    date, timestamp = (date or "").strip(), (timestamp or "").strip()
    if not timestamp:
        if not date:
            raise ValueError("an event needs a date or a timestamp")
        return parse_event_date(date)
    seconds = parse_timestamp(timestamp)
    if date and not _date_matches(date, seconds):
        raise ValueError(f"the date {date} and the timestamp {timestamp} are different moments. Change only one of them")
    return seconds


def sync_event_rows(rows: List[List[str]], shown: List[List[str]]) -> Tuple[List[List[str]], str]:
    """After an edit in the events table, fill in the other half of each changed row: a changed date gives the
    timestamp, a changed timestamp gives the date. Rows are [date, timestamp, text]; `shown` is the table as it
    was last shown. Returns the rows and a message for the first one that can't be read ("" when all can).

    The table can be re-sorted on screen, so which cell was changed is found from the shown rows: a row whose
    timestamp was shown before had its date changed, and a row whose date was shown before had its timestamp changed.
    """
    synced: List[List[str]] = []
    problem = ""
    shown_dates = {row[0] for row in shown}
    shown_timestamps = {row[1] for row in shown}
    for index, row in enumerate(rows):
        date, timestamp, text = (list(row) + ["", "", ""])[:3]
        date, timestamp = date.strip(), timestamp.strip()
        try:
            if timestamp and (not date or not _date_matches(date, parse_timestamp(timestamp))):
                date_changed = bool(date) and timestamp in shown_timestamps
                timestamp_changed = not date or date in shown_dates
                if date_changed and timestamp_changed:
                    # Both were shown before (e.g. two events swapped values): the row's own place decides
                    same_place = shown[index] if index < len(shown) else ["", ""]
                    date_changed = same_place[1] == timestamp
                if date_changed:
                    timestamp = str(parse_event_date(date))
                elif not timestamp_changed:
                    raise ValueError(f"the date {date} and the timestamp {timestamp} are different moments. Change only one of them")
                date = format_event_date(int(timestamp))
            elif date and not timestamp:
                timestamp = str(parse_event_date(date))
                date = format_event_date(int(timestamp))
        except ValueError as e:
            problem = problem or str(e)
        synced.append([date, timestamp, text])
    return synced, problem


# --- Where values come from ---

def current_source(sources: Dict[str, Dict[str, List[Source]]], tag: str, column: str) -> Source | None:
    """The (layer, file, value) that wins for a cell, or None when no file fills it in"""
    entries = sources.get(tag, {}).get(column, [])
    return entries[-1] if entries else None


def source_underneath(sources: Dict[str, Dict[str, List[Source]]], tag: str, column: str) -> Source | None:
    """What a cell falls back to if your personal files stop filling it in: the last base or mod value"""
    for entry in reversed(sources.get(tag, {}).get(column, [])):
        if entry[0] != LAYER_PERSONAL:
            return entry
    return None


def personal_files(files_with_tag: Dict[str, List[Tuple[str, str]]], tag: str) -> List[str]:
    """Your personal files that have a row for the tag, in load order"""
    return [path for layer, path in files_with_tag.get(tag, []) if layer == LAYER_PERSONAL]


def has_base_or_mod_rows(files_with_tag: Dict[str, List[Tuple[str, str]]], tag: str) -> bool:
    return any(layer != LAYER_PERSONAL for layer, _ in files_with_tag.get(tag, []))


def personal_files_with_value(sources: Dict[str, Dict[str, List[Source]]], tag: str, column: str) -> List[str]:
    """Your personal files that fill in this cell. Clearing a field has to empty it in all of them"""
    files: List[str] = []
    for layer, path, _ in sources.get(tag, {}).get(column, []):
        if layer == LAYER_PERSONAL and path not in files:
            files.append(path)
    return files


def choose_target_file(files_with_tag: Dict[str, List[Tuple[str, str]]], tag: str, folder: str) -> str:
    """Where a change goes: the personal file that already has the tag (the last one read, which wins), or else `tag_editor.csv`"""
    existing = personal_files(files_with_tag, tag)
    return existing[-1] if existing else os.path.join(folder, TAG_EDITOR_FILE)


def changed_cells(before: Dict[str, str], after: Dict[str, str]) -> Dict[str, str]:
    """Only the cells that are different. Spaces at the ends don't count as a change"""
    return {
        column: (value or "").strip()
        for column, value in after.items()
        if (value or "").strip() != (before.get(column) or "").strip()
    }


# --- Search ---

SEARCH_SNIPPET_CONTEXT = 40


def _snippet(text: str, start: int, length: int) -> str:
    """The match with some text around it, on one line"""
    begin = max(0, start - SEARCH_SNIPPET_CONTEXT)
    end = min(len(text), start + length + SEARCH_SNIPPET_CONTEXT)
    snippet = " ".join(text[begin:end].split())
    return ("…" if begin > 0 else "") + snippet + ("…" if end < len(text) else "")


def search_tags(sources: Dict[str, Dict[str, List[Source]]], files_with_tag: Dict[str, List[Tuple[str, str]]], query: str) -> List[Dict[str, str]]:
    """Every place the query appears in the tags' current values, ignoring upper and lower case.

    Searches tag names, tag text, dynamic events, outcome texts, conditions, notes and source. Values that a later
    layer overrides aren't searched: only what the game uses. Each result has `tag`, `where` (the CSV column
    the match is in, as written in the files), `snippet`, `layer` and `file` (the file the matching value comes from).
    """
    needle = (query or "").strip().lower()
    if not needle:
        return []
    results: List[Dict[str, str]] = []

    def add(tag: str, where: str, text: str, source: Source | Tuple[str, str] | None):
        position = text.lower().find(needle)
        if position < 0:
            return
        layer, path = (source[0], source[1]) if source else ("", "")
        results.append({"tag": tag, "where": where, "snippet": _snippet(text, position, len(needle)), "layer": layer, "file": path})

    for tag in sorted(files_with_tag, key=str.lower):
        files = files_with_tag[tag]
        add(tag, "tag", tag, files[-1] if files else None)
        description = current_source(sources, tag, "description")
        if description:
            # Text and each dynamic event are searched apart, so a match's snippet doesn't run from one into the next
            text, events = split_description(description[2])
            add(tag, "description", text, description)
            for _, event in sorted(events):
                add(tag, "description", event, description)
        for column in [f"{prefix}_{slot}" for slot in range(1, OUTCOME_SLOTS + 1) for prefix in ("potential_paste", "code")] + ["notes", "source"]:
            source = current_source(sources, tag, column)
            if source:
                add(tag, column, source[2], source)
    return results


# --- Reading and writing ---

def _read_csv(path: str) -> Tuple[pd.DataFrame, str]:
    """Every cell as the text it is in the file (`1` stays `1`, `NA` stays `NA`), and the file's encoding.

    Uses the same encoding rule as the tag loader, so the text the tab shows is the text it writes back.
    """
    encoding = file_encoding(path)
    if os.path.getsize(path) == 0:
        return pd.DataFrame(columns=["tag", "description"]), encoding
    df = pd.read_csv(path, dtype=str, keep_default_na=False, engine="python", encoding=encoding)
    return df, encoding


def _write_csv(df: pd.DataFrame, path: str, encoding: str):
    """Write with the file's own encoding. Plain ASCII, or an encoding that can't hold the new text, becomes UTF-8"""
    # Columns without a header (e.g. from trailing commas) are read as "Unnamed: N"; keep them without a header
    headers = ["" if str(column).startswith("Unnamed: ") else column for column in df.columns]
    text = df.to_csv(index=False, header=headers)
    if not encoding or encoding.lower() == "ascii":
        encoding = "utf-8"
    try:
        data = text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        data = text.encode("utf-8")
    # Write a temporary file next to it, then swap it in: if writing fails halfway (disk full, Mantella closed),
    # the tag file is never left empty or cut off
    temporary = path + ".tmp"
    try:
        with open(temporary, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def backup(path: str):
    """Keep the file as it was just before this change, as `<name>.csv.bak`. Mantella only loads `.csv` files, so it's never read as tags"""
    if os.path.exists(path):
        shutil.copy2(path, path + BACKUP_SUFFIX)


def _rows_for_tag(df: pd.DataFrame, tag: str) -> List[int]:
    if "tag" not in df.columns:
        return []
    return [index for index, value in df["tag"].items() if utils.normalize_apostrophes(str(value).strip()) == tag]


def _ordered_columns(original: List[str], present: List[str]) -> List[str]:
    """The file's columns with the tag columns in their usual order (tag, description, potential_paste_1, code_1, ...
    announce, outcome_mode, notes, source), so a column added later lands in its place instead of at the end.

    Any other column stays right after the tag column it followed in the file (or at the start if it came first).
    """
    known = ["tag", *TAG_COLUMNS]
    leading: List[str] = []
    following: Dict[str, List[str]] = {}
    previous = None
    for column in original:
        if column in known:
            previous = column
        elif previous is None:
            leading.append(column)
        else:
            following.setdefault(previous, []).append(column)
    ordered = list(leading)
    for column in known:
        if column in present:
            ordered += [column, *following.get(column, [])]
    # Anything not placed above (a column added that isn't a tag column) goes at the end, as before
    return ordered + [column for column in present if column not in ordered]


def write_cells(path: str, tag: str, cells: Dict[str, str]):
    """Write these cells of the tag's row, keeping everything else in the file as it is.

    The row is the last one with this tag in the file (the one that wins), or a new row at the end.
    An emptied cell is emptied on every row with the tag: Mantella reads every row, so a value left
    on an earlier row would come back.
    A new file gets the `tag` and `description` columns Mantella needs to read it. The tag columns are kept in
    their usual order (see `_ordered_columns`), which also tidies a file whose columns were added out of order.
    """
    if os.path.exists(path):
        backup(path)
        df, encoding = _read_csv(path)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df, encoding = pd.DataFrame(columns=["tag", "description"]), "utf-8"

    original_columns = list(df.columns)
    for column in ["tag", "description", *cells]:
        if column not in df.columns:
            df[column] = ""
    df = df[_ordered_columns(original_columns, list(df.columns))]

    rows = _rows_for_tag(df, tag)
    if rows:
        index = rows[-1]
    else:
        new_row = {column: "" for column in df.columns}
        new_row["tag"] = tag
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        index = df.index[-1]

    for column, value in cells.items():
        for row in (rows or [index]) if value == "" else [index]:
            df.at[row, column] = value
    _write_csv(df, path, encoding)


def remove_tag_rows(paths: List[str], tag: str) -> List[str]:
    """Remove every row with this tag from these files. Returns the files that changed"""
    changed: List[str] = []
    for path in dict.fromkeys(paths):
        if not os.path.exists(path):
            continue
        df, encoding = _read_csv(path)
        rows = _rows_for_tag(df, tag)
        if not rows:
            continue
        backup(path)
        _write_csv(df.drop(index=rows), path, encoding)
        changed.append(path)
    return changed


# --- NPCs with a tag ---

def npcs_by_tag(character_df: pd.DataFrame | None) -> Dict[str, List[str]]:
    """Tag -> every NPC with it, as "Name (base_id)". Uses each NPC's tags at runtime (`tags_overwrite` if set, else `tags`)"""
    result: Dict[str, List[str]] = {}
    if character_df is None or character_df.empty:
        return result
    columns = character_df.columns
    for _, row in character_df.iterrows():
        tags = effective_tags(row["tags"] if "tags" in columns else "", row["tags_overwrite"] if "tags_overwrite" in columns else "")
        if not tags:
            continue
        name = str(row["name"] if "name" in columns else "").strip()
        base_id = str(row["base_id"] if "base_id" in columns else "").strip()
        label = f"{name} ({base_id})" if base_id and base_id.lower() != "nan" else name
        for tag in split_tags(tags):
            npcs = result.setdefault(tag, [])
            if label not in npcs:
                npcs.append(label)
    for npcs in result.values():
        npcs.sort(key=str.lower)
    return result

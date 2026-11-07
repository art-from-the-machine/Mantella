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
from src.bio_template_manager import LAYER_PERSONAL, _split_static_and_dynamic, effective_tags, split_tags

TAG_EDITOR_FILE = "tag_editor.csv"
BACKUP_SUFFIX = ".bak"

# Seconds are shown so an event nobody touched keeps its exact timestamp when the tag is saved again
EVENT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_EVENT_DATE_INPUT_FORMATS = (EVENT_DATE_FORMAT, "%Y-%m-%d %H:%M", "%Y-%m-%d")

# (layer, file, value), as BioTemplateManager.sources keeps them
Source = Tuple[str, str, str]


def personal_folder(save_folder: str, game_folder: str = "Skyrim") -> str:
    """The personal bio templates folder, the same one BioTemplateManager loads last"""
    return os.path.join(save_folder, "data", game_folder, "bio_templates")


# --- Description and dated events ---

def split_description(description: str) -> Tuple[str, List[Tuple[int, str]]]:
    """The ordinary text (goes into the bio) and the dated events (go into the memory timeline)"""
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
    """A date in local time as Unix seconds, or a plain number of seconds. Raises ValueError with a readable message"""
    value = str(text or "").strip()
    if value.isdigit():
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


# --- Reading and writing ---

def _file_encoding(path: str) -> str:
    """A file that is valid UTF-8 is read as UTF-8. Encoding guesses can mistake short UTF-8 files for another
    encoding, and writing back after such a guess would garble their accented text for good"""
    with open(path, "rb") as file:
        data = file.read()
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return utils.get_file_encoding(path) or "utf-8"


def _read_csv(path: str) -> Tuple[pd.DataFrame, str]:
    """Every cell as the text it is in the file (`1` stays `1`, `NA` stays `NA`), and the file's encoding"""
    encoding = _file_encoding(path)
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
    with open(path, "wb") as file:
        file.write(data)


def backup(path: str):
    """Keep the file as it was just before this change, as `<name>.csv.bak`. Mantella only loads `.csv` files, so it's never read as tags"""
    if os.path.exists(path):
        shutil.copy2(path, path + BACKUP_SUFFIX)


def _rows_for_tag(df: pd.DataFrame, tag: str) -> List[int]:
    if "tag" not in df.columns:
        return []
    return [index for index, value in df["tag"].items() if utils.normalize_apostrophes(str(value).strip()) == tag]


def write_cells(path: str, tag: str, cells: Dict[str, str]):
    """Write these cells of the tag's row, keeping everything else in the file as it is.

    The row is the last one with this tag in the file (the one that wins), or a new row at the end.
    An emptied cell is emptied on every row with the tag: Mantella reads every row, so a value left
    on an earlier row would come back.
    A new file gets the `tag` and `description` columns Mantella needs to read it.
    """
    if os.path.exists(path):
        backup(path)
        df, encoding = _read_csv(path)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df, encoding = pd.DataFrame(columns=["tag", "description"]), "utf-8"

    for column in ["tag", "description", *cells]:
        if column not in df.columns:
            df[column] = ""

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

"""The Tag Editor tab: read, change and add tags without opening CSV files.

See docs/tag_editor.md. File handling lives in tag_editor_files.py; this module is the UI and applying changes to the running game.
"""
import functools
import logging
import os
import time
from typing import Any, Dict, List, Tuple

import gradio as gr
import pandas as pd

import src.utils as utils
from src.bio_template_manager import (LAYER_BASE, LAYER_MOD, LAYER_PERSONAL, OUTCOME_MODE_DEFAULT, OUTCOME_MODES, OUTCOME_SLOTS,
                                      TAG_COLUMNS, BioTemplateManager)
from src.config.config_loader import ConfigLoader
from src.config.definitions.game_definitions import GameEnum
from src.quest_tags import history as quest_tag_history
from src.quest_tags.conditions import CheckList
from src.ui import tag_editor_files as files

LAYER_NAMES = {LAYER_BASE: "Base", LAYER_MOD: "Mod", LAYER_PERSONAL: "Personal"}
EVENT_HEADERS = ["Date", "Timestamp", "Event"]
OUTCOME_COLUMNS = [column for slot in range(1, OUTCOME_SLOTS + 1) for column in (f"potential_paste_{slot}", f"code_{slot}")]
NPC_LIST_NEEDS_GAME = "Shown once Mantella has connected to the game."
SEARCH_HEADERS = ["Tag", "Column", "Text", "From"]
SEARCH_RESULT_LIMIT = 200
# What the form compares against when no tag is open: typing into the empty form counts as unsaved changes too
BLANK_SNAPSHOT = {"tag": "", "text": "", "events": [], "announce": True, "mode": OUTCOME_MODE_DEFAULT,
                  "cells": {column: "" for column in TAG_COLUMNS}}
# The `outcome_mode` column as a list to pick from: (what the tab shows, what the file holds)
OUTCOME_MODE_CHOICES = [
    ("Follow the Auto Quest Tag Outcomes setting", OUTCOME_MODE_DEFAULT),
    ("Static: in the NPC's bio, right before the tag text", "static"),
    ("Dynamic: a dated memory, brought up as news once", "dynamic"),
    ("Off: this tag's outcomes aren't checked, only the tag text is used", "off"),
]


def _column_name(column: str) -> str:
    """A column as the tab calls it"""
    if column == "description":
        return "tag text and events"
    # Outcome fields are labelled with their column names, so messages use them too
    return column


def _outcome_mode(value: Any) -> str:
    """An `outcome_mode` cell, or the list's value, as one of the list's choices. Empty or unknown follows the setting, as at runtime"""
    mode = str(value or "").strip().lower()
    return mode if mode in OUTCOME_MODES else OUTCOME_MODE_DEFAULT


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _timestamp_text(value: Any) -> str:
    """A Timestamp cell as text. The table can hand a number back, e.g. 1762435800.0"""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _cell_text(value).strip()


def _all_event_rows(table: Any) -> List[List[str]]:
    """The events table as [date, timestamp, text] rows, including rows whose text was cleared"""
    if isinstance(table, pd.DataFrame):
        raw_rows = table.values.tolist()
    elif isinstance(table, dict):
        raw_rows = table.get("data") or []
    else:
        raw_rows = table or []
    rows: List[List[str]] = []
    for row in raw_rows:
        cells = list(row) + ["", "", ""]
        rows.append([_cell_text(cells[0]).strip(), _timestamp_text(cells[1]), files.clean_event_text(_cell_text(cells[2]))])
    return rows


def _event_rows(table: Any) -> List[List[str]]:
    """The events as [date, timestamp, text] rows. Rows without text are dropped: clearing the text deletes the event"""
    return [row for row in _all_event_rows(table) if row[2]]


def _event_row(timestamp: int, text: str) -> List[str]:
    return [files.format_event_date(timestamp), str(int(timestamp)), text]


def _sentence(problem: Any) -> str:
    """A problem message as a sentence: capital first letter, full stop at the end"""
    text = str(problem).strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else text + "."


def _events_table_value(rows: List[List[str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=EVENT_HEADERS)


def build_tag_editor_page(config: ConfigLoader):
    if config.game.base_game == GameEnum.FALLOUT4:
        gr.Markdown("Tags exist only for Skyrim, so the Tag Editor only works when the game is set to Skyrim.")
        return

    templates_folder = os.path.join(utils.resolve_path(), "data", "Skyrim", "bio_templates")
    # The tab's own view of the tag files. The running game has its own, which Save brings up to date
    state: Dict[str, Any] = {"manager": None, "npcs": None}

    # The files are read again whenever a tag is picked and before anything is written (about 0.1 s for ~1,000 tags),
    # so CSVs edited by hand while Mantella runs are never acted on from an old copy
    def load_manager() -> BioTemplateManager:
        state["manager"] = BioTemplateManager(templates_folder, config, "Skyrim")
        state["npcs"] = None
        return state["manager"]

    def manager() -> BioTemplateManager:
        return state["manager"] or load_manager()

    def all_tags() -> List[str]:
        return sorted(manager().files_with_tag.keys(), key=str.lower)

    def game_manager():
        from src.ui import settings_ui_constructor as sui
        return getattr(sui, "_game_manager_ref", None)

    def npcs_by_tag() -> Dict[str, List[str]] | None:
        """None when the game hasn't connected yet: only the game has the merged character table"""
        if state["npcs"] is None:
            gm = game_manager()
            game = getattr(gm, "game", None) if gm else None
            if game is None:
                return None
            state["npcs"] = files.npcs_by_tag(game.character_df)
        return state["npcs"]

    def folders_list() -> str:
        """The three folders tags are read from, as the "From" names call them, so the names point somewhere real"""
        mod_folder = os.path.join(config.mod_path_base, "SKSE", "Plugins", "MantellaSoftware", "data", "Skyrim", "bio_templates")
        folders = [
            ("Base", "the tags that come with Mantella", templates_folder),
            ("Mod", "tags from Skyrim mods you've installed", mod_folder),
            ("Personal", "your own tags and changes", files.personal_folder(config.save_folder)),
        ]
        lines = []
        for number, (name, what, folder) in enumerate(folders, start=1):
            missing = "" if os.path.isdir(folder) else " (folder not found)"
            lines.append(f"{number}. **{name}**, {what}: `{os.path.normpath(folder)}`{missing}")
        return "\n".join(lines)

    def tag_reading_note() -> str:
        if getattr(config, "enable_character_tag_reading", True):
            return ""
        return "**Enable Character Tag Reading is off** (LLM settings), so saved tags won't be used until it's turned back on."

    # --- Showing a tag ---

    def source_label(tag: str, column: str) -> str:
        current = files.current_source(manager().sources, tag, column)
        if current is None:
            return ""
        layer, path, _ = current
        label = f"From: {LAYER_NAMES.get(layer, layer)}, `{os.path.basename(path)}`"
        if layer == LAYER_PERSONAL:
            underneath = files.source_underneath(manager().sources, tag, column)
            if underneath:
                label += f". Clearing it brings back the {LAYER_NAMES.get(underneath[0], underneath[0])} value"
        return label

    def unreadable_reasons(tag: str, codes: Dict[int, str]) -> Dict[int, str]:
        codes = {slot: code for slot, code in codes.items() if code.strip()}
        if not codes:
            return {}
        return {outcome.slot: outcome.reason for outcome in CheckList({tag: codes}).unreadable}

    def in_several_files(tag: str) -> bool:
        """Only then does each field say where it comes from: otherwise the line under the tag name already does"""
        return len({path for _, path in manager().files_with_tag.get(tag, [])}) > 1

    def where_line(tag: str) -> str:
        """Which files the tag is in, with full paths and the folder names from the intro, and where a save goes"""
        files_with_tag = manager().files_with_tag
        target = f"`{os.path.normpath(files.choose_target_file(files_with_tag, tag, files.personal_folder(config.save_folder)))}`"

        def described(layer: str, path: str) -> str:
            name = LAYER_NAMES.get(layer, layer)
            what = "where your changes are saved" if layer == LAYER_PERSONAL else "never changed"
            return f"`{os.path.normpath(path)}` ({name} folder, {what})"

        rows = list(dict.fromkeys(files_with_tag.get(tag, [])))
        if len(rows) == 1:
            line = f"**File:** {described(*rows[0])}"
        else:
            line = "**Files** (a value in a later file wins):\n" + "\n".join(f"- {described(layer, path)}" for layer, path in rows)
        if not files.personal_files(files_with_tag, tag):
            line += f"\n\n**Your changes will be saved to:** {target} (Personal folder)"
        return line

    def remove_action(tag: str) -> str | None:
        """What the remove button does for this tag: "delete" (only in your files), "back" (you changed a base or mod tag), or nothing"""
        files_with_tag = manager().files_with_tag
        if not files.personal_files(files_with_tag, tag):
            return None
        return "back" if files.has_base_or_mod_rows(files_with_tag, tag) else "delete"

    def original_name(tag: str) -> str:
        """"mod version", "base version", or "original": what Reset brings a tag back to"""
        layers = [layer for layer, _ in manager().files_with_tag.get(tag, []) if layer != LAYER_PERSONAL]
        return f"{LAYER_NAMES.get(layers[-1], 'original').lower()} version" if layers else "original"

    def back_label(tag: str) -> str:
        return f"Reset to {original_name(tag)}"

    def remove_note_text(tag: str, action: str | None) -> str:
        """What the remove button will do, shown under it before it's clicked"""
        if action == "delete":
            return ("Deletes the whole tag: its row in the personal file is removed. "
                    "NPCs who were given this tag get nothing from it anymore. Asks to confirm first.")
        if action == "back":
            return f"Drops your changes, so every field goes back to the {original_name(tag)}. Asks to confirm first."
        return ""

    def npc_lines(tag: str) -> Tuple[str, str]:
        """The label and the content of the NPC list"""
        npcs = npcs_by_tag()
        if npcs is None:
            return "NPCs with this tag", NPC_LIST_NEEDS_GAME
        with_tag = npcs.get(tag, [])
        if not with_tag:
            return "Used by no NPC yet", "Give it to NPCs in the Bio Editor."
        return f"Used by {len(with_tag)} NPC{'s' if len(with_tag) != 1 else ''}", ", ".join(with_tag)

    def outcome_label(tag: str, slot: int, code: str) -> str:
        parts = []
        if in_several_files(tag):
            text_source = source_label(tag, f"potential_paste_{slot}")
            code_source = source_label(tag, f"code_{slot}")
            if text_source:
                parts.append(f"potential_paste_{slot} {text_source[0].lower()}{text_source[1:]}")
            if code_source:
                parts.append(f"code_{slot} {code_source[0].lower()}{code_source[1:]}")
        reason = unreadable_reasons(tag, {slot: code}).get(slot)
        if reason:
            parts.append(f"**code_{slot} can't be read: {reason}**")
        return " · ".join(parts)

    def render(tag: str | None, message: str = "", fold: bool = True) -> Dict[Any, Any]:
        """Every component showing this tag, as loaded from the files. No tag empties the form, ready for a new tag"""
        tags = all_tags()
        if not tag:
            values = {column: "" for column in TAG_COLUMNS}
        else:
            values = {column: (files.current_source(manager().sources, tag, column) or ("", "", ""))[2] for column in TAG_COLUMNS}
        text, events = files.split_description(values["description"])
        event_rows = [_event_row(ts, files.clean_event_text(event)) for ts, event in sorted(events)]
        announce = values["announce"].strip().lower() != "no"
        mode = _outcome_mode(values["outcome_mode"])
        # A value typed by hand that isn't one of the choices, e.g. `dynamc`: shown under the list, and replaced by the next Save
        unknown_mode = values["outcome_mode"].strip() if values["outcome_mode"].strip().lower() not in (*OUTCOME_MODES, OUTCOME_MODE_DEFAULT) else ""
        snapshot = {"tag": tag or "", "text": text, "events": event_rows, "announce": announce, "mode": mode,
                    "unknown_mode": unknown_mode, "cells": values}

        update: Dict[Any, Any] = {
            tag_dropdown: gr.update(choices=tags, value=tag or None),
            snapshot_state: snapshot,
            text_box: text,
            **events_updates(event_rows),
            announce_box: announce,
            mode_box: mode,
            notes_box: values["notes"],
            source_box: values["source"],
            new_event_text: "",
            new_event_date: "",
            new_event_timestamp: "",
            confirm_remove_btn: gr.update(visible=False),
            new_tag_message: "",
            picker_message: "",
            tag_note: tag_reading_note(),
            message_line: message,
        }
        for column, box in zip(OUTCOME_COLUMNS, outcome_boxes):
            update[box] = values[column]
        # Folded each time a tag opens, even when they have something in them. Not when the same tag is shown again
        # (Save, Reload files, Discard, Reset): folding what you had open then made the page jump while it redrew
        if fold:
            update[outcomes_section] = gr.update(open=False)
            update[notes_section] = gr.update(open=False)

        has_conditions = bool(tag) and any(values[f"code_{slot}"] for slot in range(1, OUTCOME_SLOTS + 1))
        update[quest_warning] = gr.update(
            visible=has_conditions,
            value="This tag has quest outcomes. NPCs get the tag text **and** the text of the outcome that's true now. "
                  "To use only the tag text, set **Where this tag's quest outcome goes** to **Off**, under Quest outcomes.",
        )
        if tag:
            several = in_several_files(tag)
            # Opened from Global search while Choose or create a tag is folded: unfold it, or nothing seems to happen
            update[choose_section] = gr.update(open=True)
            update[header] = gr.update(value=where_line(tag), visible=True)
            update[text_source] = source_label(tag, "description") if several else ""
            update[announce_source] = source_label(tag, "announce") if several else ""
            update[mode_source] = source_label(tag, "outcome_mode") if several else ""
            if unknown_mode:
                update[mode_source] = (f"**The file says `{unknown_mode}`, which isn't static, dynamic, off or default, so this tag "
                                       f"follows the setting.** Pick what you want and click **Save** to replace it. {update[mode_source]}").strip()
            update[notes_source] = source_label(tag, "notes") if several else ""
            update[source_from] = source_label(tag, "source") if several else ""
            for slot, label in enumerate(outcome_labels, start=1):
                update[label] = outcome_label(tag, slot, values[f"code_{slot}"])
            npc_label, npc_text = npc_lines(tag)
            update[npc_section] = gr.update(label=npc_label, visible=True, **({"open": False} if fold else {}))
            update[npc_list] = npc_text
            action = remove_action(tag)
            update[remove_btn] = gr.update(visible=action is not None, value="Delete tag" if action == "delete" else back_label(tag))
            update[remove_note] = remove_note_text(tag, action)
        else:
            for component in [text_source, announce_source, mode_source, notes_source, source_from, npc_list, remove_note, *outcome_labels]:
                update[component] = ""
            update[header] = gr.update(value="", visible=False)
            update[npc_section] = gr.update(visible=False)
            update[remove_btn] = gr.update(visible=False)
        return update

    def events_updates(rows: List[List[str]]) -> Dict[Any, Any]:
        """The table only shows when there are events: an empty one looks broken"""
        return {
            # row_count is the number of rows the table shows and sends back: "fixed" hides the New row button, but
            # left at 1 it cut the table to its first event, so Add event seemed to do nothing and Save dropped the rest
            events_table: gr.update(value=_events_table_value(rows), visible=bool(rows), row_count=(max(len(rows), 1), "fixed")),
            events_shown: rows,
            selected_event: None,
            remove_event_btn: remove_button(None),
            remove_event_row: gr.update(visible=bool(rows)),
            no_events: gr.update(visible=not rows),
        }

    # --- What's on screen vs what was loaded ---

    def form_values(field_values: Tuple[Any, ...]) -> Dict[str, Any]:
        text, table, *rest = field_values
        outcome_values = rest[:len(OUTCOME_COLUMNS)]
        announce, mode, notes, source = rest[len(OUTCOME_COLUMNS):]
        values = {
            "text": (text or "").strip(),
            "events": _event_rows(table),
            "announce": bool(announce),
            "mode": _outcome_mode(mode),
            "notes": (notes or "").strip(),
            "source": (source or "").strip(),
        }
        for column, value in zip(OUTCOME_COLUMNS, outcome_values):
            values[column] = (value or "").strip()
        return values

    def has_unsaved_changes(snapshot: Dict[str, Any], field_values: Tuple[Any, ...]) -> bool:
        if not snapshot or not snapshot.get("tag"):
            snapshot = BLANK_SNAPSHOT
        current = form_values(field_values)
        cells = snapshot["cells"]
        if current["text"] != snapshot["text"].strip() or current["events"] != snapshot["events"]:
            return True
        if current["announce"] != snapshot["announce"] or current["notes"] != cells["notes"].strip():
            return True
        if current["source"] != cells.get("source", "").strip():
            return True
        if current["mode"] != snapshot.get("mode", OUTCOME_MODE_DEFAULT):
            return True
        return any(current[column] != cells[column].strip() for column in OUTCOME_COLUMNS)

    def unsaved_message(snapshot: Dict[str, Any]) -> Dict[Any, Any]:
        """Shown right under the tag list, where you just tried to switch, not under the Save button at the end of the form"""
        tag = (snapshot or {}).get("tag")
        if not tag:
            return {
                tag_dropdown: gr.update(value=None),
                picker_message: "The fields have text that isn't saved anywhere yet. Give it a name and click **Create** to keep "
                              "it as a new tag, or click **Discard changes**, then pick the tag again.",
            }
        return {
            tag_dropdown: gr.update(value=tag),
            picker_message: f"You have unsaved changes to `{tag}`. Save them, or click **Discard changes**, then pick the tag again.",
        }

    # --- Applying a change to the running game ---

    def apply_to_game(tag: str) -> List[str]:
        """Re-read the tag files in the running game, and rebuild NPCs in a running conversation. Returns lines for the message"""
        gm = game_manager()
        game = getattr(gm, "game", None) if gm else None
        if game is None:
            return ["Mantella hasn't connected to the game yet. It uses the new version when it does."]
        lines: List[str] = []
        try:
            old_version, new_version = game.reload_bio_templates()
            talk = gm.active_conversation
            if talk:
                world_id = talk.context.world_id
                tag_outcomes = quest_tag_history.current_outcomes(quest_tag_history.load(
                    quest_tag_history.record_path(game.conversation_folder_path, world_id)))
                refreshed = game.refresh_characters_with_tag(talk.context.npcs_in_conversation.get_all_characters(), tag, tag_outcomes)
                if refreshed:
                    lines.append(f"{', '.join(refreshed)}, in the current conversation, use the new version from their next reply.")
                if old_version != new_version:
                    lines.append("**A conversation is running, so quest progress won't be checked until the next conversation starts.**")
                    logging.info("Tag Editor: the quest checks changed during a conversation. The game gets the new list at the next conversation start; until then its answers are ignored.")
            elif old_version != new_version:
                lines.append("Changed conditions reach the game when the next conversation starts.")
        except Exception as e:
            logging.warning(f"Tag Editor: saved, but could not apply the change to the running game: {e}")
            lines.append(f"Saved, but it couldn't be applied to the running game ({e}). Use **Other → Reload Character Data**.")
        return lines

    # --- Handlers ---

    def on_pick(tag: str, snapshot: Dict[str, Any], *field_values):
        if snapshot and tag == snapshot.get("tag"):
            # Already open: keep the form, edits included. Gradio 4 reads an empty dict as one output value and fails,
            # so return a real update. Unfolding Choose or create a tag shows the tag when it came from a Global search click
            return {choose_section: gr.update(open=True)}
        if has_unsaved_changes(snapshot, field_values):
            return unsaved_message(snapshot)
        load_manager()
        return render(tag)

    def read_events(event_rows: List[List[str]], opened_rows: List[List[str]]) -> Tuple[List[Tuple[int, str]], str]:
        """The events as (timestamp, text) for the file, or a problem. Save and Create can be clicked before the table has
        filled in the other half of an edited date or timestamp (the edit and the click arrive together), so that's
        filled in here, judged against the events as they were shown when the tag opened"""
        rows, _ = files.sync_event_rows(event_rows, opened_rows)
        events = []
        for date, timestamp, text in rows:
            try:
                events.append((files.event_timestamp(date, timestamp), text))
            except ValueError as e:
                return [], _sentence(f"The event \"{text}\" can't be read: {e}")
        return events, ""

    def on_create(name: str, snapshot: Dict[str, Any], *field_values):
        """A new tag from what the fields show now: an empty form filled in, or a copy of the open tag with any edits.
        It's written to the personal folder straight away and opens in the form. The tag that was open isn't changed.
        Everything about it is said under the name box, where Create was clicked"""
        tag = utils.normalize_apostrophes((name or "").strip())
        if not tag:
            return {new_tag_message: "Type a name for the new tag first."}
        if "," in tag:
            return {new_tag_message: "A tag name can't contain commas: an NPC's tags are written as a comma-separated list."}
        m = load_manager()
        if tag in m.files_with_tag:
            return {new_tag_message: f"`{tag}` already exists. Pick it from the list to change it."}
        current = form_values(field_values)
        events, problem = read_events(current["events"], (snapshot or {}).get("events") or [])
        if problem:
            return {new_tag_message: f"Not created. {problem}"}
        cells = {column: current[column] for column in OUTCOME_COLUMNS if current[column]}
        description = files.join_description(current["text"], events)
        if description:
            cells["description"] = description
        if current["notes"]:
            cells["notes"] = current["notes"]
        if current["source"]:
            cells["source"] = current["source"]
        if not current["announce"]:
            cells["announce"] = "no"
        if current["mode"] != OUTCOME_MODE_DEFAULT:
            cells["outcome_mode"] = current["mode"]
        target = files.choose_target_file(m.files_with_tag, tag, files.personal_folder(config.save_folder))
        created_file = not os.path.exists(target)
        try:
            files.write_cells(target, tag, cells)
        except Exception as e:
            logging.warning(f"Tag Editor: could not create {tag}: {e}")
            return {new_tag_message: f"Couldn't create `{tag}`: {e}"}

        lines = [f"Created `{tag}` in `{os.path.basename(target)}`.{'' if created_file else backup_note([target])} "
                 "Give it to NPCs in the Bio Editor."]
        old_tag = (snapshot or {}).get("tag")
        if old_tag and has_unsaved_changes(snapshot, field_values):
            lines.append(f"`{old_tag}` wasn't changed: your edits went into the new tag.")
        reasons = unreadable_reasons(tag, {slot: current[f"code_{slot}"] for slot in range(1, OUTCOME_SLOTS + 1)})
        for slot, reason in sorted(reasons.items()):
            lines.append(f"code_{slot} can't be read: {reason}. It's saved, but that outcome won't happen automatically until it's fixed.")
        lines += apply_to_game(tag)
        load_manager()
        update = render(tag)
        update[new_tag_name] = ""
        update[new_tag_message] = "\n\n".join(lines)
        return update

    def on_add_event(table, text: str, date: str, timestamp: str):
        event_text = files.clean_event_text(text)
        if not event_text:
            return {message_line: "Type what happened first."}
        try:
            # Both boxes empty means the moment Add event is clicked, not when the page or tag was opened
            if (date or "").strip() or (timestamp or "").strip():
                seconds = files.event_timestamp(date, timestamp)
            else:
                seconds = int(time.time())
        except ValueError as e:
            return {message_line: _sentence(e)}
        rows = [row for row in _all_event_rows(table) if row[2]] + [_event_row(seconds, event_text)]
        # Oldest first, as the table is shown when a tag opens. A timestamp that can't be read keeps its place at the end
        rows.sort(key=lambda row: int(row[1]) if row[1].isdigit() else float("inf"))
        return {
            **events_updates(rows),
            new_event_text: "",
            new_event_date: "",
            new_event_timestamp: "",
            message_line: "Event added. Click **Save** to keep it.",
        }

    def on_new_event_date(date: str):
        """Typing a date fills in its timestamp, so both boxes always show the same moment"""
        try:
            return str(files.parse_event_date(date)) if (date or "").strip() else ""
        except ValueError:
            return ""

    def on_new_event_timestamp(timestamp: str):
        """Typing a timestamp fills in its date"""
        try:
            return files.format_event_date(files.parse_timestamp(timestamp)) if (timestamp or "").strip() else ""
        except ValueError:
            return ""

    def on_events_edited(table, shown: List[List[str]]):
        """An edited date gets its timestamp filled in, and an edited timestamp its date"""
        before = _all_event_rows(table)
        rows, problem = files.sync_event_rows(before, shown or [])
        # A row whose text was cleared isn't taken out here: a stale report (below) can look like that, e.g. the empty
        # row Gradio puts in an empty table, and taking it out would drop an event just added. It goes on Save
        # Gradio 4.28's table can report an "edit" right after the page sets it (e.g. when a tag opens), sometimes
        # with the value from before. Answering that with the table again made it report again, forever. So the
        # table (and what was shown) is only sent back when a date or timestamp was actually filled in
        update: Dict[Any, Any] = {message_line: _sentence(problem) if problem else gr.update()}
        if rows != before:
            update[events_table] = gr.update(value=_events_table_value(rows))
            update[events_shown] = rows
        return update

    def remove_button(row: List[str] | None) -> Dict[str, Any]:
        """The Remove event button names the event it will remove, so it's clear which row goes. Off until one is clicked"""
        if not row or not row[2]:
            return gr.update(value="Click an event to remove it", interactive=False)
        text = row[2] if len(row[2]) <= 40 else row[2][:39].rstrip() + "…"
        return gr.update(value=f"Remove \"{text}\" ({row[0]})", interactive=True)

    def clicked_event(table, evt: gr.SelectData) -> List[str] | None:
        """The clicked event, as its [date, timestamp, text] row. The table can be re-sorted on screen, and the click
        then reports the row's place in the sorted table, so the clicked cell's text decides, as in Global search"""
        rows = _all_event_rows(table)
        if isinstance(evt.index, (list, tuple)) and len(evt.index) == 2:
            row, col = evt.index
        else:
            row, col = evt.index, 0
        if not isinstance(row, int) or not isinstance(col, int) or not 0 <= col < len(EVENT_HEADERS):
            return None
        value = _timestamp_text(evt.value) if col == 1 else _cell_text(evt.value).strip()
        if col == 2:
            value = files.clean_event_text(value)
        matching = [r for r in rows if r[col] == value]
        if len(matching) == 1:
            return matching[0]
        if 0 <= row < len(rows) and rows[row][col] == value:
            return rows[row]
        return None

    def on_event_select(table, evt: gr.SelectData):
        row = clicked_event(table, evt)
        return {selected_event: row, remove_event_btn: remove_button(row)}

    def on_remove_event(table, selected: List[str] | None):
        rows = _all_event_rows(table)
        if not selected:
            return {remove_event_btn: remove_button(None), message_line: "Click an event in the table first."}
        if list(selected) not in rows:
            return {selected_event: None, remove_event_btn: remove_button(None),
                    message_line: "That event changed since you clicked it. Click it again to remove it."}
        rows.remove(list(selected))
        return {**events_updates([row for row in rows if row[2]]), message_line: "Event removed. Click **Save** to keep the change."}

    def on_save(snapshot: Dict[str, Any], *field_values):
        tag = (snapshot or {}).get("tag")
        if not tag:
            return {message_line: "No tag is open, so there's nothing to save to. To keep these fields as a new tag, "
                                  "give it a name and click **Create**."}
        current = form_values(field_values)
        events, problem = read_events(current["events"], snapshot.get("events") or [])
        if problem:
            return {message_line: f"Not saved. {problem}"}

        before = snapshot["cells"]
        after: Dict[str, str] = {column: current[column] for column in OUTCOME_COLUMNS}
        after["notes"] = current["notes"]
        after["source"] = current["source"]
        if current["text"] != snapshot["text"].strip() or current["events"] != snapshot["events"]:
            after["description"] = files.join_description(current["text"], events)
        changes = files.changed_cells({column: before.get(column, "") for column in after}, after)
        if current["announce"] != snapshot["announce"]:
            changes["announce"] = "yes" if current["announce"] else "no"
        # Written out even when it's back to following the setting: an empty cell wouldn't undo a base or mod file's choice
        if current["mode"] != snapshot.get("mode", OUTCOME_MODE_DEFAULT) or snapshot.get("unknown_mode"):
            changes["outcome_mode"] = current["mode"]
        if not changes:
            return {message_line: "Nothing to save."}

        m = load_manager()
        # Someone changed these fields in the files since the tag was opened (e.g. by hand): saving would overwrite that
        changed_on_disk = [
            column for column in changes
            if (files.current_source(m.sources, tag, column) or ("", "", ""))[2].strip() != (before.get(column) or "").strip()
        ]
        if changed_on_disk:
            fields = ", ".join(_column_name(column) for column in changed_on_disk)
            return {message_line: f"Not saved: `{tag}` was changed in its files since you opened it ({fields}). "
                                  "Saving now would overwrite that. Copy your edits somewhere if you need them, click "
                                  "**Discard changes** to load the new version, then make your edits again."}
        folder = files.personal_folder(config.save_folder)
        target = files.choose_target_file(m.files_with_tag, tag, folder)
        written: List[str] = []
        new_files: List[str] = []
        notes: List[str] = []
        try:
            # Clearing a field: empty it in every personal file that fills it in. One write per file,
            # so each file's backup is the version from before this save
            cleared_elsewhere: Dict[str, Dict[str, str]] = {}
            for column, value in list(changes.items()):
                if value:
                    continue
                personal_with_value = files.personal_files_with_value(m.sources, tag, column)
                for path in personal_with_value:
                    if path != target:
                        cleared_elsewhere.setdefault(path, {})[column] = ""
                underneath = files.source_underneath(m.sources, tag, column)
                if underneath:
                    layer = LAYER_NAMES.get(underneath[0], underneath[0])
                    if personal_with_value:
                        notes.append(f"Cleared {_column_name(column)}: the {layer} value comes back.")
                    else:
                        notes.append(f"{_column_name(column).capitalize()} comes from a {layer} file and can't be blanked.")
                        del changes[column]
            for path, cells in cleared_elsewhere.items():
                files.write_cells(path, tag, cells)
                written.append(path)
            if changes:
                # A file this save creates has nothing to back up
                created = not os.path.exists(target)
                files.write_cells(target, tag, changes)
                written.append(target)
                if created:
                    new_files.append(target)
        except Exception as e:
            logging.warning(f"Tag Editor: could not save {tag}: {e}")
            return {message_line: f"Couldn't save `{tag}`: {e}"}

        lines = []
        if written:
            names = ", ".join(f"`{os.path.basename(path)}`" for path in dict.fromkeys(written))
            what = ", ".join(_column_name(column) for column in changes)
            lines.append(f"Saved {what} to {names}.{backup_note([path for path in written if path not in new_files])}")
        lines += notes
        reasons = unreadable_reasons(tag, {slot: current[f"code_{slot}"] for slot in range(1, OUTCOME_SLOTS + 1)})
        for slot, reason in sorted(reasons.items()):
            lines.append(f"code_{slot} can't be read: {reason}. It's saved, but that outcome won't happen automatically until it's fixed.")
        if written:
            lines += apply_to_game(tag)
        load_manager()
        return render(tag, message="\n\n".join(lines), fold=False)

    def on_refresh(snapshot: Dict[str, Any], *field_values):
        if has_unsaved_changes(snapshot, field_values):
            return unsaved_message(snapshot)
        load_manager()
        tag = (snapshot or {}).get("tag")
        if tag and tag not in manager().files_with_tag:
            tag = None
        return render(tag, message="Read all tag files again.", fold=False)

    def on_discard(snapshot: Dict[str, Any], *field_values):
        tag = (snapshot or {}).get("tag")
        if not tag:
            if not has_unsaved_changes(snapshot, field_values):
                return {message_line: "Nothing to discard."}
            return render(None, message="Fields emptied.")
        load_manager()
        return render(tag if tag in manager().files_with_tag else None, message="Unsaved changes dropped.", fold=False)

    def backup_note(paths: List[str]) -> str:
        """Each changed file was copied to `<name>.csv.bak` just before the change. Says so, naming the copies"""
        backups = [f"`{os.path.basename(path)}{files.BACKUP_SUFFIX}`" for path in dict.fromkeys(paths)]
        if not backups:
            return ""
        if len(backups) == 1:
            return f" A copy of the file from before this change is kept as {backups[0]}, in the same folder."
        return f" Copies of the files from before this change are kept as {', '.join(backups)}, in the same folder."

    def npc_count_line(tag: str) -> str:
        npcs = npcs_by_tag()
        if npcs is None:
            return ""
        count = len(npcs.get(tag, []))
        if not count:
            return " No NPC has it."
        return f" {count} NPC{'s' if count != 1 else ''} {'have' if count != 1 else 'has'} this tag and will stop getting its text."

    def on_remove(snapshot: Dict[str, Any]):
        """First click of the one remove button: Delete tag for a tag only in your files, Reset for a base or mod tag you changed.
        Says what will change and shows the confirm button. What it offered is kept, so the confirm click can't do the other one"""
        tag = (snapshot or {}).get("tag")
        if not tag:
            return {message_line: "Pick a tag first."}
        load_manager()
        action = remove_action(tag)
        if action is None:
            return {message_line: f"`{tag}` has nothing in your personal files to remove."}
        names = ", ".join(f"`{os.path.basename(path)}`" for path in files.personal_files(manager().files_with_tag, tag))
        if action == "delete":
            confirm, message = "Confirm delete", (f"Delete `{tag}`? This removes its row from {names} in your personal folder.{npc_count_line(tag)} "
                                                  "Click **Confirm delete** to go ahead.")
        else:
            confirm, message = "Confirm reset", (f"Remove your changes to `{tag}`? This removes its row from {names} in your personal folder, "
                                                 "so every field goes back to the base or mod version. Base and mod files aren't touched. "
                                                 "Click **Confirm reset** to go ahead.")
        return {
            snapshot_state: {**snapshot, "remove": action},
            confirm_remove_btn: gr.update(visible=True, value=confirm),
            message_line: message,
        }

    def on_confirm_remove(snapshot: Dict[str, Any]):
        action = (snapshot or {}).get("remove")
        if action == "delete":
            return confirm_delete(snapshot)
        if action == "back":
            return confirm_back(snapshot)
        return {message_line: "Click the remove button first.", confirm_remove_btn: gr.update(visible=False)}

    def confirm_delete(snapshot: Dict[str, Any]):
        tag = (snapshot or {}).get("tag")
        files_with_tag = load_manager().files_with_tag
        if not tag or not files.personal_files(files_with_tag, tag) or files.has_base_or_mod_rows(files_with_tag, tag):
            return {message_line: "Only a tag that exists only in your personal files can be deleted.", confirm_remove_btn: gr.update(visible=False)}
        try:
            changed = files.remove_tag_rows(files.personal_files(files_with_tag, tag), tag)
        except Exception as e:
            logging.warning(f"Tag Editor: could not delete {tag}: {e}")
            return {message_line: f"Couldn't delete `{tag}`: {e}", confirm_remove_btn: gr.update(visible=False)}
        lines = [f"Deleted `{tag}` from {', '.join(f'`{os.path.basename(path)}`' for path in changed)}.{backup_note(changed)}"]
        lines += apply_to_game(tag)
        load_manager()
        return render(None, message="\n\n".join(lines))

    def confirm_back(snapshot: Dict[str, Any]):
        tag = (snapshot or {}).get("tag")
        files_with_tag = load_manager().files_with_tag
        if not tag or not files.personal_files(files_with_tag, tag) or not files.has_base_or_mod_rows(files_with_tag, tag):
            return {message_line: "Reset only works for a tag that's in a base or mod file and that you've changed.", confirm_remove_btn: gr.update(visible=False)}
        try:
            changed = files.remove_tag_rows(files.personal_files(files_with_tag, tag), tag)
        except Exception as e:
            logging.warning(f"Tag Editor: could not undo the changes to {tag}: {e}")
            return {message_line: f"Couldn't undo your changes to `{tag}`: {e}", confirm_remove_btn: gr.update(visible=False)}
        lines = [f"`{tag}` is back to the original. Removed its row from {', '.join(f'`{os.path.basename(path)}`' for path in changed)}.{backup_note(changed)}"]
        lines += apply_to_game(tag)
        load_manager()
        return render(tag, message="\n\n".join(lines), fold=False)

    # --- Search ---

    def on_search(query: str):
        """Find text in every tag's current values, like Ctrl+F across the tag files"""
        if not (query or "").strip():
            return {search_results: pd.DataFrame([], columns=SEARCH_HEADERS), search_result_rows: [], search_summary: ""}
        m = load_manager()
        results = files.search_tags(m.sources, m.files_with_tag, query)
        shown = results[:SEARCH_RESULT_LIMIT]
        rows = [[result["tag"], result["where"], result["snippet"],
                 f"{LAYER_NAMES.get(result['layer'], result['layer'])}, {os.path.basename(result['file'])}" if result["file"] else ""]
                for result in shown]
        tag_count = len({result["tag"] for result in results})
        if not results:
            summary = f"Nothing found for `{query.strip()}`."
        else:
            summary = f"{len(results)} match{'es' if len(results) != 1 else ''} in {tag_count} tag{'s' if tag_count != 1 else ''}."
            if len(results) > len(shown):
                summary += f" Showing the first {len(shown)}; type more to narrow it down."
            summary += " Click a row to open the tag."
        return {search_results: pd.DataFrame(rows, columns=SEARCH_HEADERS), search_result_rows: rows, search_summary: summary}

    def on_result_select(result_rows: List[List[str]], evt: gr.SelectData):
        """The tag of the clicked row. Opening it is the next step, with the usual unsaved-changes check.

        The table can be re-sorted on screen, and the click then reports the row's position in the sorted table,
        not in the results as they were found. So the clicked cell's text decides, and the position is only
        used when it agrees with that text.
        """
        rows = result_rows or []
        if isinstance(evt.index, (list, tuple)) and len(evt.index) == 2:
            row, col = evt.index
        else:
            row, col = evt.index, 0
        value = _cell_text(evt.value)
        if not isinstance(row, int) or not isinstance(col, int) or not 0 <= col < len(SEARCH_HEADERS):
            return None
        if col == 0:
            return value if any(r[0] == value for r in rows) else None
        tags = {r[0] for r in rows if r[col] == value}
        if len(tags) == 1:
            return tags.pop()
        if 0 <= row < len(rows) and rows[row][col] == value:
            return rows[row][0]
        return None

    def on_open_result(tag: str | None, snapshot: Dict[str, Any], *field_values):
        if not tag:
            return {message_line: "Couldn't tell which tag that row is. Click its tag name in the results."}
        return on_pick(tag, snapshot, *field_values)

    # --- Showing that something is happening, and when it's done ---

    def working(text: str):
        """A first step for a button: puts `text` (e.g. "Saving…") in the message line the moment it's clicked. The page
        doesn't grey out while the real work runs (see style.css), so this is what shows it's running"""
        def show(*_):
            return text
        return show

    def finished(handler, line):
        """`handler` with the time it finished at the start of its message in `line`, so saving twice gives two different
        messages and you can tell the second one went through. A result that says nothing there clears the working text"""
        @functools.wraps(handler)
        def run(*args):
            result = handler(*args)
            text = result.get(line)
            if isinstance(text, str) and text:
                result[line] = f"**{time.strftime('%H:%M:%S')}** · {text}"
            elif line not in result:
                result[line] = ""
            return result
        return run

    def opening_text(tag: str | None) -> str:
        return f"Opening `{tag}`…" if tag else ""

    def confirm_text(snapshot: Dict[str, Any]) -> str:
        return "Deleting…" if (snapshot or {}).get("remove") == "delete" else "Resetting…"

    # --- Layout ---

    gr.Markdown(
        "Change what a tag says, add dynamic events, and create new tags. "
        "Changes apply right away, including to NPCs in a running conversation.\n\n"
        f"Tags are read from three folders. If a tag is in more than one, the later folder wins.\n\n{folders_list()}\n\n"
        "Your changes are always saved to the Personal folder. Base and Mod files are never changed."
    )
    tag_note = gr.Markdown(tag_reading_note())

    # Three foldable sections, like the Bio Editor's: choose (and edit) a tag, search, create
    # Choosing a tag, or creating one: one form for both. With no tag open it's empty, ready to fill in for a new tag
    with gr.Accordion(label="Choose or create a tag", open=True) as choose_section:
        # The tag list and the new-tag name box share one row.
        # A new tag is made from whatever the fields below show, so it can also start as a copy of the open tag
        with gr.Row(equal_height=True, elem_classes="tag-editor-picker"):
            tag_dropdown = gr.Dropdown(choices=all_tags(), value=None, label="Tag", show_label=False, container=False,
                                       filterable=True, allow_custom_value=False, scale=4)
            refresh_btn = gr.Button("Reload files", variant="secondary", size="sm", scale=0, min_width=110)
            new_tag_name = gr.Text(label="Name of the new tag", show_label=False, container=False, max_lines=1,
                                   placeholder="Name for a new tag made from the fields below", scale=3)
            create_btn = gr.Button("Create", variant="secondary", size="sm", scale=0, min_width=110)
        picker_message = gr.Markdown(elem_id="tag-editor-picker-message")
        new_tag_message = gr.Markdown(elem_id="tag-editor-new-tag-message")
        with gr.Column():
            # The open tag's NPCs are further down, after Dynamic events; its files are above Save
            text_box = gr.Text(label="Tag text", lines=6)
            text_source = gr.Markdown(elem_classes="tag-editor-source")
            quest_warning = gr.Markdown(visible=False)

            with gr.Accordion(label="Dynamic events", open=True, elem_classes="tag-editor-subsection"):
                no_events = gr.Markdown("This tag has no events yet.")
                events_table = gr.Dataframe(
                    headers=EVENT_HEADERS, datatype=["str", "str", "str"], col_count=(3, "fixed"), row_count=(1, "fixed"),
                    interactive=True, wrap=True, column_widths=["20%", "15%", "65%"],
                    label="Events (date in your local time; the timestamp is what the file stores). "
                          "Change either one and the other follows. To remove an event, click it, then the Remove button below",
                    value=_events_table_value([]), visible=False, elem_classes="mantella-quiet-table",
                )
                # The table as last shown, to tell which cell of a row was edited
                events_shown = gr.State([])
                # The event last clicked, as its [date, timestamp, text] row, for Remove event
                selected_event = gr.State(None)
                with gr.Row(visible=False, elem_classes="tag-editor-actions") as remove_event_row:
                    gr.HTML("", elem_classes="tag-editor-spacer")
                    remove_event_btn = gr.Button("Click an event to remove it", variant="secondary", size="sm", scale=0,
                                                 min_width=200, interactive=False, elem_id="tag-editor-remove-event")
                with gr.Row():
                    new_event_text = gr.Text(label="What happened", placeholder="{player_name} became Thane of Whiterun", scale=3)
                    new_event_date = gr.Text(label="When (YYYY-MM-DD HH:MM)", placeholder="Empty = the exact time you click Add event", scale=1)
                    new_event_timestamp = gr.Text(label="Timestamp", placeholder="e.g. 1762435800", scale=1)
                    add_event_btn = gr.Button("Add event", variant="secondary", scale=0, min_width=120)

            # The NPCs who have the open tag
            with gr.Accordion(label="NPCs with this tag", open=False, visible=False, elem_id="tag-editor-npc-section", elem_classes="tag-editor-subsection") as npc_section:
                npc_list = gr.Markdown(elem_id="tag-editor-npc-list")

            outcome_boxes: List[gr.Text] = []
            outcome_labels: List[gr.Markdown] = []
            with gr.Accordion(label="Quest outcomes", open=False, elem_classes="tag-editor-subsection") as outcomes_section:
                for slot in range(1, OUTCOME_SLOTS + 1):
                    with gr.Row():
                        outcome_boxes.append(gr.Text(label=f"potential_paste_{slot}", lines=2, scale=3))
                        outcome_boxes.append(gr.Text(label=f"code_{slot}", lines=2, scale=2))
                    outcome_labels.append(gr.Markdown(elem_classes="tag-editor-source"))
                announce_box = gr.Checkbox(label="Announce changes of this tag to NPCs during a conversation", value=True)
                announce_source = gr.Markdown(elem_classes="tag-editor-source")
                mode_box = gr.Dropdown(choices=OUTCOME_MODE_CHOICES, value=OUTCOME_MODE_DEFAULT, filterable=False,
                                       label="Where this tag's quest outcome goes")
                mode_source = gr.Markdown(elem_classes="tag-editor-source")
                gr.Markdown("Changed conditions reach the game when the next conversation starts.", elem_classes="tag-editor-source")

            # The `source` column: which mod the tag is for. For people editing the files, like notes; never sent to the AI
            source_box = gr.Text(label="Source (which mod this tag is for; never sent to the AI)", max_lines=1,
                                 placeholder="e.g. Interesting NPCs")
            source_from = gr.Markdown(elem_classes="tag-editor-source")

            with gr.Accordion(label="Notes (for people editing the files; never sent to the AI)", open=False, elem_classes="tag-editor-subsection") as notes_section:
                notes_box = gr.Text(show_label=False, lines=2)
                notes_source = gr.Markdown(elem_classes="tag-editor-source")

            # The open tag's files and where a save goes, right above Save
            header = gr.Markdown("", visible=False, elem_classes="tag-editor-header")
            with gr.Row(elem_classes="tag-editor-actions"):
                save_btn = gr.Button("Save", variant="primary", scale=2)
                discard_btn = gr.Button("Discard changes", variant="secondary", scale=2)
                gr.HTML("", elem_classes="tag-editor-spacer")
                remove_btn = gr.Button("Delete tag", variant="stop", size="sm", visible=False, scale=0, min_width=170,
                                       elem_id="tag-editor-remove")
                confirm_remove_btn = gr.Button("Confirm", variant="stop", size="sm", visible=False, scale=0, min_width=150,
                                               elem_id="tag-editor-confirm-remove")
            remove_note = gr.Markdown(elem_classes=["tag-editor-source", "tag-editor-remove-note"])
        message_line = gr.Markdown()
    snapshot_state = gr.State({})

    with gr.Accordion(label="Global search", open=False):
        with gr.Row(equal_height=True):
            search_box = gr.Text(label="Find text in all tags", placeholder="e.g. Thane", max_lines=1, scale=4)
            search_btn = gr.Button("Search", variant="secondary", scale=0, min_width=120)
        search_summary = gr.Markdown()
        search_results = gr.Dataframe(headers=SEARCH_HEADERS, datatype=["str"] * 4, col_count=(4, "fixed"), interactive=False,
                                      wrap=True, value=pd.DataFrame([], columns=SEARCH_HEADERS), label="Results",
                                      elem_classes="mantella-quiet-table")
        search_result_rows = gr.State([])
        opened_result_tag = gr.State(None)

    field_inputs = [text_box, events_table, *outcome_boxes, announce_box, mode_box, notes_box, source_box]
    outputs = [
        tag_dropdown, snapshot_state, tag_note, choose_section, header, npc_section, new_tag_message, source_box, source_from,
        text_box, text_source, quest_warning, events_table, events_shown, selected_event, remove_event_btn, remove_event_row, no_events, new_event_text, new_event_date, new_event_timestamp,
        *outcome_boxes, *outcome_labels, outcomes_section, announce_box, announce_source, mode_box, mode_source,
        notes_section, notes_box, notes_source, npc_list,
        remove_btn, remove_note, confirm_remove_btn, new_tag_name, picker_message, message_line,
    ]

    # No loading animation on the events that refresh the whole form: Gradio puts one on every output, so Save and
    # the others filled each box of the form with its own copy (and style.css stops the greying out it does anyway).
    # So instead, each one first puts a short "Saving…" line where its result will appear (queue=False: shown at once,
    # not behind other events), and the result starts with the time it finished (finished())
    def with_working_line(trigger, text_fn, text_inputs, line, handler, inputs):
        trigger(text_fn, inputs=text_inputs, outputs=[line], queue=False, show_progress="hidden").then(
            finished(handler, line), inputs=inputs, outputs=outputs, show_progress="hidden")

    form_inputs = [snapshot_state, *field_inputs]
    with_working_line(tag_dropdown.input, opening_text, [tag_dropdown], picker_message, on_pick, [tag_dropdown, *form_inputs])
    search_outputs = [search_results, search_result_rows, search_summary]
    search_btn.click(on_search, inputs=[search_box], outputs=search_outputs)
    search_box.submit(on_search, inputs=[search_box], outputs=search_outputs)
    search_results.select(on_result_select, inputs=[search_result_rows], outputs=[opened_result_tag]).then(
        opening_text, inputs=[opened_result_tag], outputs=[picker_message], queue=False, show_progress="hidden").then(
        finished(on_open_result, picker_message), inputs=[opened_result_tag, *form_inputs], outputs=outputs, show_progress="hidden")
    for trigger in (create_btn.click, new_tag_name.submit):
        with_working_line(trigger, working("Creating…"), None, new_tag_message, on_create, [new_tag_name, *form_inputs])
    add_event_btn.click(finished(on_add_event, message_line), inputs=[events_table, new_event_text, new_event_date, new_event_timestamp],
                        outputs=outputs, show_progress="hidden")
    # Only typing triggers these (.input), so filling one box from the other doesn't loop back. "always_last": the
    # default ("once") ignores keystrokes while a call is running, so the other box would keep the value for a
    # half-typed date and Add event would then find two different moments
    new_event_date.input(on_new_event_date, inputs=[new_event_date], outputs=[new_event_timestamp],
                         show_progress="hidden", trigger_mode="always_last")
    new_event_timestamp.input(on_new_event_timestamp, inputs=[new_event_timestamp], outputs=[new_event_date],
                              show_progress="hidden", trigger_mode="always_last")
    # Small events with only the components they change, and no loading animation: Gradio shows one on every
    # output while an event runs, so listing the whole form made the page flicker
    events_outputs = [events_table, events_shown, selected_event, remove_event_btn, remove_event_row, no_events, message_line]
    events_table.input(on_events_edited, inputs=[events_table, events_shown], outputs=events_outputs,
                       show_progress="hidden", trigger_mode="always_last")
    events_table.select(on_event_select, inputs=[events_table], outputs=[selected_event, remove_event_btn], show_progress="hidden")
    remove_event_btn.click(finished(on_remove_event, message_line), inputs=[events_table, selected_event], outputs=events_outputs,
                           show_progress="hidden")
    with_working_line(save_btn.click, working("Saving…"), None, message_line, on_save, form_inputs)
    with_working_line(refresh_btn.click, working("Reading the tag files…"), None, message_line, on_refresh, form_inputs)
    with_working_line(discard_btn.click, working("Discarding…"), None, message_line, on_discard, form_inputs)
    remove_btn.click(finished(on_remove, message_line), inputs=[snapshot_state], outputs=outputs, show_progress="hidden")
    with_working_line(confirm_remove_btn.click, confirm_text, [snapshot_state], message_line, on_confirm_remove, [snapshot_state])

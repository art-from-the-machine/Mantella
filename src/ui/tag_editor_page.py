"""The Tag Editor tab: read, change and add tags without opening CSV files.

See docs/tag_editor.md. File handling lives in tag_editor_files.py; this module is the UI and applying changes to the running game.
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

import gradio as gr
import pandas as pd

import src.utils as utils
from src.bio_template_manager import LAYER_BASE, LAYER_MOD, LAYER_PERSONAL, OUTCOME_SLOTS, TAG_COLUMNS, BioTemplateManager
from src.config.config_loader import ConfigLoader
from src.config.definitions.game_definitions import GameEnum
from src.quest_tags import history as quest_tag_history
from src.quest_tags.conditions import CheckList
from src.ui import tag_editor_files as files

LAYER_NAMES = {LAYER_BASE: "Base", LAYER_MOD: "Mod", LAYER_PERSONAL: "Personal"}
EVENT_HEADERS = ["Date", "Event"]
NEW_EVENT_DATE_FORMAT = "%Y-%m-%d %H:%M"
OUTCOME_COLUMNS = [column for slot in range(1, OUTCOME_SLOTS + 1) for column in (f"potential_paste_{slot}", f"code_{slot}")]
NPC_LIST_NEEDS_GAME = "Shown once Mantella has connected to the game."
SEARCH_HEADERS = ["Tag", "Where", "Text", "From"]
SEARCH_RESULT_LIMIT = 200


def _column_name(column: str) -> str:
    """A column as the tab calls it"""
    if column == "description":
        return "tag text and events"
    if column.startswith("potential_paste_"):
        return f"outcome {column.rsplit('_', 1)[1]} text"
    if column.startswith("code_"):
        return f"condition {column.rsplit('_', 1)[1]}"
    return column


def _now_for_new_event() -> str:
    return datetime.now().strftime(NEW_EVENT_DATE_FORMAT)


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _event_rows(table: Any) -> List[List[str]]:
    """The events table as [date, text] rows. Rows without text are dropped: clearing the text deletes the event"""
    if isinstance(table, pd.DataFrame):
        raw_rows = table.values.tolist()
    elif isinstance(table, dict):
        raw_rows = table.get("data") or []
    else:
        raw_rows = table or []
    rows: List[List[str]] = []
    for row in raw_rows:
        cells = list(row) + ["", ""]
        date, text = _cell_text(cells[0]).strip(), files.clean_event_text(_cell_text(cells[1]))
        if text:
            rows.append([date, text])
    return rows


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

    def outcome_label(tag: str, slot: int, code: str) -> str:
        parts = []
        text_source = source_label(tag, f"potential_paste_{slot}")
        code_source = source_label(tag, f"code_{slot}")
        if text_source:
            parts.append(f"Text {text_source[0].lower()}{text_source[1:]}")
        if code_source:
            parts.append(f"Condition {code_source[0].lower()}{code_source[1:]}")
        reason = unreadable_reasons(tag, {slot: code}).get(slot)
        if reason:
            parts.append(f"**Condition {slot} can't be read: {reason}**")
        return " · ".join(parts)

    def render(tag: str | None, is_new: bool = False, message: str = "") -> Dict[Any, Any]:
        """Every component showing this tag, as loaded from the files. No tag clears the form"""
        tags = all_tags()
        if not tag:
            values = {column: "" for column in TAG_COLUMNS}
        else:
            values = {column: (files.current_source(manager().sources, tag, column) or ("", "", ""))[2] for column in TAG_COLUMNS}
        text, events = files.split_description(values["description"])
        event_rows = [[files.format_event_date(ts), files.clean_event_text(event)] for ts, event in sorted(events)]
        announce = values["announce"].strip().lower() != "no"
        # Each event's exact timestamp, so saving doesn't turn an untouched event's shown local time back into a different one
        event_timestamps = [[date, event, ts] for (date, event), (ts, _) in zip(event_rows, sorted(events))]
        snapshot = {"tag": tag or "", "is_new": is_new, "text": text, "events": event_rows, "announce": announce,
                    "cells": values, "event_timestamps": event_timestamps}

        update: Dict[Any, Any] = {
            tag_dropdown: gr.update(choices=tags + ([tag] if is_new and tag not in tags else []), value=tag or None),
            snapshot_state: snapshot,
            text_box: text,
            events_table: _events_table_value(event_rows),
            announce_box: announce,
            notes_box: values["notes"],
            new_event_text: "",
            new_event_date: _now_for_new_event(),
            confirm_delete_btn: gr.update(visible=False),
            confirm_back_btn: gr.update(visible=False),
            tag_note: tag_reading_note(),
            message_line: message,
        }
        for column, box in zip(OUTCOME_COLUMNS, outcome_boxes):
            update[box] = values[column]

        has_conditions = bool(tag) and any(values[f"code_{slot}"] for slot in range(1, OUTCOME_SLOTS + 1))
        update[quest_warning] = gr.update(
            visible=has_conditions,
            value="This tag has quest outcomes. **Filling in the tag text turns its automatic outcomes off.**",
        )
        if tag:
            update[text_source] = source_label(tag, "description")
            update[announce_source] = source_label(tag, "announce")
            update[notes_source] = source_label(tag, "notes")
            for slot, label in enumerate(outcome_labels, start=1):
                update[label] = outcome_label(tag, slot, values[f"code_{slot}"])
            npcs = npcs_by_tag()
            if npcs is None:
                update[npc_list] = NPC_LIST_NEEDS_GAME
            else:
                with_tag = npcs.get(tag, [])
                update[npc_list] = ", ".join(with_tag) if with_tag else "No NPC has this tag. Give it to NPCs in the Bio Editor."
            in_files = manager().files_with_tag.get(tag, [])
            personal = files.personal_files(manager().files_with_tag, tag)
            base_or_mod = files.has_base_or_mod_rows(manager().files_with_tag, tag)
            update[delete_btn] = gr.update(interactive=bool(in_files) and not base_or_mod)
            update[back_btn] = gr.update(interactive=bool(personal) and base_or_mod)
        else:
            for component in [text_source, announce_source, notes_source, npc_list, *outcome_labels]:
                update[component] = ""
            update[delete_btn] = gr.update(interactive=False)
            update[back_btn] = gr.update(interactive=False)
        return update

    # --- What's on screen vs what was loaded ---

    def form_values(field_values: Tuple[Any, ...]) -> Dict[str, Any]:
        text, table, *rest = field_values
        outcome_values = rest[:len(OUTCOME_COLUMNS)]
        announce, notes = rest[len(OUTCOME_COLUMNS):]
        values = {
            "text": (text or "").strip(),
            "events": _event_rows(table),
            "announce": bool(announce),
            "notes": (notes or "").strip(),
        }
        for column, value in zip(OUTCOME_COLUMNS, outcome_values):
            values[column] = (value or "").strip()
        return values

    def has_unsaved_changes(snapshot: Dict[str, Any], field_values: Tuple[Any, ...]) -> bool:
        if not snapshot or not snapshot.get("tag"):
            return False
        current = form_values(field_values)
        cells = snapshot["cells"]
        if current["text"] != snapshot["text"].strip() or current["events"] != snapshot["events"]:
            return True
        if current["announce"] != snapshot["announce"] or current["notes"] != cells["notes"].strip():
            return True
        return any(current[column] != cells[column].strip() for column in OUTCOME_COLUMNS)

    def unsaved_message(snapshot: Dict[str, Any]) -> Dict[Any, Any]:
        return {
            tag_dropdown: gr.update(value=snapshot["tag"]),
            message_line: f"You have unsaved changes to `{snapshot['tag']}`. Save them, or click **Discard changes**, then pick the tag again.",
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
            return {}
        if has_unsaved_changes(snapshot, field_values):
            return unsaved_message(snapshot)
        load_manager()
        return render(tag)

    def on_create(name: str, snapshot: Dict[str, Any], *field_values):
        if has_unsaved_changes(snapshot, field_values):
            return unsaved_message(snapshot)
        tag = utils.normalize_apostrophes((name or "").strip())
        if not tag:
            return {message_line: "Type a name for the new tag first."}
        if "," in tag:
            return {message_line: "A tag name can't contain commas: an NPC's tags are written as a comma-separated list."}
        if tag in load_manager().files_with_tag:
            return {message_line: f"`{tag}` already exists. Pick it from the list to change it."}
        update = render(tag, is_new=True, message=f"New tag `{tag}`. Fill it in and click **Save**; it's only written to a file then. After that, give it to NPCs in the Bio Editor.")
        update[new_tag_name] = ""
        return update

    def on_add_event(table, text: str, date: str):
        event_text = files.clean_event_text(text)
        if not event_text:
            return {message_line: "Type what happened first."}
        try:
            timestamp = files.parse_event_date(date)
        except ValueError as e:
            return {message_line: str(e)}
        rows = _event_rows(table) + [[files.format_event_date(timestamp), event_text]]
        return {
            events_table: _events_table_value(rows),
            new_event_text: "",
            new_event_date: _now_for_new_event(),
            message_line: "Event added. Click **Save** to keep it.",
        }

    def on_save(snapshot: Dict[str, Any], *field_values):
        tag = (snapshot or {}).get("tag")
        if not tag:
            return {message_line: "Pick a tag first."}
        current = form_values(field_values)
        try:
            events = files.event_timestamps(current["events"], [tuple(entry) for entry in snapshot.get("event_timestamps", [])])
        except ValueError as e:
            return {message_line: f"An event date can't be read: {e}"}

        before = snapshot["cells"]
        after: Dict[str, str] = {column: current[column] for column in OUTCOME_COLUMNS}
        after["notes"] = current["notes"]
        if current["text"] != snapshot["text"].strip() or current["events"] != snapshot["events"]:
            after["description"] = files.join_description(current["text"], events)
        changes = files.changed_cells({column: before.get(column, "") for column in after}, after)
        if current["announce"] != snapshot["announce"]:
            changes["announce"] = "yes" if current["announce"] else "no"
        if not changes and not snapshot.get("is_new"):
            return {message_line: "Nothing to save."}

        m = load_manager()
        folder = files.personal_folder(config.save_folder)
        target = files.choose_target_file(m.files_with_tag, tag, folder)
        written: List[str] = []
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
            if changes or snapshot.get("is_new"):
                files.write_cells(target, tag, changes)
                written.append(target)
        except Exception as e:
            logging.warning(f"Tag Editor: could not save {tag}: {e}")
            return {message_line: f"Couldn't save `{tag}`: {e}"}

        lines = []
        if written:
            names = ", ".join(f"`{os.path.basename(path)}`" for path in dict.fromkeys(written))
            what = ", ".join(_column_name(column) for column in changes) or "the new tag"
            lines.append(f"Saved {what} to {names} (the previous version is in the `.bak` file next to it).")
        lines += notes
        reasons = unreadable_reasons(tag, {slot: current[f"code_{slot}"] for slot in range(1, OUTCOME_SLOTS + 1)})
        for slot, reason in sorted(reasons.items()):
            lines.append(f"Condition {slot} can't be read: {reason}. It's saved, but that outcome won't happen automatically until it's fixed.")
        if written:
            lines += apply_to_game(tag)
        load_manager()
        return render(tag, message="\n\n".join(lines))

    def on_refresh(snapshot: Dict[str, Any], *field_values):
        if has_unsaved_changes(snapshot, field_values):
            return unsaved_message(snapshot)
        load_manager()
        tag = (snapshot or {}).get("tag")
        if tag and tag not in manager().files_with_tag:
            tag = None
        return render(tag, message="Read all tag files again.")

    def on_discard(snapshot: Dict[str, Any]):
        tag = (snapshot or {}).get("tag")
        if not tag:
            return {message_line: "Nothing to discard."}
        if snapshot.get("is_new"):
            return render(None, message=f"Dropped the new tag `{tag}`.")
        load_manager()
        return render(tag if tag in manager().files_with_tag else None, message="Unsaved changes dropped.")

    def npc_count_line(tag: str) -> str:
        npcs = npcs_by_tag()
        if npcs is None:
            return ""
        count = len(npcs.get(tag, []))
        if not count:
            return " No NPC has it."
        return f" {count} NPC{'s' if count != 1 else ''} still {'have' if count != 1 else 'has'} it: they keep the tag name, but it won't add anything."

    def on_delete(snapshot: Dict[str, Any]):
        tag = (snapshot or {}).get("tag")
        if not tag:
            return {message_line: "Pick a tag first."}
        paths = files.personal_files(load_manager().files_with_tag, tag)
        names = ", ".join(f"`{os.path.basename(path)}`" for path in paths)
        return {
            confirm_delete_btn: gr.update(visible=True),
            confirm_back_btn: gr.update(visible=False),
            message_line: f"Delete `{tag}`? This removes its row from {names} in your personal folder.{npc_count_line(tag)} Click **Confirm delete** to go ahead.",
        }

    def on_confirm_delete(snapshot: Dict[str, Any]):
        tag = (snapshot or {}).get("tag")
        files_with_tag = load_manager().files_with_tag
        if not tag or not files.personal_files(files_with_tag, tag) or files.has_base_or_mod_rows(files_with_tag, tag):
            return {message_line: "Only a tag that exists only in your personal files can be deleted.", confirm_delete_btn: gr.update(visible=False)}
        try:
            changed = files.remove_tag_rows(files.personal_files(files_with_tag, tag), tag)
        except Exception as e:
            logging.warning(f"Tag Editor: could not delete {tag}: {e}")
            return {message_line: f"Couldn't delete `{tag}`: {e}", confirm_delete_btn: gr.update(visible=False)}
        lines = [f"Deleted `{tag}` from {', '.join(f'`{os.path.basename(path)}`' for path in changed)} (the previous version is in the `.bak` file next to it)."]
        lines += apply_to_game(tag)
        load_manager()
        return render(None, message="\n\n".join(lines))

    def on_back(snapshot: Dict[str, Any]):
        tag = (snapshot or {}).get("tag")
        if not tag:
            return {message_line: "Pick a tag first."}
        paths = files.personal_files(load_manager().files_with_tag, tag)
        names = ", ".join(f"`{os.path.basename(path)}`" for path in paths)
        return {
            confirm_back_btn: gr.update(visible=True),
            confirm_delete_btn: gr.update(visible=False),
            message_line: f"Remove your changes to `{tag}`? This removes its row from {names} in your personal folder, so every field goes back to the base or mod version. Base and mod files aren't touched. Click **Confirm** to go ahead.",
        }

    def on_confirm_back(snapshot: Dict[str, Any]):
        tag = (snapshot or {}).get("tag")
        files_with_tag = load_manager().files_with_tag
        if not tag or not files.personal_files(files_with_tag, tag) or not files.has_base_or_mod_rows(files_with_tag, tag):
            return {message_line: "Back to original only works for a tag that's in a base or mod file and that you've changed.", confirm_back_btn: gr.update(visible=False)}
        try:
            changed = files.remove_tag_rows(files.personal_files(files_with_tag, tag), tag)
        except Exception as e:
            logging.warning(f"Tag Editor: could not undo the changes to {tag}: {e}")
            return {message_line: f"Couldn't undo your changes to `{tag}`: {e}", confirm_back_btn: gr.update(visible=False)}
        lines = [f"`{tag}` is back to the original. Removed its row from {', '.join(f'`{os.path.basename(path)}`' for path in changed)} (the previous version is in the `.bak` file next to it)."]
        lines += apply_to_game(tag)
        load_manager()
        return render(tag, message="\n\n".join(lines))

    # --- Search ---

    def on_search(query: str):
        """Find text in every tag's current values, like Ctrl+F across the tag files"""
        if not (query or "").strip():
            return {search_results: pd.DataFrame([], columns=SEARCH_HEADERS), search_result_tags: [], search_summary: ""}
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
        return {search_results: pd.DataFrame(rows, columns=SEARCH_HEADERS), search_result_tags: [result["tag"] for result in shown], search_summary: summary}

    def on_result_select(result_tags: List[str], evt: gr.SelectData):
        """The tag of the clicked row. Opening it is the next step, with the usual unsaved-changes check"""
        row = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        return result_tags[row] if isinstance(row, int) and 0 <= row < len(result_tags or []) else None

    def on_open_result(tag: str | None, snapshot: Dict[str, Any], *field_values):
        if not tag:
            return {}
        return on_pick(tag, snapshot, *field_values)

    # --- Layout ---

    gr.Markdown(
        "Change what a tag says, add dated events, and create new tags. "
        "Changes are saved to your personal files (`Documents\\My Games\\Mantella\\data\\Skyrim\\bio_templates`) and apply right away, "
        "including to NPCs in a running conversation. Base and mod files are never changed."
    )
    tag_note = gr.Markdown(tag_reading_note())
    with gr.Accordion(label="Search", open=True):
        with gr.Row():
            search_box = gr.Text(label="Find text in all tags", placeholder="e.g. Thane", max_lines=1, scale=4)
            search_btn = gr.Button("Search", variant="secondary", scale=1)
        search_summary = gr.Markdown()
        search_results = gr.Dataframe(headers=SEARCH_HEADERS, datatype=["str"] * 4, col_count=(4, "fixed"), interactive=False,
                                      wrap=True, value=pd.DataFrame([], columns=SEARCH_HEADERS), label="Results")
        search_result_tags = gr.State([])
        opened_result_tag = gr.State(None)
    with gr.Row():
        tag_dropdown = gr.Dropdown(choices=all_tags(), value=None, label="Tag", filterable=True, allow_custom_value=False, scale=3)
        new_tag_name = gr.Text(label="New tag", max_lines=1, placeholder="new_tag_name", scale=2)
        create_btn = gr.Button("Create", variant="secondary", scale=1)

    text_box = gr.Text(label="Tag text (added to the bio of every NPC with this tag)", lines=6)
    text_source = gr.Markdown()
    quest_warning = gr.Markdown(visible=False)

    with gr.Accordion(label="Dated events", open=True):
        events_table = gr.Dataframe(
            headers=EVENT_HEADERS, datatype=["str", "str"], col_count=(2, "fixed"), row_count=(1, "dynamic"),
            interactive=True, wrap=True, label="Events (your local time). Clear an event's text to delete it", value=_events_table_value([]),
        )
        with gr.Row():
            new_event_text = gr.Text(label="What happened", placeholder="{player_name} became Thane of Whiterun", scale=3)
            new_event_date = gr.Text(label="Date (YYYY-MM-DD HH:MM)", value=_now_for_new_event(), scale=1)
            add_event_btn = gr.Button("Add", variant="secondary", scale=0)
        gr.Markdown(
            "An event dated after an NPC's last conversation shows up as **New developments since last meeting** "
            "the next time you talk to them, so an event dated now is new for every NPC with this tag."
        )

    outcome_boxes: List[gr.Text] = []
    outcome_labels: List[gr.Markdown] = []
    with gr.Accordion(label="Quest outcomes", open=False):
        for slot in range(1, OUTCOME_SLOTS + 1):
            with gr.Row():
                outcome_boxes.append(gr.Text(label=f"Outcome {slot} text", lines=2, scale=3))
                outcome_boxes.append(gr.Text(label=f"Outcome {slot} condition", lines=2, scale=2))
            outcome_labels.append(gr.Markdown())
        announce_box = gr.Checkbox(label="Announce changes of this tag to NPCs during a conversation", value=True)
        announce_source = gr.Markdown()
        gr.Markdown("Changed conditions reach the game when the next conversation starts.")

    notes_box = gr.Text(label="Notes (for people editing the files; never sent to the AI)", lines=2)
    notes_source = gr.Markdown()
    npc_list = gr.Text(label="NPCs with this tag", lines=2, interactive=False, value="")

    with gr.Row():
        save_btn = gr.Button("Save", variant="primary")
        refresh_btn = gr.Button("Refresh", variant="secondary")
        discard_btn = gr.Button("Discard changes", variant="secondary")
        delete_btn = gr.Button("Delete tag", variant="stop", interactive=False)
        confirm_delete_btn = gr.Button("Confirm delete", variant="stop", visible=False)
        back_btn = gr.Button("Back to original", variant="secondary", interactive=False)
        confirm_back_btn = gr.Button("Confirm", variant="stop", visible=False)
    message_line = gr.Markdown()
    snapshot_state = gr.State({})

    field_inputs = [text_box, events_table, *outcome_boxes, announce_box, notes_box]
    outputs = [
        tag_dropdown, snapshot_state, tag_note, text_box, text_source, quest_warning, events_table, new_event_text, new_event_date,
        *outcome_boxes, *outcome_labels, announce_box, announce_source, notes_box, notes_source, npc_list,
        delete_btn, confirm_delete_btn, back_btn, confirm_back_btn, new_tag_name, message_line,
    ]

    tag_dropdown.input(on_pick, inputs=[tag_dropdown, snapshot_state, *field_inputs], outputs=outputs)
    search_outputs = [search_results, search_result_tags, search_summary]
    search_btn.click(on_search, inputs=[search_box], outputs=search_outputs)
    search_box.submit(on_search, inputs=[search_box], outputs=search_outputs)
    search_results.select(on_result_select, inputs=[search_result_tags], outputs=[opened_result_tag]).then(
        on_open_result, inputs=[opened_result_tag, snapshot_state, *field_inputs], outputs=outputs)
    create_btn.click(on_create, inputs=[new_tag_name, snapshot_state, *field_inputs], outputs=outputs)
    add_event_btn.click(on_add_event, inputs=[events_table, new_event_text, new_event_date], outputs=outputs)
    save_btn.click(on_save, inputs=[snapshot_state, *field_inputs], outputs=outputs)
    refresh_btn.click(on_refresh, inputs=[snapshot_state, *field_inputs], outputs=outputs)
    discard_btn.click(on_discard, inputs=[snapshot_state], outputs=outputs)
    delete_btn.click(on_delete, inputs=[snapshot_state], outputs=outputs)
    confirm_delete_btn.click(on_confirm_delete, inputs=[snapshot_state], outputs=outputs)
    back_btn.click(on_back, inputs=[snapshot_state], outputs=outputs)
    confirm_back_btn.click(on_confirm_back, inputs=[snapshot_state], outputs=outputs)

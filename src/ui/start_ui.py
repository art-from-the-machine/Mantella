from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
import webbrowser
import gradio as gr
from src.config.config_loader import ConfigLoader
from src.http.routes.routeable import routeable
from src.ui.settings_ui_constructor import SettingsUIConstructor
import logging
import os
import sys
import pandas as pd
from src.config.definitions.game_definitions import GameEnum
import src.utils as utils
import json
import re
from src.ui.bio_llm_requester import BioLLMRequester
from src.ui.tab_reorder import (
    BIO_EDITOR_TAB,
    DOCUMENTATION_TAB,
    LIVE_CONVERSATION_TAB,
    TAB_REORDER_JS,
    default_tab_names,
    merge_tab_order,
)
from src.ui.bio_editor_memory_files import (
    conversations_base_dir,
    load_latest_text,
    pick_world_id,
    reflections_base_dir,
    save_latest_text,
    thoughts_base_dir,
)
from src.llm.client_base import ClientBase

class StartUI(routeable):
    BANNER = "docs/_static/img/mantella_banner.png"
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config, False)
        self.__constructor = SettingsUIConstructor(config)

    def create_main_block(self) -> gr.Blocks:
        with gr.Blocks(title="Mantella", fill_height=True, analytics_enabled=False, theme= self.__get_theme(), css=self.__load_css(), js="() => {\n" + TAB_REORDER_JS + "\n}", head="<script>" + TAB_REORDER_JS + "</script>") as main_block:
            # with gr.Tab("Settings") as tabs:
            self.__generate_tabs()
            # with gr.Tab("Chat with NPCs", interactive=False):
            #     self.__generate_chat_page()
            # with gr.Tab("NPC editor", interactive=False):
            #     self.__generate_character_editor_page()

            with gr.Row(elem_classes="custom-footer"):
                gr.HTML("""
                    <div class="custom-footer">
                        <a href="https://art-from-the-machine.github.io/Mantella/" target="_blank">Mantella Installation Guide</a>
                    </div>
                """)
        return main_block

    def __generate_tabs(self) -> None:
        groups_by_name = {cf.name: cf for cf in self._config.definitions.base_groups if not cf.is_hidden}
        ordered_names = merge_tab_order(
            default_tab_names(self._config.definitions.base_groups),
            self._config.get_ui_tab_order(),
        )
        for name in ordered_names:
            with gr.Tab(name):
                if name == LIVE_CONVERSATION_TAB:
                    self.__generate_live_conversation_page()
                elif name == BIO_EDITOR_TAB:
                    self.__generate_bio_editor_page()
                elif name == DOCUMENTATION_TAB:
                    self.__generate_documentation_page()
                else:
                    group = groups_by_name.get(name)
                    if group is not None:
                        group.accept_visitor(self.__constructor)

        self.__constructor.setup_model_dependencies()
    
    def __generate_chat_page(self):
        return gr.Column()
    
    def __generate_character_editor_page(self):
        return gr.Column()

    def __generate_documentation_page(self):
        docs_url = "https://github.com/dreaminalife/Mantella/blob/personal_use/FEATURES_README.md"
        gr.Markdown(
            "# Documentation\n\n"
            "Trying my best to explain why I added these features and how to make the most of them. "
            "Currently it only works with Mantella below v 0.14.\n\n"
            f"See the full feature docs here:\n\n"
            f"**[{docs_url}]({docs_url})**"
        )

    def __generate_live_conversation_page(self):
        gr.Markdown(
            "Edit the active conversation in real time. When the model returns gibberish, click **Reload** to fetch the current history, fix the bad text in the JSON, then click **Save** to apply. Use **Undo last round** to remove the last player turn and everything after it, **Undo NPC reply** to keep the player line and drop only the reply, or **Remove last user message** to drop the last player line when it is the most recent message. All information is preserved in the JSON format."
        )
        live_conversation_editor = gr.Text(value="", lines=20, label="Conversation (JSON)", placeholder="Click Reload to fetch current conversation. Edit the JSON and click Save to apply changes.")
        with gr.Row():
            live_reload_btn = gr.Button("Reload", variant="secondary")
            live_save_btn = gr.Button("Save", variant="primary")
            live_undo_btn = gr.Button("Undo last round", variant="secondary")
            live_undo_npc_reply_btn = gr.Button("Undo NPC reply", variant="secondary")
            live_remove_last_user_btn = gr.Button("Remove last user message", variant="secondary")
        live_conversation_info = gr.Markdown(value="", visible=True)
        live_decensor_preview = gr.Text(
            value="",
            lines=8,
            label="Decensor bypass (read-only)",
            info="Sent after the system prompt and before this conversation. Edit the wording in Prompts or Prompt Profiles, then click Reload.",
            placeholder="Nothing is sent until Enable Decensor Bypass is on and both prompts have text. Click Reload to refresh.",
            interactive=False,
        )

        def decensor_preview(gm) -> str:
            if not gm:
                return ""
            return gm.get_decensor_bypass_preview()

        def on_live_reload():
            try:
                from src.ui import settings_ui_constructor as sui
                gm = getattr(sui, '_game_manager_ref', None)
                if not gm:
                    return "", "", " No game manager. Start the game first."
                preview = decensor_preview(gm)
                json_str = gm.get_conversation_as_json()
                if json_str is None:
                    return "", preview, " No active conversation, or conversation has no messages yet."
                return json_str, preview, " Reloaded current conversation."
            except Exception as e:
                logging.error(f"Live conversation reload failed: {e}", exc_info=True)
                return "", "", f" Reload failed: {e}"

        def on_live_save(json_str: str):
            if not json_str or not json_str.strip():
                return " Enter or load conversation JSON first."
            try:
                from src.ui import settings_ui_constructor as sui
                gm = getattr(sui, '_game_manager_ref', None)
                if not gm:
                    return " No game manager. Start the game first."
                ok = gm.apply_conversation_from_json(json_str.strip())
                if ok:
                    return " Conversation updated successfully."
                return " Apply failed. Check logs."
            except Exception as e:
                logging.error(f"Live conversation save failed: {e}", exc_info=True)
                return f" Save failed: {e}"

        def on_live_undo():
            try:
                from src.ui import settings_ui_constructor as sui
                gm = getattr(sui, '_game_manager_ref', None)
                if not gm:
                    return "", "", " No game manager. Start the game first."
                result = gm.undo_last_conversation_round()
                preview = decensor_preview(gm)
                if result is None:
                    return "", preview, " No active conversation."
                json_str = gm.get_conversation_as_json() or ""
                if result:
                    return json_str, preview, " Undid last round of talk."
                return json_str, preview, " No player turn to undo."
            except Exception as e:
                logging.error(f"Live conversation undo failed: {e}", exc_info=True)
                return "", "", f" Undo failed: {e}"

        def on_live_undo_npc_reply():
            try:
                from src.ui import settings_ui_constructor as sui
                gm = getattr(sui, '_game_manager_ref', None)
                if not gm:
                    return "", "", " No game manager. Start the game first."
                result = gm.undo_last_npc_reply()
                preview = decensor_preview(gm)
                if result is None:
                    return "", preview, " No active conversation."
                json_str = gm.get_conversation_as_json() or ""
                if result:
                    return json_str, preview, " Undid last NPC reply."
                return json_str, preview, " No NPC reply to undo."
            except Exception as e:
                logging.error(f"Live conversation undo NPC reply failed: {e}", exc_info=True)
                return "", "", f" Undo NPC reply failed: {e}"

        def on_live_remove_last_user_message():
            try:
                from src.ui import settings_ui_constructor as sui
                gm = getattr(sui, '_game_manager_ref', None)
                if not gm:
                    return "", "", " No game manager. Start the game first."
                result = gm.undo_last_user_message()
                preview = decensor_preview(gm)
                if result is None:
                    return "", preview, " No active conversation."
                json_str = gm.get_conversation_as_json() or ""
                if result:
                    return json_str, preview, " Removed last user message."
                return json_str, preview, " Last message is not from the user."
            except Exception as e:
                logging.error(f"Live conversation remove last user message failed: {e}", exc_info=True)
                return "", "", f" Remove last user message failed: {e}"

        live_reload_btn.click(
            on_live_reload,
            inputs=[],
            outputs=[live_conversation_editor, live_decensor_preview, live_conversation_info],
        )
        live_save_btn.click(
            on_live_save,
            inputs=[live_conversation_editor],
            outputs=[live_conversation_info],
        )
        live_undo_btn.click(
            on_live_undo,
            inputs=[],
            outputs=[live_conversation_editor, live_decensor_preview, live_conversation_info],
        )
        live_undo_npc_reply_btn.click(
            on_live_undo_npc_reply,
            inputs=[],
            outputs=[live_conversation_editor, live_decensor_preview, live_conversation_info],
        )
        live_remove_last_user_btn.click(
            on_live_remove_last_user_message,
            inputs=[],
            outputs=[live_conversation_editor, live_decensor_preview, live_conversation_info],
        )

    def __generate_bio_editor_page(self):
        config = self._config

        def _get_game_folder_name() -> str:
            # Use capitalization consistent with Gameable override loader
            return 'Fallout4' if config.game.base_game == GameEnum.FALLOUT4 else 'Skyrim'

        def _get_base_csv_path() -> str:
            return 'data/Fallout4/fallout4_characters.csv' if config.game.base_game == GameEnum.FALLOUT4 else 'data/Skyrim/skyrim_characters.csv'

        def _get_personal_override_dir() -> str:
            return os.path.join(config.save_folder, 'data', _get_game_folder_name(), 'character_overrides')

        def _get_resolved_character_df() -> pd.DataFrame:
            # Prefer the active game's merged DataFrame if available (fast path)
            try:
                from src.ui import settings_ui_constructor as sui
                if sui._game_manager_ref and hasattr(sui._game_manager_ref, 'game'):
                    df = sui._game_manager_ref.game.character_df
                    if df is not None:
                        return df.copy()
            except Exception as e:
                logging.debug(f"Bio Editor: fallback to base CSV (reason: {e})")

            # Fallback: base CSV + apply all override files (CSV/JSON) to include override-only NPCs
            base_csv = _get_base_csv_path()
            try:
                encoding = utils.get_file_encoding(base_csv)
                base_df = pd.read_csv(base_csv, engine='python', encoding=encoding)
            except Exception as e:
                logging.error(f"Bio Editor: failed to read base CSV '{base_csv}': {e}")
                return pd.DataFrame(columns=['name','base_id','race','bio'])

            # Ensure required columns exist and normalize keys
            key_cols = ['name','base_id','race']
            for c in key_cols:
                if c not in base_df.columns:
                    base_df[c] = ''
            for c in key_cols:
                base_df[c] = base_df[c].fillna('').astype(str)
                try:
                    base_df[c] = base_df[c].str.strip()
                except Exception:
                    pass
            if 'bio' not in base_df.columns:
                base_df['bio'] = ''

            # Apply all overrides from both mod and personal folders
            try:
                files = _list_override_files_in_order()
                for full_path in files:
                    filename, extension = os.path.splitext(full_path)
                    ext = extension.lower()
                    if ext == '.csv':
                        try:
                            enc = utils.get_file_encoding(full_path)
                            odf = pd.read_csv(full_path, engine='python', encoding=enc)
                            if odf is None or odf.empty:
                                continue
                            # Minimal columns
                            for c in key_cols:
                                if c not in odf.columns:
                                    odf[c] = ''
                                odf[c] = odf[c].fillna('').astype(str)
                            if 'bio' not in odf.columns:
                                odf['bio'] = ''
                            # Merge: update matching rows; add non-matching as new rows
                            for _, orow in odf.iterrows():
                                oname = str(orow.get('name','')).strip()
                                obase = str(orow.get('base_id','')).strip()
                                orace = str(orow.get('race','')).strip()
                                mb = (base_df['name'] == oname) & (base_df['base_id'] == obase) & (base_df['race'] == orace)
                                if mb.any():
                                    # Update non-empty bio
                                    obio = orow.get('bio','')
                                    if obio is not None and not (isinstance(obio, float) and pd.isna(obio)) and str(obio) != '':
                                        base_df.loc[mb, 'bio'] = str(obio)
                                else:
                                    new_row = {
                                        'name': oname,
                                        'base_id': obase,
                                        'race': orace,
                                        'bio': str(orow.get('bio','') if not pd.isna(orow.get('bio','')) else '')
                                    }
                                    base_df = pd.concat([base_df, pd.DataFrame([new_row])], ignore_index=True)
                        except Exception as e:
                            logging.debug(f"Bio Editor: failed reading override CSV {full_path}: {e}")
                    elif ext == '.json':
                        try:
                            # Skip empty JSON files
                            if os.path.getsize(full_path) == 0:
                                continue
                            with open(full_path, 'r', encoding='utf-8') as fp:
                                obj = json.load(fp)
                            items = obj if isinstance(obj, list) else [obj]
                            for content in items:
                                if not isinstance(content, dict):
                                    continue
                                oname = str(content.get('name','')).strip()
                                obase = str(content.get('base_id','')).strip()
                                orace = str(content.get('race','')).strip()
                                obio = content.get('bio', '')
                                mb = (base_df['name'] == oname) & (base_df['base_id'] == obase) & (base_df['race'] == orace)
                                if mb.any():
                                    if obio is not None and str(obio) != '':
                                        base_df.loc[mb, 'bio'] = str(obio)
                                else:
                                    new_row = {
                                        'name': oname,
                                        'base_id': obase,
                                        'race': orace,
                                        'bio': str(obio if obio is not None else '')
                                    }
                                    base_df = pd.concat([base_df, pd.DataFrame([new_row])], ignore_index=True)
                        except Exception as e:
                            logging.debug(f"Bio Editor: failed reading override JSON {full_path}: {e}")
            except Exception as e:
                logging.debug(f"Bio Editor: failed applying overrides in fallback: {e}")

            return base_df

        def _list_override_files_in_order() -> list[str]:
            files: list[str] = []
            try:
                mod_dir = os.path.join(config.mod_path_base, 'SKSE' if config.game.base_game != GameEnum.FALLOUT4 else 'F4SE', 'Plugins', 'MantellaSoftware', 'data', _get_game_folder_name(), 'character_overrides')
                if os.path.isdir(mod_dir):
                    for f in sorted(os.listdir(mod_dir)):
                        files.append(os.path.join(mod_dir, f))
            except Exception:
                pass
            try:
                personal_dir = _get_personal_override_dir()
                if os.path.isdir(personal_dir):
                    for f in sorted(os.listdir(personal_dir)):
                        files.append(os.path.join(personal_dir, f))
            except Exception:
                pass
            return files

        def _apply_override_file_to_df(base_df: pd.DataFrame, full_path: str) -> pd.DataFrame:
            try:
                if not full_path or not os.path.exists(full_path):
                    return base_df
                filename, extension = os.path.splitext(full_path)
                ext = extension.lower()
                key_cols = ['name','base_id','race']
                # Ensure required columns exist and normalized
                for c in key_cols + ['bio']:
                    if c not in base_df.columns:
                        base_df[c] = ''
                for c in key_cols:
                    base_df[c] = base_df[c].fillna('').astype(str)
                if ext == '.csv':
                    enc = utils.get_file_encoding(full_path)
                    odf = pd.read_csv(full_path, engine='python', encoding=enc)
                    if odf is None or odf.empty:
                        return base_df
                    for c in key_cols:
                        if c not in odf.columns:
                            odf[c] = ''
                        odf[c] = odf[c].fillna('').astype(str)
                    if 'bio' not in odf.columns:
                        odf['bio'] = ''
                    for _, orow in odf.iterrows():
                        oname = str(orow.get('name','')).strip()
                        obase = str(orow.get('base_id','')).strip()
                        orace = str(orow.get('race','')).strip()
                        mb = (base_df['name'] == oname) & (base_df['base_id'] == obase) & (base_df['race'] == orace)
                        if mb.any():
                            obio = orow.get('bio','')
                            if obio is not None and not (isinstance(obio, float) and pd.isna(obio)) and str(obio) != '':
                                base_df.loc[mb, 'bio'] = str(obio)
                        else:
                            new_row = {
                                'name': oname,
                                'base_id': obase,
                                'race': orace,
                                'bio': str(orow.get('bio','') if not pd.isna(orow.get('bio','')) else '')
                            }
                            base_df = pd.concat([base_df, pd.DataFrame([new_row])], ignore_index=True)
                elif ext == '.json':
                    if os.path.getsize(full_path) == 0:
                        return base_df
                    with open(full_path, 'r', encoding='utf-8') as fp:
                        obj = json.load(fp)
                    items = obj if isinstance(obj, list) else [obj]
                    for content in items:
                        if not isinstance(content, dict):
                            continue
                        oname = str(content.get('name','')).strip()
                        obase = str(content.get('base_id','')).strip()
                        orace = str(content.get('race','')).strip()
                        obio = content.get('bio', '')
                        mb = (base_df['name'] == oname) & (base_df['base_id'] == obase) & (base_df['race'] == orace)
                        if mb.any():
                            if obio is not None and str(obio) != '':
                                base_df.loc[mb, 'bio'] = str(obio)
                        else:
                            new_row = {
                                'name': oname,
                                'base_id': obase,
                                'race': orace,
                                'bio': str(obio if obio is not None else '')
                            }
                            base_df = pd.concat([base_df, pd.DataFrame([new_row])], ignore_index=True)
                return base_df
            except Exception as e:
                logging.debug(f"Bio Editor: failed to apply override file '{full_path}': {e}")
                return base_df

        def _build_provenance() -> dict[str, dict[str, dict]]:
            """Build mapping: key -> { 'row': {file,type,index}, 'bio': {file,type,index,is_single_json} }"""
            provenance: dict[str, dict[str, dict]] = {}
            files = _list_override_files_in_order()
            for full_path in files:
                try:
                    filename, extension = os.path.splitext(full_path)
                    ext = extension.lower()
                    if ext == '.csv':
                        encoding = utils.get_file_encoding(full_path)
                        df = pd.read_csv(full_path, engine='python', encoding=encoding)
                        if df is None or df.empty:
                            continue
                        for i, row in df.iterrows():
                            name = str(row.get('name', '') if not pd.isna(row.get('name', '')) else '')
                            base_id = str(row.get('base_id', '') if not pd.isna(row.get('base_id', '')) else '')
                            race = str(row.get('race', '') if not pd.isna(row.get('race', '')) else '')
                            key = f"{name}§{base_id}§{race}"
                            if key not in provenance:
                                provenance[key] = {}
                            provenance[key]['row'] = {'file': full_path, 'type': 'csv', 'index': int(i)}
                            bio_val = row.get('bio', None)
                            if bio_val is not None and not (isinstance(bio_val, float) and pd.isna(bio_val)) and str(bio_val) != '':
                                provenance[key]['bio'] = {'file': full_path, 'type': 'csv', 'index': int(i)}
                    elif ext == '.json':
                        with open(full_path, 'r', encoding='utf-8') as fp:
                            obj = json.load(fp)
                        items = obj if isinstance(obj, list) else [obj]
                        for idx, content in enumerate(items):
                            if not isinstance(content, dict):
                                continue
                            name = str(content.get('name', ''))
                            base_id = str(content.get('base_id', ''))
                            race = str(content.get('race', ''))
                            key = f"{name}§{base_id}§{race}"
                            if key not in provenance:
                                provenance[key] = {}
                            provenance[key]['row'] = {'file': full_path, 'type': 'json', 'index': int(idx), 'is_single_json': isinstance(obj, dict)}
                            bio_val = content.get('bio', None)
                            if bio_val is not None and str(bio_val) != '':
                                provenance[key]['bio'] = {'file': full_path, 'type': 'json', 'index': int(idx), 'is_single_json': isinstance(obj, dict)}
                except Exception as e:
                    logging.debug(f"Bio Editor: provenance scan failed for {full_path}: {e}")
            return provenance

        def _choose_default_personal_csv(user_csv_path: str | None) -> str:
            """Pick the target personal override file path.
            - If a directory is provided, use `<dir>/character_overrides.csv`.
            - If a file path is provided, preserve its extension; default to `.csv` if none.
            - If the file path has no directory, place it inside the personal override folder.
            - If nothing provided or any error occurs, default to `<personal>/character_overrides.csv`.
            """
            folder = _get_personal_override_dir()
            if user_csv_path:
                path = user_csv_path.strip()
                try:
                    # Directory input or trailing separator → default filename inside it
                    if path.endswith(os.sep) or os.path.isdir(path):
                        target_dir = path if os.path.isdir(path) else path.rstrip(os.sep)
                        if target_dir:
                            os.makedirs(target_dir, exist_ok=True)
                        return os.path.join(target_dir or folder, 'character_overrides.csv')
                    # Treat as file path
                    target_dir = os.path.dirname(path)
                    filename = os.path.basename(path)
                    if not target_dir:
                        target_dir = folder
                        final_path = os.path.join(target_dir, filename)
                    else:
                        final_path = path
                    if target_dir:
                        os.makedirs(target_dir, exist_ok=True)
                    # Preserve extension if provided; default to .csv
                    _, final_ext = os.path.splitext(final_path)
                    if not final_ext:
                        final_path = final_path + '.csv'
                    return final_path
                except Exception:
                    pass
            # Default fallback
            try:
                os.makedirs(folder, exist_ok=True)
            except Exception:
                pass
            return os.path.join(folder, 'character_overrides.csv')

        def _save_bio_to_user_path(label: str, bio_text: str, label_to_key: dict[str, str], user_csv_path: str | None, optional_values: dict[str, str | None], override_tags: str | None = None) -> str:
            key = label_to_key.get(label, '')
            if key == '':
                return ''
            name, base_id, race = _split_key(key)
            
            # Always save to user-defined path, ignoring provenance
            target_path = _choose_default_personal_csv(user_csv_path)
            
            try:
                # Determine file type based on extension
                filename, extension = os.path.splitext(target_path)
                ext = extension.lower()
                
                def _clean(v) -> str:
                    if v is None:
                        return ''
                    try:
                        if pd.isna(v):
                            return ''
                    except Exception:
                        pass
                    if not isinstance(v, str):
                        v = str(v)
                    return v.strip()
                
                def _append_csv(existing: str, incoming: str) -> str:
                    existing = _clean(existing)
                    incoming = _clean(incoming)
                    if not incoming:
                        return existing
                    if not existing:
                        return incoming
                    return f"{existing},{incoming}"
                
                if ext == '.json':
                    # Handle JSON file
                    if os.path.exists(target_path):
                        with open(target_path, 'r', encoding='utf-8') as fp:
                            try:
                                obj = json.load(fp)
                            except json.JSONDecodeError:
                                obj = []
                    else:
                        obj = []
                    
                    # Convert to list if single object
                    was_single = isinstance(obj, dict)
                    items = [obj] if was_single else obj if isinstance(obj, list) else []
                    
                    # Find and update existing entry or add new one
                    updated = False
                    for content in items:
                        if not isinstance(content, dict):
                            continue
                        if (str(content.get('name', '')) == name and 
                            str(content.get('base_id', '')) == base_id and 
                            str(content.get('race', '')) == race):
                            content['bio'] = bio_text
                            if optional_values.get('ref_id') is not None:
                                content['ref_id'] = optional_values['ref_id']
                            if optional_values.get('tags_overwrite') is not None:
                                content['tags_overwrite'] = optional_values['tags_overwrite']
                            # Write override tags from the tags editor when provided;
                            # otherwise keep existing `tags` unchanged.
                            if override_tags is not None:
                                content['tags'] = override_tags
                            elif 'tags' in content:
                                content['tags'] = content.get('tags', '')
                            updated = True
                            break
                    
                    if not updated:
                        # Add new entry at the end
                        new_entry = {'name': name, 'base_id': base_id, 'race': race, 'bio': bio_text}
                        if optional_values.get('ref_id') is not None:
                            new_entry['ref_id'] = optional_values['ref_id']
                        if optional_values.get('tags_overwrite') is not None:
                            new_entry['tags_overwrite'] = optional_values['tags_overwrite']
                        if override_tags is not None:
                            new_entry['tags'] = override_tags
                        elif optional_values.get('tags') is not None:
                            new_entry['tags'] = optional_values['tags']
                        items.append(new_entry)
                    
                    # Preserve single-object format only if it was originally single and remains single
                    to_write = items[0] if was_single and len(items) == 1 else items
                    
                    # Ensure directory exists (guard empty dirname)
                    _dir = os.path.dirname(target_path)
                    if _dir:
                        os.makedirs(_dir, exist_ok=True)
                    
                    with open(target_path, 'w', encoding='utf-8') as fp:
                        json.dump(to_write, fp, ensure_ascii=False, indent=2)
                    return target_path
                    
                else:
                    # Handle CSV file (default)
                    cols = ['name','base_id','race','bio']
                    if os.path.exists(target_path):
                        encoding = utils.get_file_encoding(target_path)
                        df = pd.read_csv(target_path, engine='python', encoding=encoding)
                    else:
                        df = pd.DataFrame(columns=cols)
                    
                    # Ensure required columns exist
                    for c in cols:
                        if c not in df.columns:
                            df[c] = ''
                    
                    # Handle optional columns in a generic way
                    # For each optional column, preserve it if it exists or add it if we have a value
                    for col_name, col_value in optional_values.items():
                        if col_name in df.columns:
                            # Column already exists, ensure it's preserved
                            pass
                        elif col_value is not None:
                            # Only add column if we have a value for it
                            df.insert(len(df.columns), col_name, '')
                    
                    # Find matching row
                    m = ((df['name'].fillna('').astype(str) == name) & 
                         (df['base_id'].fillna('').astype(str) == base_id) & 
                         (df['race'].fillna('').astype(str) == race))
                    
                    # Ensure `tags` column exists when we have override tags to write
                    if override_tags is not None and 'tags' not in df.columns:
                        df.insert(len(df.columns), 'tags', '')

                    if m.any():
                        # Update existing entry
                        df.loc[m, 'bio'] = bio_text
                        # Write override tags from the tags editor when provided
                        if override_tags is not None and 'tags' in df.columns:
                            df.loc[m, 'tags'] = override_tags
                        # Update optional columns only if we have new values, otherwise preserve existing
                        for col_name, col_value in optional_values.items():
                            if col_value is not None and col_name in df.columns:
                                if col_name == 'tags':
                                    # Tags are handled explicitly above via override_tags;
                                    # preserve existing value here.
                                    existing_val = df.loc[m, col_name].iloc[0]
                                    df.loc[m, col_name] = existing_val if override_tags is None else override_tags
                                else:
                                    df.loc[m, col_name] = col_value
                    else:
                        # Add new entry at the end
                        new_row = {'name': name, 'base_id': base_id, 'race': race, 'bio': bio_text}
                        if override_tags is not None:
                            new_row['tags'] = override_tags
                        # Add optional columns only if we have values for them
                        for col_name, col_value in optional_values.items():
                            if col_value is not None and col_name in df.columns:
                                if col_name == 'tags' and override_tags is not None:
                                    pass  # already handled above
                                else:
                                    new_row[col_name] = col_value
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    
                    # Ensure directory exists (guard empty dirname)
                    _dir = os.path.dirname(target_path)
                    if _dir:
                        os.makedirs(_dir, exist_ok=True)
                    
                    df.to_csv(target_path, index=False, encoding='utf-8')
                    return target_path
                    
            except Exception as e:
                logging.error(f"Bio Editor: failed to save to user-defined path '{target_path}': {e}")
                return ''

        def _build_labels_and_map(df: pd.DataFrame):
            if df is None or df.empty:
                return [], {}, {}
            labels: list[str] = []
            label_to_key: dict[str, str] = {}
            key_to_label: dict[str, str] = {}
            try:
                for _, row in df.iterrows():
                    name = str(row.get('name', ''))
                    base_id = str(row.get('base_id', ''))
                    race = str(row.get('race', ''))
                    label = f"{name} ({base_id}) — {race}"
                    key = f"{name}§{base_id}§{race}"
                    labels.append(label)
                    label_to_key[label] = key
                    key_to_label[key] = label
            except Exception as e:
                logging.error(f"Bio Editor: failed to build labels: {e}")
            return labels, label_to_key, key_to_label

        def _filter_labels(query: str, all_labels: list[str], limit: int = 200):
            if not query:
                return all_labels[:limit]
            q = query.lower()
            return [lbl for lbl in all_labels if q in lbl.lower()][:limit]

        def _split_key(value: str) -> tuple[str, str, str]:
            try:
                name, base_id, race = value.split('§', 2)
                return name, base_id, race
            except Exception:
                return "", "", ""

        def _key_from_label(label: str, label_to_key: dict[str, str]) -> str:
            return label_to_key.get(label, "")

        # --- Summary / private-thought file helpers (no heavy reloads) ---
        def _get_conversations_base_dir() -> str:
            return conversations_base_dir(config.save_folder, _get_game_folder_name())

        def _get_thoughts_base_dir() -> str:
            return thoughts_base_dir(config.save_folder, _get_game_folder_name())

        def _get_reflections_base_dir() -> str:
            return reflections_base_dir(config.save_folder, _get_game_folder_name())

        def _base_name_from_label(label: str, l2k: dict[str, str]) -> str:
            key = _key_from_label(label, l2k)
            if key == "":
                return ""
            name, _, _ = _split_key(key)
            return utils.remove_trailing_number(name)

        def _load_summary_for_label(label: str, l2k: dict[str, str], world_id: str) -> str:
            try:
                base_name = _base_name_from_label(label, l2k)
                if not base_name:
                    return ""
                return load_latest_text(_get_conversations_base_dir(), world_id, base_name, "summary")
            except Exception as e:
                logging.debug(f"Bio Editor: failed to load summary: {e}")
                return ""

        def _save_summary_for_label(label: str, summary_text: str, l2k: dict[str, str], world_id: str) -> str:
            try:
                base_name = _base_name_from_label(label, l2k)
                if not base_name:
                    return ""
                return save_latest_text(_get_conversations_base_dir(), world_id, base_name, "summary", summary_text)
            except Exception as e:
                logging.error(f"Bio Editor: failed to save summary: {e}")
                return ""

        def _load_thoughts_for_label(label: str, l2k: dict[str, str], world_id: str) -> str:
            try:
                base_name = _base_name_from_label(label, l2k)
                if not base_name:
                    return ""
                return load_latest_text(_get_thoughts_base_dir(), world_id, base_name, "thoughts")
            except Exception as e:
                logging.debug(f"Bio Editor: failed to load private thoughts: {e}")
                return ""

        def _save_thoughts_for_label(label: str, thoughts_text: str, l2k: dict[str, str], world_id: str) -> str:
            try:
                base_name = _base_name_from_label(label, l2k)
                if not base_name:
                    return ""
                return save_latest_text(_get_thoughts_base_dir(), world_id, base_name, "thoughts", thoughts_text)
            except Exception as e:
                logging.error(f"Bio Editor: failed to save private thoughts: {e}")
                return ""

        def _load_reflections_for_label(label: str, l2k: dict[str, str], world_id: str) -> str:
            try:
                base_name = _base_name_from_label(label, l2k)
                if not base_name:
                    return ""
                return load_latest_text(_get_reflections_base_dir(), world_id, base_name, "reflections")
            except Exception as e:
                logging.debug(f"Bio Editor: failed to load personal reflections: {e}")
                return ""

        def _save_reflections_for_label(label: str, reflections_text: str, l2k: dict[str, str], world_id: str) -> str:
            try:
                base_name = _base_name_from_label(label, l2k)
                if not base_name:
                    return ""
                return save_latest_text(_get_reflections_base_dir(), world_id, base_name, "reflections", reflections_text)
            except Exception as e:
                logging.error(f"Bio Editor: failed to save personal reflections: {e}")
                return ""

        def _load_override_tags_for_label(label: str, label_to_key: dict[str, str], user_csv_path: str | None) -> str:
            """Load only the override-portion of tags for a given NPC.

            This reads the personal override file (CSV or JSON) and returns the
            ``tags`` value stored there — *not* the merged runtime tags.
            """
            key = _key_from_label(label, label_to_key)
            if key == "":
                return ""
            name, base_id, race = _split_key(key)
            target_path = _choose_default_personal_csv(user_csv_path)
            try:
                if not target_path or not os.path.exists(target_path):
                    return ""
                _, ext = os.path.splitext(target_path)
                ext = ext.lower()
                if ext == '.json':
                    with open(target_path, 'r', encoding='utf-8') as fp:
                        obj = json.load(fp)
                    items = obj if isinstance(obj, list) else [obj]
                    for content in items:
                        if not isinstance(content, dict):
                            continue
                        if (str(content.get('name', '')).strip() == name and
                                str(content.get('base_id', '')).strip() == base_id and
                                str(content.get('race', '')).strip() == race):
                            raw = content.get('tags', '')
                            if raw is None:
                                return ""
                            return str(raw).strip()
                    return ""
                else:
                    if not os.path.exists(target_path):
                        return ""
                    enc = utils.get_file_encoding(target_path)
                    odf = pd.read_csv(target_path, engine='python', encoding=enc)
                    if odf is None or odf.empty:
                        return ""
                    if 'tags' not in odf.columns:
                        return ""
                    for c in ['name', 'base_id', 'race']:
                        if c not in odf.columns:
                            odf[c] = ''
                        odf[c] = odf[c].fillna('').astype(str)
                    m = ((odf['name'] == name) &
                         (odf['base_id'] == base_id) &
                         (odf['race'] == race))
                    if m.any():
                        val = odf.loc[m, 'tags'].iloc[0]
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            return ""
                        return str(val).strip()
                    return ""
            except Exception as e:
                logging.debug(f"Bio Editor: failed to load override tags: {e}")
                return ""

        def _compute_runtime_tags_for_label(label: str, label_to_key: dict[str, str]) -> str:
            """Compute the fully-merged runtime tags for an NPC (read-only).

            Walks the base CSV and all override files (mod + personal) in order,
            replicating the same append/overwrite semantics used by
            ``_refresh_runtime_tags_for_npc`` and ``Gameable.__apply_character_overrides``.

            Returns the effective tags string (``tags_overwrite`` if set, else
            the accumulated ``tags``).  Never modifies any state.
            """
            key = _key_from_label(label, label_to_key)
            if key == "":
                return ""
            name, base_id, race = _split_key(key)
            if not name and not base_id:
                return ""

            def _clean(v) -> str:
                if v is None:
                    return ""
                try:
                    if pd.isna(v):
                        return ""
                except Exception:
                    pass
                if not isinstance(v, str):
                    v = str(v)
                return v.strip()

            def _append_csv(existing: str, incoming: str) -> str:
                existing = _clean(existing)
                incoming = _clean(incoming)
                if not incoming:
                    return existing
                if not existing:
                    return incoming
                return f"{existing},{incoming}"

            try:
                # Step 1: base CSV tags
                base_csv = _get_base_csv_path()
                base_tags = ""
                try:
                    enc = utils.get_file_encoding(base_csv)
                    bdf = pd.read_csv(base_csv, engine='python', encoding=enc)
                    for c in ['name', 'base_id', 'race']:
                        if c not in bdf.columns:
                            bdf[c] = ''
                        bdf[c] = bdf[c].fillna('').astype(str).str.strip()
                    bm = (bdf['name'] == name) & (bdf['base_id'] == base_id) & (bdf['race'] == race)
                    if bm.any() and 'tags' in bdf.columns:
                        base_tags = _clean(bdf.loc[bm, 'tags'].iloc[0])
                except Exception:
                    pass

                # Step 2: walk overrides in order (same as Gameable.__apply_character_overrides)
                merged_tags = base_tags
                merged_tags_overwrite = ""
                try:
                    override_files = _list_override_files_in_order()
                    for fpath in override_files:
                        try:
                            _, ext = os.path.splitext(fpath)
                            ext = ext.lower()
                            if ext == '.csv':
                                enc2 = utils.get_file_encoding(fpath)
                                odf = pd.read_csv(fpath, engine='python', encoding=enc2)
                                if odf is None or odf.empty:
                                    continue
                                for c in ['name', 'base_id', 'race']:
                                    if c not in odf.columns:
                                        odf[c] = ''
                                    odf[c] = odf[c].fillna('').astype(str).str.strip()
                                om = (odf['name'] == name) & (odf['base_id'] == base_id) & (odf['race'] == race)
                                if om.any():
                                    if 'tags' in odf.columns:
                                        incoming_tags = _clean(odf.loc[om, 'tags'].iloc[0])
                                        if incoming_tags:
                                            merged_tags = _append_csv(merged_tags, incoming_tags)
                                    if 'tags_overwrite' in odf.columns:
                                        incoming_tw = _clean(odf.loc[om, 'tags_overwrite'].iloc[0])
                                        if incoming_tw:
                                            merged_tags_overwrite = incoming_tw
                            elif ext == '.json':
                                if os.path.getsize(fpath) == 0:
                                    continue
                                with open(fpath, 'r', encoding='utf-8') as fp:
                                    obj = json.load(fp)
                                items = obj if isinstance(obj, list) else [obj]
                                for content in items:
                                    if not isinstance(content, dict):
                                        continue
                                    if (str(content.get('name', '')).strip() == name and
                                            str(content.get('base_id', '')).strip() == base_id and
                                            str(content.get('race', '')).strip() == race):
                                        incoming_tags = _clean(content.get('tags', ''))
                                        if incoming_tags:
                                            merged_tags = _append_csv(merged_tags, incoming_tags)
                                        incoming_tw = _clean(content.get('tags_overwrite', ''))
                                        if incoming_tw:
                                            merged_tags_overwrite = incoming_tw
                        except Exception:
                            continue
                except Exception:
                    pass

                effective_tags = merged_tags_overwrite if merged_tags_overwrite else merged_tags
                return effective_tags
            except Exception as e:
                logging.debug(f"Bio Editor: runtime tags computation failed: {e}")
                return ""

        def _load_bio_for_label(label: str, df: pd.DataFrame, label_to_key: dict[str, str]) -> str:
            key = _key_from_label(label, label_to_key)
            if key == "":
                return ""
            name, base_id, race = _split_key(key)
            try:
                name_match = df['name'].fillna('').astype(str) == name
                base_id_match = df['base_id'].fillna('').astype(str) == base_id
                race_match = df['race'].fillna('').astype(str) == race
                view = df[name_match & base_id_match & race_match]
                if view.empty:
                    return ""
                bio = view.iloc[0].get('bio', '')
                return '' if pd.isna(bio) else str(bio)
            except Exception as e:
                logging.error(f"Bio Editor: failed to load bio: {e}")
                return ""

        def _save_bio_override_from_label(label: str, new_bio: str, label_to_key: dict[str, str]) -> str:
            key = _key_from_label(label, label_to_key)
            if key == "":
                return ""
            name, base_id, race = _split_key(key)
            override_dir = _get_personal_override_dir()
            os.makedirs(override_dir, exist_ok=True)
            csv_path = os.path.join(override_dir, 'mantella_bio_overrides.csv')
            cols = ['name','base_id','race','bio']
            try:
                if os.path.exists(csv_path):
                    df = pd.read_csv(csv_path, engine='python')
                else:
                    df = pd.DataFrame(columns=cols)
                for c in cols:
                    if c not in df.columns:
                        df[c] = ''
                name_match = df['name'].fillna('').astype(str) == name
                base_id_match = df['base_id'].fillna('').astype(str) == base_id
                race_match = df['race'].fillna('').astype(str) == race
                matcher = name_match & base_id_match & race_match
                if matcher.any():
                    df.loc[matcher, 'bio'] = new_bio
                else:
                    df.loc[len(df)] = {'name': name, 'base_id': base_id, 'race': race, 'bio': new_bio}
                df.to_csv(csv_path, index=False, encoding='utf-8')
                return csv_path
            except Exception as e:
                logging.error(f"Bio Editor: failed to save bio override: {e}")
                return ""

        # Initial data
        resolved_df = _get_resolved_character_df()
        labels, label_to_key, key_to_label = _build_labels_and_map(resolved_df)

        with gr.Column():
            state_df = gr.State(value=resolved_df)
            state_labels = gr.State(value=labels)
            state_label_to_key = gr.State(value=label_to_key)
            state_key_to_label = gr.State(value=key_to_label)
            # Remember chosen world id for summaries
            initial_world_id = pick_world_id(_get_conversations_base_dir())
            state_world_id = gr.State(value=initial_world_id)
            _default_override_target = os.path.join(_get_personal_override_dir(), 'character_overrides.csv').replace('\\','/')
            override_csv_path = gr.Text(
                value=config.definitions.get_string_value("bio_override_csv_path"),
                label="Override path (CSV or JSON, optional)",
                placeholder=f"Default: {_default_override_target}",
                visible=True
            )
            _personal_override_dir = _get_personal_override_dir().replace('\\','/')
            _mod_override_dir = os.path.join(
                config.mod_path_base,
                'SKSE' if config.game.base_game != GameEnum.FALLOUT4 else 'F4SE',
                'Plugins','MantellaSoftware','data', _get_game_folder_name(), 'character_overrides'
            ).replace('\\','/')
            with gr.Accordion(label="Override path details", open=False):
                gr.Markdown(
                    value=(
                        f"**What this path does**\n\n"
                        "- Sets where the Bio Editor writes your saved bios (CSV or JSON).\n"
                        "- Also used by the Refresh bios button: the file at this path is merged on top of all other sources.\n\n"
                        f"**If left empty:** saves to `{_default_override_target}`.\n\n"
                        "**Accepted inputs**\n"
                        "- File path to the CSV or JSON file.\n"
                        "- Folder path → writes `character_overrides.csv` inside that folder.\n"
                        "- File path without extension → `.csv` is added.\n"
                        "- File path ending with `.json` → writes JSON instead of CSV.\n\n"
                        f"**Where the game auto-loads overrides from**\n"
                        f"- Personal overrides: `{_personal_override_dir}`\n"
                        f"- Mod overrides: `{_mod_override_dir}`\n\n"
                        "Saves also update the in-memory cache, so new conversations use the updated bio immediately."
                    )
                )

            with gr.Accordion(label="Bio Editor", open=True):
                gr.Markdown("Manually edit character bios, conversation summaries, private thoughts, and personal reflections. Select an NPC from the dropdown, modify their bio, summary, thoughts, or reflections, and save your changes.")
                npc_dropdown = gr.Dropdown(choices=labels, label="NPC", multiselect=False, allow_custom_value=False)
                bio_editor = gr.Text(value="", lines=12, label="Bio")
                tags_editor = gr.Text(value="", lines=2, label='Tags ("tags" column in override csv file only)', placeholder="Comma-separated tags from your personal override file")
                runtime_tags_display = gr.Text(value="", lines=2, label="Runtime Tags (read-only, all sources merged)", interactive=False, placeholder="Select an NPC to see its effective runtime tags")
                
                info_line = gr.Markdown(value="", visible=True)
                # Optional: user-chosen path for base-only NPCs; persisted in hidden config key
                with gr.Row():
                    save_btn = gr.Button("Save", variant="primary", interactive=False)
                    refresh_btn = gr.Button("Refresh bios", variant="secondary")
                
                summary_editor = gr.Text(value="", lines=12, label="Summary")
                with gr.Row():
                    save_summary_btn = gr.Button("Save Summary", variant="primary", interactive=False)
                    refresh_summaries_btn = gr.Button("Refresh summaries", variant="secondary")

                thoughts_editor = gr.Text(value="", lines=12, label="Private thoughts")
                with gr.Row():
                    save_thoughts_btn = gr.Button("Save Thoughts", variant="primary", interactive=False)
                    refresh_thoughts_btn = gr.Button("Refresh thoughts", variant="secondary")

                reflections_editor = gr.Text(value="", lines=12, label="Personal Reflection")
                with gr.Row():
                    save_reflections_btn = gr.Button("Save Reflection", variant="primary", interactive=False)
                    refresh_reflections_btn = gr.Button("Refresh reflection", variant="secondary")
                    generate_reflection_btn = gr.Button("Generate Reflection", variant="primary", interactive=False)

            # --- LLM Request section ---
            with gr.Accordion(label="Bio Editor – LLM Request", open=True):
                gr.Markdown("Use AI to generate or enhance character bios. Configure prompts, select an LLM service and model, then send requests to generate new bio content based on existing character information.")
                # Prompt profiles UI
                try:
                    _profiles_json = config.definitions.get_string_value("bio_prompt_profiles") or "{}"
                    _profiles_dict = json.loads(_profiles_json)
                    if not isinstance(_profiles_dict, dict):
                        _profiles_dict = {}
                except Exception:
                    _profiles_dict = {}
                _selected_prompt_name = config.definitions.get_string_value("bio_prompt_selected") or ""
                prompt_names = sorted(list(_profiles_dict.keys())) if _profiles_dict else []
                with gr.Row():
                    prompt_selector = gr.Dropdown(choices=prompt_names, value=_selected_prompt_name if _selected_prompt_name in prompt_names else None, label="Prompt profile", multiselect=False, allow_custom_value=False)
                    new_prompt_name = gr.Text(value="", label="New prompt name", max_lines=1)
                    save_prompt_btn = gr.Button("Save prompt", variant="primary")
                    delete_prompt_btn = gr.Button("Delete prompt", variant="secondary")
                prompt_editor = gr.Text(value=_profiles_dict.get(_selected_prompt_name, ""), lines=8, label="Prompt (supports {bio}, {summary}, {player_description}, and {conversation_history})")
                params_editor = gr.Text(value=json.dumps({"max_tokens": 250}, indent=2), lines=6, label="Parameters (JSON)")
                with gr.Row():
                    service_dropdown = gr.Dropdown(
                        choices=["OpenRouter", "OpenAI", "NanoGPT", "KoboldCpp", "textgenwebui"],
                        value=config.definitions.get_string_value("bio_llm_api") or config.llm_api,
                        multiselect=False,
                        allow_custom_value=True,
                        label="LLM Service"
                    )
                    # Build initial model dropdown mirroring LLM tab logic
                    try:
                        from src.llm.key_file_resolver import key_file_resolver as _kfr
                        _service = config.definitions.get_string_value("bio_llm_api") or config.llm_api
                        _skf = _kfr.get_key_files_for_service(_service, 'GPT_SECRET_KEY.txt')
                        _skf0 = _skf[0] if _skf else 'GPT_SECRET_KEY.txt'
                        _model_list = ClientBase.get_model_list(_service, _skf0, 'google/gemma-2-9b-it:free', False)
                        _initial_model = config.definitions.get_string_value("bio_llm_model") or config.llm
                        _selected_model = _initial_model if _model_list.is_model_in_list(_initial_model) else _model_list.default_model
                    except Exception:
                        _model_list = ClientBase.get_model_list("OpenRouter", 'GPT_SECRET_KEY.txt', 'google/gemma-2-9b-it:free', False)
                        _selected_model = _model_list.default_model
                    model_dropdown = gr.Dropdown(
                        value=_selected_model,
                        choices=_model_list.available_models,
                        multiselect=False,
                        allow_custom_value=_model_list.allows_manual_model_input,
                        label="Model"
                    )
                    update_models_btn = gr.Button("Update models", variant="secondary")
                with gr.Row():
                    apply_profile_checkbox = gr.Checkbox(value=config.definitions.get_bool_value("bio_llm_apply_profile"), label="Apply model profile for this request")
                    omit_stop_checkbox = gr.Checkbox(value=config.definitions.get_bool_value("bio_llm_omit_stop"), label="Remove stop sequences from this request")
                    temp_override = gr.Number(value=config.definitions.get_float_value("bio_llm_temperature_override"), label="Temperature override (-1 to ignore)", precision=2)
                    max_tokens_override = gr.Number(value=config.definitions.get_int_value("bio_llm_max_tokens_override"), label="Max tokens override (-1 to ignore)", precision=0)
                send_request_btn = gr.Button("Send Request", variant="primary")
                llm_response_editor = gr.Text(value="", lines=12, label="LLM Response")
                with gr.Row():
                    save_from_llm_btn = gr.Button("Save Bio (from LLM response)", variant="primary", interactive=False)
                    refresh_llm_btn = gr.Button("Refresh bios", variant="secondary")
                llm_info_line = gr.Markdown(value="", visible=True)

            def on_select(label: str, df: pd.DataFrame, l2k: dict[str, str], world_id: str, user_csv: str):
                # Clear info and load bio + override tags; enable save when selection exists
                bio = _load_bio_for_label(label, df, l2k)
                summary = _load_summary_for_label(label, l2k, world_id)
                thoughts = _load_thoughts_for_label(label, l2k, world_id)
                reflections = _load_reflections_for_label(label, l2k, world_id)
                override_tags = _load_override_tags_for_label(label, l2k, user_csv)
                runtime_tags = _compute_runtime_tags_for_label(label, l2k)
                can_save = bool(label)
                return bio, summary, thoughts, reflections, override_tags, runtime_tags, "", gr.Button(interactive=can_save), gr.Button(interactive=can_save), gr.Button(interactive=can_save), gr.Button(interactive=can_save), gr.Button(interactive=can_save)

            def on_save(label: str, bio_text: str, tags_text: str, l2k: dict[str, str], k2l: dict[str, str], user_csv: str):
                # Try to infer optional column values from current df row, if present
                optional_values = {}
                try:
                    key = l2k.get(label, '')
                    n, b, r = _split_key(key)
                    if n and b:
                        rowmask = (state_df.value['name'].fillna('').astype(str) == n) & \
                                  (state_df.value['base_id'].fillna('').astype(str) == b) & \
                                  (state_df.value['race'].fillna('').astype(str) == r)
                        if rowmask.any():
                            row0 = state_df.value.loc[rowmask].iloc[0]
                            
                            # Get all columns that are not the required ones
                            required_columns = {'name', 'base_id', 'race', 'bio'}
                            optional_columns = [col for col in row0.index if col not in required_columns]
                            
                            # Handle each optional column dynamically
                            for col_name in optional_columns:
                                col_value = row0.get(col_name, '')
                                # Check if the value is NaN before converting to string
                                if pd.isna(col_value):
                                    optional_values[col_name] = None
                                else:
                                    optional_values[col_name] = str(col_value)
                except Exception:
                    pass
                # The tags editor always shows the override-only portion.
                # Pass it explicitly so _save_bio_to_user_path writes it
                # to the override file's `tags` column.
                override_tags = tags_text.strip() if isinstance(tags_text, str) else None
                path = _save_bio_to_user_path(label, bio_text, l2k, user_csv, optional_values, override_tags=override_tags)
                # Fast refresh: avoid heavy reload when game isn't running
                new_df = state_df.value if isinstance(state_df.value, pd.DataFrame) else _get_resolved_character_df()
                # Apply the saved bio into in-memory df for immediate UI feedback
                try:
                    key = l2k.get(label, '')
                    name, base_id, race = _split_key(key)
                    if name and base_id:
                        mask = (new_df['name'].fillna('').astype(str) == name) & \
                               (new_df['base_id'].fillna('').astype(str) == base_id) & \
                               (new_df['race'].fillna('').astype(str) == race)
                        if mask.any():
                            new_df.loc[mask, 'bio'] = bio_text
                        else:
                            # If row doesn't exist (override-only), append minimal row
                            new_row = {'name': name, 'base_id': base_id, 'race': race, 'bio': bio_text}
                            new_df = pd.concat([new_df, pd.DataFrame([new_row])], ignore_index=True)
                        # Persist to hidden config so it survives restarts
                        try:
                            if user_csv is not None and user_csv != config.definitions.get_string_value("bio_override_csv_path"):
                                cv = config.definitions.get_config_value_definition("bio_override_csv_path")
                                cv.value = user_csv
                                try:
                                    config._ConfigLoader__write_config_state(config.definitions)
                                except Exception:
                                    pass
                                config.update_config_loader_with_changed_config_values()
                        except Exception:
                            pass
                except Exception as e:
                    logging.debug(f"Bio Editor: in-memory update failed: {e}")
                # Also update runtime bio for active conversation if possible
                try:
                    key_for_runtime = l2k.get(label, '')
                    rn, rb, rr = _split_key(key_for_runtime)
                    if rn and rb:
                        _update_runtime_bio_if_possible(rn, rb, rr, bio_text)
                except Exception as e:
                    logging.debug(f"Bio Editor: runtime update after manual save failed: {e}")
                # Update cached game DataFrame (bio + tags) for future conversations
                try:
                    key_for_cached = l2k.get(label, '')
                    cn, cb, cr = _split_key(key_for_cached)
                    if cn and cb:
                        _update_cached_game_df_if_possible(cn, cb, cr, bio_text)
                        # Refresh runtime tags for this NPC so the next conversation
                        # picks up the new combined tags without a full reload.
                        if override_tags is not None:
                            _refresh_runtime_tags_for_npc(cn, cb, cr, override_tags)
                except Exception as e:
                    logging.debug(f"Bio Editor: cached df update after manual save failed: {e}")
                new_labels, new_l2k, new_k2l = _build_labels_and_map(new_df)
                # Preserve selection by key
                current_key = l2k.get(label, '')
                keep_label = new_k2l.get(current_key, None) if current_key else None
                info = f"Saved to: {path}" if path else "Save failed. Check logs."
                return (
                    info,
                    new_df,
                    new_labels,
                    new_l2k,
                    new_k2l,
                    gr.Dropdown(choices=new_labels, value=keep_label)
                )

            def on_user_csv_change(user_csv: str):
                try:
                    cv = config.definitions.get_config_value_definition("bio_override_csv_path")
                    if user_csv is None:
                        user_csv = ""
                    if user_csv != cv.value:
                        cv.value = user_csv
                        try:
                            config._ConfigLoader__write_config_state(config.definitions)
                        except Exception:
                            pass
                        config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass

            def on_refresh(user_csv_path: str = ""):
                # Rebuild from disk
                new_df = _get_resolved_character_df()
                # Apply user-selected override path on top if provided
                try:
                    if user_csv_path and isinstance(user_csv_path, str):
                        # Avoid duplicate apply if it's already in personal overrides, but harmless if applied twice
                        new_df = _apply_override_file_to_df(new_df, user_csv_path)
                except Exception:
                    pass
                new_labels, new_l2k, new_k2l = _build_labels_and_map(new_df)
                # Clear selection and editor (including tags + runtime tags), disable save
                return (
                    "Bios refreshed.",
                    new_df,
                    new_labels,
                    new_l2k,
                    new_k2l,
                    gr.Dropdown(choices=new_labels, value=None),
                    gr.Text(value=""),
                    gr.Text(value=""),
                    gr.Text(value=""),
                    gr.Button(interactive=False)
                )

            def on_refresh_memory(label: str, l2k: dict[str, str], world_id: str):
                summary = _load_summary_for_label(label, l2k, world_id)
                thoughts = _load_thoughts_for_label(label, l2k, world_id)
                reflections = _load_reflections_for_label(label, l2k, world_id)
                can_save = bool(label)
                return (
                    "Summaries, thoughts, and reflection refreshed.",
                    summary,
                    thoughts,
                    reflections,
                    gr.Button(interactive=can_save),
                    gr.Button(interactive=can_save),
                    gr.Button(interactive=can_save),
                    gr.Button(interactive=can_save),
                )
            # Prompt profiles handlers
            def _get_profiles_state():
                try:
                    raw = config.definitions.get_string_value("bio_prompt_profiles") or "{}"
                    data = json.loads(raw)
                    return data if isinstance(data, dict) else {}
                except Exception:
                    return {}

            def save_prompt_profile(current_text: str, new_name: str, selected_name: str) -> tuple[str, gr.Dropdown, gr.Text]:
                # If no new name provided, overwrite the currently selected profile
                target_name = (new_name or selected_name or "").strip()
                if target_name == "":
                    # Keep selection unchanged
                    return (
                        "Enter a prompt name or select a profile to overwrite.",
                        gr.Dropdown(choices=prompt_selector.choices, value=prompt_selector.value),
                        gr.Text(value=new_name)
                    )
                profiles = _get_profiles_state()
                profiles[target_name] = current_text or ""
                try:
                    cvp = config.definitions.get_config_value_definition("bio_prompt_profiles")
                    cvp.value = json.dumps(profiles, indent=2)
                    cvs = config.definitions.get_config_value_definition("bio_prompt_selected")
                    cvs.value = target_name
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass
                names = sorted(list(profiles.keys()))
                # Select the saved profile and clear the new-name field to avoid accidental switches
                return (
                    f"Prompt '{target_name}' saved.",
                    gr.Dropdown(choices=names, value=target_name, label="Prompt profile"),
                    gr.Text(value="")
                )

            def apply_selected_prompt(name: str) -> tuple[str, gr.Button]:
                profiles = _get_profiles_state()
                text = profiles.get(name or "", "")
                try:
                    cvs = config.definitions.get_config_value_definition("bio_prompt_selected")
                    cvs.value = name or ""
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass
                return text, gr.Button(interactive=True)

            def delete_prompt_profile(name: str) -> tuple[str, gr.Dropdown, gr.Text, gr.Text]:
                profiles = _get_profiles_state()
                if name in profiles:
                    try:
                        del profiles[name]
                        cvp = config.definitions.get_config_value_definition("bio_prompt_profiles")
                        cvp.value = json.dumps(profiles, indent=2)
                        cvs = config.definitions.get_config_value_definition("bio_prompt_selected")
                        cvs.value = ""
                        try:
                            config._ConfigLoader__write_config_state(config.definitions)
                        except Exception:
                            pass
                        config.update_config_loader_with_changed_config_values()
                    except Exception:
                        pass
                names = sorted(list(profiles.keys()))
                return "Prompt deleted.", gr.Dropdown(choices=names, value=None, label="Prompt profile"), gr.Text(value=""), gr.Text(value="")


            def on_save_summary(label: str, summary_text: str, l2k: dict[str, str], world_id: str):
                path = _save_summary_for_label(label, summary_text, l2k, world_id)
                info = f"Summary saved to: {path}" if path else "Summary save failed. Check logs."
                return info

            def on_save_thoughts(label: str, thoughts_text: str, l2k: dict[str, str], world_id: str):
                path = _save_thoughts_for_label(label, thoughts_text, l2k, world_id)
                info = f"Thoughts saved to: {path}" if path else "Thoughts save failed. Check logs."
                return info

            def on_save_reflections(label: str, reflections_text: str, l2k: dict[str, str], world_id: str):
                path = _save_reflections_for_label(label, reflections_text, l2k, world_id)
                info = f"Personal reflection saved to: {path}" if path else "Personal reflection save failed. Check logs."
                return info

            def on_generate_reflection(label: str, bio_text: str, summary_text: str, l2k: dict[str, str], world_id: str):
                if not label:
                    return "Select an NPC first.", "", gr.Button(interactive=False), gr.Button(interactive=False)
                if not (summary_text or "").strip():
                    return "Personal reflection not generated. This NPC has no summaries.", _load_reflections_for_label(label, l2k, world_id), gr.Button(interactive=True), gr.Button(interactive=True)
                npc_name = _base_name_from_label(label, l2k)
                if not npc_name:
                    return "Could not resolve NPC name.", "", gr.Button(interactive=False), gr.Button(interactive=False)
                try:
                    from src.game_manager import GameStateManager
                    from src.llm.key_file_resolver import key_file_resolver as _kfr
                    from src.remember.personal_reflection import PersonalReflection
                    from src.ui import settings_ui_constructor as sui

                    gm_ref = getattr(sui, "_game_manager_ref", None)
                    try:
                        config.sync_summary_llm_settings_from_definitions()
                        config.sync_bio_section_filter_settings_from_definitions()
                        config.sync_prompt_values_from_definitions()
                        config.enable_character_tag_reading = config.definitions.get_bool_value("enable_character_tag_reading")
                    except Exception:
                        pass

                    summary_client = GameStateManager.create_reflection_client(
                        config, "GPT_SECRET_KEY.txt", GameStateManager.create_summary_client(config, "GPT_SECRET_KEY.txt"))
                    if summary_client is None:
                        skf = _kfr.get_key_files_for_service(config.llm_api, "GPT_SECRET_KEY.txt")
                        summary_client = ClientBase(
                            config.llm_api,
                            config.llm,
                            config.llm_params,
                            config.custom_token_count,
                            skf,
                            response_timeout=config.llm_response_timeout,
                        )
                    language_name = getattr(config, "language", "English") or "English"
                    player_name = "the player"
                    try:
                        if gm_ref and getattr(gm_ref, "_GameStateManager__talk", None):
                            talk = gm_ref._GameStateManager__talk
                            player = talk.context.npcs_in_conversation.get_player_character()
                            if player and player.name:
                                player_name = player.name
                    except Exception:
                        pass
                    manager = PersonalReflection(
                        getattr(gm_ref, "game", None) if gm_ref else None,
                        config,
                        summary_client,
                        language_name,
                        summary_client,
                        reflections_folder_path=_get_reflections_base_dir(),
                    )
                    result = manager.save_for_named_npc(
                        npc_name,
                        bio_text or "",
                        summary_text or "",
                        world_id or "default",
                        player_name=player_name,
                        tags=_compute_runtime_tags_for_label(label, l2k),
                    )
                    updated = _load_reflections_for_label(label, l2k, world_id)
                    if result:
                        return "Personal reflection generated and appended.", updated, gr.Button(interactive=True), gr.Button(interactive=True)
                    return "Personal reflection generation failed. Check the log.", updated, gr.Button(interactive=True), gr.Button(interactive=True)
                except Exception as e:
                    logging.error(f"Bio Editor: failed to generate personal reflection: {e}", exc_info=True)
                    return f"Personal reflection generation failed: {e}", _load_reflections_for_label(label, l2k, world_id), gr.Button(interactive=True), gr.Button(interactive=True)

            # --- LLM helper handlers ---
            def _render_prompt_text(template_text: str, bio_text: str, summary_text: str, player_description: str = "", conversation_history: str = "") -> str:
                """Render variables inside the prompt template.
                Supports {bio}, {summary}, {player_description}, and {conversation_history} (case-insensitive, allows whitespace inside braces).
                {conversation_history} is only available when there's an active conversation.
                """
                def repl(match: re.Match) -> str:
                    key = match.group(1).strip().lower()
                    if key == "bio":
                        return bio_text or ""
                    if key == "summary":
                        return summary_text or ""
                    if key == "player_description":
                        return player_description or ""
                    if key == "conversation_history":
                        return conversation_history or ""
                    return match.group(0)

                pattern = re.compile(r"\{\s*(bio|summary|player_description|conversation_history)\s*\}", re.IGNORECASE)
                return pattern.sub(repl, template_text or "")

            def update_model_list_for_service(service_value: str) -> gr.Dropdown:
                try:
                    from src.llm.key_file_resolver import key_file_resolver as _kfr
                    skf = _kfr.get_key_files_for_service(service_value, 'GPT_SECRET_KEY.txt')
                    skf0 = skf[0] if skf else 'GPT_SECRET_KEY.txt'
                    ml = ClientBase.get_model_list(service_value, skf0, 'google/gemma-2-9b-it:free', False)
                    # prefer saved bio_llm_model when available
                    saved_model = config.definitions.get_string_value("bio_llm_model") or config.llm
                    sel = saved_model if ml.is_model_in_list(saved_model) else (model_dropdown.value if hasattr(model_dropdown, 'value') and ml.is_model_in_list(model_dropdown.value) else ml.default_model)
                    if not ml.is_model_in_list(sel):
                        sel = ml.default_model
                    return gr.Dropdown(value=sel, choices=ml.available_models, multiselect=False, allow_custom_value=ml.allows_manual_model_input, label="Model")
                except Exception as e:
                    logging.error(f"LLM model list update failed: {e}")
                    ml = ClientBase.get_model_list("OpenRouter", 'GPT_SECRET_KEY.txt', 'google/gemma-2-9b-it:free', False)
                    return gr.Dropdown(value=ml.default_model, choices=ml.available_models, multiselect=False, allow_custom_value=ml.allows_manual_model_input, label="Model")

            def on_send_llm_request(label: str, df: pd.DataFrame, l2k: dict[str, str], world_id: str, raw_prompt: str, bio_text_ui: str, summary_text_ui: str, params_text: str, apply_profile: bool, omit_stop: bool, temp_ovr: float, max_tokens_ovr: int, srv: str, mdl: str):
                # Resolve variables from current selection
                try:
                    # Always reload latest bio from df for the selected label
                    current_summary = summary_text_ui or ""
                    if label:
                        current_bio = _load_bio_for_label(label, df, l2k) or ""
                        if not current_summary:
                            current_summary = _load_summary_for_label(label, l2k, world_id) or ""
                    else:
                        current_bio = ""

                    # Get conversation history if there's an active conversation
                    current_conversation_history = ""
                    try:
                        from src.ui import settings_ui_constructor as sui
                        gm = getattr(sui, '_game_manager_ref', None)
                        if gm and hasattr(gm, '_GameStateManager__talk') and gm._GameStateManager__talk:
                            # Get talk-only messages to avoid system prompts
                            talk_messages = gm._GameStateManager__talk._Conversation__messages.get_talk_only(include_system_generated_messages=False)
                            if talk_messages:
                                from src.llm.message_thread import message_thread
                                current_conversation_history = message_thread.transform_to_text(talk_messages).strip()
                    except Exception as e:
                        logging.debug(f"Bio Editor: Could not retrieve conversation history: {e}")

                    final_prompt = _render_prompt_text(raw_prompt or "", current_bio, current_summary, config.player_character_description, current_conversation_history)
                    # Parse per-request params; ignore profile system, use only this
                    params_override = None
                    if params_text and params_text.strip():
                        try:
                            params_override = json.loads(params_text)
                            if not isinstance(params_override, dict):
                                params_override = None
                                logging.error("LLM parameters must be a JSON object.")
                        except Exception as e:
                            logging.error(f"LLM parameters JSON parse error: {e}")
                    # Apply model profile optionally on top of params_override
                    if apply_profile:
                        try:
                            from src.model_profile_manager import ModelProfileManager
                            pm = ModelProfileManager()
                            profile_params = pm.apply_profile_to_params(srv, mdl, params_override or {})
                            params_override = profile_params
                        except Exception as e:
                            logging.error(f"Error applying model profile: {e}")
                    # Apply on-the-fly overrides for temperature and max_tokens
                    if params_override is None:
                        params_override = {}
                    try:
                        if isinstance(temp_ovr, (int, float)) and float(temp_ovr) >= 0:
                            params_override["temperature"] = float(temp_ovr)
                    except Exception:
                        pass
                    try:
                        if isinstance(max_tokens_ovr, (int, float)) and int(max_tokens_ovr) > 0:
                            params_override["max_tokens"] = int(max_tokens_ovr)
                    except Exception:
                        pass
                    if omit_stop:
                        params_override.pop("stop", None)
                    requester = BioLLMRequester(config)
                    reply = requester.send(srv, mdl, final_prompt, params_override=params_override)
                    if reply:
                        try:
                            logging.log(23, f"LLM response (Bio Editor): {reply.strip()}")
                        except Exception:
                            logging.info("LLM response (Bio Editor) logged")
                    info = "LLM reply received." if reply else "No reply from LLM. Check logs."
                    return info, (reply or ""), gr.Button(interactive=bool(reply))
                except Exception as e:
                    logging.error(f"LLM request failed: {e}")
                    return "LLM request failed. Check logs.", "", gr.Button(interactive=False)

            def _update_runtime_bio_if_possible(name: str, base_id: str, race: str, new_bio: str):
                try:
                    from src.ui import settings_ui_constructor as sui
                    gm = getattr(sui, '_game_manager_ref', None)
                    if not gm:
                        return
                    talk = getattr(gm, '_GameStateManager__talk', None)
                    if not talk or not hasattr(talk, 'context'):
                        return
                    def _normalize_id(val: str) -> str:
                        try:
                            s = str(val or "").upper()
                        except Exception:
                            s = str(val) if val is not None else ""
                        if s.startswith('FE'):
                            return s[-3:].rjust(6, "0")
                        return s[-6:]
                    try:
                        characters = talk.context.npcs_in_conversation.get_all_characters()
                    except Exception:
                        characters = []
                    # First filter by base_id
                    try:
                        base_matches = [ch for ch in characters if _normalize_id(getattr(ch, 'base_id', "")) == _normalize_id(base_id)]
                    except Exception:
                        base_matches = []
                    candidates = base_matches
                    # If multiple remain, refine with name/race where possible
                    try:
                        if len(candidates) > 1:
                            refined = [ch for ch in candidates if (not name or str(getattr(ch, 'name', "")) == str(name)) and (not race or str(getattr(ch, 'race', "")) == str(race))]
                            if refined:
                                candidates = refined
                    except Exception:
                        pass
                    for ch in candidates:
                        try:
                            ch.bio = new_bio or ""
                        except Exception:
                            continue
                except Exception as e:
                    logging.debug(f"Bio Editor: runtime bio update skipped: {e}")

            def _update_cached_game_df_if_possible(name: str, base_id: str, race: str, new_bio: str):
                try:
                    from src.ui import settings_ui_constructor as sui
                    gm = getattr(sui, '_game_manager_ref', None)
                    if not gm or not hasattr(gm, 'game') or gm.game is None:
                        return
                    gdf = gm.game.character_df
                    if gdf is None:
                        return
                    # Ensure required columns
                    for c in ['name','base_id','race','bio']:
                        if c not in gdf.columns:
                            gdf[c] = ''
                    # Try exact match first
                    try:
                        exact_mask = (
                            gdf['name'].fillna('').astype(str) == str(name)
                        ) & (
                            gdf['base_id'].fillna('').astype(str) == str(base_id)
                        ) & (
                            gdf['race'].fillna('').astype(str) == str(race)
                        )
                    except Exception:
                        exact_mask = None
                    updated = False
                    if isinstance(exact_mask, pd.Series) and exact_mask.any():
                        gdf.loc[exact_mask, 'bio'] = new_bio
                        updated = True
                    else:
                        # Fallback: normalize base_id to last 6 (strip plugin ID) and compare case-insensitive
                        try:
                            def _norm_id_series(s: pd.Series) -> pd.Series:
                                ss = s.fillna('').astype(str).str.upper()
                                # Remove FE prefix handling by taking last 6 chars
                                return ss.apply(lambda v: (v[-3:].rjust(6, '0') if v.startswith('FE') else v[-6:]))
                            df_norm = _norm_id_series(gdf['base_id'])
                            target_norm = (str(base_id or '').upper())
                            target_norm = (target_norm[-3:].rjust(6,'0') if target_norm.startswith('FE') else target_norm[-6:])
                            id_mask = df_norm == target_norm
                        except Exception:
                            id_mask = None
                        if isinstance(id_mask, pd.Series) and id_mask.any():
                            # If multiple rows, prefer those matching name/race
                            try:
                                name_mask = gdf['name'].fillna('').astype(str) == str(name)
                                race_mask = gdf['race'].fillna('').astype(str) == str(race)
                                refined = id_mask & name_mask & race_mask
                                if refined.any():
                                    gdf.loc[refined, 'bio'] = new_bio
                                    updated = True
                                else:
                                    gdf.loc[id_mask, 'bio'] = new_bio
                                    updated = True
                            except Exception:
                                gdf.loc[id_mask, 'bio'] = new_bio
                                updated = True
                    if not updated:
                        # Append minimal row so new conversations can find it
                        try:
                            gdf.loc[len(gdf)] = {
                                'name': str(name),
                                'base_id': str(base_id),
                                'race': str(race),
                                'bio': new_bio
                            }
                        except Exception:
                            pass
                except Exception as e:
                    logging.debug(f"Bio Editor: cached game df update skipped: {e}")

            def _refresh_runtime_tags_for_npc(name: str, base_id: str, race: str, new_override_tags: str):
                """Recompute the merged runtime `tags` column for a single NPC.

                After saving override tags from the Bio Editor, this function:
                1. Reads the base CSV tags for the NPC.
                2. Reads all override files in order (mod then personal) and
                   appends their `tags` values, matching Gameable's append
                   semantics.
                3. Writes the recomputed merged tags into ``gm.game.character_df``
                   so subsequent conversations pick up the change.
                4. If the NPC is currently in an active conversation, re-expands
                   their bio with the new effective tags and updates the
                   ``Character.bio`` attribute in place.
                """
                try:
                    from src.ui import settings_ui_constructor as sui
                    gm = getattr(sui, '_game_manager_ref', None)
                    if not gm or not hasattr(gm, 'game') or gm.game is None:
                        return
                    gdf = gm.game.character_df
                    if gdf is None:
                        return

                    def _clean(v) -> str:
                        if v is None:
                            return ""
                        try:
                            if pd.isna(v):
                                return ""
                        except Exception:
                            pass
                        if not isinstance(v, str):
                            v = str(v)
                        return v.strip()

                    def _append_csv(existing: str, incoming: str) -> str:
                        existing = _clean(existing)
                        incoming = _clean(incoming)
                        if not incoming:
                            return existing
                        if not existing:
                            return incoming
                        return f"{existing},{incoming}"

                    # --- Step 1: base CSV tags ---
                    base_csv = _get_base_csv_path()
                    base_tags = ""
                    try:
                        enc = utils.get_file_encoding(base_csv)
                        bdf = pd.read_csv(base_csv, engine='python', encoding=enc)
                        for c in ['name', 'base_id', 'race']:
                            if c not in bdf.columns:
                                bdf[c] = ''
                            bdf[c] = bdf[c].fillna('').astype(str).str.strip()
                        bm = (bdf['name'] == name) & (bdf['base_id'] == base_id) & (bdf['race'] == race)
                        if bm.any() and 'tags' in bdf.columns:
                            base_tags = _clean(bdf.loc[bm, 'tags'].iloc[0])
                    except Exception:
                        pass

                    # --- Step 2: walk overrides in order (same as Gameable.__apply_character_overrides) ---
                    merged_tags = base_tags
                    merged_tags_overwrite = ""
                    try:
                        override_files = _list_override_files_in_order()
                        for fpath in override_files:
                            try:
                                _, ext = os.path.splitext(fpath)
                                ext = ext.lower()
                                if ext == '.csv':
                                    enc2 = utils.get_file_encoding(fpath)
                                    odf = pd.read_csv(fpath, engine='python', encoding=enc2)
                                    if odf is None or odf.empty:
                                        continue
                                    for c in ['name', 'base_id', 'race']:
                                        if c not in odf.columns:
                                            odf[c] = ''
                                        odf[c] = odf[c].fillna('').astype(str).str.strip()
                                    om = (odf['name'] == name) & (odf['base_id'] == base_id) & (odf['race'] == race)
                                    if om.any():
                                        if 'tags' in odf.columns:
                                            incoming_tags = _clean(odf.loc[om, 'tags'].iloc[0])
                                            if incoming_tags:
                                                merged_tags = _append_csv(merged_tags, incoming_tags)
                                        if 'tags_overwrite' in odf.columns:
                                            incoming_tw = _clean(odf.loc[om, 'tags_overwrite'].iloc[0])
                                            if incoming_tw:
                                                merged_tags_overwrite = incoming_tw
                                elif ext == '.json':
                                    if os.path.getsize(fpath) == 0:
                                        continue
                                    with open(fpath, 'r', encoding='utf-8') as fp:
                                        obj = json.load(fp)
                                    items = obj if isinstance(obj, list) else [obj]
                                    for content in items:
                                        if not isinstance(content, dict):
                                            continue
                                        if (str(content.get('name', '')).strip() == name and
                                                str(content.get('base_id', '')).strip() == base_id and
                                                str(content.get('race', '')).strip() == race):
                                            incoming_tags = _clean(content.get('tags', ''))
                                            if incoming_tags:
                                                merged_tags = _append_csv(merged_tags, incoming_tags)
                                            incoming_tw = _clean(content.get('tags_overwrite', ''))
                                            if incoming_tw:
                                                merged_tags_overwrite = incoming_tw
                            except Exception:
                                continue
                    except Exception:
                        pass

                    # --- Step 3: write merged tags into character_df ---
                    for c in ['tags', 'tags_overwrite']:
                        if c not in gdf.columns:
                            gdf[c] = ''
                    try:
                        exact_mask = (
                            gdf['name'].fillna('').astype(str) == str(name)
                        ) & (
                            gdf['base_id'].fillna('').astype(str) == str(base_id)
                        ) & (
                            gdf['race'].fillna('').astype(str) == str(race)
                        )
                    except Exception:
                        exact_mask = None
                    if isinstance(exact_mask, pd.Series) and exact_mask.any():
                        gdf.loc[exact_mask, 'tags'] = merged_tags
                        if merged_tags_overwrite:
                            gdf.loc[exact_mask, 'tags_overwrite'] = merged_tags_overwrite

                    # --- Step 4: update in-conversation Character.bio with re-expanded tags ---
                    effective_tags = merged_tags_overwrite if merged_tags_overwrite else merged_tags
                    try:
                        talk = getattr(gm, '_GameStateManager__talk', None)
                        if talk and hasattr(talk, 'context'):
                            game_obj = gm.game
                            bio_tmpl_mgr = getattr(game_obj, '_Skyrim__bio_template_manager', None) or \
                                           getattr(game_obj, '_Fallout4__bio_template_manager', None)
                            characters = talk.context.npcs_in_conversation.get_all_characters()
                            def _normalize_id(val: str) -> str:
                                s = str(val or "").upper()
                                return s[-3:].rjust(6, "0") if s.startswith('FE') else s[-6:]
                            for ch in characters:
                                if _normalize_id(getattr(ch, 'base_id', "")) == _normalize_id(base_id):
                                    if (not name or str(getattr(ch, 'name', "")) == str(name)):
                                        # Re-read the base bio from character_df (before tag expansion)
                                        if isinstance(exact_mask, pd.Series) and exact_mask.any():
                                            raw_bio = _clean(gdf.loc[exact_mask, 'bio'].iloc[0])
                                        else:
                                            raw_bio = ch.bio
                                        if bio_tmpl_mgr:
                                            ch.bio = bio_tmpl_mgr.expand_bio_with_tags(raw_bio, effective_tags)
                                        # Update dynamic tag events
                                        if bio_tmpl_mgr and hasattr(bio_tmpl_mgr, 'extract_dynamic_events'):
                                            dyn = bio_tmpl_mgr.extract_dynamic_events(effective_tags)
                                            if dyn:
                                                ch.set_custom_character_value('mantella_dynamic_tag_events', dyn)
                    except Exception as e:
                        logging.debug(f"Bio Editor: in-conversation tag refresh skipped: {e}")
                except Exception as e:
                    logging.debug(f"Bio Editor: runtime tags refresh skipped: {e}")

            def on_save_from_llm(label: str, response_text: str, tags_text: str, l2k: dict[str, str], k2l: dict[str, str], user_csv: str):
                # Reuse existing save logic (already updates runtime)
                return on_save(label, response_text, tags_text, l2k, k2l, user_csv)

            # Persist Bio LLM UI selections into config.ini so they survive restarts
            def on_service_change_persist(new_service: str):
                try:
                    cv = config.definitions.get_config_value_definition("bio_llm_api")
                    cv.value = new_service
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass
                return update_model_list_for_service(new_service)

            def on_model_change_persist(new_model: str):
                try:
                    cv = config.definitions.get_config_value_definition("bio_llm_model")
                    cv.value = new_model
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass
                return gr.Dropdown(value=new_model, choices=model_dropdown.choices, multiselect=False, allow_custom_value=model_dropdown.allow_custom_value, label="Model")

            def on_apply_profile_change_persist(new_val: bool):
                try:
                    cv = config.definitions.get_config_value_definition("bio_llm_apply_profile")
                    cv.value = bool(new_val)
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass

            def on_temp_override_persist(new_val):
                try:
                    cv = config.definitions.get_config_value_definition("bio_llm_temperature_override")
                    try:
                        cv.value = float(new_val)
                    except Exception:
                        cv.value = -1.0
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass

            def on_max_tokens_override_persist(new_val):
                try:
                    cv = config.definitions.get_config_value_definition("bio_llm_max_tokens_override")
                    try:
                        cv.value = int(new_val)
                    except Exception:
                        cv.value = -1
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass

            def on_omit_stop_change_persist(new_val: bool):
                try:
                    cv = config.definitions.get_config_value_definition("bio_llm_omit_stop")
                    cv.value = bool(new_val)
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass

            override_csv_path.change(on_user_csv_change, inputs=[override_csv_path], outputs=[], show_progress="hidden")
            npc_dropdown.change(on_select, inputs=[npc_dropdown, state_df, state_label_to_key, state_world_id, override_csv_path], outputs=[bio_editor, summary_editor, thoughts_editor, reflections_editor, tags_editor, runtime_tags_display, info_line, save_btn, save_summary_btn, save_thoughts_btn, save_reflections_btn, generate_reflection_btn], show_progress="hidden")
            save_btn.click(on_save, inputs=[npc_dropdown, bio_editor, tags_editor, state_label_to_key, state_key_to_label, override_csv_path], outputs=[info_line, state_df, state_labels, state_label_to_key, state_key_to_label, npc_dropdown])
            refresh_btn.click(on_refresh, inputs=[override_csv_path], outputs=[info_line, state_df, state_labels, state_label_to_key, state_key_to_label, npc_dropdown, bio_editor, tags_editor, runtime_tags_display, save_btn])
            _memory_refresh_outputs = [info_line, summary_editor, thoughts_editor, reflections_editor, save_summary_btn, save_thoughts_btn, save_reflections_btn, generate_reflection_btn]
            refresh_summaries_btn.click(on_refresh_memory, inputs=[npc_dropdown, state_label_to_key, state_world_id], outputs=_memory_refresh_outputs)
            save_summary_btn.click(on_save_summary, inputs=[npc_dropdown, summary_editor, state_label_to_key, state_world_id], outputs=[info_line])
            refresh_thoughts_btn.click(on_refresh_memory, inputs=[npc_dropdown, state_label_to_key, state_world_id], outputs=_memory_refresh_outputs)
            save_thoughts_btn.click(on_save_thoughts, inputs=[npc_dropdown, thoughts_editor, state_label_to_key, state_world_id], outputs=[info_line])
            refresh_reflections_btn.click(on_refresh_memory, inputs=[npc_dropdown, state_label_to_key, state_world_id], outputs=_memory_refresh_outputs)
            save_reflections_btn.click(on_save_reflections, inputs=[npc_dropdown, reflections_editor, state_label_to_key, state_world_id], outputs=[info_line])
            generate_reflection_btn.click(on_generate_reflection, inputs=[npc_dropdown, bio_editor, summary_editor, state_label_to_key, state_world_id], outputs=[info_line, reflections_editor, save_reflections_btn, generate_reflection_btn])

            # LLM section wiring
            # Prompt profile wiring
            prompt_selector.change(apply_selected_prompt, inputs=[prompt_selector], outputs=[prompt_editor, save_prompt_btn], show_progress="hidden")
            save_prompt_btn.click(save_prompt_profile, inputs=[prompt_editor, new_prompt_name, prompt_selector], outputs=[info_line, prompt_selector, new_prompt_name])
            delete_prompt_btn.click(delete_prompt_profile, inputs=[prompt_selector], outputs=[info_line, prompt_selector, prompt_editor, new_prompt_name])

            service_dropdown.change(on_service_change_persist, inputs=[service_dropdown], outputs=[model_dropdown], show_progress="hidden")
            update_models_btn.click(on_service_change_persist, inputs=[service_dropdown], outputs=[model_dropdown])
            model_dropdown.change(on_model_change_persist, inputs=[model_dropdown], outputs=[model_dropdown], show_progress="hidden")
            apply_profile_checkbox.change(on_apply_profile_change_persist, inputs=[apply_profile_checkbox], outputs=[], show_progress="hidden")
            omit_stop_checkbox.change(on_omit_stop_change_persist, inputs=[omit_stop_checkbox], outputs=[], show_progress="hidden")
            temp_override.change(on_temp_override_persist, inputs=[temp_override], outputs=[], show_progress="hidden")
            max_tokens_override.change(on_max_tokens_override_persist, inputs=[max_tokens_override], outputs=[], show_progress="hidden")
            send_request_btn.click(on_send_llm_request, inputs=[npc_dropdown, state_df, state_label_to_key, state_world_id, prompt_editor, bio_editor, summary_editor, params_editor, apply_profile_checkbox, omit_stop_checkbox, temp_override, max_tokens_override, service_dropdown, model_dropdown], outputs=[info_line, llm_response_editor, save_from_llm_btn])
            save_from_llm_btn.click(on_save_from_llm, inputs=[npc_dropdown, llm_response_editor, tags_editor, state_label_to_key, state_key_to_label, override_csv_path], outputs=[llm_info_line, state_df, state_labels, state_label_to_key, state_key_to_label, npc_dropdown])
            refresh_llm_btn.click(on_refresh, inputs=[override_csv_path], outputs=[info_line, state_df, state_labels, state_label_to_key, state_key_to_label, npc_dropdown, bio_editor, tags_editor, runtime_tags_display, save_btn])

    def __get_theme(self):
        return gr.themes.Soft(primary_hue="green",
                            secondary_hue="green",
                            neutral_hue="zinc",
                            font=['Montserrat', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                            font_mono=['IBM Plex Mono', 'ui-monospace', 'Consolas', 'monospace']).set(
                                input_text_size='*text_md',
                                input_padding='*spacing_md',
                            )

    
    def add_route_to_server(self, app: FastAPI):
        @app.get("/favicon.ico")
        async def favicon():
            return FileResponse("Mantella.ico")

        @app.post("/tab-order")
        async def save_tab_order(request: Request):
            try:
                payload = await request.json()
                order = payload.get("order", [])
                if not isinstance(order, list):
                    return {"ok": False}
                names = [str(item).strip() for item in order if str(item).strip()]
                if not names:
                    return {"ok": False}
                self._config.save_ui_tab_order(names)
                return {"ok": True}
            except Exception as e:
                logging.warning(f"Failed to save tab order: {e}")
                return {"ok": False}

        gr.mount_gradio_app(app,
                            self.create_main_block(),
                            path="/ui")
        
        link = f'http://localhost:{str(self._config.port)}/ui?__theme=dark'
        logging.log(24, f'\nMantella settings can be changed via this link:')
        logging.log(25, link)
        if self._config.auto_launch_ui == True:
            if not webbrowser.open(link, new=2):
                logging.warning('\nFailed to open Mantella settings UI automatically. To edit settings, see here:')
                logging.log(25, link)
    
    def __load_css(self):
        # Determine CSS path based on whether we are running as an exe or from source
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            css_path = os.path.join(exe_dir, 'src', 'ui', 'style.css')
        else:
            css_path = os.path.join('src', 'ui', 'style.css')

        try:
            with open(css_path, 'r') as file:
                css_content = file.read()
                return css_content
        except FileNotFoundError:
            # Fallback: return empty CSS so the app still runs
            logging.warning(f"StartUI: Could not find CSS file at {css_path}. UI will load without custom styles.")
            return ""

    
    def _setup_route(self):
        pass

    
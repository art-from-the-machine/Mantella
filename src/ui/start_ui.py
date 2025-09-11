from fastapi import FastAPI
from fastapi.responses import FileResponse
import webbrowser
import gradio as gr
from src.config.config_loader import ConfigLoader
from src.http.routes.routeable import routeable
from src.ui.settings_ui_constructor import SettingsUIConstructor
import logging
import os
import pandas as pd
from src.config.definitions.game_definitions import GameEnum
import src.utils as utils
import json
import re
from src.ui.bio_llm_requester import BioLLMRequester
from src.llm.client_base import ClientBase

class StartUI(routeable):
    BANNER = "docs/_static/img/mantella_banner.png"
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config, False)
        self.__constructor = SettingsUIConstructor()

    def create_main_block(self) -> gr.Blocks:
        with gr.Blocks(title="Mantella", fill_height=True, analytics_enabled=False, theme= self.__get_theme(), css=self.__load_css()) as main_block:
            # with gr.Tab("Settings") as tabs:
            settings_page = self.__generate_settings_page()
            # with gr.Tab("Chat with NPCs", interactive=False):
            #     self.__generate_chat_page()
            # with gr.Tab("NPC editor", interactive=False):
            #     self.__generate_character_editor_page()
            with gr.Tab("Bio Editor"):
                self.__generate_bio_editor_page()

            with gr.Row(elem_classes="custom-footer"):
                gr.HTML("""
                    <div class="custom-footer">
                        <a href="https://art-from-the-machine.github.io/Mantella/" target="_blank">Mantella Installation Guide</a>
                    </div>
                """)
        return main_block

    def __generate_settings_page(self) -> gr.Column:
        # with gr.Column() as settings:
        for cf in self._config.definitions.base_groups:
            if not cf.is_hidden:
                with gr.Tab(cf.name):
                    cf.accept_visitor(self.__constructor)
        
        # Set up model dependencies after all UI elements are created
        self.__constructor.setup_model_dependencies()
        
        return None #settings
    
    def __generate_chat_page(self):
        return gr.Column()
    
    def __generate_character_editor_page(self):
        return gr.Column() 

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

        def _save_bio_to_user_path(label: str, bio_text: str, label_to_key: dict[str, str], user_csv_path: str | None, ref_id_value: str | None, tags_value: str | None) -> str:
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
                            if ref_id_value is not None:
                                content['ref_id'] = ref_id_value
                            if tags_value is not None:
                                content['tags'] = tags_value
                            updated = True
                            break
                    
                    if not updated:
                        # Add new entry at the end
                        new_entry = {'name': name, 'base_id': base_id, 'race': race, 'bio': bio_text}
                        if ref_id_value is not None:
                            new_entry['ref_id'] = ref_id_value
                        if tags_value is not None:
                            new_entry['tags'] = tags_value
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
                    
                    # Add optional columns if provided (proper pandas insertion)
                    if ref_id_value is not None and 'ref_id' not in df.columns:
                        df.insert(len(df.columns), 'ref_id', '')
                    if tags_value is not None and 'tags' not in df.columns:
                        df.insert(len(df.columns), 'tags', '')
                    
                    # Find matching row
                    m = ((df['name'].fillna('').astype(str) == name) & 
                         (df['base_id'].fillna('').astype(str) == base_id) & 
                         (df['race'].fillna('').astype(str) == race))
                    
                    if m.any():
                        # Update existing entry
                        df.loc[m, 'bio'] = bio_text
                        if ref_id_value is not None and 'ref_id' in df.columns:
                            df.loc[m, 'ref_id'] = ref_id_value
                        if tags_value is not None and 'tags' in df.columns:
                            df.loc[m, 'tags'] = tags_value
                    else:
                        # Add new entry at the end
                        new_row = {'name': name, 'base_id': base_id, 'race': race, 'bio': bio_text}
                        if ref_id_value is not None and 'ref_id' in df.columns:
                            new_row['ref_id'] = ref_id_value
                        if tags_value is not None and 'tags' in df.columns:
                            new_row['tags'] = tags_value
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

        # --- Summaries helpers (no heavy reloads) ---
        def _get_conversations_base_dir() -> str:
            # Same structure as Gameable.conversation_folder_path
            return os.path.join(config.save_folder, 'data', _get_game_folder_name(), 'conversations')

        def _pick_world_id(base_dir: str) -> str:
            try:
                if not os.path.isdir(base_dir):
                    return 'default'
                world_ids = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
                if not world_ids:
                    return 'default'
                if 'default' in world_ids:
                    return 'default'
                # choose most recently modified world folder
                world_ids_sorted = sorted(world_ids, key=lambda d: os.path.getmtime(os.path.join(base_dir, d)), reverse=True)
                return world_ids_sorted[0]
            except Exception:
                return 'default'

        def _find_summary_folder_for_name(base_dir: str, world_id: str, base_name: str) -> str | None:
            try:
                world_path = os.path.join(base_dir, world_id)
                if not os.path.isdir(world_path):
                    return None
                # Prefer name-ref folders if present
                candidates: list[tuple[float, str]] = []
                for d in os.listdir(world_path):
                    dpath = os.path.join(world_path, d)
                    if not os.path.isdir(dpath):
                        continue
                    if d == base_name or d.startswith(f"{base_name} - "):
                        try:
                            candidates.append((os.path.getmtime(dpath), dpath))
                        except Exception:
                            continue
                if not candidates:
                    return None
                candidates.sort(key=lambda x: x[0], reverse=True)
                return candidates[0][1]
            except Exception:
                return None

        def _latest_summary_file_path(folder_path: str, base_name: str) -> tuple[str | None, int]:
            try:
                if not folder_path or not os.path.isdir(folder_path):
                    return None, 1
                prefix = f"{base_name}_summary_"
                max_n = 0
                for f in os.listdir(folder_path):
                    if not f.endswith('.txt') or not f.startswith(prefix):
                        continue
                    try:
                        n = int(os.path.splitext(f)[0].split('_')[-1])
                        if n > max_n:
                            max_n = n
                    except Exception:
                        continue
                if max_n == 0:
                    return None, 1
                return os.path.join(folder_path, f"{base_name}_summary_{max_n}.txt"), max_n
            except Exception:
                return None, 1

        def _load_summary_for_label(label: str, l2k: dict[str, str], world_id: str) -> str:
            try:
                key = _key_from_label(label, l2k)
                if key == "":
                    return ""
                name, _, _ = _split_key(key)
                base_name = utils.remove_trailing_number(name)
                base_dir = _get_conversations_base_dir()
                folder = _find_summary_folder_for_name(base_dir, world_id, base_name)
                if not folder:
                    return ""
                latest_path, _ = _latest_summary_file_path(folder, base_name)
                if latest_path and os.path.exists(latest_path):
                    with open(latest_path, 'r', encoding='utf-8') as f:
                        return f.read().strip()
                return ""
            except Exception as e:
                logging.debug(f"Bio Editor: failed to load summary: {e}")
                return ""

        def _save_summary_for_label(label: str, summary_text: str, l2k: dict[str, str], world_id: str) -> str:
            try:
                key = _key_from_label(label, l2k)
                if key == "":
                    return ""
                name, _, _ = _split_key(key)
                base_name = utils.remove_trailing_number(name)
                base_dir = _get_conversations_base_dir()
                world_path = os.path.join(base_dir, world_id)
                os.makedirs(world_path, exist_ok=True)
                folder = _find_summary_folder_for_name(base_dir, world_id, base_name)
                if not folder:
                    # default to name-only folder
                    folder = os.path.join(world_path, base_name)
                os.makedirs(folder, exist_ok=True)
                latest_path, n = _latest_summary_file_path(folder, base_name)
                target_path = latest_path or os.path.join(folder, f"{base_name}_summary_{n}.txt")
                # Normalize text endings
                content = (summary_text or "").rstrip() + "\n"
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return target_path.replace('\\', '/')
            except Exception as e:
                logging.error(f"Bio Editor: failed to save summary: {e}")
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
            initial_world_id = _pick_world_id(_get_conversations_base_dir())
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

            gr.Markdown("### Bio Editor")
            npc_dropdown = gr.Dropdown(choices=labels, label="NPC", multiselect=False, allow_custom_value=False)
            bio_editor = gr.Text(value="", lines=12, label="Bio")
            
            info_line = gr.Markdown(value="", visible=True)
            # Optional: user-chosen path for base-only NPCs; persisted in hidden config key
            with gr.Row():
                save_btn = gr.Button("Save", variant="primary", interactive=False)
                refresh_btn = gr.Button("Refresh bios", variant="secondary")
                
            summary_editor = gr.Text(value="", lines=12, label="Summary")
            with gr.Row():
                save_summary_btn = gr.Button("Save Summary", variant="primary", interactive=False)
                refresh_summaries_btn = gr.Button("Refresh summaries", variant="secondary")

            # --- LLM Request section ---
            gr.Markdown("### Bio Editor – LLM Request")
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
            prompt_editor = gr.Text(value=_profiles_dict.get(_selected_prompt_name, ""), lines=8, label="Prompt (supports {bio} and {summary})")
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
                temp_override = gr.Number(value=config.definitions.get_float_value("bio_llm_temperature_override"), label="Temperature override (-1 to ignore)", precision=2)
                max_tokens_override = gr.Number(value=config.definitions.get_int_value("bio_llm_max_tokens_override"), label="Max tokens override (-1 to ignore)", precision=0)
            send_request_btn = gr.Button("Send Request", variant="primary")
            llm_response_editor = gr.Text(value="", lines=12, label="LLM Response")
            with gr.Row():
                save_from_llm_btn = gr.Button("Save Bio (from LLM response)", variant="primary", interactive=False)
                refresh_llm_btn = gr.Button("Refresh bios", variant="secondary")
            llm_info_line = gr.Markdown(value="", visible=True)

            def on_select(label: str, df: pd.DataFrame, l2k: dict[str, str], world_id: str):
                # Clear info and load bio; enable save when selection exists
                bio = _load_bio_for_label(label, df, l2k)
                summary = _load_summary_for_label(label, l2k, world_id)
                return bio, summary, "", gr.Button(interactive=bool(label)), gr.Button(interactive=bool(label))

            def on_save(label: str, bio_text: str, l2k: dict[str, str], k2l: dict[str, str], user_csv: str):
                # Try to infer optional ref_id and tags from current df row, if present
                ref_id_val = None
                tags_val = None
                try:
                    key = l2k.get(label, '')
                    n, b, r = _split_key(key)
                    if n and b:
                        rowmask = (state_df.value['name'].fillna('').astype(str) == n) & \
                                  (state_df.value['base_id'].fillna('').astype(str) == b) & \
                                  (state_df.value['race'].fillna('').astype(str) == r)
                        if rowmask.any():
                            row0 = state_df.value.loc[rowmask].iloc[0]
                            if 'ref_id' in row0.index:
                                ref_id_val = str(row0.get('ref_id', ''))
                            if 'tags' in row0.index:
                                tags_val = str(row0.get('tags', ''))
                except Exception:
                    pass
                path = _save_bio_to_user_path(label, bio_text, l2k, user_csv, ref_id_val, tags_val)
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
                # Update cached game DataFrame for future conversations
                try:
                    key_for_cached = l2k.get(label, '')
                    cn, cb, cr = _split_key(key_for_cached)
                    if cn and cb:
                        _update_cached_game_df_if_possible(cn, cb, cr, bio_text)
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
                # Clear selection and editor, disable save
                return (
                    "Bios refreshed.",
                    new_df,
                    new_labels,
                    new_l2k,
                    new_k2l,
                    gr.Dropdown(choices=new_labels, value=None),
                    gr.Text(value=""),
                    gr.Button(interactive=False)
                )

            def on_refresh_summaries(label: str, l2k: dict[str, str], world_id: str):
                summary = _load_summary_for_label(label, l2k, world_id)
                return "Summaries refreshed.", summary, gr.Button(interactive=bool(label))
            # Prompt profiles handlers
            def _get_profiles_state():
                try:
                    raw = config.definitions.get_string_value("bio_prompt_profiles") or "{}"
                    data = json.loads(raw)
                    return data if isinstance(data, dict) else {}
                except Exception:
                    return {}

            def save_prompt_profile(current_text: str, name: str, _) -> tuple[str, gr.Dropdown, gr.Text]:
                name = (name or "").strip()
                if name == "":
                    return "Enter a prompt name.", gr.Dropdown(choices=prompt_selector.choices, value=prompt_selector.value), gr.Text(value=name)
                profiles = _get_profiles_state()
                profiles[name] = current_text or ""
                try:
                    cvp = config.definitions.get_config_value_definition("bio_prompt_profiles")
                    cvp.value = json.dumps(profiles, indent=2)
                    cvs = config.definitions.get_config_value_definition("bio_prompt_selected")
                    cvs.value = name
                    try:
                        config._ConfigLoader__write_config_state(config.definitions)
                    except Exception:
                        pass
                    config.update_config_loader_with_changed_config_values()
                except Exception:
                    pass
                names = sorted(list(profiles.keys()))
                return f"Prompt '{name}' saved.", gr.Dropdown(choices=names, value=name, label="Prompt profile"), gr.Text(value=name)

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

            # --- LLM helper handlers ---
            def _render_prompt_text(template_text: str, bio_text: str, summary_text: str) -> str:
                """Render variables inside the prompt template.
                Supports {bio} and {summary} (case-insensitive, allows whitespace inside braces).
                """
                def repl(match: re.Match) -> str:
                    key = match.group(1).strip().lower()
                    if key == "bio":
                        return bio_text or ""
                    if key == "summary":
                        return summary_text or ""
                    return match.group(0)

                pattern = re.compile(r"\{\s*(bio|summary)\s*\}", re.IGNORECASE)
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

            def on_send_llm_request(label: str, df: pd.DataFrame, l2k: dict[str, str], world_id: str, raw_prompt: str, bio_text_ui: str, summary_text_ui: str, params_text: str, apply_profile: bool, temp_ovr: float, max_tokens_ovr: int, srv: str, mdl: str):
                # Resolve variables from current selection
                try:
                    # Prefer UI textboxes to ensure it works even if game is not running
                    current_bio = bio_text_ui or ""
                    current_summary = summary_text_ui or ""
                    if (not current_bio or not current_summary) and label:
                        # Fallback to disk/df if any is empty
                        if not current_bio:
                            current_bio = _load_bio_for_label(label, df, l2k) or ""
                        if not current_summary:
                            current_summary = _load_summary_for_label(label, l2k, world_id) or ""
                    final_prompt = _render_prompt_text(raw_prompt or "", current_bio, current_summary)
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

            def on_save_from_llm(label: str, response_text: str, l2k: dict[str, str], k2l: dict[str, str], user_csv: str):
                # Reuse existing save logic (already updates runtime)
                return on_save(label, response_text, l2k, k2l, user_csv)

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

            override_csv_path.change(on_user_csv_change, inputs=[override_csv_path], outputs=[])
            npc_dropdown.change(on_select, inputs=[npc_dropdown, state_df, state_label_to_key, state_world_id], outputs=[bio_editor, summary_editor, info_line, save_btn, save_summary_btn])
            save_btn.click(on_save, inputs=[npc_dropdown, bio_editor, state_label_to_key, state_key_to_label, override_csv_path], outputs=[info_line, state_df, state_labels, state_label_to_key, state_key_to_label, npc_dropdown])
            refresh_btn.click(on_refresh, inputs=[override_csv_path], outputs=[info_line, state_df, state_labels, state_label_to_key, state_key_to_label, npc_dropdown, bio_editor, save_btn])
            refresh_summaries_btn.click(on_refresh_summaries, inputs=[npc_dropdown, state_label_to_key, state_world_id], outputs=[info_line, summary_editor, save_summary_btn])
            save_summary_btn.click(on_save_summary, inputs=[npc_dropdown, summary_editor, state_label_to_key, state_world_id], outputs=[info_line])

            # LLM section wiring
            # Prompt profile wiring
            prompt_selector.change(apply_selected_prompt, inputs=[prompt_selector], outputs=[prompt_editor, save_prompt_btn])
            save_prompt_btn.click(save_prompt_profile, inputs=[prompt_editor, new_prompt_name, prompt_selector], outputs=[info_line, prompt_selector, new_prompt_name])
            delete_prompt_btn.click(delete_prompt_profile, inputs=[prompt_selector], outputs=[info_line, prompt_selector, prompt_editor, new_prompt_name])

            service_dropdown.change(on_service_change_persist, inputs=[service_dropdown], outputs=[model_dropdown])
            update_models_btn.click(on_service_change_persist, inputs=[service_dropdown], outputs=[model_dropdown])
            model_dropdown.change(on_model_change_persist, inputs=[model_dropdown], outputs=[model_dropdown])
            apply_profile_checkbox.change(on_apply_profile_change_persist, inputs=[apply_profile_checkbox], outputs=[])
            temp_override.change(on_temp_override_persist, inputs=[temp_override], outputs=[])
            max_tokens_override.change(on_max_tokens_override_persist, inputs=[max_tokens_override], outputs=[])
            send_request_btn.click(on_send_llm_request, inputs=[npc_dropdown, state_df, state_label_to_key, state_world_id, prompt_editor, bio_editor, summary_editor, params_editor, apply_profile_checkbox, temp_override, max_tokens_override, service_dropdown, model_dropdown], outputs=[info_line, llm_response_editor, save_from_llm_btn])
            save_from_llm_btn.click(on_save_from_llm, inputs=[npc_dropdown, llm_response_editor, state_label_to_key, state_key_to_label, override_csv_path], outputs=[llm_info_line, state_df, state_labels, state_label_to_key, state_key_to_label, npc_dropdown])
            refresh_llm_btn.click(on_refresh, inputs=[override_csv_path], outputs=[info_line, state_df, state_labels, state_label_to_key, state_key_to_label, npc_dropdown, bio_editor, save_btn])

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
        with open('src/ui/style.css', 'r') as file:
            css_content = file.read()
        return css_content
    
    def _setup_route(self):
        pass

    
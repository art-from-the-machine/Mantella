# =============================================================================
# settings_ui_constructor.py
# =============================================================================
# Original file by art-from-the-machine (Mantella project)
# https://github.com/art-from-the-machine/Mantella
#
# PLAYER2 INTEGRATION — Added by community contributor
# Changes are clearly marked with:
#   # --- PLAYER2 START ---
#   # --- PLAYER2 END ---
#
# Summary of changes:
#   1. New imports for Player2 auth helpers
#   2. New private method __create_player2_auth_section()
#      - Auto-detects existing key in secret_keys.json on service switch
#      - Checks Player2 app health via /v1/health before prompting user
#      - Auto-obtains key silently if app is running
#      - Shows minimal UI if already configured; full UI only when needed
#   3. visit_ConfigValueSelection() extended to:
#      - Show/hide the Player2 auth panel when Player2 is selected
#      - Auto-update the Model dropdown to "Managed by Player2" on service switch
#
# NOTE FOR MAINTAINER:
#   The Player2 GAME_CLIENT_ID in src/llm/player2_auth.py is a test ID.
#   Replace it with the official Mantella client ID from https://developer.player2.game
# =============================================================================

import typing
import gradio as gr
from typing import Any, Callable, TypeVar, NamedTuple, Dict, TypedDict, Optional
import src.utils as utils

logger = utils.get_logger()

from src.llm.client_base import ClientBase
from src.config.types.config_value_path import ConfigValuePath
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_multi_selection import ConfigValueMultiSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.config_value_constraint import ConfigValueConstraintResult
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_group import ConfigValueGroup
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_visitor import ConfigValueVisitor

# --- PLAYER2 START ---
from src.llm.player2_auth import (
    get_key_from_local_app,
    get_existing_key,
    check_player2_app_running,
    save_key_to_file,
    PLAYER2_API_BASE_URL,
    PLAYER2_DASHBOARD_URL,
    PLAYER2_GAME_CLIENT_ID
)
import webbrowser
import json
import time
import requests as req
from pathlib import Path
# --- PLAYER2 END ---


class SettingUIComponents(NamedTuple):
    input_ui: Any
    error_message: gr.Markdown

class SettingConfig(NamedTuple):
    config_value: ConfigValue
    create_input: Callable[[ConfigValue], Any]
    update_on_change: bool
    update_on_submit: bool
    update_on_blur: bool
    additional_buttons: list[tuple[str, Callable[[], Any]]]

class ModelConfig(TypedDict):
    dependent_config: str
    model_list_getter: Callable[[str], Any]


class SettingsUIConstructor(ConfigValueVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.__identifier_to_config_value: dict[str, ConfigValue] = {}
        self.__config_value_to_ui_element: dict[ConfigValue, Any] = {}
        self.__pending_shared_setting: SettingConfig | None = None

    @property
    def config_value_to_ui_element(self) -> dict[ConfigValue, gr.Column]:
        return self.__config_value_to_ui_element

    def __create_tooltip(self, config_value: ConfigValue, is_second_setting: bool = False) -> str:
        """Creates the tooltip HTML for a config value"""
        constraints_html = (f'<p class="constraints">' +
                          '<br>'.join(c.description for c in config_value.constraints) +
                          '</p>' if config_value.constraints else '')
        tooltip_content = 'tooltip-content-right' if is_second_setting else 'tooltip-content-left'
        description_html = (config_value.description or "").replace("\n", "<br>")

        return f"""
        <div class="tooltip-container" role="tooltip" aria-label="{config_value.name} help">
            <span class="tooltip-icon" tabindex="0">?</span>
            <div class={tooltip_content}>
                <p>{description_html}</p>
                {constraints_html}
            </div>
        </div>
        """

    def __create_buttons(self, config_value: ConfigValue,
                        create_input_component: Callable[[ConfigValue], Any],
                        input_ui: Any,
                        error_message: gr.Markdown,
                        additional_buttons: list[tuple[str, Callable[[], Any]]]) -> None:
        """Creates the buttons for a setting"""
        with gr.Row(elem_classes="button-container"):
            for btn_label, btn_action in additional_buttons:
                gr.Button(btn_label, variant="primary", size='sm').click(btn_action, outputs=input_ui)
            if not additional_buttons:
                reset_button = gr.Button("Default", size='sm')
                if hasattr(reset_button, "_id"):
                    reset_button.click(
                        lambda: self.__on_reset_click(config_value, create_input_component),
                        outputs = [input_ui, error_message]
                    )

    def __on_reset_click(self, config_value: ConfigValue, create_input_component: Callable[[ConfigValue], Any]):
        error_message = self.__on_change(config_value, config_value.default_value)
        new_input = create_input_component(config_value)
        return [new_input, error_message]

    def __setup_event_handlers(self, config_value: ConfigValue,
                             input_ui: Any,
                             error_message: gr.Markdown,
                             update_on_change: bool,
                             update_on_submit: bool,
                             update_on_blur: bool) -> None:
        """Sets up the event handlers for an input component"""
        if hasattr(input_ui, "_id"):
            if update_on_change:
                input_ui.change(lambda x: self.__on_change(config_value, x), input_ui, error_message)
            if update_on_submit:
                input_ui.submit(lambda x: self.__on_change(config_value, x), input_ui, error_message)
            if update_on_blur:
                input_ui.blur(lambda x: self.__on_change(config_value, x), input_ui, error_message)

    def __create_setting_components(self, setting: SettingConfig, is_second_setting: bool = False) -> SettingUIComponents:
        """Creates the UI components for a single setting"""
        if isinstance(setting.config_value, ConfigValueBool):
            elem_class = "setting-bool-container-wide" if ConfigValueTag.share_row in setting.config_value.tags else "setting-bool-container-narrow"
            with gr.Row(elem_classes=elem_class):
                input_ui = setting.create_input(setting.config_value)
                gr.HTML(self.__create_tooltip(setting.config_value, is_second_setting))
        else:
            self.__construct_name_description_constraints(setting.config_value, is_second_setting)
            with gr.Row(equal_height=True, elem_classes="setting-controls"):
                input_ui = setting.create_input(setting.config_value)
                input_ui.scale = 999
                self.__create_buttons(setting.config_value, setting.create_input,
                                    input_ui, gr.Markdown(None), setting.additional_buttons)

        error_message = self.__construct_initial_error_message(setting.config_value)

        self.__setup_event_handlers(
            setting.config_value, input_ui, error_message,
            setting.update_on_change, setting.update_on_submit, setting.update_on_blur
        )

        return SettingUIComponents(input_ui, error_message)

    def __create_paired_settings(self, setting1: SettingConfig, setting2: SettingConfig):
        """Creates two settings side by side in the same row"""
        with gr.Row():
            is_second_setting = False
            for setting in [setting1, setting2]:
                with gr.Column(variant="panel", scale=1):
                    components = self.__create_setting_components(setting, is_second_setting)
                    is_second_setting = True
                    self.__identifier_to_config_value[setting.config_value.identifier] = setting.config_value
                    self.__config_value_to_ui_element[setting.config_value] = components.input_ui

    def __create_single_setting(self, setting: SettingConfig):
        """Creates a single setting taking up the full row"""
        with gr.Column(variant="panel", scale=1):
            components = self.__create_setting_components(setting)
            self.__identifier_to_config_value[setting.config_value.identifier] = setting.config_value
            self.__config_value_to_ui_element[setting.config_value] = components.input_ui

    def __create_config_value_ui_element(self, config_value: ConfigValue,
                                       create_input_component: Callable[[ConfigValue], Any],
                                       update_on_change: bool = True,
                                       update_on_submit: bool = False,
                                       update_on_blur: bool = False,
                                       additional_buttons: list[tuple[str, Callable[[], Any]]] = []):
        current_setting = SettingConfig(
            config_value, create_input_component,
            update_on_change, update_on_submit, update_on_blur,
            additional_buttons
        )

        if ConfigValueTag.share_row in config_value.tags:
            if self.__pending_shared_setting is not None:
                self.__create_paired_settings(self.__pending_shared_setting, current_setting)
                self.__pending_shared_setting = None
            else:
                self.__pending_shared_setting = current_setting
            return

        if self.__pending_shared_setting is not None:
            self.__create_single_setting(self.__pending_shared_setting)
            self.__pending_shared_setting = None

        self.__create_single_setting(current_setting)

    T = TypeVar('T')
    def __on_change(self, config_value: ConfigValue[T], new_value: T) -> gr.Markdown:
        result: ConfigValueConstraintResult = config_value.does_value_cause_error(new_value)
        if result.is_success:
            if config_value.value != new_value:
                config_value.value = new_value
                logger.info(f'{config_value.name} set to {config_value.value}')
            return self.__construct_error_message_panel('', is_visible=False)
        else:
            return self.__construct_error_message_panel(result.error_message, is_visible=True)

    def __construct_error_message_panel(self, message: str, is_visible: bool) -> gr.Markdown:
        markdown = gr.Markdown(value=message, visible=is_visible, elem_classes="constraint-violation")
        return markdown

    def _construct_badges(self, config_value: ConfigValue):
        if len(config_value.tags) > 0:
            with gr.Row():
                for tag in config_value.tags:
                    gr.HTML(f"<b>{str(tag).upper()}</b>", elem_classes=["badge",f"badge-{tag}"])
                gr.Column()

    def __construct_name_description_constraints(self, config_value: ConfigValue, is_second_setting: bool = False):
        with gr.Row():
            description_html = (config_value.description or "").replace("\n", "<br>")
            tooltip_content = 'tooltip-content-right' if is_second_setting else 'tooltip-content-left'
            tooltip_html = f"""
            <div style="display: flex; align-items: center;">
                <h3 style="margin: 0; font-size: 1.25em;">{config_value.name}</h3>
                <div class="tooltip-container" role="tooltip" aria-label="{config_value.name} help">
                    <span class="tooltip-icon">?</span>
                    <div class={tooltip_content}>
                        <p>{description_html}</p>
                        {'<p>' + '<br>'.join(c.description for c in config_value.constraints if c.description is not None) + '</p>' if config_value.constraints else ''}
                    </div>
                </div>
            </div>
            """
            gr.HTML(tooltip_html)

    def __construct_initial_error_message(self, config_value: ConfigValue) -> gr.Markdown:
        result: ConfigValueConstraintResult = config_value.does_value_cause_error(config_value.value)
        return self.__construct_error_message_panel(result.error_message, is_visible=not result.is_success)

    def visit_ConfigValueGroup(self, config_value: ConfigValueGroup):
        if not config_value.is_hidden:
            has_advanced_values = False
            regular_settings = []
            advanced_settings = []
            for cf in config_value.value:
                if not cf.is_hidden:
                    if ConfigValueTag.advanced in cf.tags:
                        advanced_settings.append(cf)
                        has_advanced_values = True
                    else:
                        regular_settings.append(cf)

            for i, cf in enumerate(regular_settings):
                cf.accept_visitor(self)

            if has_advanced_values:
                with gr.Accordion(label="Advanced", open=False):
                    for cf in advanced_settings:
                        cf.accept_visitor(self)

    def visit_ConfigValueInt(self, config_value: ConfigValueInt):
        def create_input_component(raw_config_value: ConfigValue) -> gr.Number:
            config_value = typing.cast(ConfigValueInt, raw_config_value)
            return gr.Number(value=config_value.value,
                        precision=0,
                        show_label=False,
                        container=False)

        self.__create_config_value_ui_element(config_value, create_input_component)

    def visit_ConfigValueFloat(self, config_value: ConfigValueFloat):
        def create_input_component(raw_config_value: ConfigValue) -> gr.Number:
            config_value = typing.cast(ConfigValueFloat, raw_config_value)
            return gr.Number(value=config_value.value,
                    precision=2,
                    show_label=False,
                    container=False,
                    step=0.1)

        self.__create_config_value_ui_element(config_value, create_input_component)

    def visit_ConfigValueBool(self, config_value: ConfigValueBool):
        def create_input_component(raw_config_value: ConfigValue) -> gr.Checkbox:
            config_value = typing.cast(ConfigValueBool, raw_config_value)
            return gr.Checkbox(label = config_value.name,
                                    value=config_value.value,
                                    show_label=False,
                                    container=False,elem_classes="checkboxelement")

        self.__create_config_value_ui_element(config_value, create_input_component)

    def visit_ConfigValueString(self, config_value: ConfigValueString):
        def create_input_component(raw_config_value: ConfigValue) -> gr.Text:
            config_value = typing.cast(ConfigValueString, raw_config_value)
            count_rows = self.__count_rows_in_text(config_value.value)
            if count_rows == 1:
                return gr.Text(value=config_value.value,
                        show_label=False,
                        container=False,
                        max_lines=1)
            else:
                return gr.Text(value=config_value.value,
                        show_label=False,
                        container=False,
                        lines= count_rows,
                        elem_classes="multiline-textbox")

        self.__create_config_value_ui_element(config_value, create_input_component, False, True, True)

    def __count_rows_in_text(self, text: str) -> int:
        count_CRLF = text.count("\r\n")
        count_newline = text.count("\n")
        return count_CRLF + (count_newline - count_CRLF) + 1

    # --- PLAYER2 START ---
    def __create_player2_auth_section(self) -> gr.Column:
        """Creates the Player2 authentication panel shown when Player2 is selected as LLM service.

        The panel is smart and minimal by design:

        1. When Player2 is selected from the dropdown, auto_detect_on_show() runs immediately:
           a. If secret_keys.json already has a Player2 key → show "Already configured" state.
              No action needed from the user.
           b. If no key but Player2 app is running (/v1/health) → silently obtain the key,
              save it, and show "Configured automatically" state.
           c. If neither → show the manual auth buttons so the user can get a key.

        2. The user can always click "Reconfigure" to force a new key if needed.

        3. The browser OAuth flow (Device Code) is available as fallback when the app
           is not running.

        NOTE FOR MAINTAINER:
          PLAYER2_GAME_CLIENT_ID in player2_auth.py is a test ID.
          Replace it with the official Mantella ID from https://developer.player2.game
        """

        with gr.Column(visible=False) as p2_section:
            gr.HTML("""
                <div style='border-left: 4px solid #4a8c4a; padding: 8px 12px; margin: 4px 0 8px 0;
                            background: rgba(74,140,74,0.08); border-radius: 4px;'>
                    <strong>🎮 Player2 Authentication</strong>
                </div>
            """)

            # Status message — updates automatically based on detection result
            p2_status = gr.Markdown("🔍 Checking Player2 configuration...")

            # Key display — only shown after obtaining a new key
            p2_key_display = gr.Textbox(
                label="Player2 API Key",
                placeholder="Your key will appear here once authenticated...",
                visible=False,
                interactive=False,
                show_label=True,
                container=True
            )

            # Manual auth buttons — only shown when no key is found automatically
            with gr.Row(visible=False) as p2_buttons_row:
                p2_oauth_btn = gr.Button(
                    "🌐 Generate via Browser",
                    variant="primary",
                    size="sm"
                )
                p2_reconfigure_btn = gr.Button(
                    "🔄 Reconfigure",
                    variant="secondary",
                    size="sm",
                    visible=False
                )

            p2_save_btn = gr.Button(
                "💾 Save key to secret_keys.json",
                variant="primary",
                size="sm",
                visible=False
            )

            gr.HTML("""
                <small style='color: #888;'>
                    💡 Download the <a href='https://player2.game' target='_blank'>Player2 App</a>
                    for zero-config setup — no API key management needed.
                </small>
            """)

            # ------------------------------------------------------------------
            # Auto-detection logic — runs when Player2 is selected from dropdown.
            #
            # Priority order:
            #   1. Existing key in secret_keys.json → already configured, do nothing
            #   2. Player2 app running (/v1/health) → get key silently, save it
            #   3. Neither → show manual auth buttons
            # ------------------------------------------------------------------
            def auto_detect_on_show(service: str):
                if service != "Player2":
                    return (
                        gr.update(visible=False),  # p2_section
                        gr.update(),               # p2_status
                        gr.update(visible=False),  # p2_buttons_row
                        gr.update(visible=False),  # p2_reconfigure_btn
                        gr.update(visible=False),  # p2_key_display
                        gr.update(visible=False),  # p2_save_btn
                    )

                # Check 1: existing key in secret_keys.json
                existing_key = get_existing_key()
                if existing_key:
                    return (
                        gr.update(visible=True),
                        gr.update(value="✅ Player2 is configured. API key found in `secret_keys.json`."),
                        gr.update(visible=False),
                        gr.update(visible=True),   # show Reconfigure button
                        gr.update(visible=False),
                        gr.update(visible=False),
                    )

                # Check 2: Player2 app running → get key silently
                if check_player2_app_running():
                    key = get_key_from_local_app()
                    if key:
                        save_key_to_file(key)
                        return (
                            gr.update(visible=True),
                            gr.update(value="✅ Player2 App detected. API key configured automatically."),
                            gr.update(visible=False),
                            gr.update(visible=True),   # show Reconfigure button
                            gr.update(visible=False),
                            gr.update(visible=False),
                        )

                # Check 3: nothing found → show manual buttons
                return (
                    gr.update(visible=True),
                    gr.update(value="⚠️ No Player2 API key found. Choose an authentication method:"),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )

            # ------------------------------------------------------------------
            # Reconfigure button — forces re-detection even if already configured
            # ------------------------------------------------------------------
            def on_reconfigure_click():
                if check_player2_app_running():
                    key = get_key_from_local_app()
                    if key:
                        save_key_to_file(key)
                        return (
                            gr.update(value="✅ Player2 App detected. Key refreshed automatically."),
                            gr.update(visible=False),
                            gr.update(visible=True),
                            gr.update(visible=False),
                            gr.update(visible=False),
                        )

                return (
                    gr.update(value="⚠️ Player2 App not running. Choose an authentication method:"),
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                )

            p2_reconfigure_btn.click(
                fn=on_reconfigure_click,
                outputs=[p2_status, p2_buttons_row, p2_reconfigure_btn, p2_key_display, p2_save_btn]
            )

            # ------------------------------------------------------------------
            # Browser OAuth flow (Device Code)
            # Used when the Player2 app is not installed or not running.
            #
            # Flow:
            #   1. POST /login/device/new → get device_code + verification URL
            #   2. Open browser to verification URL
            #   3. Poll /login/device/token until authorized or timed out
            # ------------------------------------------------------------------
            def start_browser_flow():
                try:
                    response = req.post(
                        f"https://api.player2.game/v1/login/device/new",
                        json={"client_id": PLAYER2_GAME_CLIENT_ID},
                        timeout=10
                    )
                    if response.status_code != 200:
                        return (
                            gr.update(value=f"❌ Could not start authentication (HTTP {response.status_code})."),
                            gr.update(visible=True),
                            gr.update(visible=False),
                            gr.update(visible=False),
                        )

                    data = response.json()
                    auth_url = data.get("verificationUriComplete") or data.get("verification_uri_complete")
                    device_code = data.get("deviceCode") or data.get("device_code")
                    poll_interval = data.get("interval", 5)

                    if not auth_url or not device_code:
                        return (
                            gr.update(value="❌ Unexpected response from Player2. Please try again."),
                            gr.update(visible=True),
                            gr.update(visible=False),
                            gr.update(visible=False),
                        )

                    webbrowser.open(auth_url)

                    for _ in range(60):  # max 5 minutes
                        time.sleep(poll_interval)
                        poll = req.post(
                            f"https://api.player2.game/v1/login/device/token",
                            json={
                                "client_id": PLAYER2_GAME_CLIENT_ID,
                                "device_code": device_code,
                                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                            },
                            timeout=10
                        )
                        if poll.status_code == 200:
                            key = poll.json().get("p2Key", "")
                            if key:
                                return (
                                    gr.update(value="✅ Authorization successful! Save your key below."),
                                    gr.update(visible=False),
                                    gr.update(value=key, visible=True),
                                    gr.update(visible=True),
                                )
                        elif poll.status_code != 400:
                            break

                    return (
                        gr.update(value="⏱️ Timed out. Please try again."),
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False),
                    )

                except Exception as e:
                    return (
                        gr.update(value=f"❌ Error: {e}"),
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False),
                    )

            p2_oauth_btn.click(
                fn=start_browser_flow,
                outputs=[p2_status, p2_buttons_row, p2_key_display, p2_save_btn]
            )

            # ------------------------------------------------------------------
            # Save key button — saves the newly obtained key to secret_keys.json
            # ------------------------------------------------------------------
            def save_key(key: str):
                if not key or not key.strip():
                    return gr.update(value="⚠️ No key to save.")
                if save_key_to_file(key):
                    return gr.update(value="✅ Key saved! Restart Mantella to apply.")
                return gr.update(value="❌ Could not save key. Check file permissions.")

            p2_save_btn.click(
                fn=save_key,
                inputs=[p2_key_display],
                outputs=[p2_status]
            )

        return (
            p2_section,
            p2_status,
            p2_buttons_row,
            p2_reconfigure_btn,
            p2_key_display,
            p2_save_btn,
            auto_detect_on_show,
        )
    # --- PLAYER2 END ---

    def visit_ConfigValueSelection(self, config_value: ConfigValueSelection):
        special_handlers: Dict[str, ModelConfig] = {
            "model": {
                "dependent_config": "llm_api",
                "default_model": 'mistralai/mistral-small-3.1-24b-instruct:free',
                "model_list_getter": ClientBase.get_model_list,
            },
            "vision_model": {
                "dependent_config": "vision_llm_api",
                "default_model": 'google/gemma-3-27b-it:free',
                "model_list_getter": ClientBase.get_model_list,
            },
            "function_llm": {
                "dependent_config": "function_llm_api",
                "default_model": 'mistralai/mistral-small-3.1-24b-instruct:free',
                "model_list_getter": ClientBase.get_model_list,
            }
        }

        def update_model_list() -> gr.Dropdown:
            current_config = self.__identifier_to_config_value[config_value.identifier]
            return create_input_component(current_config)

        def create_input_component(raw_config_value: ConfigValue) -> gr.Dropdown:
            config_value = typing.cast(ConfigValueSelection, raw_config_value)

            handler = special_handlers.get(config_value.identifier)
            if handler:
                service: str = self.__identifier_to_config_value[handler["dependent_config"]].value
                default_model = handler.get("default_model", 'mistralai/mistral-small-3.1-24b-instruct:free')
                is_vision = True if config_value.identifier == 'vision_model' else False
                is_tool_calling = True if config_value.identifier == 'function_llm' else False
                model_list = handler["model_list_getter"](service, default_model, is_vision, is_tool_calling)
                selected_model = config_value.value

                if not model_list.is_model_in_list(selected_model):
                    selected_model = model_list.default_model

                return gr.Dropdown(
                    value=selected_model,
                    choices=model_list.available_models,
                    multiselect=False,
                    allow_custom_value=model_list.allows_manual_model_input,
                    show_label=False,
                    container=False
                )

            return gr.Dropdown(
                value=config_value.value,
                choices=config_value.options,
                multiselect=False,
                allow_custom_value=config_value.allows_custom_value,
                show_label=False,
                container=False
            )

        additional_buttons: list[tuple[str, Callable[[], Any]]] = []
        if config_value.identifier in special_handlers:
            additional_buttons = [("Update", update_model_list)]

        self.__create_config_value_ui_element(
            config_value,
            create_input_component,
            additional_buttons=additional_buttons
        )

        # --- PLAYER2 START ---
        # When rendering the "llm_api" dropdown, build the Player2 auth panel
        # and store all its components on self so they can be accessed later
        # when wiring the "model" dropdown's change handler.
        #
        # IMPORTANT: We do NOT call service_dropdown.change() here.
        # Gradio does not support calling .change() twice on the same component.
        # All wiring for the llm_api dropdown is done in the "model" visit below,
        # where both the model update and the player2 panel update are combined
        # into a single .change() handler.
        if config_value.identifier == "llm_api":
            (
                self.__p2_section,
                self.__p2_status,
                self.__p2_buttons_row,
                self.__p2_reconfigure_btn,
                self.__p2_key_display,
                self.__p2_save_btn,
                self.__p2_auto_detect_fn,
            ) = self.__create_player2_auth_section()

        # When rendering the "model" dropdown (which depends on "llm_api"):
        # Wire a single .change() on the service dropdown that simultaneously:
        #   1. Updates the model dropdown (standard Mantella behavior)
        #   2. Shows/hides the Player2 auth panel and runs auto-detection
        #
        # This avoids calling .change() twice on the same component, which
        # causes Gradio to throw "Component not a valid output component" errors.
        if config_value.identifier == "model":
            dependent_config = self.__identifier_to_config_value.get("llm_api")
            if dependent_config is not None:
                service_dropdown = self.__config_value_to_ui_element.get(dependent_config)
                model_dropdown = self.__config_value_to_ui_element.get(config_value)
                if service_dropdown is not None and model_dropdown is not None:
                    p2_auto_detect_fn = self.__p2_auto_detect_fn

                    def on_service_change(service: str):
                        # --- PLAYER2: update the stored config value before calling update_model_list
                        # so it reads the correct service instead of the previous one
                        self.__identifier_to_config_value["llm_api"].value = service
                        model_update = update_model_list()
                        p2_updates = p2_auto_detect_fn(service)
                        return (model_update, *p2_updates)
                    
                    service_dropdown.change(
                        fn=on_service_change,
                        inputs=[service_dropdown],
                        outputs=[
                            model_dropdown,
                            self.__p2_section,
                            self.__p2_status,
                            self.__p2_buttons_row,
                            self.__p2_reconfigure_btn,
                            self.__p2_key_display,
                            self.__p2_save_btn,
                        ]
                    )

        # For vision_model and function_llm, wire their service dropdowns normally
        # (they are independent of Player2 and have no auth panel to manage)
        if config_value.identifier in ("vision_model", "function_llm"):
            dependent_id = special_handlers[config_value.identifier]["dependent_config"]
            dependent_config = self.__identifier_to_config_value.get(dependent_id)
            if dependent_config is not None:
                service_dropdown = self.__config_value_to_ui_element.get(dependent_config)
                model_dropdown = self.__config_value_to_ui_element.get(config_value)
                if service_dropdown is not None and model_dropdown is not None:
                    service_dropdown.change(
                        fn=update_model_list,
                        outputs=[model_dropdown]
                    )
        # --- PLAYER2 END ---

    def visit_ConfigValueMultiSelection(self, config_value: ConfigValueMultiSelection):
        def create_input_component(raw_config_value: ConfigValue) -> gr.Dropdown:
            config_value = typing.cast(ConfigValueMultiSelection, raw_config_value)
            values: list[str | int | float] = []
            for s in config_value.value:
                values.append(s)
            return gr.Dropdown(value=values,
                choices=config_value.options,
                multiselect=True,
                allow_custom_value=False,
                show_label=False,
                container=False)

        self.__create_config_value_ui_element(config_value, create_input_component)

    def visit_ConfigValuePath(self, config_value: ConfigValuePath):
        def on_pick_click() -> str | None:
            return config_value.show_file_or_path_picker_dialog()

        def create_input_component(raw_config_value: ConfigValue) -> gr.Text:
            config_value = typing.cast(ConfigValuePath, raw_config_value)
            return gr.Text(value=config_value.value, show_label=False, container=False, max_lines=1)

        self.__create_config_value_ui_element(config_value, create_input_component, True, True, True, [("Browse...", on_pick_click)])
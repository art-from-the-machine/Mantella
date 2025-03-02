import typing
import gradio as gr
from typing import Any, Callable, TypeVar, NamedTuple, Dict, TypedDict, Optional
import logging

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
    dependent_config: str  # The config value this model depends on (e.g., "llm_api")
    model_list_getter: Callable[[str], Any]  # Function to get model list based on service

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
            # dynamically change width of bool title depending on whether the setting shares a row with another setting
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
                logging.info(f'{config_value.name} set to {config_value.value}')
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

    def visit_ConfigValueSelection(self, config_value: ConfigValueSelection):
        # Define special handlers for different identifiers
        special_handlers: Dict[str, ModelConfig] = {
            "model": {
                "dependent_config": "llm_api",
                "model_list_getter": ClientBase.get_model_list,
            },
            "vision_model": {
                "dependent_config": "vision_llm_api",
                "model_list_getter": ClientBase.get_model_list,
            },
            "model_summaries": {
                "dependent_config": "llm_api",
                "model_list_getter": ClientBase.get_model_list,
            }
        }

        def update_model_list() -> gr.Dropdown:
            current_config = self.__identifier_to_config_value[config_value.identifier]
            return create_input_component(current_config)

        def create_input_component(raw_config_value: ConfigValue) -> gr.Dropdown:
            config_value = typing.cast(ConfigValueSelection, raw_config_value)
            
            # Handle special cases
            handler = special_handlers.get(config_value.identifier)
            if handler:
                service: str = self.__identifier_to_config_value[handler["dependent_config"]].value
                secret_key_file = 'IMAGE_SECRET_KEY.txt' if config_value.identifier == 'vision_model' else 'GPT_SECRET_KEY.txt'
                default_model = 'meta-llama/llama-3.2-11b-vision-instruct:free' if config_value.identifier == 'vision_model' else 'google/gemma-2-9b-it:free'
                is_vision = True if config_value.identifier == 'vision_model' else False
                model_list = handler["model_list_getter"](service, secret_key_file, default_model, is_vision)
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
            
            # Default handling for non-special cases
            return gr.Dropdown(
                value=config_value.value,                        
                choices=config_value.options,
                multiselect=False,
                allow_custom_value=config_value.allows_custom_value,
                show_label=False,
                container=False
            )

        # Add update button only for special cases
        additional_buttons: list[tuple[str, Callable[[], Any]]] = []
        if config_value.identifier in special_handlers:
            additional_buttons = [("Update", update_model_list)]

        self.__create_config_value_ui_element(
            config_value,
            create_input_component,
            additional_buttons=additional_buttons
        )

    def visit_ConfigValueMultiSelection(self, config_value: ConfigValueMultiSelection):
        def create_input_component(raw_config_value: ConfigValue) -> gr.Dropdown:
            config_value = typing.cast(ConfigValueMultiSelection, raw_config_value)
            values: list[str | int | float] = []
            for s in config_value.value:
                values.append(s)
            return gr.Dropdown(value=values,                        
                choices=config_value.options, # type: ignore
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


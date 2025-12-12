import typing
import gradio as gr
from typing import Any, Callable, TypeVar, NamedTuple, Dict, TypedDict, Optional
import logging

from src.llm.client_base import ClientBase
from src.model_profile_manager import ModelProfileManager
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

# Global reference to the game manager for character data reload functionality
_game_manager_ref = None

def set_game_manager_reference(game_manager):
    """Set the global game manager reference for UI access"""
    global _game_manager_ref
    _game_manager_ref = game_manager

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
    model_list_getter: Callable[[str, str, str, bool], Any]  # Function to get model list based on service, secret_key_file, default_model, is_vision

class SettingsUIConstructor(ConfigValueVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.__identifier_to_config_value: dict[str, ConfigValue] = {}
        self.__config_value_to_ui_element: dict[ConfigValue, Any] = {}
        self.__pending_shared_setting: SettingConfig | None = None
        self.__row_groups: dict[str, list[SettingConfig]] = {}  # Track settings by row_group
        self.__last_row_group: str | None = None  # Track the last row group being built
        self.__model_dependencies: list[tuple[str, str]] = []  # (model_id, service_id) pairs
        self.__profile_manager: ModelProfileManager | None = None
    
    @property
    def config_value_to_ui_element(self) -> dict[ConfigValue, gr.Column]:
        return self.__config_value_to_ui_element
    
    def _get_profile_manager(self) -> ModelProfileManager:
        """Lazily initialize and return the profile manager"""
        if self.__profile_manager is None:
            self.__profile_manager = ModelProfileManager()
        return self.__profile_manager
    

    
    def setup_model_dependencies(self) -> None:
        """Set up automatic model list updates when dependent service changes.
        Call this after all UI elements have been created."""
        special_handlers: Dict[str, ModelConfig] = {
            "model": {
                "dependent_config": "llm_api",
                "model_list_getter": ClientBase.get_model_list,
            },
            "vision_model": {
                "dependent_config": "vision_llm_api",
                "model_list_getter": ClientBase.get_model_list,
            },
            "multi_npc_model": {
                "dependent_config": "multi_npc_llm_api",
                "model_list_getter": ClientBase.get_model_list,
            },
            "summary_model": {
                "dependent_config": "summary_llm_api",
                "model_list_getter": ClientBase.get_model_list,
            },
            "profile_selected_model": {
                "dependent_config": "profile_selected_service",
                "model_list_getter": ClientBase.get_model_list,
            }
        }
        
        for model_id, service_id in self.__model_dependencies:
            model_config = self.__identifier_to_config_value.get(model_id)
            service_config = self.__identifier_to_config_value.get(service_id)
            
            if model_config and service_config:
                model_ui = self.__config_value_to_ui_element.get(model_config)
                service_ui = self.__config_value_to_ui_element.get(service_config)
                
                if model_ui and service_ui and hasattr(service_ui, "_id"):
                    handler = special_handlers.get(model_id)
                    if handler:
                        def create_update_function(model_cfg, handler_cfg):
                            def update_model_list_for_service() -> gr.Dropdown:
                                return self.__create_model_dropdown(model_cfg, handler_cfg)
                            return update_model_list_for_service
                        
                        def create_change_handler(model_cfg, service_cfg, update_func):
                            def on_service_change(new_service_value):
                                # Update the service config value
                                service_cfg.value = new_service_value
                                # Return updated model dropdown
                                return update_func()
                            return on_service_change
                        
                        update_func = create_update_function(model_config, handler)
                        change_handler = create_change_handler(model_config, service_config, update_func)
                        
                        # Special handling for profile service changes
                        if model_config.identifier == "profile_selected_model":
                            parameters_config = self.__identifier_to_config_value.get("profile_parameters")
                            parameters_ui = self.__config_value_to_ui_element.get(parameters_config) if parameters_config else None
                            
                            if parameters_ui:
                                def profile_service_change_handler(new_service_value):
                                    # Update the service config value
                                    service_config.value = new_service_value
                                    
                                    # Clear parameters when service changes
                                    parameters_config.value = ""
                                    logging.info(f"Service changed to {new_service_value}, cleared profile parameters")
                                    
                                    # Return updated model dropdown and cleared parameters
                                    updated_dropdown = update_func()
                                    return updated_dropdown, ""
                                
                                service_ui.change(
                                    profile_service_change_handler,
                                    inputs=service_ui,
                                    outputs=[model_ui, parameters_ui]
                                )
                            else:
                                service_ui.change(
                                    change_handler,
                                    inputs=service_ui,
                                    outputs=model_ui
                                )
                        else:
                            service_ui.change(
                                change_handler,
                                inputs=service_ui,
                                outputs=model_ui
                            )
        
        # Set up automatic profile loading for model profiles  
        # This will be handled by the standard model dependency system above, 
        # we just need to add a custom handler for when the profile model changes
        profile_model_config = self.__identifier_to_config_value.get("profile_selected_model")
        profile_service_config = self.__identifier_to_config_value.get("profile_selected_service")
        
        if profile_model_config and profile_service_config:
            profile_model_ui = self.__config_value_to_ui_element.get(profile_model_config)
            parameters_config = self.__identifier_to_config_value.get("profile_parameters")
            parameters_ui = self.__config_value_to_ui_element.get(parameters_config) if parameters_config else None
            
            if profile_model_ui and parameters_ui:
                def load_profile_on_model_change(new_model_value):
                    """Load profile when model changes"""
                    try:
                        # Update the model config value
                        profile_model_config.value = new_model_value
                        
                        # Load profile if it exists
                        service_value = profile_service_config.value
                        if service_value and new_model_value:
                            profile = self._get_profile_manager().get_profile_for_model(service_value, new_model_value)
                            
                            if profile:
                                import json
                                parameters_json = json.dumps(profile.parameters, indent=4)
                                parameters_config.value = parameters_json
                                logging.info(f"Loaded profile for {new_model_value}")
                                return parameters_json
                            else:
                                # Clear parameters if no profile exists
                                parameters_config.value = ""
                                logging.info(f"No profile found for {new_model_value}")
                                return ""
                        else:
                            return ""
                    except Exception as e:
                        logging.error(f"Error loading profile on model change: {e}")
                        return ""
                
                # Set up profile loading when model changes
                profile_model_ui.change(
                    load_profile_on_model_change,
                    inputs=profile_model_ui,
                    outputs=parameters_ui
                )
    
    def __create_model_dropdown(self, model_config: ConfigValue, handler: ModelConfig) -> gr.Dropdown:
        """Create a model dropdown for the given config and handler"""
        service: str = self.__identifier_to_config_value[handler["dependent_config"]].value
        # Choose appropriate secret key file based on service and model type
        if model_config.identifier == 'vision_model':
            secret_key_file = 'IMAGE_SECRET_KEY.txt'
        else:
            from src.llm.key_file_resolver import key_file_resolver
            # Use the first (primary) key file from the resolver
            key_files = key_file_resolver.get_key_files_for_service(service, 'GPT_SECRET_KEY.txt')
            secret_key_file = key_files[0] if key_files else 'GPT_SECRET_KEY.txt'
        default_model = 'meta-llama/llama-3.2-11b-vision-instruct:free' if model_config.identifier == 'vision_model' else 'google/gemma-2-9b-it:free'
        is_vision = True if model_config.identifier == 'vision_model' else False
        model_list = handler["model_list_getter"](service, secret_key_file, default_model, is_vision)
        selected_model = model_config.value
        
        if not model_list.is_model_in_list(selected_model):
            selected_model = model_list.default_model
            # Update the config value to the default model
            model_config.value = selected_model
            
        return gr.Dropdown(
            value=selected_model,                        
            choices=model_list.available_models,
            multiselect=False,
            allow_custom_value=model_list.allows_manual_model_input,
            show_label=False,
            container=False
        )
    
    def __create_tooltip(self, config_value: ConfigValue, is_second_setting: bool = False) -> str:
        """Creates the tooltip HTML for a config value"""
        constraints_html = (
            f'<p class="constraints">' +
            '<br>'.join(c.description for c in config_value.constraints) +
            '</p>' if config_value.constraints else ''
        )
        use_right_aligned_tooltip = is_second_setting or isinstance(config_value, ConfigValueBool)
        tooltip_content = 'tooltip-content-right' if use_right_aligned_tooltip else 'tooltip-content-left'
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
                button = gr.Button(btn_label, variant="primary", size='sm')
                # Ensure the button click event is properly connected
                if hasattr(button, "_id"):
                    button.click(btn_action, outputs=input_ui)
                else:
                    # Fallback: try connecting without checking _id
                    try:
                        button.click(btn_action, outputs=input_ui)
                    except Exception as e:
                        logging.error(f"Failed to connect button '{btn_label}' click event: {e}")
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

        # Handle row grouping
        if config_value.row_group is not None:
            # Check if we need to render a different pending row group first
            if self.__last_row_group is not None and self.__last_row_group != config_value.row_group:
                self.__render_row_group(self.__last_row_group)
            
            # Add to the current row group
            if config_value.row_group not in self.__row_groups:
                self.__row_groups[config_value.row_group] = []
            self.__row_groups[config_value.row_group].append(current_setting)
            self.__last_row_group = config_value.row_group
            return
        
        # If we have a pending row group, render it now before processing this non-grouped item
        if self.__last_row_group is not None:
            self.__render_row_group(self.__last_row_group)
            self.__last_row_group = None
        
        # Legacy share_row tag support (for backwards compatibility)
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
            use_right_aligned_tooltip = is_second_setting or isinstance(config_value, ConfigValueBool)
            tooltip_content = 'tooltip-content-right' if use_right_aligned_tooltip else 'tooltip-content-left'
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

    def __render_row_group(self, group_id: str):
        """Render all settings in a row group"""
        if group_id in self.__row_groups and len(self.__row_groups[group_id]) > 0:
            settings = self.__row_groups[group_id]
            with gr.Row():
                for i, setting in enumerate(settings):
                    is_second_setting = i > 0
                    with gr.Column(variant="panel", scale=1):
                        components = self.__create_setting_components(setting, is_second_setting)
                        self.__identifier_to_config_value[setting.config_value.identifier] = setting.config_value
                        self.__config_value_to_ui_element[setting.config_value] = components.input_ui
            # Clear the group after rendering
            del self.__row_groups[group_id]

    def visit_ConfigValueGroup(self, config_value: ConfigValueGroup):
        if not config_value.is_hidden:
            if config_value.description and config_value.name == "Model Profiles":
                gr.Markdown(config_value.description)
            
            has_advanced_values = False
            has_basic_values = False
            regular_settings = []
            basic_settings = []
            advanced_settings = []
            for cf in config_value.value:
                if not cf.is_hidden:
                    if ConfigValueTag.advanced in cf.tags:
                        advanced_settings.append(cf)
                        has_advanced_values = True
                    elif ConfigValueTag.basic in cf.tags:
                        basic_settings.append(cf)
                        has_basic_values = True
                    else:
                        regular_settings.append(cf)

            # Render basic settings in an accordion
            if has_basic_values:
                with gr.Accordion(label="Basic Settings", open=False):
                    for cf in basic_settings:
                        cf.accept_visitor(self)
                    
                    # Render any pending row group in basic section
                    if self.__last_row_group is not None:
                        self.__render_row_group(self.__last_row_group)
                        self.__last_row_group = None
                    
                    # Render any remaining row groups in basic section
                    for group_id in list(self.__row_groups.keys()):
                        self.__render_row_group(group_id)

            for i, cf in enumerate(regular_settings):
                cf.accept_visitor(self)
            
            # Render any pending row group after processing regular settings
            if self.__last_row_group is not None:
                self.__render_row_group(self.__last_row_group)
                self.__last_row_group = None
            
            # Render any remaining row groups (shouldn't happen but just in case)
            for group_id in list(self.__row_groups.keys()):
                self.__render_row_group(group_id)
            
            if has_advanced_values:
                with gr.Accordion(label="Advanced", open=False):
                    for cf in advanced_settings:
                        cf.accept_visitor(self)
                    
                    # Render any pending row group in advanced section
                    if self.__last_row_group is not None:
                        self.__render_row_group(self.__last_row_group)
                        self.__last_row_group = None
                    
                    # Render any remaining row groups in advanced section
                    for group_id in list(self.__row_groups.keys()):
                        self.__render_row_group(group_id)

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
            
            # Special handling for example profile JSON - make it readonly
            if config_value.identifier == "example_profile_json":
                return gr.Text(
                    value=config_value.value,
                    show_label=False,
                    container=False,
                    lines=15,  # Show all the JSON
                    max_lines=15,
                    elem_classes="multiline-textbox",
                    interactive=False  # Make it readonly
                )
            
            # Special handling for profile parameters - always allow multi-line
            if config_value.identifier == "profile_parameters":
                return gr.Text(
                    value=config_value.value,
                    show_label=False,
                    container=False,
                    lines=10,  # Start with 10 lines for JSON input
                    max_lines=20,  # Allow up to 20 lines
                    elem_classes="multiline-textbox",
                    placeholder="Enter JSON parameters here...\nExample:\n{\n  \"temperature\": 0.8,\n  \"max_tokens\": 250\n}"
                )
            
            # Special handling for LLM pools - always allow multi-line
            if config_value.identifier in ["llm_pool_one_on_one", "llm_pool_multi_npc"]:
                pool_type = "one-on-one" if config_value.identifier == "llm_pool_one_on_one" else "multi-NPC"
                return gr.Text(
                    value=config_value.value,
                    show_label=False,
                    container=False,
                    lines=8,  # Start with 8 lines for JSON pool input
                    max_lines=15,  # Allow up to 15 lines
                    elem_classes="multiline-textbox",
                    placeholder=f"Enter JSON array for {pool_type} LLM pool...\nExample:\n[\n  {{\"service\": \"OpenRouter\", \"model\": \"deepseek/deepseek-chat\"}},\n  {{\"service\": \"OpenAI\", \"model\": \"gpt-4o-mini\"}}\n]"
                )
            
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
        
        # Add reload button for character data reload functionality and model profile buttons
        additional_buttons = []
        if config_value.identifier == "reload_character_data":
            def on_reload_click() -> str:
                """Handle the reload character data button click"""
                global _game_manager_ref
                try:
                    # Log that the button was clicked
                    logging.info("Attempting character data reload via UI button...")
                    
                    # Use the global game manager reference
                    if _game_manager_ref:
                        logging.info("Game manager reference found. Calling reload_character_data()...")
                        success = _game_manager_ref.reload_character_data()
                        if success:
                            logging.info("Character data reloaded successfully!")
                            return " Character data reloaded successfully!"
                        else:
                            logging.error("reload_character_data() returned False.")
                            return " Reload failed. Check logs for details."
                    else:
                        logging.warning("Button clicked, but game manager reference is not set. The game might not have been started.")
                        return " Game not started. Please start the game first."
                        
                except Exception as e:
                    logging.error(f"Error during character data reload: {e}", exc_info=True)
                    return f" An error occurred: {str(e)}"

            additional_buttons.append(("Reload", on_reload_click))

        elif config_value.identifier == "save_summary_now":
            def on_save_summary_click() -> str:
                """Trigger summary/log saving without ending the current conversation."""
                global _game_manager_ref
                try:
                    if _game_manager_ref:
                        logging.info("Manual summary trigger via UI button (will save summary/log if enabled)...")
                        ok = _game_manager_ref.save_summary_only()
                        if ok:
                            return " Summary/log save triggered (conversation continues)."
                        return " No active conversation to summarize."
                    else:
                        logging.warning("Manual summary clicked, but game manager reference is not set. The game might not have been started.")
                        return " Game not started. Please start the game first."
                except Exception as e:
                    logging.error(f"Error triggering summary-only via UI: {e}", exc_info=True)
                    return f" An error occurred: {str(e)}"

            additional_buttons.append(("Save Summary", on_save_summary_click))
        
        # Add model profile management buttons
        elif config_value.identifier == "profile_parameters":
            def on_save_profile_click() -> str:
                """Handle save profile button click"""
                logging.info("Save Profile button clicked")
                try:
                    # Get values from profile config fields
                    service = self.__identifier_to_config_value.get("profile_selected_service", None)
                    model = self.__identifier_to_config_value.get("profile_selected_model", None)
                    parameters_json = self.__identifier_to_config_value.get("profile_parameters", None)
                    
                    logging.debug(f"Profile save attempt - Service: {service.value if service else 'None'}, Model: {model.value if model else 'None'}")
                    
                    # Check if config values exist
                    if not all([service, model, parameters_json]):
                        logging.error("Missing profile configuration fields")
                        return " Please select Service, Model, and enter Parameters"
                    
                    # Check if values are not empty/default
                    if not service.value or service.value.strip() == "":
                        logging.error("Service not selected")
                        return " Please select a Service"
                    
                    if not model.value or model.value.strip() == "" or model.value == "Select a service first":
                        logging.error("Model not selected") 
                        return " Please select a Model"
                    
                    # Handle empty parameters - allow empty JSON object as default
                    parameters_text = parameters_json.value.strip() if parameters_json.value else ""
                    if not parameters_text:
                        # Default to empty JSON object if no parameters provided
                        parameters_text = "{}"
                        parameters_json.value = parameters_text
                    
                    # Parse JSON parameters
                    try:
                        import json
                        parameters = json.loads(parameters_text)
                        if not isinstance(parameters, dict):
                            logging.error("Parameters is not a JSON object")
                            return " Parameters must be a JSON object"
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON parsing error: {e}")
                        return f" Invalid JSON: {str(e)}"
                    
                    # Create or update the profile
                    success = self._get_profile_manager().create_or_update_profile(
                        service.value,
                        model.value,
                        parameters
                    )
                    
                    if success:
                        logging.info(f"Profile saved successfully for {service.value}/{model.value}")
                        # Update the parameters field with properly formatted JSON
                        formatted_json = json.dumps(parameters, indent=4)
                        parameters_json.value = formatted_json
                        return formatted_json
                    else:
                        logging.error(f"Failed to save profile for {service.value}/{model.value}")
                        return " ❌ Failed to save profile. Check logs for details."
                        
                except Exception as e:
                    logging.error(f"Error saving profile: {e}")
                    # Return current parameters unchanged on error
                    return f" ❌ Error: {str(e)}"
            
            def on_delete_profile_click() -> str:
                """Handle delete profile button click"""
                try:
                    service = self.__identifier_to_config_value.get("profile_selected_service", None)
                    model = self.__identifier_to_config_value.get("profile_selected_model", None)
                    
                    if not all([service, model]):
                        return " Please select Service and Model"
                    
                    # Map display names to short identifiers for profile ID
                    service_map = {
                        "OpenRouter": "or",
                        "NanoGPT": "nano", 
                        "OpenAI": "openai"
                    }
                    service_id = service_map.get(service.value, service.value.lower())
                    profile_id = f"{service_id}:{model.value}"
                    success = self._get_profile_manager().delete_profile(profile_id)
                    
                    if success:
                        logging.info(f"Profile deleted successfully for {service.value}/{model.value}")
                        # Clear parameters to default
                        parameters_config = self.__identifier_to_config_value.get("profile_parameters")
                        if parameters_config:
                            default_json = """{
    "max_tokens": 250,
    "temperature": 0.8,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "stop": ["#"]
}"""
                            parameters_config.value = default_json
                            return default_json
                    else:
                        logging.error(f"Failed to delete profile for {service.value}/{model.value} (may not exist)")
                        # Return current parameters unchanged
                        parameters_config = self.__identifier_to_config_value.get("profile_parameters")
                        return parameters_config.value if parameters_config else ""
                        
                except Exception as e:
                    logging.error(f"Error deleting profile: {e}")
                    # Return current parameters unchanged on error
                    parameters_config = self.__identifier_to_config_value.get("profile_parameters")
                    return parameters_config.value if parameters_config else ""
            
            additional_buttons.append(("Save", on_save_profile_click))
            additional_buttons.append(("Delete", on_delete_profile_click))
            
        self.__create_config_value_ui_element(config_value, create_input_component, False, True, True, additional_buttons)
    
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
            "multi_npc_model": {
                "dependent_config": "multi_npc_llm_api",
                "model_list_getter": ClientBase.get_model_list,
            },
            "summary_model": {
                "dependent_config": "summary_llm_api",
                "model_list_getter": ClientBase.get_model_list,
            },
            "profile_selected_model": {
                "dependent_config": "profile_selected_service",
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
                # Choose appropriate secret key file based on service and model type
                if config_value.identifier == 'vision_model':
                    secret_key_file = 'IMAGE_SECRET_KEY.txt'
                else:
                    from src.llm.key_file_resolver import key_file_resolver
                    # Use the first (primary) key file from the resolver
                    key_files = key_file_resolver.get_key_files_for_service(service, 'GPT_SECRET_KEY.txt')
                    secret_key_file = key_files[0] if key_files else 'GPT_SECRET_KEY.txt'
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
        
        # Track model dependencies for later setup
        handler = special_handlers.get(config_value.identifier)
        if handler:
            self.__model_dependencies.append((config_value.identifier, handler["dependent_config"]))

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


import typing
import gradio as gr
from typing import Any, Callable, TypeVar
import logging

from src.llm.openai_client import openai_client
from src.config.types.config_value_path import ConfigValuePath
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_float import ConfigValueFloat
from src.config.types.config_value_selection import ConfigValueSelection
from src.config.types.config_value_string import ConfigValueString
from src.config.config_value_constraint import ConfigValueConstraintResult
from src.config.types.config_value import ConfigValue, ConvigValueTag
from src.config.types.config_value_group import ConfigValueGroup
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_visitor import ConfigValueVisitor

class SettingsUIConstructor(ConfigValueVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.__identifier_to_config_value: dict[str, ConfigValue] = {}
        self.__config_value_to_ui_element: dict[ConfigValue, Any] = {}
    
    @property
    def config_value_to_ui_element(self) -> dict[ConfigValue, gr.Column]:
        return self.__config_value_to_ui_element
    
    def __create_config_value_ui_element(self, config_value: ConfigValue, create_input_component: Callable[[ConfigValue],Any], update_on_change: bool = True, update_on_submit: bool = False, update_on_blur: bool = False, additional_buttons: list[tuple[str, Callable[[], Any]]] = []):
        def on_change(new_value) -> gr.Markdown:
            return self.__on_change(config_value, new_value)
        
        def on_submit(new_value:str) -> gr.Markdown:
            return self.__on_change(config_value, new_value)
       
        def on_blur(new_value:str) -> gr.Markdown: #aka lose focus
            return self.__on_change(config_value, new_value)
        
        def on_reset_click():
            config_value.value = config_value.default_value
            return create_input_component(config_value)
        
        with gr.Column(variant="panel") as panel:
            self.__construct_name_description_constraints(config_value)
            with gr.Row(equal_height=True):
                input_ui = create_input_component(config_value)
                for btn in additional_buttons:
                    gr.Button(btn[0], variant="primary", scale=0).click(btn[1], outputs=input_ui)
                reset_button = gr.Button("Default", scale=0)
                if hasattr(reset_button, "_id"):
                    reset_button.click(on_reset_click, outputs=input_ui)
            error_message = self.__construct_initial_error_message(config_value)
            if hasattr(input_ui, "_id"):
                if update_on_change:
                    input_ui.change(on_change, input_ui, error_message)
                if update_on_submit:
                    input_ui.submit(on_submit, input_ui, error_message)
                if update_on_blur:
                    input_ui.blur(on_blur, input_ui, error_message)                
        self.__identifier_to_config_value[config_value.identifier] = config_value
        self.__config_value_to_ui_element[config_value] = input_ui

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
                gr.Column(scale=1)
    
    def __construct_name_description_constraints(self, config_value: ConfigValue):
        with gr.Row():
            gr.Markdown(f"## {config_value.name}", elem_classes="setting-title")
            gr.Column(scale=1)
        gr.Markdown(value=config_value.description, line_breaks=True)
        constraints_text = ""
        for constraint in config_value.constraints:
            constraints_text += constraint.description + "\n"
        if len(constraints_text) > 0:
            gr.Markdown(value=constraints_text, line_breaks=True)
        
    def __construct_initial_error_message(self, config_value: ConfigValue) -> gr.Markdown:
        result: ConfigValueConstraintResult = config_value.does_value_cause_error(config_value.value)
        return self.__construct_error_message_panel(result.error_message, is_visible=not result.is_success)

    def visit_ConfigValueGroup(self, config_value: ConfigValueGroup):
        if not config_value.is_hidden:            
            has_advanced_values = False
            for cf in config_value.value:
                if not cf.is_hidden:
                    if not ConvigValueTag.advanced in cf.tags:
                        cf.accept_visitor(self)
                    else:
                        has_advanced_values = True
            if has_advanced_values:
                with gr.Accordion(label="Advanced", open=False):
                    for cf in config_value.value:
                        if not cf.is_hidden:
                            if ConvigValueTag.advanced in cf.tags:
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
                        container=False)
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
        def update_model_list() -> gr.Dropdown:
            config_value = self.__identifier_to_config_value["model"]
            return create_input_component(config_value)

        def create_input_component(raw_config_value: ConfigValue) -> gr.Dropdown:
            config_value = typing.cast(ConfigValueSelection, raw_config_value)
            if config_value.identifier != "model":
                return gr.Dropdown(value=config_value.value,                        
                    choices=config_value.options, # type: ignore
                    multiselect=False,
                    allow_custom_value=config_value.allows_custom_value, 
                    show_label=False,
                    container=False)
            else: #special treatment for 'model' because the content of the dropdown needs to reload on change of 'llm_api'
                service: str = self.__identifier_to_config_value["llm_api"].value
                model_list = openai_client.get_model_list(service)
                selected_model = config_value.value
                if not model_list.is_model_in_list(selected_model):
                    selected_model = model_list.default_model
                return gr.Dropdown(value=selected_model,                        
                    choices= model_list.available_models, # type: ignore
                    multiselect=False,
                    allow_custom_value=model_list.allows_manual_model_input,
                    show_label=False,
                    container=False)
        
        additional_buttons: list[tuple[str, Callable[[], Any]]] = []
        if config_value.identifier == "model":
            additional_buttons = [("Update list", update_model_list)]
        self.__create_config_value_ui_element(config_value, create_input_component,additional_buttons=additional_buttons)

    def visit_ConfigValuePath(self, config_value: ConfigValuePath):
        def on_pick_click() -> str | None:
            return config_value.show_file_or_path_picker_dialog()

        def create_input_component(raw_config_value: ConfigValue) -> gr.Text:
            config_value = typing.cast(ConfigValuePath, raw_config_value)
            return gr.Text(value=config_value.value, show_label=False, container=False)
        
        self.__create_config_value_ui_element(config_value, create_input_component, True, True, True, [("Pick", on_pick_click)])


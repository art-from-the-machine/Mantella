import gradio as gr
from typing import Awaitable, Callable, Optional, TypeVar, Union

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
        self.__all_ui_elements: dict[ConfigValue, gr.Column] = {}
    
    @property
    def All_ui_elements(self) -> dict[ConfigValue, gr.Column]:
        return self.__all_ui_elements


    T = TypeVar('T')
    def __on_change(self, config_value: ConfigValue[T], new_value: T) -> gr.Column | None:
        result: ConfigValueConstraintResult = config_value.does_value_cause_error(new_value)
        if result.Is_success:
            config_value.Value = new_value
        else:
            return self.__construct_error_message_panel(result.Error_message, is_visible=True)
        
    def __construct_error_message_panel(self, message: str, is_visible: bool) -> gr.Column | None:
        with gr.Column(variant="panel", visible=is_visible, elem_classes="constraint-violation") as result:
            gr.Markdown(f"{message}")

    def _construct_badges(self, config_value: ConfigValue):
        if len(config_value.Tags) > 0:
            with gr.Row():
                for tag in config_value.Tags:
                    gr.HTML(f"<b>{str(tag).upper()}</b>", elem_classes=["badge",f"badge-{tag}"])
                gr.Column(scale=1)

    
    def __construct_name_description_constraints(self, config_value: ConfigValue):
        with gr.Row():
            gr.Markdown(f"## {config_value.Name}", elem_classes="setting-title")
            gr.Column(scale=1)
        #self._construct_badges(config_value)
        gr.Markdown(value=config_value.Description, line_breaks=True)
        constraints_text = ""
        for constraint in config_value.Constraints:
            constraints_text += constraint.Description + "\n"
        if len(constraints_text) > 0:
            gr.Markdown(value=constraints_text, line_breaks=True)
        
    def __construct_initial_error_message(self, config_value: ConfigValue) -> gr.Column | None:
        result: ConfigValueConstraintResult = config_value.does_value_cause_error(config_value.Value)
        return self.__construct_error_message_panel(result.Error_message, is_visible=not result.Is_success)
        # return gr.Markdown(result.Error_message, visible=not result.Is_success)

    def visit_ConfigValueGroup(self, config_value: ConfigValueGroup):
        if not config_value.Is_hidden:            
            gr.Markdown(f"# {config_value.Name}")
            gr.Markdown(value=config_value.Description, line_breaks=True)
            has_advanced_values = False
            for cf in config_value.Value:
                if not cf.Is_hidden:
                    if not ConvigValueTag.advanced in cf.Tags:
                        cf.accept_visitor(self)
                    else:
                        has_advanced_values = True
            if has_advanced_values:
                with gr.Accordion(label="Advanced", open=False):
                    for cf in config_value.Value:
                        if not cf.Is_hidden:
                            if ConvigValueTag.advanced in cf.Tags:
                                cf.accept_visitor(self)

    def visit_ConfigValueInt(self, config_value: ConfigValueInt):
        def on_change(new_value:int) -> gr.Column | None:
            return self.__on_change(config_value, new_value)
        
        with gr.Column(variant="panel") as panel:
            self.__construct_name_description_constraints(config_value)
            input_ui = gr.Number(value=config_value.Value, 
                    minimum=config_value.MinValue, 
                    maximum=config_value.MaxValue, 
                    precision=0,
                    show_label=False, 
                    container=False)            
            error_message = self.__construct_initial_error_message(config_value)
            if hasattr(input_ui, "_id"):
                input_ui.change(on_change, input_ui, error_message)
        self.__all_ui_elements[config_value] = panel

    def visit_ConfigValueFloat(self, config_value: ConfigValueFloat):
        def on_change(new_value:float) -> gr.Column | None:
            return self.__on_change(config_value, new_value)
        
        with gr.Column(variant="panel") as panel:
            self.__construct_name_description_constraints(config_value)
            input_ui = gr.Number(value=config_value.Value, 
                    minimum=config_value.MinValue, 
                    maximum=config_value.MaxValue, 
                    precision=2,
                    show_label=False, 
                    container=False,
                    step=0.1)
            error_message = self.__construct_initial_error_message(config_value)
            if hasattr(input_ui, "_id"):
                input_ui.change(on_change, input_ui, error_message)
        self.__all_ui_elements[config_value] = panel

    def visit_ConfigValueBool(self, config_value: ConfigValueBool):
        def on_change(new_value:bool) -> gr.Column | None:
            return self.__on_change(config_value, new_value)
        
        with gr.Column(variant="panel") as panel:
            self.__construct_name_description_constraints(config_value)
            input_ui = gr.Checkbox(label = config_value.Name,
                                    value=config_value.Value,
                                    show_label=False, 
                                    container=False,elem_classes="checkboxelement")
            error_message = self.__construct_initial_error_message(config_value)
            if hasattr(input_ui, "_id"):
                input_ui.change(on_change, input_ui, error_message)
        self.__all_ui_elements[config_value] = panel

    def visit_ConfigValueString(self, config_value: ConfigValueString):
        def on_change(new_value:str) -> gr.Column | None:
            return self.__on_change(config_value, new_value)
        
        with gr.Column(variant="panel") as panel:
            self.__construct_name_description_constraints(config_value)
            count_rows = self.__count_rows_in_text(config_value.Value)
            if count_rows == 1:
                input_ui = gr.Text(value=config_value.Value,
                        show_label=False, 
                        container=False)
            else:
                input_ui = gr.Text(value=config_value.Value,
                        show_label=False, 
                        container=False,
                        lines= count_rows,
                        elem_classes="multiline-textbox")
            error_message = self.__construct_initial_error_message(config_value)
            if hasattr(input_ui, "_id"):
                input_ui.change(on_change, input_ui, error_message)
        self.__all_ui_elements[config_value] = panel
    
    def __count_rows_in_text(self, text: str) -> int:
        count_CRLF = text.count("\r\n")
        count_newline = text.count("\n")
        return count_CRLF + (count_newline - count_CRLF) + 1

    def visit_ConfigValueSelection(self, config_value: ConfigValueSelection):
        def on_change(new_value:str) -> gr.Column | None:
            return self.__on_change(config_value, new_value)
        
        with gr.Column(variant="panel") as panel:
            self.__construct_name_description_constraints(config_value)
            input_ui = gr.Dropdown(value=config_value.Value,                        
                    choices=config_value.Options, # type: ignore
                    multiselect=False,
                    allow_custom_value=False, 
                    show_label=False,
                    container=False)
            error_message = self.__construct_initial_error_message(config_value)
            if hasattr(input_ui, "_id"):
                input_ui.change(on_change, input_ui, error_message)
        self.__all_ui_elements[config_value] = panel

    def visit_ConfigValuePath(self, config_value: ConfigValuePath):
        def on_change(new_value:str) -> gr.Column | None:
            return self.__on_change(config_value, new_value)
        
        def on_click() -> str | None:
            return config_value.show_file_or_path_picker_dialog()
        
        with gr.Column(variant="panel") as panel:
            self.__construct_name_description_constraints(config_value)
            with gr.Row(equal_height=True):
                input_ui = gr.Text(value=config_value.Value, show_label=False, container=False)
                select_path_button = gr.Button("Pick", scale=0, variant="primary")
                if hasattr(select_path_button, "_id"):
                    select_path_button.click(on_click, outputs=input_ui)
            error_message = self.__construct_initial_error_message(config_value)
            if hasattr(input_ui, "_id"):
                input_ui.change(on_change, input_ui, error_message)
        self.__all_ui_elements[config_value] = panel 

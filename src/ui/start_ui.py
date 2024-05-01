from fastapi import FastAPI
import webbrowser
import gradio as gr
from src.config.types.config_value import ConfigValue
from src.http.routes.routeable import routeable
from src.ui.settings_ui_constructor import SettingsUIConstructor


class StartUI(routeable):
    def __init__(self,definitions: list[ConfigValue], port: int) -> None:
        self.__constructor = SettingsUIConstructor()
        self.__definitions = definitions
        self.__port = port

        self.__ui: gr.Blocks = gr.Blocks(title="Mantella", fill_height=True, analytics_enabled=False, theme= self.__get_theme())
        with self.__ui:
            with gr.Tab("Settings"):
                self.__generate_settings_page()
            with gr.Tab("Chat with NPCs", interactive=False):
                self.__generate_chat_page()
            with gr.Tab("NPC editor", interactive=False):
                self.__generate_character_editor_page()

    def __generate_settings_page(self):
        for cf in self.__definitions:
            with gr.Tab(cf.Name):
                cf.accept_visitor(self.__constructor)
    
    def __generate_chat_page(self):
        return gr.Blocks(analytics_enabled=False)
    
    def __generate_character_editor_page(self):
        return gr.Blocks(analytics_enabled=False) 

    def __get_theme(self):
        return gr.themes.Soft(primary_hue="green",
                            secondary_hue="green",
                            neutral_hue="zinc",
                            font=['Montserrat', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                            font_mono=['IBM Plex Mono', 'ui-monospace', 'Consolas', 'monospace']).set(
                                input_text_size='*text_xl',
                                input_padding='*spacing_lg',
                                checkbox_label_text_size='*text_xl'
                            )

    
    def add_route_to_server(self, app: FastAPI):
        gr.mount_gradio_app(app,
                            self.__ui,
                            path="/ui",
                            favicon_path="./docs/_static/img/mantella_favicon.ico")
        
        webbrowser.open(f'http://localhost:{str(self.__port)}/ui', new=2)
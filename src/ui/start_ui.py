from fastapi import FastAPI
from fastapi.responses import FileResponse
import webbrowser
import gradio as gr
from src.config.config_loader import ConfigLoader
from src.http.routes.routeable import routeable
from src.ui.settings_ui_constructor import SettingsUIConstructor
import logging

class StartUI(routeable):
    BANNER = "docs/_static/img/mantella_banner.png"
    def __init__(self, config: ConfigLoader) -> None:
        super().__init__(config, False)
        self.__constructor = SettingsUIConstructor()

    def create_main_block(self) -> gr.Blocks:
        with gr.Blocks(title="Mantella", fill_height=True, analytics_enabled=False, theme= self.__get_theme(), css=self.__load_css()) as main_block:
            with gr.Tab("Settings") as tabs:
                settings_page = self.__generate_settings_page()
            with gr.Tab("Chat with NPCs", interactive=False):
                self.__generate_chat_page()
            with gr.Tab("NPC editor", interactive=False):
                self.__generate_character_editor_page()
        return main_block

    def __generate_settings_page(self) -> gr.Column:
        with gr.Column() as settings:
            for cf in self._config.definitions.base_groups:
                if not cf.is_hidden:
                    with gr.Tab(cf.name):
                        cf.accept_visitor(self.__constructor)
        return settings
    
    def __generate_chat_page(self):
        return gr.Column()
    
    def __generate_character_editor_page(self):
        return gr.Column() 

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
        @app.get("/favicon.ico")
        async def favicon():
            return FileResponse("Mantella.ico")

        gr.mount_gradio_app(app,
                            self.create_main_block(),
                            path="/ui")
        
        link = f'http://localhost:{str(self._config.port)}/ui?__theme=dark'
        logging.info(f'Mantella settings can be changed via this link: {link}')
        if self._config.auto_launch_ui == True:
            webbrowser.open(link, new=2)
    
    def __load_css(self):
        with open('src/ui/style.css', 'r') as file:
            css_content = file.read()
        return css_content
    
    def _setup_route(self):
        pass

    
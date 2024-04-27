from fastapi import FastAPI
import webbrowser
import gradio as gr

from src.config.types.config_value import ConfigValue
from src.ui.settings_ui_constructor import SettingsUIConstructor


class SettingsUI:
    def __init__(self, definitions: list[ConfigValue],port: int) -> None:
        constructor: SettingsUIConstructor = SettingsUIConstructor()
        
        self.__port = port
        self.__ui: gr.Blocks = gr.Blocks(analytics_enabled=False)
        with self.__ui:
            for cf in definitions:
                cf.accept_visitor(constructor)

    def add_ui(self, app: FastAPI):
        pass
        # app.native.window_args['resizable'] = False
        # app.native.start_args['debug'] = True

        # ui.run(host="0.0.0.0",reload=False,native=True, window_size=(400, 300), fullscreen=False)
        gr.mount_gradio_app(app,
                            self.__ui,
                            path="/ui",
                            favicon_path="docs/_static/img/mantella_favicon.ico")
        
        webbrowser.open(f'http://localhost:{str(self.__port)}/ui', new=2)

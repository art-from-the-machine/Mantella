from src.ui.start_ui import StartUI
from src.ui.settings_ui_constructor import SettingsUIConstructor
from src.config.config_loader import ConfigLoader

def test_start_ui_initialization(default_config: ConfigLoader):
    ui: StartUI = StartUI(default_config)
    assert ui._config == default_config
    assert isinstance(ui._StartUI__constructor, SettingsUIConstructor)
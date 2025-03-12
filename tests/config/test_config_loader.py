from src.config.config_loader import ConfigLoader

def test_init_new_config_ini(tmp_path):
    '''Ensure ConfigLoader can create a new config file for paths with non-existent config file'''
    ConfigLoader(tmp_path)
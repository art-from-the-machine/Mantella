import configparser

class ConfigLoader:
    def __init__(self, file_name='config.ini'):
        config = configparser.ConfigParser()
        config.read(file_name)

        self.language = config['Language']['language']
        self.end_conversation_keyword = config['Language']['end_conversation_keyword']
        self.goodbye_npc_response = config['Language']['goodbye_npc_response']
        self.collecting_thoughts_npc_response = config['Language']['collecting_thoughts_npc_response']

        self.game_path = config['Paths']['skyrim_folder']
        self.xvasynth_path = config['Paths']['xvasynth_folder']
        self.mod_path = config['Paths']['mod_folder']+'\Sound\Voice\Mantella.esp'

        self.whisper_model = config['Microphone']['model_size']
        self.whisper_process_device = config['Microphone']['process_device']
        self.audio_threshold = config['Microphone']['audio_threshold']
        self.pause_threshold = float(config['Microphone']['pause_threshold'])
        self.listen_timeout = int(config['Microphone']['listen_timeout'])

        self.max_response_sentences = int(config['LanguageModel']['max_response_sentences'])
        self.llm = config['LanguageModel']['model']

        self.subtitles_enabled = config['HUD']['subtitles']

        self.debug_mode = config['Debugging']['debugging']
        self.play_audio_from_script = config['Debugging']['play_audio_from_script']
        self.debug_character_name = config['Debugging']['debugging_npc']
        self.debug_use_mic = config['Debugging']['use_mic']
        self.default_player_response = config['Debugging']['default_player_response']
        self.debug_exit_on_first_exchange = config['Debugging']['exit_on_first_exchange']

        self.prompt = config['Prompt']['prompt']
import traceback
import src.tts as tts
import src.stt as stt
import logging
import os
import src.output_manager as output_manager
import src.game_manager as game_manager
import src.character_manager as character_manager
import src.characters_manager as characters_manager
import src.setup as setup
from src.conversation.conversation import conversation
from src.conversation.context import context
from src.remember.remembering import remembering
from src.remember.summaries import summaries

# Added initial setup to make sure no variable is potentially unbound
game_state_manager = None

try:
    config, character_df, language_info, client, FO4_Voice_folder_and_models_df = setup.initialise(
        config_file='config.ini',
        logging_file='logging.log', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        #Additional df_file added to support Fallout 4 data/fallout4_characters.csv, keep in mind there's also a new file in data\FO4_data\FO4_Voice_folder_XVASynth_matches.csv
        character_df_files=('data/skyrim_characters.csv', 'data/fallout4_characters.csv'), 
        language_file='data/language_support.csv',
        FO4_XVASynth_file='data\\FO4_data\\FO4_Voice_folder_XVASynth_matches.csv'
    )

    token_limit = client.token_limit
    token_limit_percent: float = 0.45
    mantella_version = '0.11'
    logging.info(f'\nMantella v{mantella_version}')

    # Check if the mic setting has been configured in MCM
    # If it has, use this instead of the config.ini setting, otherwise take the config.ini value
    if os.path.exists(f'{config.game_path}/_mantella_microphone_enabled.txt'):
        with open(f'{config.game_path}/_mantella_microphone_enabled.txt', 'r', encoding='utf-8') as f:
            mcm_mic_enabled = f.readline().strip()
        config.mic_enabled = '1' if mcm_mic_enabled == 'TRUE' else '0'

    synthesizer = tts.Synthesizer(config)
    game_state_manager = game_manager.GameStateManager(config.game_path)
    chat_manager = output_manager.ChatManager(game_state_manager, config, synthesizer, client)
    transcriber = stt.Transcriber(game_state_manager, config, client.api_key)    
    rememberer: remembering = summaries(config.memory_prompt, config.resummarize_prompt, client, language_info['language'])
    chat_manager.pygame_initialize()
    
    while True:
        # clear _mantella_ files in Skyrim or Fallout4 folder
        character_name, character_id, location, in_game_time = game_state_manager.reset_game_info()

        logging.info('\nConversations not starting when you select an NPC? See here:\nhttps://github.com/art-from-the-machine/Mantella#issues-qa')
        logging.info('\nWaiting for player to select an NPC...')
        game_state_manager.wait_for_conversation_init() #<- wait for init here

        #base setup for conversation
        num_characters_selected = 0
        context_for_conversation = context(config, rememberer, language_info, client, token_limit_percent)

        with open(f'{config.game_path}/_mantella_radiant_dialogue.txt', 'r', encoding='utf-8') as f:
            is_radiant_dialogue = f.readline().strip().lower() == 'true'

        talk = conversation(context_for_conversation, transcriber, game_state_manager, chat_manager, rememberer, is_radiant_dialogue, token_limit, token_limit_percent)

        while True: # Start conversation loop
            with open(f'{config.game_path}/_mantella_actor_count.txt', 'r', encoding='utf-8') as f:
                    try:
                        num_characters_selected = int(f.readline().strip())
                    except:
                        logging.info('Failed to read _mantella_actor_count.txt')

            # check if a new character has been added to conversation
            if num_characters_selected > context_for_conversation.npcs_in_conversation.active_character_count():
                try:
                    # load character when data is available
                    character_info, location, in_game_time, is_generic_npc = game_state_manager.load_game_state(
                        config.debug_mode, config.debug_character_name, character_df, character_name, character_id, location, in_game_time, FO4_Voice_folder_and_models_df
                    )
                except game_manager.CharacterDoesNotExist:
                    game_state_manager.write_game_info('_mantella_end_conversation', 'True')
                    logging.info('Restarting...')
                    continue
                
                context_for_conversation.location = location
                context_for_conversation.ingame_time = int(in_game_time)

                character = character_manager.Character(character_info, language_info['language'], is_generic_npc)
                if num_characters_selected == 1: 
                    #Only automatically preload the voice model for the first character, can't predict who will talk first/next in multi-npc or radiant
                    synthesizer.change_voice(character.voice_model)
                    chat_manager.character_num = 0
                    chat_manager.active_character = character
                game_state_manager.write_game_info('_mantella_character_selection', 'True')
                # if the NPC is from a mod, create the NPC's voice folder and exit Mantella
                chat_manager.setup_voiceline_save_location(character_info['in_game_voice_model'])
                talk.add_character(character)

            with open(f'{config.game_path}/_mantella_end_conversation.txt', 'r', encoding='utf-8') as f:
                if f.readline().strip() == 'true':
                    talk.end()

            # proceed the conversation
            if not talk.proceed():
                break

except Exception as e:
    if isinstance(game_state_manager, game_manager.GameStateManager):
        game_state_manager.write_game_info('_mantella_status', 'Error with Mantella.exe. Please check MantellaSoftware/logging.log')

    logging.error("".join(traceback.format_exception(e)))
    input("Press Enter to exit.")
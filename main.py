import src.tts as tts
import src.stt as stt
import src.chat_response as chat_response
import logging
import src.utils as utils
import sys
import asyncio
import src.output_manager as output_manager
import src.game_manager as game_manager
import src.character_manager as character_manager
import src.setup as setup

async def get_response(input_text, messages, synthesizer, character):
    sentence_queue = asyncio.Queue()
    event = asyncio.Event()
    event.set()

    results = await asyncio.gather(
        chat_manager.process_response(sentence_queue, input_text, messages, synthesizer, character, event), 
        chat_manager.send_response(sentence_queue, event)
    )
    messages, _ = results

    return messages

try:
    config, character_df, language_info, encoding, token_limit = setup.initialise(
        config_file='config.ini',
        logging_file='logging.log', 
        secret_key_file='GPT_SECRET_KEY.txt', 
        character_df_file='data/skyrim_characters.csv', 
        language_file='data/language_support.csv'
    )

    mantella_version = '0.7'
    logging.info(f'\nMantella v{mantella_version}')

    game_state_manager = game_manager.GameStateManager(config.game_path)
    chat_manager = output_manager.ChatManager(game_state_manager, config, encoding)
    transcriber = stt.Transcriber(game_state_manager, config)
    synthesizer = tts.Synthesizer(config)

    while True:
        # clear _mantella_ files in Skyrim folder
        character_name, character_id, location, in_game_time = game_state_manager.reset_game_info()

        logging.info('\nWaiting for player to select an NPC...')
        try:
            # load character when data is available
            character_info, location, in_game_time, is_generic_npc = game_state_manager.load_game_state(
                config.debug_mode, config.debug_character_name, character_df, character_name, character_id, location, in_game_time
            )
        except game_manager.CharacterDoesNotExist:
            game_state_manager.write_game_info('_mantella_end_conversation', 'True')
            logging.info('Restarting...')
            continue

        character = character_manager.Character(character_info, language_info['language'], is_generic_npc)
        context = character.set_context(config.prompt, location, in_game_time)

        tokens_available = token_limit - chat_response.num_tokens_from_messages(context, model=config.llm)
        
        # initiate conversation with character
        try:
            messages = asyncio.run(get_response(f"{language_info['hello']} {character.name}.", context, synthesizer, character.info))
        except tts.VoiceModelNotFound:
            game_state_manager.write_game_info('_mantella_end_conversation', 'True')
            logging.info('Restarting...')
            # if debugging and character name not found, exit here to avoid endless loop
            if (config.debug_mode == '1') & (config.debug_character_name != 'None'):
                sys.exit(0)
            continue

        # debugging variable
        say_goodbye = False
        
        # start back and forth conversation loop until conversation ends
        while True:
            with open(f'{config.game_path}/_mantella_end_conversation.txt', 'r') as f:
                conversation_ended = f.readline().strip()

            if conversation_ended.lower() != 'true':
                transcribed_text, say_goodbye = transcriber.get_player_response(say_goodbye)
                transcript_cleaned = utils.clean_text(transcribed_text)

            # check if conversation has ended again after player input
            with open(f'{config.game_path}/_mantella_end_conversation.txt', 'r') as f:
                conversation_ended = f.readline().strip()

            # check if user is ending conversation
            if (transcriber.activation_name_exists(transcript_cleaned, config.end_conversation_keyword.lower())) or (transcriber.activation_name_exists(transcript_cleaned, 'good bye')) or (conversation_ended.lower() == 'true'):
                game_state_manager.end_conversation(conversation_ended, config, encoding, synthesizer, chat_manager, messages, character, tokens_available)
                break

            # Let the player know that they were heard
            #audio_file = synthesizer.synthesize(character.info['voice_model'], character.info['skyrim_voice_folder'], 'Beep boop. Let me think.')
            #chat_manager.save_files_to_voice_folders([audio_file, 'Beep boop. Let me think.'])

            # add in-game events to player's response
            transcribed_text = game_state_manager.update_game_events(transcribed_text)
            logging.info(f"Text passed to NPC: {transcribed_text}")

            # get character's response
            if transcribed_text:
                messages = asyncio.run(get_response(transcribed_text, messages, synthesizer, character.info))

            # if the conversation is becoming too long, save the conversation to memory and reload
            current_conversation_limit_pct = 0.45
            if chat_response.num_tokens_from_messages(messages[1:], model=config.llm) > (round(tokens_available*current_conversation_limit_pct,0)):
                conversation_summary_file, context, messages = game_state_manager.reload_conversation(config, encoding, synthesizer, chat_manager, messages, character, tokens_available, location, in_game_time)
                # continue conversation
                messages = asyncio.run(get_response(f"{character.info['name']}?", context, synthesizer, character.info))

except Exception as e:
    try:
        game_state_manager.write_game_info('_mantella_error_check', 'True')
    except:
        None

    logging.error(f"Error: {e}")
    input("Press Enter to exit.")
import traceback
import src.tts as tts
import src.stt as stt
import src.chat_response as chat_response
import logging
import src.utils as utils
import sys
import os
import asyncio
import src.output_manager as output_manager
import src.game_manager as game_manager
import src.character_manager as character_manager
import src.characters_manager as characters_manager
import src.setup as setup

async def main(): 
    async def get_response(input_text, messages, synthesizer, characters, radiant_dialogue):
        sentence_queue = asyncio.Queue()
        event = asyncio.Event()
        event.set()

        results = await asyncio.gather(
            chat_manager.process_response(sentence_queue, input_text, messages, synthesizer, characters, radiant_dialogue, event), 
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

        mantella_version = '0.10'
        logging.info(f'\nMantella v{mantella_version}')

        # Check if the mic setting has been configured in MCM
        # If it has, use this instead of the config.ini setting, otherwise take the config.ini value
        if os.path.exists(f'{config.game_path}/_mantella_microphone_enabled.txt'):
            with open(f'{config.game_path}/_mantella_microphone_enabled.txt', 'r', encoding='utf-8') as f:
                mcm_mic_enabled = f.readline().strip()
            config.mic_enabled = '1' if mcm_mic_enabled == 'TRUE' else '0'

        game_state_manager = game_manager.GameStateManager(config.game_path)
        chat_manager = output_manager.ChatManager(game_state_manager, config, encoding)
        transcriber = stt.Transcriber(game_state_manager, config)
        synthesizer = tts.Synthesizer(config)

        while True:
            # clear _mantella_ files in Skyrim folder
            character_name, character_id, location, in_game_time = game_state_manager.reset_game_info()

            characters = characters_manager.Characters()
            transcriber.call_count = 0 # reset radiant back and forth count

            logging.info('\nConversations not starting when you select an NPC? See here:\nhttps://github.com/art-from-the-machine/Mantella#issues-qa')
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

            character = character_manager.Character(character_info, language_info['language'], is_generic_npc, config.memory_prompt, config.resummarize_prompt)
            synthesizer.change_voice(character.voice_model)
            chat_manager.active_character = character
            chat_manager.character_num = 0
            characters.active_characters[character.name] = character
            game_state_manager.write_game_info('_mantella_character_selection', 'True')
            # if the NPC is from a mod, create the NPC's voice folder and exit Mantella
            restart_required = chat_manager.setup_voiceline_save_location(character_info['in_game_voice_model'])
            if restart_required:
                continue

            with open(f'{config.game_path}/_mantella_radiant_dialogue.txt', 'r', encoding='utf-8') as f:
                radiant_dialogue = f.readline().strip().lower()
                conversation_started_radiant = radiant_dialogue
            
            context = character.set_context(config.prompt, location, in_game_time, characters.active_characters, token_limit, radiant_dialogue)

            tokens_available = token_limit - chat_response.num_tokens_from_messages(context, model=config.llm)
            
            messages = context.copy()
            if radiant_dialogue == "false":
                # initiate conversation with character
                try:
                    messages = await get_response(f"{language_info['hello']} {character.name}.", context, synthesizer, characters, radiant_dialogue)
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
                with open(f'{config.game_path}/_mantella_end_conversation.txt', 'r', encoding='utf-8') as f:
                    conversation_ended = f.readline().strip()

                with open(f'{config.game_path}/_mantella_actor_count.txt', 'r', encoding='utf-8') as f:
                    try:
                        num_characters_selected = int(f.readline().strip())
                    except:
                        logging.info('Failed to read _mantella_actor_count.txt')

                # check if new character has been added to conversation
                if num_characters_selected > characters.active_character_count():
                    try:
                        # load character when data is available
                        character_info, location, in_game_time, is_generic_npc = game_state_manager.load_game_state(
                            config.debug_mode, config.debug_character_name, character_df, character_name, character_id, location, in_game_time
                        )
                    except game_manager.CharacterDoesNotExist:
                        game_state_manager.write_game_info('_mantella_end_conversation', 'True')
                        logging.info('Restarting...')
                        continue

                    messages_wo_system_prompt = messages[1:]
                    # add character name before each response to be consistent with the multi-NPC format
                    last_assistant_idx = None
                    for idx, message in enumerate(messages_wo_system_prompt):
                        if message['role'] == 'assistant':
                            last_assistant_idx = idx
                            if characters.active_character_count() == 1:
                                message['content'] = character.name+': '+message['content']

                    character = character_manager.Character(character_info, language_info['language'], is_generic_npc, config.memory_prompt, config.resummarize_prompt)
                    characters.active_characters[character.name] = character
                    # if the NPC is from a mod, create the NPC's voice folder and exit Mantella
                    chat_manager.setup_voiceline_save_location(character_info['in_game_voice_model'])

                    # if not radiant dialogue format
                    if radiant_dialogue == "false":
                        # add greeting from newly added NPC to help the LLM understand that this NPC has joined the conversation
                        for active_character in characters.active_characters:
                            if active_character != character.name: 
                                # existing NPCs greet the new NPC
                                messages_wo_system_prompt[last_assistant_idx]['content'] += f"\n{active_character}: {language_info['hello']} {character.name}."
                            else: 
                                # new NPC greets the existing NPCs
                                messages_wo_system_prompt[last_assistant_idx]['content'] += f"\n{active_character}: {language_info['hello']}."
                    
                    new_context = character.set_context(config.multi_npc_prompt, location, in_game_time, characters.active_characters, token_limit, radiant_dialogue)

                    # if not radiant dialogue format
                    if radiant_dialogue == "false":
                        new_context.extend(messages_wo_system_prompt)

                    messages = new_context.copy()
                    game_state_manager.write_game_info('_mantella_character_selection', 'True')
                
                # if radiant dialogue, do not run the conversation until all NPCs are loaded (ie actor count > 1)
                if (characters.active_character_count() > 1) or (radiant_dialogue == "false"):
                    # if the conversation was initially radiant but now the player is jumping in, reset the system prompt to include player
                    if (radiant_dialogue == "false") and (conversation_started_radiant == "true"):
                        conversation_started_radiant = "false"
                        messages_wo_system_prompt = messages[1:]

                    # check if radiant dialogue has switched to multi NPC
                    with open(f'{config.game_path}/_mantella_radiant_dialogue.txt', 'r', encoding='utf-8') as f:
                        radiant_dialogue = f.readline().strip().lower()
                    
                    transcript_cleaned = ''
                    transcribed_text = None
                    if conversation_ended.lower() != 'true':
                        transcribed_text, say_goodbye = transcriber.get_player_response(say_goodbye, radiant_dialogue)

                        game_state_manager.write_game_info('_mantella_player_input', transcribed_text)

                        transcript_cleaned = utils.clean_text(transcribed_text)

                        # if multi NPC conversation, add "Player:" to beginning of output to clarify to the LLM who is speaking
                        if (characters.active_character_count() > 1) and (radiant_dialogue != "true"):
                            transcribed_text = 'Player: ' + transcribed_text
                        # add in-game events to player's response
                        transcribed_text = game_state_manager.update_game_events(transcribed_text)
                        logging.info(f"Text passed to NPC: {transcribed_text}")

                    # check if conversation has ended again after player input
                    with open(f'{config.game_path}/_mantella_end_conversation.txt', 'r', encoding='utf-8') as f:
                        conversation_ended = f.readline().strip()

                    # check if user is ending conversation
                    if (transcriber.activation_name_exists(transcript_cleaned, config.end_conversation_keyword.lower())) or (transcriber.activation_name_exists(transcript_cleaned, 'good bye')) or (conversation_ended.lower() == 'true'):
                        game_state_manager.end_conversation(conversation_ended, config, encoding, synthesizer, chat_manager, messages, characters.active_characters, tokens_available)
                        break

                    # Let the player know that they were heard
                    #audio_file = synthesizer.synthesize(character.info['voice_model'], character.info['skyrim_voice_folder'], 'Beep boop. Let me think.')
                    #chat_manager.save_files_to_voice_folders([audio_file, 'Beep boop. Let me think.'])

                    # check if NPC is in combat to change their voice tone (if one on one conversation)
                    if characters.active_character_count() == 1:
                        aggro = game_state_manager.load_data_when_available('_mantella_actor_is_in_combat', '').lower()
                        if aggro == 'true':
                            chat_manager.active_character.is_in_combat = 1
                        else:
                            chat_manager.active_character.is_in_combat = 0

                    # get character's response
                    if transcribed_text:
                        messages = await get_response(transcribed_text, messages, synthesizer, characters, radiant_dialogue)

                    # if the conversation is becoming too long, save the conversation to memory and reload
                    current_conversation_limit_pct = 0.45
                    if chat_response.num_tokens_from_messages(messages[1:], model=config.llm) > (round(tokens_available*current_conversation_limit_pct,0)):
                        conversation_summary_file, context, messages = game_state_manager.reload_conversation(config, encoding, synthesizer, chat_manager, messages, characters.active_characters, tokens_available, token_limit, location, in_game_time)
                        # continue conversation
                        messages = await get_response(f"{character.name}?", context, synthesizer, characters, radiant_dialogue)

    except Exception as e:
        try:
            game_state_manager.write_game_info('_mantella_status', 'Error with Mantella.exe. Please check MantellaSoftware/logging.log')
        except:
            None

        logging.error("".join(traceback.format_exception(e)))
        input("Press Enter to exit.")

asyncio.run(main())
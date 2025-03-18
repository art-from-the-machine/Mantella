import src.utils as utils
import logging
from openai.types.chat import ChatCompletionMessageParam
import unicodedata
from src.config.config_loader import ConfigLoader
from src.image.image_manager import ImageManager
from src.llm.client_base import ClientBase
from src.llm.messages import image_message

class ImageClient(ClientBase):
    '''Image class to handle LLM vision
    '''
    @utils.time_it
    def __init__(self, config: ConfigLoader, secret_key_file: str, image_secret_key_file: str) -> None:
        self.__config = config    
        self.__custom_vision_model: bool = config.custom_vision_model

        if self.__custom_vision_model: # if using a custom model for vision, load these custom config values
            setup_values = {'api_url': config.vision_llm_api, 'llm': config.vision_llm, 'llm_params': config.vision_llm_params, 'custom_token_count': config.vision_custom_token_count}
        else: # default to base LLM config values
            setup_values = {'api_url': config.llm_api, 'llm': config.llm, 'llm_params': config.llm_params, 'custom_token_count': config.custom_token_count}
        
        super().__init__(**setup_values, secret_key_files=[image_secret_key_file, secret_key_file])

        if self.__custom_vision_model:
            if self._is_local:
                logging.info(f"Running local vision model")
            else:
                logging.log(23, f"Running Mantella with custom vision model '{config.vision_llm}'")

        self.__end_of_sentence_chars = ['.', '?', '!', ';', '。', '？', '！', '；', '：']
        self.__end_of_sentence_chars = [unicodedata.normalize('NFKC', char) for char in self.__end_of_sentence_chars]

        self.__vision_prompt: str = config.vision_prompt.format(game=config.game.display_name)
        self.__detail: str = "low" if config.low_resolution_mode else "high"
        self.__image_manager: ImageManager | None = ImageManager(config.game, 
                                                config.save_folder, 
                                                config.save_screenshot, 
                                                config.image_quality, 
                                                config.low_resolution_mode, 
                                                config.resize_method, 
                                                config.capture_offset,
                                                config.use_game_screenshots,
                                                config.game_path)
    
    @utils.time_it
    def add_image_to_messages(self, openai_messages: list[ChatCompletionMessageParam], vision_hints: str) -> list[ChatCompletionMessageParam]:
        '''Adds a captured image to the latest user message

        Args:
            openai_messages (list[ChatCompletionMessageParam]): The existing list of messages in the OpenAI format

        Returns:
            list[ChatCompletionMessageParam]: The updated list of messages with the image added
        '''
        image = self.__image_manager.get_image()
        if image is None:
            return openai_messages
        
        if not self.__custom_vision_model:
            # Add the image to the last user message or create a new message if needed
            if openai_messages and openai_messages[-1]['role'] == 'user':
                openai_messages[-1]['content'] = [
                    {"type": "text", "text": openai_messages[-1]['content']},
                    {"type": "image_url", "image_url": {"url":  f"data:image/jpeg;base64,{image}", "detail": self.__detail}}
                ]
            else:
                openai_messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_hints},
                        {"type": "image_url", "image_url": {"url":  f"data:image/jpeg;base64,{image}", "detail": self.__detail}}
                    ]
                })
        else:
            if len(vision_hints) > 0:
                vision_prompt = f"{self.__vision_prompt}\n{vision_hints}"
            else:
                vision_prompt = self.__vision_prompt
            image_msg_instance = image_message(self.__config, image, vision_prompt, self.__detail, True)
            image_transcription = self.request_call(image_msg_instance)
            if image_transcription:
                last_punctuation = max(image_transcription.rfind(p) for p in self.__end_of_sentence_chars)
                # filter transcription to full sentences
                image_transcription = image_transcription if last_punctuation == -1 else image_transcription[:last_punctuation + 1]

                logging.log(23, f"Image transcription: {image_transcription}")

                # Add the image to the last user message or create a new message if needed
                if openai_messages and openai_messages[-1]['role'] == 'user':
                    openai_messages[-1]['content'] = [
                        {"type": "text", "text": f"*{image_transcription}*\n{openai_messages[-1]['content']}"}
                    ]
                else:
                    openai_messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"*{image_transcription}*"}
                        ]
                    })

        return openai_messages
import time
import logging
import re
import string
import sys
import os
from shutil import rmtree
from charset_normalizer import detect


def time_it(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logging.debug(f"Function {func.__name__} took {round(end - start, 5)} seconds to execute")
        return result
    return wrapper


def clean_text(text):
    # Remove all punctuation from the sentence
    text_cleaned = text.translate(str.maketrans('', '', string.punctuation))
    # Remove any extra whitespace
    text_cleaned = re.sub('\s+', ' ', text_cleaned).strip()
    text_cleaned = text_cleaned.lower()

    return text_cleaned


def resolve_path():
    if getattr(sys, 'frozen', False):
        resolved_path = os.path.dirname(sys.executable)
    else:
        resolved_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return resolved_path


def get_file_encoding(file_path) -> str | None:
    with open(file_path,'rb') as f:
        data = f.read()
    encoding = detect(data).get("encoding")
    if isinstance(encoding, str):
        return encoding
    else:
        return None


def cleanup_mei(remove_mei_folders):
    """
    Rudimentary workaround for https://github.com/pyinstaller/pyinstaller/issues/2379
    """
    mei_bundle = getattr(sys, "_MEIPASS", False)

    if mei_bundle:
        dir_mei, current_mei = mei_bundle.split("_MEI")
        mei_files = []
        for file in os.listdir(dir_mei):
            if file.startswith("_MEI") and not file.endswith(current_mei):
                mei_files.append(file)
        
        if (len(mei_files) > 0):
            if (remove_mei_folders == '1'):
                file_removed = 0
                for file in mei_files:
                    try:
                        rmtree(os.path.join(dir_mei, file))
                        file_removed += 1
                    except PermissionError:  # mainly to allow simultaneous pyinstaller instances
                        pass
                logging.info(f'{file_removed} previous runtime folder(s) cleaned up from {dir_mei}')
            else:
                logging.warn(f"Warning: {len(mei_files)} previous Mantella.exe runtime folder(s) found in {dir_mei}. See MantellaSoftware/config.ini's remove_mei_folders setting for more information.")
        


def get_time_group(in_game_time):
    in_game_time = int(in_game_time)

    if in_game_time <= 4:
        time_group = 'at night'
    elif in_game_time <= 7:
        # NPCs wake up between 6 and 8
        time_group = 'in the early morning'
    elif in_game_time <= 11:
        # shops open at 8
        time_group = 'in the morning'
    elif in_game_time <= 14:
        time_group = 'in the afternoon'
    elif in_game_time <= 19:
        time_group = 'in the early evening'
    elif in_game_time <= 21:
        # shops shut at 8
        time_group = 'in the late evening'
    elif in_game_time <= 24:
        # NPCs sleep between 8 and 10
        time_group = 'at night'
    
    return time_group


def get_model_token_limits():
    token_limit_dict = {
        'auto': 128_000,
        'nous-capybara-7b:free': 4096,
        'mistral-7b-instruct:free': 32_768,
        'mythomist-7b:free': 32_768,
        'toppy-m-7b:free': 4096,
        'cinematika-7b:free': 8000,
        'gemma-7b-it:free': 8192,
        'bagel-34b': 8000,
        'psyfighter-13b': 4096,
        'psyfighter-13b-2': 4096,
        'noromaid-mixtral-8x7b-instruct': 8000,
        'nous-hermes-llama2-13b': 4096,
        'codellama-34b-instruct': 8192,
        'phind-codellama-34b': 4096,
        'neural-chat-7b': 4096,
        'nous-hermes-2-mixtral-8x7b-dpo': 32_000,
        'nous-hermes-2-mixtral-8x7b-sft': 32_000,
        'llava-13b': 2048,
        'nous-hermes-2-vision-7b': 4096,
        'llama-2-13b-chat': 4096,
        'synthia-70b': 8192,
        'mythalion-13b': 8192,
        'mythomax-l2-13b': 4096,
        'xwin-lm-70b': 8192,
        'goliath-120b': 6144,
        'noromaid-20b': 8192,
        'mythomist-7b': 32768,
        'remm-slerp-l2-13b:extended': 6144,
        'mythomax-l2-13b:extended': 8192,
        'weaver': 8000,
        'nous-capybara-7b': 4096,
        'codellama-70b-instruct': 2048,
        'openhermes-2-mistral-7b': 4096,
        'openhermes-2.5-mistral-7b': 4096,
        'remm-slerp-l2-13b': 4096,
        'toppy-m-7b': 4096,
        'cinematika-7b': 8000,
        'yi-34b-chat': 4096,
        'yi-34b': 4096,
        'yi-6b': 4096,
        'stripedhyena-nous-7b': 32_768,
        'stripedhyena-hessian-7b': 32_768,
        'mixtral-8x7b': 32_768,
        'nous-hermes-yi-34b': 4096,
        'nous-hermes-2-mistral-7b-dpo': 8192,
        'mistral-7b-openorca': 8192,
        'zephyr-7b-beta': 4096,
        'gpt-3.5-turbo': 4095,
        'gpt-3.5-turbo-0125': 16_385,
        'gpt-3.5-turbo-16k': 16_385,
        'gpt-4-turbo-preview': 128_000,
        'gpt-4': 8191,
        'gpt-4-32k': 32_767,
        'gpt-4-vision-preview': 128_000,
        'gpt-3.5-turbo-instruct': 4095,
        'palm-2-chat-bison': 36_864,
        'palm-2-codechat-bison': 28_672,
        'palm-2-chat-bison-32k': 131_072,
        'palm-2-codechat-bison-32k': 131_072,
        'gemini-pro': 131_040,
        'gemini-pro-vision': 65_536,
        'pplx-70b-online': 4096,
        'pplx-7b-online': 4096,
        'pplx-7b-chat': 8192,
        'pplx-70b-chat': 4096,
        'sonar-small-chat': 16_384,
        'sonar-medium-chat': 16_384,
        'sonar-small-online': 12_000,
        'sonar-medium-online': 12_000,
        'claude-3-opus': 200_000,
        'claude-3-sonnet': 200_000,
        'claude-3-haiku': 200_000,
        'claude-3-opus:beta': 200_000,
        'claude-3-sonnet:beta': 200_000,
        'claude-3-haiku:beta': 200_000,
        'llama-2-70b-chat': 4096,
        'nous-capybara-34b': 32_768,
        'airoboros-l2-70b': 4096,
        'chronos-hermes-13b': 4096,
        'mistral-7b-instruct': 32_768,
        'openchat-7b': 8192,
        'lzlv-70b-fp16-hf': 4096,
        'mixtral-8x7b-instruct': 32_768,
        'dolphin-mixtral-8x7b': 32_000,
        'rwkv-5-world-3b': 10_000,
        'rwkv-5-3b-ai-town': 10_000,
        'eagle-7b': 10_000,
        'gemma-7b-it': 8192,
        'claude-2': 200_000,
        'claude-2.1': 200_000,
        'claude-2.0': 100_000,
        'claude-instant-1': 100_000,
        'claude-instant-1.2': 100_000,
        'claude-2:beta': 200_000,
        'claude-2.1:beta': 200_000,
        'claude-2.0:beta': 100_000,
        'claude-instant-1:beta': 100_000,
        'zephyr-7b-beta:free': 4096,
        'openchat-7b:free': 8192,
        'mixtral-8x7b-instruct:nitro': 32_768,
        'llama-2-70b-chat:nitro': 4096,
        'mythomax-l2-13b:nitro': 4096,
        'mistral-7b-instruct:nitro': 32_768,
        'gemma-7b-it:nitro': 8192,
        'mistral-tiny': 32_000,
        'mistral-small': 32_000,
        'mistral-medium': 32_000,
        'mistral-large': 32_000,
        'command': 4096,
        'command-r': 128_000
    }
    return token_limit_dict
import time
import logging
import re
import string
import sys
import os
from charset_normalizer import detect


def time_it(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logging.info(f"Function {func.__name__} took {round(end - start, 5)} seconds to execute")
        return result
    return wrapper


def clean_text(text):
    # Remove all punctuation from the sentence
    text_cleaned = text.translate(str.maketrans('', '', string.punctuation))
    # Remove any extra whitespace
    text_cleaned = re.sub('\s+', ' ', text_cleaned).strip()
    text_cleaned = text_cleaned.lower()

    return text_cleaned


def resolve_path(path):
    if getattr(sys, 'frozen', False):
        resolved_path = os.path.dirname(sys.executable)
    else:
        resolved_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return resolved_path


def get_file_encoding(file_path):
    with open(file_path,'rb') as f:
        data = f.read()
    encoding = detect(data).get("encoding")
    return encoding


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
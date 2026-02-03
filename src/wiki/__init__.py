# Wiki module for character/quest info
#
# Production usage (static pre-generated files):
#     from src.wiki.wiki_loader import load_character_wiki
#     wiki = load_character_wiki("Preston Garvey", "Fallout4")
#
# Batch processing (create_wiki_prompts.py):
#     from src.wiki import WikiDB, WikiProcessor

from src.wiki.wiki_db import WikiDB
from src.wiki.wiki_loader import WikiLoader, load_character_wiki

__all__ = ['WikiDB', 'WikiLoader', 'load_character_wiki']

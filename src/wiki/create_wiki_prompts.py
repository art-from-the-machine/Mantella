"""
Create wiki prompts for characters in fallout4_characters.csv.

Features:
- Process single character by name (--name "Preston Garvey")
- Process batch from CSV (--count 10 for testing)
- Save to wiki/characters/{A-Z}/ folders
- Option to save raw wiki (--save-raw)
- Configurable max output size

Usage:
    python -m src.wiki.create_wiki_prompts --name "Preston Garvey"  # Single character
    python -m src.wiki.create_wiki_prompts --count 10               # Test with 10
    python -m src.wiki.create_wiki_prompts --count 10 --save-raw    # With raw wiki
    python -m src.wiki.create_wiki_prompts --all                    # All characters
"""
import argparse
import csv
import logging
import time
from pathlib import Path

from src.config.config_loader import ConfigLoader
from src.llm.llm_client import LLMClient

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Paths
CSV_PATH = Path("data/Fallout4/fallout4_characters.csv")
OUTPUT_BASE = Path("data/Fallout4/wiki")
CHARS_DIR = OUTPUT_BASE / "characters"
RAW_DIR = OUTPUT_BASE / "raw"

# LLM prompt for wiki conversion
WIKI_PROMPT = """Convert this Fallout 4 wiki page into roleplay-friendly XML for: {name}

TASK:
1. Analyze the wiki structure: look for ==Section== headers, infobox fields, dialogue
2. For each wiki section, create a matching XML tag (e.g. ==Background== becomes <background>)
3. Merge infobox fields into one <info> prose paragraph (e.g. "Deb is a human female merchant at Bunker Hill...")
4. PRESERVE original text - only clean up wiki markup ([[links]], bullets, etc.)
5. Only rewrite/compress if the section is very long or redundant

SECTION EXTRACTION:
Extract sections DYNAMICALLY based on what the wiki actually contains.
Examples: <info>, <background>, <personality>, <relationships>, <quests>, <interactions>, <quotes>, <combat>, <notes>
But create whatever tags match the wiki's actual structure.
For character quotes/dialogue, use <quotes> consistently.

RULES:
1. NO wrapper tags. Start directly with content tags, not <character_profile> or similar
2. NO nested tags inside sections. Content must be plain text/prose, not <name>, <race>, <wares> etc.
3. PRESERVE original wording. Only clean wiki syntax like [[links]], bullets, templates
4. Only rewrite if needed to compress very long/redundant sections
5. NO markdown. No **bold**, no *italics*, no asterisks
6. NO fancy quotes. Plain ASCII or none
7. NO indentation inside tags
8. Maximum {max_words} words (shorter is fine for minor characters)

SPECIAL FORMATTING:
- Quests: "Quest Name: Description" (one per line, preserve original description)
- Quotes: Just the spoken text, no quotation marks

SKIP ENTIRELY:
- Stats, SPECIAL, inventory, equipment lists
- Bugs, technical info, voice actors, voice type info, file names
- Category tags, language links
- "Appearances" sections (e.g. "appears in Fallout 4")
- Game mechanics (workshop system, supply lines, settlement mechanics)
- Behind the scenes / real world references
- Pure vendor info like "Wares: X items" or "sells X, has Y caps" (unless there's story context)

INTERACTIONS HANDLING:
- Skip if it's just vendor inventory ("Wares: misc items")
- Keep if it describes story-relevant behavior (quest consequences, unique dialogue, relationship changes)
- Merge any RP-relevant interaction info into <background> or <notes> instead of separate <interactions>

RAW WIKI:
{content}"""


def get_alpha_folder(name: str) -> str:
    """Get alphabetical folder based on last name (A-Z or _other).
    
    Examples:
        Blake Abernathy -> A
        Johnny D. -> D
        Maisie -> M (single name uses first letter)
    """
    if not name:
        return "_other"
    
    parts = name.split()
    # Use last part (last name), or the only part if single name
    last_part = parts[-1] if parts else name
    
    # Find first alphabetic character (skip punctuation like "D.")
    for char in last_part:
        if char.isalpha():
            return char.upper()
    
    # Fallback to first character of full name
    for char in name:
        if char.isalpha():
            return char.upper()
    
    return "_other"


def create_llm_client():
    """Create Mantella's LLM client."""
    from pathlib import Path
    from src.config.config_loader import ConfigLoader
    from src.llm.llm_client import LLMClient
    
    save_folder = str(Path("user_folder").absolute())
    config = ConfigLoader(save_folder, "config.ini")
    
    logger.info(f"Config: {save_folder}/config.ini")
    logger.info(f"Model: {config.llm}")
    
    client = LLMClient(
        config,
        secret_key_file="GPT_SECRET_KEY.txt",
        image_secret_key_file="GPT_SECRET_KEY.txt",
    )
    
    return client, config


def process_character(client: LLMClient, config: ConfigLoader, name: str, raw_wiki: str, save_raw: bool = False, max_tokens: int = 2000, max_words: int = 1500) -> tuple[str | None, str | None]:
    """
    Process a character's wiki content.
    
    Returns:
        (processed_content, raw_wiki) or (None, raw_wiki) on failure
    """
    from src.llm.messages import UserMessage
    
    if not raw_wiki or len(raw_wiki) < 200:
        return None, raw_wiki
    
    prompt = WIKI_PROMPT.format(name=name, content=raw_wiki, max_words=max_words)
    
    try:
        with client.override_params(max_tokens=max_tokens, temperature=0):
            msg = UserMessage(config, prompt, "")
            response = client.request_call(msg)
        
        if response:
            result = f'<wiki>\n{response.strip()}\n</wiki>'
            return result, raw_wiki if save_raw else None
    except Exception as e:
        logger.error(f"LLM failed for {name}: {e}")
    
    return None, raw_wiki if save_raw else None


def load_characters_with_wiki(csv_path: Path, db) -> list[dict]:
    """Load characters from CSV that have wiki data."""
    characters = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('name', '').strip()
            if not name:
                continue
            
            # Check if character has wiki data
            char_data = db.get_character(name)
            if char_data and char_data.get('wiki_content'):
                characters.append({
                    'name': name,
                    'wiki_content': char_data['wiki_content'],
                    'csv_row': row,
                })
    
    return characters


def main():
    parser = argparse.ArgumentParser(description="Create wiki prompts for characters")
    parser.add_argument("--name", type=str, help="Process a specific character by name")
    parser.add_argument("--count", type=int, default=10, help="Number of characters to process (default: 10)")
    parser.add_argument("--all", action="store_true", help="Process ALL characters")
    parser.add_argument("--save-raw", action="store_true", help="Also save raw wiki content")
    parser.add_argument("--start", type=int, default=0, help="Start from character index N")
    parser.add_argument("--skip-existing", action="store_true", help="Skip characters that already have output")
    parser.add_argument("--max-tokens", type=int, default=4000, help="Max tokens for LLM output (default: 4000)")
    parser.add_argument("--min-words", type=int, default=300, help="Min words in output (default: 300)")
    parser.add_argument("--max-words", type=int, default=1500, help="Max words in output (default: 1500)")
    args = parser.parse_args()
    
    print("=" * 70)
    print("CREATE WIKI PROMPTS")
    print("=" * 70)
    
    # Check CSV
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found: {CSV_PATH}")
        return
    
    # Check wiki database
    from src.wiki.wiki_db import WikiDB
    db = WikiDB()
    if not db.is_available:
        print(f"ERROR: Wiki database not found: {db.db_path}")
        print("Run: python -m src.wiki.dump_parser --full")
        return
    
    stats = db.get_stats()
    print(f"\nWiki DB: {stats['characters']} characters")
    
    # Handle single character lookup
    if args.name:
        char_data = db.get_character(args.name)
        if not char_data or not char_data.get('wiki_content'):
            print(f"ERROR: No wiki data found for '{args.name}'")
            db.close()
            return
        characters = [{
            'name': args.name,
            'wiki_content': char_data['wiki_content'],
            'csv_row': {},
        }]
        print(f"Processing single character: {args.name}")
    else:
        # Load characters with wiki data
        print(f"Loading characters from CSV...")
        characters = load_characters_with_wiki(CSV_PATH, db)
        print(f"Found {len(characters)} characters with wiki data")
        
        # Apply limits
        if args.start > 0:
            characters = characters[args.start:]
        
        if not args.all:
            characters = characters[:args.count]
    
    db.close()
    
    print(f"\nProcessing {len(characters)} characters (max_tokens={args.max_tokens})")
    if args.save_raw:
        print("Saving raw wiki: YES")
    
    # Create output directories
    CHARS_DIR.mkdir(parents=True, exist_ok=True)
    if args.save_raw:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create LLM client
    print("\n" + "-" * 40)
    print("Initializing LLM...")
    
    try:
        client, config = create_llm_client()
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    # Process characters
    print("\n" + "=" * 70)
    print("PROCESSING")
    print("=" * 70)
    
    results = {'ok': 0, 'failed': 0, 'skipped': 0}
    total_time = 0
    
    for i, char in enumerate(characters, 1):
        name = char['name']
        safe_name = name.replace(" ", "_").replace("/", "_").replace(":", "_")
        alpha = get_alpha_folder(name)
        
        # Output paths
        char_dir = CHARS_DIR / alpha
        char_dir.mkdir(parents=True, exist_ok=True)
        output_file = char_dir / f"{safe_name}.txt"
        
        # Skip if exists
        if args.skip_existing and output_file.exists():
            print(f"[{i}/{len(characters)}] {name} - SKIPPED (exists)")
            results['skipped'] += 1
            continue
        
        print(f"[{i}/{len(characters)}] {name}...", end=" ", flush=True)
        
        start = time.time()
        processed, raw = process_character(
            client, config, 
            name, 
            char['wiki_content'],
            save_raw=args.save_raw,
            max_tokens=args.max_tokens,
            max_words=args.max_words
        )
        elapsed = time.time() - start
        total_time += elapsed
        
        if processed:
            # Save processed
            output_file.write_text(processed, encoding='utf-8')
            
            # Save raw if requested
            if args.save_raw and raw:
                raw_dir = RAW_DIR / alpha
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_file = raw_dir / f"{safe_name}_raw.txt"
                raw_file.write_text(raw, encoding='utf-8')
            
            raw_size = len(char['wiki_content'])
            proc_size = len(processed)
            print(f"OK ({raw_size} -> {proc_size} chars, {elapsed:.1f}s)")
            results['ok'] += 1
        else:
            print(f"FAILED ({elapsed:.1f}s)")
            results['failed'] += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Processed: {results['ok']}")
    print(f"Failed:    {results['failed']}")
    print(f"Skipped:   {results['skipped']}")
    print(f"Total time: {total_time:.1f}s")
    print(f"\nOutput: {CHARS_DIR.absolute()}")
    if args.save_raw:
        print(f"Raw:    {RAW_DIR.absolute()}")


if __name__ == "__main__":
    main()


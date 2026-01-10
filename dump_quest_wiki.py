"""
Dump full raw wiki for quest analysis.
Run to see what we can include in prompt.
"""

from src.wiki.wiki_db import WikiDB
from pathlib import Path

def dump_quest(quest_name: str):
    """Dump full wiki content for a quest."""
    db = WikiDB()
    if not db.is_available:
        print("ERROR: Wiki DB not available")
        return
    
    quest = db.get_quest_by_title(quest_name)
    if not quest:
        print(f"Quest not found: {quest_name}")
        return
    
    wiki = quest.get('wiki_content', '')
    
    # Save to file
    safe_name = quest_name.replace(" ", "_").replace(":", "_")
    output_path = Path(f"data/Fallout4/wiki_data/{safe_name}_FULL.txt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    output = f"""
{'='*80}
QUEST: {quest_name}
FormID: {quest.get('formid', 'N/A')}
Type: {quest.get('quest_type', 'N/A')}
{'='*80}

RAW WIKI ({len(wiki)} chars):
{'='*80}

{wiki}
"""
    
    output_path.write_text(output, encoding='utf-8')
    print(f"\nSaved: {output_path}")
    print(f"Size: {len(wiki)} chars")
    
    # Also print key sections
    print(f"\n{'='*60}")
    print(f"KEY SECTIONS FOR: {quest_name}")
    print('='*60)
    
    # Print quest stages section
    import re
    stages_match = re.search(r'==Quest stages==.*?\{\{Quest stage table.*?\}\}', wiki, re.DOTALL)
    if stages_match:
        print("\n--- QUEST STAGES ---")
        print(stages_match.group(0))
    
    # Print infobox
    infobox_match = re.search(r'\{\{Infobox quest.*?\}\}', wiki, re.DOTALL)
    if infobox_match:
        print("\n--- INFOBOX ---")
        print(infobox_match.group(0))


def main():
    quests = [
        "When Freedom Calls",
        "Taking Independence", 
        "Sanctuary",
        "The First Step"
    ]
    
    for quest in quests:
        dump_quest(quest)
        print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()



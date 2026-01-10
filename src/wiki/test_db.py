"""
Test and explore wiki database content (raw data, no LLM).

Usage:
    python -m src.wiki.test_db                    # Show database stats and samples
    python -m src.wiki.test_db "Preston Garvey"   # Lookup specific character
    python -m src.wiki.test_db --quest "Reunions" # Lookup specific quest
"""
import sys
import time
from pathlib import Path

from src.wiki.wiki_db import WikiDB


def show_stats():
    """Show database statistics and sample content."""
    db = WikiDB()
    
    if not db.is_available:
        print(f"Database not found: {db.db_path}")
        print("Run: python -m src.wiki.dump_parser --full")
        return
    
    stats = db.get_stats()
    
    print("=" * 60)
    print("DATABASE STATS")
    print("=" * 60)
    print(f"Characters: {stats['characters']}")
    print(f"Quests:     {stats['quests']}")
    print(f"Pages:      {stats['pages']}")
    
    # Sample character
    print("\n" + "=" * 60)
    print("SAMPLE CHARACTER: Preston Garvey")
    print("=" * 60)
    
    char = db.get_character("Preston Garvey")
    if char:
        print(f"Name:        {char['name']}")
        print(f"FormID:      {char['formid']}")
        print(f"Role:        {char['role']}")
        print(f"Location:    {char['location']}")
        print(f"Affiliation: {char['affiliation']}")
        print(f"Raw wiki:    {len(char['wiki_content'])} chars")
    else:
        print("Preston Garvey not found!")
    
    # Sample quest
    print("\n" + "=" * 60)
    print("SAMPLE QUEST: When Freedom Calls")
    print("=" * 60)
    
    quest = db.get_quest_by_title("When Freedom Calls")
    if quest:
        print(f"Title:    {quest['title']}")
        print(f"FormID:   {quest['formid']}")
        print(f"EditorID: {quest['edid']}")
        print(f"Type:     {quest['quest_type']}")
        print(f"Raw wiki: {len(quest['wiki_content'])} chars")
    else:
        print("When Freedom Calls not found!")
    
    db.close()


def lookup_character(name: str):
    """Look up and save character data to file (raw only, no LLM)."""
    db = WikiDB()
    
    if not db.is_available:
        print(f"Database not found: {db.db_path}")
        return
    
    start = time.perf_counter()
    char = db.get_character(name)
    lookup_ms = (time.perf_counter() - start) * 1000
    
    print(f"Lookup time: {lookup_ms:.3f} ms")
    
    if not char:
        print(f"Character '{name}' not found")
        
        # Suggest similar names
        matches = db.search_characters(name, limit=10)
        if matches:
            print("\nDid you mean:")
            for m in matches:
                print(f"  - {m['name']}")
        
        db.close()
        return
    
    raw = char['wiki_content']
    
    # Build output
    lines = [
        "=" * 70,
        f"CHARACTER: {char['name']}",
        "=" * 70,
        "",
        "DATABASE FIELDS:",
        "-" * 40,
        f"  id:          {char['id']}",
        f"  name:        {char['name']}",
        f"  formid:      {char['formid']}",
        f"  race:        {char['race']}",
        f"  gender:      {char['gender']}",
        f"  role:        {char['role']}",
        f"  location:    {char['location']}",
        f"  affiliation: {char['affiliation']}",
        "",
        f"RAW WIKI SIZE: {len(raw)} chars",
        "",
        "=" * 70,
        "RAW WIKITEXT:",
        "=" * 70,
        raw,
    ]
    
    full_output = "\n".join(lines)
    
    # Save to file
    safe_name = name.replace(" ", "_").replace("/", "_")
    output_file = Path(f"data/Fallout4/wiki_data/{safe_name}_RAW.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(full_output, encoding='utf-8')
    
    print(f"\nCharacter: {char['name']}")
    print(f"Raw wiki: {len(raw)} chars")
    print(f"\nSAVED TO: {output_file.absolute()}")
    
    db.close()


def lookup_quest(title: str):
    """Look up and save quest data to file (raw only)."""
    db = WikiDB()
    
    if not db.is_available:
        print(f"Database not found: {db.db_path}")
        return
    
    start = time.perf_counter()
    quest = db.get_quest_by_title(title)
    lookup_ms = (time.perf_counter() - start) * 1000
    
    print(f"Lookup time: {lookup_ms:.3f} ms")
    
    if not quest:
        print(f"Quest '{title}' not found")
        
        matches = db.search_quests(title, limit=10)
        if matches:
            print("\nDid you mean:")
            for m in matches:
                print(f"  - {m['title']}")
        
        db.close()
        return
    
    raw = quest['wiki_content']
    
    # Build output
    lines = [
        "=" * 70,
        f"QUEST: {quest['title']}",
        "=" * 70,
        "",
        "DATABASE FIELDS:",
        "-" * 40,
        f"  id:         {quest['id']}",
        f"  title:      {quest['title']}",
        f"  formid:     {quest['formid']}",
        f"  edid:       {quest['edid']}",
        f"  quest_type: {quest['quest_type']}",
        f"  location:   {quest['location']}",
        "",
        f"RAW WIKI SIZE: {len(raw)} chars",
        "",
        "=" * 70,
        "RAW WIKITEXT:",
        "=" * 70,
        raw,
    ]
    
    full_output = "\n".join(lines)
    
    # Save to file
    safe_name = title.replace(" ", "_").replace("/", "_").replace(":", "_")
    output_file = Path(f"data/Fallout4/wiki_data/{safe_name}_QUEST_RAW.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(full_output, encoding='utf-8')
    
    print("\n" + "=" * 60)
    print(f"QUEST: {quest['title']}")
    print("=" * 60)
    print(f"FormID:   {quest['formid']}")
    print(f"EditorID: {quest['edid']}")
    print(f"Type:     {quest['quest_type']}")
    print(f"Location: {quest['location']}")
    print(f"Raw wiki: {len(raw)} chars")
    print(f"\nSAVED TO: {output_file.absolute()}")
    
    db.close()


def test_npc_quests(npc_name: str = "Preston Garvey"):
    """Test NPC to quest mapping using the new overview page parser."""
    from src.wiki.quest_lookup import get_quest_lookup, QuestNPCMapper
    
    print("=" * 60)
    print(f"NPC QUEST LOOKUP: {npc_name}")
    print("=" * 60)
    
    db = WikiDB()
    if not db.is_available:
        print(f"Database not found: {db.db_path}")
        return
    
    # Check if overview page exists
    content = db.get_quests_overview_page()
    if not content:
        print("ERROR: 'Fallout 4 quests' page not found in database!")
        print("Make sure the wiki dump includes this page.")
        db.close()
        return
    
    print(f"Overview page size: {len(content)} chars")
    
    # Create mapper and parse
    mapper = QuestNPCMapper(db)
    
    # Get stats
    stats = mapper.get_stats()
    print(f"\nMapping stats:")
    print(f"  NPCs with quests: {stats['npcs']}")
    print(f"  Total mappings:   {stats['total_mappings']}")
    
    # Get quests for specific NPC
    print(f"\n" + "-" * 40)
    print(f"Quests for '{npc_name}':")
    print("-" * 40)
    
    formids = mapper.get_quests_for_npc(npc_name)
    
    if not formids:
        print(f"  No quests found for {npc_name}")
        
        # Show available NPCs
        all_npcs = mapper.get_all_npcs()
        print(f"\nAvailable NPCs ({len(all_npcs)} total):")
        for npc in sorted(all_npcs)[:20]:
            print(f"  - {npc}")
        if len(all_npcs) > 20:
            print(f"  ... and {len(all_npcs) - 20} more")
    else:
        print(f"  Found {len(formids)} quest FormIDs:")
        for fid in formids:
            # Look up quest title by FormID
            hex_id = format(int(fid), '08X')
            quest = db.get_quest_by_formid(hex_id)
            if quest:
                print(f"    {fid} (0x{hex_id}) -> {quest['title']}")
            else:
                print(f"    {fid} (0x{hex_id}) -> [quest not in DB]")
    
    # Test a few more NPCs
    print(f"\n" + "-" * 40)
    print("Sample NPCs and their quest counts:")
    print("-" * 40)
    
    test_npcs = ["Preston Garvey", "Nick Valentine", "Piper Wright", "Sturges", 
                 "Arthur Maxson", "Desdemona", "Father", "Shaun"]
    
    for test_npc in test_npcs:
        fids = mapper.get_quests_for_npc(test_npc)
        if fids:
            print(f"  {test_npc}: {len(fids)} quests")
    
    db.close()


def main():
    if len(sys.argv) < 2:
        show_stats()
    elif sys.argv[1] == '--quest' and len(sys.argv) > 2:
        lookup_quest(" ".join(sys.argv[2:]))
    elif sys.argv[1] == '--npc-quests':
        npc_name = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Preston Garvey"
        test_npc_quests(npc_name)
    else:
        lookup_character(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()

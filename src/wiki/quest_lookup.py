"""
Quest lookup from wiki database.

Uses the "Fallout 4 quests" overview page which has complete tables
of all quests with their quest givers (NPCs). This is more complete
than extracting quest names from individual character wiki pages.
"""
import re
import logging
from typing import Optional

from src.wiki.wiki_db import WikiDB

logger = logging.getLogger(__name__)


class QuestNPCMapper:
    """
    Maps NPCs to their associated quests by parsing the Fallout 4 quests overview page.
    
    The overview page has wiki tables with columns:
    Icon | Name | Location(s) | Given by | Reward | Form ID | Editor ID
    
    We parse the "Given by" column to build NPC -> [quest_formids] mappings.
    """
    
    def __init__(self, db: WikiDB):
        self._db = db
        self._npc_to_quests: dict[str, list[str]] = {}  # NPC name -> [decimal formids]
        self._parsed = False
    
    def get_quests_for_npc(self, npc_name: str) -> list[str]:
        """
        Get quest FormIDs associated with an NPC.
        
        Args:
            npc_name: Character name (e.g., "Preston Garvey")
            
        Returns:
            List of FormIDs as decimal strings (e.g., ["1703964", "1159022"])
        """
        if not self._parsed:
            self._parse_quests_page()
        
        # Normalize name for lookup
        name_lower = npc_name.lower().strip()
        
        # Try exact match first
        for stored_name, formids in self._npc_to_quests.items():
            if stored_name.lower() == name_lower:
                return formids
        
        # Try partial match (e.g., "Preston" matches "Preston Garvey")
        for stored_name, formids in self._npc_to_quests.items():
            if name_lower in stored_name.lower() or stored_name.lower() in name_lower:
                return formids
        
        return []
    
    def _parse_quests_page(self) -> None:
        """Parse the Fallout 4 quests overview page to build NPC mappings."""
        self._parsed = True
        
        content = self._db.get_quests_overview_page()
        if not content:
            logger.warning("Fallout 4 quests overview page not found in database")
            return
        
        # Parse wiki table rows
        # Each row starts with |- and contains cells with | or ||
        # We need: Name (col 2), Given by (col 4), Form ID (col 6)
        
        # Split by table rows
        rows = re.split(r'\n\|-\n?', content)
        
        quest_count = 0
        for row in rows:
            # Skip header rows and section headers
            if not row.strip() or row.startswith('!') or 'colspan' in row.lower():
                continue
            
            # Split row into cells (handle both | and || separators)
            # Cells are separated by newline followed by | or ||
            cells = re.split(r'\n\|+\s*', row)
            
            if len(cells) < 6:
                continue
            
            # Extract quest name from cell 2 (index 1 after split)
            # Format: [[Quest Name]] or [[Quest Name|Display]]
            quest_cell = cells[1] if len(cells) > 1 else ""
            quest_name = self._extract_link_text(quest_cell)
            
            if not quest_name:
                continue
            
            # Extract NPC names from "Given by" cell (cell 4, index 3)
            given_by_cell = cells[3] if len(cells) > 3 else ""
            npc_names = self._extract_npc_names(given_by_cell)
            
            # Extract FormID from cell 6 (index 5)
            # Format: {{ID|001a001c}}
            formid_cell = cells[5] if len(cells) > 5 else ""
            formid = self._extract_formid(formid_cell)
            
            if formid and npc_names:
                quest_count += 1
                for npc in npc_names:
                    if npc not in self._npc_to_quests:
                        self._npc_to_quests[npc] = []
                    if formid not in self._npc_to_quests[npc]:
                        self._npc_to_quests[npc].append(formid)
                        logger.debug(f"Mapped {npc} -> {quest_name} (FormID: {formid})")
        
        logger.info(f"Parsed {quest_count} quests, mapped to {len(self._npc_to_quests)} NPCs")
    
    def _extract_link_text(self, cell: str) -> str:
        """Extract text from wiki link [[Name]] or [[Name|Display]]."""
        match = re.search(r'\[\[([^|\]]+)(?:\|([^\]]+))?\]\]', cell)
        if match:
            # Return display text if present, else link target
            return (match.group(2) or match.group(1)).strip()
        return ""
    
    def _extract_npc_names(self, cell: str) -> list[str]:
        """Extract NPC names from 'Given by' cell.
        
        Handles formats like:
        - [[Preston Garvey]]
        - [[Nick Valentine]]<br />[[Piper Wright|Piper]]
        - [[Preston Garvey]] ''or''<br />[[Radio Freedom]]
        """
        names = []
        
        # Find all wiki links
        for match in re.finditer(r'\[\[([^|\]]+)(?:\|([^\]]+))?\]\]', cell):
            name = (match.group(2) or match.group(1)).strip()
            
            # Skip non-NPC links (locations, items, etc.)
            skip_patterns = [
                r'^Radio',
                r'^File:',
                r'^Image:',
                r'settlement',
                r'holotape',
                r'terminal',
                r'note$',
            ]
            
            should_skip = False
            for pattern in skip_patterns:
                if re.search(pattern, name, re.IGNORECASE):
                    should_skip = True
                    break
            
            if not should_skip and name:
                names.append(name)
        
        return names
    
    def _extract_formid(self, cell: str) -> str:
        """Extract FormID from {{ID|hexid}} template and convert to decimal."""
        match = re.search(r'\{\{ID\|([0-9a-fA-F]+)\}\}', cell)
        if match:
            hex_id = match.group(1)
            try:
                # Convert hex to decimal string
                return str(int(hex_id, 16))
            except ValueError:
                pass
        return ""
    
    def get_all_npcs(self) -> list[str]:
        """Get list of all NPCs that have associated quests."""
        if not self._parsed:
            self._parse_quests_page()
        return list(self._npc_to_quests.keys())
    
    def get_stats(self) -> dict:
        """Get mapping statistics."""
        if not self._parsed:
            self._parse_quests_page()
        
        total_quests = sum(len(q) for q in self._npc_to_quests.values())
        return {
            'npcs': len(self._npc_to_quests),
            'total_mappings': total_quests,
        }


class QuestLookup:
    """Look up quest FormIDs for NPCs from wiki database."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize with optional custom database path."""
        self._db = WikiDB(db_path)
        self._mapper: Optional[QuestNPCMapper] = None
        self._cache: dict[str, list[str]] = {}
    
    @property
    def is_available(self) -> bool:
        """Check if wiki database is available."""
        return self._db.is_available
    
    @property
    def mapper(self) -> QuestNPCMapper:
        """Get or create the quest NPC mapper."""
        if self._mapper is None:
            self._mapper = QuestNPCMapper(self._db)
        return self._mapper
    
    def get_quest_formids_for_npc(self, npc_name: str) -> list[str]:
        """
        Get quest FormIDs associated with an NPC.
        
        Uses the "Fallout 4 quests" overview page for complete quest listings.
        
        Args:
            npc_name: Character name (e.g., "Preston Garvey")
            
        Returns:
            List of FormIDs as decimal strings (e.g., ["1703964", "1159022"])
        """
        if npc_name in self._cache:
            return self._cache[npc_name]
        
        if not self._db.is_available:
            logger.warning("Wiki database not available for quest lookup")
            return []
        
        # Use the new mapper based on overview page
        formids = self.mapper.get_quests_for_npc(npc_name)
        
        self._cache[npc_name] = formids
        
        if formids:
            logger.info(f"Found {len(formids)} quests for {npc_name}")
        else:
            logger.debug(f"No quests found for {npc_name}")
        
        return formids
    
    def close(self):
        """Close database connection."""
        self._db.close()


# Singleton instance for reuse
_instance: Optional[QuestLookup] = None


def get_quest_lookup(db_path: Optional[str] = None) -> QuestLookup:
    """Get or create singleton QuestLookup instance."""
    global _instance
    if _instance is None:
        _instance = QuestLookup(db_path)
    return _instance

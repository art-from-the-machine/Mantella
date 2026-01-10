"""
Quest context enrichment from wiki database.

Parses quest status from Papyrus and enriches with wiki data.
Includes FULL quest stages and walkthroughs for rich context.
"""
import re
from typing import Optional
from src.wiki.wiki_db import WikiDB
import src.utils as utils

logger = utils.get_logger()


class QuestContextBuilder:
    """Builds enriched quest context from Papyrus data + wiki."""
    
    def __init__(self):
        self._db: Optional[WikiDB] = None
    
    @property
    def db(self) -> WikiDB:
        if self._db is None:
            self._db = WikiDB()
        return self._db
    
    def parse_quest_context(self, raw: str) -> str:
        """Parse quest context string from Papyrus into readable format with wiki enrichment.
        
        Input format: "Quest Name:status:stage|Quest Name 2:status"
        Status: running, completed, not_started
        
        Returns formatted text for LLM prompt with FULL detail.
        """
        if not raw:
            return ""
        
        active_quests = []  # List of (name, stage) tuples
        completed = []
        
        for entry in raw.split("|"):
            if not entry.strip():
                continue
            parts = entry.split(":")
            if len(parts) >= 2:
                name = parts[0].strip()
                status = parts[1].strip().lower()
                stage = int(parts[2].strip()) if len(parts) >= 3 and parts[2].strip().isdigit() else 0
                
                if status == "completed":
                    completed.append(name)
                elif status == "running":
                    active_quests.append((name, stage))
        
        lines = []
        
        # Enrich active quests with FULL wiki data
        if active_quests:
            for quest_name, stage in active_quests:
                quest_info = self._get_quest_info(quest_name, stage)
                if quest_info:
                    lines.append(f"=== QUEST: {quest_name} (current stage: {stage}) ===")
                    lines.append(quest_info)
                    lines.append("")  # Blank line between quests
                else:
                    lines.append(f"=== QUEST: {quest_name} (stage {stage}) ===")
        
        # Enriched completed quests (with walkthrough and stages)
        if completed:
            lines.append("=== COMPLETED QUESTS ===")
            for quest_name in completed:
                quest_info = self._get_completed_quest_info(quest_name)
                if quest_info:
                    lines.append(f"  {quest_name}:")
                    for line in quest_info.split("\n"):
                        lines.append(f"    {line}")
                else:
                    lines.append(f"  - {quest_name}")
        
        return "\n".join(lines)
    
    def _get_quest_info(self, quest_name: str, stage: int) -> str:
        """Get enriched quest info from wiki database.
        
        Includes full detailed walkthrough and quest stages with current stage marked.
        """
        try:
            if not self.db.is_available:
                return ""
            
            quest = self.db.get_quest_by_title(quest_name)
            if not quest or not quest.get('wiki_content'):
                return ""
            
            wiki = quest['wiki_content']
            sections = []
            
            # Extract location
            location = self._extract_location(wiki)
            if location:
                sections.append(f"Location: {location}")
            
            # Extract ALL quest stages with current marked
            stages_text = self._extract_all_stages(wiki, stage)
            if stages_text:
                sections.append(stages_text)
            
            # Extract FULL detailed walkthrough
            narrative = self._extract_narrative(wiki)
            if narrative:
                sections.append(f"Walkthrough:\n{narrative}")
            
            return "\n".join(sections) if sections else ""
            
        except Exception as e:
            logger.debug(f"Error getting quest wiki info for '{quest_name}': {e}")
            return ""
    
    def _extract_all_stages(self, wiki: str, current_stage: int) -> str:
        """Extract all quest stages with log entries (player's journal).
        
        Uses log entries as they're clean, complete sentences from player's perspective.
        Falls back to desc if no log available.
        """
        stages = []
        
        # Find all stage numbers first: |stage1 = 40 or ||stage1 = 40
        stage_pattern = r'\|+stage(\d+)\s*=\s*(\d+)'
        
        for match in re.finditer(stage_pattern, wiki):
            idx = match.group(1)
            stage_num = int(match.group(2))
            
            if stage_num >= 1000:  # Skip "Quest complete" stage
                continue
            
            # Get log entry (preferred - clean complete sentences)
            # Use [ \t]* instead of \s* to avoid matching newlines
            log_pattern = r'\|+log' + idx + r'[ \t]*=[ \t]*([^\n]*)'
            log_match = re.search(log_pattern, wiki)
            log = self._clean_wiki_markup(log_match.group(1)).strip() if log_match else ""
            
            # Fallback to desc if no log
            if not log:
                desc_pattern = r'\|+desc' + idx + r'\s*=\s*([^\n]+)'
                desc_match = re.search(desc_pattern, wiki)
                log = self._clean_wiki_markup(desc_match.group(1)).strip() if desc_match else ""
            
            if log:
                stages.append((stage_num, log))
        
        if not stages:
            return ""
        
        # Sort by stage number
        stages.sort(key=lambda x: x[0])
        
        # Format as detailed list
        lines = ["Quest Stages:"]
        for stage_num, log in stages:
            if stage_num < current_stage:
                marker = "[DONE]"
            elif stage_num == current_stage:
                marker = "[CURRENT]"
            else:
                marker = "[UPCOMING]"
            
            # Truncate very long logs
            if len(log) > 200:
                log = log[:197] + "..."
            
            lines.append(f"  {marker} Stage {stage_num}: {log}")
        
        return "\n".join(lines)
    
    def _get_completed_quest_info(self, quest_name: str) -> str:
        """Get info for a completed quest (location + walkthrough + stages)."""
        try:
            if not self.db.is_available:
                return ""
            
            quest = self.db.get_quest_by_title(quest_name)
            if not quest or not quest.get('wiki_content'):
                return ""
            
            wiki = quest['wiki_content']
            lines = []
            
            # Get location
            location = self._extract_location(wiki)
            if location:
                lines.append(f"Location: {location}")
            
            # Get full walkthrough (what happened in this quest)
            narrative = self._extract_narrative(wiki)
            if narrative:
                lines.append("What happened:")
                lines.append(narrative)
            
            # Get ALL stages (marked as done since quest is complete)
            stages_text = self._extract_all_stages_completed(wiki)
            if stages_text:
                lines.append(stages_text)
            
            return "\n".join(lines) if lines else ""
            
        except Exception as e:
            logger.debug(f"Error getting completed quest info for '{quest_name}': {e}")
            return ""
    
    def _extract_all_stages_completed(self, wiki: str) -> str:
        """Extract all quest stages for a completed quest (all marked DONE)."""
        stages = []
        
        stage_pattern = r'\|+stage(\d+)\s*=\s*(\d+)'
        
        for match in re.finditer(stage_pattern, wiki):
            idx = match.group(1)
            stage_num = int(match.group(2))
            
            if stage_num >= 1000:
                continue
            
            # Get log entry
            log_pattern = r'\|+log' + idx + r'[ \t]*=[ \t]*([^\n]*)'
            log_match = re.search(log_pattern, wiki)
            log = self._clean_wiki_markup(log_match.group(1)).strip() if log_match else ""
            
            # Fallback to desc if no log
            if not log:
                desc_pattern = r'\|+desc' + idx + r'\s*=\s*([^\n]+)'
                desc_match = re.search(desc_pattern, wiki)
                log = self._clean_wiki_markup(desc_match.group(1)).strip() if desc_match else ""
            
            if log:
                if len(log) > 150:
                    log = log[:147] + "..."
                stages.append((stage_num, log))
        
        if not stages:
            return ""
        
        stages.sort(key=lambda x: x[0])
        
        lines = ["Stages completed:"]
        for stage_num, log in stages:
            lines.append(f"  [DONE] {log}")
        
        return "\n".join(lines)
    
    def _extract_location(self, wiki: str) -> str:
        """Extract quest location from infobox."""
        match = re.search(r'\|location\s*=\s*([^\n|]+)', wiki, re.IGNORECASE)
        if match:
            loc = self._clean_wiki_markup(match.group(1))
            # Limit length
            if len(loc) > 60:
                loc = loc[:57] + "..."
            return loc
        return ""
    
    def _extract_narrative(self, wiki: str) -> str:
        """Extract FULL detailed walkthrough section.
        
        This provides rich context about what happens in this quest.
        """
        # Find the detailed walkthrough section (everything between ==Detailed walkthrough== and next ==)
        match = re.search(r'==\s*Detailed walkthrough\s*==\s*\n(.+?)(?=\n==)', wiki, re.DOTALL | re.IGNORECASE)
        
        if match:
            text = match.group(1).strip()
            text = self._clean_wiki_markup(text)
            
            # Split into paragraphs and clean
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            
            # Join with single newlines for readability
            narrative = '\n'.join(paragraphs)
            
            return narrative
        
        return ""
    
    def _clean_wiki_markup(self, text: str) -> str:
        """Remove all wiki markup from text."""
        if not text:
            return ""
        
        result = text
        
        # FIRST: Extract content from common templates that contain useful text
        # {{tooltip|DISPLAY TEXT|hover text}} -> DISPLAY TEXT
        result = re.sub(r'\{\{tooltip\|([^|]+)\|[^}]+\}\}', r'\1', result, flags=re.IGNORECASE)
        # {{sic}} -> empty (just marks typos in original)
        result = re.sub(r'\{\{sic\}\}', '', result, flags=re.IGNORECASE)
        
        # Remove remaining templates {{ ... }} including nested - iterate until stable
        prev_len = -1
        while len(result) != prev_len:
            prev_len = len(result)
            result = re.sub(r'\{\{[^{}]*\}\}', '', result)
        
        # Remove wiki links, keeping display text
        result = re.sub(r'\[\[([^|\]]+)\|([^\]]+)\]\]', r'\2', result)  # [[link|text]] -> text
        result = re.sub(r'\[\[([^\]]+)\]\]', r'\1', result)  # [[link]] -> link
        
        # Remove bold/italic
        result = re.sub(r"'''([^']+)'''", r'\1', result)
        result = re.sub(r"''([^']+)''", r'\1', result)
        
        # Remove HTML
        result = re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)
        result = re.sub(r'<[^>]+>', ' ', result)
        
        # Clean whitespace
        result = re.sub(r'\s+', ' ', result)
        
        return result.strip()


# Singleton instance
_quest_context_builder: Optional[QuestContextBuilder] = None

def get_quest_context_builder() -> QuestContextBuilder:
    global _quest_context_builder
    if _quest_context_builder is None:
        _quest_context_builder = QuestContextBuilder()
    return _quest_context_builder


def build_quest_context(raw_quest_data: str) -> str:
    """Convenience function to parse and enrich quest context.
    
    Args:
        raw_quest_data: Quest string from Papyrus like "Quest:running:50|Quest2:completed"
    
    Returns:
        Formatted quest context for LLM prompt.
    """
    return get_quest_context_builder().parse_quest_context(raw_quest_data)

"""
Quest context enrichment from wiki database.

Parses quest status from Papyrus and enriches with wiki data.
Format: QuestName:status[:stage]
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
        
        Input format: "QuestName:status[:stage]|..."
        - QuestName: Display name (may contain <Alias=X> patterns)
        - Status: running, completed, not_started
        - Stage: Quest stage number (for running quests)
        """
        if not raw:
            return ""
        
        active_quests = []  # (name, stage)
        completed = []  # (name,)
        
        for entry in raw.split("|"):
            if not entry.strip():
                continue
            
            # Format: QuestName:status[:stage]
            # Find status by searching for known values
            parts = entry.split(":")
            if len(parts) < 2:
                continue
            
            # Find status field (completed, running, not_started)
            status_idx = -1
            for i, p in enumerate(parts):
                if p.strip().lower() in ("completed", "running", "not_started"):
                    status_idx = i
                    break
            
            if status_idx < 1:
                continue
            
            # Everything before status is the quest name
            name = ":".join(parts[:status_idx]).strip()
            status = parts[status_idx].strip().lower()
            
            if status == "completed":
                completed.append(name)
            elif status == "running":
                stage = 0
                locations = []
                if len(parts) > status_idx + 1:
                    stage_str = parts[status_idx + 1].strip()
                    if stage_str.isdigit():
                        stage = int(stage_str)
                    # Check for locations (format: :stage:Location1~Location2)
                    if len(parts) > status_idx + 2:
                        loc_str = parts[status_idx + 2].strip()
                        if loc_str and "~" in loc_str:
                            locations = [loc.strip() for loc in loc_str.split("~") if loc.strip()]
                        elif loc_str:
                            locations = [loc_str]
                active_quests.append((name, stage, locations))
        
        lines = []
        
        # Active quests with wiki data
        for quest_data in active_quests:
            name = quest_data[0]
            stage = quest_data[1]
            locations = quest_data[2] if len(quest_data) > 2 else []
            
            quest_info = self._get_quest_info(name, stage)
            if quest_info:
                lines.append(f"=== QUEST: {name} (current stage: {stage}) ===")
                # Add actual locations from Lighthouse if available (overrides wiki "Radiant settlement")
                if locations:
                    lines.append(f"Quest Locations: {', '.join(locations)}")
                lines.append(quest_info)
                lines.append("")
            else:
                header = f"=== QUEST: {name} (stage {stage}) ==="
                if locations:
                    header += f" - Locations: {', '.join(locations)}"
                lines.append(header)
        
        # Completed quests
        if completed:
            lines.append("=== COMPLETED QUESTS ===")
            for name in completed:
                quest_info = self._get_completed_quest_info(name)
                if quest_info:
                    lines.append(f"  {name}:")
                    for line in quest_info.split("\n"):
                        lines.append(f"    {line}")
                else:
                    lines.append(f"  - {name}")
        
        return "\n".join(lines)
    
    def _strip_alias_pattern(self, name: str) -> str:
        """Strip <Alias=X> patterns from quest name for wiki lookup."""
        # "Raider Troubles at <Alias=ActualLocation>" -> "Raider Troubles"
        cleaned = re.sub(r'\s*<Alias=[^>]+>\s*', '', name).strip()
        # Remove trailing "at", "for", "in", etc. if they're now at the end
        cleaned = re.sub(r'\s+(at|for|in|to)$', '', cleaned, flags=re.IGNORECASE).strip()
        return cleaned if cleaned else name
    
    def _get_quest_info(self, name: str, stage: int) -> str:
        """Get quest info from wiki by quest name."""
        try:
            if not self.db.is_available:
                return ""
            
            # Try exact name first, then stripped name (for radiant quests)
            quest = self.db.get_quest_by_title(name)
            if not quest:
                stripped = self._strip_alias_pattern(name)
                if stripped != name:
                    quest = self.db.get_quest_by_title(stripped)
            
            if not quest or not quest.get('wiki_content'):
                return ""
            
            wiki = quest['wiki_content']
            sections = []
            
            # Location from database (already cleaned during import)
            loc = quest.get('location', '')
            if loc and loc.strip():
                sections.append(f"Location: {loc}")
            
            # Quest stages
            stages_text = self._extract_stages(wiki, stage)
            if stages_text:
                sections.append(stages_text)
            
            # Walkthrough
            narrative = self._extract_narrative(wiki)
            if narrative:
                sections.append(f"Walkthrough:\n{narrative}")
            
            return "\n".join(sections) if sections else ""
        except Exception as e:
            logger.debug(f"Error getting quest info ({name}): {e}")
            return ""
    
    def _get_completed_quest_info(self, name: str) -> str:
        """Get completed quest info from wiki by quest name."""
        try:
            if not self.db.is_available:
                return ""
            
            # Try exact name first, then stripped name (for radiant quests)
            quest = self.db.get_quest_by_title(name)
            if not quest:
                stripped = self._strip_alias_pattern(name)
                if stripped != name:
                    quest = self.db.get_quest_by_title(stripped)
            
            if not quest or not quest.get('wiki_content'):
                return ""
            
            wiki = quest['wiki_content']
            lines = []
            
            # Location from database (already cleaned during import)
            loc = quest.get('location', '')
            if loc and loc.strip():
                lines.append(f"Location: {loc}")
            
            narrative = self._extract_narrative(wiki)
            if narrative:
                lines.append("What happened:")
                lines.append(narrative)
            
            stages = self._extract_stages_completed(wiki)
            if stages:
                lines.append(stages)
            
            return "\n".join(lines) if lines else ""
        except Exception as e:
            logger.debug(f"Error getting completed quest info ({name}): {e}")
            return ""
    
    def _extract_stages(self, wiki: str, current_stage: int) -> str:
        """Extract quest stages with current marked."""
        stages = []
        
        for match in re.finditer(r'\|+stage(\d+)\s*=\s*(\d+)', wiki):
            idx = match.group(1)
            stage_num = int(match.group(2))
            
            if stage_num >= 1000:
                continue
            
            # Get log entry
            log_match = re.search(r'\|+log' + idx + r'[ \t]*=[ \t]*([^\n]*)', wiki)
            log = self._clean_markup(log_match.group(1)).strip() if log_match else ""
            
            # Fallback to desc
            if not log:
                desc_match = re.search(r'\|+desc' + idx + r'\s*=\s*([^\n]+)', wiki)
                log = self._clean_markup(desc_match.group(1)).strip() if desc_match else ""
            
            if log:
                if len(log) > 200:
                    log = log[:197] + "..."
                stages.append((stage_num, log))
        
        if not stages:
            return ""
        
        stages.sort(key=lambda x: x[0])
        
        lines = ["Quest Stages:"]
        for num, log in stages:
            if num < current_stage:
                marker = "[DONE]"
            elif num == current_stage:
                marker = "[CURRENT]"
            else:
                marker = "[UPCOMING]"
            lines.append(f"  {marker} Stage {num}: {log}")
        
        return "\n".join(lines)
    
    def _extract_stages_completed(self, wiki: str) -> str:
        """Extract all stages for completed quest."""
        stages = []
        
        for match in re.finditer(r'\|+stage(\d+)\s*=\s*(\d+)', wiki):
            idx = match.group(1)
            stage_num = int(match.group(2))
            
            if stage_num >= 1000:
                continue
            
            log_match = re.search(r'\|+log' + idx + r'[ \t]*=[ \t]*([^\n]*)', wiki)
            log = self._clean_markup(log_match.group(1)).strip() if log_match else ""
            
            if not log:
                desc_match = re.search(r'\|+desc' + idx + r'\s*=\s*([^\n]+)', wiki)
                log = self._clean_markup(desc_match.group(1)).strip() if desc_match else ""
            
            if log:
                if len(log) > 150:
                    log = log[:147] + "..."
                stages.append((stage_num, log))
        
        if not stages:
            return ""
        
        stages.sort(key=lambda x: x[0])
        return "Stages completed:\n" + "\n".join(f"  [DONE] {log}" for _, log in stages)
    
    def _extract_narrative(self, wiki: str) -> str:
        """Extract walkthrough section."""
        match = re.search(r'==\s*Detailed walkthrough\s*==\s*\n(.+?)(?=\n==)', wiki, re.DOTALL | re.IGNORECASE)
        if match:
            text = self._clean_markup(match.group(1).strip())
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            return '\n'.join(paragraphs)
        return ""
    
    def _clean_markup(self, text: str) -> str:
        """Remove wiki markup."""
        if not text:
            return ""
        
        result = text
        
        # Templates
        result = re.sub(r'\{\{tooltip\|([^|]+)\|[^}]+\}\}', r'\1', result, flags=re.IGNORECASE)
        result = re.sub(r'\{\{sic\}\}', '', result, flags=re.IGNORECASE)
        
        prev_len = -1
        while len(result) != prev_len:
            prev_len = len(result)
            result = re.sub(r'\{\{[^{}]*\}\}', '', result)
        
        # Wiki links - complete ones first
        result = re.sub(r'\[\[([^|\]]+)\|([^\]]+)\]\]', r'\2', result)
        result = re.sub(r'\[\[([^\]]+)\]\]', r'\1', result)
        
        # Incomplete wiki links (cut off by regex)
        # Remove [[Something#anchor patterns (internal wiki refs)
        result = re.sub(r'\[\[[^\]]*#[^\]]*', '', result)
        # Remove any remaining [[ or ]]
        result = re.sub(r'\[\[|\]\]', '', result)
        
        # Bold/italic
        result = re.sub(r"'''([^']+)'''", r'\1', result)
        result = re.sub(r"''([^']+)''", r'\1', result)
        
        # HTML
        result = re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)
        result = re.sub(r'<[^>]+>', ' ', result)
        
        # Whitespace
        result = re.sub(r'\s+', ' ', result)
        
        return result.strip()


# Singleton
_builder: Optional[QuestContextBuilder] = None

def get_quest_context_builder() -> QuestContextBuilder:
    global _builder
    if _builder is None:
        _builder = QuestContextBuilder()
    return _builder

def build_quest_context(raw_quest_data: str) -> str:
    """Parse and enrich quest context from Papyrus data."""
    return get_quest_context_builder().parse_quest_context(raw_quest_data)

"""
Fast wiki lookups from SQLite database.

Tables:
  - characters: name, formid, race, gender, role, location, affiliation, wiki_content
  - quests: formid, edid, title, quest_type, location, wiki_content
  - pages: title, wiki_content

Usage:
    from src.wiki.wiki_db import WikiDB
    
    db = WikiDB()
    char = db.get_character("Preston Garvey")
    quest = db.get_quest_by_title("When Freedom Calls")
"""
import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WikiDB:
    """Fast O(1) lookups for wiki content from SQLite database."""
    
    DEFAULT_DB_PATH = Path("data/Fallout4/wiki.db")
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
    
    @property
    def is_available(self) -> bool:
        """Check if the database file exists."""
        return self.db_path.exists()
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy connection to database."""
        if self._conn is None:
            if not self.db_path.exists():
                raise FileNotFoundError(f"Wiki database not found: {self.db_path}")
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    # -------------------------------------------------------------------------
    # Character lookups
    # -------------------------------------------------------------------------
    
    def get_character(self, name: str) -> Optional[dict]:
        """Lookup character by name (case-insensitive)."""
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM characters WHERE name = ? COLLATE NOCASE', (name,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def get_character_by_formid(self, formid: str) -> Optional[dict]:
        """Lookup character by FormID."""
        formid = formid.upper().strip()
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM characters WHERE formid = ?', (formid,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def search_characters(self, partial_name: str, limit: int = 10) -> list[dict]:
        """Search characters by partial name match."""
        cur = self.conn.cursor()
        cur.execute(
            'SELECT * FROM characters WHERE name LIKE ? LIMIT ?',
            (f'%{partial_name}%', limit)
        )
        return [dict(row) for row in cur.fetchall()]
    
    # -------------------------------------------------------------------------
    # Quest lookups
    # -------------------------------------------------------------------------
    
    def get_quest_by_formid(self, formid: str) -> Optional[dict]:
        """Lookup quest by FormID (e.g., '000EDCEF')."""
        formid = formid.upper().strip()
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM quests WHERE formid = ?', (formid,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def get_quest_by_edid(self, edid: str) -> Optional[dict]:
        """Lookup quest by EditorID (e.g., 'MQ102')."""
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM quests WHERE edid = ? COLLATE NOCASE', (edid,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def get_quest_by_title(self, title: str) -> Optional[dict]:
        """Lookup quest by title (e.g., 'Reunions')."""
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM quests WHERE title = ? COLLATE NOCASE', (title,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def search_quests(self, partial_title: str, limit: int = 10) -> list[dict]:
        """Search quests by partial title match."""
        cur = self.conn.cursor()
        cur.execute(
            'SELECT * FROM quests WHERE title LIKE ? LIMIT ?',
            (f'%{partial_title}%', limit)
        )
        return [dict(row) for row in cur.fetchall()]
    
    def get_quests_by_titles(self, titles: list[str]) -> list[dict]:
        """Get multiple quests by their titles."""
        if not titles:
            return []
        
        cur = self.conn.cursor()
        placeholders = ','.join(['?' for _ in titles])
        cur.execute(
            f'SELECT * FROM quests WHERE title IN ({placeholders}) COLLATE NOCASE',
            titles
        )
        return [dict(row) for row in cur.fetchall()]
    
    # -------------------------------------------------------------------------
    # General page lookups
    # -------------------------------------------------------------------------
    
    def get_page(self, title: str) -> Optional[dict]:
        """Lookup any wiki page by title."""
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM pages WHERE title = ? COLLATE NOCASE', (title,))
        row = cur.fetchone()
        return dict(row) if row else None
    
    def search_pages(self, partial_title: str, limit: int = 10) -> list[dict]:
        """Search pages by partial title match."""
        cur = self.conn.cursor()
        cur.execute(
            'SELECT * FROM pages WHERE title LIKE ? LIMIT ?',
            (f'%{partial_title}%', limit)
        )
        return [dict(row) for row in cur.fetchall()]
    
    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        cur = self.conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM characters")
        char_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM quests")
        quest_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM pages")
        page_count = cur.fetchone()[0]
        
        return {
            'characters': char_count,
            'quests': quest_count,
            'pages': page_count,
        }
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Quick test
if __name__ == "__main__":
    db = WikiDB()
    
    if not db.is_available:
        print(f"Database not found: {db.db_path}")
        print("Run: python -m src.wiki.dump_parser --full")
        exit(1)
    
    print("WikiDB Test")
    print("=" * 50)
    
    stats = db.get_stats()
    print(f"Characters: {stats['characters']}")
    print(f"Quests: {stats['quests']}")
    print(f"Pages: {stats['pages']}")
    
    print("\n" + "-" * 50)
    print("Character lookup: Preston Garvey")
    char = db.get_character("Preston Garvey")
    if char:
        print(f"  Name: {char['name']}")
        print(f"  Role: {char['role']}")
        print(f"  Location: {char['location']}")
        print(f"  Wiki content: {len(char['wiki_content'])} chars")
    
    print("\n" + "-" * 50)
    print("Quest lookup: When Freedom Calls")
    quest = db.get_quest_by_title("When Freedom Calls")
    if quest:
        print(f"  Title: {quest['title']}")
        print(f"  FormID: {quest['formid']}")
        print(f"  EditorID: {quest['edid']}")
        print(f"  Wiki content: {len(quest['wiki_content'])} chars")
    
    db.close()

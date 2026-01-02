"""
Fandom Wiki Dump Parser - Builds SQLite database from wiki XML dump.

This is a BUILD SCRIPT - run it to create/update the wiki.db file.

Tables created:
  - characters: name, formid, race, gender, role, location, affiliation, wiki_content
  - quests: formid, edid, title, quest_type, location, wiki_content  
  - pages: title, wiki_content (everything else)

Usage:
    python -m src.wiki.dump_parser              # Test with 5000 pages
    python -m src.wiki.dump_parser --full       # Parse entire dump (~200k pages)
    python -m src.wiki.dump_parser --download   # Download dump then parse (TODO)

Requirements:
    pip install mediawiki-dump wikitextparser
    
    Download wiki dump from:
    https://fallout.fandom.com/wiki/Special:Statistics -> Database dumps
    Place at: data/Fallout4/wiki/fallout_pages_current.xml
"""
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check dependencies
try:
    from mediawiki_dump.dumps import LocalFileDump
    from mediawiki_dump.reader import DumpReaderArticles
    HAS_MW_DUMP = True
except ImportError:
    HAS_MW_DUMP = False

try:
    import wikitextparser as wtp
    HAS_WTP = True
except ImportError:
    HAS_WTP = False


class FandomDumpParser:
    """Parses Fandom wiki XML dump into SQLite database."""
    
    DUMP_PATH = Path("data/Fallout4/wiki/fallout_pages_current.xml")
    DB_PATH = Path("data/Fallout4/wiki.db")
    
    # Meta namespaces to skip
    SKIP_NAMESPACES = {
        'Category', 'Template', 'File', 'MediaWiki', 'Module',
        'User', 'Talk', 'Help', 'Portal', 'Draft', 'User talk',
        'Template talk', 'Category talk', 'File talk'
    }
    
    def __init__(self, dump_path: Optional[Path] = None, db_path: Optional[Path] = None):
        self.dump_path = dump_path or self.DUMP_PATH
        self.db_path = db_path or self.DB_PATH
        self.stats = {
            'total': 0, 
            'characters': 0, 
            'quests': 0, 
            'pages': 0, 
            'skipped': 0,
            'errors': 0
        }
        self.conn: Optional[sqlite3.Connection] = None
    
    def parse(self, max_pages: Optional[int] = None) -> bool:
        """
        Parse wiki dump and build SQLite database.
        
        Args:
            max_pages: Limit number of pages (for testing). None = all pages.
            
        Returns:
            True if successful, False otherwise.
        """
        # Check dependencies
        if not HAS_MW_DUMP:
            logger.error("Missing dependency: pip install mediawiki-dump")
            return False
        if not HAS_WTP:
            logger.error("Missing dependency: pip install wikitextparser")
            return False
        
        # Check dump file
        if not self.dump_path.exists():
            logger.error(f"Wiki dump not found: {self.dump_path}")
            logger.info("Download from: https://fallout.fandom.com/wiki/Special:Statistics")
            return False
        
        # Initialize database
        self._init_database()
        
        # Parse dump
        dump_size_mb = self.dump_path.stat().st_size / 1024 / 1024
        logger.info(f"Parsing: {self.dump_path}")
        logger.info(f"Dump size: {dump_size_mb:.0f} MB")
        
        if max_pages:
            logger.info(f"Limiting to {max_pages} pages (test mode)")
        
        dump = LocalFileDump(dump_file=str(self.dump_path))
        reader = DumpReaderArticles()
        
        for page in reader.read(dump):
            self.stats['total'] += 1
            
            if max_pages and self.stats['total'] > max_pages:
                break
            
            try:
                self._process_page(page)
            except Exception as e:
                self.stats['errors'] += 1
                logger.debug(f"Error processing '{page.title}': {e}")
            
            # Commit periodically
            if self.stats['total'] % 1000 == 0:
                self.conn.commit()
            
            # Progress log
            if self.stats['total'] % 10000 == 0:
                self._log_progress()
        
        # Final commit and cleanup
        self.conn.commit()
        self.conn.close()
        
        # Log results
        db_size_mb = self.db_path.stat().st_size / 1024 / 1024
        logger.info("=" * 50)
        logger.info("PARSE COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Total pages:  {self.stats['total']}")
        logger.info(f"Characters:   {self.stats['characters']}")
        logger.info(f"Quests:       {self.stats['quests']}")
        logger.info(f"Other pages:  {self.stats['pages']}")
        logger.info(f"Skipped:      {self.stats['skipped']}")
        logger.info(f"Errors:       {self.stats['errors']}")
        logger.info(f"Database:     {self.db_path} ({db_size_mb:.1f} MB)")
        
        return True
    
    def _init_database(self):
        """Create fresh database with tables and indexes."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove old database
        if self.db_path.exists():
            self.db_path.unlink()
            logger.info(f"Removed old database")
        
        self.conn = sqlite3.connect(str(self.db_path))
        cur = self.conn.cursor()
        
        # Characters table
        cur.execute('''
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                formid TEXT,
                race TEXT,
                gender TEXT,
                role TEXT,
                location TEXT,
                affiliation TEXT,
                wiki_content TEXT
            )
        ''')
        cur.execute('CREATE INDEX idx_char_name ON characters(name COLLATE NOCASE)')
        cur.execute('CREATE INDEX idx_char_formid ON characters(formid)')
        
        # Quests table
        cur.execute('''
            CREATE TABLE quests (
                id INTEGER PRIMARY KEY,
                formid TEXT,
                edid TEXT,
                title TEXT NOT NULL,
                quest_type TEXT,
                location TEXT,
                wiki_content TEXT
            )
        ''')
        cur.execute('CREATE INDEX idx_quest_formid ON quests(formid)')
        cur.execute('CREATE INDEX idx_quest_edid ON quests(edid COLLATE NOCASE)')
        cur.execute('CREATE INDEX idx_quest_title ON quests(title COLLATE NOCASE)')
        
        # General pages table
        cur.execute('''
            CREATE TABLE pages (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL UNIQUE,
                wiki_content TEXT
            )
        ''')
        cur.execute('CREATE INDEX idx_page_title ON pages(title COLLATE NOCASE)')
        
        self.conn.commit()
        logger.info(f"Created database: {self.db_path}")
    
    def _process_page(self, page) -> None:
        """Process a single wiki page."""
        if not page.content or not page.content.strip():
            return
        
        title = page.title.strip()
        
        # Skip meta pages
        if ':' in title:
            namespace = title.split(':')[0]
            if namespace in self.SKIP_NAMESPACES:
                self.stats['skipped'] += 1
                return
        
        parsed = wtp.parse(page.content)
        cur = self.conn.cursor()
        
        # Check for infoboxes to categorize
        for template in parsed.templates:
            tname = template.name.strip().lower()
            
            if 'infobox quest' in tname:
                if self._is_fallout4(template):
                    self._save_quest(cur, title, template, page.content)
                return
            
            elif 'infobox character' in tname:
                if self._is_fallout4(template):
                    self._save_character(cur, title, template, page.content)
                return
        
        # Save as general page if substantial content
        if len(page.content) > 100:
            cur.execute(
                'INSERT OR REPLACE INTO pages (title, wiki_content) VALUES (?, ?)',
                (title, page.content)
            )
            self.stats['pages'] += 1
    
    def _is_fallout4(self, template) -> bool:
        """Check if template is for Fallout 4."""
        games = self._get_arg(template, 'games')
        if not games:
            return True  # Include if no games specified
        games_upper = games.upper()
        return 'FO4' in games_upper or 'FALLOUT 4' in games_upper
    
    def _save_character(self, cur, title: str, infobox, raw_content: str):
        """Save character to database."""
        cur.execute('''
            INSERT INTO characters 
            (name, formid, race, gender, role, location, affiliation, wiki_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title,
            self._clean_formid(self._get_arg(infobox, 'formid')),
            self._get_arg(infobox, 'race'),
            self._get_arg(infobox, 'gender'),
            self._get_arg(infobox, 'role'),
            self._get_arg(infobox, 'location'),
            self._get_arg(infobox, 'affiliation'),
            raw_content  # Store FULL raw wikitext
        ))
        self.stats['characters'] += 1
    
    def _save_quest(self, cur, title: str, infobox, raw_content: str):
        """Save quest to database."""
        cur.execute('''
            INSERT INTO quests 
            (formid, edid, title, quest_type, location, wiki_content)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            self._clean_formid(self._get_arg(infobox, 'formid')),
            self._get_arg(infobox, 'edid'),
            title,
            self._get_arg(infobox, 'type'),
            self._get_arg(infobox, 'location'),
            raw_content  # Store FULL raw wikitext
        ))
        self.stats['quests'] += 1
    
    def _get_arg(self, template, name: str) -> str:
        """Extract template argument value."""
        arg = template.get_arg(name)
        if arg and arg.value:
            text = wtp.remove_markup(str(arg.value))
            return ' '.join(text.split()).strip()
        return ""
    
    def _clean_formid(self, raw: str) -> str:
        """Clean FormID from template markup."""
        if not raw:
            return ""
        # Remove {{ID|...}} wrapper
        raw = raw.replace('{{ID|', '').replace('{{id|', '').replace('}}', '')
        # Extract hex ID pattern
        match = re.search(r'[0-9A-Fa-f]{8}', raw)
        return match.group(0).upper() if match else raw.strip()
    
    def _log_progress(self):
        """Log progress during parsing."""
        logger.info(
            f"Progress: {self.stats['total']} pages | "
            f"C:{self.stats['characters']} Q:{self.stats['quests']} P:{self.stats['pages']}"
        )


def main():
    """CLI entry point."""
    import argparse
    
    arg_parser = argparse.ArgumentParser(description="Parse Fandom wiki dump into SQLite database")
    arg_parser.add_argument("--full", action="store_true", help="Parse all pages (default: 5000 for testing)")
    arg_parser.add_argument("--input", "-i", type=Path, help="Input XML dump path")
    arg_parser.add_argument("--output", "-o", type=Path, help="Output SQLite database path")
    arg_parser.add_argument("--download", action="store_true", help="Download dump (not implemented)")
    args = arg_parser.parse_args()
    
    print("=" * 60)
    print("FANDOM WIKI DUMP PARSER")
    print("=" * 60)
    
    # Create parser with optional paths
    dump_path = args.input if args.input else None
    db_path = args.output if args.output else None
    parser = FandomDumpParser(dump_path=dump_path, db_path=db_path)
    
    print(f"\nInput:  {parser.dump_path}")
    print(f"Output: {parser.db_path}")
    
    if args.download:
        print("\nDownload not yet implemented.")
        print("Please download manually from:")
        print("https://fallout.fandom.com/wiki/Special:Statistics")
        print(f"Save to: {parser.dump_path}")
    elif args.full:
        print("\nMode: FULL PARSE (all pages)")
        print("This may take several minutes...\n")
        parser.parse(max_pages=None)
    else:
        print("\nMode: TEST (5000 pages)")
        print("Use --full for complete parse\n")
        parser.parse(max_pages=5000)


if __name__ == "__main__":
    main()

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '../../posts.db')

class DatabaseHandler:
    def __init__(self, account_name: str = "default"):
        """
        Initialize database handler for a specific account.
        
        Args:
            account_name: Account identifier to track posts separately
        """
        self.account_name = account_name
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.migrate_schema()  # Run migration first

    def create_table(self):
        """Create posts table with enhanced tracking (URL + AT URI)."""
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL DEFAULT 'default',
                    rss_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    bluesky_uri TEXT,
                    bluesky_url TEXT,
                    posted_at TEXT,
                    published_date TEXT,
                    UNIQUE(account_name, rss_url)
                )
            ''')
            # Create indexes for faster lookups
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_account_url 
                ON posts(account_name, rss_url)
            ''')
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_account_title 
                ON posts(account_name, title)
            ''')

    def migrate_schema(self):
        """Migrate existing database schema to support URL-based tracking with AT URI."""
        cursor = self.conn.cursor()
        
        # First, ensure the table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='posts'
        """)
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            # Fresh install - create the table with new schema
            self.create_table()
            return
        
        # Check what columns exist
        cursor.execute("PRAGMA table_info(posts)")
        columns = {column[1] for column in cursor.fetchall()}
        
        # Determine what migration is needed
        needs_migration = False
        
        # Check if we have the new columns
        if 'rss_url' not in columns:
            needs_migration = True
        
        if needs_migration:
            # Migration needed - recreate table with new schema
            self.conn.execute('''
                CREATE TABLE posts_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL DEFAULT 'default',
                    rss_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    bluesky_uri TEXT,
                    bluesky_url TEXT,
                    posted_at TEXT,
                    published_date TEXT,
                    UNIQUE(account_name, rss_url)
                )
            ''')
            
            # Migrate old data - use title as rss_url for backwards compatibility
            if 'account_name' in columns:
                # New-ish schema with account_name
                self.conn.execute('''
                    INSERT INTO posts_new (id, account_name, rss_url, title, published_date)
                    SELECT id, account_name, title, title, published_date FROM posts
                ''')
            else:
                # Very old schema without account_name
                self.conn.execute('''
                    INSERT INTO posts_new (id, account_name, rss_url, title, published_date)
                    SELECT id, 'default', title, title, published_date FROM posts
                ''')
            
            self.conn.execute('DROP TABLE posts')
            self.conn.execute('ALTER TABLE posts_new RENAME TO posts')
            
            # Create indexes
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_account_url 
                ON posts(account_name, rss_url)
            ''')
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_account_title 
                ON posts(account_name, title)
            ''')
            
            self.conn.commit()

    def is_posted(self, rss_url: str = None, title: str = None) -> bool:
        """
        Check if a post has already been made for this account.
        Checks by RSS URL first (most reliable), then falls back to title.
        
        Args:
            rss_url: The RSS article URL
            title: The article title (fallback)
        """
        cursor = self.conn.cursor()
        
        # Primary check: by RSS URL (most reliable)
        if rss_url:
            cursor.execute(
                "SELECT 1 FROM posts WHERE account_name = ? AND rss_url = ?", 
                (self.account_name, rss_url)
            )
            if cursor.fetchone() is not None:
                return True
        
        # Fallback: check by title (for backwards compatibility)
        if title:
            cursor.execute(
                "SELECT 1 FROM posts WHERE account_name = ? AND title = ?", 
                (self.account_name, title)
            )
            if cursor.fetchone() is not None:
                return True
        
        return False

    def save_post(self, rss_url: str, title: str, published_date: str, 
                  bluesky_uri: str = None, bluesky_url: str = None):
        """
        Save a post with full tracking information.
        
        Args:
            rss_url: The RSS article URL
            title: The article title
            published_date: When the article was published
            bluesky_uri: AT URI of the Bluesky post (at://...)
            bluesky_url: Human-readable Bluesky URL
        """
        posted_at = datetime.now().isoformat()
        
        with self.conn:
            self.conn.execute('''
                INSERT OR IGNORE INTO posts 
                (account_name, rss_url, title, bluesky_uri, bluesky_url, posted_at, published_date) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (self.account_name, rss_url, title, bluesky_uri, bluesky_url, posted_at, published_date))

    def close(self):
        self.conn.close()

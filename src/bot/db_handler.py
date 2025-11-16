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
        self.create_table()
        self.migrate_schema()

    def create_table(self):
        """Create posts table with account_name column for multi-account support."""
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    published_date TEXT,
                    UNIQUE(account_name, title)
                )
            ''')
            # Create index for faster lookups
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_account_title 
                ON posts(account_name, title)
            ''')

    def migrate_schema(self):
        """Migrate existing database schema to support multiple accounts."""
        cursor = self.conn.cursor()
        
        # Check if account_name column exists
        cursor.execute("PRAGMA table_info(posts)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'account_name' not in columns:
            # Add account_name column with default value
            self.conn.execute('''
                ALTER TABLE posts ADD COLUMN account_name TEXT NOT NULL DEFAULT 'default'
            ''')
            # Drop old unique constraint if it exists and create new one
            # SQLite doesn't support dropping constraints directly, so we need to recreate the table
            self.conn.execute('''
                CREATE TABLE posts_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    published_date TEXT,
                    UNIQUE(account_name, title)
                )
            ''')
            self.conn.execute('''
                INSERT INTO posts_new (id, account_name, title, published_date)
                SELECT id, 'default', title, published_date FROM posts
            ''')
            self.conn.execute('DROP TABLE posts')
            self.conn.execute('ALTER TABLE posts_new RENAME TO posts')
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_account_title 
                ON posts(account_name, title)
            ''')
            self.conn.commit()

    def is_posted(self, title):
        """Check if the title has already been posted for this account."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM posts WHERE account_name = ? AND title = ?", 
            (self.account_name, title)
        )
        return cursor.fetchone() is not None

    def save_post(self, title, published_date):
        """Save a post's title and published date for this account."""
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO posts (account_name, title, published_date) VALUES (?, ?, ?)",
                (self.account_name, title, published_date)
            )

    def close(self):
        self.conn.close()

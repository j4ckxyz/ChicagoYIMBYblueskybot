import time
import yaml
import os
from datetime import datetime
from atproto import Client
from bot.post_handler import PostHandler
from bot.db_handler import DatabaseHandler
from utils.rss_parser import fetch_new_rss_entries
import logging
from typing import List
from dotenv import load_dotenv
from settings import AccountConfig

class BotLogic:
    def __init__(self, account_config: AccountConfig = None):
        """
        Initialize bot logic for a specific account.
        
        Args:
            account_config: AccountConfig instance with account credentials and settings
        """
        # Load environment variables
        load_dotenv()
        self.config = self._load_config()
        
        # Store account configuration
        if account_config is None:
            # Fallback to legacy mode with environment variables
            from settings import get_accounts
            accounts = get_accounts()
            if not accounts:
                raise Exception("No valid account configuration found")
            account_config = accounts[0]
        
        self.account_config = account_config
        
        # Initialize client with custom PDS URL if provided
        self.client = Client(base_url=account_config.pds_url)
        self.interval = self.config['bot']['check_interval']
        self.max_retries = self.config['bot']['max_retries']
        self.initial_delay = self.config['bot']['initial_delay']
        
        # Initialize database handler if database checking is enabled
        if self.config['bot']['duplicate_detection']['check_database']:
            self.db_handler = DatabaseHandler(account_name=account_config.name)
        else:
            self.db_handler = None
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, self.config['logging']['level']),
            format=self.config['logging']['format']
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing bot for account: {account_config.name} (PDS: {account_config.pds_url})")

        # Try to log in with exponential backoff
        self._login_with_retries()

        # Pass the logged-in client to PostHandler
        self.post_handler = PostHandler(self.client)

    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '../../config.yaml')
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.critical(f"Failed to load config file: {e}")
            raise

    def _login_with_retries(self):
        """Attempt to log in with exponential backoff."""
        retries = 0
        delay = self.initial_delay
        while retries < self.max_retries:
            try:
                self.client.login(
                    self.account_config.username,
                    self.account_config.password
                )
                self.logger.info(f"Logged in successfully as {self.account_config.username}!")
                return
            except Exception as e:
                self.logger.error(f"Login attempt {retries + 1} failed: {e}")
                if "RateLimitExceeded" in str(e):
                    time.sleep(delay)
                    delay *= 2
                    retries += 1
                else:
                    raise e
        raise Exception("Max retries exceeded. Could not log in to Bluesky.")

    def _get_recent_posts(self) -> List[str]:
        """Fetch recent posts from the account to check for duplicates."""
        try:
            profile = self.client.get_profile(self.account_config.username)
            feed = self.client.get_author_feed(profile.did, limit=self.config['bot']['posts_to_check'])
            # Extract text from each post record
            posts = []
            for post in feed.feed:
                try:
                    if hasattr(post, 'post') and hasattr(post.post, 'record') and hasattr(post.post.record, 'text'):
                        posts.append(post.post.record.text.split('\n')[0])
                    elif hasattr(post.record, 'text'):
                        posts.append(post.record.text.split('\n')[0])
                except AttributeError as e:
                    self.logger.warning(f"Unexpected post structure: {e}")
                    continue
            
            self.logger.info(f"[{self.account_config.name}] Extracted {len(posts)} post titles from feed")
            return posts
        except Exception as e:
            self.logger.error(f"Error fetching recent posts: {e}", exc_info=True)
            return []

    def run(self):
        """Run the bot continuously at the specified interval."""
        while True:
            try:
                self.logger.info(f"[{self.account_config.name}] Fetching new RSS entries...")
                
                # Fetch recent posts once at the beginning if Bluesky backup check is enabled
                recent_posts = []
                if self.config['bot']['duplicate_detection']['check_bluesky_backup']:
                    recent_posts = self._get_recent_posts()
                    self.logger.info(f"[{self.account_config.name}] Fetched {len(recent_posts)} recent posts for duplicate checking")
                
                # Create a wrapper function that uses the cached recent_posts
                def is_already_posted_wrapper(title: str, rss_url: str = None) -> bool:
                    try:
                        # Check database if enabled (by URL first, then title)
                        if self.config['bot']['duplicate_detection']['check_database']:
                            if self.db_handler.is_posted(rss_url=rss_url, title=title):
                                self.logger.info(f"Found post in database: {title}")
                                return True
                            
                        # Check recent Bluesky posts if enabled (using cached posts)
                        if self.config['bot']['duplicate_detection']['check_bluesky_backup']:
                            if any(title.lower() in post.lower() for post in recent_posts):
                                self.logger.info(f"Found post in recent Bluesky posts: {title}")
                                # If database sync is enabled and database checking is enabled, sync the post
                                if (self.config['bot']['duplicate_detection']['auto_sync_to_database'] and 
                                    self.config['bot']['duplicate_detection']['check_database']):
                                    try:
                                        self.db_handler.save_post(
                                            rss_url=rss_url or title,
                                            title=title,
                                            published_date=datetime.now().isoformat()
                                        )
                                        self.logger.info(f"Added missing post to database: {title}")
                                    except Exception as e:
                                        self.logger.error(f"Failed to save post to database: {e}")
                                return True
                            
                        return False
                    except Exception as e:
                        self.logger.error(f"Error checking if post exists: {e}")
                        return True  # Err on the side of caution
                
                new_entries = fetch_new_rss_entries(
                    is_already_posted_wrapper,
                    self.config['rss']['min_post_date'],
                    self.account_config.rss_feed_url,
                    max_entries=self.config['bot'].get('max_backfill_entries')
                )
                
                if not new_entries:
                    self.logger.info(f"[{self.account_config.name}] No new entries to post")
                else:
                    self.logger.info(f"[{self.account_config.name}] Found {len(new_entries)} new entries to post")
                
                for entry in new_entries:
                    try:
                        self.logger.info(f"[{self.account_config.name}] Attempting to post: {entry.title}")
                        post_result = self.post_handler.post_entry(entry)
                        
                        # Save successful posts to database if enabled
                        if self.config['bot']['duplicate_detection']['check_database']:
                            try:
                                self.db_handler.save_post(
                                    rss_url=entry.link,
                                    title=entry.title,
                                    published_date=entry.published.isoformat(),
                                    bluesky_uri=post_result.get('uri'),
                                    bluesky_url=post_result.get('url')
                                )
                                self.logger.info(f"[{self.account_config.name}] Successfully saved to database: {entry.title}")
                                if post_result.get('url'):
                                    self.logger.info(f"[{self.account_config.name}] Bluesky post: {post_result.get('url')}")
                            except Exception as e:
                                self.logger.error(f"[{self.account_config.name}] Failed to save post to database: {e}")
                            
                        self.logger.info(f"[{self.account_config.name}] Successfully posted: {entry.title}")
                        # Add a small delay between posts to avoid rate limits
                        time.sleep(5)
                    except Exception as e:
                        self.logger.error(f"[{self.account_config.name}] Error posting entry {entry.title}: {e}")
                        continue

                self.logger.info(f"[{self.account_config.name}] Sleeping for {self.interval} seconds...")
                time.sleep(self.interval)
            except Exception as e:
                self.logger.error(f"[{self.account_config.name}] Error in main loop: {e}")
                self.logger.info(f"[{self.account_config.name}] Sleeping for {self.interval} seconds before retrying...")
                time.sleep(self.interval)

    def __del__(self):
        """Cleanup resources when the bot is destroyed."""
        if self.db_handler:
            try:
                self.db_handler.close()
            except:
                pass

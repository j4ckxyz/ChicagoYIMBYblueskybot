import os
import yaml
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Dict, Optional

load_dotenv()

# Legacy environment variables for backward compatibility
BLUESKY_USERNAME = os.getenv("BLUESKY_USERNAME")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")
RSS_FEED_URL = os.getenv("RSS_FEED_URL")

# Minimum date for RSS entries to be posted (default to November 13, 2024)
MIN_POST_DATE = os.getenv("MIN_POST_DATE", "2024-11-13")
MIN_POST_DATE = datetime.strptime(MIN_POST_DATE, "%Y-%m-%d")

# Load config for global access
def _load_config():
    """Load configuration from YAML file."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), '../config.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise Exception(f"Failed to load config file: {e}")

config = _load_config()

class AccountConfig:
    """Configuration for a single Bluesky account."""
    
    def __init__(self, name: str, pds_url: Optional[str] = None, env_prefix: Optional[str] = None):
        self.name = name
        self.pds_url = pds_url or "https://bsky.social"
        self.env_prefix = env_prefix or name.upper()
        
        # Load credentials from environment variables
        self.username = os.getenv(f"{self.env_prefix}_USERNAME")
        self.password = os.getenv(f"{self.env_prefix}_PASSWORD")
        self.rss_feed_url = os.getenv(f"{self.env_prefix}_RSS_FEED_URL")
        
        # Fallback to legacy env vars if this is the default account and no specific vars exist
        if not self.username and name == "default":
            self.username = BLUESKY_USERNAME
        if not self.password and name == "default":
            self.password = BLUESKY_PASSWORD
        if not self.rss_feed_url and name == "default":
            self.rss_feed_url = RSS_FEED_URL
    
    def is_valid(self) -> bool:
        """Check if account has all required credentials."""
        return bool(self.username and self.password and self.rss_feed_url)
    
    def __repr__(self):
        return f"AccountConfig(name={self.name}, username={self.username}, pds_url={self.pds_url})"

def get_accounts() -> List[AccountConfig]:
    """Load all account configurations from config.yaml."""
    accounts = []
    
    if 'accounts' in config and config['accounts']:
        for account_data in config['accounts']:
            account = AccountConfig(
                name=account_data.get('name', 'default'),
                pds_url=account_data.get('pds_url'),
                env_prefix=account_data.get('env_prefix')
            )
            if account.is_valid():
                accounts.append(account)
            else:
                print(f"Warning: Account '{account.name}' is missing required credentials and will be skipped")
    else:
        # Fallback to legacy single account mode
        account = AccountConfig(name="default")
        if account.is_valid():
            accounts.append(account)
        else:
            print("Warning: No valid account configuration found")
    
    return accounts

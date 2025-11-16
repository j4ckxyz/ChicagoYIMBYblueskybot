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
    
    def __init__(self, name: str):
        self.name = name
        env_prefix = name.upper()
        
        # Load all account-specific settings from environment variables
        self.username = os.getenv(f"{env_prefix}_USERNAME")
        self.password = os.getenv(f"{env_prefix}_PASSWORD")
        self.rss_feed_url = os.getenv(f"{env_prefix}_RSS_FEED_URL")
        self.pds_url = os.getenv(f"{env_prefix}_PDS_URL", "https://bsky.social")
        
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
        for account_name in config['accounts']:
            # Account names can be either strings or dicts (for backward compatibility)
            if isinstance(account_name, dict):
                account_name = account_name.get('name', 'default')
            
            account = AccountConfig(name=account_name)
            if account.is_valid():
                accounts.append(account)
            else:
                print(f"Warning: Account '{account_name}' is missing required credentials and will be skipped")
                print(f"  Add to .env: {account_name.upper()}_USERNAME, {account_name.upper()}_PASSWORD, {account_name.upper()}_RSS_FEED_URL")
    else:
        # Fallback to legacy single account mode
        account = AccountConfig(name="default")
        if account.is_valid():
            accounts.append(account)
        else:
            print("Warning: No valid account configuration found")
    
    return accounts

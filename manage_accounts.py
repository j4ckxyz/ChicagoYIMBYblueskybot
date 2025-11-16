#!/usr/bin/env python3
"""
Account Management CLI Tool for Bluesky RSS Bot

This tool helps you manage your bot accounts easily.
Run: python manage_accounts.py
"""

import os
import sys
import yaml
from pathlib import Path
from getpass import getpass

# ANSI color codes for pretty output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.ENDC}")

def load_config():
    """Load config.yaml"""
    config_path = Path(__file__).parent / 'config.yaml'
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print_error(f"Failed to load config.yaml: {e}")
        sys.exit(1)

def save_config(config):
    """Save config.yaml"""
    config_path = Path(__file__).parent / 'config.yaml'
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        print_success("Configuration saved!")
    except Exception as e:
        print_error(f"Failed to save config.yaml: {e}")

def load_env():
    """Load .env file as a dictionary"""
    env_path = Path(__file__).parent / '.env'
    env_vars = {}
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    return env_vars

def save_env(env_vars):
    """Save environment variables to .env file"""
    env_path = Path(__file__).parent / '.env'
    try:
        with open(env_path, 'w') as f:
            for key, value in sorted(env_vars.items()):
                f.write(f"{key}={value}\n")
        print_success(".env file updated!")
    except Exception as e:
        print_error(f"Failed to save .env file: {e}")

def get_account_info(account_name, env_vars):
    """Get account information from env vars"""
    prefix = account_name.upper()
    return {
        'username': env_vars.get(f"{prefix}_USERNAME", "Not set"),
        'password': '***' if env_vars.get(f"{prefix}_PASSWORD") else "Not set",
        'rss_feed': env_vars.get(f"{prefix}_RSS_FEED_URL", "Not set"),
        'pds_url': env_vars.get(f"{prefix}_PDS_URL", "https://bsky.social (default)")
    }

def list_accounts():
    """List all configured accounts"""
    print_header("Configured Accounts")
    
    config = load_config()
    env_vars = load_env()
    
    if 'accounts' not in config or not config['accounts']:
        print_info("No accounts configured yet. Use option 2 to add one!")
        return
    
    for i, account_name in enumerate(config['accounts'], 1):
        if isinstance(account_name, dict):
            account_name = account_name.get('name', 'unknown')
        
        info = get_account_info(account_name, env_vars)
        
        print(f"{Colors.BOLD}{i}. Account: {account_name}{Colors.ENDC}")
        print(f"   {Colors.CYAN}Username:{Colors.ENDC}     {info['username']}")
        print(f"   {Colors.CYAN}Password:{Colors.ENDC}     {info['password']}")
        print(f"   {Colors.CYAN}RSS Feed:{Colors.ENDC}     {info['rss_feed']}")
        print(f"   {Colors.CYAN}PDS Server:{Colors.ENDC}   {info['pds_url']}")
        print()

def add_account():
    """Add a new account interactively"""
    print_header("Add New Account")
    
    config = load_config()
    env_vars = load_env()
    
    # Get account name
    print(f"{Colors.YELLOW}Enter account name (lowercase, no spaces):{Colors.ENDC}")
    print(f"{Colors.BLUE}Examples: 'chicago', 'housing', 'urbanism'{Colors.ENDC}")
    account_name = input("Name: ").strip().lower()
    
    if not account_name:
        print_error("Account name cannot be empty!")
        return
    
    # Check if account already exists
    accounts_list = config.get('accounts', [])
    existing = [a if isinstance(a, str) else a.get('name') for a in accounts_list]
    if account_name in existing:
        print_error(f"Account '{account_name}' already exists!")
        return
    
    prefix = account_name.upper()
    
    # Get credentials
    print(f"\n{Colors.YELLOW}Enter Bluesky username:{Colors.ENDC}")
    username = input("Username: ").strip()
    
    print(f"\n{Colors.YELLOW}Enter Bluesky app password:{Colors.ENDC}")
    print(f"{Colors.BLUE}Get one at: https://bsky.app/settings/app-passwords{Colors.ENDC}")
    password = getpass("Password (hidden): ").strip()
    
    print(f"\n{Colors.YELLOW}Enter RSS feed URL:{Colors.ENDC}")
    rss_feed = input("RSS Feed: ").strip()
    
    print(f"\n{Colors.YELLOW}Enter custom PDS URL (or press Enter for default bsky.social):{Colors.ENDC}")
    pds_url = input("PDS URL: ").strip()
    
    # Validate inputs
    if not username or not password or not rss_feed:
        print_error("Username, password, and RSS feed are required!")
        return
    
    # Update env vars
    env_vars[f"{prefix}_USERNAME"] = username
    env_vars[f"{prefix}_PASSWORD"] = password
    env_vars[f"{prefix}_RSS_FEED_URL"] = rss_feed
    if pds_url:
        env_vars[f"{prefix}_PDS_URL"] = pds_url
    
    # Update config
    if 'accounts' not in config:
        config['accounts'] = []
    config['accounts'].append(account_name)
    
    # Save everything
    save_env(env_vars)
    save_config(config)
    
    print_success(f"Account '{account_name}' added successfully!")
    print_info(f"Environment variables created: {prefix}_USERNAME, {prefix}_PASSWORD, {prefix}_RSS_FEED_URL")
    if pds_url:
        print_info(f"Custom PDS URL set: {prefix}_PDS_URL")

def remove_account():
    """Remove an account"""
    print_header("Remove Account")
    
    config = load_config()
    env_vars = load_env()
    
    accounts_list = config.get('accounts', [])
    if not accounts_list:
        print_info("No accounts to remove!")
        return
    
    # Display accounts
    print("Select account to remove:\n")
    for i, account_name in enumerate(accounts_list, 1):
        if isinstance(account_name, dict):
            account_name = account_name.get('name', 'unknown')
        print(f"{i}. {account_name}")
    
    print(f"\n{Colors.YELLOW}Enter account number (or 'q' to cancel):{Colors.ENDC}")
    choice = input("Choice: ").strip()
    
    if choice.lower() == 'q':
        print_info("Cancelled")
        return
    
    try:
        index = int(choice) - 1
        if index < 0 or index >= len(accounts_list):
            print_error("Invalid choice!")
            return
        
        account_name = accounts_list[index]
        if isinstance(account_name, dict):
            account_name = account_name.get('name', 'unknown')
        
        # Confirm
        print(f"\n{Colors.RED}Are you sure you want to remove '{account_name}'? (y/n){Colors.ENDC}")
        confirm = input().strip().lower()
        
        if confirm != 'y':
            print_info("Cancelled")
            return
        
        # Remove from config
        accounts_list.pop(index)
        config['accounts'] = accounts_list
        
        # Remove from env
        prefix = account_name.upper()
        env_vars.pop(f"{prefix}_USERNAME", None)
        env_vars.pop(f"{prefix}_PASSWORD", None)
        env_vars.pop(f"{prefix}_RSS_FEED_URL", None)
        env_vars.pop(f"{prefix}_PDS_URL", None)
        
        # Save
        save_config(config)
        save_env(env_vars)
        
        print_success(f"Account '{account_name}' removed!")
        
    except ValueError:
        print_error("Please enter a valid number!")

def main_menu():
    """Display main menu and handle user input"""
    while True:
        print_header("Bluesky RSS Bot - Account Manager")
        
        print(f"{Colors.BOLD}What would you like to do?{Colors.ENDC}\n")
        print(f"  {Colors.GREEN}1.{Colors.ENDC} List all accounts")
        print(f"  {Colors.GREEN}2.{Colors.ENDC} Add new account")
        print(f"  {Colors.GREEN}3.{Colors.ENDC} Remove account")
        print(f"  {Colors.GREEN}4.{Colors.ENDC} Exit")
        
        print(f"\n{Colors.YELLOW}Enter your choice (1-4):{Colors.ENDC}")
        choice = input("> ").strip()
        
        if choice == '1':
            list_accounts()
            input("\nPress Enter to continue...")
        elif choice == '2':
            add_account()
            input("\nPress Enter to continue...")
        elif choice == '3':
            remove_account()
            input("\nPress Enter to continue...")
        elif choice == '4':
            print_info("Goodbye!")
            break
        else:
            print_error("Invalid choice! Please enter 1-4")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.BLUE}Interrupted by user. Goodbye!{Colors.ENDC}")
        sys.exit(0)

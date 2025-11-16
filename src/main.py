import time
import logging
import threading
from bot.bot_logic import BotLogic
from utils.logging_config import setup_logging
from settings import get_accounts

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

def run_bot_instance(account_config):
    """Run a bot instance for a specific account."""
    try:
        logger.info(f"Starting bot instance for account: {account_config.name}")
        bot = BotLogic(account_config)
        bot.run()
    except Exception as e:
        logger.error(f"Error in bot instance for {account_config.name}: {e}", exc_info=True)

def main():
    logger.info("Starting the Bluesky RSS Posting Bot")
    
    # Get all configured accounts
    accounts = get_accounts()
    
    if not accounts:
        logger.error("No valid accounts configured. Please check your config.yaml and environment variables.")
        return
    
    logger.info(f"Found {len(accounts)} configured account(s)")
    
    # If there's only one account, run it in the main thread
    if len(accounts) == 1:
        logger.info(f"Running single account mode for: {accounts[0].name}")
        run_bot_instance(accounts[0])
    else:
        # Multiple accounts - run each in a separate thread
        logger.info(f"Running multi-account mode with {len(accounts)} accounts")
        threads = []
        
        for account in accounts:
            thread = threading.Thread(
                target=run_bot_instance,
                args=(account,),
                name=f"Bot-{account.name}",
                daemon=True
            )
            thread.start()
            threads.append(thread)
            logger.info(f"Started thread for account: {account.name}")
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(60)
                # Check if any threads have died
                for i, thread in enumerate(threads):
                    if not thread.is_alive():
                        logger.warning(f"Thread {thread.name} has stopped. Restarting...")
                        account = accounts[i]
                        new_thread = threading.Thread(
                            target=run_bot_instance,
                            args=(account,),
                            name=f"Bot-{account.name}",
                            daemon=True
                        )
                        new_thread.start()
                        threads[i] = new_thread
        except KeyboardInterrupt:
            logger.info("Shutting down bot...")

if __name__ == "__main__":
    main()

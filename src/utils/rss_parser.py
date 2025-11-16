import feedparser
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from typing import Callable, List
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import os
from settings import config

logger = logging.getLogger(__name__)

class RSSEntry:
    def __init__(self, title: str, link: str, published: datetime, image_url: str = None):
        self.title = title
        self.link = link
        self.published = published
        self.image_url = image_url

def create_session():
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_image_url(article_url: str, session: requests.Session) -> str:
    """
    Extracts the header image URL from the article page based on configured sources.
    """
    try:
        response = session.get(article_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Build image sources list based on configuration
        image_sources = []
        if config['rss']['image_sources'].get('use_og_image', True):
            image_sources.append(('meta', {'property': 'og:image'}, 'content'))
        if config['rss']['image_sources'].get('use_twitter_image', True):
            image_sources.append(('meta', {'name': 'twitter:image'}, 'content'))
        if config['rss']['image_sources'].get('use_wp_post_image', True):
            image_sources.append(('img', {'class': 'wp-post-image'}, 'src'))
        if config['rss']['image_sources'].get('use_first_image', True):
            image_sources.append(('img', {}, 'src'))
        
        for tag, attrs, attr_name in image_sources:
            element = soup.find(tag, attrs)
            if element and element.get(attr_name):
                return element[attr_name]
        
        return None
    except Exception as e:
        logger.error(f"Error fetching image from {article_url}: {e}")
        return None

def fetch_new_rss_entries(is_posted_check: Callable[[str, str], bool], min_post_date: str, rss_feed_url: str) -> List[RSSEntry]:
    """
    Fetch new RSS entries that haven't been posted yet.
    
    Args:
        is_posted_check: Function to check if a title has been posted (takes title and rss_url)
        min_post_date: Minimum date string in format 'YYYY-MM-DD'
        rss_feed_url: URL of the RSS feed to parse
    """
    try:
        feed = feedparser.parse(rss_feed_url)
        if feed.bozo:  # feedparser encountered an error
            logger.error(f"Feed parsing error: {feed.bozo_exception}")
            return []

        new_entries = []
        min_date = datetime.strptime(min_post_date, "%Y-%m-%d")
        session = create_session()

        logger.info(f"Checking {len(feed.entries)} entries from RSS feed")

        for entry in feed.entries:
            try:
                title = entry.title
                rss_url = entry.link
                published = datetime(*entry.published_parsed[:6])

                # Skip if too old
                if published < min_date:
                    logger.debug(f"Skipping old entry: {title} (published {published})")
                    continue
                    
                # Skip if already posted (pass both title and URL)
                if is_posted_check(title, rss_url):
                    logger.debug(f"Skipping already posted entry: {title}")
                    continue

                logger.info(f"New entry found: {title}")
                # Fetch the image URL from the article page
                image_url = fetch_image_url(entry.link, session)
                new_entry = RSSEntry(
                    title=title,
                    link=entry.link,
                    published=published,
                    image_url=image_url
                )
                new_entries.append(new_entry)
                
            except Exception as e:
                logger.error(f"Error processing entry {getattr(entry, 'title', 'unknown')}: {e}")
                continue

        logger.info(f"Found {len(new_entries)} new entries to post")
        return new_entries

    except Exception as e:
        logger.error(f"Error fetching RSS feed: {e}", exc_info=True)
        return []

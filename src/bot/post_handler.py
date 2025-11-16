from atproto import client_utils
from utils.image_utils import download_and_compress_image
from utils.rss_parser import fetch_image_url  # Import fetch_image_url
import logging
from settings import config

logger = logging.getLogger(__name__)

class PostHandler:
    def __init__(self, client):
        self.client = client  # Use an existing, logged-in client instance

    def post_entry(self, entry):
        """
        Post an RSS entry to Bluesky.
        
        Returns:
            dict: Contains 'uri' (AT URI) and 'url' (human-readable URL) of the post
        """
        title = entry.title
        link = entry.link  # Remove the rstrip('.html') to keep the full URL

        # Use configured post format, defaulting to original format if not specified
        post_format = config['bot'].get('post_format', "{title}\n\nRead more: {link}")
        post_text = client_utils.TextBuilder().text(
            post_format.format(title=title, link=link)
        ).link(link, link)

        response = None
        
        # Only process images if the feature flag is enabled
        if config['bot'].get('include_images', True):
            # Access image_url directly as a property
            image_url = entry.image_url or fetch_image_url(link)
            if image_url:
                logger.info(f"Attempting to download and compress image: {image_url}")
                compressed_image_data = download_and_compress_image(image_url)
                if compressed_image_data:
                    try:
                        logger.info("Image compression successful, attempting to send post with image")
                        # Include `image_alts` to provide alt text for accessibility
                        response = self.client.send_images(text=post_text, images=[compressed_image_data], image_alts=[title])
                        logger.info("Post with image sent successfully")
                    except Exception as e:
                        logger.error(f"Failed to send post with image: {e}")
                        logger.info("Falling back to text-only post")
                        response = None
                else:
                    logger.warning("Image compression failed or image is too large, sending text-only post")
            else:
                logger.info("No image URL provided in entry; sending text-only post")
        else:
            logger.info("Image posting is disabled via config; sending text-only post")

        # If we reach here, either images are disabled or image processing failed
        if response is None:
            response = self.client.send_post(text=post_text)
        
        # Extract AT URI and create human-readable URL
        at_uri = response.uri if hasattr(response, 'uri') else None
        bluesky_url = None
        
        if at_uri:
            # Parse AT URI: at://did:plc:xxx/app.bsky.feed.post/xxx
            parts = at_uri.split('/')
            if len(parts) >= 5:
                did = parts[2]
                rkey = parts[4]
                # Get the handle from the client profile
                try:
                    profile = self.client.get_profile(did)
                    handle = profile.handle
                    bluesky_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
                except:
                    # Fallback to DID if we can't get handle
                    bluesky_url = f"https://bsky.app/profile/{did}/post/{rkey}"
        
        return {
            'uri': at_uri,
            'url': bluesky_url
        }

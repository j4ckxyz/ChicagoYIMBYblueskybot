from atproto import client_utils
from utils.image_utils import download_and_compress_image
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
        
        # Bluesky has a 300 character limit - truncate title if needed
        # Calculate how much space we have for the title (300 - format overhead - link length)
        format_overhead = len(post_format) - len("{title}") - len("{link}")
        max_title_length = 300 - format_overhead - len(link)
        
        if len(title) > max_title_length:
            # Truncate and add ellipsis
            title = title[:max_title_length - 1] + "…"
            logger.warning(f"Title truncated to fit 300 char limit: {title}")
        
        # Build text with embedded link - find where {link} appears and make it clickable
        formatted_text = post_format.format(title=title, link=link)
        text_builder = client_utils.TextBuilder()
        
        # Find the link in the formatted text and make it clickable
        link_start = formatted_text.find(link)
        if link_start != -1:
            # Add text before link
            if link_start > 0:
                text_builder.text(formatted_text[:link_start])
            # Add clickable link
            text_builder.link(link, link)
            # Add text after link
            if link_start + len(link) < len(formatted_text):
                text_builder.text(formatted_text[link_start + len(link):])
        else:
            # Fallback if link not found in format
            text_builder.text(formatted_text)
        
        post_text = text_builder

        response = None
        
        # Only process images if the feature flag is enabled
        if config['bot'].get('include_images', True):
            # Access image_url directly as a property
            image_url = entry.image_url
            if image_url:
                logger.info(f"Attempting to download and compress image: {image_url}")
                compressed_image = download_and_compress_image(image_url)
                if compressed_image:
                    try:
                        logger.info("Image compression successful, attempting to send post with image")
                        
                        # Upload the image blob
                        upload_resp = self.client.upload_blob(compressed_image['data'])
                        aspect_ratio = compressed_image['aspect_ratio']
                        
                        # Create the embed structure according to Bluesky docs
                        # https://docs.bsky.app/docs/advanced-guides/posts#images-embeds
                        embed = {
                            "$type": "app.bsky.embed.images",
                            "images": [{
                                "alt": title,
                                "image": upload_resp.blob,
                                "aspectRatio": {
                                    "width": aspect_ratio['width'],
                                    "height": aspect_ratio['height']
                                }
                            }]
                        }
                        
                        # Send post with the embed
                        response = self.client.send_post(text=post_text, embed=embed)
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

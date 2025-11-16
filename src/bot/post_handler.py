from atproto import client_utils
from utils.image_utils import download_and_compress_image
import logging
from settings import config
import requests
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

def parse_facets(text: str):
    """
    Parse rich text facets (hashtags, mentions, URLs) from text.
    Returns list of facets with byte offsets for Bluesky API.
    
    Based on: https://docs.bsky.app/docs/advanced-guides/post-richtext
    """
    facets = []
    
    # Encode text to UTF-8 to get proper byte offsets
    text_bytes = text.encode('utf-8')
    
    # Parse hashtags: #word
    # Pattern matches hashtags that don't start with a digit
    hashtag_pattern = r'(?:^|\s)(#[^\d\s]\S*)(?=\s|$)?'
    for match in re.finditer(hashtag_pattern, text):
        hashtag = match.group(1)
        # Get byte positions
        start_char = match.start(1)
        end_char = match.end(1)
        
        # Convert character positions to byte positions
        byte_start = len(text[:start_char].encode('utf-8'))
        byte_end = len(text[:end_char].encode('utf-8'))
        
        # Extract tag value (strip the # symbol)
        tag = hashtag[1:]
        
        facets.append({
            "index": {
                "byteStart": byte_start,
                "byteEnd": byte_end
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#tag",
                "tag": tag
            }]
        })
    
    # Parse mentions: @handle.bsky.social
    mention_pattern = r'(?:^|\s)(@[a-zA-Z0-9.-]+)(?=\s|$)?'
    for match in re.finditer(mention_pattern, text):
        mention = match.group(1)
        start_char = match.start(1)
        end_char = match.end(1)
        
        byte_start = len(text[:start_char].encode('utf-8'))
        byte_end = len(text[:end_char].encode('utf-8'))
        
        # Extract handle (strip the @ symbol)
        handle = mention[1:]
        
        facets.append({
            "index": {
                "byteStart": byte_start,
                "byteEnd": byte_end
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#mention",
                "did": handle  # Note: In production, you'd resolve handle to DID
            }]
        })
    
    # Parse URLs: http:// or https://
    url_pattern = r'https?://[^\s]+'
    for match in re.finditer(url_pattern, text):
        url = match.group(0)
        start_char = match.start()
        end_char = match.end()
        
        byte_start = len(text[:start_char].encode('utf-8'))
        byte_end = len(text[:end_char].encode('utf-8'))
        
        facets.append({
            "index": {
                "byteStart": byte_start,
                "byteEnd": byte_end
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": url
            }]
        })
    
    return facets if facets else None

class PostHandler:
    def __init__(self, client):
        self.client = client  # Use an existing, logged-in client instance
    
    def _fetch_link_card(self, url: str):
        """
        Fetch Open Graph metadata from a URL to create a link card embed.
        Returns dict with card data or None if unable to fetch.
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Required fields for a card
            card = {
                "uri": url,
                "title": "",
                "description": ""
            }
            
            # Extract og:title
            title_tag = soup.find("meta", property="og:title")
            if title_tag and title_tag.get("content"):
                card["title"] = title_tag["content"]
            else:
                # Fallback to page title
                title = soup.find("title")
                if title:
                    card["title"] = title.get_text().strip()
            
            # Extract og:description
            desc_tag = soup.find("meta", property="og:description")
            if desc_tag and desc_tag.get("content"):
                card["description"] = desc_tag["content"]
            else:
                # Fallback to meta description
                desc = soup.find("meta", attrs={"name": "description"})
                if desc and desc.get("content"):
                    card["description"] = desc["content"]
            
            # Extract og:image for thumbnail
            image_tag = soup.find("meta", property="og:image")
            if image_tag and image_tag.get("content"):
                img_url = image_tag["content"]
                
                # Handle relative URLs
                if img_url.startswith('/'):
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
                elif not img_url.startswith('http'):
                    img_url = url.rstrip('/') + '/' + img_url.lstrip('/')
                
                # Download and upload the thumbnail
                try:
                    img_resp = requests.get(img_url, headers=headers, timeout=10)
                    img_resp.raise_for_status()
                    
                    # Upload as blob
                    upload_resp = self.client.upload_blob(img_resp.content)
                    card["thumb"] = upload_resp.blob
                    logger.info(f"Successfully uploaded card thumbnail from {img_url}")
                except Exception as e:
                    logger.warning(f"Failed to upload card thumbnail: {e}")
                    # Card can still work without thumbnail
            
            # Only return card if we have at least title or description
            if card["title"] or card["description"]:
                logger.info(f"Successfully created link card for {url}")
                return card
            else:
                logger.warning(f"No card metadata found for {url}")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to fetch link card for {url}: {e}")
            return None

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
        
        # Parse facets from the text (hashtags, mentions, URLs)
        facets = parse_facets(formatted_text)

        response = None
        embed = None
        
        # Only process embeds if the feature flag is enabled
        if config['bot'].get('include_images', True):
            # Try to create a link card embed first (preferred - like Twitter cards)
            logger.info(f"Attempting to fetch link card for: {link}")
            card_data = self._fetch_link_card(link)
            
            if card_data:
                # Create external link card embed
                embed = {
                    "$type": "app.bsky.embed.external",
                    "external": card_data
                }
                logger.info("Using link card embed")
            else:
                 # Fallback to image embed if we have an image URL
                image_url = entry.image_url
                if image_url:
                    logger.info(f"No link card available, attempting image embed: {image_url}")
                    try:
                        compressed_image = download_and_compress_image(image_url)
                        if compressed_image:
                            # Upload the image blob
                            upload_resp = self.client.upload_blob(compressed_image['data'])
                            aspect_ratio = compressed_image['aspect_ratio']
                            
                            # Create image embed
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
                            logger.info("Using image embed as fallback")
                        else:
                            logger.warning("Image compression failed, will post text-only")
                    except Exception as e:
                        logger.error(f"Failed to create image embed: {e}, will post text-only")
                        embed = None
                else:
                    logger.info("No image URL available, will post text-only")
        
        # Send the post with embed (if available)
        try:
            if embed:
                response = self.client.send_post(text=formatted_text, facets=facets, embed=embed)
                logger.info("Post with embed sent successfully")
            else:
                response = self.client.send_post(text=formatted_text, facets=facets)
                logger.info("Text-only post sent successfully")
        except Exception as e:
            logger.error(f"Failed to send post: {e}")
            # Try fallback without embed
            if embed:
                logger.info("Retrying without embed...")
                try:
                    response = self.client.send_post(text=formatted_text, facets=facets)
                    logger.info("Text-only fallback post sent successfully")
                except Exception as e2:
                    logger.error(f"Fallback post also failed: {e2}")
                    raise
        
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

from io import BytesIO
from PIL import Image
import requests
import time
import logging

logger = logging.getLogger(__name__)

def download_and_compress_image(image_url, max_size_kb=1000, max_retries=3, backoff_factor=2, initial_delay=5):
    """
    Downloads and compresses the image to be under the max_size_kb limit, with retry logic.
    
    Returns:
        dict: Contains 'data' (image bytes) and 'aspect_ratio' (width/height ratio), or None if failed
    """
    attempt = 0
    delay = initial_delay

    while attempt < max_retries:
        try:
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                # Process the image if download is successful
                image = Image.open(BytesIO(response.content))
                original_width, original_height = image.size
                
                max_dimension = 1024
                if max(image.size) > max_dimension:
                    image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

                if image.format != "JPEG":
                    image = image.convert("RGB")

                output = BytesIO()
                image.save(output, format="JPEG", quality=65)
                output.seek(0)

                # Check if the compressed image size is within the allowed limit
                size_kb = output.tell() / 1024
                if size_kb <= max_size_kb:
                    # Get final image dimensions after compression
                    final_width, final_height = image.size
                    aspect_ratio = {
                        'width': final_width,
                        'height': final_height
                    }
                    logger.info(f"Image downloaded and compressed successfully: {image_url} ({final_width}x{final_height})")
                    return {
                        'data': output.getvalue(),
                        'aspect_ratio': aspect_ratio
                    }
                else:
                    logger.warning(f"Image too large even after compression: {size_kb:.2f} KB. Skipping image.")
                    return None

            else:
                logger.warning(f"Failed to download image (status code: {response.status_code}). Retrying...")

        except requests.RequestException as e:
            logger.error(f"Error downloading image: {e}. Retrying...")

        attempt += 1
        time.sleep(delay)
        delay *= backoff_factor  # Exponential backoff

    logger.error(f"Failed to download image after {max_retries} attempts: {image_url}")
    return None

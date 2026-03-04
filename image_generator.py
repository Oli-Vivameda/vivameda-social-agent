"""Generate featured images for social media posts using OpenAI DALL-E."""
import os
import logging
import httpx
import tempfile

log = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


def generate_image(prompt: str) -> str | None:
    """
    Generate an image from a prompt using DALL-E 3.
    Returns the file path to the downloaded image, or None on failure.
    """
    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY not set — skipping image generation")
        return None

    log.info(f"Generating image: {prompt[:80]}...")

    resp = httpx.post(
        "https://api.openai.com/v1/images/generations",
        json={
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1792x1024",  # Landscape 16:9-ish
            "quality": "standard",
        },
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    image_url = data["data"][0]["url"]

    # Download image to temp file
    img_resp = httpx.get(image_url, timeout=30)
    img_resp.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(img_resp.content)
    tmp.close()

    log.info(f"Image downloaded: {tmp.name} ({len(img_resp.content) / 1024:.0f} KB)")
    return tmp.name

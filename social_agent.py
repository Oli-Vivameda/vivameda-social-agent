#!/usr/bin/env python3
"""
Vivameda Social Media Agent
Posts daily content to LinkedIn and X (Twitter).
Finds trending workforce/data topics, generates platform-specific content,
and publishes via official APIs.
"""

import os
import sys
import json
import random
import logging
import argparse
from datetime import datetime

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
try:
    import anthropic
    import httpx
except ImportError:
    log.error("Missing dependencies. Run: pip install anthropic httpx")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
from config import (
    ANTHROPIC_API_KEY,
    BRAVE_API_KEY,
    LINKEDIN_ACCESS_TOKEN,
    LINKEDIN_ACCESS_TOKEN_LISA,
    LINKEDIN_BIZ_ACCESS_TOKEN,
    LINKEDIN_COMPANY_ID,
    X_API_KEY,
    X_API_SECRET,
    X_ACCESS_TOKEN,
    X_ACCESS_SECRET,
    X_BIZ_API_KEY,
    X_BIZ_API_SECRET,
    X_BIZ_ACCESS_TOKEN,
    X_BIZ_ACCESS_SECRET,
    BLOG_MODEL,
)
from style_guide import VIVAMEDA_VOICE, OLI_PERSONAL_VOICE, LISA_PERSONAL_VOICE
from topic_discovery import discover_topics

# Optional image generation
try:
    from image_generator import generate_image
    HAS_IMAGE_GEN = True
except ImportError:
    HAS_IMAGE_GEN = False


# ---------------------------------------------------------------------------
# Topic Selection (same pattern as blog agent)
# ---------------------------------------------------------------------------
TOPIC_SELECTOR_PROMPT = """You are a social media strategist for Vivameda, a company that provides 
large-scale workforce intelligence data (250M+ records, 2010-2025, 100+ countries).

Given these trending topics, select TWO different topics: one for LinkedIn and one for X (Twitter).
They should be DIFFERENT topics, not the same topic reworded.

CRITICAL: Every post must connect the news back to what Vivameda does. The pattern is:
1. Start with the trending news/topic as a hook
2. Flip it into WHY workforce data, company intelligence, or longitudinal business data matters
3. End with an insight that only someone with access to large-scale workforce data would have

Vivameda provides: workforce intelligence across 250M+ professional records, company headcount tracking,
hiring/layoff trend data, skills migration data, organizational structure analysis, and business
intelligence datasets. The current product is a US agency intelligence dataset (46,575 decision-makers).

LinkedIn audience: investment researchers, HR-tech leaders, data buyers, enterprise decision makers.
X audience: data people, startup founders, VCs, analysts, alternative data enthusiasts.

Trending topics:
{topics}

Respond in JSON:
{{
  "linkedin_topic": "...",
  "linkedin_angle": "2-3 sentences on the LinkedIn post angle. MUST explain how this connects to workforce data or business intelligence.",
  "x_topic": "...",
  "x_angle": "1-2 sentences on the X post angle. MUST flip the news into a workforce data insight."
}}
"""


def select_topics(topics: list[str]) -> dict:
    """Use Claude to pick two different topics for each platform."""
    from topic_discovery import load_topic_history, save_topic_history

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    topic_list = "\n".join(f"- {t}" for t in topics)

    # Include recent history so Claude avoids repeats
    history = load_topic_history()
    history_text = ""
    if history:
        recent = history[-10:]
        history_text = "\n\nTOPICS ALREADY USED RECENTLY (do NOT pick these or anything too similar):\n"
        history_text += "\n".join(f"- {h[:80]}" for h in recent)

    resp = client.messages.create(
        model=BLOG_MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": TOPIC_SELECTOR_PROMPT.format(topics=topic_list) + history_text,
        }],
    )
    text = resp.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1].replace("json", "", 1).strip()
    selection = json.loads(text)

    # Save selected topics to history
    save_topic_history([selection["linkedin_topic"], selection["x_topic"]])

    return selection


# ---------------------------------------------------------------------------
# Content Generation
# ---------------------------------------------------------------------------
LINKEDIN_PROMPT = """Write a LinkedIn post for Vivameda (workforce intelligence company).

Topic: {topic}
Angle: {angle}

{voice}

RULES:
- 150-250 words
- Opening hook (first line gets people to stop scrolling)
- Use the trending topic as a hook, then FLIP it into why workforce data or business intelligence matters
- The post should demonstrate the kind of insight you can only get from tracking workforce movements at scale
- Reference specific data points where possible (headcount shifts, hiring patterns, skills migration)
- No hashtags in the body, add exactly 3 lowercase hashtags at the very end (e.g. #workforcedata not #WorkforceData)
- Conversational but professional tone
- End with a thought-provoking question or bold statement
- Do NOT be salesy or mention Vivameda's products directly
- Write as a thought leader sharing knowledge, not a company promoting itself
- Use line breaks between paragraphs for readability
- NEVER use em dashes or en dashes. Use commas, semicolons, colons, or periods instead.
"""

X_PROMPT = """Write a tweet (X post) for Vivameda (workforce intelligence company).

Topic: {topic}
Angle: {angle}

{voice}

RULES:
- 500-1000 characters. Develop the thought, give context, make it substantial.
- Provocative and opinionated
- Use the trending topic as a hook, then FLIP it into a workforce data insight
- Show the kind of thinking that comes from tracking millions of professional records over 15 years
- One clear insight or hot take, backed with reasoning
- No hashtags unless they fit naturally. Max 3, all lowercase (e.g. #workforcedata not #WorkforceData)
- No emojis
- Make people want to reply or retweet
- Do NOT mention Vivameda
- NEVER use em dashes or en dashes. Use commas, semicolons, colons, or periods instead.
"""

IMAGE_STYLES = [
    {
        "name": "code on dark screen",
        "dalle_style": "vivid",
        "prompt": "Close-up photograph of glowing programming code on a dark monitor screen relating to {topic}. Lines of code in amber and cyan on a deep black background. Syntax highlighting visible. Slight bokeh and lens blur at edges. Like looking at a developer terminal in a dark room. Moody, technical, authentic. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image.",
    },
    {
        "name": "data center server room",
        "dalle_style": "natural",
        "prompt": "Photograph of a modern data center server room relating to {topic}. Rows of server racks with blinking LED lights in blue, green, and amber. Cold blue ambient lighting. Reflective floor. Deep perspective down the aisle. Industrial, powerful, technical. Professional photography. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image.",
    },
    {
        "name": "circuit board macro",
        "dalle_style": "natural",
        "prompt": "Extreme macro photograph of a circuit board relating to {topic}. Visible traces, solder points, microchips, and capacitors. Shallow depth of field with selective focus. Dark background with blue and green tones. Like an electron microscope view of technology infrastructure. Technical and beautiful. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image.",
    },
    {
        "name": "technical watercolor mashup",
        "dalle_style": "vivid",
        "prompt": "Artistic watercolor painting blended with technical elements relating to {topic}. Human head silhouette filled with circuit board patterns, gears, data nodes, and flowing digital elements. Watercolor ink drips and splashes in deep navy, amber, and rust tones on aged parchment background. Where art meets engineering. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image.",
    },
    {
        "name": "isometric 3D diorama",
        "dalle_style": "vivid",
        "prompt": "Isometric 3D miniature diorama scene relating to {topic}. Detailed tiny world on a floating platform with dark background. Glowing warm lights, miniature buildings, trees, and technical infrastructure. Like a tilt-shift photograph of a model. Rich detail, dramatic single spotlight from above. Dark green and amber tones. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image.",
    },
    {
        "name": "terminal hacker screen",
        "dalle_style": "vivid",
        "prompt": "Dark terminal screen with scrolling data output relating to {topic}. Green and amber monospace font on pure black background. Matrix-style data streams mixed with realistic terminal commands. Multiple overlapping transparent terminal windows. Like a hacker workstation at 3am. Technical and atmospheric. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image.",
    },
    {
        "name": "network topology visualization",
        "dalle_style": "vivid",
        "prompt": "Technical visualization of a complex network topology relating to {topic}. Interconnected nodes and edges forming a large-scale graph on a dark background. Nodes glow in electric blue and white, connections pulse with data flow. Like a real-time infrastructure monitoring dashboard. Scientific and precise. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image.",
    },
    {
        "name": "blueprint technical drawing",
        "dalle_style": "vivid",
        "prompt": "Technical blueprint-style drawing relating to {topic}. White line drawings on deep blue background. Engineering diagrams, data flow charts, and system architecture sketches. Grid lines visible. Like an architect's technical plan for a data system. Precise, structured, professional. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image.",
    },
]

STYLE_HISTORY_FILE = ".style_history.json"
CUSTOM_IMAGES_DIR = "images"
CUSTOM_IMAGE_CHANCE_LINKEDIN = 0.40  # ~2 out of 3 for LinkedIn
CUSTOM_IMAGE_CHANCE_X = 0.0  # ~1 out of 3 for X
USED_IMAGES_FILE = ".used_images.json"


def pick_custom_image() -> str | None:
    """Pick a random unused custom image from images/ folder. Returns path or None."""
    if not os.path.isdir(CUSTOM_IMAGES_DIR):
        return None

    all_images = [
        f for f in os.listdir(CUSTOM_IMAGES_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]
    if not all_images:
        return None

    # Load used images history
    used = []
    try:
        if os.path.exists(USED_IMAGES_FILE):
            with open(USED_IMAGES_FILE) as f:
                used = json.load(f).get("used", [])
    except Exception:
        pass

    # Filter out recently used
    available = [img for img in all_images if img not in used]
    if not available:
        # All used, reset
        available = all_images
        used = []

    chosen = random.choice(available)
    used.append(chosen)

    # Save used history
    try:
        with open(USED_IMAGES_FILE, "w") as f:
            json.dump({"used": used[-50:]}, f)
    except Exception:
        pass

    return os.path.join(CUSTOM_IMAGES_DIR, chosen)


def generate_content(selection: dict) -> dict:
    """Generate independent content for each platform."""
    # Personal voice on odd days, business voice on even days
    day_of_year = datetime.now().timetuple().tm_yday
    is_personal = (day_of_year % 2 != 0)
    linkedin_voice = OLI_PERSONAL_VOICE  # Always Oli voice on LinkedIn
    x_voice = OLI_PERSONAL_VOICE if is_personal else VIVAMEDA_VOICE
    log.info(f"LinkedIn voice: {'OLI' if is_personal else 'LISA'}, X voice: {'OLI' if is_personal else 'VIVAMEDA'}")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # LinkedIn post
    log.info(f"Generating LinkedIn post on: {selection['linkedin_topic'][:60]}...")
    li_resp = client.messages.create(
        model=BLOG_MODEL,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": LINKEDIN_PROMPT.format(
                topic=selection["linkedin_topic"],
                angle=selection["linkedin_angle"],
                voice=linkedin_voice,
            ),
        }],
    )
    linkedin_post = li_resp.content[0].text.strip()
    linkedin_post = linkedin_post.replace("—", ",").replace("–", ",")

    # X post
    log.info(f"Generating X post on: {selection['x_topic'][:60]}...")
    x_resp = client.messages.create(
        model=BLOG_MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": X_PROMPT.format(
                topic=selection["x_topic"],
                angle=selection["x_angle"],
                voice=x_voice,
            ),
        }],
    )
    x_post = x_resp.content[0].text.strip()

    # Strip any em/en dashes that slipped through
    x_post = x_post.replace("—", ",").replace("–", ",")

    # Generate image prompts directly (no Claude middleman)
    # Load style history to avoid repeats
    import json as _json
    style_history = []
    if os.path.exists(STYLE_HISTORY_FILE):
        try:
            with open(STYLE_HISTORY_FILE) as _f:
                style_history = _json.load(_f).get("styles", [])[-8:]
        except Exception:
            pass

    # Filter out recently used styles
    available = [s for s in IMAGE_STYLES if s["name"] not in style_history]
    if len(available) < 2:
        available = IMAGE_STYLES  # Reset if we've used them all

    li_style, x_style = random.sample(available, 2)
    log.info(f"Image styles: LinkedIn={li_style['name']}, X={x_style['name']}")

    # Save to history
    style_history.extend([li_style["name"], x_style["name"]])
    try:
        with open(STYLE_HISTORY_FILE, "w") as _f:
            _json.dump({"styles": style_history[-12:]}, _f)
    except Exception:
        pass

    # Build prompts directly with topic inserted
    # Strip company/brand names from image prompts to avoid DALL-E rejections
    _brands = ["Databricks","Google","Microsoft","Amazon","Meta","Apple","OpenAI","Anthropic","Tesla","Nvidia","Intel","IBM","Oracle","Salesforce","SAP","Snowflake","Palantir","Stripe","Uber","Airbnb","Netflix","Spotify","Adobe","Zoom","Slack","HubSpot","Workday","ServiceNow","Atlassian","Shopify","MongoDB","GitLab","GitHub","LinkedIn","Twitter","TikTok","ByteDance","CMU","MIT","Stanford","Harvard","AWS","Azure","Figma","Canva","Reddit","Discord"]
    _safe_li = selection["linkedin_topic"][:80]
    _safe_x = selection["x_topic"][:80]
    for _b in _brands:
        _safe_li = _safe_li.replace(_b, "a leading organization")
        _safe_x = _safe_x.replace(_b, "a leading organization")
    li_image_prompt = li_style["prompt"].format(topic=_safe_li)
    x_image_prompt = x_style["prompt"].format(topic=_safe_x)

    return {
        "linkedin": linkedin_post,
        "linkedin_topic": selection["linkedin_topic"],
        "linkedin_image_prompt": li_image_prompt,
        "linkedin_dalle_style": li_style["dalle_style"],
        "x": x_post,
        "x_topic": selection["x_topic"],
        "x_image_prompt": x_image_prompt,
        "x_dalle_style": x_style["dalle_style"],
    }


# ---------------------------------------------------------------------------
# LinkedIn Publishing
# ---------------------------------------------------------------------------
def get_linkedin_user_id(access_token: str) -> str:
    """Get LinkedIn user URN."""
    resp = httpx.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()["sub"]


def post_to_linkedin(text: str, access_token: str, image_path: str = None, company_id: str = None) -> dict:
    """Publish a post to LinkedIn, optionally with an image. If company_id is set, posts as company page."""
    if company_id:
        author = f"urn:li:organization:{company_id}"
    else:
        user_id = get_linkedin_user_id(access_token)
        author = f"urn:li:person:{user_id}"

    if image_path:
        # Step 1: Register image upload
        log.info("Uploading image to LinkedIn...")
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": author,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        }
        reg_resp = httpx.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            json=register_payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        reg_resp.raise_for_status()
        reg_data = reg_resp.json()

        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = reg_data["value"]["asset"]

        # Step 2: Upload the image binary (strip EXIF/metadata to avoid AI detection)
        from PIL import Image
        import io

        try:
            img = Image.open(image_path)
            clean = Image.new(img.mode, img.size)
            clean.putdata(list(img.getdata()))
            buf = io.BytesIO()
            fmt = "PNG" if image_path.lower().endswith(".png") else "JPEG"
            clean.save(buf, format=fmt, quality=95)
            image_bytes = buf.getvalue()
            log.info("Stripped image metadata for LinkedIn upload")
        except Exception as e:
            log.warning(f"Could not strip metadata ({e}), uploading raw")
            with open(image_path, "rb") as f:
                image_bytes = f.read()

        upload_resp = httpx.put(
            upload_url,
            content=image_bytes,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "image/png",
            },
        )
        upload_resp.raise_for_status()
        log.info(f"Image uploaded to LinkedIn: {asset}")

        # Step 3: Post with image
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "media": asset,
                    }],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
    else:
        # Text-only post
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

    resp = httpx.post(
        "https://api.linkedin.com/v2/ugcPosts",
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )
    resp.raise_for_status()
    log.info(f"LinkedIn post published! ID: {resp.json().get('id', 'unknown')}")
    return resp.json()


# ---------------------------------------------------------------------------
# X (Twitter) Publishing
# ---------------------------------------------------------------------------
def post_to_x(text: str, image_path: str = None, api_key: str = None, api_secret: str = None, access_token: str = None, access_secret: str = None) -> dict:
    """Publish a tweet using OAuth 1.0a, optionally with an image."""
    import hashlib
    import hmac
    import time
    import urllib.parse
    import uuid
    import base64

    # Default to personal account credentials
    api_key = api_key or X_API_KEY
    api_secret = api_secret or X_API_SECRET
    access_token = access_token or X_ACCESS_TOKEN
    access_secret = access_secret or X_ACCESS_SECRET

    media_id = None

    # Upload image first if provided
    if image_path:
        log.info("Uploading image to X...")
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"

        # Strip EXIF/metadata to avoid AI detection
        from PIL import Image
        import io

        try:
            img = Image.open(image_path)
            clean = Image.new(img.mode, img.size)
            clean.putdata(list(img.getdata()))
            buf = io.BytesIO()
            fmt = "PNG" if image_path.lower().endswith(".png") else "JPEG"
            clean.save(buf, format=fmt, quality=95)
            image_bytes = buf.getvalue()
            log.info("Stripped image metadata for X upload")
        except Exception as e:
            log.warning(f"Could not strip metadata ({e}), uploading raw")
            with open(image_path, "rb") as f:
                image_bytes = f.read()

        media_b64 = base64.b64encode(image_bytes).decode()

        # OAuth for upload
        oauth_params = {
            "oauth_consumer_key": api_key,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": access_token,
            "oauth_version": "1.0",
        }

        body_params = {"media_data": media_b64}
        all_params = {**oauth_params, **body_params}

        params_string = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
            for k, v in sorted(all_params.items())
        )
        base_string = f"POST&{urllib.parse.quote(upload_url, safe='')}&{urllib.parse.quote(params_string, safe='')}"
        signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
        signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
        oauth_params["oauth_signature"] = base64.b64encode(signature).decode()

        auth_header = "OAuth " + ", ".join(
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        )

        upload_resp = httpx.post(
            upload_url,
            data={"media_data": media_b64},
            headers={"Authorization": auth_header},
            timeout=60,
        )
        upload_resp.raise_for_status()
        media_id = upload_resp.json().get("media_id_string")
        log.info(f"Image uploaded to X: media_id={media_id}")

    # Post tweet
    url = "https://api.x.com/2/tweets"

    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    params_string = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = f"POST&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(params_string, safe='')}"
    signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
    signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    oauth_params["oauth_signature"] = base64.b64encode(signature).decode()

    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )

    tweet_body = {"text": text}
    if media_id:
        tweet_body["media"] = {"media_ids": [media_id]}

    resp = httpx.post(
        url,
        json=tweet_body,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    tweet_id = data.get("data", {}).get("id", "unknown")
    log.info(f"X post published! ID: {tweet_id}")
    return data




def retweet_from_other_account(tweet_id: str, api_key: str, api_secret: str, 
                                access_token: str, access_secret: str):
    """Retweet a post from the other X account."""
    # First get the user ID for this account
    user_url = "https://api.x.com/2/users/me"
    
    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    
    params_string = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = f"GET&{urllib.parse.quote(user_url, safe='')}&{urllib.parse.quote(params_string, safe='')}"
    signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
    signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    oauth_params["oauth_signature"] = base64.b64encode(signature).decode()
    
    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    
    user_resp = httpx.get(user_url, headers={"Authorization": auth_header}, timeout=15)
    user_resp.raise_for_status()
    user_id = user_resp.json().get("data", {}).get("id")
    
    if not user_id:
        log.warning("Could not get user ID for retweet")
        return
    
    # Now retweet
    rt_url = f"https://api.x.com/2/users/{user_id}/retweets"
    
    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    
    params_string = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = f"POST&{urllib.parse.quote(rt_url, safe='')}&{urllib.parse.quote(params_string, safe='')}"
    signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
    signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    oauth_params["oauth_signature"] = base64.b64encode(signature).decode()
    
    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    
    rt_resp = httpx.post(
        rt_url,
        json={"tweet_id": tweet_id},
        headers={"Authorization": auth_header, "Content-Type": "application/json"},
        timeout=15,
    )
    rt_resp.raise_for_status()
    log.info(f"Retweeted {tweet_id} from other account")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Vivameda Social Media Agent")
    parser.add_argument("--dry-run", action="store_true", help="Preview content without posting")
    parser.add_argument("--linkedin-only", action="store_true", help="Only post to LinkedIn")
    parser.add_argument("--x-only", action="store_true", help="Only post to X")
    parser.add_argument("--topic", type=str, help="Override topic (skip discovery)")
    args = parser.parse_args()

    post_linkedin = not args.x_only
    post_x = not args.linkedin_only

    # Step 1: Discover topics
    if args.topic:
        topics = [args.topic]
        log.info(f"Using manual topic: {args.topic}")
    else:
        log.info("Discovering trending topics...")
        topics = discover_topics()

    # Step 2: Select topics (one per platform)
    log.info("Selecting topics with Claude...")
    selection = select_topics(topics)
    log.info(f"LinkedIn topic: {selection['linkedin_topic'][:60]}...")
    log.info(f"X topic: {selection['x_topic'][:60]}...")

    # Step 3: Generate content
    content = generate_content(selection)

    # Determine if today is a personal (Oli) day
    day_of_year = datetime.now().timetuple().tm_yday
    is_personal = (day_of_year % 2 != 0)

    # Step 4: Generate images
    li_image_path = None
    x_image_path = None
    if not args.dry_run:
        # LinkedIn: custom images ~2/3 on personal (Oli) days only
        if post_linkedin:
            custom = None
            if is_personal and random.random() < CUSTOM_IMAGE_CHANCE_LINKEDIN:
                custom = pick_custom_image()
            if custom:
                li_image_path = custom
                log.info(f"Using custom image for LinkedIn: {li_image_path}")
            elif HAS_IMAGE_GEN:
                log.info("Generating LinkedIn image with DALL-E...")
                try:
                    li_image_path = generate_image(
                        content["linkedin_image_prompt"],
                        style=content.get("linkedin_dalle_style", "vivid"),
                    )
                    log.info(f"LinkedIn image saved: {li_image_path}")
                except Exception as e:
                    log.warning(f"LinkedIn image failed: {e}")
                    fallback = pick_custom_image()
                    if fallback:
                        li_image_path = fallback
                        log.info(f"DALL-E failed, using custom photo: {li_image_path}")
                    fallback = pick_custom_image()
                    if fallback:
                        li_image_path = fallback
                        log.info(f"Fallback to custom image: {li_image_path}")

        # X: custom images ~1/3 on personal (Oli) days only
        if post_x:
            custom = None
            if is_personal and random.random() < CUSTOM_IMAGE_CHANCE_X:
                custom = pick_custom_image()
            if custom:
                x_image_path = custom
                log.info(f"Using custom image for X: {x_image_path}")
            elif HAS_IMAGE_GEN:
                log.info("Generating X image with DALL-E...")
                try:
                    x_image_path = generate_image(
                        content["x_image_prompt"],
                        style=content.get("x_dalle_style", "vivid"),
                    )
                    log.info(f"X image saved: {x_image_path}")
                except Exception as e:
                    log.warning(f"X image failed: {e}")
                    fallback = pick_custom_image()
                    if fallback:
                        x_image_path = fallback
                        log.info(f"DALL-E failed, using custom photo: {x_image_path}")
                    fallback = pick_custom_image()
                    if fallback:
                        x_image_path = fallback
                        log.info(f"Fallback to custom image: {x_image_path}")

    # Step 5: Preview or publish
    if post_linkedin:
        print("\n" + "=" * 60)
        print(f"LINKEDIN — {content['linkedin_topic']}")
        print("=" * 60)
        print(content["linkedin"])
        print(f"\n({len(content['linkedin'])} characters)")

    if post_x:
        print("\n" + "=" * 60)
        print(f"X — {content['x_topic']}")
        print("=" * 60)
        print(content["x"])
        print(f"\n({len(content['x'])} characters)")

    print("=" * 60)

    if args.dry_run:
        print("\nDRY RUN — nothing posted.")
        return

    # Determine account: odd day = Oli personal, even day = business X + Lisa LinkedIn
    day_of_year = datetime.now().timetuple().tm_yday
    is_business_day = (day_of_year % 2 == 0)
    account_label = "LISA" if is_business_day else "OLI"
    log.info(f"Day {day_of_year} of year, LinkedIn posting to {account_label}")

    # Publish
    # LinkedIn: always post to Oli's profile
    if post_linkedin:
        token = LINKEDIN_ACCESS_TOKEN
        label = "Oli"

        if not token:
            log.warning(f"LinkedIn token for {label} not set, skipping LinkedIn")
        else:
            try:
                post_to_linkedin(content["linkedin"], token, li_image_path)
                log.info(f"Posted to LinkedIn: {label}'s profile")
            except Exception as e:
                log.error(f"LinkedIn post failed ({label}): {e}")

    # X: alternate personal/business by day
    if post_x:
        if is_business_day:
            if not X_BIZ_API_KEY or not X_BIZ_ACCESS_TOKEN:
                log.warning("X business credentials not set, skipping X")
            else:
                try:
                    result = post_to_x(content["x"], x_image_path,
                              api_key=X_BIZ_API_KEY, api_secret=X_BIZ_API_SECRET,
                              access_token=X_BIZ_ACCESS_TOKEN, access_secret=X_BIZ_ACCESS_SECRET)
                    log.info("Posted to X BUSINESS account")
                    # Cross-retweet from personal account
                    tid = result.get("data", {}).get("id") if result else None
                    if tid and X_API_KEY and X_ACCESS_TOKEN:
                        try:
                            time.sleep(5)
                            retweet_from_other_account(tid, X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
                            log.info("Personal account retweeted business post")
                        except Exception as e2:
                            log.warning(f"Cross-retweet failed: {e2}")
                except Exception as e:
                    log.error(f"X business post failed: {e}")
        else:
            if not X_API_KEY or not X_ACCESS_TOKEN:
                log.warning("X API credentials not set, skipping X")
            else:
                try:
                    result = post_to_x(content["x"], x_image_path)
                    log.info("Posted to X PERSONAL account")
                    # Cross-retweet from business account
                    tid = result.get("data", {}).get("id") if result else None
                    if tid and X_BIZ_API_KEY and X_BIZ_ACCESS_TOKEN:
                        try:
                            time.sleep(5)
                            retweet_from_other_account(tid, X_BIZ_API_KEY, X_BIZ_API_SECRET, X_BIZ_ACCESS_TOKEN, X_BIZ_ACCESS_SECRET)
                            log.info("Business account retweeted personal post")
                        except Exception as e2:
                            log.warning(f"Cross-retweet failed: {e2}")
                except Exception as e:
                    log.error(f"X post failed: {e}")

    # Cleanup
    for path in [li_image_path, x_image_path]:
        if path and os.path.exists(path):
            os.remove(path)

    print("\nDone!")


if __name__ == "__main__":
    main()

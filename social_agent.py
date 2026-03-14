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
        "name": "editorial watercolor",
        "dalle_style": "vivid",
        "prompt": "Editorial watercolor and ink illustration depicting {topic}. Loose, expressive brushstrokes with paint drips and splashes. Washes of burnt sienna, raw umber, and deep indigo on rough textured dark paper. Hand-painted feel with visible paper grain. Like an original fine art piece in a gallery. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "isometric 3D diorama",
        "dalle_style": "vivid",
        "prompt": "Stylized isometric 3D diorama related to {topic}. Miniature world with tiny detailed objects on a floating platform. Dark slate base with warm spotlighting from above. Tilt-shift depth of field. Colors: deep forest green, burnished gold, and charcoal. Playful yet sophisticated, like a premium product render. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "torn paper collage",
        "dalle_style": "vivid",
        "prompt": "Torn paper collage with layered textures about {topic}. Ripped cardboard, kraft paper, and dark fabric textures overlapping. Stamped ink marks and hand-drawn pencil sketches visible. Earth tones: raw umber, deep ochre, slate gray. Handmade craft aesthetic, tactile and analog. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "abstract oil painting",
        "dalle_style": "vivid",
        "prompt": "Abstract oil painting with thick impasto texture evoking {topic}. Bold palette knife strokes creating ridges and valleys of paint. Colors: deep crimson, midnight blue, and metallic bronze on a near-black canvas. Museum-quality contemporary art. Richly textured surface catching dramatic side light. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "vintage flat-lay still life",
        "dalle_style": "natural",
        "prompt": "Overhead flat-lay arrangement on weathered dark wood surface relating metaphorically to {topic}. Vintage brass scientific instruments, aged leather-bound journals, antique maps, and dried botanical specimens. Warm candlelight atmosphere. Dutch Golden Age still life aesthetic. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "linocut print",
        "dalle_style": "vivid",
        "prompt": "Linocut style illustration about {topic}. Bold carved lines with visible wood grain texture. Limited to two ink colors: deep vermillion and dark teal on black paper. High contrast with strong graphic shapes. Folk art meets modernist design. Hand-carved imperfections visible. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "moody landscape metaphor",
        "dalle_style": "natural",
        "prompt": "Moody landscape photograph as visual metaphor for {topic}. Fog-covered ancient forest at dawn, or volcanic terrain with steam, or vast desert dunes. Single dominant warm accent against cool muted tones. Ultra-wide cinematic composition. National Geographic expedition photography quality. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "art deco poster",
        "dalle_style": "vivid",
        "prompt": "Geometric art deco abstract composition about {topic}. Sharp angular shapes, radiating sunburst patterns, and stepped forms. Rich jewel tones: deep emerald, sapphire blue, and antiqued gold on matte black. Roaring twenties luxury aesthetic. Ornamental borders with precision symmetry. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "japanese woodblock",
        "dalle_style": "vivid",
        "prompt": "Japanese woodblock print (ukiyo-e) inspired illustration of {topic}. Flowing organic lines, flat color areas, and subtle gradients. Colors: deep indigo, rust red, sage green, and warm cream on dark ground. Edo period aesthetic with contemporary subject matter. Delicate and refined. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "macro natural textures",
        "dalle_style": "natural",
        "prompt": "Macro photography of natural textures as metaphor for {topic}. Extreme close-up of crystalline formations, tree bark patterns, or geological strata. Deep earth tones with occasional iridescent highlights. Scientific precision meets artistic beauty. Dark moody lighting revealing intricate detail. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
    {
        "name": "blueprint technical drawing",
        "dalle_style": "vivid",
        "prompt": "Blueprint and technical drawing aesthetic about {topic}. White and copper-toned linework on deep navy background. Architectural plans, engineering schematics, geometric patterns. Compass roses and cross-sections. Vintage industrial draftsmanship meets modern data visualization. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS, NO ANNOTATIONS, NO MEASUREMENTS anywhere in the image. Pure visual linework only.",
    },
    {
        "name": "scandinavian dark minimalism",
        "dalle_style": "natural",
        "prompt": "Scandinavian dark minimalism: a single powerful symbolic object related to {topic} placed on a dark concrete surface. Dramatic chiaroscuro lighting from one side. Muted palette of charcoal, warm gray, and a single accent of burnt orange. Negative space dominates. Gallery photography aesthetic. Landscape 16:9. ABSOLUTELY NO TEXT, NO LETTERS, NO WORDS, NO WRITING, NO TYPOGRAPHY, NO SIGNAGE, NO LABELS anywhere in the image. Pure visual art only.",
    },
]

STYLE_HISTORY_FILE = ".style_history.json"
CUSTOM_IMAGES_DIR = "images"
CUSTOM_IMAGE_CHANCE_LINKEDIN = 0.67  # ~2 out of 3 for LinkedIn
CUSTOM_IMAGE_CHANCE_X = 0.33  # ~1 out of 3 for X
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
    linkedin_voice = OLI_PERSONAL_VOICE if is_personal else LISA_PERSONAL_VOICE
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
    li_image_prompt = li_style["prompt"].format(topic=selection["linkedin_topic"][:80])
    x_image_prompt = x_style["prompt"].format(topic=selection["x_topic"][:80])

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

        # Step 2: Upload the image binary
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
    # LinkedIn: alternate between Oli (odd days) and Lisa (even days)
    if post_linkedin:
        if is_business_day:
            token = LINKEDIN_ACCESS_TOKEN_LISA
            label = "Lisa"
        else:
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
                    post_to_x(content["x"], x_image_path,
                              api_key=X_BIZ_API_KEY, api_secret=X_BIZ_API_SECRET,
                              access_token=X_BIZ_ACCESS_TOKEN, access_secret=X_BIZ_ACCESS_SECRET)
                    log.info("Posted to X BUSINESS account")
                except Exception as e:
                    log.error(f"X business post failed: {e}")
        else:
            if not X_API_KEY or not X_ACCESS_TOKEN:
                log.warning("X API credentials not set, skipping X")
            else:
                try:
                    post_to_x(content["x"], x_image_path)
                    log.info("Posted to X PERSONAL account")
                except Exception as e:
                    log.error(f"X post failed: {e}")

    # Cleanup
    for path in [li_image_path, x_image_path]:
        if path and os.path.exists(path):
            os.remove(path)

    print("\nDone!")


if __name__ == "__main__":
    main()

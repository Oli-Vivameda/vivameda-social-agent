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
from style_guide import VIVAMEDA_VOICE, OLI_PERSONAL_VOICE
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
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    topic_list = "\n".join(f"- {t}" for t in topics)

    resp = client.messages.create(
        model=BLOG_MODEL,
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": TOPIC_SELECTOR_PROMPT.format(topics=topic_list),
        }],
    )
    text = resp.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1].replace("json", "", 1).strip()
    return json.loads(text)


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
- No hashtags in the body, add 3-5 relevant hashtags at the very end
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
- No hashtags unless they fit naturally
- No emojis
- Make people want to reply or retweet
- Do NOT mention Vivameda
- NEVER use em dashes or en dashes. Use commas, semicolons, colons, or periods instead.
"""

IMAGE_STYLES = [
    {
        "name": "laptop with data on screen",
        "dalle_style": "natural",
        "desc": "STYLE: Photorealistic photograph of a laptop or large monitor displaying data, charts, or a dashboard. The screen content should relate to the post topic (hiring trends, company data, market analysis). Shot at a slight angle with shallow depth of field. Bright, clean workspace with natural light. Think: a real photo you'd take at your desk to share on LinkedIn. NO dark rooms, NO neon.",
    },
    {
        "name": "printed report on table",
        "dalle_style": "natural",
        "desc": "STYLE: Photorealistic overhead photograph of a printed business report or data printout on a conference table. Visible charts, tables, and numbers on paper. Maybe a pen, a coffee cup, or glasses nearby. Natural office lighting from above. Think: someone just printed the quarterly analysis and laid it out. Clean, professional, real.",
    },
    {
        "name": "team at a screen",
        "dalle_style": "natural",
        "desc": "STYLE: Photorealistic photograph of 2-3 professionals (shot from behind or side, no clear faces) looking at a large screen or TV showing a chart, graph, or data dashboard. Bright modern office, glass walls, natural light. The screen content should loosely relate to the post topic. Think: a real meeting room photo. Documentary style.",
    },
    {
        "name": "city skyline editorial",
        "dalle_style": "natural",
        "desc": "STYLE: High-quality editorial photograph of a city skyline or financial district. Daytime or golden hour. Think: the kind of photo The Economist or Bloomberg would use as a header image. Sharp, clean, professional. Can include office buildings, a busy street, or a modern business campus. Natural colors, no filters.",
    },
    {
        "name": "clean data visualization",
        "dalle_style": "natural",
        "desc": "STYLE: A clean, professional chart or graph on a white or light background. Could be a bar chart, line chart, scatter plot, or heat map. The data should loosely relate to the post topic (workforce trends, hiring numbers, company growth). Think: a chart from a Financial Times article or a Bloomberg terminal screenshot. Muted professional colors. No 3D effects.",
    },
    {
        "name": "hands typing with data",
        "dalle_style": "natural",
        "desc": "STYLE: Close-up photorealistic photograph of hands on a keyboard or trackpad, with a screen in the background showing data, a spreadsheet, or an analytics tool. Shallow depth of field, warm natural light from the side. Think: a stock photo for TechCrunch or Wired, but more authentic. Clean desk, modern setup.",
    },
    {
        "name": "office hallway or lobby",
        "dalle_style": "natural",
        "desc": "STYLE: Photorealistic photograph of a modern corporate office hallway, lobby, or open-plan workspace. Light, airy, lots of glass and clean lines. Maybe a few people walking in the distance (blurred, no faces). Think: the kind of photo on a tech company About page. Architectural photography feel, natural light.",
    },
    {
        "name": "sticky notes and planning",
        "dalle_style": "natural",
        "desc": "STYLE: Photorealistic photograph of a planning session: sticky notes on a glass wall, a whiteboard with diagrams, or index cards arranged on a table. Colorful sticky notes with handwritten text (not readable). Bright office lighting. Think: a real startup strategy session. Authentic, messy, human.",
    },
]

IMAGE_PROMPT_GENERATOR = """Write a DALL-E image prompt for a social media post.

Post topic: {topic}
Visual style to follow: {style_desc}

RULES:
- Make the image RELEVANT to the post topic. The image should make sense alongside the post.
- Follow the visual style described above
- The image must look like a REAL PHOTOGRAPH, not AI art
- NO dark backgrounds, NO neon glow, NO purple, NO particle effects, NO sci-fi
- NO text, words, or logos in the image
- Landscape 16:9 aspect ratio
- Be specific: describe exact lighting, camera angle, what is on any visible screens

Respond with ONLY the image prompt. Max 120 words.
"""


def generate_content(selection: dict) -> dict:
    """Generate independent content for each platform."""
    # Personal voice on odd days, business voice on even days
    day_of_year = datetime.now().timetuple().tm_yday
    is_personal = (day_of_year % 2 != 0)
    active_voice = OLI_PERSONAL_VOICE if is_personal else VIVAMEDA_VOICE
    log.info(f"Using {'PERSONAL (Oli)' if is_personal else 'BUSINESS (Vivameda)'} voice")

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
                voice=active_voice,
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
                voice=active_voice,
            ),
        }],
    )
    x_post = x_resp.content[0].text.strip()

    # Strip any em/en dashes that slipped through
    x_post = x_post.replace("—", ",").replace("–", ",")

    # Generate image prompts, one per platform with different visual styles
    li_style, x_style = random.sample(IMAGE_STYLES, 2)
    log.info(f"Image styles: LinkedIn={li_style['name']}, X={x_style['name']}")
    li_img_resp = client.messages.create(
        model=BLOG_MODEL,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": IMAGE_PROMPT_GENERATOR.format(
                topic=selection["linkedin_topic"],
                style_desc=li_style["desc"],
            ),
        }],
    )
    x_img_resp = client.messages.create(
        model=BLOG_MODEL,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": IMAGE_PROMPT_GENERATOR.format(
                topic=selection["x_topic"],
                style_desc=x_style["desc"],
            ),
        }],
    )

    return {
        "linkedin": linkedin_post,
        "linkedin_topic": selection["linkedin_topic"],
        "linkedin_image_prompt": li_img_resp.content[0].text.strip(),
        "linkedin_dalle_style": li_style["dalle_style"],
        "x": x_post,
        "x_topic": selection["x_topic"],
        "x_image_prompt": x_img_resp.content[0].text.strip(),
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

    # Step 4: Generate images
    li_image_path = None
    x_image_path = None
    if HAS_IMAGE_GEN and not args.dry_run:
        if post_linkedin:
            log.info("Generating LinkedIn image...")
            try:
                li_image_path = generate_image(
                    content["linkedin_image_prompt"],
                    style=content.get("linkedin_dalle_style", "vivid"),
                )
                log.info(f"LinkedIn image saved: {li_image_path}")
            except Exception as e:
                log.warning(f"LinkedIn image failed: {e}")

        if post_x:
            log.info("Generating X image...")
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

    # Determine account: odd day = personal, even day = business
    day_of_year = datetime.now().timetuple().tm_yday
    is_business_day = (day_of_year % 2 == 0)
    account_label = "BUSINESS" if is_business_day else "PERSONAL"
    log.info(f"Day {day_of_year} of year, posting to {account_label} accounts")

    # Publish
    if post_linkedin:
        if is_business_day:
            token = LINKEDIN_BIZ_ACCESS_TOKEN
            if not token:
                log.warning("LINKEDIN_BIZ_ACCESS_TOKEN not set, skipping LinkedIn")
            else:
                try:
                    post_to_linkedin(content["linkedin"], token, li_image_path, company_id=LINKEDIN_COMPANY_ID)
                    log.info("Posted to LinkedIn COMPANY page")
                except Exception as e:
                    log.error(f"LinkedIn company post failed: {e}")
        else:
            if not LINKEDIN_ACCESS_TOKEN:
                log.warning("LINKEDIN_ACCESS_TOKEN not set, skipping LinkedIn")
            else:
                try:
                    post_to_linkedin(content["linkedin"], LINKEDIN_ACCESS_TOKEN, li_image_path)
                    log.info("Posted to LinkedIn PERSONAL profile")
                except Exception as e:
                    log.error(f"LinkedIn post failed: {e}")

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

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

LinkedIn audience: investment researchers, HR-tech leaders, data buyers, enterprise decision makers.
X audience: data people, startup founders, VCs, analysts, alternative data enthusiasts.

Trending topics:
{topics}

Respond in JSON:
{{
  "linkedin_topic": "...",
  "linkedin_angle": "2-3 sentences on the LinkedIn post angle (professional, insightful)",
  "x_topic": "...",
  "x_angle": "1 sentence on the X post angle (punchy, provocative)"
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
- Share a genuine insight about workforce data or business intelligence
- No hashtags in the body, add 3-5 relevant hashtags at the very end
- Conversational but professional tone
- End with a thought-provoking question or bold statement
- Do NOT be salesy or mention Vivameda's products directly
- Write as a thought leader sharing knowledge, not a company promoting itself
- Use line breaks between paragraphs for readability
- NEVER use em dashes or en dashes (— or –). Use commas, semicolons, colons, or periods instead.
"""

X_PROMPT = """Write a tweet (X post) for Vivameda (workforce intelligence company).

Topic: {topic}
Angle: {angle}

{voice}

RULES:
- 500-1000 characters. Develop the thought, give context, make it substantial.
- Provocative and opinionated
- One clear insight or hot take, backed with reasoning
- No hashtags unless they fit naturally
- No emojis
- Make people want to reply or retweet
- Do NOT mention Vivameda
- NEVER use em dashes or en dashes (— or –). Use commas, semicolons, colons, or periods instead.
"""

IMAGE_STYLES = [
    {
        "name": "photorealistic office",
        "dalle_style": "natural",
        "desc": "STYLE: Photorealistic photograph, like shot on a Canon EOS R5. A real, bright office environment with natural daylight coming through windows. Could be: a conference room with printed reports on the table, a laptop on a standing desk with a city view, hands typing on a keyboard with a bright screen, a whiteboard covered in real marker writing. WARM natural lighting. ABSOLUTELY NO dark backgrounds, NO glowing effects, NO neon colors, NO digital particles.",
    },
    {
        "name": "clean bar chart",
        "dalle_style": "natural",
        "desc": "STYLE: A simple, clean data visualization on a WHITE or very light background. Think: a professional bar chart or line graph like you'd see in the Wall Street Journal or Financial Times. Minimal design, thin lines, clear labels, muted professional colors (navy, gray, coral, teal). Flat 2D, no 3D effects. ABSOLUTELY NO dark backgrounds, NO glowing effects, NO neon, NO abstract digital art.",
    },
    {
        "name": "aerial city photograph",
        "dalle_style": "natural",
        "desc": "STYLE: Real aerial photograph of a major city during daytime. Golden hour or midday sun. Think: drone shot of Manhattan, London financial district, Singapore skyline, or a highway interchange from above. Sharp, high-resolution, photojournalistic quality. Colors should be natural and warm. ABSOLUTELY NO dark backgrounds, NO neon glow, NO digital overlay, NO abstract effects.",
    },
    {
        "name": "flat vector infographic",
        "dalle_style": "natural",
        "desc": "STYLE: Flat vector illustration in the style of a consulting firm report. Think: simple people icons, pie charts, arrow diagrams, percentage circles, all on a CLEAN WHITE background. Bold flat colors like orange, teal, navy, and yellow. NO gradients, NO shadows, NO 3D. Looks like it belongs in a McKinsey presentation. ABSOLUTELY NO dark backgrounds, NO glowing effects, NO sci-fi aesthetic.",
    },
    {
        "name": "cozy desk photograph",
        "dalle_style": "natural",
        "desc": "STYLE: Photorealistic overhead or angled shot of a real desk workspace. Think: a MacBook next to a coffee cup, a notebook with handwritten notes, printed spreadsheets with highlighter marks, a potted plant in the corner. Warm, soft, natural light from a window. Film photography feel, slightly warm color grading. ABSOLUTELY NO dark backgrounds, NO screens showing futuristic UI, NO glowing effects.",
    },
    {
        "name": "whiteboard sketch",
        "dalle_style": "natural",
        "desc": "STYLE: A real whiteboard or paper with hand-drawn diagrams. Think: black and blue marker on a white whiteboard showing flowcharts, boxes with arrows, rough graphs, sticky notes in different colors. Slightly messy, authentic, human. Shot as a photograph with natural office lighting. ABSOLUTELY NO digital art, NO dark backgrounds, NO neon, NO glowing lines.",
    },
    {
        "name": "nature landscape metaphor",
        "dalle_style": "natural",
        "desc": "STYLE: Breathtaking photorealistic nature photograph. Think: an aerial shot of a river delta branching out, tree rings in a cross-section of wood, a winding mountain road from above, waves crashing on geometric rock formations, a field of wheat at golden hour. National Geographic quality, stunning natural colors and light. ABSOLUTELY NO tech elements, NO screens, NO digital overlays, NO dark backgrounds.",
    },
    {
        "name": "retro newspaper",
        "dalle_style": "natural",
        "desc": "STYLE: Vintage newspaper or printed media aesthetic. Think: a 1960s newspaper front page with columns and headlines, an old stock ticker tape, a vintage printed chart on yellowed paper, a retro business magazine cover. Sepia tones, warm faded colors, visible paper texture and grain. ABSOLUTELY NO modern tech, NO screens, NO dark backgrounds, NO neon or glowing effects.",
    },
    {
        "name": "colorful geometric abstract",
        "dalle_style": "natural",
        "desc": "STYLE: Bold, bright geometric abstract art on a WHITE or very LIGHT background. Think: overlapping circles, triangles, and rectangles in primary colors. Inspired by Bauhaus, Mondrian, or modern corporate art. Simple, clean, striking. Two to four bold colors max. ABSOLUTELY NO dark backgrounds, NO purple glow, NO network nodes, NO particle effects, NO sci-fi look.",
    },
    {
        "name": "people at work photograph",
        "dalle_style": "natural",
        "desc": "STYLE: Photorealistic candid photograph of people in a work setting, shot from behind or from a distance so faces are not clearly visible. Think: a team standing around a whiteboard, someone pointing at a large screen showing a chart, two people walking through a bright modern office lobby, a group working at a long table in a sunlit room. Documentary photography style, natural colors. ABSOLUTELY NO dark backgrounds, NO futuristic elements, NO glowing effects.",
    },
]

IMAGE_PROMPT_GENERATOR = """Your job is to write a DALL-E image prompt. The visual style is MORE important than the topic.

VISUAL STYLE (this is the priority, follow it exactly): {style_desc}

The image should loosely relate to this subject: {topic}

CRITICAL RULES:
- The STYLE description above is the #1 priority. Follow it exactly.
- Do NOT default to dark backgrounds with glowing blue/purple effects. This is BANNED unless the style explicitly asks for it.
- Do NOT create abstract digital network visualizations. This is BANNED.
- Do NOT create sci-fi or futuristic looking images. This is BANNED.
- NO text, NO words, NO logos in the image
- Landscape 16:9 aspect ratio
- Be very specific about: exact colors, lighting direction, camera angle, materials, and textures

Respond with ONLY the image prompt, nothing else. Max 120 words.
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

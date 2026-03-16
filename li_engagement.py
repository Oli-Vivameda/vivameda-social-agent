#!/usr/bin/env python3
"""
Vivameda LinkedIn Engagement Agent
Runs 2x daily at 11:00 and 15:00 Cyprus time (peak LinkedIn hours)
Uses Oli's LinkedIn account ONLY (Lisa's account is protected)

Strategy:
  1. Search for recent posts via LinkedIn API using workforce/data keywords
  2. Score posts by relevance + author quality
  3. Like high-relevance posts (up to 15 per run)
  4. Comment on top-scored posts using Claude for intelligent, on-brand replies (up to 4 per run)
  5. Track engagement history to avoid double-engaging

LinkedIn API limits:
  - Rate limited but no published hard caps for organic actions
  - We stay conservative: 15 likes + 4 comments per run = safe zone
  - Never engage with the same post or author twice within 14 days
  - Comments are 3-5 sentences, Oli's voice, always include a Vivameda angle

Uses: LINKEDIN_ACCESS_TOKEN (Oli), ANTHROPIC_API_KEY (Claude for comments)
"""

import os
import json
import time
import random
import requests
from datetime import datetime, timedelta
from urllib.parse import quote

# ============================================================
# CONFIG
# ============================================================
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

VINNIE_PHONE = "4915129005414"
VINNIE_API_KEY = "5944134"

# Engagement limits per run (conservative)
MAX_LIKES = 15
MAX_COMMENTS = 4

# Don't re-engage same post/author within this many days
COOLDOWN_DAYS = 14

# History file
HISTORY_FILE = ".li_engagement_history.json"

# Search queries (picks 3 random per run)
SEARCH_QUERIES = [
    "workforce data analytics",
    "workforce intelligence",
    "alternative data hiring",
    "HR tech data",
    "talent analytics",
    "people analytics trends",
    "labor market data",
    "employee data insights",
    "hiring trends 2026",
    "recruitment data",
    "workforce planning data",
    "skills gap analysis",
    "headcount data",
    "org chart intelligence",
    "employee turnover data",
    "compensation benchmarking data",
    "job market analytics",
    "talent acquisition technology",
    "human capital analytics",
    "professional data providers",
]

# Bio keywords that indicate a relevant person
RELEVANT_BIO_KEYWORDS = [
    "data", "analytics", "intelligence", "research", "insights",
    "hr", "talent", "recruitment", "workforce", "people",
    "investor", "venture", "private equity", "fund",
    "strategy", "consulting", "advisor",
    "ceo", "cto", "cdo", "vp", "head of", "director",
    "founder", "co-founder",
]

log = print


def send_vinnie(message):
    try:
        url = f"https://api.callmebot.com/whatsapp.php?phone={VINNIE_PHONE}&text={quote(message)}&apikey={VINNIE_API_KEY}"
        resp = requests.get(url, timeout=15)
        log(f"Vinnie: {resp.status_code}")
    except Exception as e:
        log(f"Vinnie error: {e}")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"liked_posts": {}, "commented_posts": {}, "engaged_authors": {}}


def save_history(history):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        log(f"Error saving history: {e}")


def cleanup_history(history):
    """Remove entries older than COOLDOWN_DAYS."""
    cutoff = (datetime.now() - timedelta(days=COOLDOWN_DAYS)).isoformat()
    for key in ["liked_posts", "commented_posts", "engaged_authors"]:
        if key in history:
            history[key] = {k: v for k, v in history[key].items() if v > cutoff}
    return history


def linkedin_get(endpoint, params=None):
    """Make a GET request to LinkedIn API."""
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202401",
    }
    url = f"https://api.linkedin.com/v2/{endpoint}"
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            log(f"LinkedIn GET {endpoint}: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        log(f"LinkedIn GET error: {e}")
        return None


def linkedin_post(endpoint, data):
    """Make a POST request to LinkedIn API."""
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202401",
    }
    url = f"https://api.linkedin.com/v2/{endpoint}"
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code in (200, 201):
            return True
        else:
            log(f"LinkedIn POST {endpoint}: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        log(f"LinkedIn POST error: {e}")
        return False


def get_my_urn():
    """Get Oli's LinkedIn member URN."""
    data = linkedin_get("userinfo")
    if data and "sub" in data:
        return f"urn:li:person:{data['sub']}"
    # Fallback: try /me endpoint
    data = linkedin_get("me")
    if data and "id" in data:
        return f"urn:li:person:{data['id']}"
    return None


def search_posts(query):
    """
    Search for recent LinkedIn posts.
    Note: LinkedIn's content search API is limited. We use the posts API
    to find feed posts. If the search API isn't available with the token scope,
    we fall back to fetching the authenticated user's feed.
    """
    # Try content search first (requires r_organization_social or similar)
    params = {
        "q": "search",
        "query": query,
        "count": 20,
        "sortBy": "RELEVANCE",
    }
    data = linkedin_get("posts", params)
    if data and "elements" in data:
        return data["elements"]

    # Fallback: fetch feed posts (always works with r_liteprofile + w_member_social)
    # The feed naturally contains relevant content if Oli follows the right people
    data = linkedin_get("feed/updates", {"count": 50, "timeWindow": "LAST_24_HOURS"})
    if data and "elements" in data:
        return data["elements"]

    return []


def get_feed_posts():
    """
    Get posts from Oli's LinkedIn feed.
    Uses the UGC posts endpoint or feed endpoint.
    """
    posts = []

    # Try fetching feed
    data = linkedin_get("feed/updates", {"count": 50})
    if data and "elements" in data:
        for item in data["elements"]:
            post = extract_post_info(item)
            if post:
                posts.append(post)
        return posts

    # Alternative: try the shares endpoint for network shares
    data = linkedin_get("shares", {"count": 50, "q": "owners"})
    if data and "elements" in data:
        for item in data["elements"]:
            post = extract_post_info(item)
            if post:
                posts.append(post)

    return posts


def extract_post_info(raw):
    """Extract useful info from a LinkedIn API post object."""
    try:
        # Handle different response formats
        post_id = raw.get("id") or raw.get("activity") or raw.get("updateKey", "")
        author_urn = raw.get("author") or raw.get("actor", "")

        # Get text content
        text = ""
        if "specificContent" in raw:
            share = raw["specificContent"].get("com.linkedin.ugc.ShareContent", {})
            text = share.get("shareCommentary", {}).get("text", "")
        elif "commentary" in raw:
            text = raw.get("commentary", "")
        elif "text" in raw:
            text = raw.get("text", {}).get("text", "") if isinstance(raw.get("text"), dict) else str(raw.get("text", ""))

        if not text or len(text) < 30:
            return None

        # Get engagement metrics
        likes = raw.get("numLikes", 0) or raw.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numLikes", 0)
        comments = raw.get("numComments", 0) or raw.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numComments", 0)

        return {
            "id": str(post_id),
            "author_urn": str(author_urn),
            "text": text[:500],
            "likes": likes,
            "comments": comments,
            "raw": raw,
        }
    except Exception as e:
        log(f"Error extracting post: {e}")
        return None


def score_post(post, query_terms):
    """Score a post for engagement relevance (0-100)."""
    score = 0
    text_lower = post["text"].lower()

    # Keyword relevance
    for term in query_terms:
        for word in term.lower().split():
            if word in text_lower:
                score += 8

    # Workforce/data specific terms
    high_value_terms = [
        "workforce", "hiring data", "talent data", "people analytics",
        "alternative data", "labor market", "headcount", "employee data",
        "HR tech", "recruitment data", "compensation data",
    ]
    for term in high_value_terms:
        if term.lower() in text_lower:
            score += 12

    # Engagement sweet spot (not too viral, not dead)
    likes = post.get("likes", 0)
    if 5 <= likes <= 200:
        score += 15
    elif likes > 200:
        score += 5  # Big posts = less visibility for our comment

    # Post length (thoughtful posts are better to engage with)
    if len(post["text"]) > 150:
        score += 10

    # Cap at 100
    return min(score, 100)


def generate_comment(post_text):
    """Use Claude to generate an on-brand comment in Oli's voice."""
    if not ANTHROPIC_API_KEY:
        log("No Anthropic API key, skipping comment generation")
        return None

    prompt = f"""You are writing a LinkedIn comment as Oli Nold, founder of Vivameda, a workforce intelligence company.

VOICE RULES:
- Direct, raw, experience-driven, occasionally contrarian
- Reads like texting a sharp friend
- NO corporate jargon, NO opening compliments like "Great post!" or "Love this!"
- 3-5 sentences max
- NO em dashes (use commas instead)
- Include a subtle "Vivameda flip" connecting the topic to workforce data insights when natural
- Don't force it if the connection isn't natural
- NO hashtags in comments
- Sound like a real person, not a bot

POST TO COMMENT ON:
{post_text[:800]}

Write ONE comment. Just the comment text, nothing else."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            comment = data["content"][0]["text"].strip()
            # Safety: strip em dashes
            comment = comment.replace("\u2014", ",").replace("\u2013", ",").replace("--", ",")
            # Safety: remove quotes that might wrap the whole comment
            if comment.startswith('"') and comment.endswith('"'):
                comment = comment[1:-1]
            return comment
        else:
            log(f"Claude API error: {resp.status_code}")
            return None
    except Exception as e:
        log(f"Claude error: {e}")
        return None


def like_post(post_urn, actor_urn):
    """Like a LinkedIn post."""
    data = {
        "actor": actor_urn,
        "object": post_urn,
    }
    # Use the socialActions endpoint
    return linkedin_post("socialActions/{post_urn}/likes", {"actor": actor_urn})


def comment_on_post(post_urn, actor_urn, comment_text):
    """Comment on a LinkedIn post."""
    data = {
        "actor": actor_urn,
        "message": {
            "text": comment_text,
        },
    }
    return linkedin_post(f"socialActions/{post_urn}/comments", data)


def main():
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    log(f"LinkedIn Engagement Agent starting: {today}")

    if not LINKEDIN_ACCESS_TOKEN:
        log("ERROR: No LinkedIn access token")
        send_vinnie("LI ENGAGEMENT: No LinkedIn token. Agent cannot run.")
        return

    # Get Oli's URN
    log("\nGetting member URN...")
    my_urn = get_my_urn()
    if not my_urn:
        log("ERROR: Could not get member URN. Token may be expired.")
        send_vinnie("LI ENGAGEMENT: Token error, could not get member URN. Check token.")
        return
    log(f"  URN: {my_urn}")

    # Load and clean history
    history = load_history()
    history = cleanup_history(history)

    # Pick random queries
    queries = random.sample(SEARCH_QUERIES, min(3, len(SEARCH_QUERIES)))
    log(f"\nSearch queries: {queries}")

    # Collect posts from feed
    log("\nFetching feed posts...")
    all_posts = get_feed_posts()
    log(f"  Found {len(all_posts)} posts in feed")

    if not all_posts:
        log("No posts found. Feed may be empty or API scope insufficient.")
        log("The agent needs at minimum: r_liteprofile and w_member_social scopes.")
        send_vinnie("LI ENGAGEMENT: No posts found in feed. Check API scopes.")
        return

    # Filter out already-engaged posts and own posts
    eligible = []
    for post in all_posts:
        post_id = post["id"]
        author = post["author_urn"]

        # Skip own posts
        if my_urn in str(author):
            continue

        # Skip already liked
        if post_id in history.get("liked_posts", {}):
            continue

        # Skip recently engaged authors
        if author in history.get("engaged_authors", {}) and \
           history["engaged_authors"][author] > (datetime.now() - timedelta(days=COOLDOWN_DAYS)).isoformat():
            continue

        # Score the post
        post["score"] = score_post(post, queries)
        if post["score"] >= 20:
            eligible.append(post)

    log(f"\nEligible posts after filtering: {len(eligible)}")

    if not eligible:
        log("No eligible posts to engage with.")
        return

    # Sort by score
    eligible.sort(key=lambda x: x["score"], reverse=True)

    # LIKES
    liked = 0
    log(f"\nLiking posts (max {MAX_LIKES})...")
    for post in eligible[:MAX_LIKES]:
        post_urn = post["id"]
        log(f"  Liking: {post['text'][:60]}... (score {post['score']})")

        success = like_post(post_urn, my_urn)
        if success:
            liked += 1
            history.setdefault("liked_posts", {})[post_urn] = datetime.now().isoformat()
            history.setdefault("engaged_authors", {})[post["author_urn"]] = datetime.now().isoformat()
        else:
            log(f"    Like failed for {post_urn}")

        # Throttle: 2-5 seconds between actions
        time.sleep(random.uniform(2, 5))

    # COMMENTS (top scored posts only)
    commented = 0
    log(f"\nCommenting on top posts (max {MAX_COMMENTS})...")
    comment_candidates = [p for p in eligible if p["score"] >= 40 and p["id"] not in history.get("commented_posts", {})]

    for post in comment_candidates[:MAX_COMMENTS]:
        post_urn = post["id"]
        log(f"  Generating comment for: {post['text'][:60]}...")

        comment_text = generate_comment(post["text"])
        if not comment_text:
            log("    Comment generation failed, skipping")
            continue

        log(f"    Comment: {comment_text[:80]}...")
        success = comment_on_post(post_urn, my_urn, comment_text)
        if success:
            commented += 1
            history.setdefault("commented_posts", {})[post_urn] = datetime.now().isoformat()
            history.setdefault("engaged_authors", {})[post["author_urn"]] = datetime.now().isoformat()
        else:
            log(f"    Comment failed for {post_urn}")

        # Longer throttle for comments: 10-20 seconds
        time.sleep(random.uniform(10, 20))

    # Save history
    save_history(history)

    # Git commit history file
    log("\nCommitting engagement history...")
    os.system(f'git config user.email "bot@vivameda.com"')
    os.system(f'git config user.name "Vivameda Bot"')
    os.system(f'git add {HISTORY_FILE}')
    os.system(f'git diff --cached --quiet || git commit -m "LinkedIn engagement: {liked} likes, {commented} comments"')
    os.system(f'git push || true')

    # Vinnie summary
    personality = random.choice([
        f"LinkedIn hustle done. {liked} likes, {commented} comments. Oli's out there networking while sleeping.",
        f"Dropped {liked} likes and {commented} thoughtful comments on LinkedIn. The algo rewards consistency.",
        f"LI engagement complete: {liked} likes, {commented} comments. Building the brand one interaction at a time.",
    ])
    send_vinnie(personality)

    log(f"\nDone! Liked: {liked}, Commented: {commented}")


if __name__ == "__main__":
    main()

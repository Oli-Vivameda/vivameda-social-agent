#!/usr/bin/env python3
"""
X (Twitter) Engagement Agent
Searches for relevant posts, likes them, and leaves thoughtful replies.
Runs multiple times per day via GitHub Actions.
"""

import os
import sys
import json
import logging
import hashlib
import hmac
import time
import base64
import urllib.parse
import uuid
import random
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

try:
    import anthropic
    import httpx
except ImportError:
    log.error("Missing dependencies. Run: pip install anthropic httpx")
    sys.exit(1)

from config import (
    ANTHROPIC_API_KEY,
    BLOG_MODEL,
    X_API_KEY,
    X_API_SECRET,
    X_ACCESS_TOKEN,
    X_ACCESS_SECRET,
)

# ---------------------------------------------------------------------------
# Search queries to find relevant conversations
# ---------------------------------------------------------------------------
ENGAGEMENT_SEARCHES = [
    "workforce data",
    "workforce intelligence",
    "alternative data investing",
    "headcount growth signal",
    "people analytics",
    "talent intelligence",
    "HR tech data",
    "workforce analytics",
    "labor market data",
    "employee data trends",
    "hiring velocity",
    "company headcount",
]

# How many tweets to engage with per run
LIKES_PER_RUN = 8
REPLIES_PER_RUN = 3

# Minimum followers for accounts we engage with (avoid bots/spam)
MIN_FOLLOWERS = 100


# ---------------------------------------------------------------------------
# OAuth 1.0a helpers
# ---------------------------------------------------------------------------
def _oauth_header(method: str, url: str, extra_params: dict = None) -> str:
    """Build OAuth 1.0a Authorization header."""
    oauth_params = {
        "oauth_consumer_key": X_API_KEY,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": X_ACCESS_TOKEN,
        "oauth_version": "1.0",
    }

    all_params = {**oauth_params}
    if extra_params:
        all_params.update(extra_params)

    params_string = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    base_string = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(params_string, safe='')}"
    signing_key = f"{urllib.parse.quote(X_API_SECRET, safe='')}&{urllib.parse.quote(X_ACCESS_SECRET, safe='')}"
    signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    oauth_params["oauth_signature"] = base64.b64encode(signature).decode()

    return "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )


def _get_my_user_id() -> str:
    """Get authenticated user's ID."""
    url = "https://api.x.com/2/users/me"
    resp = httpx.get(url, headers={"Authorization": _oauth_header("GET", url)})
    resp.raise_for_status()
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# Search for relevant tweets
# ---------------------------------------------------------------------------
def search_relevant_tweets(query: str, max_results: int = 10) -> list[dict]:
    """Search recent tweets matching a query."""
    url = "https://api.x.com/2/tweets/search/recent"
    params = {
        "query": f"{query} -is:retweet -is:reply lang:en",
        "max_results": min(max_results, 10),
        "tweet.fields": "author_id,created_at,public_metrics,text",
        "expansions": "author_id",
        "user.fields": "public_metrics,username,name",
    }

    auth = _oauth_header("GET", url, params)
    resp = httpx.get(url, params=params, headers={"Authorization": auth})

    if resp.status_code == 429:
        log.warning("Rate limited on search — backing off")
        return []

    resp.raise_for_status()
    data = resp.json()

    tweets = data.get("data", [])
    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

    results = []
    for tweet in tweets:
        author = users.get(tweet["author_id"], {})
        followers = author.get("public_metrics", {}).get("followers_count", 0)

        if followers < MIN_FOLLOWERS:
            continue

        results.append({
            "id": tweet["id"],
            "text": tweet["text"],
            "author_id": tweet["author_id"],
            "author_username": author.get("username", "unknown"),
            "author_name": author.get("name", "Unknown"),
            "followers": followers,
            "likes": tweet.get("public_metrics", {}).get("like_count", 0),
            "retweets": tweet.get("public_metrics", {}).get("retweet_count", 0),
        })

    return results


# ---------------------------------------------------------------------------
# Like a tweet
# ---------------------------------------------------------------------------
def like_tweet(tweet_id: str, my_user_id: str) -> bool:
    """Like a tweet."""
    url = f"https://api.x.com/2/users/{my_user_id}/likes"
    auth = _oauth_header("POST", url)

    resp = httpx.post(
        url,
        json={"tweet_id": tweet_id},
        headers={"Authorization": auth, "Content-Type": "application/json"},
    )

    if resp.status_code == 429:
        log.warning("Rate limited on likes — stopping")
        return False
    if resp.status_code == 200:
        return True

    log.warning(f"Like failed ({resp.status_code}): {resp.text[:100]}")
    return False


# ---------------------------------------------------------------------------
# Generate and post a reply
# ---------------------------------------------------------------------------
REPLY_PROMPT = """You are engaging on X (Twitter) as a workforce data expert.

Someone posted this tweet:
"{tweet_text}"
— @{author_username} ({author_name}, {followers} followers)

Write a thoughtful reply that:
- Adds genuine value or a new perspective
- Shows expertise in workforce data, business intelligence, or alternative data
- Feels natural and conversational (NOT promotional)
- Maximum 200 characters
- No hashtags, no emojis
- Do NOT mention Vivameda or any company
- Do NOT be sycophantic ("Great post!", "Love this!")
- Start with a substantive point, not a compliment

Respond with ONLY the reply text, nothing else.
"""


def generate_reply(tweet: dict) -> str:
    """Use Claude to generate a contextual reply."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    resp = client.messages.create(
        model=BLOG_MODEL,
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": REPLY_PROMPT.format(
                tweet_text=tweet["text"][:500],
                author_username=tweet["author_username"],
                author_name=tweet["author_name"],
                followers=tweet["followers"],
            ),
        }],
    )
    reply = resp.content[0].text.strip().strip('"')

    if len(reply) > 280:
        reply = reply[:277] + "..."

    return reply


def post_reply(tweet_id: str, text: str) -> bool:
    """Post a reply to a tweet."""
    url = "https://api.x.com/2/tweets"
    auth = _oauth_header("POST", url)

    resp = httpx.post(
        url,
        json={
            "text": text,
            "reply": {"in_reply_to_tweet_id": tweet_id},
        },
        headers={"Authorization": auth, "Content-Type": "application/json"},
    )

    if resp.status_code == 429:
        log.warning("Rate limited on replies — stopping")
        return False
    if resp.status_code in (200, 201):
        return True

    log.warning(f"Reply failed ({resp.status_code}): {resp.text[:100]}")
    return False


# ---------------------------------------------------------------------------
# Engagement scoring — prioritize high-value tweets
# ---------------------------------------------------------------------------
def score_tweet(tweet: dict) -> float:
    """Score a tweet for engagement priority."""
    score = 0.0

    # More followers = more visibility for our reply
    if tweet["followers"] > 10000:
        score += 3
    elif tweet["followers"] > 1000:
        score += 2
    else:
        score += 1

    # Some engagement but not viral (we can still add value)
    likes = tweet["likes"]
    if 5 <= likes <= 100:
        score += 2
    elif likes < 5:
        score += 1

    # Longer tweets tend to be more substantive
    if len(tweet["text"]) > 150:
        score += 1

    return score


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="X Engagement Agent")
    parser.add_argument("--dry-run", action="store_true", help="Preview without engaging")
    parser.add_argument("--likes-only", action="store_true", help="Only like, don't reply")
    parser.add_argument("--max-likes", type=int, default=LIKES_PER_RUN, help="Max likes per run")
    parser.add_argument("--max-replies", type=int, default=REPLIES_PER_RUN, help="Max replies per run")
    args = parser.parse_args()

    if not X_API_KEY or not X_ACCESS_TOKEN:
        log.error("X API credentials not configured")
        sys.exit(1)

    # Get my user ID
    my_user_id = _get_my_user_id()
    log.info(f"Authenticated as user: {my_user_id}")

    # Pick 2-3 random search queries per run for variety
    queries = random.sample(ENGAGEMENT_SEARCHES, min(3, len(ENGAGEMENT_SEARCHES)))

    # Collect candidate tweets
    all_tweets = []
    seen_ids = set()

    for query in queries:
        log.info(f"Searching: {query}")
        tweets = search_relevant_tweets(query, max_results=10)
        for t in tweets:
            if t["id"] not in seen_ids:
                seen_ids.add(t["id"])
                all_tweets.append(t)

        # Respect rate limits
        time.sleep(2)

    log.info(f"Found {len(all_tweets)} candidate tweets")

    if not all_tweets:
        log.info("No relevant tweets found — done")
        return

    # Score and sort
    all_tweets.sort(key=score_tweet, reverse=True)

    # --- LIKES ---
    liked = 0
    for tweet in all_tweets:
        if liked >= args.max_likes:
            break

        if args.dry_run:
            log.info(f"[DRY RUN] Would like: @{tweet['author_username']}: {tweet['text'][:80]}...")
            liked += 1
            continue

        if like_tweet(tweet["id"], my_user_id):
            log.info(f"Liked: @{tweet['author_username']}: {tweet['text'][:60]}...")
            liked += 1
            # Random delay between actions (3-8 seconds)
            time.sleep(random.uniform(3, 8))
        else:
            break  # Rate limited, stop

    log.info(f"Liked {liked} tweets")

    # --- REPLIES ---
    if args.likes_only:
        log.info("Likes only mode — skipping replies")
        return

    replied = 0
    # Only reply to top-scored tweets
    reply_candidates = all_tweets[:args.max_replies * 2]

    for tweet in reply_candidates:
        if replied >= args.max_replies:
            break

        log.info(f"Generating reply for @{tweet['author_username']}...")
        reply_text = generate_reply(tweet)

        if args.dry_run:
            log.info(f"[DRY RUN] Would reply to @{tweet['author_username']}:")
            log.info(f"  Original: {tweet['text'][:80]}...")
            log.info(f"  Reply: {reply_text}")
            replied += 1
            continue

        if post_reply(tweet["id"], reply_text):
            log.info(f"Replied to @{tweet['author_username']}: {reply_text[:60]}...")
            replied += 1
            # Longer delay between replies (15-30 seconds)
            time.sleep(random.uniform(15, 30))
        else:
            break  # Rate limited, stop

    log.info(f"Replied to {replied} tweets")
    print(f"\nDone! Liked: {liked}, Replied: {replied}")


if __name__ == "__main__":
    main()

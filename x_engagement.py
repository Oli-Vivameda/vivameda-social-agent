#!/usr/bin/env python3
"""
X (Twitter) Engagement Agent
Searches for relevant posts, likes, replies, follows relevant accounts,
unfollows non-followers, and curates timeline.
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
from datetime import datetime

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
    X_BIZ_API_KEY,
    X_BIZ_API_SECRET,
    X_BIZ_ACCESS_TOKEN,
    X_BIZ_ACCESS_SECRET,
)

# Active credentials (swapped between personal and business)
_active_api_key = X_API_KEY
_active_api_secret = X_API_SECRET
_active_access_token = X_ACCESS_TOKEN
_active_access_secret = X_ACCESS_SECRET
_active_account = "personal"


def _set_account(account: str):
    """Switch between personal and business X credentials."""
    global _active_api_key, _active_api_secret, _active_access_token, _active_access_secret, _active_account
    if account == "business":
        _active_api_key = X_BIZ_API_KEY
        _active_api_secret = X_BIZ_API_SECRET
        _active_access_token = X_BIZ_ACCESS_TOKEN
        _active_access_secret = X_BIZ_ACCESS_SECRET
    else:
        _active_api_key = X_API_KEY
        _active_api_secret = X_API_SECRET
        _active_access_token = X_ACCESS_TOKEN
        _active_access_secret = X_ACCESS_SECRET
    _active_account = account

# ---------------------------------------------------------------------------
# WhatsApp alert via Vinnie
# ---------------------------------------------------------------------------
_vinnie_alerted = set()

def _vinnie_alert(msg: str):
    """Send a WhatsApp alert via CallMeBot. Only sends each message once per run."""
    if msg in _vinnie_alerted:
        return
    _vinnie_alerted.add(msg)
    try:
        httpx.get(f"https://api.callmebot.com/whatsapp.php?phone=4915129005414&text={msg}&apikey=5944134", timeout=10)
        log.info("Vinnie alert sent")
    except Exception:
        log.warning("Failed to send Vinnie alert")

def _flag_credits_empty():
    """Mark that credits ran out."""
    if not os.path.exists(CREDIT_EMPTY_FLAG):
        with open(CREDIT_EMPTY_FLAG, "w") as f:
            f.write(datetime.now().isoformat())

def _check_credits_recovered():
    """If credits were empty last run but work now, Vinnie reports the recharge."""
    if os.path.exists(CREDIT_EMPTY_FLAG):
        try:
            with open(CREDIT_EMPTY_FLAG) as f:
                empty_since = f.read().strip()
            os.remove(CREDIT_EMPTY_FLAG)
            _vinnie_alert(f"Vinnie+here.+X+API+credits+recharged.+Was+empty+since+{empty_since[:16].replace(':', '%3A')}.+Back+in+business+boss.")
            log.info("Credits recovered, flag cleared")
        except Exception:
            pass

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
    "skills gap data",
    "talent acquisition data",
    "organizational restructuring",
    "hiring freeze layoffs data",
    "workforce planning AI",
    "business intelligence B2B data",
    "alternative data hedge fund",
    "human capital analytics",
]

# Per-run limits
LIKES_PER_RUN = 10
REPLIES_PER_RUN = 3
FOLLOWS_PER_RUN = 5
UNFOLLOWS_PER_RUN = 5

# Quality filters
MIN_FOLLOWERS = 100
MIN_FOLLOWERS_TO_FOLLOW = 500

# Files for tracking
FOLLOW_HISTORY_FILE = ".follow_history.json"
CREDIT_EMPTY_FLAG = ".credits_empty"

def _init_file_paths():
    """Set file paths based on active account."""
    global FOLLOW_HISTORY_FILE, CREDIT_EMPTY_FLAG
    if _active_account == "business":
        FOLLOW_HISTORY_FILE = ".follow_history_biz.json"
        CREDIT_EMPTY_FLAG = ".credits_empty_biz"


# ---------------------------------------------------------------------------
# OAuth 1.0a helpers
# ---------------------------------------------------------------------------
def _oauth_header(method: str, url: str, extra_params: dict = None) -> str:
    """Build OAuth 1.0a Authorization header."""
    oauth_params = {
        "oauth_consumer_key": _active_api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": _active_access_token,
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
    signing_key = f"{urllib.parse.quote(_active_api_secret, safe='')}&{urllib.parse.quote(_active_access_secret, safe='')}"
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
# Follow history management
# ---------------------------------------------------------------------------
def load_follow_history() -> dict:
    """Load follow tracking data."""
    if os.path.exists(FOLLOW_HISTORY_FILE):
        try:
            with open(FOLLOW_HISTORY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"followed": {}, "unfollowed": [], "last_unfollow_check": ""}


def save_follow_history(data: dict):
    """Save follow tracking data."""
    try:
        with open(FOLLOW_HISTORY_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        log.warning(f"Could not save follow history: {e}")


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
        "user.fields": "public_metrics,username,name,description",
    }

    auth = _oauth_header("GET", url, params)
    resp = httpx.get(url, params=params, headers={"Authorization": auth})

    if resp.status_code == 429:
        log.warning("Rate limited on search, backing off")
        return []

    if resp.status_code == 402:
        log.warning("X API payment required, search quota may be exceeded")
        _vinnie_alert("Vinnie+here.+X+API+credits+just+ran+out.+Auto-recharge+should+kick+in+but+check+developer.x.com+to+be+sure.")
        _flag_credits_empty()
        return []

    if resp.status_code >= 400:
        log.warning(f"Search failed ({resp.status_code}): {resp.text[:100]}")
        return []

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
            "author_bio": author.get("description", ""),
            "followers": followers,
            "following": author.get("public_metrics", {}).get("following_count", 0),
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
        log.warning("Rate limited on likes, stopping")
        return False
    if resp.status_code == 402:
        _vinnie_alert("Vinnie+here.+X+API+credits+ran+out+while+liking.+Check+developer.x.com.")
        _flag_credits_empty()
        return False
    if resp.status_code == 200:
        return True

    log.warning(f"Like failed ({resp.status_code}): {resp.text[:100]}")
    return False


# ---------------------------------------------------------------------------
# Follow a user
# ---------------------------------------------------------------------------
def follow_user(user_id: str, my_user_id: str) -> bool:
    """Follow a user."""
    url = f"https://api.x.com/2/users/{my_user_id}/following"
    auth = _oauth_header("POST", url)

    resp = httpx.post(
        url,
        json={"target_user_id": user_id},
        headers={"Authorization": auth, "Content-Type": "application/json"},
    )

    if resp.status_code == 429:
        log.warning("Rate limited on follows, stopping")
        return False
    if resp.status_code == 402:
        _vinnie_alert("Vinnie+here.+X+API+credits+ran+out+while+following.+Check+developer.x.com.")
        _flag_credits_empty()
        return False
    if resp.status_code == 200:
        return True

    log.warning(f"Follow failed ({resp.status_code}): {resp.text[:100]}")
    return False


# ---------------------------------------------------------------------------
# Unfollow a user
# ---------------------------------------------------------------------------
def unfollow_user(user_id: str, my_user_id: str) -> bool:
    """Unfollow a user."""
    url = f"https://api.x.com/2/users/{my_user_id}/following/{user_id}"
    auth = _oauth_header("DELETE", url)

    resp = httpx.delete(
        url,
        headers={"Authorization": auth},
    )

    if resp.status_code == 429:
        log.warning("Rate limited on unfollows, stopping")
        return False
    if resp.status_code == 200:
        return True

    log.warning(f"Unfollow failed ({resp.status_code}): {resp.text[:100]}")
    return False


# ---------------------------------------------------------------------------
# Get following list (people I follow)
# ---------------------------------------------------------------------------
def get_my_following(my_user_id: str, max_results: int = 100) -> list[dict]:
    """Get list of users I follow."""
    url = f"https://api.x.com/2/users/{my_user_id}/following"
    params = {
        "max_results": min(max_results, 1000),
        "user.fields": "public_metrics,username,name,description,created_at",
    }
    auth = _oauth_header("GET", url, params)
    resp = httpx.get(url, params=params, headers={"Authorization": auth})

    if resp.status_code == 429:
        log.warning("Rate limited on following list")
        return []

    resp.raise_for_status()
    return resp.json().get("data", [])


# ---------------------------------------------------------------------------
# Get followers (people who follow me)
# ---------------------------------------------------------------------------
def get_my_followers(my_user_id: str, max_results: int = 100) -> list[dict]:
    """Get list of my followers."""
    url = f"https://api.x.com/2/users/{my_user_id}/followers"
    params = {
        "max_results": min(max_results, 1000),
        "user.fields": "public_metrics,username,name",
    }
    auth = _oauth_header("GET", url, params)
    resp = httpx.get(url, params=params, headers={"Authorization": auth})

    if resp.status_code == 429:
        log.warning("Rate limited on followers list")
        return []

    resp.raise_for_status()
    return resp.json().get("data", [])


# ---------------------------------------------------------------------------
# Generate and post a reply
# ---------------------------------------------------------------------------
REPLY_PROMPT_PERSONAL = """You are engaging on X (Twitter) as a workforce data expert.

Someone posted this tweet:
"{tweet_text}"
-- @{author_username} ({author_name}, {followers} followers)

Write a thoughtful reply that:
- Adds genuine value or a new perspective
- Shows expertise in workforce data, business intelligence, or alternative data
- Feels natural and conversational (NOT promotional)
- Maximum 280 characters
- No hashtags, no emojis
- Do NOT mention Vivameda or any company
- Do NOT be sycophantic ("Great post!", "Love this!")
- Start with a substantive point, not a compliment
- NEVER use em dashes or en dashes

Respond with ONLY the reply text, nothing else.
"""

REPLY_PROMPT_BUSINESS = """You are engaging on X (Twitter) as Vivameda, a workforce intelligence company.

Someone posted this tweet:
"{tweet_text}"
-- @{author_username} ({author_name}, {followers} followers)

Write a thoughtful reply that:
- Adds genuine value from a workforce data perspective
- Shows Vivameda's expertise in tracking workforce movements at scale
- Feels authoritative but conversational
- Maximum 280 characters
- No hashtags, no emojis
- You CAN mention Vivameda naturally if it fits, but don't force it
- Do NOT be sycophantic ("Great post!", "Love this!")
- Start with a substantive point, not a compliment
- NEVER use em dashes or en dashes

Respond with ONLY the reply text, nothing else.
"""


def generate_reply(tweet: dict) -> str:
    """Use Claude to generate a contextual reply."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = REPLY_PROMPT_BUSINESS if _active_account == "business" else REPLY_PROMPT_PERSONAL

    resp = client.messages.create(
        model=BLOG_MODEL,
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": prompt.format(
                tweet_text=tweet["text"][:500],
                author_username=tweet["author_username"],
                author_name=tweet["author_name"],
                followers=tweet["followers"],
            ),
        }],
    )
    reply = resp.content[0].text.strip().strip('"')
    reply = reply.replace("\u2014", ",").replace("\u2013", ",")

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
        log.warning("Rate limited on replies, stopping")
        return False
    if resp.status_code == 402:
        _vinnie_alert("Vinnie+here.+X+API+credits+ran+out+while+replying.+Check+developer.x.com.")
        _flag_credits_empty()
        return False
    if resp.status_code in (200, 201):
        return True

    log.warning(f"Reply failed ({resp.status_code}): {resp.text[:100]}")
    return False


# ---------------------------------------------------------------------------
# Engagement scoring
# ---------------------------------------------------------------------------
def score_tweet(tweet: dict) -> float:
    """Score a tweet for engagement priority."""
    score = 0.0

    if tweet["followers"] > 10000:
        score += 3
    elif tweet["followers"] > 1000:
        score += 2
    else:
        score += 1

    likes = tweet["likes"]
    if 5 <= likes <= 100:
        score += 2
    elif likes < 5:
        score += 1

    if len(tweet["text"]) > 150:
        score += 1

    return score


def is_relevant_account(user: dict) -> bool:
    """Check if a user's bio suggests they're in our target audience."""
    bio = (user.get("description") or user.get("author_bio") or "").lower()
    keywords = [
        "data", "analytics", "intelligence", "workforce", "hiring",
        "talent", "hr tech", "investment", "venture", "startup",
        "founder", "ceo", "cto", "research", "alternative data",
        "fintech", "saas", "b2b", "machine learning", "ai ",
        "hedge fund", "private equity", "recruiting", "headcount",
        "people ops", "chief", "director", "vp ", "head of",
    ]
    return any(kw in bio for kw in keywords)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="X Engagement Agent")
    parser.add_argument("--dry-run", action="store_true", help="Preview without engaging")
    parser.add_argument("--likes-only", action="store_true", help="Only like, don't reply or follow")
    parser.add_argument("--no-follow", action="store_true", help="Skip follow/unfollow")
    parser.add_argument("--account", choices=["personal", "business"], default="personal", help="Which X account to use")
    args = parser.parse_args()

    # Switch to the right account
    _set_account(args.account)
    _init_file_paths()
    log.info(f"Running as {args.account} account")

    if not _active_api_key or not _active_access_token:
        log.error("X API credentials not configured")
        sys.exit(1)

    my_user_id = _get_my_user_id()
    log.info(f"Authenticated as user: {my_user_id}")

    # Load follow history
    history = load_follow_history()

    # Pick 4 random search queries per run for variety
    queries = random.sample(ENGAGEMENT_SEARCHES, min(4, len(ENGAGEMENT_SEARCHES)))

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
        time.sleep(2)

    log.info(f"Found {len(all_tweets)} candidate tweets")

    # If we found tweets, searches worked. Check if credits were previously empty.
    if all_tweets:
        _check_credits_recovered()

    if not all_tweets:
        log.info("No relevant tweets found, done")
        return

    # Score and sort
    all_tweets.sort(key=score_tweet, reverse=True)

    # ═══════════════════════════════════════════
    # LIKES
    # ═══════════════════════════════════════════
    liked = 0
    for tweet in all_tweets:
        if liked >= LIKES_PER_RUN:
            break

        if args.dry_run:
            log.info(f"[DRY] Would like: @{tweet['author_username']}: {tweet['text'][:80]}...")
            liked += 1
            continue

        if like_tweet(tweet["id"], my_user_id):
            log.info(f"Liked: @{tweet['author_username']}: {tweet['text'][:60]}...")
            liked += 1
            time.sleep(random.uniform(2, 5))
        else:
            break

    log.info(f"Liked {liked} tweets")

    # ═══════════════════════════════════════════
    # REPLIES
    # ═══════════════════════════════════════════
    if not args.likes_only:
        replied = 0
        reply_candidates = all_tweets[:REPLIES_PER_RUN * 2]

        for tweet in reply_candidates:
            if replied >= REPLIES_PER_RUN:
                break

            log.info(f"Generating reply for @{tweet['author_username']}...")
            reply_text = generate_reply(tweet)

            if args.dry_run:
                log.info(f"[DRY] Would reply to @{tweet['author_username']}: {reply_text}")
                replied += 1
                continue

            if post_reply(tweet["id"], reply_text):
                log.info(f"Replied to @{tweet['author_username']}: {reply_text[:60]}...")
                replied += 1
                time.sleep(random.uniform(10, 25))
            else:
                break

        log.info(f"Replied to {replied} tweets")

    # ═══════════════════════════════════════════
    # FOLLOW relevant accounts from search results
    # ═══════════════════════════════════════════
    if not args.likes_only and not args.no_follow:
        followed = 0
        already_followed = set(history.get("followed", {}).keys())

        # Find relevant accounts from today's search that we don't follow yet
        follow_candidates = []
        for tweet in all_tweets:
            uid = tweet["author_id"]
            if uid in already_followed or uid == my_user_id:
                continue
            if tweet["followers"] < MIN_FOLLOWERS_TO_FOLLOW:
                continue
            if is_relevant_account(tweet):
                follow_candidates.append(tweet)

        # Deduplicate by author
        seen_authors = set()
        unique_candidates = []
        for t in follow_candidates:
            if t["author_id"] not in seen_authors:
                seen_authors.add(t["author_id"])
                unique_candidates.append(t)

        random.shuffle(unique_candidates)

        for tweet in unique_candidates[:FOLLOWS_PER_RUN]:
            if followed >= FOLLOWS_PER_RUN:
                break

            if args.dry_run:
                log.info(f"[DRY] Would follow: @{tweet['author_username']} ({tweet['followers']} followers)")
                followed += 1
                continue

            if follow_user(tweet["author_id"], my_user_id):
                log.info(f"Followed: @{tweet['author_username']} ({tweet['followers']} followers)")
                history["followed"][tweet["author_id"]] = {
                    "username": tweet["author_username"],
                    "date": datetime.now().isoformat(),
                    "followers": tweet["followers"],
                }
                followed += 1
                time.sleep(random.uniform(5, 15))
            else:
                break

        log.info(f"Followed {followed} new accounts")

        # ═══════════════════════════════════════════
        # UNFOLLOW non-followers (once per day, first run only)
        # ═══════════════════════════════════════════
        today = datetime.now().strftime("%Y-%m-%d")
        if history.get("last_unfollow_check") != today:
            log.info("Running daily unfollow check...")
            history["last_unfollow_check"] = today

            try:
                following_list = get_my_following(my_user_id, max_results=200)
                time.sleep(2)
                followers_list = get_my_followers(my_user_id, max_results=200)

                follower_ids = {u["id"] for u in followers_list}
                following_ids = {u["id"]: u for u in following_list}

                # Find accounts we follow that don't follow back
                # Only unfollow if we followed them > 3 days ago
                unfollow_candidates = []
                for uid, user in following_ids.items():
                    if uid in follower_ids:
                        continue  # They follow back, keep
                    if uid == my_user_id:
                        continue

                    # Check if we followed recently (give them time to follow back)
                    follow_record = history.get("followed", {}).get(uid, {})
                    follow_date = follow_record.get("date", "2020-01-01")
                    try:
                        days_since = (datetime.now() - datetime.fromisoformat(follow_date)).days
                    except Exception:
                        days_since = 999

                    if days_since < 3:
                        continue  # Too soon, give them time

                    # Don't unfollow high-value accounts (they're worth following regardless)
                    followers = user.get("public_metrics", {}).get("followers_count", 0)
                    if followers > 50000:
                        continue  # Keep following big accounts

                    unfollow_candidates.append({
                        "id": uid,
                        "username": user.get("username", "unknown"),
                        "followers": followers,
                    })

                random.shuffle(unfollow_candidates)
                unfollowed = 0

                for candidate in unfollow_candidates[:UNFOLLOWS_PER_RUN]:
                    if args.dry_run:
                        log.info(f"[DRY] Would unfollow: @{candidate['username']} (doesn't follow back)")
                        unfollowed += 1
                        continue

                    if unfollow_user(candidate["id"], my_user_id):
                        log.info(f"Unfollowed: @{candidate['username']} (doesn't follow back)")
                        history.get("followed", {}).pop(candidate["id"], None)
                        unfollowed += 1
                        time.sleep(random.uniform(5, 12))
                    else:
                        break

                log.info(f"Unfollowed {unfollowed} non-followers")

            except Exception as e:
                log.warning(f"Unfollow check failed: {e}")

    # Save follow history
    save_follow_history(history)

    log.info("Done!")


if __name__ == "__main__":
    main()

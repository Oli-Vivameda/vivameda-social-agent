#!/usr/bin/env python3
"""
Vivameda LinkedIn Engagement Agent (Brave Search approach)
Uses Brave Search to find LinkedIn posts, then w_member_social to like/comment.
No r_member_social scope needed.
"""

import os
import json
import time
import random
import re
import requests
from datetime import datetime, timedelta
from urllib.parse import quote

LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")

VINNIE_PHONE = "4915129005414"
VINNIE_API_KEY = "5944134"

MAX_LIKES = 15
MAX_COMMENTS = 4
COOLDOWN_DAYS = 14
HISTORY_FILE = ".li_engagement_history.json"

SEARCH_QUERIES = [
    "site:linkedin.com/posts workforce data analytics",
    "site:linkedin.com/posts workforce intelligence hiring",
    "site:linkedin.com/posts alternative data HR",
    "site:linkedin.com/posts talent analytics trends",
    "site:linkedin.com/posts people analytics workforce",
    "site:linkedin.com/posts labor market data insights",
    "site:linkedin.com/posts hiring trends data",
    "site:linkedin.com/posts employee data workforce planning",
    "site:linkedin.com/posts recruitment data technology",
    "site:linkedin.com/posts skills gap workforce",
    "site:linkedin.com/posts headcount data analytics",
    "site:linkedin.com/posts compensation benchmarking data",
    "site:linkedin.com/posts HR tech data driven",
    "site:linkedin.com/posts talent acquisition data",
    "site:linkedin.com/posts org design workforce",
    "site:linkedin.com/posts future of work data",
    "site:linkedin.com/posts workforce automation AI",
    "site:linkedin.com/posts professional data intelligence",
    "site:linkedin.com/posts remote work data trends",
    "site:linkedin.com/posts gig economy workforce data",
]

log = print


def send_vinnie(message):
    try:
        url = f"https://api.callmebot.com/whatsapp.php?phone={VINNIE_PHONE}&text={quote(message)}&apikey={VINNIE_API_KEY}"
        requests.get(url, timeout=15)
    except Exception as e:
        log(f"Vinnie error: {e}")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"liked_posts": {}, "commented_posts": {}, "engaged_urls": {}}


def save_history(history):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        log(f"Error saving history: {e}")


def cleanup_history(history):
    cutoff = (datetime.now() - timedelta(days=COOLDOWN_DAYS)).isoformat()
    for key in ["liked_posts", "commented_posts", "engaged_urls"]:
        if key in history:
            history[key] = {k: v for k, v in history[key].items() if v > cutoff}
    return history


def get_my_urn():
    try:
        resp = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"},
            timeout=15,
        )
        if resp.status_code == 200:
            sub = resp.json().get("sub", "")
            if sub:
                return f"urn:li:person:{sub}"
    except Exception as e:
        log(f"URN error: {e}")
    return None


def brave_search(query, count=20):
    if not BRAVE_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": count, "freshness": "pw"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("web", {}).get("results", [])
        log(f"Brave error: {resp.status_code}")
        return []
    except Exception as e:
        log(f"Brave error: {e}")
        return []


def extract_post_urn_from_url(url):
    match = re.search(r'activity[:-](\d{19,20})', url)
    if match:
        return f"urn:li:activity:{match.group(1)}"
    match = re.search(r'ugcPost[:-](\d{19,20})', url)
    if match:
        return f"urn:li:ugcPost:{match.group(1)}"
    return None


def extract_author_from_url(url):
    match = re.search(r'linkedin\.com/posts/([^_/]+)', url)
    return match.group(1) if match else None


def score_post(title, description, url):
    score = 0
    text = f"{title} {description}".lower()
    for term in ["workforce data", "workforce intelligence", "hiring data", "talent data",
                  "people analytics", "alternative data", "labor market", "headcount",
                  "employee data", "hr tech", "recruitment data", "compensation data",
                  "workforce planning", "skills gap", "talent analytics"]:
        if term in text:
            score += 15
    for term in ["data", "analytics", "workforce", "hiring", "talent", "recruitment",
                  "hr", "human resources", "automation", "ai", "machine learning", "insights", "trends"]:
        if term in text:
            score += 5
    if "/posts/" in url:
        score += 10
    elif "/feed/update/" in url:
        score += 10
    if "/pulse/" in url:
        score -= 20
    if "/company/" in url and "/posts/" not in url:
        score -= 15
    return min(max(score, 0), 100)


def like_post(activity_urn, actor_urn):
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    url = f"https://api.linkedin.com/v2/socialActions/{activity_urn}/likes"
    data = {"actor": actor_urn, "object": activity_urn}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code in (200, 201, 409):
            return True
        react_url = "https://api.linkedin.com/v2/reactions"
        react_data = {"root": activity_urn, "reactionType": "LIKE", "actor": actor_urn}
        resp2 = requests.post(react_url, headers=headers, json=react_data, timeout=15)
        if resp2.status_code in (200, 201, 409):
            return True
        log(f"    Like failed: {resp.status_code} / {resp2.status_code}")
        return False
    except Exception as e:
        log(f"    Like error: {e}")
        return False


def comment_on_post(activity_urn, actor_urn, comment_text):
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    url = f"https://api.linkedin.com/v2/socialActions/{activity_urn}/comments"
    data = {"actor": actor_urn, "message": {"text": comment_text}}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code in (200, 201):
            return True
        log(f"    Comment failed: {resp.status_code} - {resp.text[:200]}")
        return False
    except Exception as e:
        log(f"    Comment error: {e}")
        return False


def generate_comment(post_title, post_description):
    if not ANTHROPIC_API_KEY:
        return None
    context = f"{post_title}\n{post_description}"
    prompt = f"""You are writing a LinkedIn comment as Oli Nold, founder of Vivameda, a workforce intelligence company that tracks professional records across millions of data points.

VOICE RULES:
- Direct, raw, experience-driven, occasionally contrarian
- Reads like texting a sharp friend
- NO corporate jargon, NO opening compliments like "Great post!" or "Love this!" or "Great insight!"
- 3-5 sentences max
- NO em dashes (use commas instead)
- Include a subtle "Vivameda flip" connecting the topic to workforce data insights when natural, but don't force it
- NO hashtags in comments
- Sound like a real person having a conversation, not a bot or a marketer
- Add genuine value or a different perspective

POST CONTEXT (title + snippet):
{context[:800]}

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
            comment = resp.json()["content"][0]["text"].strip()
            comment = comment.replace("\u2014", ",").replace("\u2013", ",").replace("--", ",")
            if comment.startswith('"') and comment.endswith('"'):
                comment = comment[1:-1]
            return comment
        log(f"Claude error: {resp.status_code}")
        return None
    except Exception as e:
        log(f"Claude error: {e}")
        return None


def main():
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    log(f"LinkedIn Engagement Agent (Brave Search) starting: {today}")

    if not LINKEDIN_ACCESS_TOKEN:
        send_vinnie("LI ENGAGEMENT: No LinkedIn token.")
        return
    if not BRAVE_API_KEY:
        send_vinnie("LI ENGAGEMENT: No Brave API key.")
        return

    log("\nGetting member URN...")
    my_urn = get_my_urn()
    if not my_urn:
        send_vinnie("LI ENGAGEMENT: Token error, could not get member URN.")
        return
    log(f"  URN: {my_urn}")

    history = load_history()
    history = cleanup_history(history)

    queries = random.sample(SEARCH_QUERIES, min(3, len(SEARCH_QUERIES)))
    log(f"\nSearching with {len(queries)} queries...")

    all_results = []
    for query in queries:
        results = brave_search(query, count=15)
        short_q = query.replace("site:linkedin.com/posts ", "")
        log(f"  '{short_q}': {len(results)} results")
        all_results.extend(results)
        time.sleep(1)

    if not all_results:
        send_vinnie("LI ENGAGEMENT: Brave returned no results.")
        return

    seen_urns = set()
    posts = []
    for result in all_results:
        url = result.get("url", "")
        title = result.get("title", "")
        description = result.get("description", "")
        if "linkedin.com" not in url:
            continue
        urn = extract_post_urn_from_url(url)
        if not urn or urn in seen_urns:
            continue
        seen_urns.add(urn)
        if urn in history.get("liked_posts", {}):
            continue
        if url in history.get("engaged_urls", {}):
            continue
        author = extract_author_from_url(url)
        if author and author.lower() in ("olinold", "oli-nold", "olivernold"):
            continue
        score = score_post(title, description, url)
        if score < 20:
            continue
        posts.append({"urn": urn, "url": url, "title": title,
                       "description": description, "author": author or "unknown", "score": score})

    posts.sort(key=lambda x: x["score"], reverse=True)
    log(f"\nEligible posts: {len(posts)}")

    if not posts:
        send_vinnie("LI ENGAGEMENT: No posts with extractable activity URNs. Next run will try different queries.")
        return

    liked = 0
    like_fails = 0
    log(f"\nLiking (max {MAX_LIKES})...")
    for post in posts[:MAX_LIKES + 5]:
        if liked >= MAX_LIKES:
            break
        log(f"  {post['author']}: {post['title'][:50]}... (score {post['score']})")
        if like_post(post["urn"], my_urn):
            liked += 1
            history.setdefault("liked_posts", {})[post["urn"]] = datetime.now().isoformat()
            history.setdefault("engaged_urls", {})[post["url"]] = datetime.now().isoformat()
        else:
            like_fails += 1
            if like_fails >= 5:
                log("  Too many failures, stopping.")
                break
        time.sleep(random.uniform(3, 6))

    commented = 0
    comment_fails = 0
    log(f"\nCommenting (max {MAX_COMMENTS})...")
    candidates = [p for p in posts if p["score"] >= 40 and p["urn"] not in history.get("commented_posts", {})]
    for post in candidates[:MAX_COMMENTS + 2]:
        if commented >= MAX_COMMENTS:
            break
        log(f"  Commenting on: {post['title'][:50]}...")
        text = generate_comment(post["title"], post["description"])
        if not text:
            continue
        log(f"    -> {text[:80]}...")
        if comment_on_post(post["urn"], my_urn, text):
            commented += 1
            history.setdefault("commented_posts", {})[post["urn"]] = datetime.now().isoformat()
            history.setdefault("engaged_urls", {})[post["url"]] = datetime.now().isoformat()
        else:
            comment_fails += 1
            if comment_fails >= 3:
                break
        time.sleep(random.uniform(10, 20))

    save_history(history)

    log("\nCommitting history...")
    os.system('git config user.email "bot@vivameda.com"')
    os.system('git config user.name "Vivameda Bot"')
    os.system(f'git add {HISTORY_FILE}')
    os.system('git diff --cached --quiet || git commit -m "LinkedIn engagement: {} likes, {} comments"'.format(liked, commented))
    os.system('git push || true')

    msg = random.choice([
        f"LinkedIn hustle done. {liked} likes, {commented} comments via Brave Search.",
        f"LI engagement: {liked} likes, {commented} comments. Workforce data crowd engaged.",
        f"Dropped {liked} likes and {commented} comments on LinkedIn. Consistency compounds.",
    ])
    if like_fails >= 5:
        msg += " (Some likes failed, may need scope check.)"
    send_vinnie(msg)
    log(f"\nDone! Liked: {liked}, Commented: {commented}")


if __name__ == "__main__":
    main()

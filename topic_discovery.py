"""Discover trending topics via Brave Search API."""
import logging
import random
import json
import os
from datetime import datetime
import httpx
from config import BRAVE_API_KEY

log = logging.getLogger(__name__)

# Large pool of search queries, rotated daily
SEARCH_QUERIES = [
    "workforce intelligence trends",
    "alternative data investment",
    "labor market analysis",
    "HR tech workforce data",
    "AI workforce analytics",
    "hiring trends 2026",
    "layoff data analysis",
    "talent acquisition technology",
    "employee turnover data",
    "workforce planning AI",
    "skills gap data",
    "remote work trends data",
    "headcount growth tech companies",
    "HR analytics market",
    "people analytics trends",
    "organizational restructuring news",
    "job market data insights",
    "recruitment technology funding",
    "business intelligence workforce",
    "company hiring freeze data",
    "alternative data hedge fund",
    "workforce composition trends",
    "talent intelligence platform",
    "human capital analytics",
    "gig economy workforce data",
    "AI replacing jobs data",
    "salary benchmarking data",
    "diversity hiring data trends",
    "workforce mobility data",
    "enterprise data strategy",
]

STATIC_TOPICS = [
    "Why headcount data is the most underused signal in investment research",
    "Skills-based hiring is rewriting how we measure workforce health",
    "The gap between what companies report and what workforce data reveals",
    "How AI is changing the demand for workforce intelligence at scale",
    "Why historical workforce data matters more than real-time snapshots",
    "The rise of alternative data in private equity due diligence",
    "What hiring velocity tells you that revenue growth cannot",
    "Workforce composition as a leading indicator of company strategy",
    "Remote work reshaped org charts forever and most companies still haven't adapted",
    "The talent war nobody talks about: mid-level technical roles",
    "Why 90% of workforce analytics projects fail before they start",
    "Company culture isn't what the CEO says, it's what the org chart shows",
    "Data infrastructure is the real moat, not AI models",
    "The death of the annual workforce plan",
    "What 250 million professional records teach you about economic cycles",
]

TOPIC_HISTORY_FILE = ".topic_history.json"


def load_topic_history() -> list[str]:
    """Load previously used topics to avoid repeats."""
    if os.path.exists(TOPIC_HISTORY_FILE):
        try:
            with open(TOPIC_HISTORY_FILE, "r") as f:
                data = json.load(f)
                return data.get("topics", [])[-60:]  # Keep last 60
        except Exception:
            pass
    return []


def save_topic_history(topics: list[str]):
    """Save used topics."""
    existing = load_topic_history()
    existing.extend(topics)
    existing = existing[-60:]  # Keep last 60
    with open(TOPIC_HISTORY_FILE, "w") as f:
        json.dump({"topics": existing, "updated": datetime.now().isoformat()}, f)


def discover_topics() -> list[str]:
    """Return a list of trending topic strings."""
    if not BRAVE_API_KEY:
        log.warning("No Brave API key, using static topic rotation")
        return random.sample(STATIC_TOPICS, min(5, len(STATIC_TOPICS)))

    # Pick 4 random queries from the pool each day for variety
    daily_queries = random.sample(SEARCH_QUERIES, min(4, len(SEARCH_QUERIES)))
    log.info(f"Search queries today: {daily_queries}")

    topics = []
    history = load_topic_history()

    for query in daily_queries:
        try:
            resp = httpx.get(
                "https://api.search.brave.com/res/v1/news/search",
                params={"q": query, "count": 5, "freshness": "pd"},  # past day, not past week
                headers={"X-Subscription-Token": BRAVE_API_KEY},
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            for r in results:
                title = r.get("title", "").strip()
                desc = r.get("description", "").strip()
                if title and len(title) > 20:
                    # Add description for more context
                    topic = f"{title}. {desc[:150]}" if desc else title
                    # Skip if too similar to recent topics
                    if not any(title[:40].lower() in h.lower() for h in history):
                        topics.append(topic)
        except Exception as e:
            log.warning(f"Brave Search failed for '{query}': {e}")

    if len(topics) < 3:
        # Fallback: try past week if past day is thin
        log.info("Few daily results, expanding to past week...")
        extra_queries = random.sample(SEARCH_QUERIES, min(3, len(SEARCH_QUERIES)))
        for query in extra_queries:
            try:
                resp = httpx.get(
                    "https://api.search.brave.com/res/v1/news/search",
                    params={"q": query, "count": 5, "freshness": "pw"},
                    headers={"X-Subscription-Token": BRAVE_API_KEY},
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                for r in results:
                    title = r.get("title", "").strip()
                    desc = r.get("description", "").strip()
                    if title and len(title) > 20:
                        topic = f"{title}. {desc[:150]}" if desc else title
                        if not any(title[:40].lower() in h.lower() for h in history):
                            topics.append(topic)
            except Exception:
                pass

    if len(topics) < 3:
        log.warning("Low search results, mixing in static topics")
        unused_static = [t for t in STATIC_TOPICS if t not in history]
        if unused_static:
            topics.extend(random.sample(unused_static, min(3, len(unused_static))))

    if topics:
        log.info(f"Total topics found: {len(topics)}")
    else:
        log.warning("No topics found, using static fallback")
        topics = random.sample(STATIC_TOPICS, min(5, len(STATIC_TOPICS)))

    return topics

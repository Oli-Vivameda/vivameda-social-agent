"""Discover trending topics via Brave Search API."""
import logging
import httpx
from config import BRAVE_API_KEY

log = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "workforce intelligence trends",
    "alternative data investment",
    "labor market analysis",
    "HR tech workforce data",
    "AI workforce analytics",
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
]


def discover_topics() -> list[str]:
    """Return a list of trending topic strings."""
    if not BRAVE_API_KEY:
        log.warning("No Brave API key — using static topic rotation")
        import random
        return random.sample(STATIC_TOPICS, min(5, len(STATIC_TOPICS)))

    topics = []
    for query in SEARCH_QUERIES[:3]:  # Limit API calls
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
                if title and len(title) > 20:
                    topics.append(title)
        except Exception as e:
            log.warning(f"Brave Search failed for '{query}': {e}")

    if topics:
        log.info(f"Brave Search returned {len(topics)} topics")
    else:
        log.warning("No search results — falling back to static topics")
        import random
        topics = random.sample(STATIC_TOPICS, min(5, len(STATIC_TOPICS)))

    return topics

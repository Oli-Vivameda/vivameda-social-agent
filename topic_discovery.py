"""Discover trending topics via Brave Search API.

PHILOSOPHY: Cast the widest possible net for topics, but every post must
flip back to Vivameda's core: workforce intelligence, professional data
at scale, and the infrastructure behind it. The connection can be direct
("hiring data shows X") or creative ("this trend in quantum computing
will reshape how we think about talent pipelines"). The agent's job is
to find the news. Claude's job is to find the Vivameda angle.
"""
import logging
import random
import json
import os
import httpx
from config import BRAVE_API_KEY

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 120+ search queries. 4 random ones picked per run.
# At 4/day, 5 days/week, this pool takes 6+ weeks to cycle through.
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    # ═══════════════════════════════════════════
    # INVESTMENT & ALTERNATIVE DATA (20%)
    # ═══════════════════════════════════════════
    "alternative data hedge fund",
    "venture capital deal flow data",
    "private equity due diligence technology",
    "quant fund data strategy",
    "investment research data tools",
    "alpha generation alternative data",
    "M&A market intelligence",
    "portfolio analytics trends",
    "ESG data investing",
    "corporate earnings signal data",
    "credit risk data analytics",
    "real estate investment data",
    "commodity trading data intelligence",
    "sentiment analysis financial markets",
    "startup valuation data trends",
    "IPO market data analysis",
    "sovereign wealth fund strategy",
    "family office investment technology",
    "distressed debt data signals",
    "activist investor data strategy",

    # ═══════════════════════════════════════════
    # AI & MACHINE LEARNING (20%)
    # ═══════════════════════════════════════════
    "machine learning training data market",
    "AI model performance benchmarks",
    "foundation model competition news",
    "enterprise AI adoption metrics",
    "synthetic data generation business",
    "AI infrastructure cloud spending",
    "large language model enterprise",
    "computer vision industry applications",
    "reinforcement learning business",
    "AI regulation policy news",
    "open source AI business impact",
    "AI agent autonomous business",
    "edge AI deployment trends",
    "AI chip semiconductor race",
    "generative AI revenue models",
    "multimodal AI applications",
    "AI safety alignment research",
    "vector database embeddings market",
    "AI copilot enterprise productivity",
    "neural network architecture breakthroughs",

    # ═══════════════════════════════════════════
    # DATA INDUSTRY & INFRASTRUCTURE (20%)
    # ═══════════════════════════════════════════
    "data marketplace business model",
    "data monetization strategy",
    "data as a service trends",
    "data broker regulation news",
    "data quality enterprise market",
    "data governance compliance",
    "data mesh data fabric trends",
    "cloud data warehouse competition",
    "real time data processing",
    "data pipeline automation",
    "data privacy regulation business impact",
    "data licensing revenue model",
    "web scraping data legal",
    "geospatial data business",
    "satellite imagery data analytics",
    "IoT sensor data market",
    "graph database knowledge graph",
    "data catalog discovery tools",
    "master data management trends",
    "data observability platform growth",

    # ═══════════════════════════════════════════
    # CORPORATE STRATEGY & COMPETITIVE INTEL (20%)
    # ═══════════════════════════════════════════
    "competitive intelligence technology",
    "market intelligence platform",
    "corporate strategy data driven",
    "business intelligence trends",
    "decision intelligence analytics",
    "predictive analytics enterprise",
    "supply chain intelligence data",
    "pricing intelligence tools",
    "customer analytics trends",
    "digital transformation metrics",
    "industry benchmarking data",
    "company growth signals data",
    "organizational restructuring news",
    "tech company strategic pivot",
    "corporate innovation metrics",
    "strategic workforce planning",
    "SaaS metrics benchmarks",
    "B2B sales intelligence tools",
    "revenue operations data",
    "product led growth metrics",

    # ═══════════════════════════════════════════
    # NEWS OF THE DAY / BIG STORIES (20%)
    # ═══════════════════════════════════════════
    "technology news today",
    "startup funding news today",
    "big tech earnings results",
    "fintech news today",
    "venture capital news today",
    "cybersecurity breach news",
    "climate tech funding news",
    "semiconductor industry news",
    "biotech pharma deal news",
    "space industry business news",
    "autonomous vehicles industry",
    "quantum computing business",
    "robotics automation industry",
    "crypto blockchain institutional",
    "energy transition business",
    "defense tech industry news",
    "healthcare technology news",
    "retail technology disruption",
    "logistics supply chain technology",
    "global trade policy business impact",
]

TOPIC_HISTORY_FILE = ".topic_history.json"
TOPIC_HISTORY_SIZE = 90  # Remember last 90 topics (longer memory)


def load_topic_history() -> list[str]:
    if os.path.exists(TOPIC_HISTORY_FILE):
        try:
            with open(TOPIC_HISTORY_FILE) as f:
                return json.load(f).get("topics", [])
        except Exception:
            pass
    return []


def save_topic_history(new_topics: list[str]):
    history = load_topic_history()
    history.extend(new_topics)
    history = history[-TOPIC_HISTORY_SIZE:]
    try:
        with open(TOPIC_HISTORY_FILE, "w") as f:
            json.dump({"topics": history}, f)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Static fallback pool (20 diverse evergreen topics)
# ---------------------------------------------------------------------------
STATIC_TOPICS = [
    "Why headcount data is the most underused signal in investment research",
    "Skills-based hiring is rewriting how we measure workforce health",
    "The gap between what companies report and what workforce data reveals",
    "How AI is changing the demand for workforce intelligence at scale",
    "Why historical workforce data matters more than real-time snapshots",
    "The rise of alternative data in private equity due diligence",
    "What hiring velocity tells you that revenue growth cannot",
    "Workforce composition as a leading indicator of company strategy",
    "The four day work week experiment: what the data actually shows",
    "Why most HR dashboards are useless for strategic decisions",
    "How the gig economy is redefining what workforce means",
    "The talent density myth: why small teams outperform large ones",
    "Job title inflation is making workforce data harder to trust",
    "What 15 years of professional data reveals about career velocity",
    "The hidden cost of bad workforce data in M&A due diligence",
    "Data infrastructure is eating the world and nobody is tracking the talent building it",
    "The real reason big data projects fail has nothing to do with technology",
    "How semiconductor workforce shortages are reshaping geopolitics",
    "Why the best investment signal is not in earnings calls but in hiring patterns",
    "The death of the generalist: what skills data tells us about specialization",
]


def discover_topics() -> list[str]:
    """Return a list of trending topic strings."""
    if not BRAVE_API_KEY:
        log.warning("No Brave API key, using static topic rotation")
        return random.sample(STATIC_TOPICS, min(5, len(STATIC_TOPICS)))

    # Pick 4 random queries from the massive pool
    queries = random.sample(SEARCH_QUERIES, min(4, len(SEARCH_QUERIES)))
    log.info(f"Search queries today: {[q[:50] for q in queries]}")

    # Load history to avoid repeats
    history = load_topic_history()

    topics = []
    for query in queries:
        # Try past day first
        for freshness in ["pd", "pw"]:
            try:
                resp = httpx.get(
                    "https://api.search.brave.com/res/v1/news/search",
                    params={"q": query, "count": 5, "freshness": freshness},
                    headers={"X-Subscription-Token": BRAVE_API_KEY},
                    timeout=15,
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                found_any = False
                for r in results:
                    title = r.get("title", "").strip()
                    if title and len(title) > 20:
                        title_lower = title.lower()
                        # Skip if too similar to recent history
                        if not any(
                            t.lower() in title_lower or title_lower in t.lower()
                            for t in history[-30:]
                        ):
                            topics.append(title)
                            found_any = True
                if found_any:
                    break  # Got results for past day, skip past week
            except Exception as e:
                log.warning(f"Brave Search failed for '{query}' ({freshness}): {e}")

    if topics:
        log.info(f"Brave Search returned {len(topics)} topics")
    else:
        log.warning("No search results, falling back to static topics")
        available = [t for t in STATIC_TOPICS if t not in history[-20:]]
        if not available:
            available = STATIC_TOPICS
        topics = random.sample(available, min(5, len(available)))

    return topics

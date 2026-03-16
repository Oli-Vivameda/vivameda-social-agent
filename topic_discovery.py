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
    # WORKFORCE & TALENT (the obvious ones)
    # ═══════════════════════════════════════════
    "workforce intelligence trends",
    "talent acquisition technology news",
    "employee retention data",
    "remote work workforce trends",
    "skills gap crisis",
    "workforce planning AI tools",
    "global talent migration",
    "gig economy growth data",
    "diversity hiring statistics",
    "executive turnover C-suite",
    "employer branding trends",
    "internal mobility data",
    "talent marketplace platform",
    "workforce reskilling programs",
    "contingent workforce trends",
    "people analytics ROI",
    "employee experience data",
    "organizational design trends",
    "succession planning data",
    "compensation benchmarking trends",

    # ═══════════════════════════════════════════
    # AI & MACHINE LEARNING
    # ═══════════════════════════════════════════
    "artificial intelligence hiring impact",
    "generative AI workforce disruption",
    "AI replacing white collar jobs",
    "machine learning enterprise adoption",
    "large language model business use",
    "AI startup funding round",
    "AI regulation policy news",
    "AI ethics workforce",
    "autonomous agents business",
    "AI copilot productivity data",
    "computer vision industry applications",
    "natural language processing business",
    "AI infrastructure spending",
    "foundation model competition",
    "open source AI models business impact",
    "AI hallucination enterprise risk",
    "synthetic data market growth",

    # ═══════════════════════════════════════════
    # BIG DATA & DATA INFRASTRUCTURE
    # ═══════════════════════════════════════════
    "big data market trends",
    "data infrastructure spending",
    "data pipeline engineering trends",
    "data lake data warehouse trends",
    "Snowflake Databricks competition",
    "real-time data processing trends",
    "data mesh architecture adoption",
    "data governance enterprise",
    "data quality market growth",
    "master data management trends",
    "data observability platform",
    "ETL ELT market trends",
    "vector database market growth",
    "graph database business applications",
    "data monetization strategies",
    "data marketplace business model",
    "data broker industry regulation",
    "zero party first party data",
    "data privacy regulation impact business",
    "GDPR CCPA enforcement news",

    # ═══════════════════════════════════════════
    # BUSINESS INTELLIGENCE & ANALYTICS
    # ═══════════════════════════════════════════
    "business intelligence market trends",
    "embedded analytics growth",
    "self-service analytics adoption",
    "predictive analytics enterprise",
    "decision intelligence trends",
    "augmented analytics AI",
    "data visualization market",
    "real-time dashboards business",
    "competitive intelligence tools",
    "market intelligence platform",

    # ═══════════════════════════════════════════
    # B2B, SAAS & STARTUP
    # ═══════════════════════════════════════════
    "B2B data market news",
    "SaaS growth metrics trends",
    "startup funding news today",
    "venture capital trends",
    "B2B sales technology trends",
    "product-led growth data",
    "vertical SaaS market growth",
    "API economy business trends",
    "developer tools market",
    "no-code low-code enterprise",
    "cloud infrastructure spending",
    "SaaS consolidation acquisitions",

    # ═══════════════════════════════════════════
    # PRIVATE EQUITY, M&A & INVESTING
    # ═══════════════════════════════════════════
    "private equity acquisitions news",
    "alternative data investing trends",
    "headcount data investment signal",
    "hedge fund alternative data",
    "ESG workforce metrics investing",
    "human capital due diligence",
    "M&A market trends",
    "corporate restructuring news",
    "search fund acquisition trends",
    "roll-up strategy private equity",

    # ═══════════════════════════════════════════
    # ECONOMICS & LABOR MARKETS
    # ═══════════════════════════════════════════
    "labor market report",
    "unemployment rate trends",
    "wage growth data",
    "inflation impact on hiring",
    "recession indicator data",
    "labor force participation trends",
    "job openings JOLTS",
    "immigration workforce impact",
    "minimum wage economic impact",
    "productivity growth paradox",

    # ═══════════════════════════════════════════
    # INDUSTRY VERTICALS
    # ═══════════════════════════════════════════
    "marketing agency industry news",
    "advertising technology trends",
    "fintech workforce trends",
    "healthcare staffing crisis",
    "cybersecurity talent shortage",
    "climate tech hiring",
    "manufacturing automation jobs",
    "biotech workforce expansion",
    "defense tech talent competition",
    "space industry hiring boom",
    "gaming industry layoffs hiring",
    "crypto blockchain hiring trends",
    "energy sector workforce transition",
    "retail technology workforce",
    "logistics supply chain talent",

    # ═══════════════════════════════════════════
    # FUTURE OF WORK
    # ═══════════════════════════════════════════
    "future of work trends",
    "four day work week results",
    "hybrid work productivity research",
    "workplace culture data",
    "employee burnout epidemic data",
    "career change great resignation data",
    "freelance economy growth statistics",
    "upskilling reskilling corporate",
    "digital nomad workforce data",
    "workplace surveillance productivity",
    "return to office mandate data",
    "office occupancy rates trends",
    "coworking space market growth",

    # ═══════════════════════════════════════════
    # GEOPOLITICS & MACRO (creative angles)
    # ═══════════════════════════════════════════
    "US China tech talent war",
    "semiconductor workforce shortage",
    "nearshoring reshoring workforce impact",
    "trade war impact hiring",
    "sanctions impact tech workforce",
    "BRICS economy workforce shifts",
    "European tech talent trends",
    "Middle East tech hub growth",
    "Africa tech workforce emerging",
    "India tech outsourcing evolution",

    # ═══════════════════════════════════════════
    # CONTRARIAN & PROVOCATIVE
    # ═══════════════════════════════════════════
    "LinkedIn data accuracy problems",
    "HR tech failing companies",
    "job title inflation meaningless",
    "company culture myth data",
    "overemployment remote work",
    "quiet quitting actually real data",
    "degrees becoming irrelevant hiring",
    "resume fraud statistics",
    "interview process broken data",
    "performance review useless data",
    "CEO pay worker pay gap data",
    "corporate DEI data reality",
    "layoffs disguised as restructuring",
    "tech bubble workforce signal",

    # ═══════════════════════════════════════════
    # EMERGING TECH (far-field but connectable)
    # ═══════════════════════════════════════════
    "quantum computing talent demand",
    "robotics workforce displacement",
    "AR VR enterprise workforce training",
    "brain computer interface talent",
    "edge computing business growth",
    "5G enterprise applications workforce",
    "digital twin technology business",
    "web3 decentralized workforce",
    "drone industry hiring trends",
    "autonomous vehicles workforce impact",
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

#!/usr/bin/env python3
"""
Vivameda BI Lead Hunter Agent
Searches for buyers of the Workforce Intelligence Dataset (flagship BI product).
Separate from the Agency Dataset lead hunter.

Product: US SaaS Workforce Intelligence (2018-2020), ~4,900 companies, ~1.2M observations.
Broader infrastructure: 1.2TB+, 2010-2025, 250M+ professional records.
Pricing: $5K-$500K/yr depending on segment.
"""

import os
import sys
import json
import csv
import random
import logging
import time
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

try:
    import anthropic
    import httpx
    import requests
except ImportError:
    log.error("Missing dependencies. Run: pip install anthropic httpx")
    sys.exit(1)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
# Pipedrive CRM
PIPEDRIVE_API_TOKEN = os.environ.get("PIPEDRIVE_API_TOKEN", "")
PIPEDRIVE_DOMAIN = "vivameda"

MODEL = "claude-sonnet-4-20250514"

LEADS_CSV = "leads_bi/pipeline.csv"
LEADS_HISTORY = "leads_bi/.lead_history.json"
LEADS_PER_RUN = 20
MIN_SCORE = 5

VINNIE_PHONE = "35799909204"
VINNIE_APIKEY = "wdXW78gEZEFt"


def vinnie_alert(msg: str):
    try:
        httpx.get(
            f"https://api.textmebot.com/send.php?recipient={VINNIE_PHONE}&text={msg}&apikey={VINNIE_APIKEY}",
            timeout=10,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Search queries from BI Buyer Intelligence Dossier
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    # QUANT FUNDS: the proven segment (Quantbot example)
    "small quant fund alternative data workforce",
    "systematic trading firm alternative data sourcing",
    "quant fund BattleFin conference 2025 2026",
    "quant fund Neudata alternative data evaluation",
    "small hedge fund chief data officer",
    "quant fund hiring data sourcing analyst",
    "quantitative fund Eagle Alpha alternative data",
    "emerging quant fund alternative data strategy",
    "quant fund workforce signals alpha generation",
    "small fund backtesting workforce hiring data",

    # AI STARTUPS THAT ANALYZE COMPANIES (the Sumble/Churned pattern)
    "startup predicts company growth revenue workforce",
    "AI company health scoring prediction startup",
    "startup company failure prediction model",
    "AI estimates company revenue headcount",
    "startup tracks hiring as investment signal",
    "company evolution tracking AI startup",
    "talent flow analysis investment signal startup",
    "AI startup company benchmarking scoring product",
    "workforce signal company prediction funded startup",
    "startup uses company data predict outcomes",

    # DATA-DRIVEN PE/VC (the Ensemble VC pattern)
    "boutique PE firm data-driven investment",
    "VC firm talent data platform proprietary",
    "PE firm workforce data due diligence",
    "investment firm proprietary data engine company",
    "VC data-driven deal sourcing workforce signals",
    "PE portfolio monitoring company health data",
    "venture capital data analytics workforce hiring",
    "small PE firm alternative data company evaluation",

    # CONFERENCE ATTENDEES (proven data buyers)
    "BattleFin 2025 2026 attendees speakers",
    "Neudata 2025 2026 alternative data buyers",
    "Eagle Alpha alternative data festival 2026",
    "alternative data conference attendees exhibitors 2026",

    # COMPETITOR CUSTOMERS (want cheaper/deeper alternative)
    "uses Revelio Labs customer switched alternative",
    "Lightcast data customer alternative workforce",
    "LinkedIn Talent Insights alternative company data",
    "Burning Glass alternative workforce data provider",

    # JOB POSTINGS (companies actively buying data)
    "hiring alternative data analyst 2026",
    "hiring data sourcing manager fund 2026",
    "hiring head of data company intelligence startup",
    "job alternative data procurement analyst",

    # PEOPLE-FIRST (find the buyer, then their company)
    "head of alternative data joined appointed 2025 2026",
    "chief data officer startup joined 2025 2026",
    "head of data science quant fund investment",
    "VP data startup company intelligence",

    # SPECIFIC USE CASES FOR OUR DATA
    "company failure prediction training data historical",
    "workforce composition alpha signal equity research",
    "hiring velocity leading indicator revenue prediction",
    "headcount growth predictor company performance",
    "organizational change detection investment signal",
    "company capability transition workforce skills",
    "employee growth contraction signal investment",

    # NICHE VERTICALS
    "private credit risk model company workforce data",
    "supply chain risk scoring company signals workforce",
    "ESG workforce diversity scoring company data",
    "M&A target screening workforce signals",

    # CAREER-PATH EVIDENCE (Ibrahim pattern)
    "YipitData alumni quant fund moved to",
    "Revelio Labs alumni startup moved to",
    "alternative data analyst moved to fund startup",

    # BLOGS/CONTENT FROM BUYERS
    "blog need historical workforce data investment",
    "blog company-level training data hard to find",
    "blog alternative data workforce signals quality",
    "blog backtesting workforce features equity",

    # DOCUMENTATION GAPS (Sumble pattern)
    "site:docs.* company data workforce API coverage",
    "site:docs.* data sources companies historical",

    # MARKETPLACE BROWSERS
    "site:datarade.ai workforce company data",
    "site:snowflake.com marketplace workforce intelligence",
    "AWS Data Exchange workforce company data",
]



















SEGMENT_CONTEXT = """
## VIVAMEDA DATASET (what we sell)

- 4.2M+ companies, 48M+ observed company-year records
- 1950 to 2020 time series (longitudinal, not snapshots)
- Workforce growth, role composition, skill shifts, capability transitions
- 226,000+ high-density companies with >90% attribute coverage
- 86% role coverage, 89% skill coverage at headcount >= 20
- Pre-computed signals: growth acceleration, early scaling, contraction, recovery
- Survivorship-bias-free (includes failed, merged, delisted companies)
- Delivery: CSV, Parquet, Snowflake
- Price: USD 20,000 to 50,000
- Website: https://www.vivameda.com

## TARGET COMPANY PROFILE

We want small to mid-sized teams. Companies where decisions happen fast and budgets do not require months of procurement. 10 to 200 person organizations, founder-led or with a small leadership team, where the person you identify can actually say yes. We want short sales cycles, not enterprise pipelines.

Avoid large multi-strategy shops (Citadel, Point72, Millennium, Two Sigma, etc.) and large enterprises.

## TARGET SEGMENTS

### Segment 1: Small quantitative fund or trading firm
A smaller quant fund or systematic trading firm that uses alternative data. Look for evidence of purchasing external datasets: job postings mentioning alternative data, conference appearances at events like BattleFin, Eagle Alpha, or Neudata, or a visible data sourcing function.

### Segment 2: AI startup building B2B predictive models
A startup (Series A or later, small team) building predictive products for business clients. Examples: companies predicting churn, revenue, hiring trends, company health, or credit risk. They must visibly use ML and would benefit from historical company-level training data. Look for evidence in their product pages, blog posts, documentation, or hiring patterns.

### Segment 3: Boutique PE or VC firm with data-driven approach
A smaller PE or VC firm that uses data to evaluate investments, monitor portfolio companies, or source deals. Look for firms that mention data-driven processes on their website, have an in-house analyst or data team, or have published content about using alternative data in their investment process.

### Additional segments (apply when evidence is strong)
- Distressed debt traders needing bankruptcy prediction signals
- Litigation support firms needing historical workforce evidence
- Insurance underwriters pricing employment-related risk
- Credit risk modelers
- Prediction market traders and data providers

## RESEARCH PROCESS

### Step 1: Company identification
Search results give you candidate companies. Filter for 10 to 200 person teams where workforce data or company evolution data is core to their product or process.

### Step 2: Deep qualification
This is where quality happens. Read the company actual materials. Do not summarize their About page. You must find specific evidence from at least one of these sources:

- Product pages and feature descriptions
- Documentation and API docs (what data they use, what gaps exist)
- Blog posts mentioning data needs, methodology, or data partnerships
- Job postings mentioning alternative data, external datasets, or data sourcing
- Conference appearances at BattleFin, Eagle Alpha, Neudata, Data Council
- Funding announcements describing how capital will be used
- LinkedIn posts from key people about data challenges

What to look for specifically:
- Do they already use workforce or company-level data? What are their gaps?
- Do they have limited historical depth? (Most started collecting after 2015)
- Do they rely on point-in-time snapshots rather than longitudinal panels?
- Are they actively looking to onboard new datasets?
- Is there a dedicated data sourcing or data acquisition role?

### Step 3: Contact identification
Find 1 to 2 decision-makers who evaluate or purchase external datasets.
Prioritize these titles: Chief Data Officer, Head of Data, VP of Data Science, Head of Research, CTO (at startups under 20 people).
Do NOT default to CEO unless the company is under 20 people.
Include full name, job title, LinkedIn profile URL.

### Step 4: Opening angle
Write 1 to 2 sentences that reference something specific you found in Step 2. This must be concrete enough to paste into the first line of a cold email.

### Step 5: Confidence scoring
- HIGH: specific evidence of data purchasing intent or a clear product gap that Vivameda fills, plus an identifiable decision-maker
- MEDIUM: strong product fit but no direct evidence of active data sourcing
- LOW: theoretical fit but no concrete evidence

Only return HIGH and MEDIUM leads. Drop LOW leads entirely.

## QUALITY RULES

- If nothing in this batch qualifies as HIGH or MEDIUM, return empty
- 3 deeply qualified leads are worth more than 20 surface-level ones
- Never produce a lead without specific evidence from their website, docs, or blog
- Never write an opening angle that could apply to any data company
- Never rate a lead HIGH without concrete evidence of data purchasing intent
- The why_buyer field must contain at least one specific URL or reference

## CRITICAL QUALIFYING LOGIC: DATA CONSUMER vs DATA TOOL

Before qualifying ANY lead, determine whether the company CONSUMES external
data as a product input or PROCESSES data their users bring.

### BUYER (consumes external data):
The company's product depends on external datasets to function. They integrate
third-party data into their models, pipelines, or analysis. Without external
data, their product is weaker or incomplete.

Examples: ExtractAlpha (buys datasets to build trading signals), Sumble (needs
company data to train AI models), Wokelo (needs company data for diligence
reports), Churned (uses company signals to predict churn).

### NOT A BUYER (processes user's own data):
The company builds a tool that visualizes, analyzes, or processes whatever data
the user uploads. They are a canvas, not a consumer. They don't need external
datasets because their users bring their own.

Examples: Tableau, Golden Analytics, Metabase, Power BI, Looker. These companies
will never buy our dataset because their product works on any data the user provides.

### THE TEST:
Ask: "If I removed all external datasets from this company's product, would their
product still work?"
- If YES -> they are a TOOL. SKIP.
- If NO -> they are a CONSUMER. QUALIFY.

### NEGATIVE EXAMPLE: Golden Analytics
Golden Analytics launched with $7M seed funding to build an AI-native BI platform.
They use "AI" and "data" in their description. But they are a dashboard tool.
Users upload their own CSV and get visualizations. They don't integrate external
datasets. They are a Tableau replacement, NOT a data buyer. SKIP.

The presence of "AI," "data," "analytics," or "machine learning" in a company
description does NOT make them a buyer. The question is ALWAYS: does their
product depend on external company-level data?

### NEGATIVE EXAMPLE: Nuclia / Progress Agentic RAG
Nuclia builds RAG-as-a-Service that "indexes unstructured data from internal
and external sources." The agent qualified them because they mention "indexing
external data sources." This was wrong. "External sources" means their CUSTOMERS'
external sources — PDFs, videos, documents that users upload. Nuclia itself does
not buy datasets. They are a platform that processes other people's data. Also
acquired by Progress Software (1,800+ employees, public company = too large).
RAG platforms, search platforms, and knowledge management tools are TOOLS, not
data CONSUMERS. SKIP all of them.

### NEGATIVE EXAMPLE: Mercor ($10B AI hiring/labeling marketplace)
Mercor connects human experts with AI labs for RLHF training. $10B valuation,
200+ employees, $492M raised. The agent might qualify them because they are
"AI" and work with "data." Wrong. They are a labor marketplace, not a data
consumer. They don't buy external datasets — they sell human labor to AI labs.
Also way too large for a $20K deal. SKIP all AI hiring/labeling/annotation
platforms: Mercor, Scale AI, Appen, Surge, Micro1, Labelbox.

### NEGATIVE EXAMPLE: Obviant (defense acquisition intelligence)
Obviant builds intelligence for defense acquisition — budgets, congressional
hearings, policy documents. The agent might qualify them because they do
"intelligence" and "analytics." Wrong. They serve defense/government customers
with long procurement cycles. Our workforce data has no defense acquisition
use case. SKIP all defense intelligence, government analytics, and policy
research platforms.

### NEGATIVE EXAMPLE: AfterQuery ($300M AI training data vendor)
AfterQuery SELLS expert-generated training datasets to AI labs. $300M valuation,
$100M+ ARR, 100K contractors. The agent might qualify them because they work
with "training data" and "AI." Wrong. They are a DATA VENDOR like us — they
sell data, they don't buy it. They would see us as a peer or competitor, not
a customer. SKIP all companies that SELL training data or data annotation
services. They are vendors, not buyers.

### QUALITY BENCHMARK: ADVANCED RESEARCH EXAMPLES

The following 6 examples represent the highest quality standard for lead research.
Every lead below has: specific evidence from actual web pages, named decision-makers
with LinkedIn, paste-ready opening angles, and full research trails. MATCH THIS LEVEL.

### Example: Moonfire Ventures (VC, HIGH)
Evidence: Firm positions itself as "a technology company that does venture capital" —
more ML engineers than investors on a ~14-person team. Published post titled
"Building the machine for data-driven investing." Has a dedicated Head of AI & ML
(Jonas Vetterle) and CTO Managing Partner (Mike Arpaia, ex-Facebook).
Angle: "Moonfire's entire identity is 'the machine for data-driven investing' run
by a dedicated Head of AI & ML and a CTO Managing Partner — position Vivameda as
the longitudinal workforce training set their pre-seed sourcing model can't scrape
from public sources."
Research trail: moonfire.com/ → moonfire.com/stories/jonas-vetterle-head-of-ai-ml/
→ "Building the machine for data-driven investing" post.

### Example: Correlation Ventures (VC, HIGH)
Evidence: Analytical co-investment fund trained on 20+ years of US VC financings.
Dedicated analytics org: Managing Director of Analytics (Anu Pathria, ex-Burning
Glass founder), Partner of Analytics, Data Engineer, Senior Analyst. Process is
"data-driven fundraising" built on "the world's most complete VC dataset."
Angle: "Correlation's fund is an analytical co-investment model run by an MD of
Analytics who co-founded Burning Glass — Vivameda's longitudinal workforce panel
is the complementary training input their financings-only dataset is missing."

### Example: Middesk (AI B2B Predictive, HIGH)
Evidence: Credit Assessment page states "Payment history doesn't tell you if the
business is still operating." Product core: "Purpose-built ML models detect risk
patterns. AI agents investigate ownership networks." Open reqs for ML Engineer and
Data Scientist. Launched Signal product fusing "authoritative and alternative data."
Angle: "'Payment history doesn't tell you if the business is still operating.'
Vivameda's headcount trajectory per company-year answers that gap directly —
operating business hires show up first in our panel."
Decision makers: Kurt Ruppel (Co-Founder & CTO), Kyle Mack (Co-Founder & CEO).

### Example: Keyplay (AI B2B Predictive, HIGH)
Evidence: Product page explicitly lists "hiring signals by role and recruiting
velocity" as scoring ingredients. Their differentiator is "measuring growth
activity rather than funding." Story page describes model customization and signal
composition as core product.
Angle: "Your product page calls out 'recruiting velocity' and 'hiring signals by
role' as core scoring ingredients — Vivameda's company-year panel is the longitudinal
version of exactly that signal, across 70 years and 4M+ companies."
Decision maker: Adam Schoenfeld (Co-founder & CEO).

### Example: Sturdy.ai (AI B2B Predictive, HIGH)
Evidence: Revenue threat detection platform. Their churn framework lists
"Executive Sponsor Changes: Detecting when a champion leaves" as a top churn signal
— but they detect it from customer conversations, not company-level data.
Angle: "Their model reads customer conversations. Churn framework names executive
sponsor changes as a top signal — but only catches it once it lands in a customer
email. Vivameda's workforce panel fires that signal directly from company-level data."

### Example: PredictLeads (AI-ML teams, HIGH)
Evidence: Crawls job postings across 2.2M+ companies, 9.2M jobs. Blog post
"Job Openings Data as a Leading Indicator of Company Growth." ML-extracted company
signals since 2016.
Angle: "ML-extracted company signals across 2.2M companies, 9.2M jobs since 2016 —
Vivameda has 70 years of historical depth, pre-dating the web-scraped era."
Decision maker: Matic Perovsek (Founder, CTO, Data Scientist).

### WHAT MAKES THESE EXAMPLES GOLD:

1. EVIDENCE IS SPECIFIC AND ATTRIBUTED
   - Not "they use ML" but "their credit assessment page says X"
   - Every claim has a URL or quote backing it
   - Read product pages, blog posts, team pages, job reqs

2. DECISION-MAKERS ARE NAMED AND LINKED
   - Full name + title + LinkedIn URL
   - Prioritize technical co-founders, Heads of Data/AI, CTOs
   - Check for ex-Burning Glass, ex-YipitData, ex-Revelio signals

3. OPENING ANGLES ARE PASTE-READY
   - Quote something the company actually said
   - Name the exact gap Vivameda fills
   - Write it so the recipient can't say "this is generic"

4. CONFIDENCE NOTES EXPLAIN WHY
   - "Dedicated Head of AI & ML, CTO Managing Partner, ML-stack"
   - "Productized ML" / "Uses job posts as core signal"
   - Short phrases that summarize the buying signals

### RESEARCH PATTERNS TO REPLICATE (CRITICAL):

Pattern 1: Find the engineering/ML team page
- VCs/funds with dedicated AI/ML engineers = data buyers
- "Head of AI & ML" or "Technology Partner" = the right contact
- Engineering:Investor ratio > 1 = highly technical firm

Pattern 2: Read the product/methodology page
- Extract the exact phrases they use about their data
- Identify what they DON'T have (historical depth, snapshot-only, limited coverage)
- Find the buzzwords: "proprietary platform", "ML ensemble", "training set"

Pattern 3: Check job boards
- Active reqs for "Data Engineer", "ML Engineer", "Data Scientist" = operational
  capacity to ingest new datasets
- Active reqs for "Data Sourcing" = explicit signal

Pattern 4: Follow the content trail
- Blog posts about methodology reveal gaps
- Medium/Substack posts from founders about data challenges
- Newsletter archives showing their current thinking

Pattern 5: Check for signal-level products
- Firms selling "risk scores", "predictive models", "scoring APIs" over company
  data are buyers
- "Signal" products often explicitly mention external/alt data consumption

### KEY LESSON FROM THESE FOUR FAILURES:
The agent was fooled by surface-level keywords: "AI", "data", "intelligence",
"analytics", "training data." None of these words make a company a BUYER.

THE REAL QUESTIONS:
1. Does their PRODUCT depend on structured company-level data as INPUT?
2. Are they SMALL enough for a $20K deal (under 200 people)?
3. Do they BUY external datasets, or do they SELL data/labor?
4. Is company evolution / workforce intelligence relevant to what they build?

If any answer is NO → SKIP.

Additional categories to ALWAYS SKIP:
- AI hiring/labeling platforms (Mercor, Scale AI, Appen, Surge)
- Defense/government intelligence platforms
- Companies that SELL training data (AfterQuery, Scale AI)
- RAG/search platforms that process user-uploaded data (Nuclia, Elasticsearch)
- Dashboard/BI tools (Tableau, Golden Analytics, Metabase)
- Companies valued over $500M (too large, too slow)
- Companies with 200+ employees

### POSITIVE EXAMPLE: Fast Data Science
Builds customer churn prediction models. Their blog states they use "data points
available at the snapshot date" as model features. Adding workforce contraction
data as a feature would improve their predictions. VALID LEAD because their
product directly benefits from external company-level data as a feature input.

### UPDATED QUALIFYING QUESTIONS (answer in order):
1. Does the company's product DEPEND on external company-level data?
   (Not just "could use" but "needs")
2. Would our workforce evolution data become a feature, signal, or input in their product?
3. Can the decision-maker approve a $20-50K data purchase without enterprise procurement?
4. Is there specific evidence (blog, job posting, product page, conference) that they source external datasets?

Scoring:
- All four YES = HIGH confidence
- Three YES = MEDIUM confidence
- Two or fewer YES = SKIP entirely

## QUALITY BENCHMARK: REAL EXAMPLES (study these carefully)

### Example A: Anomaly Capital Management (Quant Fund, MEDIUM)
A data scientist (Christopher Goessling) moved from YipitData to this quant fund.
At YipitData his role was "identifying, screening, licensing, cleaning, and analyzing
alternative data." A data scientist moving from an alt data provider INTO a quant fund
strongly suggests active data sourcing function. This is the kind of career-path
evidence that makes a lead actionable.
OPENING: "Given your background at YipitData sourcing alternative data, I'd love to
show you how a 70-year workforce panel could help Anomaly build structural signals
like capability transitions before they show up in fundamentals."

### Example B: Churned (AI Startup B2B Predictive, HIGH)
11-50 person AI startup building churn prediction models. Founders explained in a
podcast that they use ML models (not rule-based) to predict customer churn. Their
models use product usage and financial data. INSIGHT: when a customer's headcount
declines or hiring slows, it signals financial stress leading to subscription
cancellations. Workforce data = early indicator BEFORE it shows in usage/payment.
OPENING: "Your churn models use product usage and financial signals. Have you explored
adding company-level workforce data as an early indicator of customer health before it
shows up in usage or payment patterns?"

### Example C: Ensemble VC (Data-Driven VC, HIGH)
11-50 person VC that "continuously scrapes, analyzes, and refreshes billions of
datapoints across the global talent ecosystem." They already built an in-house
alternative data engine focused on workforce signals. But they only have current
data — no historical depth. Vivameda adds 70 years of company evolution.
OPENING: "Your platform already scrapes billions of talent ecosystem datapoints. I'd
like to show you how a 70-year company-level workforce panel could add capability
transition and hiring discipline features to your scoring models."

### What makes these examples exceptional:
1. Career-path evidence: tracking where data professionals moved FROM (YipitData → quant fund = data buyer)
2. Podcast/interview mining: finding specific statements about methodology and data needs
3. Gap identification: they have current data but no historical depth — Vivameda fills exactly this
4. Feature-level pitch: not "you might like our data" but "headcount decline = churn early indicator"
5. Platform adjacency: they already built a talent data engine, so they understand the value instantly

### Research patterns to replicate:
- Check team pages for ex-alt-data-provider employees (YipitData, Revelio, Lightcast alumni = data buyers)
- Find podcast interviews where founders discuss methodology and data inputs
- Look for "our platform scrapes/analyzes/aggregates" language = already built data infrastructure
- Identify the specific feature our data would add to their existing product
- Match company size (11-50) with founder-led structure = fast purchasing decision

## COMPANIES TO SKIP

Do not qualify any company already in the known_companies list provided with each batch.
Also skip these permanently: Revelio Labs, Lightcast, LinkedIn, Vivameda, any company with fewer than 5 employees.
"""



















def load_lead_history() -> set:
    if os.path.exists(LEADS_HISTORY):
        try:
            with open(LEADS_HISTORY) as f:
                return set(json.load(f).get("companies", []))
        except Exception:
            pass
    return set()


def save_lead_history(companies: set):
    try:
        os.makedirs(os.path.dirname(LEADS_HISTORY), exist_ok=True)
        with open(LEADS_HISTORY, "w") as f:
            json.dump({"companies": list(companies)}, f)
    except Exception as e:
        log.warning(f"Could not save lead history: {e}")


def brave_search(query: str, count: int = 10) -> list[dict]:
    resp = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": count, "freshness": "py"},
        headers={"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": BRAVE_API_KEY},
        timeout=15,
    )
    if resp.status_code != 200:
        log.warning(f"Brave search failed ({resp.status_code})")
        return []
    results = resp.json().get("web", {}).get("results", [])
    return [{"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("description", "")} for r in results]


def google_search(query: str, count: int = 10) -> list[dict]:
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return []
    try:
        resp = httpx.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": min(count, 10)},
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning(f"Google search failed ({resp.status_code})")
            return []
        items = resp.json().get("items", [])
        return [{"title": r.get("title", ""), "url": r.get("link", ""), "description": r.get("snippet", "")} for r in items]
    except Exception as e:
        log.warning(f"Google search error: {e}")
        return []



def fetch_page(url: str, max_chars: int = 3000) -> str:
    """Fetch a web page and return text content, truncated."""
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; VivamedalBot/1.0)"
        })
        if resp.status_code != 200:
            return ""
        text = resp.text
        # Strip HTML tags roughly
        import re
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    except Exception as e:
        log.warning(f"Failed to fetch {url}: {e}")
        return ""

def extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def qualify_leads_with_claude(search_results: list[dict], known_companies: set) -> list[dict]:
    if not search_results:
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    results_text = ""
    for i, r in enumerate(search_results):
        results_text += f"\n{i+1}. {r['title']}\n   URL: {r['url']}\n   Description: {r['description']}\n   === HOMEPAGE ===\n   {r.get('page_content', '[not fetched]')[:1500]}\n   === SUBPAGES (product/about/data/docs) ===\n   {r.get('subpages', '[none found]')[:2000]}\n   === DEEP EVIDENCE (blogs/hiring/methodology) ===\n   {r.get('deep_evidence', '[none found]')[:2000]}\n"

    known_list = ", ".join(list(known_companies)[:50]) if known_companies else "None yet"

    prompt = f"""You are a Lead Research & Qualification Agent for Vivameda.

You have been given DEEP RESEARCH on each candidate: their homepage, product/about/data
subpages, blog posts, hiring pages, and methodology pages. Use ALL of this to qualify.

PRODUCT: Longitudinal workforce intelligence. 4.2M companies, 48M records, 1950-2020.
Headcount, growth, roles, skills, capability transitions. $20K-$50K. Parquet/CSV/Snowflake.

FOR EACH CANDIDATE, do this analysis:

1. DATA CONSUMER TEST: Does their product DEPEND on external company-level data?
   If they process user-uploaded data (dashboards, BI tools, RAG) → SKIP
   If their product needs external company/workforce data to function → CONTINUE

2. EVIDENCE CHECK: From the homepage, subpages, and deep evidence provided, find:
   - What data sources they currently use (and gaps)
   - Job postings for data roles
   - Blog posts about data methodology
   - Conference appearances
   - Product pages showing data integrations

3. GAP IDENTIFICATION: What specific gap does Vivameda fill?
   - Limited historical depth? (most start after 2015)
   - Snapshot-only, no longitudinal view?
   - Missing workforce/company evolution signals?

4. OPENING ANGLE: Write 1-2 sentences referencing something specific from the research.
   If you found a blog post, reference it. If you found a data gap, name it.
   If you found nothing specific, write the best angle based on their product.

ALWAYS SKIP:
- Dashboard/BI tools, RAG/search platforms, AI hiring/labeling platforms
- Companies that SELL training data or annotation
- Defense/government platforms
- Pure recruiting/ATS without ML
- Over 200 employees
- Competitors: Revelio Labs, Lightcast, People Data Labs

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

RESEARCH RESULTS (homepage + subpages + deep evidence for each candidate):
{results_text}

Return ONLY valid JSON:

{{{{"leads": [{{{{
  "company": "Company Name",
  "website": "domain.com",
  "segment": "Company Intelligence / Quant Fund / AI Predictive / PE-VC",
  "why_buyer": "3-5 sentences with specific evidence from the research provided. Reference specific pages, data gaps, or methodology mentions you found in the subpages or deep evidence.",
  "evidence_url": "URL of the strongest evidence page",
  "buying_signals": "Specific signals found in research",
  "suggested_opening_angle": "1-2 sentences referencing something specific. Paste-ready for cold email.",
  "confidence": "HIGH or MEDIUM with justification",
  "recommended_contact_role": "Specific name if found in research, otherwise title",
  "company_size": "Estimated",
  "est_data_budget": "$20K-$50K",
  "use_case": "Specific use case based on their product",
  "country": "HQ country",
  "lead_score": 7
}}}}],
"analysis": {{{{
  "top_3": ["A", "B", "C"],
  "top_3_reasoning": "Strongest evidence of data need + smallest team + clearest gap",
  "emerging_themes": ""
}}}}
}}}}

If nothing qualifies: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "No qualifying leads", "emerging_themes": ""}}}}}}

QUALITY BAR:
- HIGH: found specific evidence in subpages/blogs/hiring of data purchasing intent
- MEDIUM: product clearly needs this data but no explicit evidence found
- Include MEDIUM leads — the human will do final verification
- 5-10 leads per batch. Quality matters but don't reject everything.
- If a company looks like a plausible buyer, INCLUDE IT at MEDIUM confidence.
"""


















    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = resp.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.split("```")[0].strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            if "analysis" in parsed:
                analysis = parsed["analysis"]
                if analysis.get("top_3"):
                    log.info(f"Top 3 today: {', '.join(analysis['top_3'])}")
                if analysis.get("emerging_themes"):
                    log.info(f"Emerging themes: {analysis['emerging_themes'][:200]}")
            return parsed.get("leads", [])
        return []
    except json.JSONDecodeError:
        log.warning("Claude returned invalid JSON")
        return []



def append_to_csv(leads: list[dict]):
    os.makedirs(os.path.dirname(LEADS_CSV), exist_ok=True)
    file_exists = os.path.exists(LEADS_CSV)

    with open(LEADS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Date", "Company", "Website", "Segment",
                "Why They Are a Buyer", "Evidence URL",
                "Buying Signals", "Lead Score",
                "Recommended Contact Role", "Company Size",
                "Est. Data Budget", "Known Subscriptions",
                "Notes", "Status",
            ])

        today = datetime.now().strftime("%Y-%m-%d")
        for lead in leads:
            writer.writerow([
                today,
                lead.get("company", ""),
                lead.get("website", ""),
                lead.get("segment", ""),
                lead.get("why_buyer", ""),
                lead.get("evidence_url", ""),
                lead.get("buying_signals", ""),
                lead.get("lead_score", ""),
                lead.get("recommended_contact_role", lead.get("contact_role", "")),
                lead.get("company_size", ""),
                lead.get("est_data_budget", ""),
                lead.get("known_subscriptions", ""),
                lead.get("notes", ""),
                "New",
            ])


def email_csv():
    if not GMAIL_APP_PASSWORD:
        log.warning("No Gmail password, skipping email")
        return
    if not os.path.exists(LEADS_CSV):
        log.warning("No CSV to email")
        return

    msg = MIMEMultipart()
    msg["From"] = "nold.oliver@gmail.com"
    msg["To"] = "oli@vivameda.com"
    msg["Subject"] = f"Vivameda BI LEADS - Workforce Intelligence - {datetime.now().strftime('%Y-%m-%d')}"

    body = "BI product leads (Workforce Intelligence Dataset) attached.\nThis is the flagship product pipeline, not the agency dataset.\n\n- Vinnie"
    msg.attach(MIMEText(body, "plain"))

    with open(LEADS_CSV, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=vivameda_bi_leads_{datetime.now().strftime('%Y%m%d')}.csv")
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login("nold.oliver@gmail.com", GMAIL_APP_PASSWORD)
            server.sendmail("nold.oliver@gmail.com", "oli@vivameda.com", msg.as_string())
        log.info("BI leads email sent")
    except Exception as e:
        log.warning(f"Email failed: {e}")




def find_decision_maker(company_name: str, domain: str) -> dict:
    """Search for decision maker LinkedIn profile using Brave/Google."""
    result = {"name": "", "title": "", "linkedin": ""}
    query = f'"{company_name}" CEO OR founder OR "head of research" OR "head of data" site:linkedin.com'
    
    try:
        # Try Brave first
        results = brave_search(query, count=3)
        if not results:
            results = google_search(query, count=3)
        
        for r in results:
            url = r.get("url", "")
            title_text = r.get("title", "")
            if "linkedin.com/in/" in url and company_name.lower().split()[0].lower() in title_text.lower():
                result["linkedin"] = url
                # Extract name from LinkedIn title (usually "Name - Title - Company")
                parts = title_text.split(" - ")
                if parts:
                    result["name"] = parts[0].strip().replace(" | LinkedIn", "")
                if len(parts) > 1:
                    result["title"] = parts[1].strip()
                break
    except Exception as e:
        log.warning(f"Decision maker search failed for {company_name}: {e}")
    
    return result

def push_to_pipedrive(leads):
    """Push qualified leads to Pipedrive as Organizations + Leads."""
    if not PIPEDRIVE_API_TOKEN:
        log.warning("No Pipedrive API token, skipping CRM push")
        return 0

    base_url = f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/api/v1"
    pushed = 0

    for lead in leads:
        try:
            # Step 1: Create Organization
            website = lead.get('website', '')
            if website and not website.startswith('http'):
                website = 'https://' + website
            org_data = {
                "name": lead.get("company", "Unknown Company"),
                "visible_to": "3",  # visible to whole company
            }
            if website:
                org_data["website"] = website
            org_resp = requests.post(
                f"{base_url}/organizations?api_token={PIPEDRIVE_API_TOKEN}",
                json=org_data,
                timeout=15,
            )
            if org_resp.status_code not in (200, 201):
                log.warning(f"  Pipedrive org create failed for {lead.get('company')}: {org_resp.status_code}")
                continue

            org_id = org_resp.json().get("data", {}).get("id")
            if not org_id:
                log.warning(f"  No org ID returned for {lead.get('company')}")
                continue

            # Step 2: Create Lead linked to Organization
            score = lead.get("lead_score", 0)
            segment = lead.get("segment", "?")
            notes_parts = [
                f"Score: {score} | Segment: {segment}",
                f"Website: {lead.get('website', 'N/A')}",
                f"Why buyer: {lead.get('why_buyer', 'N/A')}",
                f"Signals: {lead.get('buying_signals', 'N/A')}",
                f"Contact role: {lead.get('recommended_contact_role', 'N/A')}",
                f"Size: {lead.get('company_size', 'N/A')}",
                f"Est. budget: {lead.get('est_data_budget', 'N/A')}",
                f"Evidence: {lead.get('evidence_url', 'N/A')}",
                f"Notes: {lead.get('notes', 'N/A')}",
            ]

            lead_data = {
                "title": lead.get("company", "Unknown"),
                "organization_id": org_id,
                "value": {
                    "amount": lead.get("lead_score", 0),
                    "currency": "USD",
                },
            }

            lead_resp = requests.post(
                f"{base_url}/leads?api_token={PIPEDRIVE_API_TOKEN}",
                json=lead_data,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if lead_resp.status_code not in (200, 201):
                log.warning(f"  Pipedrive lead create failed for {lead.get('company')}: {lead_resp.status_code}")
                continue

            lead_id = lead_resp.json().get("data", {}).get("id")

            # Step 2.5: Find decision maker and create Person in Pipedrive
            dm = find_decision_maker(lead.get("company", ""), lead.get("website", ""))
            if dm.get("name"):
                person_data = {
                    "name": dm["name"],
                    "org_id": org_id,
                    "visible_to": "3",
                }
                if dm.get("linkedin"):
                    # Store LinkedIn in a custom note since Pipedrive doesn't have a native LinkedIn field
                    pass
                person_resp = requests.post(
                    f"{base_url}/persons?api_token={PIPEDRIVE_API_TOKEN}",
                    json=person_data,
                    timeout=15,
                )
                if person_resp.status_code in (200, 201):
                    person_id = person_resp.json().get("data", {}).get("id")
                    log.info(f"  Created person: {dm['name']} for {lead.get('company')}")
                    # Link person to lead
                    if person_id and lead_id:
                        requests.patch(
                            f"{base_url}/leads/{lead_id}?api_token={PIPEDRIVE_API_TOKEN}",
                            json={"person_id": person_id},
                            timeout=15,
                        )
                # Add DM info to notes
                if dm.get("name"):
                    notes_parts.append(f"Decision Maker: {dm['name']} ({dm.get('title', 'N/A')})")
                if dm.get("linkedin"):
                    notes_parts.append(f"LinkedIn: {dm['linkedin']}")
            
            time.sleep(1)  # Rate limit for search

            # Step 3: Add note with all the details
            if lead_id:
                note_data = {
                    "content": "\n".join(notes_parts),
                    "lead_id": lead_id,
                }
                requests.post(
                    f"{base_url}/notes?api_token={PIPEDRIVE_API_TOKEN}",
                    json=note_data,
                    timeout=15,
                )

            pushed += 1
            log.info(f"  Pushed to Pipedrive: {lead.get('company')} (org {org_id}, lead {lead_id})")

        except Exception as e:
            log.warning(f"  Pipedrive error for {lead.get('company')}: {e}")

    return pushed


def main():
    if not ANTHROPIC_API_KEY or not BRAVE_API_KEY:
        log.error("Missing API keys")
        sys.exit(1)

    log.info("BI Lead Hunter starting (Workforce Intelligence product)...")

    known = load_lead_history()
    log.info(f"Known companies: {len(known)}")

    queries = random.sample(SEARCH_QUERIES, min(15, len(SEARCH_QUERIES)))

    all_results = []
    seen_domains = set()

    for query in queries:
        log.info(f"Searching: {query[:60]}...")
        results = brave_search(query, count=10)
        google_results = google_search(query, count=10)
        results.extend(google_results)

        for r in results:
            domain = extract_domain(r["url"])
            if domain in seen_domains or domain in known:
                continue
            skip_domains = [
                "linkedin.com", "facebook.com", "twitter.com", "youtube.com",
                "reddit.com", "g2.com", "capterra.com", "producthunt.com",
                "crunchbase.com", "pitchbook.com", "wikipedia.org", "github.com",
                "medium.com", "forbes.com", "techcrunch.com", "bloomberg.com",
                "revelio.com", "lightcast.io", "peopledatalabs.com",
                "vivameda.com", "revelioresearch.com", "revealera.com",
                "nuclia.com", "progress.com",
                "mercor.com", "mercor.ai", "afterquery.com", "afterquery.ai",
                "obviant.com", "scale.com", "appen.com", "surge.ai",
                "labelbox.com", "micro1.ai",
            ]
            if any(domain.endswith(sd) for sd in skip_domains):
                continue
            seen_domains.add(domain)
            # MULTI-PAGE RESEARCH: fetch homepage + key subpages
            page_text = fetch_page(r["url"])
            if page_text:
                r["page_content"] = page_text[:2000]
            
            # Try to fetch product/about/data pages for deeper context
            domain_url = r["url"].rstrip("/")
            base_url = "/".join(domain_url.split("/")[:3])  # https://domain.com
            extra_content = []
            for subpath in ["/about", "/product", "/platform", "/data", "/docs", "/how-it-works", "/solutions", "/api", "/integrations"]:
                try:
                    sub_text = fetch_page(base_url + subpath, max_chars=1500)
                    if sub_text and len(sub_text) > 200:
                        extra_content.append(sub_text[:1000])
                except Exception:
                    pass
                if len(extra_content) >= 3:
                    break
            if extra_content:
                r["subpages"] = " ||| ".join(extra_content)
            
            # TARGETED deep evidence search
            company_name = r.get("title", "").split(" - ")[0].split(" | ")[0].strip()
            if company_name and len(company_name) > 2:
                deep_evidence = []
                try:
                    # Search for data methodology, partnerships, and hiring
                    data_results = brave_search(f'"{company_name}" data sources methodology external datasets', count=3)
                    hiring_results = brave_search(f'"{company_name}" hiring "data scientist" OR "alternative data" OR "head of data"', count=3)
                    blog_results = brave_search(f'"{company_name}" blog data OR dataset OR partnership OR integration', count=3)
                    for dr in data_results + hiring_results + blog_results:
                        if dr.get("url") != r.get("url"):
                            # Fetch the actual evidence page
                            evidence_text = fetch_page(dr["url"], max_chars=1000)
                            if evidence_text and len(evidence_text) > 100:
                                deep_evidence.append(f"SOURCE: {dr['url']}\nCONTENT: {evidence_text[:500]}")
                            else:
                                deep_evidence.append(f"{dr['title']}: {dr['description'][:200]}")
                    if deep_evidence:
                        r["deep_evidence"] = " ||| ".join(deep_evidence[:4])
                except Exception:
                    pass
            
            all_results.append(r)

        time.sleep(1)

    log.info(f"Found {len(all_results)} unique candidate URLs")

    if not all_results:
        log.info("No new candidates found today")
        vinnie_alert("Vinnie+here.+BI+Lead+Hunter+found+nothing+new+today.+All+quiet+on+the+flagship.")
        return

    all_leads = []

    # ONE-TIME MANUAL LEADS INJECTION
    manual_companies = [
        # CYPRUS QUANT FIRMS
        {"company": "Pinely", "website": "pinely.com", "country": "Cyprus"},
        {"company": "QST Financial", "website": "qstfinancial.com", "country": "Cyprus"},
        {"company": "FinYX Investments", "website": "finyx.com", "country": "Cyprus"},
        {"company": "Quant Infinity", "website": "quantinfinity.com", "country": "Cyprus"},
        {"company": "Alfa Algorithms", "website": "alfaalgorithms.com", "country": "Cyprus"},
        {"company": "AIP Algorithmic Investment Platform", "website": "aip.com.cy", "country": "Cyprus"},
        {"company": "Alber Blanc Capital", "website": "alberblanc.com", "country": "Cyprus"},
        {"company": "Boltzmann Research", "website": "boltzmannresearch.com", "country": "Cyprus"},
        {"company": "Victoria Quant", "website": "victoriaquant.com", "country": "Cyprus"},
        {"company": "Quant Tekel", "website": "quanttekel.com", "country": "Cyprus"},
        {"company": "V-Quant Trading", "website": "v-quant.com", "country": "Cyprus"},
        {"company": "AENAON Markets", "website": "aenaonmarkets.com", "country": "Cyprus"},
        {"company": "MasterFunders", "website": "masterfunders.com", "country": "Cyprus"},
        {"company": "Olive Tree Capital Markets", "website": "otcm.com.cy", "country": "Cyprus"},
        {"company": "FXPro", "website": "fxpro.com", "country": "Cyprus"},
        {"company": "Exness", "website": "exness.com", "country": "Cyprus"},
        # PREVIOUS DATA COMPANIES
        {"company": "Exact Data", "website": "exactdata.com"},
        {"company": "Fount Media", "website": "fountmedia.com"},
        {"company": "Thomson Data", "website": "thomsondata.com"},
        {"company": "Lake B2B", "website": "lakeb2b.com"},
        {"company": "Data Axle SMB", "website": "dataaxle.com"},
        {"company": "Salesfully", "website": "salesfully.com"},
        {"company": "Email Data Group", "website": "emaildatagroup.net"},
        {"company": "Lead Forensics", "website": "leadforensics.com"},
        {"company": "Versium", "website": "versium.com"},
        {"company": "Alesco Data", "website": "alescodata.com"},
        {"company": "BoldData", "website": "bolddata.nl"},
        {"company": "LeadGenius", "website": "leadgenius.com"},
        {"company": "Coresignal", "website": "coresignal.com"},
        {"company": "Forager.ai", "website": "forager.ai"},
        {"company": "Grepsr", "website": "grepsr.com"},
        {"company": "Lead411", "website": "lead411.com"},
        {"company": "Datanyze", "website": "datanyze.com"},
        {"company": "InfoUSA", "website": "infousa.com"},
        {"company": "DataCaptive", "website": "datacaptive.com"},
        {"company": "LeadsPlease", "website": "leadsplease.com"},
    ]
    
    manual_leads_file = "leads_bi/.manual_injected.json"
    already_injected = set()
    if os.path.exists(manual_leads_file):
        with open(manual_leads_file) as mf:
            already_injected = set(json.load(mf))
    
    new_manual = [m for m in manual_companies if m["website"] not in already_injected]
    
    if new_manual:
        log.info(f"Injecting {len(new_manual)} manual research targets...")
        # Research each company using search
        for mc in new_manual:
            company = mc["company"]
            domain = mc["website"]
            log.info(f"  Researching: {company} ({domain})...")
            
            research_results = brave_search(f"{company} {domain} company about", count=5)
            google_results = google_search(f"{company} {domain} company about", count=5)
            research_results.extend(google_results)
            
            if research_results:
                try:
                    qualified = qualify_leads_with_claude(research_results, known)
                    if qualified:
                        # Use the first qualified result but override company name and website
                        lead = qualified[0]
                        lead["company"] = company
                        lead["website"] = domain
                        all_leads.append(lead)
                    else:
                        # Create a basic lead entry even if Claude doesn't qualify
                        all_leads.append({
                            "company": company,
                            "website": domain,
                            "segment": "Manual Research Target",
                            "why_buyer": "Manually identified data company for outreach.",
                            "evidence_url": f"https://{domain}",
                            "buying_signals": "Manual target - requires human review.",
                            "lead_score": 6,
                            "recommended_contact_role": "Founder / CEO / Head of Data",
                            "company_size": "Unknown",
                            "est_data_budget": "$15K-$50K",
                            "known_subscriptions": "Unknown",
                            "notes": "Manually added research target.",
                            "product_fit": "Data Product / Training Data",
                            "use_case": "Review and qualify manually",
                            "is_hot": False,
                            "tier": 2,
                            "country": "US",
                        })
                except Exception as e:
                    log.warning(f"  Research failed for {company}: {e}")
                    all_leads.append({
                        "company": company,
                        "website": domain,
                        "segment": "Manual Research Target",
                        "why_buyer": "Manually identified - research failed.",
                        "evidence_url": f"https://{domain}",
                        "buying_signals": "Manual target.",
                        "lead_score": 5,
                        "recommended_contact_role": "Founder / CEO",
                        "company_size": "Unknown",
                        "est_data_budget": "$15K-$50K",
                        "known_subscriptions": "Unknown",
                        "notes": "Manually added. Auto-research failed.",
                        "product_fit": "Review needed",
                        "use_case": "Review manually",
                        "is_hot": False,
                        "tier": 3,
                        "country": "US",
                    })
            
            already_injected.add(domain)
            time.sleep(1)
        
        # Save injected list so we don't repeat
        os.makedirs(os.path.dirname(manual_leads_file), exist_ok=True)
        with open(manual_leads_file, "w") as mf:
            json.dump(list(already_injected), mf)
        log.info(f"Manual injection complete: {len(new_manual)} companies researched")


    for i in range(0, len(all_results), 8):
        batch = all_results[i:i+8]
        log.info(f"Qualifying batch {i//15 + 1} ({len(batch)} results)...")
        try:
            leads = qualify_leads_with_claude(batch, known)
            all_leads.extend(leads)
        except Exception as e:
            log.error(f"Batch {i//15 + 1} failed: {e}. Continuing with leads found so far.")
        time.sleep(2)

    final_leads = []
    for lead in all_leads:
        domain = lead.get("website", "").lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        confidence = lead.get("confidence", "").upper()
        score = lead.get("lead_score", 0)
        # Accept HIGH (8-10) or MEDIUM (5-7), reject LOW
        if confidence.startswith("LOW"):
            continue
        if domain and domain not in known and score >= MIN_SCORE:
            final_leads.append(lead)
            known.add(domain)

    final_leads = final_leads[:LEADS_PER_RUN]

    if final_leads:
        append_to_csv(final_leads)
        save_lead_history(known)
        pushed = push_to_pipedrive(final_leads)
        log.info(f"Pushed {pushed}/{len(final_leads)} leads to Pipedrive")
        email_csv()

        high_score = [l for l in final_leads if l.get("lead_score", 0) >= 8]
        msg = (
            f"Vinnie+here.+BI+Lead+Hunter+found+{len(final_leads)}+new+leads+today+(flagship+product)."
            f"+{len(high_score)}+scored+above+8."
            f"+Top:+{final_leads[0].get('company', 'Unknown').replace(' ', '+')}"
            f"+({final_leads[0].get('lead_score', '?')}pts,+Segment+{final_leads[0].get('segment', '?')})."
            f"+CSV+sent+to+email.+Check+oli@vivameda.com+boss."
        )
        vinnie_alert(msg)

        log.info(f"\nFound {len(final_leads)} qualified BI leads:")
        for lead in final_leads:
            log.info(f"  {lead['company']} (Seg {lead.get('segment', '?')}) - Score: {lead.get('lead_score', '?')}")
    else:
        log.info("No qualified BI leads found today")
        vinnie_alert("Vinnie+here.+BI+Lead+Hunter+ran+but+no+qualified+leads+today.+Standards+are+high+for+the+flagship.")

    print(f"\nDone! {len(final_leads)} BI leads added to pipeline.")


if __name__ == "__main__":
    main()

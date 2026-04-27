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
### THE AVATAR: COMPANIES THAT BUILD AI MODELS ON COMPANY DATA

Vivameda sells longitudinal company-evolution data (4.2M companies, 48M company-year
records, 1950-2020) as TRAINING SUBSTRATE for any AI/ML model that reasons about
companies. The avatar is ONE thing said many ways:

  "Companies that build AI models on top of company data."

This includes:
- AI investment research / equity analyst platforms
- AI due diligence agents (PE, M&A, consulting)
- AI deal sourcing platforms with proprietary ML
- B2B predictive AI startups scoring companies (credit risk, churn, growth)
- Quant funds running ML on company-level alt data
- Data-driven VCs with proprietary sourcing models
- Synthetic-population / company-simulation startups
- Workforce-signal startups feeding investor models

A buyer has ALL of these properties:
1. Their product trains, fine-tunes, or grounds models on external company data
2. Output is a SIGNAL/SCORE/PREDICTION/INSIGHT about a company's future state
3. 10-100 employees, Seed to Series B, founder/CTO has buying authority
4. Budget for $5K-$20K data deals (rough heuristic; not procurement-bound)
5. Has explicit data-quality concerns: "training corpus", "ground truth",
   "fine-tuning", "evaluation benchmark", "data layer", "pre-training"

### THE DATA CONSUMER TEST (CRITICAL)

Ask: "If I removed all external company datasets, would their product still work?"
- YES they still work -> they are a TOOL or AGGREGATOR -> SKIP
- NO their product breaks -> they are a DATA CONSUMER -> QUALIFY

### GOLD-STANDARD EXAMPLES (POSITIVE)

These are real qualified buyers. MATCH THIS LEVEL of evidence and angle.

Example: Bridgetown Research (HIGH)
Evidence: Series A $19M (Accel + Lightspeed + Sequoia, Feb 2025). Seattle/Bangalore.
Founded Dec 2023 by Harsh Sahai (ex-McKinsey, ex-Amazon ML research scientist).
"AI agents that crawl the internet and analyze datasets" + voice agents that
interview industry experts. They sell to PE, VC, consulting, corporate strategy.
Angle: "Bridgetown's agents synthesize secondary research with primary expert
interviews, but every output needs structural grounding. Vivameda provides 70 years
of company evolution as the longitudinal substrate their analysis layer is missing."
Decision maker: Harsh Sahai (CEO/Co-founder).

Example: DiligenceSquared (HIGH)
Evidence: YC F25, $5M seed (Relentless / ex-Index Ventures Damir Becirovic, Oct 2025).
Co-founders Frederik Hansen (ex-Blackstone principal) and Soren Biltoft (ex-BCG PE
practice). AI voice-agent platform delivering McKinsey-grade commercial diligence
for $50K vs the $500K-$1M traditional cost.
Angle: "DiligenceSquared replaces $500K McKinsey reports with AI voice agents at
$50K. Their next moat is the data their agents reason over. Vivameda is the
longitudinal company corpus that turns voice-agent transcripts into defensible
diligence insights."
Decision makers: Frederik Hansen (CEO), Soren Biltoft, Harshil Rastogi (ex-Google).

Example: Brightwave (HIGH)
Evidence: $15M Series A. Founded by Mike Conover, ex-Databricks principal scientist
(led the Dolly LLM team). AI research analyst for investment professionals — reads
filings and generates investment theses.
Angle: "Brightwave grounds AI research analyst output in filings. Filings tell you
what a company reported. Vivameda's longitudinal workforce panel tells you what a
company actually became — a complementary feature layer for investment thesis
generation."
Decision maker: Mike Conover (Co-founder, ex-Databricks).

Example: Grasp (HIGH)
Evidence: $7M Series A. Multi-agent AI analyst that automates IB and management
consulting workflows. Small team, founder-led.
Angle: "Multi-agent IB analyst output is only as good as its company-data
substrate. Vivameda is 4.2M companies with 70 years of structural evolution data
— the substrate Grasp's agents need to produce defensible analysis."

Example: Aaru (HIGH)
Evidence: $50M+ multi-tier Series A 2025, blended valuation ~$1B. Founded March
2024 by Cameron Fink, Ned Koh, John Kessler. Generates "thousands of AI agents
that simulate human behavior using both public and proprietary data." Pre-trains
synthetic populations on company-level behavioral data.
Angle: "Aaru pre-trains synthetic populations on public + proprietary data.
Workforce-evolution patterns over 70 years are the missing structural input —
synthetic agents that understand how companies hire, grow, and contract."
Decision makers: Cameron Fink, Ned Koh, John Kessler.

Example: Linq Alpha (HIGH)
Evidence: AI co-pilot for hedge fund analysts. Builds private LLM-driven research
tools for buy-side. Small Seed/Series A team. Felix Wang (ex-Hedgeye) co-founder.
Angle: "Linq Alpha trains private LLMs for hedge fund research. The longitudinal
company-year panel is the entity-resolved feature layer their research tools need
to ground predictions across decades, not just the last 10 years of public filings."
Decision maker: Felix Wang (Co-founder/CEO, ex-Hedgeye).

Example: Daloopa (HIGH)
Evidence: Series B reported 2024. AI extracts financial data from filings to power
equity research models. Founded by Thomas Li.
Angle: "Daloopa already trains models on company financials extracted from filings.
Vivameda adds the next axis: workforce composition and capability transitions across
70 years — features that filings don't structure."
Decision maker: Thomas Li (CEO/Co-founder).

### NEGATIVE EXAMPLES (DO NOT QUALIFY)

Skip these patterns - they look adjacent but FAIL the Data Consumer test:

- Golden Analytics: dashboard tool over customer data, not company training data
- Nuclia / Progress: RAG infrastructure (processes user docs, not company data)
- Mercor: AI hiring marketplace (matches humans, not models on companies)
- Obviant: defense procurement intelligence (gov data, not company evolution)
- AfterQuery: AI training data vendor for foundation labs (PEER not buyer)
- Crunchr / HRBench: HR dashboards (consume internal HR data, not external panels)
- Humwork / agent platforms: human-in-the-loop infra (no model training on companies)
- Babbl Labs: video intelligence vendor (sells data, peer not buyer)
- Live Data Technologies: present-tense workforce data vendor (PEER)
- Databar / SyncGTM / Apollo: GTM/sales enrichment (resells data, partnership not sale)

### KEY LESSON FROM THESE FAILURES

Surface keywords are not enough. "AI" + "data" + "intelligence" can describe both
buyers AND tools/peers/aggregators. Always run the Data Consumer test.

### RESEARCH PATTERNS TO REPLICATE

Pattern 1 - Engineering/ML team page: dedicated Heads of AI/ML, CTO co-founder,
ML Engineer reqs = data buyer

Pattern 2 - Product/methodology page: extract exact phrases about their data;
identify gaps (no historical depth, snapshot-only, limited coverage)

Pattern 3 - Job postings: open reqs for "Data Engineer", "ML Engineer",
"Data Scientist", "Data Sourcing Manager" = operational capacity to ingest

Pattern 4 - Content trail: blog posts, Substack, podcast appearances about
data challenges, methodology, training corpus needs

Pattern 5 - Funding signal: Seed-Series B in last 12 months; founder-led;
pricing on website suggests <$50K ACV (so $5-20K data deal fits in budget)

Pattern 6 - Founder background: ex-McKinsey/BCG/Bain, ex-FAANG ML, ex-PE/IB
analysts, ex-data-vendor employees (YipitData, Revelio, Burning Glass alumni)
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

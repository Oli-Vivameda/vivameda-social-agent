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
LEADS_PER_RUN = 5
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
    # Segment 1: Small Quant Funds
    "small quant fund alternative data workforce",
    "systematic trading firm alternative data sourcing",
    "quant fund BattleFin conference alternative data",
    "quant fund Neudata alternative data evaluation",
    "small hedge fund chief data officer alternative data",
    "quant fund hiring data sourcing analyst",
    "systematic fund external datasets workforce",
    "quantitative fund Eagle Alpha alternative data",

    # Segment 2: AI Startups B2B Predictive
    "AI startup company prediction model training data",
    "AI startup B2B predictive model company data",
    "startup predicts company health workforce data",
    "AI startup credit risk prediction company features",
    "startup company intelligence ML training data",
    "AI startup workforce data predictive model",
    "startup building company scoring ML model",
    "AI startup churn prediction company-level data",

    # Segment 3: Boutique PE/VC Data-Driven
    "boutique PE firm data-driven investment evaluation",
    "VC firm data-driven deal sourcing",
    "PE firm alternative data portfolio monitoring",
    "boutique VC data analyst investment research",
    "PE firm workforce data due diligence",

    # Additional Segments
    "distressed debt trader bankruptcy prediction data",
    "litigation support firm workforce evidence historical",
    "insurance underwriter employment risk data",
    "credit risk modeler company data historical",

    # Evidence-rich searches
    "company blog alternative data needs gaps datasets",
    "startup documentation data sources company-level",
    "company hiring alternative data analyst sourcing",
    "firm conference BattleFin Neudata Eagle Alpha speaker",
    "startup raised funding data acquisition company",

    # Geographic
    "quant fund alternative data US small",
    "AI startup company prediction Israel",
    "PE firm data-driven UK London boutique",
    "AI startup company data EU funded",

    # Site-targeted
    "site:crunchbase.com AI startup company prediction funded",
    "site:linkedin.com chief data officer quant fund small",
    "site:medium.com alternative data workforce company signals",
    "site:ycombinator.com company data AI prediction",

    # Documentation pattern queries (finds specific data gaps)
    "site:docs.* company data workforce API",
    "site:docs.* data sources companies coverage",
    '"our data" company workforce historical coverage',
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
        results_text += f"\n{i+1}. {r['title']}\n   URL: {r['url']}\n   Description: {r['description']}\n   Page Content: {r.get('page_content', '[not fetched]')[:1500]}\n   Deep Evidence: {r.get('deep_evidence', '[none found]')}\n"

    known_list = ", ".join(list(known_companies)[:50]) if known_companies else "None yet"

    prompt = f"""You are a Lead Research & Qualification Agent for Vivameda.

Research and qualify HIGH-PROBABILITY buyer leads. Each lead must include
specific, verifiable evidence of fit and a concrete outreach angle.

PRODUCT: Longitudinal workforce intelligence dataset. 4.2M+ companies,
48M+ company-year records, 1950-2020. USD 20,000-50,000. CSV/Parquet/Snowflake.

KEY DIFFERENTIATORS: Historical depth (1950-2020), longitudinal structure
(not snapshots), pre-computed signals, 226K+ high-density companies.

SEGMENTS:
1. Small quant funds using alt data (10-200 people, avoid large multi-strats)
2. AI startups building B2B predictive models (Series A+, small team)
3. Boutique PE/VC with data-driven approach (10-200 people)
Also: distressed debt, litigation support, insurance, credit risk, prediction markets

DEEP QUALIFICATION REQUIRED:
- Read their actual website, docs, blog posts, job postings
- Find SPECIFIC evidence: data gaps, alt data mentions, conference appearances,
  data sourcing roles, methodology discussions
- Identify the exact gap Vivameda fills (limited history? snapshot-only? no workforce data?)

OPENING ANGLE MUST BE SPECIFIC:
- Reference something concrete they said, built, or published
- "Your data starts at 2022. Vivameda goes back to 1950." = GOOD
- "You might benefit from our data." = REJECT

CONFIDENCE:
- HIGH: specific evidence of data purchasing intent + decision-maker identified
- MEDIUM: strong product fit but no direct data sourcing evidence
- LOW: theoretical fit only

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Return JSON:

"leads": array, each element:
{{{{
  "company": "Company Name",
  "website": "domain.com",
  "segment": "Small Quant Fund / AI Startup B2B Predictive / Boutique PE-VC Data-Driven",
  "why_buyer": "3-5 sentences with SPECIFIC evidence. Must reference at least one concrete source: a blog post, job posting, documentation page, conference appearance, or funding announcement. Example: Per their docs at docs.company.com/data, their foundation is built on job posts starting 2022. They have no historical depth. Vivameda fills this gap with 48M records back to 1950.",
  "evidence_url": "https://specific-page-you-found.com",
  "buying_signals": "Specific signals: CDO role exists, spoke at BattleFin, blog mentions needing more datasets, hiring data scientist.",
  "lead_score": 9,
  "recommended_contact_role": "CDO / Head of Data / VP Data Science / CTO",
  "company_size": "25",
  "est_data_budget": "$20K-$50K",
  "known_subscriptions": "Unknown",
  "notes": "SEGMENT: AI Startup. CONFIDENCE: HIGH. OPENING ANGLE: Your data foundation covers 2.6M companies from 2022. Vivameda adds 4.2M companies back to 1950 with longitudinal workforce signals. GAP: no historical depth, snapshot-only.",
  "product_fit": "Training Data / Signal Discovery / Feature Engineering",
  "use_case": "Fill historical gap in company-level data for predictive model training",
  "is_hot": true,
  "tier": 1,
  "country": "US"
}}}}

"analysis": {{{{
  "top_3": ["Company A", "Company B", "Company C"],
  "top_3_reasoning": "Specific evidence of data purchasing intent + clear product gap + identifiable decision-maker",
  "emerging_themes": "Patterns from today"
}}}}

Empty: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "Nothing qualified", "emerging_themes": "None"}}}}}}

RULES:
- Max 5 leads per run. ONLY high-confidence matches.
- Each lead must have SPECIFIC evidence from their website/docs/blog.
- Opening angle must reference something concrete. Generic = reject.
- 10-200 employees. Small enough for fast decisions.
- 3 deeply qualified leads > 20 surface-level ones.
- If nothing qualifies, return empty. Do NOT pad.
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
            ]
            if any(domain.endswith(sd) for sd in skip_domains):
                continue
            seen_domains.add(domain)
            # Fetch actual page content for deep qualification
            page_text = fetch_page(r["url"])
            if page_text:
                r["page_content"] = page_text[:2000]
            
            # Second search pass: find deep evidence (blog posts, conference appearances)
            company_name = r.get("title", "").split(" - ")[0].split(" | ")[0].strip()
            if company_name and len(company_name) > 2:
                deep_evidence = []
                try:
                    blog_results = brave_search(f'"{company_name}" blog data dataset', count=3)
                    conf_results = brave_search(f'"{company_name}" conference neudata battlefin eagle alpha', count=3)
                    for dr in blog_results + conf_results:
                        if dr.get("url") != r.get("url"):
                            deep_evidence.append(f"{dr['title']}: {dr['description'][:200]}")
                    if deep_evidence:
                        r["deep_evidence"] = " | ".join(deep_evidence[:3])
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


    for i in range(0, len(all_results), 15):
        batch = all_results[i:i+15]
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

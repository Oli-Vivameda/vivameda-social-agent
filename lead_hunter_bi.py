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
LEADS_PER_RUN = 25
MIN_SCORE = 4

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
    # People Analytics / Talent Intelligence
    "people analytics startup ML company data",
    "talent intelligence platform AI startup",
    "workforce planning AI company ML models",
    "workforce analytics startup machine learning",
    "people analytics company training data",
    "talent intelligence AI startup funded",

    # Company Intelligence / Firmographic
    "company intelligence platform AI startup",
    "firmographic scoring AI company startup",
    "company benchmarking platform ML startup",
    "company scoring engine AI machine learning",
    "competitive intelligence AI startup data",

    # Credit Risk / ESG / Financial
    "credit risk modeling AI company data startup",
    "ESG scoring platform AI structured data",
    "credit risk AI startup company data",
    "ESG analytics AI company machine learning",
    "financial risk AI startup structured data",

    # Market Intelligence / Alt Data
    "market intelligence platform AI startup",
    "alternative data aggregation company ML",
    "market intelligence AI company structured data",
    "alt data startup machine learning company",

    # HR Tech with ML component
    "HR tech AI startup machine learning analytics",
    "HR analytics AI company workforce data",
    "workforce prediction AI startup HR",

    # Training data seekers
    "AI startup training data company-level structured",
    "ML company needs structured dataset historical",
    "AI startup feature engineering company data",
    "startup data acquisition structured datasets",
    "AI company proprietary data structured historical",

    # Geographic
    "AI startup people analytics US funded",
    "talent intelligence startup UK London",
    "company intelligence AI startup Israel",
    "workforce AI startup EU Europe funded",

    # Funded / Why Now
    "AI startup raised seed series A 2025 2026 people analytics",
    "talent intelligence startup funding 2025 2026",
    "company intelligence AI funded 2025 2026",
    "workforce analytics startup hiring ML engineer",

    # Site-targeted
    "site:crunchbase.com people analytics AI startup funded",
    "site:crunchbase.com talent intelligence startup series A",
    "site:crunchbase.com company intelligence AI funded",
    "site:linkedin.com head of ML people analytics startup",
    "site:ycombinator.com company data AI workforce",
]














SEGMENT_CONTEXT = """
====================================================================
AI/ML DATA BUYER LEAD AGENT
====================================================================

Target: AI/ML companies that would buy structured historical company
data for model training.

====================================================================
COMPANY PROFILE
====================================================================

Companies building products in:
- People analytics
- Talent intelligence
- Workforce planning
- HR tech (with ML/analytics component)
- Company intelligence
- Firmographic scoring
- Credit risk modeling
- ESG scoring
- Company benchmarking
- Market intelligence platforms
- Alternative data aggregation

Stage: Seed through Series C
- Small enough that one person decides on data purchases
- Large enough to have budget

Team size: 10-200 people

MUST have ML engineers, data scientists, or AI researchers on team.
Ideally already buying or licensing external datasets.

====================================================================
HARD EXCLUSIONS
====================================================================

- Companies that only sell real-time data or live dashboards
- Pure recruiting/ATS platforms with no analytical or ML component
- Companies larger than 500 people (too slow to close)
- Direct workforce data competitors:
  Revelio Labs, Lightcast, People Data Labs, LinkedIn Talent Insights,
  Burning Glass, Eightfold AI (at scale)

====================================================================
TARGET PERSONA
====================================================================

Title:
- CTO
- VP Engineering
- Head of Data
- Head of ML
- ML Lead
- Chief Data Officer
- Founder (if technical)

The person who can evaluate a dataset sample and approve a $10K-$20K
purchase without a procurement process.

====================================================================
GEOGRAPHIES
====================================================================

- US (primary)
- UK
- EU
- Israel

These are where AI/ML companies cluster and where data purchasing is normal.

====================================================================
SEARCH SIGNALS (look for these)
====================================================================

- Job postings mentioning "training data", "data acquisition",
  "ML engineer", "data pipeline"
- Website mentions "proprietary data", "structured data",
  "historical data", "longitudinal", "company intelligence"
- Blog posts or papers about using company-level or workforce data
- Recently raised funding (means budget to spend on data)
- Mentions feature engineering, model training, backtesting

====================================================================
VIVAMEDA DATASET CONTEXT
====================================================================

- ~4.2M companies, ~60M+ company-year records
- 1950-2020 time series, company-year grain
- Hiring velocity, growth, churn, seniority shifts, skill signals
- 1.88B skill-level signals
- Survivorship-bias-free (includes failed/merged/delisted companies)
- 87% role coverage at headcount >= 20
- 96.5% capability coverage
- Pre-structured, analysis-ready BI views
- Delivery: Parquet, CSV, JSONL
- Price: $10K-$20K (up to $50K for training data license)

====================================================================
WHY OUR DATA FITS AI/ML USE CASES
====================================================================

- Pre-structured tabular data ready for ML pipelines
- 4.2M companies x multiple years = massive feature set
- Hiring velocity, skill signals, role distribution = predictive features
- Survivorship-bias-free = clean training data
- Time series = temporal patterns for sequence models
- Parquet/CSV/JSONL = drops into any ML pipeline
- Historical depth back to 1950 = no one else has this

====================================================================
QUALITY STANDARD
====================================================================

- Every lead must have ML/data science on their team
- Must build a product where company-level data is a training input
- If they only do NLP/vision/audio without company data angle -> SKIP
- If they are a competitor selling workforce data -> SKIP
- Must be closeable in 1-3 calls
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
        results_text += f"\n{i+1}. {r['title']}\n   URL: {r['url']}\n   {r['description']}\n"

    known_list = ", ".join(list(known_companies)[:50]) if known_companies else "None yet"

    prompt = f"""You are an AI/ML Data Buyer Lead Agent for Vivameda.

Find AI/ML companies (10-200 employees, Seed to Series C) that would buy
structured historical company data for model training. $10K-$50K deals.

PRODUCT AREAS: people analytics, talent intelligence, workforce planning,
company intelligence, firmographic scoring, credit risk modeling, ESG scoring,
company benchmarking, market intelligence, alt data aggregation.

MUST HAVE: ML engineers, data scientists, or AI researchers on team.
IDEALLY: already buying or licensing external datasets.

TARGET PERSONA: CTO, VP Engineering, Head of Data, Head of ML, Founder (technical).
Person who evaluates a dataset sample and approves $10K-$20K without procurement.

GEOGRAPHIES: US, UK, EU, Israel.

SEARCH SIGNALS:
- Job postings: "training data", "data acquisition", "ML engineer"
- Website: "proprietary data", "structured data", "historical data"
- Blog/papers about company-level or workforce data in models
- Recently raised funding

EXCLUDE: real-time only, pure ATS/recruiting, 500+ employees,
competitors (Revelio Labs, Lightcast, People Data Labs).

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Return JSON:

"leads": array, each element:
{{{{
  "company": "Company Name",
  "website": "domain.com",
  "segment": "People Analytics / Talent Intelligence / Company Intelligence / Credit Risk / ESG / Market Intelligence",
  "why_buyer": "Builds talent intelligence platform. 40 employees. Series A funded. Has ML team. Uses external workforce datasets for model training.",
  "evidence_url": "https://...",
  "buying_signals": "Raised $8M Series A. Hiring ML engineers. Website mentions structured data and proprietary models. Blog about workforce prediction.",
  "lead_score": 9,
  "recommended_contact_role": "CTO / Head of Data / Head of ML",
  "company_size": "40",
  "est_data_budget": "$10K-$50K",
  "known_subscriptions": "Unknown",
  "notes": "What they build: talent intelligence platform scoring companies on workforce health. Why our data fits: 60M company-year records as training features for their scoring model. Signal: raised Series A, hiring ML engineers.",
  "product_fit": "ML Training Data License",
  "use_case": "Train workforce scoring model using historical company-level features",
  "is_hot": true,
  "tier": 1,
  "country": "US"
}}}}

"analysis": {{{{
  "top_3": ["Company A", "Company B", "Company C"],
  "top_3_reasoning": "Has ML team + uses company data + funded + technical founder can evaluate sample",
  "emerging_themes": "Patterns from today"
}}}}

Empty: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "Nothing qualified", "emerging_themes": "None"}}}}}}

OUTPUT per lead:
1. Company name + website
2. What they build (one line)
3. Why our data fits (one line)
4. Contact name and title (from decision maker search)
5. LinkedIn URL
6. Score (1-10)

RULES:
- 10-15 leads per batch
- Every lead has ML/data science on team
- Must build product where company data = training input
- 10-200 employees, Seed to Series C
- US, UK, EU, Israel
- Closeable in 1-3 calls
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
            ]
            if any(domain.endswith(sd) for sd in skip_domains):
                continue
            seen_domains.add(domain)
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
        if domain and domain not in known and lead.get("lead_score", 0) >= MIN_SCORE:
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

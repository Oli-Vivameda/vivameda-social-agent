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
    # Financial/Investment Prediction AI (US)
    "AI startup company prediction financial US",
    "machine learning startup equity signal prediction",
    "AI lab company performance prediction structured data",
    "startup predicts company growth firmographic data",
    "AI company revenue forecasting structured features",
    "AI startup credit risk scoring company data",
    "startup success prediction AI model",
    "private market intelligence AI startup",

    # Company Intelligence AI
    "AI company scoring engine startup",
    "company benchmarking AI platform startup",
    "AI startup M&A target ranking",
    "competitive intelligence AI scoring startup",
    "company health prediction AI startup",
    "AI startup company classification model",

    # Economic/Labor Modeling AI
    "AI startup economic forecasting structured data",
    "machine learning labor market prediction startup",
    "AI workforce prediction model startup",
    "sector forecasting AI company data",

    # Israel AI Labs
    "AI startup Israel company prediction",
    "machine learning startup Tel Aviv company data",
    "AI lab Israel financial prediction",
    "Israel AI startup structured data training",
    "AI company Israel investment prediction",

    # Training data seekers
    "AI startup needs structured training data company",
    "machine learning startup feature engineering company data",
    "AI lab training data structured datasets",
    "startup looking for company-level training data",
    "AI company tabular data training features",
    "machine learning startup data quality problems",

    # Funded / Why Now
    "AI startup raised seed 2025 2026 company prediction",
    "ML startup series A 2025 2026 structured data",
    "AI company Y Combinator company prediction",
    "AI startup launched scoring product 2026",
    "ML startup hiring data scientist company analysis",

    # Backtesting / benchmarking seekers
    "AI startup backtesting company signals",
    "ML company benchmarking historical data",
    "AI startup feature engineering firmographic",

    # Site-targeted
    "site:crunchbase.com AI startup company prediction funded",
    "site:ycombinator.com company prediction AI",
    "site:producthunt.com company scoring AI",
    "site:linkedin.com AI lab company prediction small team",
]













SEGMENT_CONTEXT = """
====================================================================
REVENUE-FOCUSED LEAD GENERATION AGENT — SMALL AI LABS
====================================================================

Your only goal: find small AI labs (5-50 employees) that actively train
or evaluate models on structured company, workforce, or economic data
and would realistically pay $15K-$50K for external training datasets
within 2-4 weeks.

If a company is not a clear data buyer, REJECT it.

====================================================================
STRATEGIC CORE RULE (NON-NEGOTIABLE)
====================================================================

If they don't build prediction, scoring, or forecasting models using
structured company/economic data -> REJECT.

This overrides everything.

====================================================================
GEOGRAPHY PRIORITY
====================================================================

Focus ONLY on:
- United States (primary)
- Israel (very high-quality AI density)

Secondary (only if perfect fit):
- UK
- Canada

Reject everything else unless exceptional.

====================================================================
IDEAL ICP (ALL THREE MANDATORY)
====================================================================

1. Model Type (MANDATORY) — they build at least one of:
   - Prediction models
   - Scoring / ranking systems
   - Forecasting systems
   - Classification models
   - Time-series models

2. Data Type (MANDATORY) — they use or require:
   - Company-level data
   - Firmographic data
   - Workforce / hiring data
   - Business / economic time series
   - Structured tabular datasets

3. Product Output (MANDATORY) — they SELL:
   - Predictions
   - Scores
   - Rankings
   - Insights derived from models
   NOT dashboards. NOT automation.

====================================================================
PERFECT BUYER SEGMENTS (PRIORITIZE HARD)
====================================================================

1. AI for investment / financial prediction
   - Company performance prediction
   - Private market intelligence
   - Equity / credit signals
   - Startup success prediction

2. AI company intelligence platforms
   - Company scoring engines
   - Benchmarking tools
   - M&A target ranking
   - Competitive intelligence

3. AI economic / labor modeling
   - Workforce prediction
   - Sector forecasting
   - Macro models using company data

====================================================================
HARD EXCLUSIONS (STRICT — NO EXCEPTIONS)
====================================================================

Reject immediately if:

Product category:
- Chatbot / copilot / assistant
- Agent / workflow automation
- CRM / support AI
- Dev tools / infra / MLOps
- Data labeling / annotation
- Generic "AI platform"
- Consulting / services

Technical scope:
- NLP-only (text analysis only)
- Computer vision
- Audio / speech
- Robotics

Data usage:
- Only uses client/internal data
- No evidence of external dataset usage

Company size:
- Over 100 employees
- Enterprise AI companies

====================================================================
CRITICAL FILTER (THIS FIXES YOUR PIPELINE)
====================================================================

You MUST identify this explicitly:
"What exact model do they train?"

If you cannot answer this clearly -> REJECT.

Acceptable answers:
- "predicts company growth probability using structured firmographic features"
- "ranks startups based on likelihood to scale"
- "forecasts sector performance using company-level signals"
- "classifies companies into risk categories using historical data"

If the answer is vague like "uses AI", "analyzes data", "builds insights"
-> REJECT

====================================================================
"WHY NOW" SIGNAL (MANDATORY — at least ONE)
====================================================================

- Raised seed / Series A (last 24 months)
- Hiring ML / data scientists
- Launched product involving prediction/scoring
- YC / Product Hunt / early traction
- Mentions: training data, structured datasets, feature engineering,
  forecasting, benchmarking

====================================================================
DATA FIT (YOU MUST EXPLAIN THIS)
====================================================================

For every lead, explain EXACTLY how they would use our dataset:
- Training input
- Feature enrichment
- Backtesting
- Benchmarking
- Model validation

If you cannot map this -> REJECT

====================================================================
SCORING MODEL (ENFORCE STRICTLY)
====================================================================

Data Fit (0-4):
  4 = direct, obvious training use case
  3 = strong
  <=2 = reject

Speed to Close (0-3):
  3 = founder-led, small team
  2 = moderate
  1 = slow

Why Now (0-2):
  2 = strong trigger
  1 = weak

Commercial Relevance (0-1):
  1 = clear B2B monetization

TOTAL:
  8-10 -> HIGH PRIORITY
  6-7  -> SECONDARY
  <6   -> REJECT

====================================================================
GOLD STANDARD (MENTAL MODEL)
====================================================================

A perfect lead should feel like:
"If I send them a 300-company Parquet sample today, their CTO will test it this week."

If that is not true -> reject.

====================================================================
EXTRA EDGE (IMPORTANT FOR REVENUE)
====================================================================

Bias towards companies that:
- Talk about feature engineering
- Talk about training data problems
- Complain about data quality / missing data
- Mention benchmarking or backtesting

These are buyers in pain.

====================================================================
FINAL STRATEGIC NOTE
====================================================================

You were previously targeting "AI companies."
Now you are targeting "AI companies that depend on structured historical
data to train predictive models."

That is probably <5% of the AI market — but 90% of your buyers.

====================================================================
VIVAMEDA DATASET CONTEXT
====================================================================

- ~4.2M companies, ~60M+ company-year records
- 1950-2020 time series
- Hiring velocity, growth, churn, seniority shifts, skill signals
- 1.88B skill-level signals
- Survivorship-bias-free (includes failed/merged/delisted)
- 87% role coverage at headcount >= 20
- 96.5% capability coverage
- Delivery: Parquet, CSV, JSONL
- Price: $15K-$50K training data license
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

    prompt = f"""You are a Revenue-Focused Lead Generation Agent finding Small AI Labs.

Find AI labs (5-50 employees) that train predictive models on structured
company/economic data. US and Israel primary. UK/Canada secondary.

CORE RULE: If they don't build prediction, scoring, or forecasting models
using structured company/economic data -> REJECT. This overrides everything.

CRITICAL FILTER: "What exact model do they train?"
If you cannot answer clearly -> REJECT.
"uses AI" or "analyzes data" = REJECT.
Must be specific: "predicts company growth using firmographic features."

PERFECT SEGMENTS:
1. AI for investment/financial prediction (company performance, equity signals)
2. AI company intelligence platforms (scoring, benchmarking, M&A ranking)
3. AI economic/labor modeling (workforce prediction, sector forecasting)

HARD EXCLUDE: chatbots, assistants, agents, CRM AI, dev tools, MLOps,
data labeling, NLP-only, vision, audio, robotics, consulting, services,
100+ employees, enterprise AI, only uses internal/client data.

SCORING (enforce strictly):
Data Fit (0-4) + Speed to Close (0-3) + Why Now (0-2) + Commercial Relevance (0-1)
8-10 = HIGH PRIORITY. 6-7 = SECONDARY. Below 6 = REJECT.

GOLD STANDARD: "If I send them a 300-company Parquet sample today,
their CTO will test it this week." If not true -> reject.

BIAS TOWARD: companies mentioning feature engineering, training data problems,
data quality complaints, benchmarking, backtesting. These are buyers in pain.

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Return JSON:

"leads": array, each element:
{{{{
  "company": "Lab Name",
  "website": "domain.com",
  "segment": "Financial Prediction AI / Company Intelligence AI / Economic Modeling AI",
  "why_buyer": "8-person AI lab. Predicts startup success using firmographic features. Raised $3M seed. CTO ex-Two Sigma. Needs structured company data.",
  "evidence_url": "https://...",
  "buying_signals": "Raised seed. Hiring ML engineers. Product scores companies. Mentions feature engineering on blog.",
  "lead_score": 9,
  "recommended_contact_role": "Founder / CTO",
  "company_size": "8",
  "est_data_budget": "$15K-$50K",
  "known_subscriptions": "Unknown",
  "notes": "EXACT MODEL: predicts startup success probability using firmographic and workforce features. DATA FIT: training input for classification model. WHY NOW: raised $3M seed Q4 2025. OUTREACH: Send 300-company Parquet sample.",
  "product_fit": "ML Training Data License",
  "use_case": "Train startup success prediction model using workforce composition as input features",
  "is_hot": true,
  "tier": 1,
  "country": "US"
}}}}

"analysis": {{{{
  "top_3": ["Lab A", "Lab B", "Lab C"],
  "top_3_reasoning": "Train on structured company data + small team + funded + CTO would test Parquet this week",
  "emerging_themes": "Patterns from today"
}}}}

Empty: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "Nothing qualified", "emerging_themes": "None"}}}}}}

OUTPUT per lead:
1. Company name + website
2. Location (US or Israel preferred)
3. Employee estimate
4. What they build (SPECIFIC model/product)
5. EXACT model use case (concrete, not vague)
6. Why they need our dataset (specific training use)
7. Why now (trigger)
8. Decision maker (Founder/CTO)
9. Score (1-10)
10. One-line outreach angle

RULES:
- 10-15 leads per batch
- Score 6+ only. Below 6 = reject.
- MUST answer "what exact model do they train?"
- US + Israel primary. UK/Canada secondary.
- 5-50 employees, founder-led
- "Send Parquet sample -> CTO tests this week" = the bar
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

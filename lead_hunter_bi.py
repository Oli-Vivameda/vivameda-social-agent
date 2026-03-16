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
except ImportError:
    log.error("Missing dependencies. Run: pip install anthropic httpx")
    sys.exit(1)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
MODEL = "claude-sonnet-4-20250514"

LEADS_CSV = "leads_bi/pipeline.csv"
LEADS_HISTORY = "leads_bi/.lead_history.json"
LEADS_PER_RUN = 8
MIN_SCORE = 50

VINNIE_PHONE = "4915129005414"
VINNIE_APIKEY = "5944134"


def vinnie_alert(msg: str):
    try:
        httpx.get(
            f"https://api.callmebot.com/whatsapp.php?phone={VINNIE_PHONE}&text={msg}&apikey={VINNIE_APIKEY}",
            timeout=10,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Search queries from BI Buyer Intelligence Dossier
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    # Segment A: VC / Growth Equity
    '"venture capital" "data-driven" "workforce data" OR "headcount" OR "hiring signals"',
    '"venture capital" "head of data" OR "data scientist" hiring',
    '"VC" "alternative data" "workforce" OR "employment" OR "people analytics"',
    '"growth equity" "data team" OR "research platform" OR "quantitative"',
    '"VC data stack" OR "venture capital data infrastructure"',
    '"portfolio monitoring" "workforce" OR "headcount" OR "hiring"',
    '"venture capital" raised new fund 2025 OR 2026',
    '"data-driven investing" VC workforce',

    # Segment B: Hedge Funds / Quant
    '"hedge fund" "alternative data" "workforce" OR "employment" OR "headcount"',
    '"alternative data" "workforce intelligence" OR "people data" OR "hiring data"',
    '"Head of Alternative Data" OR "Data Procurement" hedge fund',
    '"quantitative research" "workforce" OR "employment data" OR "hiring signals"',
    '"Neudata" OR "Battlefin" attendee OR speaker OR exhibited',
    '"alternative data" marketplace workforce employment',
    '"quant fund" "data science" workforce OR headcount',
    '"systematic fund" alternative data procurement',

    # Segment C: Alt Data Platforms / Aggregators
    '"alternative data marketplace" OR "data exchange" workforce employment',
    '"Revelio Labs" OR "Lightcast" OR "Burning Glass" client OR user OR competitor',
    '"People Data Labs" OR "Proxycurl" OR "Thinknum" workforce data',
    '"Snowflake Marketplace" workforce OR employment OR headcount',
    '"AWS Data Exchange" workforce OR employment OR hiring',
    '"data aggregator" workforce OR people OR employment',

    # Segment D: Corporate Strategy / Market Intel
    '"competitive intelligence" "workforce data" OR "hiring patterns" OR "headcount"',
    '"market intelligence" "workforce analytics" OR "organizational analysis"',
    '"corporate strategy" "alternative data" workforce OR talent',
    '"M&A due diligence" workforce data OR headcount analysis',

    # Segment E: AI/ML Companies
    '"machine learning" "workforce data" OR "employment data" training',
    '"AI" "company data" OR "workforce data" structured dataset',
    '"feature engineering" workforce OR employment OR headcount',
    '"NLP" OR "LLM" company intelligence OR workforce intelligence',
    '"sales intelligence" workforce data OR hiring signals',

    # Segment F: HR-Tech / Workforce Analytics
    '"HR tech" "data enrichment" OR "workforce data" OR "external data"',
    '"workforce analytics" platform data enrichment',
    '"people analytics" "external data" OR "third party data"',
    '"talent intelligence" platform data OR dataset',

    # Segment G: Consulting
    '"workforce study" OR "organizational analysis" McKinsey OR BCG OR Bain',
    '"consulting" "workforce data" OR "headcount analysis" project',

    # Trigger events
    '"raised fund" venture capital 2025 OR 2026 "data"',
    '"Head of Data" hired VC OR "venture capital" OR "investment" 2026',
    '"alternative data" conference 2026 exhibitor OR sponsor',
    'hiring "data procurement" OR "alternative data analyst" 2026',

    # Competitors / landscape
    '"workforce intelligence" OR "people analytics data" provider',
    '"Revelio Labs" OR "Lightcast" alternative OR competitor',
]

SEGMENT_CONTEXT = """
BUYER SEGMENTS for Vivameda Workforce Intelligence Datasets:

Product: Structured workforce intelligence. 250M+ professional records processed into
company-year observations. US SaaS dataset: ~4,900 companies, ~1.2M observations (2018-2020).
Broader infrastructure: 1.2TB+, 2010-2025. Delivery: Parquet, CSV, JSONL.

Key differentiator: TEMPORAL workforce data. Not snapshots. Trajectories over time.
Headcount growth, hiring patterns, org structure changes, role distributions, seniority shifts.

Segment A: VC / Growth Equity (30% priority)
- Portfolio monitoring, deal sourcing, due diligence
- Budget: $10K-$100K/yr
- Signals: data team hires, "data-driven" on website, new fund raised

Segment B: Hedge Funds / Quant (25% priority)
- Alt data signals for investment models, alpha generation
- Budget: $25K-$500K/yr
- Signals: alt data conference attendance, "Head of Alt Data" role, quantitative approach

Segment C: Alt Data Platforms / Aggregators (15%)
- Resale, enrichment, platform integration
- Budget: $15K-$200K/yr
- Signals: data marketplace, partnership pages, "Head of Data Partnerships"

Segment D: Corporate Strategy / Market Intel (15%)
- Competitive intelligence, M&A research
- Budget: $10K-$75K/yr
- Signals: "market intelligence" team, M&A activity

Segment E: AI/ML Companies (5%)
- Training data, feature engineering
- Budget: $5K-$50K/yr
- Signals: ML team, company intelligence product

Segment F: HR-Tech / Workforce Analytics (5%)
- Platform enrichment, benchmarking
- Budget: $10K-$100K/yr

Segment G: Management Consulting (5%)
- Client deliverables, sector research
- Budget: $5K-$50K/project

SCORING (max 100, minimum 50):
+30: Buys external data products (confirmed)
+20: Has dedicated data/research team (2+ people)
+15: Is in Segment A, B, or C
+10: Has published/used workforce or hiring data
+10: Recently raised fund or received funding
+5: Hiring data/research roles currently
+5: Based in major financial center
-15: Company <10 employees
-10: Builds own workforce data internally
-25: Direct competitor (Revelio, Lightcast, PDL)
-20: No data capability or team

DISQUALIFY if:
- Does not use external data
- Direct workforce data competitor (Revelio, Lightcast, People Data Labs)
- No data/analytics/research function
- Pre-revenue startup with no funding
- Exclusively consumer-market focused
- <5 employees (unless funded AI startup)
- Use case does not require temporal/longitudinal data
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
        params={"q": query, "count": count, "freshness": "pm"},
        headers={"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": BRAVE_API_KEY},
        timeout=15,
    )
    if resp.status_code != 200:
        log.warning(f"Brave search failed ({resp.status_code})")
        return []
    results = resp.json().get("web", {}).get("results", [])
    return [{"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("description", "")} for r in results]


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

    prompt = f"""You are a lead qualification specialist for Vivameda's WORKFORCE INTELLIGENCE DATASET product.
This is NOT the agency dataset. This is the flagship BI/investment product.

{SEGMENT_CONTEXT}

Below are search results. For each that represents a POTENTIAL BUYER of temporal workforce intelligence data:

1. Identify the company
2. Determine segment (A/B/C/D/E/F/G)
3. Explain WHY they would buy temporal workforce data (1-2 sentences, specific)
4. Note evidence URL
5. List buying signals
6. Score using the model
7. Recommend contact role
8. Estimate company size
9. Note any known data subscriptions if visible

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Respond ONLY with a JSON array:
{{
  "company": "Company Name",
  "website": "domain.com",
  "segment": "A",
  "why_buyer": "Specific reason they need temporal workforce data",
  "evidence_url": "https://...",
  "buying_signals": "Signal 1. Signal 2.",
  "lead_score": 75,
  "contact_role": "Head of Data",
  "company_size": "50-100",
  "est_data_budget": "$25K-$75K/yr",
  "known_subscriptions": "PitchBook, Revelio",
  "notes": "Additional context"
}}

If NO results qualify, return: []
Only include leads scoring 50+. Be strict. These are enterprise data buyers.
Do NOT include: marketing agencies, workforce data competitors (Revelio, Lightcast, PDL), irrelevant companies.
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
        leads = json.loads(text)
        if not isinstance(leads, list):
            return []
        return leads
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
                lead.get("contact_role", ""),
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


def main():
    if not ANTHROPIC_API_KEY or not BRAVE_API_KEY:
        log.error("Missing API keys")
        sys.exit(1)

    log.info("BI Lead Hunter starting (Workforce Intelligence product)...")

    known = load_lead_history()
    log.info(f"Known companies: {len(known)}")

    queries = random.sample(SEARCH_QUERIES, min(4, len(SEARCH_QUERIES)))

    all_results = []
    seen_domains = set()

    for query in queries:
        log.info(f"Searching: {query[:60]}...")
        results = brave_search(query, count=10)

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
    for i in range(0, len(all_results), 15):
        batch = all_results[i:i+15]
        log.info(f"Qualifying batch {i//15 + 1} ({len(batch)} results)...")
        leads = qualify_leads_with_claude(batch, known)
        all_leads.extend(leads)
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
        email_csv()

        high_score = [l for l in final_leads if l.get("lead_score", 0) >= 70]
        msg = (
            f"Vinnie+here.+BI+Lead+Hunter+found+{len(final_leads)}+new+leads+today+(flagship+product)."
            f"+{len(high_score)}+scored+above+70."
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

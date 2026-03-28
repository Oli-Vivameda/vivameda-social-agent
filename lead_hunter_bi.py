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
    # Alt data / data providers (Bucket A)
    "alternative data provider company",
    "alternative data vendor startup",
    "alt data company small team",
    "data provider structured datasets",
    "data vendor API company",
    "dataset provider company intelligence",
    "data product company analytics",
    "alternative data firm workforce",
    "data marketplace vendor small",
    "financial data provider boutique",

    # Market intelligence / data platforms
    "market intelligence data platform",
    "company intelligence data provider",
    "competitive intelligence data vendor",
    "business intelligence data product company",
    "data API provider company signals",

    # Research with structured data (Bucket B)
    "investment research firm data-driven",
    "research boutique structured data",
    "equity research data provider",
    "quantitative research firm data",
    "research platform alternative data",

    # AI data companies
    "AI data company structured datasets",
    "machine learning data provider",
    "AI training data company",
    "NLP data company structured",

    # Global expansion
    "alternative data provider Singapore",
    "data vendor company London UK",
    "alternative data company Hong Kong",
    "data platform provider Europe",
    "market intelligence company UAE Dubai",
    "data provider company Israel",
    "alternative data Asia Pacific",
    "data vendor company Australia",

    # Trigger / discovery
    "alternative data startup funded 2024 2025 2026",
    "data provider company launched 2025 2026",
    "dataset vendor seed funding",
    "alternative data conference exhibitor",
    "Neudata vendor directory alternative data",

    # Site-targeted
    "site:crunchbase.com alternative data provider",
    "site:crunchbase.com data vendor startup funded",
    "site:datarade.ai data provider workforce company",
    "site:alternativedata.org vendor directory",
]





SEGMENT_CONTEXT = """
====================================================================
VIVAMEDA B2B LEAD FINDER — STRUCTURED DATA BUYERS
====================================================================

Your task is to find high-quality B2B leads for a data infrastructure
company selling structured datasets.

====================================================================
STEP 1: PRIORITIZE THESE COMPANIES
====================================================================
Focus on companies that:
- Sell datasets, APIs, or data platforms
- Operate in alternative data, AI data, or market intelligence
- Serve investors, AI teams, or research

====================================================================
STEP 2: CLASSIFY INTO BUCKETS
====================================================================

Bucket A (Top priority):
- Data providers / alt-data companies
- Companies that sell structured data products
- Data marketplaces and distributors

Bucket B:
- Research firms with structured, repeatable data
- Investment research boutiques using external datasets
- Analytics firms with data products (not services)

Bucket C (optional strategic):
- Larger firms with clear dataset procurement
- Platform companies that integrate external data

====================================================================
STEP 3: HARD EXCLUSIONS — REJECT IMMEDIATELY
====================================================================
- Consulting company
- Investment bank
- Agency (marketing, PR, digital, creative)
- HR tech (recruiting tools, ATS, HRIS)
- SaaS without data product
- Survey / polling / panel firms
- System integrators
- Software development shops

====================================================================
STEP 4: SCORING SYSTEM
====================================================================
+3 — sells datasets or API
+2 — serves investor / AI / quant customers
+2 — has productized data offering
+1 — team size 5-200
+2 — clear data positioning on website

Maximum: 10 points
Reject if score < 4

====================================================================
STEP 5: OUTPUT RULES
====================================================================
Return 10-15 companies per run:
- At least 5 Bucket A (score 6+)
- Up to 5 Bucket B (score 4-5)
- Optional Bucket C only if exceptional

====================================================================
STEP 6: SEARCH STRATEGY
====================================================================
If too few results:
- Expand globally (Asia, Europe, Middle East, smaller markets)
- Use keywords: "alternative data", "data platform", "market intelligence", "data API"
- Try: "data vendor", "data product company", "dataset provider"

DO NOT relax exclusion rules when expanding search.

====================================================================
VIVAMEDA PRODUCT CONTEXT
====================================================================
You are sourcing buyers for Vivameda's workforce intelligence dataset:
- ~4.2M companies, ~60M+ company-year records
- Hiring velocity, growth, churn, seniority shifts, capability signals
- Longitudinal time series, survivorship-bias-free
- Delivery: Parquet, CSV, JSONL, Snowflake
- Price: $10K-$20K

====================================================================
TARGET CONTACTS
====================================================================
- Founder / CEO
- Head of Data / Chief Data Officer
- Head of Research
- VP Data Partnerships
These people can say YES quickly at small firms.
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

    prompt = f"""You are Vivameda's B2B lead finder for structured data buyers.

Find companies that SELL datasets, APIs, or data platforms. Companies in
alternative data, AI data, or market intelligence. Companies serving
investors, AI teams, or research.

SCORING:
+3 sells datasets/API
+2 investor/AI customers
+2 productized data
+1 team size 5-200
+2 clear data positioning
Reject if score < 4.

HARD EXCLUDE: consulting, investment banks, agencies, HR tech, SaaS without data product.

Bucket A (priority): data providers, alt-data companies. Score 6+.
Bucket B: research firms with structured data. Score 4-5.

Return 10-15 companies. At least 5 Bucket A.

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Return JSON:

"leads": array, each element:
{{{{
  "company": "Firm Name",
  "website": "domain.com",
  "segment": "Alt Data Provider / Data Platform / Research Boutique / AI Data Co",
  "why_buyer": "Sells workforce analytics API to hedge funds. 12-person team. Clear data product.",
  "evidence_url": "https://...",
  "buying_signals": "Data product company. Sells API. Serves quant funds. Clear data positioning.",
  "lead_score": 8,
  "recommended_contact_role": "Founder / Head of Data Partnerships",
  "company_size": "12",
  "est_data_budget": "$10K-$20K",
  "known_subscriptions": "Unknown",
  "notes": "Bucket A. Sells data to funds. Would integrate workforce signals into platform.",
  "product_fit": "Data Product Enrichment",
  "use_case": "Integrate workforce signals into existing data product/API",
  "is_hot": true,
  "tier": 1,
  "country": "US"
}}}}

"analysis": {{{{
  "top_3": ["Firm A", "Firm B", "Firm C"],
  "top_3_reasoning": "Why these 3 are strongest",
  "emerging_themes": "Patterns from today"
}}}}

Empty: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "Nothing qualified", "emerging_themes": "None"}}}}}}

RULES:
- 10-15 leads per batch. At least 5 Bucket A (score 6+).
- Score < 4 = reject.
- If too few results, expand globally but DO NOT relax exclusions.
- Every lead: company name, website, classification, score, 1-line reasoning.
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
                org_data["url"] = website
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
                "title": f"BI Lead: {lead.get('company', 'Unknown')} (Score {score})",
                "organization_id": org_id,
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

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
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
# Pipedrive CRM
PIPEDRIVE_API_TOKEN = os.environ.get("PIPEDRIVE_API_TOKEN", "")
PIPEDRIVE_DOMAIN = "vivameda"

MODEL = "claude-sonnet-4-20250514"

LEADS_CSV = "leads_bi/pipeline.csv"
LEADS_HISTORY = "leads_bi/.lead_history.json"
LEADS_PER_RUN = 15
MIN_SCORE = 60

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
    # Independent Research Firms / Boutiques
    "independent research firm investment boutique",
    "independent equity research boutique small team",
    "niche investment research provider",
    "sector specialist research firm boutique",
    "macro research boutique firm institutional",
    "independent research shop sell-side buy-side",
    "boutique research firm data-driven insights",
    "investment research startup platform",
    "research boutique alternative data analytics",
    "independent research provider workforce data",

    # Quant / Data-Driven Research
    "quantitative research firm small team",
    "data-driven investment research startup",
    "quantamental research boutique",
    "systematic research firm alternative data",
    "quant research boutique emerging manager",
    "algorithmic research firm small fund",

    # Alternative Data / Analytics Startups
    "alternative data startup analytics",
    "alt data analytics company small team",
    "data analytics startup investment signals",
    "workforce analytics startup company",
    "company intelligence data startup",
    "structured data startup analytics platform",
    "data enrichment startup B2B company",
    "predictive analytics startup company data",

    # Small AI/Data Companies
    "AI data company structured datasets small",
    "machine learning company data products",
    "AI startup company intelligence workforce",
    "data product startup analytics small team",
    "NLP company structured data insights",

    # Global Research Firms
    "investment research firm Singapore",
    "research boutique Hong Kong data",
    "independent research firm London small",
    "equity research boutique Europe data-driven",
    "research firm Israel data analytics",
    "investment research firm Australia boutique",

    # Selling Research / Insights
    "sells research reports institutional investors",
    "research platform subscription data",
    "analytics platform sells insights reports",
    "data-driven research reports subscription",

    # Trigger Events
    "research firm launched 2025 2026 data",
    "analytics startup raised seed 2025 2026",
    "data company new product launch 2026",
    "hired Head of Data research firm 2026",

    # Competitor Customers
    "Revelio Labs customer alternative",
    "Lightcast workforce data client user",
    "Thinknum alternative data buyer",
    "Burning Glass workforce client",
    "workforce intelligence provider comparison review",
]

SEGMENT_CONTEXT = """
====================================================================
VIVAMEDA GLOBAL DEAL-SOURCING ANALYST
READ EVERY WORD. FOLLOW EVERY RULE. NO EXCEPTIONS.
====================================================================

You are a global deal-sourcing analyst focused on identifying high-probability
buyers for a premium workforce intelligence dataset.

Your objective is NOT to find interesting companies.
Your objective is to find companies that can REALISTICALLY BUY a $10K-$20K
dataset within 14 days.

You must prioritize: speed to close, clear use case, small decisive teams.

====================================================================
DAILY OUTPUT REQUIREMENT
====================================================================
Minimum: 30 qualified leads per day
Geography: GLOBAL (no restriction)
Prioritize:
- US (primary)
- UK, Singapore, Hong Kong, Europe (secondary)
- Rest of world (opportunistic)

====================================================================
IDEAL CUSTOMER PROFILE (STRICT)
====================================================================

Company Type (PRIMARY TARGETS):
- Independent research firms / research boutiques
- Quant / data-driven research teams
- Niche investment research providers
- Alternative data / analytics startups
- Small AI/data companies using structured datasets

Company Size:
- 2-15 employees (ideal)
- Up to 25 max
- MUST appear small, lean, and decision-fast

Behavioral Signals (MANDATORY, at least 1 required):
Company MUST show at least one of:
- Sells research, reports, or insights
- Mentions: "data", "analytics", "quant", "research platform", "investment research"
- Has a product, dataset, or analytical offering
- Publishes insights or structured analysis
- Appears data-driven (not generic consulting)

====================================================================
HARD EXCLUSIONS (STRICT)
====================================================================
DO NOT include:
- Large companies (>50 employees)
- Banks, large hedge funds, institutions
- Generic consulting firms
- Marketing agencies
- Service-heavy businesses with no data angle
- Corporates without clear data/research usage
- If unclear whether they would buy data, EXCLUDE

====================================================================
YOUR DATASET (CONTEXT)
====================================================================
You are sourcing buyers for Vivameda's workforce intelligence dataset:
- ~4.2M companies
- ~60M+ company-year records
- Includes: company growth, hiring trends, workforce structure, capability/skill signals
- Longitudinal (time series), not snapshots
- Historical archive including failure signals (companies that no longer exist)
- Survivorship-bias-free for backtesting
- Delivery: Parquet, CSV, JSONL, Snowflake
- Price: $10K-$20K

====================================================================
USE CASE MAPPING (CRITICAL)
====================================================================
For EVERY lead, you MUST define: Why would THIS company buy THIS dataset?

Examples:
- Enhance investment research with workforce signals
- Build predictive hiring/growth indicators
- Enrich existing datasets with temporal workforce data
- Improve sector analysis with company structure signals
- Power internal models or reports with survivorship-bias-free data
- Backtest investment models against historical workforce data

If you cannot clearly define the use case, EXCLUDE the lead.

====================================================================
BUYING PROBABILITY CORE FILTER
====================================================================
Only include companies that:
- Can understand the dataset immediately (no explanation needed)
- Have a clear use case within 30 seconds
- Likely have budget or revenue model tied to data

If unclear, EXCLUDE.

====================================================================
SCORING (Buying Likelihood 1-10)
====================================================================
Based on: size, clarity of use case, data sophistication

8-10: Tier 1 - Contact immediately. High probability, fast close.
6-7:  Tier 2 - Good fit, secondary priority.
4-5:  Tier 3 - Low priority, only include if still relevant.
Below 4: DO NOT INCLUDE.

Minimum score to qualify: 6

====================================================================
PRIORITY TIERS
====================================================================
Tier 1: Contact immediately. Clear use case, small team, data-driven, can close fast.
Tier 2: Good fit, may need one conversation to qualify.
Tier 3: Possible fit, include only if pipeline needs volume.

====================================================================
QUALITY RULES (VERY IMPORTANT)
====================================================================
- No fluff
- No generic descriptions
- No "maybe" companies
- Every lead must feel: actionable, relevant, closeable
- If you are unsure about a company, EXCLUDE it
- If the use case is weak, EXCLUDE it
- Only output leads that feel like: "I could sell this within 1-2 conversations"

====================================================================
TARGET CONTACT ROLES
====================================================================
At small firms (2-25 people), these are the buyers:
- Founder / CEO
- Head of Research
- CTO / Chief Data Officer
- Head of Data / Analytics
- Portfolio Manager (if data-focused)
These people can say YES and wire money the same week.
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

    prompt = f"""You are Vivameda's global deal-sourcing analyst.

Today's mission: Find companies that can REALISTICALLY BUY a $10K-$20K
workforce intelligence dataset within 14 days.

Target: small research firms, quant boutiques, alt data startups, AI/data companies.
2-25 employees. Global but US-first. Must be data-driven. Must have clear use case.

NO banks. NO large funds. NO consultants. NO agencies. NO companies >50 people.

Every lead must feel like: "I could sell this in 1-2 conversations."

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Return JSON:

"leads": array, each element:
{{{{
  "company": "Firm Name",
  "website": "domain.com",
  "segment": "Research Boutique / Quant Firm / Alt Data Startup / AI Data Company",
  "why_buyer": "VERY SPECIFIC: what exactly makes them a match. Max 2 lines.",
  "evidence_url": "https://...",
  "buying_signals": "Sells research to hedge funds. Mentions analytics on website. 8-person team.",
  "lead_score": 8,
  "recommended_contact_role": "Founder, Head of Research",
  "company_size": "8",
  "est_data_budget": "$10K-$20K",
  "known_subscriptions": "Unknown",
  "notes": "Tier 1. Use case: enhance sector research with workforce growth signals. Global, US-based.",
  "product_fit": "Investment Research Enhancement",
  "use_case": "Enhance investment research with workforce signals",
  "is_hot": true,
  "tier": 1,
  "country": "US"
}}}}

"analysis": {{{{
  "top_3": ["Firm A", "Firm B", "Firm C"],
  "top_3_reasoning": "Why these 3 are the strongest: clearest use case, smallest team, fastest close",
  "emerging_themes": "Patterns from today"
}}}}

Empty: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "Nothing today", "emerging_themes": "None"}}}}}}

FINAL: Score 6+ only. Every lead must be closeable in 14 days. No fluff. No maybes. Quality over volume, but aim for 15+ per batch.
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
            org_data = {
                "name": lead.get("company", "Unknown Company"),
                "visible_to": "3",  # visible to whole company
            }
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

    queries = random.sample(SEARCH_QUERIES, min(10, len(SEARCH_QUERIES)))

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
        pushed = push_to_pipedrive(final_leads)
        log.info(f"Pushed {pushed}/{len(final_leads)} leads to Pipedrive")
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

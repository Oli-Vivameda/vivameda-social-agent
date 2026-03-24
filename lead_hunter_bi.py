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
MIN_SCORE = 50

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
    # Tier 1: Private Equity
    "private equity data-driven due diligence workforce",
    "private equity portfolio monitoring headcount",
    "PE operating partner data analytics",
    "private equity human capital analysis",
    "growth equity data team investment",
    "PE firm alternative data strategy",
    "private equity workforce benchmarking",
    "buyout fund data procurement",

    # Tier 1: Venture Capital
    "venture capital data-driven portfolio support",
    "VC data infrastructure research platform",
    "venture capital raised fund 2025 2026 data",
    "VC head of data OR data scientist hiring",
    "venture capital portfolio analytics workforce",
    "seed series funding data team building",

    # Tier 1: Hedge Funds / Quant
    "hedge fund alternative data workforce employment",
    "alternative data workforce intelligence people data",
    "Head of Alternative Data hedge fund",
    "quantitative research workforce employment signals",
    "Neudata OR Battlefin attendee exhibitor 2026",
    "systematic fund alternative data procurement",
    "quant fund company intelligence dataset",
    "alt data conference 2026 exhibitor sponsor",

    # Tier 1: Investment Research
    "investment research firm company intelligence",
    "equity research alternative data provider",
    "institutional investor data analytics platform",
    "alpha generation company data signals",

    # Tier 1: Corporate Strategy / Corp Dev / Market Intel
    "competitive intelligence workforce data hiring patterns",
    "market intelligence organizational analysis",
    "corporate strategy alternative data workforce",
    "M&A due diligence workforce headcount analysis",
    "corporate development data sourcing",
    "market intelligence platform company data",

    # Tier 1: AI / ML Companies
    "machine learning company data structured dataset",
    "AI training data company intelligence workforce",
    "entity resolution company data knowledge graph",
    "NLP LLM company intelligence structured data",
    "AI company building data products workforce",
    "feature engineering company employment data",

    # Tier 1: Data Product / Analytics Platform Companies
    "company intelligence platform analytics",
    "workforce analytics platform data enrichment",
    "org analytics organizational intelligence product",
    "talent intelligence platform dataset",
    "knowledge graph company data product",
    "entity resolution platform workforce",

    # Tier 2: Consulting
    "consulting firm workforce study organizational analysis",
    "strategy consulting alternative data workforce",
    "management consulting company benchmarking data",

    # Tier 2: Data Marketplaces / Brokers
    "data marketplace workforce employment company",
    "Snowflake Marketplace workforce employment headcount",
    "AWS Data Exchange workforce employment hiring",
    "Databricks marketplace company data",
    "data broker company intelligence workforce",
    "data reseller B2B company data",

    # Tier 2: Executive Search / Talent Intel
    "executive search firm data analytics workforce",
    "talent intelligence firm company data",

    # Trigger Events
    "raised fund 2026 data-driven investment",
    "Head of Data hired investment firm 2026",
    "hiring data procurement alternative data analyst 2026",
    "new data partnership announcement workforce",
    "data product launch company intelligence 2026",

    # Competitor Landscape (find their customers)
    "Revelio Labs client OR customer OR alternative",
    "Lightcast client OR user OR competing",
    "People Data Labs use case OR client",
    "Thinknum alternative data customer",
    "workforce intelligence provider comparison",
]


SEGMENT_CONTEXT = """
You are a lead intelligence agent for Vivameda, a premium B2B data business.

Your job is NOT to generate mass lead lists.
Your job is to identify a small number of highly relevant buyer accounts that are likely to purchase historical workforce intelligence, company structure intelligence, or capability intelligence datasets.

Optimize for: quality over quantity, signal over noise, relevance over volume, buyer intent over generic prospecting.

BUSINESS CONTEXT:
We sell premium, non-exclusive, historical company intelligence products. US-focused with global signals.
Strongest use cases: investment research, strategic market analysis, AI/modeling/data enrichment, company benchmarking, workforce/org structure/capability analysis.

THREE CORE PRODUCT LAYERS:
- Growth Intelligence: shows how companies grew, shrank, or stayed flat over time
- Market Intelligence: shows how companies are structured internally by role/function
- Capability Intelligence: shows what companies are actually capable of building, based on skills/capability distributions

Product: 250M+ professional records, 1.2TB+, 2010-2025. US SaaS subset: ~4,900 companies, ~1.2M observations. Delivery: Parquet, CSV, JSONL. Pricing: $5K-$500K/yr.

We are NOT selling cheap contact lists. We are NOT mass-market. We are a premium, selective, intelligence-driven business.

BUYER TIERS:

Tier 1 (highest priority):
- Private equity firms, growth equity firms
- Venture capital firms with data-driven portfolio support
- Alternative data buyers, investment research firms
- Corporate strategy teams, corporate development teams, market intelligence teams
- AI companies, ML/analytics/data infrastructure companies
- Companies building data products
- Firms working on entity resolution, knowledge graphs, analytics platforms, workforce analytics, org analytics

Tier 2:
- Consulting firms with strong strategy/analytics practices
- Executive search / talent intelligence firms
- Research firms, B2B intelligence vendors
- Data marketplaces / brokers / resellers
- Snowflake / Databricks ecosystem participants
- SaaS companies with strong expansion, M&A, or intelligence use cases

Tier 3 (only if very strong fit):
- Selected agencies or specialist operators with evidence of data buying behavior

GEOGRAPHIC FOCUS: United States primary. Non-US firms only if strong US market exposure.

STRONG BUYING SIGNALS:
- Mentions of alternative data, investment intelligence, market intelligence
- Mentions of workforce analytics, talent intelligence, company benchmarking
- Mentions of org design/org analytics, corporate development/M&A sourcing
- Mentions of AI model training, enrichment, structured datasets
- Mentions of entity resolution, knowledge graphs, company intelligence, data products
- Signs they buy, sell, or integrate datasets
- Hiring for strategy, corp dev, market intelligence, research, data sourcing
- Hiring for data engineering, ML, knowledge graph, entity resolution roles
- Recent fund launch, new product launch, expansion into AI/analytics
- Data partnership announcements, Snowflake/Databricks marketplace activity

NEGATIVE FILTERS (avoid or heavily down-rank):
- Generic agencies with no data buying behavior
- Tiny freelancers, spammy lead-gen shops
- Pure service businesses with no analytics angle
- Companies with no visible use case for structured company intelligence
- No likely budget owner or clear decision context
- Direct competitors: Revelio Labs, Lightcast, People Data Labs
- Pre-revenue startups with no funding
- Exclusively consumer-market focused
- <5 employees (unless funded AI startup)

SCORING (max 100, minimum 50):
Confidence 9-10 (Score 85-100): Clear buyer type, clear use case, strong signal, likely budget
Confidence 7-8 (Score 70-84): Good fit with at least one strong signal and plausible use case
Confidence 5-6 (Score 50-69): Possible fit but not enough evidence yet
Below 5: Do not include

+30: Confirmed external data buyer
+20: Dedicated data/research team (2+ people)
+15: Tier 1 buyer type
+10: Published/used workforce or hiring data
+10: Recently raised fund or received funding
+5: Hiring data/research roles
+5: Based in major financial center
-15: Company <10 employees
-10: Builds own workforce data internally
-25: Direct competitor
-20: No data capability or team

PRODUCT FIT LOGIC:
Growth Intelligence fits best when: buyer wants growth tracking, company benchmarking, macro/sector signals, investment screening, expansion/contraction monitoring
Market Intelligence fits best when: buyer wants org structure visibility, role distribution benchmarking, function-level comparison, strategic org analysis
Capability Intelligence fits best when: buyer wants deepest insight, AI/ML/modeling use cases, strategic capability mapping, skill/capability benchmarking, advanced research or data product integration

TARGET CONTACT ROLES: Partner, Principal, Investment Team, Operating Partner, Head of Portfolio Operations, VP Strategy, Director of Strategy, Head of Corp Dev, Director of Corporate Development, Head of Market Intelligence, Research Lead, Head of Data, Head of AI, CTO, VP Engineering, Head of Analytics, Product Lead for data/intelligence products
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

    prompt = f"""Run today's buyer research scan.
Focus on high-fit US buyers for premium company intelligence datasets.
Search for fresh public signals that indicate likely need for:
- investment intelligence
- workforce intelligence
- company benchmarking
- org structure analysis
- capability / skills intelligence
- AI/data enrichment

Be selective. Include only accounts with a real reason to buy.
Think like a human analyst screening targets for a boutique high-ticket sales process.
Never include a company unless there is a real, explainable reason it might buy.
Do not guess blindly. Separate evidence from inference. If speculative, say so.
Prefer fewer, stronger leads over many weak ones.

{SEGMENT_CONTEXT}

Below are search results. For each that represents a POTENTIAL BUYER, determine:

1. Company name and website
2. Region (US preferred)
3. Buyer tier (1/2/3) and specific type (e.g. "Tier 1: Private Equity")
4. Which product layer fits best (Growth / Market / Capability) and why
5. WHY they are a fit (2-4 sentences, specific and evidence-based)
6. What buying signal triggered inclusion
7. Suggested outreach angle (1-2 sentences)
8. Suggested target contact roles/titles
9. Confidence score (1-10) mapped to lead score (50-100)
10. Company size and estimated data budget

ALREADY KNOWN (skip these): {known_list}

SEARCH RESULTS:
{results_text}

Respond with a JSON object containing two keys:

"leads": a JSON array where each element is:
{{{{
  "company": "Company Name",
  "website": "domain.com",
  "segment": "Tier 1: Private Equity",
  "why_buyer": "Specific evidence-based reason with outreach angle",
  "evidence_url": "https://...",
  "buying_signals": "Signal 1. Signal 2. Signal 3.",
  "lead_score": 75,
  "recommended_contact_role": "Head of Data, Operating Partner",
  "company_size": "50-200",
  "est_data_budget": "$25K-$75K/yr",
  "known_subscriptions": "PitchBook, Bloomberg",
  "notes": "Product fit: Growth Intelligence. Confidence: 7/10.",
  "product_fit": "Growth"
}}}}

"analysis": {{{{
  "top_3": ["Company A", "Company B", "Company C"],
  "top_3_reasoning": "Why these are strongest and best product angle for each",
  "emerging_themes": "What patterns or themes emerged from today's signals"
}}}}

If NO results qualify, return: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "No strong leads today", "emerging_themes": "None"}}}}}}
Only include leads scoring 50+. Be strict. These are premium enterprise data buyers.
Do NOT include: marketing agencies, direct competitors (Revelio, Lightcast, PDL), companies with no data use case.
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

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
    # Research boutiques
    "boutique research firm investment data",
    "small research firm equity analysis",
    "independent research boutique small team",
    "niche research firm data-driven",
    "boutique research firm UK London",
    "boutique research firm Singapore Hong Kong",
    "boutique research firm UAE Dubai",
    "investment research firm founder 2-10 employees",
    "independent research provider small",

    # Alt data providers
    "alternative data provider small team",
    "small alternative data company",
    "niche data provider analytics startup",
    "alt data vendor boutique",
    "alternative data startup founded 2023 2024 2025",

    # Small AI labs
    "small AI lab research team",
    "AI research company small team data",
    "machine learning startup structured data",
    "AI company workforce data small",
    "NLP startup structured datasets",

    # Analytics consultancies
    "data analytics consultancy boutique",
    "analytics firm small team research",
    "data consultancy boutique firm",
    "workforce analytics small company",
    "people analytics startup small",

    # Trigger events
    "research firm hiring data analyst 2026",
    "data startup seed funding 2025 2026",
    "analytics company launched 2025 2026",

    # Competitor adjacent
    "Revelio Labs alternative competitor small",
    "Lightcast competitor workforce data",
    "workforce intelligence company small",
    "company data provider startup niche",
    "hiring data analytics provider small firm",

    # Site-targeted
    "site:crunchbase.com alternative data startup seed",
    "site:crunchbase.com research boutique data small",
    "site:crunchbase.com workforce analytics startup",
    "site:datarade.ai workforce company data provider",
    "site:angel.co data analytics research startup",
]




SEGMENT_CONTEXT = """
====================================================================
VIVAMEDA LEAD QUALIFICATION AGENT — READ EVERY WORD
====================================================================

You are a highly selective B2B lead qualification agent for Vivameda.

Your job is NOT to find "interesting companies."
Your job is to find companies that are highly likely to BUY external
structured workforce intelligence datasets in the near term.

Optimize for: revenue potential, speed to close, fit with product,
probability buyer already understands alternative data.

Be extremely strict. Low quality leads are WORSE than missing good ones.
Do not return generic "data companies," "AI companies," "consultancies,"
or "research companies" unless they clearly buy and use external structured datasets.

====================================================================
VIVAMEDA PRODUCT CONTEXT
====================================================================

Vivameda sells structured workforce intelligence. NOT a service, NOT consulting.

The product:
- Structured workforce intelligence, longitudinal company intelligence
- Company evolution signals over time
- Hiring velocity, growth, churn, seniority shifts, capability build-up
- Research and modeling inputs for investment, data products, advanced analytics
- ~4.2M companies, ~60M+ company-year records
- Survivorship-bias-free, includes companies that no longer exist
- Delivery: Parquet, CSV, JSONL, Snowflake
- Price: $10K-$20K

Best buyers: companies that immediately understand and use external datasets as core input.

====================================================================
IDEAL BUYER CATEGORIES
====================================================================

TIER 1 (pursue immediately):
- Alternative data firms
- Data vendors / data product companies
- Hedge funds / quant funds
- Institutional investors using differentiated datasets
- Research platforms that evaluate, buy, integrate, or distribute datasets
- AI labs/model builders ONLY if they clearly use external structured economic/workforce data

TIER 2 (good fit, worth outreach):
- Institutional equity research boutiques
- Investor research firms / forensic research firms
- Market intelligence firms relying on external datasets
- Benchmarking firms with proprietary databases
- Specialist intelligence providers where external company-level data strengthens product

TIER 3 (secondary, only with strong evidence):
- Firms producing recurring subscription insights depending on non-obvious external signals

====================================================================
HARD EXCLUSIONS — AUTOMATICALLY REJECT
====================================================================
Unless explicit proof they buy and productize external datasets:
- Data/AI consultancies, implementation partners, system integrators
- Dashboard/BI shops, data engineering agencies, software dev agencies
- Generic SaaS, cybersecurity, martech, branding, PR, digital marketing
- Primary market research agencies, survey/polling/focus group/panel firms
- Companies whose business is mainly custom client work or building with client data
- Macro/technical research firms relying mainly on price, sentiment, positioning

====================================================================
CRITICAL DECISION RULE
====================================================================
The main question is NOT: "Do they work with data?"
The main question IS: "Do they BUY external datasets as a core input to create value?"

If the answer is not clearly yes or very likely yes → REJECT.

Secondary question: "Is their use case close enough to workforce intelligence
that a commercial conversation makes sense NOW?"

If too far from company analysis, investment research, intelligence products,
benchmarking, or advanced modeling → REJECT.

====================================================================
10-DIMENSION EVALUATION (score each lead on ALL)
====================================================================
1. Buyer Type Fit — naturally buys external datasets?
2. Data Dependency — depends on external data for product/edge?
3. Productization — monetizes data/research/models, not pure services?
4. Use Case Relevance — workforce intelligence improves what they sell?
5. Commercial Readiness — can buy now, no long education cycle?
6. Speed to Close — weeks not months?
7. Budget Potential — meaningful deal size?
8. Sophistication — understands differentiated structured datasets?
9. Strategic Value — strong logo, distribution partner, repeat buyer?
10. Urgency of Pain — competes on information advantage/signal quality?

====================================================================
SCORING (0-10)
====================================================================
9-10: Excellent. Clear buyer. Pursue immediately.
7-8.9: Good fit. Realistic buyer. Worth outreach.
5-6.9: Weak/secondary. Only include with specific reason. Must explain why.
Below 5: REJECT. Do not return.

MINIMUM SCORE TO INCLUDE: 5.0

====================================================================
DO NOT BE FOOLED BY THESE WORDS
====================================================================
These words alone do NOT make a good lead:
AI, analytics, insights, intelligence, data-driven, machine learning,
research, dashboards, strategy, platform

Look through the words. Determine the ACTUAL business model.

====================================================================
RED FLAGS (usually means reject)
====================================================================
"we help clients use their data", "consulting services", "custom solutions",
"implementation", "survey programming", "fieldwork", "respondent recruitment",
"digital transformation", "market research agency", "data strategy",
"managed services", "software development", "business intelligence consulting"

====================================================================
POSITIVE SIGNALS
====================================================================
- Sells data products or research subscriptions
- Serves hedge funds, institutional investors, asset managers, quants
- Evaluates alternative datasets
- Distributes research to financial institutions
- Uses external information sources as core edge
- Benchmarks companies/markets using structured datasets
- Offers recurring intelligence products (not one-off projects)
- Competes on information advantage, proprietary signals, differentiated data

====================================================================
COMMERCIAL BIAS
====================================================================
Bias toward:
- Smaller specialized firms, boutiques
- Clear information-edge business models
- Buyers that understand value quickly
- Founder/president/CDO/Head of Research can say yes without procurement

Avoid:
- Giant enterprises (unless very clear immediate fit)
- Long education cycles
- "Nice to have" positioning

====================================================================
FINAL RULE
====================================================================
Quality > quantity. Better 5 excellent leads than 50 weak ones.
If unsure → REJECT. Be commercially ruthless.
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

    prompt = f"""You are Vivameda's lead qualification agent. Commercially ruthless. Quality only.

Find companies that BUY external structured datasets as a core input to create value.
NOT companies that "work with data." Companies that BUY DATASETS.

Tier 1: alt data firms, data vendors, hedge/quant funds, research platforms.
Tier 2: equity research boutiques, market intelligence, benchmarking firms.
Hard exclude: consultancies, agencies, SaaS tools, survey firms, large enterprises.

Minimum score: 7.0 out of 10. If unsure, REJECT.

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Return JSON:

"leads": array, each element:
{{{{
  "company": "Firm Name",
  "website": "domain.com",
  "segment": "Alt Data Vendor / Research Platform / Quant Fund / Data Product Co",
  "why_buyer": "Sells workforce analytics to hedge funds. 8-person team. Buys external datasets. Founder-led.",
  "evidence_url": "https://...",
  "buying_signals": "Data product company. Serves institutional investors. Simple website. Clear data dependency.",
  "lead_score": 8,
  "recommended_contact_role": "Founder / Head of Data",
  "company_size": "8",
  "est_data_budget": "$10K-$20K",
  "known_subscriptions": "Unknown",
  "notes": "Tier 1. Sells data products to funds. Would use workforce signals to enrich offering.",
  "product_fit": "Data Product Enrichment",
  "use_case": "Enrich existing data product with longitudinal workforce signals",
  "is_hot": true,
  "tier": 1,
  "country": "US"
}}}}

"analysis": {{{{
  "top_3": ["Firm A", "Firm B", "Firm C"],
  "top_3_reasoning": "Why these 3 are strongest buyers",
  "emerging_themes": "Patterns from today"
}}}}

Empty: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "Nothing qualified", "emerging_themes": "None"}}}}}}

RULES:
- Score 5+ included. 7+ are priority. 5-6 are worth a look.
- Quality over volume. 5 excellent > 50 weak.
- Every lead must pass: "Do they BUY external datasets as core input?"
- If unsure, REJECT. Be commercially ruthless.
- For rejected companies from search results, note: Company Name, Rejected, Reason (1 line).
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

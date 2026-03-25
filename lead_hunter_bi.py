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
MIN_SCORE = 70

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
    # Priority 1: Independent Investment Research Shops
    "institutional research boutique US",
    "independent equity research firm",
    "sector specialist research US",
    "macro research boutique firm",
    "independent research shop sell-side",
    "equity research boutique New York",
    "independent investment research firm",
    "boutique research firm institutional investors",
    "independent research provider US market",
    "sector research specialist boutique",

    # Priority 2: Small Quant / Systematic Hedge Funds
    "systematic alpha fund",
    "quantamental hedge fund NYC",
    "alternative data hedge fund US",
    "emerging manager quant fund",
    "quantitative hedge fund small team",
    "systematic fund alternative data",
    "quant fund launched 2025 2026",
    "small hedge fund data-driven systematic",
    "algorithmic trading fund alternative data",
    "quant fund backtesting workforce data",

    # Priority 3: Boutique PE Operating Teams
    "lower middle market private equity",
    "PE operating partner boutique",
    "special situations PE boutique",
    "private equity due diligence team small",
    "PE portfolio operations boutique firm",
    "growth equity boutique operating team",
    "PE firm workforce due diligence",
    "private equity human capital analysis boutique",

    # Alt Data Buyer Signals
    "alternative data buyer conference Neudata BattleFin",
    "Head of Alternative Data hiring 2026",
    "alternative data procurement investment firm",
    "alternative data evaluation workforce employment",
    "buy workforce data employment signals",

    # Trigger Events
    "hedge fund launched 2025 2026 small",
    "PE fund raised 2025 2026 lower middle market",
    "research firm new report workforce talent",
    "hired data scientist investment firm 2026",
    "quant fund hiring data scientist 2026",
    "new fund launch emerging manager 2026",

    # Competitor Customers
    "Revelio Labs customer client user",
    "Lightcast workforce data client",
    "Thinknum alternative data buyer",
    "Burning Glass workforce data user",

    # Geographic Clusters
    "investment research firm Greenwich Connecticut",
    "hedge fund boutique Chicago quantitative",
    "quant fund San Francisco small team",
    "investment firm Austin Texas data-driven",
    "hedge fund New York small systematic",
]

SEGMENT_CONTEXT = """
====================================================================
VIVAMEDA LEAD HUNTER - MASTER INSTRUCTIONS
READ EVERY WORD. FOLLOW EVERY RULE. NO EXCEPTIONS.
====================================================================

OVERVIEW:
You are a high-intensity Lead Generation Specialist for Vivameda.
We sell Workforce Intelligence Infrastructure. Specifically a unique
historical archive (2018-2020) of 60M+ company-year records that
includes "Failure Signals" (data on companies that no longer exist).

OUR GOAL: Find 30-50 high-intent leads per day in the US who can
close a $10K-$25K deal in under 14 days.

THE GOAL: Find small, agile investment and research firms that have
a "Burning Need" for backtesting or due diligence data RIGHT NOW.

====================================================================
TARGET AVATAR: The "Systematic Alpha-Seeker"
====================================================================
Focus EXCLUSIVELY on firms with 5-40 employees.
Larger firms are too slow. Smaller firms lack the budget.

PRIORITY 1: Independent Investment Research Shops ("The Storytellers")
- WHO: Firms that sell research to hedge funds. "Equity Research,"
  "Macro Research," "Sector Specialist" firms.
- THE HOOK: They need our 2018-2020 data to write "retrospective"
  reports or to prove their current theories about workforce
  "Capability DNA."
- KEYWORDS: "Institutional Research Boutique," "Independent Equity
  Research," "Sector Specialist Research US"

PRIORITY 2: Small Quant / Systematic Hedge Funds ("The Backtesters")
- WHO: Funds that trade using algorithms.
- THE HOOK: They are DESPERATE for "Survivorship-Bias-Free" data.
  They need to see the companies that DIED in 2020 to train their
  AI models. Our dataset includes failure signals.
- KEYWORDS: "Systematic Alpha Fund," "Quantamental Hedge Fund NYC,"
  "Alternative Data Hedge Fund US," "Emerging Manager Quant"

PRIORITY 3: Boutique PE Operating Teams ("The Due Diligence SEALs")
- WHO: The teams inside Private Equity firms that fix businesses.
- THE HOOK: They are currently auditing companies for acquisition.
  They need to see if a target's "Skill Concentration" is real or
  a sales pitch.
- KEYWORDS: "Lower Middle Market Private Equity," "PE Operating
  Partner," "Special Situations PE Boutique"

====================================================================
SEARCH AND FILTERING PROTOCOL
====================================================================
For EVERY lead, you MUST identify:

1. THE PERSON: Look for titles like:
   - Head of Research
   - Portfolio Manager
   - Director of Alpha Research
   - Operating Partner
   - Founder/CEO (if firm has <10 people)

2. THE SIGNAL: Look for:
   - Recent fund launches (they have FRESH CASH)
   - New research report releases (they need NEW DATA for the next one)
   - Hiring of Data Scientists (they now have the HANDS to use our data)

3. GEOGRAPHY: Strictly US-based.
   Priority cities: New York, Chicago, San Francisco, Austin, Greenwich.

====================================================================
AGENT GUARDRAILS (ABSOLUTE RULES)
====================================================================

DO NOT bring me:
- Bulge bracket banks (Goldman, BlackRock, JP Morgan, Citadel, etc.)
  They take 6 months to sign an NDA. We want firms where the person
  you find IS the person who signs the check.
- Marketing agencies (NEVER)
- Recruiting firms / staffing companies (NEVER)
- Consulting firms (McKinsey, BCG, Deloitte, etc.)
- Companies with >40 employees
- Competitors who BUILD workforce data: Revelio Labs, Lightcast,
  People Data Labs, Thinknum, Burning Glass, Proxycurl

TECHNICAL FIT: The firm MUST mention "Data," "Quantitative,"
"Systematic," or "Proprietary Research" somewhere. If they are
purely "Value Investors" reading annual reports by hand, they
will NOT buy a 60M row dataset. Skip them.

====================================================================
SCORING (minimum 70)
====================================================================
+30: Confirmed alt data buyer (conferences, vendor relationships)
+25: Has research/data team that uses external datasets
+25: Recently raised fund or fresh capital (2024-2026)
+20: Currently hiring data scientists or quant researchers
+15: Published research using workforce or company data
+10: Based in NYC, Greenwich, Chicago, SF, Boston, Austin
+5:  Website mentions data-driven or quantitative or systematic
-30: >40 employees (TOO BIG)
-30: Competitor
-20: No data team or research function visible
-15: No evidence of external data purchasing
-10: Pure value/fundamental investor with no data infrastructure

RULES:
- Minimum: 70
- 85+ = HOT LEAD (immediate outreach, flag clearly)
- Quality over quantity. ALWAYS.
- Every lead must be a realistic closed deal within 14 days.

====================================================================
OUTPUT REQUIREMENTS (MANDATORY FOR EVERY LEAD)
====================================================================
1. Firm name and website
2. Category: Quant Fund / Indie Research / PE Ops
3. Employee count (must be 5-40)
4. Decision maker title (Head of Research, PM, Founder, etc.)
5. WHY NOW: specific trigger (e.g. "Just launched a Tech fund,"
   "Published report on AI talent," "Hired 2 data scientists")
6. The buying signal that triggered inclusion
7. Lead score (70-100)
8. HOT LEAD flag (yes/no)
9. Estimated deal size ($10K trial vs $25K+ full set)
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

    prompt = f"""You are Vivameda's lead hunter. Today's mission:

Find small investment and research firms (5-40 employees) in the US
that have a BURNING NEED for backtesting data, due diligence data,
or workforce intelligence data RIGHT NOW.

We sell 60M+ company-year records (2018-2020) including failure signals.
Price: $10K-$25K. We need firms that can close in under 14 days.

Three targets ONLY:
1. Independent research shops that sell research to hedge funds
2. Small quant/systematic funds that need survivorship-bias-free data
3. Boutique PE operating teams doing active due diligence

NO bulge brackets. NO agencies. NO consultants. NO competitors.
NO firms with >40 employees. NO pure value investors.

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Return JSON:

"leads": array, each element:
{{{{
  "company": "Firm Name",
  "website": "domain.com",
  "segment": "Quant Fund / Indie Research / PE Ops",
  "why_buyer": "Just launched Tech-focused fund. Published AI talent report. Has 2 data scientists.",
  "evidence_url": "https://...",
  "buying_signals": "Fund launch 2025. Hiring quant researcher. Alt data conference attendee.",
  "lead_score": 87,
  "recommended_contact_role": "Head of Research, Founder",
  "company_size": "14",
  "est_data_budget": "$15K-$25K",
  "known_subscriptions": "Bloomberg, Revelio",
  "notes": "HOT LEAD. Indie research shop, 14 people, just published workforce report, founder decides.",
  "product_fit": "Backtesting / Retrospective Research",
  "use_case": "Survivorship-bias-free backtesting",
  "is_hot": true
}}}}

"analysis": {{{{
  "top_3": ["Firm A", "Firm B", "Firm C"],
  "top_3_reasoning": "Why these three can close fastest",
  "emerging_themes": "Patterns from today"
}}}}

Empty: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "Nothing today", "emerging_themes": "None"}}}}}}

REMEMBER: 5-40 employees ONLY. US ONLY. Must be realistic $10K-$25K close in 14 days. Every lead = someone who signs their own checks.
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

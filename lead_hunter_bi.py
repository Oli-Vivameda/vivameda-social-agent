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
    # Equity Research Boutiques
    "equity research boutique firm independent",
    "independent equity research firm small team",
    "boutique equity research institutional investors",
    "equity research firm initiating coverage",
    "independent research firm publishes reports",
    "equity research boutique small-cap coverage",
    "sell-side research boutique independent",
    "equity research firm alternative data alpha",

    # Sector-Specific Intelligence
    "healthcare research firm boutique equity",
    "technology research firm boutique sector",
    "energy sector research firm independent",
    "consumer retail research boutique firm",
    "financial services research firm boutique",
    "industrial sector research firm equity",
    "real estate research boutique firm",
    "SaaS technology research intelligence firm",

    # Alt Data Aggregators
    "alternative data aggregator firm small",
    "niche data provider hedge funds",
    "alternative data boutique firm",
    "data aggregator investment research",

    # Why Now triggers
    "equity research firm initiated coverage 2026",
    "research firm published sector outlook 2026",
    "research boutique hiring equity researcher 2026",
    "research firm expanding coverage new sector",
    "boutique research firm new analyst hire",

    # Named competitors / pattern anchors
    "firms like Singular Research equity boutique",
    "firms like Northcoast Research independent",
    "firms like Stonegate Capital research",
    "independent research firm similar to MoffettNathanson",

    # Geographic expansion
    "equity research boutique London UK independent",
    "investment research firm Europe boutique",
    "equity research firm Asia Pacific boutique",
    "independent research firm Canada boutique",

    # Site-targeted
    "site:linkedin.com equity research boutique independent",
    "site:crunchbase.com equity research firm funded",
    "site:linkedin.com sector intelligence boutique firm",
]











SEGMENT_CONTEXT = """
====================================================================
HIGH-VELOCITY LEAD GENERATION AGENT
====================================================================

Your ONLY goal: Find Research Boutiques (Equity Research, Investment
Research, and Market Intelligence Shops) with 10-100 employees.

STRATEGIC ANCHOR:
"If they don't SELL insights, they won't BUY our data fast."

====================================================================
PRIORITY TARGETS
====================================================================

1. EQUITY RESEARCH BOUTIQUES
   Firms like Singular, Northcoast, and Stonegate that publish reports
   for institutional investors. They need differentiated data to stand
   out against bulge-bracket research.

2. SECTOR-SPECIFIC INTELLIGENCE SHOPS
   Boutique firms focusing on one industry:
   - "Healthcare Data Research"
   - "Tech Infrastructure Analysts"
   - "Energy Sector Intelligence"
   - "Financial Services Research"
   - "Consumer/Retail Specialists"
   They live and die by unique data angles.

3. ALTERNATIVE DATA AGGREGATORS
   Small firms that package niche data for hedge funds.
   They already understand datasets and can integrate fast.

====================================================================
"WHY NOW" TRIGGERS (find at least one per lead)
====================================================================

- Firm just initiated coverage on new small-cap stocks
- Firm published a "Sector Outlook" or thematic report
- Firm is hiring a "Data Analyst" or "Equity Researcher"
- Firm expanded coverage to a new sector
- Firm mentioned "alternative data" or "differentiated research"
- Firm lost coverage from a larger bank (opportunity to fill gap)

====================================================================
THE ALPHA PITCH (context for qualification)
====================================================================

Our 60M+ company-year records provide "Alpha" because:
- Hiring velocity signals revenue growth 2-3 quarters ahead
- Skill-shift patterns reveal technology adoption before earnings
- Headcount trends across 4.2M companies = sector-level signals
- Survivorship-bias-free data = clean backtesting
- 1950-2020 historical depth = no one else has this

Entry product: Growth Intelligence
- 60M+ company-year records
- $15,000-$25,000/year license
- Pre-structured BI views = plug-and-play for analysts

====================================================================
TIER MAPPING
====================================================================

Growth Intelligence — headcount trends, hiring velocity, scaling patterns
→ Best for: "How fast is this company growing vs peers?"
→ Proposed when: firm does equity research, investment analysis

Capability Intelligence — 1.88B skill signals, technology adoption
→ Best for: "Is this company building AI/cloud capabilities?"
→ Proposed when: firm covers tech, healthcare innovation, digital transformation

Market Intelligence — role distribution, org structure changes
→ Best for: "How is this company restructuring post-merger?"
→ Proposed when: firm does M&A due diligence, competitive analysis

====================================================================
HARD EXCLUSIONS
====================================================================

- Over 200 employees
- Survey/panel/UX research firms
- Generic management consulting
- Software companies without research product
- Real-time/HFT data firms
- Consumer-facing companies
- Academic institutions

====================================================================
QUALITY STANDARD
====================================================================

- Every lead must SELL insights to institutional clients
- 10-100 employees ideal, up to 200 max
- Must identify a "Why Now" trigger
- Must map to Growth or Capability tier
- If they don't sell research, SKIP
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

    prompt = f"""You are a High-Velocity Lead Generation Agent for Vivameda.

ONLY goal: Find Research Boutiques that SELL insights. 10-100 employees.

"If they don't SELL insights, they won't BUY our data fast."

PRIORITY:
1. Equity research boutiques publishing reports for institutional investors
2. Sector-specific intelligence shops (healthcare, tech, energy, consumer)
3. Alternative data aggregators packaging niche data for hedge funds

For EVERY lead, find a "Why Now" trigger:
- Initiated new stock coverage
- Published sector outlook report
- Hiring data analyst or equity researcher
- Expanded to new sector
- Mentioned alternative data publicly

Map each lead to a tier:
- Growth Intelligence: scaling analysis, headcount trends
- Capability Intelligence: tech-edge analysis, skill signals

{SEGMENT_CONTEXT}

ALREADY KNOWN (skip): {known_list}

SEARCH RESULTS:
{results_text}

Return JSON:

"leads": array, each element:
{{{{
  "company": "Firm Name",
  "website": "domain.com",
  "segment": "Equity Research Boutique / Sector Intelligence / Alt Data Aggregator",
  "why_buyer": "Publishes equity research for hedge funds. 25 analysts. Recently initiated coverage on 15 small-cap tech stocks.",
  "evidence_url": "https://...",
  "buying_signals": "Published Q1 2026 Sector Outlook. Hiring equity researcher. Mentions alternative data.",
  "lead_score": 9,
  "recommended_contact_role": "Head of Research / Lead Analyst / Managing Partner",
  "company_size": "25",
  "est_data_budget": "$15K-$25K",
  "known_subscriptions": "Unknown",
  "notes": "Why Now: Published sector outlook Q1 2026. Hook: 60M records show hiring velocity signals 2-3 quarters before earnings. Proposed Tier: Growth Intelligence.",
  "product_fit": "Growth Intelligence",
  "use_case": "Add workforce alpha signals to equity research reports for subscribers",
  "is_hot": true,
  "tier": 1,
  "country": "US"
}}}}

"analysis": {{{{
  "top_3": ["Firm A", "Firm B", "Firm C"],
  "top_3_reasoning": "Strongest Why Now signals + sell insights + small team",
  "emerging_themes": "Patterns from today"
}}}}

Empty: {{{{"leads": [], "analysis": {{"top_3": [], "top_3_reasoning": "Nothing qualified", "emerging_themes": "None"}}}}}}

OUTPUT per lead:
1. Firm Name & Target Analysts
2. Recent Report Topic (the "Hook")
3. How our 60M records provide "Alpha" for that specific report
4. Proposed Tier: Growth or Capability

RULES:
- 10-15 leads per batch
- Every lead SELLS insights. No exceptions.
- Must have Why Now trigger
- 10-100 employees (200 max)
- If they don't sell research, SKIP
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

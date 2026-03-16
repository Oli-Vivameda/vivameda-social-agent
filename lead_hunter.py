#!/usr/bin/env python3
"""
Vivameda Lead Hunter Agent
Searches for potential buyers of the US Marketing Agency Dataset.
Uses Boolean search strings from the Buyer Intelligence Dossier.
Qualifies, scores, and outputs leads in the standard template format.
"""

import os
import sys
import json
import csv
import random
import logging
import time
from datetime import datetime

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
MODEL = "claude-sonnet-4-20250514"

LEADS_CSV = "leads/pipeline.csv"
LEADS_HISTORY = "leads/.lead_history.json"
LEADS_PER_RUN = 8
MIN_SCORE = 50

# Vinnie
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
# Search queries from the Buyer Intelligence Dossier
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    # Segment A: SaaS for agencies
    '"for agencies" SaaS software platform marketing',
    '"agency partner program" software sign up apply',
    '"white label" marketing software agencies',
    '"agency pricing" marketing software tool',
    '"built for agencies" marketing platform',
    '"agency management" software tool platform',
    'site:g2.com "for agencies" marketing software',
    '"client reporting" software agencies',
    '"SEO tool" "for agencies" OR "agency plan"',
    '"social media management" "for agencies" OR "agency pricing"',
    '"proposal software" agencies OR "agency plan"',
    '"project management" "for agencies" marketing',
    # Segment B: Service providers
    '"white label SEO" "for agencies" OR "agency partner"',
    '"white label PPC" OR "PPC reseller" agencies',
    '"content for agencies" OR "content fulfillment" white label',
    '"development partner for agencies" OR "agency outsourcing"',
    '"link building for agencies" OR "link building service"',
    # Segment C: PE/M&A
    '"private equity" "marketing agency" acquisition 2025 OR 2026',
    '"search fund" "digital agency" OR "marketing services"',
    '"agency holding company" OR "marketing services group"',
    # Segment D: Recruitment
    '"marketing agency recruitment" OR "agency staffing" OR "creative staffing"',
    # Segment E: Ecosystem
    '"agency conference" OR "agency summit" 2026 sponsor',
    # Trigger events
    '"head of sales" hired "marketing agencies" OR "agency" 2026',
    '"series A" OR "series B" raised "agency" software 2026',
    '"launched" "agency partner program" 2025 OR 2026',
    'SDR OR BDR hiring "agency" OR "agencies" software',
]

# Segment mapping for Claude
SEGMENT_CONTEXT = """
BUYER SEGMENTS for Vivameda US Marketing Agency Dataset ($1,950 / $3,900 / $6,900, max 25 licenses):

Segment A: SaaS Companies Selling to Marketing Agencies (60% of research time)
- Companies whose software serves marketing agencies
- Signals: "For Agencies" page, agency pricing tier, agency partner program, white-label capabilities
- Personas: Head of Sales, Founder/CEO (under 50 employees), Head of Partnerships

Segment B: Service Providers Selling to Agencies (20%)
- White-label SEO, PPC, web design, content, link building, dev outsourcing
- Typically 5-50 employees, founder personally selling
- Signals: "white label", "for agencies", "agency partner" on website

Segment C: Private Equity and M&A Teams (10%)
- PE firms, search funds, holding companies targeting agency sector
- Buy at $3,900-$6,900 tiers
- Signals: previous agency acquisitions, "marketing services" in investment focus

Segment D: Recruitment Platforms (5%)
- Staffing agencies focused on marketing/creative talent
- Need agency data to identify hiring companies

Segment E: Media, Events, Agency Ecosystem (5%)
- Directories, conference organizers, community platforms, awards
- Need agency data for their own products

SCORING (max 100, minimum 50 to qualify):
+30: Explicitly sells to marketing agencies
+20: Has "For Agencies" page or agency program
+10: Is SaaS (vs. services)
+10: Size 11-200 employees
+10: Recently raised funding or hiring sales
+5: US-based or selling into US
+5: Agency content published recently
+5: Decision-maker contact available
-30: Non-agency industry
-10: Fewer than 5 employees
-15: Only targets Fortune 500
-20: Already has agency data (e.g., Clutch, ZoomInfo)

DISQUALIFY if:
- Does not sell to agencies
- IS a marketing agency
- Is a data provider (Clutch, ZoomInfo, Apollo)
- Solo freelancer / 1-person
- Only operates outside US
- Enterprise 5,000+ employees
- Unrelated industry
"""


def load_lead_history() -> set:
    """Load previously found companies to avoid duplicates."""
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
    """Search Brave for results."""
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
    """Extract root domain from URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def qualify_leads_with_claude(search_results: list[dict], known_companies: set) -> list[dict]:
    """Use Claude to qualify and score leads from search results."""
    if not search_results:
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    results_text = ""
    for i, r in enumerate(search_results):
        results_text += f"\n{i+1}. {r['title']}\n   URL: {r['url']}\n   {r['description']}\n"

    known_list = ", ".join(list(known_companies)[:50]) if known_companies else "None yet"

    prompt = f"""You are a lead qualification specialist for Vivameda.

{SEGMENT_CONTEXT}

Below are search results. For each result that represents a POTENTIAL BUYER (not an agency itself, not a data provider, not irrelevant):

1. Identify the company
2. Determine the buyer segment (A/B/C/D/E)
3. Explain WHY they would buy (1-2 sentences, specific)
4. Note the evidence URL
5. List any buying signals detected
6. Score them using the scoring model
7. Recommend the contact role to target
8. Estimate company size if possible

ALREADY KNOWN (skip these): {known_list}

SEARCH RESULTS:
{results_text}

Respond ONLY with a JSON array. Each element:
{{
  "company": "Company Name",
  "website": "domain.com",
  "segment": "A",
  "why_buyer": "Specific reason they would buy",
  "evidence_url": "https://...",
  "buying_signals": "Signal 1. Signal 2.",
  "lead_score": 75,
  "contact_role": "Head of Sales",
  "company_size": "50-100",
  "notes": "Additional context"
}}

If NO results qualify, return an empty array: []
Only include leads scoring 50+. Be strict. Quality over quantity.
Do NOT include marketing agencies themselves, data providers, or irrelevant companies.
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
    """Append qualified leads to the CSV file."""
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
                lead.get("notes", ""),
                "New",
            ])


def main():
    if not ANTHROPIC_API_KEY or not BRAVE_API_KEY:
        log.error("Missing API keys")
        sys.exit(1)

    log.info("Lead Hunter Agent starting...")

    # Load history
    known = load_lead_history()
    log.info(f"Known companies: {len(known)}")

    # Pick 4 random search queries
    queries = random.sample(SEARCH_QUERIES, min(4, len(SEARCH_QUERIES)))

    # Collect all search results
    all_results = []
    seen_domains = set()

    for query in queries:
        log.info(f"Searching: {query[:60]}...")
        results = brave_search(query, count=10)

        for r in results:
            domain = extract_domain(r["url"])
            # Skip known companies and duplicates
            if domain in seen_domains or domain in known:
                continue
            # Skip obvious non-targets
            skip_domains = [
                "linkedin.com", "facebook.com", "twitter.com", "youtube.com",
                "reddit.com", "g2.com", "capterra.com", "producthunt.com",
                "crunchbase.com", "pitchbook.com", "wikipedia.org", "github.com",
                "medium.com", "forbes.com", "techcrunch.com", "bloomberg.com",
            ]
            if any(domain.endswith(sd) for sd in skip_domains):
                continue

            seen_domains.add(domain)
            all_results.append(r)

        time.sleep(1)

    log.info(f"Found {len(all_results)} unique candidate URLs")

    if not all_results:
        log.info("No new candidates found today")
        vinnie_alert("Vinnie+here.+Lead+Hunter+found+nothing+new+today.+All+quiet.")
        return

    # Qualify with Claude (process in batches of 15)
    all_leads = []
    for i in range(0, len(all_results), 15):
        batch = all_results[i:i+15]
        log.info(f"Qualifying batch {i//15 + 1} ({len(batch)} results)...")
        leads = qualify_leads_with_claude(batch, known)
        all_leads.extend(leads)
        time.sleep(2)

    # Deduplicate and filter
    final_leads = []
    for lead in all_leads:
        domain = lead.get("website", "").lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        if domain and domain not in known and lead.get("lead_score", 0) >= MIN_SCORE:
            final_leads.append(lead)
            known.add(domain)

    # Cap at LEADS_PER_RUN
    final_leads = final_leads[:LEADS_PER_RUN]

    if final_leads:
        append_to_csv(final_leads)
        save_lead_history(known)

        high_score = [l for l in final_leads if l.get("lead_score", 0) >= 70]
        msg = (
            f"Vinnie+here.+Lead+Hunter+found+{len(final_leads)}+new+leads+today."
            f"+{len(high_score)}+scored+above+70."
            f"+Top+lead:+{final_leads[0].get('company', 'Unknown').replace(' ', '+')}"
            f"+({final_leads[0].get('lead_score', '?')}+points).+Check+the+pipeline."
        )
        vinnie_alert(msg)

        log.info(f"\nFound {len(final_leads)} qualified leads:")
        for lead in final_leads:
            log.info(f"  {lead['company']} ({lead.get('segment', '?')}) - Score: {lead.get('lead_score', '?')}")
    else:
        log.info("No qualified leads found today")
        vinnie_alert("Vinnie+here.+Lead+Hunter+ran+but+no+qualified+leads+today.+Standards+are+high.")

    print(f"\nDone! {len(final_leads)} leads added to pipeline.")


if __name__ == "__main__":
    main()

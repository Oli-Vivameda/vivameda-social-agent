import subprocess, sys

# Auto-install dependencies
for pkg in ['requests', 'beautifulsoup4', 'lxml']:
    try:
        __import__(pkg.replace('beautifulsoup4', 'bs4'))
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])

import re
import csv
import time
import logging
import os
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from urllib.parse import urlparse, urljoin
from threading import Lock

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

OUTPUT_FILE = "enriched_output.csv"
PARTIAL_FILE = "enriched_partial.csv"
LOG_FILE = "enrichment_log.txt"

SAVE_EVERY = 50
MAX_WORKERS = 10
PAGE_TIMEOUT = 10
DOMAIN_TIMEOUT = 30
INTER_PAGE_DELAY = 1.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

CONTACT_PATHS = ["/contact", "/contact-us", "/get-in-touch", "/reach-us", "/connect", "/contactus"]
ABOUT_PATHS   = ["/about", "/about-us", "/who-we-are", "/our-story", "/company", "/aboutus"]
TEAM_PATHS    = ["/team", "/our-team", "/people", "/leadership", "/staff", "/meet-the-team"]

GENERIC_EMAIL_PREFIXES = {
    "info", "contact", "hello", "admin", "support", "office", "sales",
    "team", "mail", "noreply", "no-reply", "webmaster", "postmaster",
    "enquiries", "enquiry", "help", "service", "billing", "marketing",
    "press", "media", "hr", "jobs", "careers", "feedback", "general",
}

SERVICE_KEYWORDS = [
    "SEO", "PPC", "social media marketing", "content marketing", "branding",
    "web design", "web development", "creative", "public relations",
    "video production", "email marketing", "performance marketing",
    "growth marketing", "lead generation", "outbound", "recruiting",
    "staffing", "consulting", "events", "direct mail", "affiliate marketing",
    "programmatic", "media buying", "full service", "white label",
    "martech", "adtech", "mobile marketing", "photography", "advertising",
    "communications", "data analytics", "market research", "ABM",
]

VERTICAL_KEYWORDS = [
    "healthcare", "dental", "automotive", "real estate", "financial services",
    "ecommerce", "retail", "SaaS", "technology", "hospitality", "travel",
    "education", "sports", "entertainment", "cannabis", "fashion", "beauty",
    "B2B", "construction", "legal", "franchise", "manufacturing", "nonprofit",
    "agriculture",
]

ALL_KEYWORDS = SERVICE_KEYWORDS + VERTICAL_KEYWORDS

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+1[\s\-.]?)?"
    r"(?:\(?\d{3}\)?[\s\-.])"
    r"\d{3}[\s\-.]"
    r"\d{4}"
    r"(?!\d)"
)

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV DETECTION
# ---------------------------------------------------------------------------

COLUMN_ALIASES = {
    "first_name":     ["first name", "firstname", "first"],
    "last_name":      ["last name", "lastname", "last"],
    "full_name":      ["full name", "fullname", "name", "contact name"],
    "company":        ["company", "company name", "organization", "account name"],
    "domain":         ["company domain", "domain", "website", "url", "company url", "company website"],
    "linkedin_url":   ["linkedin url", "linkedin", "linkedin profile", "profile url"],
    "title":          ["title", "job title", "position", "role"],
    "industry":       ["industry", "sector"],
    "location":       ["location", "city", "country", "region"],
    "company_size":   ["company size", "employee count", "employees", "headcount"],
}

def normalize_header(h):
    return h.strip().lower().replace("\ufeff", "").replace("-", " ").replace("_", " ")

def detect_columns(headers):
    norm = {normalize_header(h): h for h in headers}
    mapping = {}
    for key, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                mapping[key] = norm[alias]
                break
    return mapping

def detect_delimiter(filepath):
    with open(filepath, "rb") as f:
        sample = f.read(4096).decode("utf-8-sig", errors="replace")
    comma_count = sample.count(",")
    semi_count  = sample.count(";")
    return ";" if semi_count > comma_count else ","

def read_csv(filepath):
    delimiter = detect_delimiter(filepath)
    encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(filepath, newline="", encoding=enc) as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)
                headers = reader.fieldnames or []
            return rows, headers, delimiter
        except Exception:
            continue
    raise RuntimeError(f"Could not read {filepath} with any known encoding.")

def write_csv(filepath, rows, fieldnames, delimiter=","):
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

# ---------------------------------------------------------------------------
# DOMAIN RESOLUTION
# ---------------------------------------------------------------------------

def clean_domain(raw):
    """Normalise a raw domain/URL string to a bare hostname."""
    raw = raw.strip()
    if not raw:
        return None
    if not raw.startswith("http"):
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
        host = parsed.netloc or parsed.path
        host = host.split("/")[0].split("?")[0].lstrip("www.").strip()
        return host.lower() if host else None
    except Exception:
        return None

def company_name_to_domain(name):
    if not name:
        return None
    name = name.lower().strip()
    name = re.sub(r"\b(inc|llc|ltd|corp|co|company|group|agency|studio|media|digital|solutions|services|consulting|associates|partners|international|global)\b", "", name)
    name = re.sub(r"[^a-z0-9]", "", name)
    return f"{name}.com" if name else None

def domain_reachable(domain, timeout=5):
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            r = requests.head(url, timeout=timeout, allow_redirects=True,
                              headers={"User-Agent": USER_AGENTS[0]})
            if r.status_code < 500:
                return scheme, domain
        except Exception:
            pass
    return None, None

# ---------------------------------------------------------------------------
# HTTP HELPERS
# ---------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENTS[0]})

def fetch_page(url, timeout=PAGE_TIMEOUT):
    """Fetch a URL and return (final_url, soup) or (None, None)."""
    try:
        r = _session.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENTS[0],
                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                     "Accept-Language": "en-US,en;q=0.5"},
        )
        if r.status_code == 404:
            return None, None
        if r.status_code >= 400:
            return None, None

        # Encoding detection
        for enc in ("utf-8", "latin-1"):
            try:
                content = r.content.decode(enc)
                break
            except Exception:
                content = None
        if content is None:
            return None, None

        soup = BeautifulSoup(content, "lxml")
        return r.url, soup
    except requests.exceptions.SSLError as e:
        logger.warning("SSL error %s: %s", url, e)
        return None, None
    except requests.exceptions.Timeout as e:
        logger.warning("Timeout %s: %s", url, e)
        return None, None
    except requests.exceptions.ConnectionError as e:
        logger.warning("Connection error %s: %s", url, e)
        return None, None
    except Exception as e:
        logger.warning("Fetch error %s: %s", url, e)
        return None, None

def try_paths(base_url, paths):
    """Try a list of paths under base_url; return (final_url, soup) for first hit."""
    for path in paths:
        url = base_url.rstrip("/") + path
        final_url, soup = fetch_page(url)
        if soup:
            return final_url, soup
        time.sleep(INTER_PAGE_DELAY)
    return None, None

# ---------------------------------------------------------------------------
# EXTRACTION HELPERS
# ---------------------------------------------------------------------------

def extract_emails(soup, domain):
    """Return deduplicated list of personal emails matching domain."""
    candidates = set()

    # regex over raw html text
    raw = soup.get_text(separator=" ")
    for m in EMAIL_RE.findall(raw):
        candidates.add(m.lower())

    # mailto links
    for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)):
        href = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
        if EMAIL_RE.match(href):
            candidates.add(href)

    # filter
    result = []
    for email in candidates:
        prefix = email.split("@")[0]
        email_domain = email.split("@")[1] if "@" in email else ""
        if prefix in GENERIC_EMAIL_PREFIXES:
            continue
        if domain and domain not in email_domain and not email_domain.endswith("." + domain):
            continue
        result.append(email)

    return sorted(set(result))


def extract_phones(soup):
    """Return deduplicated list of phone numbers."""
    candidates = set()
    raw = soup.get_text(separator=" ")
    for m in PHONE_RE.findall(raw):
        candidates.add(m.strip())

    # tel: links
    for a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
        href = a["href"].replace("tel:", "").strip()
        digits = re.sub(r"\D", "", href)
        if 10 <= len(digits) <= 11:
            candidates.add(href)

    # filter obvious fax labels
    fax_re = re.compile(r"fax", re.I)
    result = []
    for phone in candidates:
        # walk back through soup text to see if nearby text says "fax"
        nearby_text = ""
        for text_node in soup.find_all(string=re.compile(re.escape(phone.strip()), re.I)):
            parent = text_node.parent
            nearby_text += (parent.get_text() if parent else "") + " "
        if fax_re.search(nearby_text[:200]):
            continue
        result.append(phone)

    return sorted(set(result))


def extract_description(soups):
    """Extract a short company description from a list of soups in priority order."""
    for soup in soups:
        if not soup:
            continue
        # 1. meta description
        tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if tag and tag.get("content", "").strip():
            return _clean_desc(tag["content"])
        # 2. og:description
        tag = soup.find("meta", attrs={"property": re.compile(r"^og:description$", re.I)})
        if tag and tag.get("content", "").strip():
            return _clean_desc(tag["content"])

    # 3. First <p> on about page, then homepage
    for soup in soups:
        if not soup:
            continue
        for p in soup.find_all("p"):
            text = p.get_text(separator=" ").strip()
            if len(text) > 40:
                return _clean_desc(text)

    return ""


def _clean_desc(text):
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


def extract_keywords(soups, company_name="", domain=""):
    """Extract matching service/vertical keywords."""
    corpus = []
    for soup in soups:
        if not soup:
            continue
        title = soup.find("title")
        if title:
            corpus.append(title.get_text())
        for tag in soup.find_all("meta", attrs={"name": re.compile(r"^(description|keywords)$", re.I)}):
            corpus.append(tag.get("content", ""))
        for tag in soup.find_all(["h1", "h2"]):
            corpus.append(tag.get_text())
        # first 500 words of body
        body_text = soup.get_text(separator=" ")
        words = body_text.split()
        corpus.append(" ".join(words[:500]))

    text = " ".join(corpus).lower()

    found = []
    for kw in ALL_KEYWORDS:
        if kw.lower() in text:
            found.append(kw)

    # Fallback: company name / domain
    if not found:
        fallback_text = f"{company_name} {domain}".lower()
        for kw in ALL_KEYWORDS:
            if kw.lower() in fallback_text:
                found.append(kw)

    # Default
    if not found:
        found = ["digital marketing"]

    return list(dict.fromkeys(found))  # dedupe, preserve order

# ---------------------------------------------------------------------------
# CORE ENRICHMENT PER COMPANY
# ---------------------------------------------------------------------------

def enrich_company(row, col_map):
    """
    Process a single CSV row. Returns a dict of enrichment fields.
    """
    result = {
        "Website_Emails": "",
        "Website_Phones": "",
        "Website_Description": "",
        "Keywords": "",
        "Enrichment_Source": "",
        "Enrichment_Status": "failed",
    }

    company_name = row.get(col_map.get("company", ""), "").strip()
    raw_domain   = (
        row.get(col_map.get("domain", ""), "")
        or row.get(col_map.get("linkedin_url", ""), "")
    ).strip()

    # --- Resolve domain ---
    domain = clean_domain(raw_domain) if raw_domain else None
    if not domain:
        domain = company_name_to_domain(company_name)

    if not domain:
        result["Enrichment_Status"] = "failed"
        result["Keywords"] = ", ".join(extract_keywords([], company_name, ""))
        return result

    scheme, reachable_domain = domain_reachable(domain)
    if not scheme:
        logger.warning("Domain unreachable: %s", domain)
        result["Enrichment_Status"] = "failed"
        result["Keywords"] = ", ".join(extract_keywords([], company_name, domain))
        return result

    base_url = f"{scheme}://{reachable_domain}"

    # --- Scrape pages ---
    soups = []
    sources = []
    all_emails = []
    all_phones = []

    start = time.time()

    def _fetch_and_collect(label, url_or_paths, is_paths=False):
        nonlocal soups, sources, all_emails, all_phones
        if time.time() - start > DOMAIN_TIMEOUT:
            return
        if is_paths:
            final_url, soup = try_paths(base_url, url_or_paths)
        else:
            final_url, soup = fetch_page(url_or_paths)
            time.sleep(INTER_PAGE_DELAY)

        if soup:
            soups.append(soup)
            sources.append(label)
            all_emails.extend(extract_emails(soup, reachable_domain))
            all_phones.extend(extract_phones(soup))

    # 1. Homepage
    _fetch_and_collect("homepage", base_url)
    # 2. Contact
    _fetch_and_collect("contact", CONTACT_PATHS, is_paths=True)
    # 3. About
    _fetch_and_collect("about", ABOUT_PATHS, is_paths=True)
    # 4. Team
    _fetch_and_collect("team", TEAM_PATHS, is_paths=True)

    # --- Deduplicate ---
    unique_emails = list(dict.fromkeys(all_emails))
    unique_phones = list(dict.fromkeys(all_phones))

    # --- Description ---
    description = extract_description(soups)

    # --- Keywords ---
    keywords = extract_keywords(soups, company_name, reachable_domain)

    # --- Status ---
    if sources:
        status = "success" if len(sources) >= 2 else "partial"
    else:
        status = "failed"

    result["Website_Emails"]     = ", ".join(unique_emails)
    result["Website_Phones"]     = ", ".join(unique_phones)
    result["Website_Description"] = description
    result["Keywords"]           = ", ".join(keywords)
    result["Enrichment_Source"]  = ", ".join(sources)
    result["Enrichment_Status"]  = status

    return result

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

NEW_COLUMNS = [
    "Website_Emails",
    "Website_Phones",
    "Website_Description",
    "Keywords",
    "Enrichment_Source",
    "Enrichment_Status",
]

write_lock = Lock()
results_lock = Lock()


def main():
    parser = argparse.ArgumentParser(description="Lead enrichment via web scraping")
    parser.add_argument("input_csv", help="Path to input CSV file")
    args = parser.parse_args()

    if not os.path.isfile(args.input_csv):
        print(f"ERROR: File not found: {args.input_csv}")
        sys.exit(1)

    setup_logging()

    print("=" * 60)
    print("  LEAD ENRICHMENT AGENT")
    print("=" * 60)
    print(f"  Input  : {args.input_csv}")
    print(f"  Output : {OUTPUT_FILE}")
    print(f"  Log    : {LOG_FILE}")
    print(f"  Workers: {MAX_WORKERS}")
    print()
    print("  Scrapes: homepage, contact, about, team pages")
    print("  Extracts: emails, phones, description, keywords")
    print()
    print("  Press Ctrl+C to cancel (partial results saved)")
    print("=" * 60)
    print()

    # Read input
    try:
        rows, original_headers, delimiter = read_csv(args.input_csv)
    except Exception as e:
        print(f"ERROR reading CSV: {e}")
        sys.exit(1)

    col_map = detect_columns(original_headers)
    total = len(rows)

    print(f"Loaded {total} rows.")
    print(f"Detected columns: { {k: v for k, v in col_map.items()} }")
    print()

    if total == 0:
        print("No rows to process. Exiting.")
        sys.exit(0)

    est_seconds = total * 15 / MAX_WORKERS
    est_min = int(est_seconds / 60)
    print(f"Estimated time: ~{est_min} minutes (varies by site speed)")
    print()

    # Build output fieldnames
    out_headers = list(original_headers)
    for col in NEW_COLUMNS:
        if col not in out_headers:
            out_headers.append(col)

    enriched_rows = [None] * total
    counters = {"processed": 0, "success": 0, "partial": 0, "failed": 0,
                "emails": 0, "phones": 0}

    def process_row(idx_row):
        idx, row = idx_row
        try:
            enrichment = enrich_company(row, col_map)
        except Exception as e:
            logger.error("Unexpected error row %d: %s", idx, e)
            enrichment = {c: "" for c in NEW_COLUMNS}
            enrichment["Enrichment_Status"] = "failed"

        out_row = dict(row)
        out_row.update(enrichment)
        return idx, out_row, enrichment

    start_time = time.time()

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_row, (i, row)): i
                       for i, row in enumerate(rows)}

            for future in as_completed(futures):
                try:
                    idx, out_row, enrichment = future.result(timeout=DOMAIN_TIMEOUT + 5)
                except Exception as e:
                    idx = futures[future]
                    logger.error("Future error row %d: %s", idx, e)
                    out_row = dict(rows[idx])
                    for col in NEW_COLUMNS:
                        out_row[col] = ""
                    out_row["Enrichment_Status"] = "failed"
                    enrichment = out_row

                enriched_rows[idx] = out_row

                with results_lock:
                    counters["processed"] += 1
                    status = enrichment.get("Enrichment_Status", "failed")
                    if status in counters:
                        counters[status] += 1
                    n_emails = len([e for e in enrichment.get("Website_Emails", "").split(",") if e.strip()])
                    n_phones = len([p for p in enrichment.get("Website_Phones", "").split(",") if p.strip()])
                    counters["emails"] += n_emails
                    counters["phones"] += n_phones
                    proc = counters["processed"]

                # Progress output
                company_col = col_map.get("company", "")
                domain_col  = col_map.get("domain", "")
                company_display = (
                    out_row.get(domain_col, "")
                    or out_row.get(company_col, "")
                    or f"row {idx+1}"
                ).strip()[:40]

                print(
                    f"  [{proc:>{len(str(total))}}/{total}] "
                    f"{company_display:<40} "
                    f"status={enrichment.get('Enrichment_Status', '?'):<8} "
                    f"emails={n_emails} phones={n_phones} "
                    f"kw={len([k for k in enrichment.get('Keywords','').split(',') if k.strip()])}"
                )

                # Periodic save
                if proc % SAVE_EVERY == 0 or proc == total:
                    saved = [r for r in enriched_rows if r is not None]
                    write_csv(PARTIAL_FILE, saved, out_headers)
                    print(f"    --> Progress saved ({len(saved)} rows) to {PARTIAL_FILE}")

    except KeyboardInterrupt:
        print("\nInterrupted! Saving partial results...")
        saved = [r for r in enriched_rows if r is not None]
        write_csv(PARTIAL_FILE, saved, out_headers)
        print(f"Partial results saved to {PARTIAL_FILE} ({len(saved)} rows)")
        sys.exit(0)

    # Fill any None slots (shouldn't happen, but safety net)
    for i, row in enumerate(enriched_rows):
        if row is None:
            out_row = dict(rows[i])
            for col in NEW_COLUMNS:
                out_row[col] = ""
            out_row["Enrichment_Status"] = "failed"
            enriched_rows[i] = out_row

    # Write final output
    write_csv(OUTPUT_FILE, enriched_rows, out_headers)

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print()
    print("=" * 60)
    print("  ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"  Total processed : {counters['processed']}")
    print(f"  Success         : {counters['success']}")
    print(f"  Partial         : {counters['partial']}")
    print(f"  Failed          : {counters['failed']}")
    success_rate = (counters['success'] + counters['partial']) / max(total, 1) * 100
    print(f"  Success rate    : {success_rate:.1f}%")
    print(f"  Emails found    : {counters['emails']}")
    print(f"  Phones found    : {counters['phones']}")
    print(f"  Time elapsed    : {minutes}m {seconds}s")
    print()
    print(f"  Output saved to : {OUTPUT_FILE}")
    print(f"  Error log       : {LOG_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()

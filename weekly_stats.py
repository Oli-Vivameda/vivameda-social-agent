#!/usr/bin/env python3
"""
Vivameda Weekly Engagement Stats
Pulls stats from LinkedIn and X, compiles a weekly report.
Vinnie sends a WhatsApp summary every Friday afternoon.
Also emails the full report to oli@vivameda.com.
"""

import os
import sys
import json
import csv
import logging
import hashlib
import hmac
import time
import base64
import urllib.parse
import uuid
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    log.error("Missing httpx. Run: pip install httpx")
    sys.exit(1)

# Credentials
X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "")
X_BIZ_API_KEY = os.environ.get("X_BIZ_API_KEY", "")
X_BIZ_API_SECRET = os.environ.get("X_BIZ_API_SECRET", "")
X_BIZ_ACCESS_TOKEN = os.environ.get("X_BIZ_ACCESS_TOKEN", "")
X_BIZ_ACCESS_SECRET = os.environ.get("X_BIZ_ACCESS_SECRET", "")
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_ACCESS_TOKEN_LISA = os.environ.get("LINKEDIN_ACCESS_TOKEN_LISA", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

VINNIE_PHONE = "4915129005414"
VINNIE_APIKEY = "5944134"

STATS_DIR = "stats"
STATS_FILE = os.path.join(STATS_DIR, "weekly_stats.csv")


def vinnie_alert(msg: str):
    try:
        httpx.get(
            f"https://api.callmebot.com/whatsapp.php?phone={VINNIE_PHONE}&text={msg}&apikey={VINNIE_APIKEY}",
            timeout=10,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# X OAuth 1.0a
# ---------------------------------------------------------------------------
def _x_oauth_header(method, url, api_key, api_secret, access_token, access_secret, extra_params=None):
    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    all_params = {**oauth_params}
    if extra_params:
        all_params.update(extra_params)
    params_string = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    base_string = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(params_string, safe='')}"
    signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
    signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    oauth_params["oauth_signature"] = base64.b64encode(signature).decode()
    return "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )


def get_x_stats(api_key, api_secret, access_token, access_secret, label="Personal"):
    """Get X account metrics: followers, following, tweet count."""
    url = "https://api.x.com/2/users/me"
    params = {"user.fields": "public_metrics"}
    auth = _x_oauth_header("GET", url, api_key, api_secret, access_token, access_secret, params)

    try:
        resp = httpx.get(url, params=params, headers={"Authorization": auth}, timeout=15)
        if resp.status_code != 200:
            log.warning(f"X {label} stats failed ({resp.status_code})")
            return None
        data = resp.json().get("data", {})
        metrics = data.get("public_metrics", {})
        return {
            "account": label,
            "username": data.get("username", ""),
            "followers": metrics.get("followers_count", 0),
            "following": metrics.get("following_count", 0),
            "tweets": metrics.get("tweet_count", 0),
        }
    except Exception as e:
        log.warning(f"X {label} stats error: {e}")
        return None


def get_linkedin_stats(access_token, label="Oli"):
    """Get basic LinkedIn profile info. Full analytics requires Marketing API."""
    try:
        resp = httpx.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "account": f"LinkedIn {label}",
                "name": data.get("name", ""),
                "status": "Token active",
            }
        elif resp.status_code == 401:
            return {
                "account": f"LinkedIn {label}",
                "name": "",
                "status": "TOKEN EXPIRED",
            }
        else:
            return {
                "account": f"LinkedIn {label}",
                "name": "",
                "status": f"Error {resp.status_code}",
            }
    except Exception as e:
        return {"account": f"LinkedIn {label}", "name": "", "status": str(e)}


def count_leads():
    """Count total leads in pipeline."""
    csv_path = "leads/pipeline.csv"
    if not os.path.exists(csv_path):
        return 0, 0
    total = 0
    this_week = 0
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                if row.get("Date", "") >= week_ago:
                    this_week += 1
    except Exception:
        pass
    return total, this_week


def count_blog_posts():
    """Count blog output files this week."""
    # Blog posts are in the other repo, so we just check the commit messages
    # For now, return placeholder
    return "Check vivameda.com"


def save_stats(stats: dict):
    """Append weekly stats to CSV."""
    os.makedirs(STATS_DIR, exist_ok=True)
    file_exists = os.path.exists(STATS_FILE)

    with open(STATS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Date", "X Personal Followers", "X Personal Following",
                "X Business Followers", "X Business Following",
                "LinkedIn Oli Status", "LinkedIn Lisa Status",
                "Total Leads", "Leads This Week",
            ])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d"),
            stats.get("x_personal", {}).get("followers", ""),
            stats.get("x_personal", {}).get("following", ""),
            stats.get("x_business", {}).get("followers", ""),
            stats.get("x_business", {}).get("following", ""),
            stats.get("li_oli", {}).get("status", ""),
            stats.get("li_lisa", {}).get("status", ""),
            stats.get("total_leads", 0),
            stats.get("week_leads", 0),
        ])


def email_report(report: str):
    """Email the weekly report."""
    if not GMAIL_APP_PASSWORD:
        log.warning("No Gmail password, skipping email")
        return

    msg = MIMEMultipart()
    msg["From"] = "nold.oliver@gmail.com"
    msg["To"] = "oli@vivameda.com"
    msg["Subject"] = f"Vivameda Weekly Report - {datetime.now().strftime('%Y-%m-%d')}"
    msg.attach(MIMEText(report, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login("nold.oliver@gmail.com", GMAIL_APP_PASSWORD)
            server.sendmail("nold.oliver@gmail.com", "oli@vivameda.com", msg.as_string())
        log.info("Weekly report emailed")
    except Exception as e:
        log.warning(f"Email failed: {e}")


def main():
    log.info("Collecting weekly engagement stats...")

    stats = {}

    # X Personal
    if X_API_KEY and X_ACCESS_TOKEN:
        stats["x_personal"] = get_x_stats(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, "Personal @olinold")
        log.info(f"X Personal: {stats['x_personal']}")
    else:
        stats["x_personal"] = {}

    # X Business
    if X_BIZ_API_KEY and X_BIZ_ACCESS_TOKEN:
        stats["x_business"] = get_x_stats(X_BIZ_API_KEY, X_BIZ_API_SECRET, X_BIZ_ACCESS_TOKEN, X_BIZ_ACCESS_SECRET, "Business @vivameda_data")
        log.info(f"X Business: {stats['x_business']}")
    else:
        stats["x_business"] = {}

    # LinkedIn
    if LINKEDIN_ACCESS_TOKEN:
        stats["li_oli"] = get_linkedin_stats(LINKEDIN_ACCESS_TOKEN, "Oli")
        log.info(f"LinkedIn Oli: {stats['li_oli']}")
    else:
        stats["li_oli"] = {}

    if LINKEDIN_ACCESS_TOKEN_LISA:
        stats["li_lisa"] = get_linkedin_stats(LINKEDIN_ACCESS_TOKEN_LISA, "Lisa")
        log.info(f"LinkedIn Lisa: {stats['li_lisa']}")
    else:
        stats["li_lisa"] = {}

    # Leads
    total_leads, week_leads = count_leads()
    stats["total_leads"] = total_leads
    stats["week_leads"] = week_leads
    log.info(f"Leads: {total_leads} total, {week_leads} this week")

    # Save to CSV
    save_stats(stats)

    # Build report
    xp = stats.get("x_personal", {})
    xb = stats.get("x_business", {})
    report = f"""VIVAMEDA WEEKLY REPORT - {datetime.now().strftime('%Y-%m-%d')}
{'='*50}

X ACCOUNTS:
  @olinold: {xp.get('followers', '?')} followers, {xp.get('following', '?')} following
  @vivameda_data: {xb.get('followers', '?')} followers, {xb.get('following', '?')} following

LINKEDIN:
  Oli: {stats.get('li_oli', {}).get('status', '?')}
  Lisa: {stats.get('li_lisa', {}).get('status', '?')}

LEAD PIPELINE:
  Total leads found: {total_leads}
  New leads this week: {week_leads}

{'='*50}
- Vinnie
"""

    print(report)

    # Email report
    email_report(report)

    # Vinnie WhatsApp summary
    vinnie_msg = (
        f"Vinnie+here.+WEEKLY+REPORT:"
        f"+@olinold+{xp.get('followers', '?')}+followers."
        f"+@vivameda_data+{xb.get('followers', '?')}+followers."
        f"+{week_leads}+new+leads+this+week+({total_leads}+total)."
        f"+Full+report+sent+to+your+email+boss."
    )
    vinnie_alert(vinnie_msg)

    log.info("Weekly report complete!")


if __name__ == "__main__":
    main()

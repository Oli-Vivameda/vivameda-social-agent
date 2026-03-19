#!/usr/bin/env python3
"""
Vivameda Weekly Stats Agent
Runs every Friday at 16:00 Cyprus time
Tracks: X followers, LinkedIn token health, lead pipelines (agency + BI), emails report, Vinnie WhatsApp summary
"""

import os
import csv
import json
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from urllib.parse import quote

# ============================================================
# CONFIG
# ============================================================
GMAIL_USER = "nold.oliver@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
REPORT_TO = "oli@vivameda.com"

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

VINNIE_PHONE = "35799909204"
VINNIE_API_KEY = "wdXW78gEZEFt"

STATS_DIR = "stats"
STATS_CSV = os.path.join(STATS_DIR, "weekly_stats.csv")
AGENCY_PIPELINE = "leads/pipeline.csv"
AGENCY_HISTORY = "leads/.lead_history.json"
BI_PIPELINE = "leads_bi/pipeline.csv"
BI_HISTORY = "leads_bi/.lead_history.json"


def send_vinnie(message):
    try:
        url = f"https://api.textmebot.com/send.php?recipient={VINNIE_PHONE}&text={quote(message)}&apikey={VINNIE_API_KEY}"
        resp = requests.get(url, timeout=15)
        print(f"Vinnie: {resp.status_code}")
    except Exception as e:
        print(f"Vinnie error: {e}")


def get_x_stats(api_key, api_secret, access_token, access_secret, account_name):
    try:
        from requests_oauthlib import OAuth1
        auth = OAuth1(api_key, api_secret, access_token, access_secret)
        resp = requests.get(
            "https://api.twitter.com/2/users/me?user.fields=public_metrics",
            auth=auth, timeout=15
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            metrics = data.get("public_metrics", {})
            return {
                "account": account_name,
                "username": data.get("username", account_name),
                "followers": metrics.get("followers_count", 0),
                "following": metrics.get("following_count", 0),
                "tweets": metrics.get("tweet_count", 0),
            }
        else:
            print(f"X API error for {account_name}: {resp.status_code}")
            return {"account": account_name, "followers": "?", "following": "?", "tweets": "?"}
    except Exception as e:
        print(f"X stats error for {account_name}: {e}")
        return {"account": account_name, "followers": "?", "following": "?", "tweets": "?"}


def check_linkedin_token(token, name):
    try:
        resp = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        if resp.status_code == 200:
            return {"name": name, "status": "VALID", "detail": "Token working"}
        elif resp.status_code == 401:
            return {"name": name, "status": "EXPIRED", "detail": "Token expired or revoked"}
        else:
            return {"name": name, "status": "UNKNOWN", "detail": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"name": name, "status": "ERROR", "detail": str(e)}


def count_leads(pipeline_path, history_path, product_name):
    total = 0
    this_week = 0
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        if os.path.exists(pipeline_path):
            with open(pipeline_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total += 1
                    date_str = row.get("Date", "")
                    if date_str >= week_ago:
                        this_week += 1
    except Exception as e:
        print(f"Error reading {product_name} pipeline: {e}")
    if total == 0:
        try:
            if os.path.exists(history_path):
                with open(history_path, "r") as f:
                    history = json.load(f)
                    if isinstance(history, (list, dict)):
                        total = len(history)
        except Exception as e:
            print(f"Error reading {product_name} history: {e}")
    return {"product": product_name, "total": total, "this_week": this_week}


def save_stats(date_str, personal_x, biz_x, li_oli, li_lisa, agency_leads, bi_leads):
    os.makedirs(STATS_DIR, exist_ok=True)
    file_exists = os.path.exists(STATS_CSV)
    with open(STATS_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Date",
                "X_Personal_Followers", "X_Personal_Following",
                "X_Biz_Followers", "X_Biz_Following",
                "LI_Oli_Status", "LI_Lisa_Status",
                "Agency_Leads_Total", "Agency_Leads_Week",
                "BI_Leads_Total", "BI_Leads_Week"
            ])
        writer.writerow([
            date_str,
            personal_x.get("followers", "?"), personal_x.get("following", "?"),
            biz_x.get("followers", "?"), biz_x.get("following", "?"),
            li_oli.get("status", "?"), li_lisa.get("status", "?"),
            agency_leads.get("total", 0), agency_leads.get("this_week", 0),
            bi_leads.get("total", 0), bi_leads.get("this_week", 0)
        ])
    print(f"Stats saved to {STATS_CSV}")


def send_email_report(date_str, personal_x, biz_x, li_oli, li_lisa, agency_leads, bi_leads):
    subject = f"Vivameda Weekly Stats - {date_str}"
    body = f"""VIVAMEDA WEEKLY STATS REPORT
{date_str}
{'=' * 50}

X ACCOUNTS
----------
@olinold (Personal)
  Followers: {personal_x.get('followers', '?')}
  Following: {personal_x.get('following', '?')}
  Tweets: {personal_x.get('tweets', '?')}

@vivameda_data (Business)
  Followers: {biz_x.get('followers', '?')}
  Following: {biz_x.get('following', '?')}
  Tweets: {biz_x.get('tweets', '?')}

LINKEDIN TOKEN HEALTH
---------------------
Oli: {li_oli.get('status', '?')} - {li_oli.get('detail', '')}
Lisa: {li_lisa.get('status', '?')} - {li_lisa.get('detail', '')}

LEAD PIPELINES
--------------
Agency Dataset (usagencydata.com)
  Total leads: {agency_leads.get('total', 0)}
  This week: {agency_leads.get('this_week', 0)}

BI Workforce Intelligence Dataset (Flagship)
  Total leads: {bi_leads.get('total', 0)}
  This week: {bi_leads.get('this_week', 0)}

Combined: {agency_leads.get('total', 0) + bi_leads.get('total', 0)} total leads across both pipelines
{'=' * 50}
Generated by Vivameda Automation System
"""
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = REPORT_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"Email sent to {REPORT_TO}")
    except Exception as e:
        print(f"Email error: {e}")


def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"Running weekly stats for {date_str}")

    print("\nFetching X stats...")
    personal_x = get_x_stats(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, "olinold")
    biz_x = get_x_stats(X_BIZ_API_KEY, X_BIZ_API_SECRET, X_BIZ_ACCESS_TOKEN, X_BIZ_ACCESS_SECRET, "vivameda_data")
    print(f"  @olinold: {personal_x.get('followers', '?')} followers")
    print(f"  @vivameda_data: {biz_x.get('followers', '?')} followers")

    print("\nChecking LinkedIn tokens...")
    li_oli = check_linkedin_token(LINKEDIN_ACCESS_TOKEN, "Oli")
    li_lisa = check_linkedin_token(LINKEDIN_ACCESS_TOKEN_LISA, "Lisa")
    print(f"  Oli: {li_oli.get('status', '?')}")
    print(f"  Lisa: {li_lisa.get('status', '?')}")

    print("\nCounting leads...")
    agency_leads = count_leads(AGENCY_PIPELINE, AGENCY_HISTORY, "Agency Dataset")
    bi_leads = count_leads(BI_PIPELINE, BI_HISTORY, "BI Workforce Intelligence")
    print(f"  Agency: {agency_leads.get('total', 0)} total, {agency_leads.get('this_week', 0)} this week")
    print(f"  BI: {bi_leads.get('total', 0)} total, {bi_leads.get('this_week', 0)} this week")

    print("\nSaving stats...")
    save_stats(date_str, personal_x, biz_x, li_oli, li_lisa, agency_leads, bi_leads)

    print("\nSending email report...")
    send_email_report(date_str, personal_x, biz_x, li_oli, li_lisa, agency_leads, bi_leads)

    print("\nSending Vinnie summary...")
    agency_total = agency_leads.get("total", 0)
    agency_week = agency_leads.get("this_week", 0)
    bi_total = bi_leads.get("total", 0)
    bi_week = bi_leads.get("this_week", 0)
    combined_total = agency_total + bi_total

    vinnie_msg = (
        f"WEEKLY STATS {date_str}\n"
        f"X: @olinold {personal_x.get('followers', '?')} | @vivameda_data {biz_x.get('followers', '?')}\n"
        f"LI: Oli={li_oli.get('status', '?')} Lisa={li_lisa.get('status', '?')}\n"
        f"Agency leads: {agency_total} total (+{agency_week} this week)\n"
        f"BI leads: {bi_total} total (+{bi_week} this week)\n"
        f"Combined: {combined_total} leads in pipeline"
    )
    send_vinnie(vinnie_msg)

    print("\nDone!")


if __name__ == "__main__":
    main()

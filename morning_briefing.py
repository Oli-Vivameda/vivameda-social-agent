#!/usr/bin/env python3
"""
Vivameda Morning Briefing Agent
Runs once at 09:15 CY, after all morning agents have finished.
Sends one consolidated Vinnie message with the full picture.
"""

import os
import json
import csv
import requests
from datetime import datetime, timedelta
from urllib.parse import quote

VINNIE_PHONE = "35799909204"
VINNIE_API_KEY = "wdXW78gEZEFt"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

log = print


def send_vinnie(message):
    try:
        url = f"https://api.textmebot.com/send.php?recipient={VINNIE_PHONE}&apikey={VINNIE_API_KEY}&text={quote(message)}"
        requests.get(url, timeout=15)
    except Exception as e:
        log(f"Vinnie error: {e}")


def count_todays_leads(csv_path):
    """Count leads added today in a pipeline CSV."""
    today = datetime.now().strftime("%Y-%m-%d")
    count = 0
    if not os.path.exists(csv_path):
        return 0
    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Date", "").startswith(today):
                    count += 1
    except Exception:
        pass
    return count


def count_total_leads(csv_path):
    """Count total leads in a pipeline CSV."""
    if not os.path.exists(csv_path):
        return 0
    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            return sum(1 for _ in reader)
    except Exception:
        return 0


def check_recent_workflow(name):
    """Check if a workflow file exists (proxy for enabled)."""
    path = f".github/workflows/{name}"
    return os.path.exists(path)


def main():
    today = datetime.now().strftime("%A, %B %d")
    log(f"Morning Briefing: {today}")

    # BI leads
    bi_today = count_todays_leads("leads_bi/pipeline.csv")
    bi_total = count_total_leads("leads_bi/pipeline.csv")

    # Agency leads (passive)
    agency_total = count_total_leads("leads/pipeline.csv")

    # Build briefing
    lines = []
    lines.append(f"MORNING BRIEFING - {today}")
    lines.append("")

    # Leads
    if bi_today > 0:
        lines.append(f"BI Leads: {bi_today} new today ({bi_total} total pipeline)")
    else:
        lines.append(f"BI Leads: No new leads yet (morning run may still be processing). {bi_total} total in pipeline.")

    if agency_total > 0:
        lines.append(f"Agency Pipeline: {agency_total} leads (passive, hunter disabled)")

    lines.append("")

    # Agent status
    lines.append("Agents: Social posting, X engagement, Smartlead monitor, blog (M/W/F), BI hunter x2 all scheduled.")

    # Day of week specials
    dow = datetime.now().strftime("%A")
    if dow == "Monday":
        lines.append("Token monitor runs today.")
    if dow == "Friday":
        lines.append("Weekly stats report runs at 16:00.")
    if dow in ("Monday", "Wednesday", "Friday"):
        lines.append("Blog post publishing today.")

    lines.append("")
    lines.append("Go close deals.")

    briefing = "\n".join(lines)
    log(briefing)

    send_vinnie(briefing.replace("\n", " | "))

    log("\nBriefing sent.")


if __name__ == "__main__":
    main()

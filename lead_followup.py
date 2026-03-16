#!/usr/bin/env python3
"""
Vivameda Lead Follow-Up Reminder Agent
Runs daily at 08:45 Cyprus time (between lead hunters and social agent)
Checks both pipeline CSVs for leads that need attention:
  - New leads (Status empty or "new") untouched for 3+ days
  - High-score leads (80+) untouched for 2+ days (priority)
  - Any lead untouched for 7+ days (urgent)
Sends Vinnie WhatsApp summary + optional email digest
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

VINNIE_PHONE = "4915129005414"
VINNIE_API_KEY = "5944134"

AGENCY_PIPELINE = "leads/pipeline.csv"
BI_PIPELINE = "leads_bi/pipeline.csv"

# Thresholds (days)
PRIORITY_DAYS = 2      # High-score leads (80+) get flagged after 2 days
STANDARD_DAYS = 3      # Normal leads get flagged after 3 days
URGENT_DAYS = 7        # Any lead untouched for 7+ days = urgent

# Statuses that mean "not yet contacted"
OPEN_STATUSES = {"", "new", "found", "qualified"}

log = print


def send_vinnie(message):
    try:
        url = f"https://api.callmebot.com/whatsapp.php?phone={VINNIE_PHONE}&text={quote(message)}&apikey={VINNIE_API_KEY}"
        resp = requests.get(url, timeout=15)
        log(f"Vinnie: {resp.status_code}")
    except Exception as e:
        log(f"Vinnie error: {e}")


def send_email(subject, body):
    if not GMAIL_APP_PASSWORD:
        log("No Gmail password, skipping email")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = REPORT_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        log(f"Email sent to {REPORT_TO}")
    except Exception as e:
        log(f"Email error: {e}")


def scan_pipeline(csv_path, product_name):
    """Scan a pipeline CSV and return leads needing follow-up."""
    urgent = []
    priority = []
    standard = []
    total = 0
    open_count = 0

    if not os.path.exists(csv_path):
        log(f"  {product_name}: No pipeline file found at {csv_path}")
        return {"urgent": urgent, "priority": priority, "standard": standard,
                "total": total, "open": open_count, "product": product_name}

    today = datetime.now().date()

    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                status = row.get("Status", "").strip().lower()

                if status not in OPEN_STATUSES:
                    continue

                open_count += 1
                date_str = row.get("Date", "").strip()
                if not date_str:
                    continue

                try:
                    lead_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        lead_date = datetime.strptime(date_str, "%m/%d/%Y").date()
                    except ValueError:
                        continue

                age_days = (today - lead_date).days
                score_str = row.get("Lead Score", "0").strip()
                try:
                    score = int(float(score_str))
                except (ValueError, TypeError):
                    score = 0

                company = row.get("Company", "Unknown").strip()
                segment = row.get("Segment", "?").strip()

                lead_info = {
                    "company": company,
                    "segment": segment,
                    "score": score,
                    "age_days": age_days,
                    "date": date_str,
                    "product": product_name,
                }

                if age_days >= URGENT_DAYS:
                    urgent.append(lead_info)
                elif score >= 80 and age_days >= PRIORITY_DAYS:
                    priority.append(lead_info)
                elif age_days >= STANDARD_DAYS:
                    standard.append(lead_info)

    except Exception as e:
        log(f"  Error reading {csv_path}: {e}")

    # Sort each bucket by score descending
    urgent.sort(key=lambda x: x["score"], reverse=True)
    priority.sort(key=lambda x: x["score"], reverse=True)
    standard.sort(key=lambda x: x["score"], reverse=True)

    return {
        "urgent": urgent, "priority": priority, "standard": standard,
        "total": total, "open": open_count, "product": product_name,
    }


def format_lead(lead):
    return f"{lead['company']} (Seg {lead['segment']}, Score {lead['score']}, {lead['age_days']}d old)"


def build_vinnie_message(agency, bi):
    """Build a concise WhatsApp message."""
    all_urgent = agency["urgent"] + bi["urgent"]
    all_priority = agency["priority"] + bi["priority"]
    all_standard = agency["standard"] + bi["standard"]

    total_flagged = len(all_urgent) + len(all_priority) + len(all_standard)

    if total_flagged == 0:
        return None  # No message needed

    lines = [f"LEAD FOLLOW-UP ({datetime.now().strftime('%Y-%m-%d')})"]

    if all_urgent:
        lines.append(f"\nURGENT ({len(all_urgent)} leads, 7+ days):")
        for lead in all_urgent[:5]:  # Cap at 5 for WhatsApp readability
            lines.append(f"  {lead['product'][:3]}: {lead['company']} (score {lead['score']}, {lead['age_days']}d)")
        if len(all_urgent) > 5:
            lines.append(f"  +{len(all_urgent) - 5} more")

    if all_priority:
        lines.append(f"\nPRIORITY ({len(all_priority)} high-score leads, 2+ days):")
        for lead in all_priority[:5]:
            lines.append(f"  {lead['product'][:3]}: {lead['company']} (score {lead['score']}, {lead['age_days']}d)")
        if len(all_priority) > 5:
            lines.append(f"  +{len(all_priority) - 5} more")

    if all_standard:
        lines.append(f"\nSTALE ({len(all_standard)} leads, 3+ days):")
        for lead in all_standard[:3]:
            lines.append(f"  {lead['product'][:3]}: {lead['company']} (score {lead['score']}, {lead['age_days']}d)")
        if len(all_standard) > 3:
            lines.append(f"  +{len(all_standard) - 3} more")

    lines.append(f"\nTotal: {total_flagged} leads need action")
    return "\n".join(lines)


def build_email_body(agency, bi):
    """Build a detailed email report."""
    today = datetime.now().strftime("%Y-%m-%d")
    sections = [
        f"VIVAMEDA LEAD FOLLOW-UP REPORT",
        f"{today}",
        "=" * 50,
        "",
        f"Pipeline Summary:",
        f"  Agency: {agency['total']} total, {agency['open']} open/uncontacted",
        f"  BI:     {bi['total']} total, {bi['open']} open/uncontacted",
        "",
    ]

    all_urgent = agency["urgent"] + bi["urgent"]
    all_priority = agency["priority"] + bi["priority"]
    all_standard = agency["standard"] + bi["standard"]
    total_flagged = len(all_urgent) + len(all_priority) + len(all_standard)

    if total_flagged == 0:
        sections.append("All leads are either recently added or already contacted. Nothing to flag.")
        return "\n".join(sections)

    if all_urgent:
        sections.append(f"URGENT - {len(all_urgent)} leads untouched 7+ days")
        sections.append("-" * 40)
        for lead in all_urgent:
            sections.append(f"  [{lead['product']}] {lead['company']}")
            sections.append(f"    Segment: {lead['segment']} | Score: {lead['score']} | Added: {lead['date']} ({lead['age_days']} days ago)")
        sections.append("")

    if all_priority:
        sections.append(f"PRIORITY - {len(all_priority)} high-score leads (80+) untouched 2+ days")
        sections.append("-" * 40)
        for lead in all_priority:
            sections.append(f"  [{lead['product']}] {lead['company']}")
            sections.append(f"    Segment: {lead['segment']} | Score: {lead['score']} | Added: {lead['date']} ({lead['age_days']} days ago)")
        sections.append("")

    if all_standard:
        sections.append(f"STALE - {len(all_standard)} leads untouched 3+ days")
        sections.append("-" * 40)
        for lead in all_standard:
            sections.append(f"  [{lead['product']}] {lead['company']}")
            sections.append(f"    Segment: {lead['segment']} | Score: {lead['score']} | Added: {lead['date']} ({lead['age_days']} days ago)")
        sections.append("")

    sections.append("=" * 50)
    sections.append(f"Total leads needing action: {total_flagged}")
    sections.append("")
    sections.append("Tip: Update the Status column in pipeline.csv to 'contacted', 'replied', 'meeting', 'closed', or 'disqualified' to clear these reminders.")
    sections.append("")
    sections.append("Generated by Vivameda Automation System")

    return "\n".join(sections)


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    log(f"Running lead follow-up check for {today}")

    log("\nScanning Agency pipeline...")
    agency = scan_pipeline(AGENCY_PIPELINE, "Agency")
    log(f"  Total: {agency['total']}, Open: {agency['open']}")
    log(f"  Urgent: {len(agency['urgent'])}, Priority: {len(agency['priority'])}, Stale: {len(agency['standard'])}")

    log("\nScanning BI pipeline...")
    bi = scan_pipeline(BI_PIPELINE, "BI")
    log(f"  Total: {bi['total']}, Open: {bi['open']}")
    log(f"  Urgent: {len(bi['urgent'])}, Priority: {len(bi['priority'])}, Stale: {len(bi['standard'])}")

    total_flagged = (
        len(agency["urgent"]) + len(agency["priority"]) + len(agency["standard"]) +
        len(bi["urgent"]) + len(bi["priority"]) + len(bi["standard"])
    )

    if total_flagged == 0:
        log("\nNo leads need follow-up. All clear.")
        # Still log to git so we know it ran
        return

    log(f"\n{total_flagged} leads need attention")

    # Send Vinnie alert
    vinnie_msg = build_vinnie_message(agency, bi)
    if vinnie_msg:
        log("\nSending Vinnie alert...")
        send_vinnie(vinnie_msg)

    # Send email digest
    email_body = build_email_body(agency, bi)
    log("\nSending email digest...")
    send_email(f"Lead Follow-Up: {total_flagged} leads need action - {today}", email_body)

    log("\nDone!")


if __name__ == "__main__":
    main()

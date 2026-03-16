#!/usr/bin/env python3
"""
LinkedIn Token Expiry Monitor
Checks if LinkedIn OAuth tokens are approaching expiry.
Vinnie alerts 14 days and 7 days before expiry.

Token info:
- Oli's token: obtained ~March 10, 2026, expires_in: 5183999 seconds (~60 days)
- Lisa's token: obtained ~March 10, 2026, expires_in: 5183999 seconds (~60 days)
- Both expire around May 9, 2026

Update TOKEN_EXPIRY_DATES when tokens are refreshed.
"""

import os
import logging
from datetime import datetime, timedelta
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

VINNIE_PHONE = "4915129005414"
VINNIE_APIKEY = "5944134"

# UPDATE THESE when tokens are refreshed
TOKEN_EXPIRY_DATES = {
    "Oli LinkedIn": "2026-05-09",
    "Lisa LinkedIn": "2026-05-09",
}

WARNING_DAYS = [14, 7, 3, 1]


def vinnie_alert(msg: str):
    try:
        httpx.get(
            f"https://api.callmebot.com/whatsapp.php?phone={VINNIE_PHONE}&text={msg}&apikey={VINNIE_APIKEY}",
            timeout=10,
        )
        log.info("Vinnie alert sent")
    except Exception:
        log.warning("Failed to send Vinnie alert")


def main():
    today = datetime.now().date()
    alerts = []

    for name, expiry_str in TOKEN_EXPIRY_DATES.items():
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        days_left = (expiry - today).days

        log.info(f"{name}: expires {expiry_str} ({days_left} days left)")

        if days_left <= 0:
            alerts.append(f"{name}+token+EXPIRED.+Refresh+NOW+or+posting+will+fail.")
        elif days_left in WARNING_DAYS or days_left <= 3:
            alerts.append(f"{name}+token+expires+in+{days_left}+days+({expiry_str}).+Plan+to+refresh.")

    if alerts:
        for alert in alerts:
            vinnie_alert(f"Vinnie+here.+TOKEN+WARNING:+{alert}")
    else:
        log.info("All tokens healthy. No alerts needed.")

    print(f"Done! Checked {len(TOKEN_EXPIRY_DATES)} tokens.")


if __name__ == "__main__":
    main()

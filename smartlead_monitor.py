#!/usr/bin/env python3
"""
Smartlead Bounce Rate Monitor
Checks all active campaigns for bounce rates above threshold.
Vinnie alerts via WhatsApp when bounce rate exceeds 4%.
"""

import os
import sys
import json
import logging
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
BOUNCE_THRESHOLD = 4.0  # percent
VINNIE_PHONE = "4915129005414"
VINNIE_APIKEY = "5944134"
BASE_URL = "https://server.smartlead.ai/api/v1"


def vinnie_alert(msg: str):
    """Send WhatsApp alert via Vinnie."""
    try:
        httpx.get(
            f"https://api.callmebot.com/whatsapp.php?phone={VINNIE_PHONE}&text={msg}&apikey={VINNIE_APIKEY}",
            timeout=10,
        )
        log.info("Vinnie alert sent")
    except Exception:
        log.warning("Failed to send Vinnie alert")


def get_all_campaigns() -> list[dict]:
    """Fetch all campaigns."""
    resp = httpx.get(
        f"{BASE_URL}/campaigns",
        params={"api_key": SMARTLEAD_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_campaign_stats(campaign_id: int) -> dict:
    """Fetch lead-level stats for a campaign to calculate bounce rate."""
    # Get total stats count first
    resp = httpx.get(
        f"{BASE_URL}/campaigns/{campaign_id}/statistics",
        params={
            "api_key": SMARTLEAD_API_KEY,
            "offset": 0,
            "limit": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    total = int(data.get("total_stats", 0))

    if total == 0:
        return {"total": 0, "bounced": 0, "bounce_rate": 0.0}

    # Get bounced count
    resp_bounced = httpx.get(
        f"{BASE_URL}/campaigns/{campaign_id}/statistics",
        params={
            "api_key": SMARTLEAD_API_KEY,
            "offset": 0,
            "limit": 1,
            "email_status": "bounced",
        },
        timeout=30,
    )
    resp_bounced.raise_for_status()
    bounced_data = resp_bounced.json()
    bounced = int(bounced_data.get("total_stats", 0))

    bounce_rate = (bounced / total * 100) if total > 0 else 0.0

    return {
        "total": total,
        "bounced": bounced,
        "bounce_rate": round(bounce_rate, 2),
    }


def main():
    if not SMARTLEAD_API_KEY:
        log.error("SMARTLEAD_API_KEY not set")
        sys.exit(1)

    log.info("Fetching Smartlead campaigns...")
    campaigns = get_all_campaigns()

    active_campaigns = [c for c in campaigns if c.get("status") == "ACTIVE"]
    log.info(f"Found {len(active_campaigns)} active campaigns")

    alerts = []

    for campaign in active_campaigns:
        cid = campaign["id"]
        name = campaign.get("name", f"Campaign {cid}")

        try:
            stats = get_campaign_stats(cid)
            log.info(
                f"  {name}: {stats['total']} sent, {stats['bounced']} bounced, "
                f"{stats['bounce_rate']}% bounce rate"
            )

            if stats["bounce_rate"] > BOUNCE_THRESHOLD and stats["total"] >= 10:
                alerts.append({
                    "name": name,
                    "bounce_rate": stats["bounce_rate"],
                    "bounced": stats["bounced"],
                    "total": stats["total"],
                })

        except Exception as e:
            log.warning(f"  Failed to get stats for {name}: {e}")

    if alerts:
        for alert in alerts:
            msg = (
                f"Vinnie+here.+BOUNCE+ALERT:+{alert['name'].replace(' ', '+')}"
                f"+is+at+{alert['bounce_rate']}%25+bounce+rate"
                f"+({alert['bounced']}/{alert['total']}).+Check+Smartlead+now."
            )
            vinnie_alert(msg)
            log.warning(
                f"ALERT: {alert['name']} bounce rate {alert['bounce_rate']}% "
                f"({alert['bounced']}/{alert['total']})"
            )
    else:
        log.info("All campaigns within bounce threshold. No alerts needed.")

    print(f"\nDone! Checked {len(active_campaigns)} campaigns, {len(alerts)} alerts sent.")


if __name__ == "__main__":
    main()

"""alerts/discord_sender.py — Discord webhook notifications (no bot needed)."""
from __future__ import annotations
import requests


def send_discord_alert(webhook_url: str, ticker: str, report: dict) -> tuple[bool, str]:
    """
    Send a trade report to a Discord channel via webhook.
    No bot, no API key — just a webhook URL from Discord channel settings.

    Returns (success: bool, message: str)
    """
    if not webhook_url or not webhook_url.startswith("https://discord.com/api/webhooks/"):
        return False, "Invalid Discord webhook URL."

    action = report.get("action", "N/A")
    conviction = report.get("conviction_score", 0)
    entry = report.get("entry_price")
    target = report.get("target_price")
    stop = report.get("stop_loss")
    rr = report.get("risk_reward_ratio")
    summary = report.get("summary", "")

    # Action emoji + color
    color_map = {"Buy": 0x10b981, "Sell": 0xef4444, "Hold": 0xf59e0b, "Avoid": 0x6b7280}
    action_emoji = {"Buy": "🟢", "Sell": "🔴", "Hold": "🟡", "Avoid": "⚫"}.get(action, "⚪")
    embed_color = color_map.get(action, 0x60a5fa)

    fields = [
        {"name": "Entry Price", "value": f"₹{entry:,.2f}" if entry else "Market", "inline": True},
        {"name": "Target", "value": f"₹{target:,.2f}" if target else "N/A", "inline": True},
        {"name": "Stop Loss", "value": f"₹{stop:,.2f}" if stop else "N/A", "inline": True},
        {"name": "R:R Ratio", "value": f"{rr:.2f}:1" if rr else "N/A", "inline": True},
        {"name": "Conviction", "value": f"{conviction}/10", "inline": True},
    ]

    payload = {
        "username": "Megha's Trading Alerts",
        "avatar_url": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f4c8.png",
        "embeds": [{
            "title": f"{action_emoji} {ticker} — {action}",
            "description": summary[:300] if summary else "Analysis complete.",
            "color": embed_color,
            "fields": fields,
            "footer": {"text": "⚠️ Not financial advice · Megha's Trading System"},
        }]
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            print(f"[discord_sender] ✅ Alert sent to Discord for {ticker}")
            return True, "Discord message sent."
        else:
            return False, f"Discord API error {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, f"Discord send error: {e}"

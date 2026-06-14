"""alerts/email_sender.py — Gmail SMTP alert delivery."""
from __future__ import annotations
import smtplib
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python 3.10 backport
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.toml")


def _load_email_cfg() -> dict:
    try:
        with open(_CONFIG_PATH, "rb") as f:
            return tomllib.load(f).get("email", {})
    except Exception:
        return {}


def send_alert_email(to_address: str, subject: str, body_html: str) -> tuple[bool, str]:
    """
    Send an HTML alert email via Gmail SMTP.

    Returns (success: bool, message: str)
    """
    cfg = _load_email_cfg()
    smtp_host = cfg.get("smtp_host", "smtp.gmail.com")
    smtp_port = cfg.get("smtp_port", 587)
    sender_email = cfg.get("sender_email", "")
    app_password = cfg.get("sender_app_password", "")
    sender_name = cfg.get("sender_name", "Megha's Trading Alerts")

    if not sender_email or not app_password:
        return False, "Email not configured. Set sender_email and sender_app_password in config.toml."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = to_address

        # Plain text fallback
        plain = body_html.replace("<br>", "\n").replace("<b>", "").replace("</b>", "")
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_address, msg.as_string())

        print(f"[email_sender] ✅ Alert sent to {to_address}")
        return True, "Email sent successfully."

    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Check your App Password in config.toml."
    except Exception as e:
        return False, f"Email send error: {e}"


def format_alert_email(ticker: str, report: dict) -> tuple[str, str]:
    """Format a trade report into an email subject + HTML body."""
    action = report.get("action", "N/A")
    conviction = report.get("conviction_score", 0)
    entry = report.get("entry_price")
    target = report.get("target_price")
    stop = report.get("stop_loss")
    rr = report.get("risk_reward_ratio")
    summary = report.get("summary", "")

    subject = f"📈 Alert: {ticker} — {action} | Conviction {conviction}/10"

    action_color = {"Buy": "#10b981", "Sell": "#ef4444", "Hold": "#f59e0b", "Avoid": "#6b7280"}.get(action, "#94a3b8")

    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#0a0e1a;color:#e2e8f0;border-radius:12px;padding:24px;">
        <h2 style="color:#60a5fa;margin:0 0 8px 0;">📈 Megha's Trading Alert</h2>
        <hr style="border-color:#1e293b;">
        <h3 style="color:#e2e8f0;">{ticker}</h3>
        <p style="font-size:1.4rem;font-weight:700;color:{action_color};">{action}</p>
        <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:6px;color:#64748b;">Entry Price</td><td style="padding:6px;color:#e2e8f0;font-weight:600;">{'₹{:,.2f}'.format(entry) if entry else 'Market'}</td></tr>
            <tr><td style="padding:6px;color:#64748b;">Target Price</td><td style="padding:6px;color:#10b981;font-weight:600;">{'₹{:,.2f}'.format(target) if target else 'N/A'}</td></tr>
            <tr><td style="padding:6px;color:#64748b;">Stop Loss</td><td style="padding:6px;color:#ef4444;font-weight:600;">{'₹{:,.2f}'.format(stop) if stop else 'N/A'}</td></tr>
            <tr><td style="padding:6px;color:#64748b;">R:R Ratio</td><td style="padding:6px;color:#e2e8f0;font-weight:600;">{f'{rr:.2f}:1' if rr else 'N/A'}</td></tr>
            <tr><td style="padding:6px;color:#64748b;">Conviction</td><td style="padding:6px;color:#f59e0b;font-weight:600;">{conviction}/10</td></tr>
        </table>
        <hr style="border-color:#1e293b;">
        <p style="color:#94a3b8;font-size:0.9rem;">{summary}</p>
        <p style="color:#334155;font-size:0.75rem;margin-top:16px;">⚠️ For educational purposes only. Not financial advice.</p>
    </div>
    """
    return subject, body

#!/usr/bin/env python3
"""Send email alerts for competitor monitoring changes.

Usage:
    python3 send_email.py --to <email> --subject <subject> --body-file <path>
    python3 send_email.py --to <email> --subject <subject> --body "inline body"

Environment variables:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

# Load .env
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(_env_path)


def send_email(
    to: list[str],
    subject: str,
    body_html: str,
    body_text: str | None = None,
) -> dict:
    """Send an email via SMTP. Returns status dict."""

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        return {"status": "failed", "error": "SMTP_USER and SMTP_PASSWORD not configured"}

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject

    # Plain text fallback
    if body_text:
        msg.attach(MIMEText(body_text, "plain"))

    # HTML body
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to, msg.as_string())
        return {"status": "sent", "recipients": to, "subject": subject}
    except smtplib.SMTPException as e:
        return {"status": "failed", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Send email alert")
    parser.add_argument("--to", required=True, help="Comma-separated recipient emails")
    parser.add_argument("--subject", required=True, help="Email subject line")
    parser.add_argument("--body", help="Inline HTML body")
    parser.add_argument("--body-file", help="Path to HTML body file")
    args = parser.parse_args()

    # Get body content
    if args.body_file:
        with open(args.body_file) as f:
            body_html = f.read()
    elif args.body:
        body_html = args.body
    else:
        print(json.dumps({"status": "failed", "error": "Provide --body or --body-file"}))
        sys.exit(1)

    recipients = [e.strip() for e in args.to.split(",")]
    result = send_email(recipients, args.subject, body_html)
    print(json.dumps(result, indent=2))

    if result["status"] == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()

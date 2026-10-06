"""Outgoing email. Messages are queued in the outbox table and sent when SMTP is configured."""

import smtplib
from email.message import EmailMessage

from . import config
from .periods import iso


def queue(conn, now, kind, to_addr, subject, body):
    conn.execute("INSERT INTO outbox (created_at, kind, to_addr, subject, body) VALUES (?,?,?,?,?)",
                 (iso(now), kind, to_addr, subject, body))


def flush(conn, now):
    """Send queued messages. Returns how many were sent; without SMTP settings nothing is sent."""
    if not config.SMTP_HOST:
        return 0
    rows = conn.execute("SELECT * FROM outbox WHERE sent_at IS NULL AND to_addr IS NOT NULL ORDER BY id").fetchall()
    if not rows:
        return 0
    sent = 0
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        for r in rows:
            msg = EmailMessage()
            msg["From"] = config.SMTP_FROM or config.SMTP_USER
            msg["To"] = r["to_addr"]
            msg["Subject"] = r["subject"]
            msg.set_content(r["body"])
            smtp.send_message(msg)
            conn.execute("UPDATE outbox SET sent_at = ? WHERE id = ?", (iso(now), r["id"]))
            sent += 1
    return sent

"""Outgoing email. Messages are queued in the outbox table and sent through Brevo or a Microsoft 365 mailbox.

The simple way is Brevo: BREVO_API_KEY and MERIDIAN_MAIL_FROM (an address confirmed in Brevo). The Microsoft way follows.

Sending goes through Microsoft Graph over the web, because the host does not allow ordinary mail ports. It needs an
app registered in Microsoft Entra with the "Mail.Send" application permission, and these settings:

    MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET   the registered app
    MERIDIAN_MAIL_FROM                              the mailbox the emails come from
    MERIDIAN_MAIL_MODE                              off | test | live. In test, every email goes only to MERIDIAN_MAIL_TEST_TO.

Nothing is sent while the mode is off. Messages that waited more than two days are dropped, never sent late.
On a laptop, MERIDIAN_SMTP_* settings are used when the Microsoft ones are missing.
"""

import json
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from email.message import EmailMessage

from . import config
from .periods import iso

STALE_DAYS = 2
GRAPH = ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET", "MERIDIAN_MAIL_FROM")


class MailError(Exception):
    """A problem the person using this can act on."""


def mode():
    value = config.setting("MERIDIAN_MAIL_MODE", "off").strip().lower()
    return value if value in ("test", "live") else "off"


def graph_ready():
    return all(config.setting(k) for k in GRAPH)


def brevo_ready():
    return bool(config.setting("BREVO_API_KEY") and config.setting("MERIDIAN_MAIL_FROM"))


def ready():
    return brevo_ready() or graph_ready() or bool(config.SMTP_HOST)


def status():
    return dict(mode=mode(), ready=ready(), sender=config.setting("MERIDIAN_MAIL_FROM") or config.SMTP_FROM or config.SMTP_USER or None,
                test_to=config.setting("MERIDIAN_MAIL_TEST_TO") or None)


def queue(conn, now, kind, to_addr, subject, body):
    conn.execute("INSERT INTO outbox (created_at, kind, to_addr, subject, body) VALUES (?,?,?,?,?)",
                 (iso(now), kind, to_addr, subject, body))


def post(url, token=None, form=None, body=None, key=None, who="Microsoft"):
    data = urllib.parse.urlencode(form).encode() if form else json.dumps(body).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if key:
        headers["api-key"] = key
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as res:
            text = res.read().decode("utf-8", "ignore")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read().decode("utf-8", "ignore"))
            detail = detail.get("error_description") or detail.get("message") or (detail.get("error") or {}).get("message") or ""
        except (ValueError, AttributeError):
            detail = ""
        raise MailError("{} answered with error {}{}".format(who, err.code, ": " + detail.splitlines()[0][:200] if detail else ""))
    except (urllib.error.URLError, OSError) as err:
        raise MailError("{} could not be reached ({})".format(who, getattr(err, "reason", err)))


def graph_sender():
    token = post("https://login.microsoftonline.com/{}/oauth2/v2.0/token".format(config.setting("MS_TENANT_ID")),
                 form=dict(client_id=config.setting("MS_CLIENT_ID"), client_secret=config.setting("MS_CLIENT_SECRET"),
                           scope="https://graph.microsoft.com/.default", grant_type="client_credentials"))["access_token"]
    url = "https://graph.microsoft.com/v1.0/users/{}/sendMail".format(urllib.parse.quote(config.setting("MERIDIAN_MAIL_FROM")))

    def send(to, subject, body):
        post(url, token=token, body=dict(saveToSentItems=True, message=dict(
            subject=subject, body=dict(contentType="Text", content=body), toRecipients=[dict(emailAddress=dict(address=a)) for a in to])))
    return send, lambda: None


def brevo_sender():
    key, sender = config.setting("BREVO_API_KEY"), dict(email=config.setting("MERIDIAN_MAIL_FROM"), name="Meridian")

    def send(to, subject, body):
        post("https://api.brevo.com/v3/smtp/email", key=key, who="Brevo",
             body=dict(sender=sender, to=[dict(email=a) for a in to], subject=subject or "Meridian", textContent=body or " "))
    return send, lambda: None


def smtp_sender():
    smtp = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
    smtp.starttls()
    if config.SMTP_USER:
        smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)

    def send(to, subject, body):
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM or config.SMTP_USER, ", ".join(to), subject
        msg.set_content(body)
        smtp.send_message(msg)
    return send, smtp.quit


def sender():
    return brevo_sender() if brevo_ready() else graph_sender() if graph_ready() else smtp_sender()


def send_now(to, subject, body):
    """Send one email straight away to the addresses someone typed on the screen. Works whatever the mode: it was asked for by hand."""
    if not ready():
        raise MailError("Email is not set up yet")
    send, close = sender()
    try:
        send(to, subject, body)
    finally:
        close()


def flush(conn, now):
    """Send queued messages. Returns how many were sent; nothing is sent while the mode is off or no mailbox is set up."""
    conn.execute("UPDATE outbox SET sent_at = 'dropped' WHERE sent_at IS NULL AND created_at < ?", (iso(now - timedelta(days=STALE_DAYS)),))
    kind, test_to = mode(), config.setting("MERIDIAN_MAIL_TEST_TO")
    if kind == "off" or not ready() or (kind == "test" and not test_to):
        return 0
    rows = conn.execute("SELECT * FROM outbox WHERE sent_at IS NULL AND to_addr IS NOT NULL ORDER BY id LIMIT 50").fetchall()
    if not rows:
        return 0
    send, close = sender()
    sent = 0
    try:
        for r in rows:
            to = [a.strip() for a in r["to_addr"].split(",") if a.strip()]
            if kind == "test":
                send([test_to], "[Test] " + (r["subject"] or ""), "Would have gone to: {}\n\n{}".format(", ".join(to), r["body"] or ""))
            else:
                send(to, r["subject"] or "", r["body"] or "")
            conn.execute("UPDATE outbox SET sent_at = ? WHERE id = ?", (iso(now), r["id"]))
            sent += 1
    finally:
        close()
    return sent

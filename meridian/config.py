import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"  # local secrets (Zoho credentials, webhook token). Never committed.


def read_env_file():
    """KEY=VALUE pairs from .env. Read on demand, so credentials saved while the app runs take effect at once."""
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def setting(key, default=""):
    """A configuration value: the environment wins, then .env, then the default."""
    return os.environ.get(key) or read_env_file().get(key) or default


STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
LIVE_DB = DATA_DIR / "meridian.db"   # real data, created when Zoho is connected
SAMPLE_DB = DATA_DIR / "sample.db"   # the built-in sample company
COMPANY = "Chat360"


def db_path():
    """The database in use: MERIDIAN_DB if set, the sample when MERIDIAN_SAMPLE=1, else live data once it exists."""
    if os.environ.get("MERIDIAN_DB"):
        return Path(os.environ["MERIDIAN_DB"])
    if os.environ.get("MERIDIAN_SAMPLE") == "1" or not LIVE_DB.exists():
        return SAMPLE_DB
    return LIVE_DB

# Shared secret that webhook senders must pass as ?token=... (empty = webhooks rejected).
WEBHOOK_TOKEN = setting("MERIDIAN_WEBHOOK_TOKEN")

# Zoho data centre: "in" for crm.zoho.in, "com" for crm.zoho.com, and so on.
ZOHO_DC = setting("ZOHO_DC", "in")
# Base URL for "Open in Zoho CRM" links; the lead's Zoho id is appended.
ZOHO_LEAD_URL = setting("MERIDIAN_ZOHO_LEAD_URL", "https://crm.zoho.{}/crm/tab/Leads".format(ZOHO_DC))

# SMTP settings for reminder and report emails. Without a host, emails are only
# written to the outbox table.
SMTP_HOST = setting("MERIDIAN_SMTP_HOST")
SMTP_PORT = int(setting("MERIDIAN_SMTP_PORT", "587"))
SMTP_USER = setting("MERIDIAN_SMTP_USER")
SMTP_PASSWORD = setting("MERIDIAN_SMTP_PASSWORD")
SMTP_FROM = setting("MERIDIAN_SMTP_FROM")

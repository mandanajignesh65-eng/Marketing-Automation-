import sqlite3
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, grp TEXT NOT NULL,  -- organic | paid | outbound
  color TEXT NOT NULL, narrative TEXT NOT NULL, sort INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS utm_map (
  id INTEGER PRIMARY KEY, source TEXT NOT NULL, medium TEXT NOT NULL,
  channel_id TEXT REFERENCES channels(id),
  excluded INTEGER NOT NULL DEFAULT 0,  -- 1 = a lead source left out as not marketing; its leads are not kept
  UNIQUE (source, medium)
);
-- Leads not kept because their lead source is left out. Only the ids stay: enough to count them and to
-- keep the deals they turned into out as well.
-- What company research found, one row per company. key is its domain, or 'name:' + the name as typed on the lead.
CREATE TABLE IF NOT EXISTS companies (
  key TEXT PRIMARY KEY, status TEXT NOT NULL,  -- found | not_found
  name TEXT, domain TEXT, industry TEXT, industries TEXT, employee_range TEXT, founded INTEGER, website TEXT,
  profile_url TEXT, source TEXT, researched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS left_out_leads (zoho_id TEXT PRIMARY KEY, source TEXT NOT NULL, deal_zoho_id TEXT);
CREATE INDEX IF NOT EXISTS left_out_deal ON left_out_leads (deal_zoho_id);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, team TEXT, role TEXT, email TEXT, last_active_at TEXT
);

CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY, zoho_id TEXT UNIQUE, name TEXT NOT NULL, title TEXT, company TEXT, email TEXT,
  channel_id TEXT REFERENCES channels(id), owner TEXT, status TEXT NOT NULL DEFAULT 'New',
  score INTEGER NOT NULL DEFAULT 0, fit INTEGER NOT NULL DEFAULT 0, intent INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, last_activity_at TEXT, last_activity TEXT, owner_updated_at TEXT,
  employees INTEGER, revenue INTEGER, industry TEXT, hq TEXT, website TEXT, founded INTEGER,
  company_size TEXT,  -- size band from the CRM when there is no employee count, e.g. "Enterprise (500+ Emp)"
  industry_via TEXT, size_via TEXT,  -- set when company research, not the CRM, supplied the industry or the size
  enriched_at TEXT, enriched_via TEXT,
  utm_source TEXT, utm_medium TEXT, utm_campaign TEXT, lead_source TEXT,
  deal_zoho_id TEXT,  -- the Zoho deal this lead was converted into, if any
  ft_channel TEXT, ft_at TEXT, ft_detail TEXT, lt_channel TEXT, lt_at TEXT, lt_detail TEXT
);
CREATE INDEX IF NOT EXISTS leads_created ON leads (created_at);
CREATE INDEX IF NOT EXISTS leads_channel ON leads (channel_id, created_at);

CREATE TABLE IF NOT EXISTS scoring_criteria (
  key TEXT PRIMARY KEY, grp TEXT NOT NULL, label TEXT NOT NULL, rule TEXT NOT NULL,
  weight INTEGER NOT NULL, sort INTEGER NOT NULL
);
-- fraction is how fully the lead meets the criterion (0..1); points = round(weight * fraction).
CREATE TABLE IF NOT EXISTS lead_score_items (
  lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE, criterion_key TEXT NOT NULL,
  fraction REAL NOT NULL, why TEXT, PRIMARY KEY (lead_id, criterion_key)
);
CREATE TABLE IF NOT EXISTS lead_events (
  id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  at TEXT NOT NULL, kind TEXT NOT NULL,  -- touch | crm | reminder
  channel_id TEXT, title TEXT NOT NULL, detail TEXT
);
CREATE INDEX IF NOT EXISTS lead_events_lead ON lead_events (lead_id, at);
CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  rule TEXT NOT NULL,  -- r3 | r7
  owner TEXT, sent_at TEXT NOT NULL, opened_at TEXT, owner_updated_at TEXT
);
CREATE INDEX IF NOT EXISTS reminders_lead ON reminders (lead_id, sent_at);
CREATE TABLE IF NOT EXISTS deals (
  id INTEGER PRIMARY KEY, zoho_id TEXT UNIQUE, name TEXT,
  lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL, channel_id TEXT,
  amount INTEGER NOT NULL, stage TEXT NOT NULL DEFAULT 'open',  -- open | won | lost
  created_at TEXT NOT NULL, closed_at TEXT, lead_source TEXT
);
CREATE INDEX IF NOT EXISTS deals_lead ON deals (lead_id);

CREATE TABLE IF NOT EXISTS channel_daily (
  date TEXT NOT NULL, channel_id TEXT NOT NULL, impressions INTEGER NOT NULL DEFAULT 0,
  clicks INTEGER NOT NULL DEFAULT 0, spend INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (date, channel_id)
);
CREATE TABLE IF NOT EXISTS ad_campaigns (
  id INTEGER PRIMARY KEY, platform TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS ad_creatives (
  id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES ad_campaigns(id), headline TEXT NOT NULL, format TEXT
);
CREATE TABLE IF NOT EXISTS ad_daily (
  date TEXT NOT NULL, creative_id INTEGER NOT NULL, spend INTEGER NOT NULL DEFAULT 0,
  impressions INTEGER NOT NULL DEFAULT 0, clicks INTEGER NOT NULL DEFAULT 0, leads INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (date, creative_id)
);
CREATE TABLE IF NOT EXISTS outbound_campaigns (
  id INTEGER PRIMARY KEY, channel_id TEXT NOT NULL, name TEXT NOT NULL, detail TEXT
);
CREATE TABLE IF NOT EXISTS outbound_daily (
  date TEXT NOT NULL, campaign_id INTEGER NOT NULL, sent INTEGER NOT NULL DEFAULT 0,
  opened INTEGER NOT NULL DEFAULT 0, replied INTEGER NOT NULL DEFAULT 0, meetings INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (date, campaign_id)
);

CREATE TABLE IF NOT EXISTS traffic_daily (
  date TEXT NOT NULL, source TEXT NOT NULL, medium TEXT NOT NULL, sessions INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (date, source, medium)
);
CREATE TABLE IF NOT EXISTS search_daily (date TEXT PRIMARY KEY, position REAL NOT NULL);
CREATE TABLE IF NOT EXISTS page_daily (
  date TEXT NOT NULL, path TEXT NOT NULL, title TEXT, views INTEGER NOT NULL DEFAULT 0,
  leads INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (date, path)
);
CREATE TABLE IF NOT EXISTS query_daily (
  date TEXT NOT NULL, query TEXT NOT NULL, clicks INTEGER NOT NULL DEFAULT 0,
  impressions INTEGER NOT NULL DEFAULT 0, position REAL, PRIMARY KEY (date, query)
);
CREATE TABLE IF NOT EXISTS form_daily (
  date TEXT NOT NULL, form TEXT NOT NULL, views INTEGER NOT NULL DEFAULT 0,
  submissions INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (date, form)
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT, monthly_cost INTEGER NOT NULL DEFAULT 0,
  seats INTEGER, owner TEXT, renews_on TEXT, billing TEXT NOT NULL DEFAULT 'Monthly', annual_cost INTEGER
);
CREATE TABLE IF NOT EXISTS subscription_history (month TEXT PRIMARY KEY, total INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS targets (
  month TEXT NOT NULL, key TEXT NOT NULL, value REAL NOT NULL, PRIMARY KEY (month, key)
);

CREATE TABLE IF NOT EXISTS sources (
  key TEXT PRIMARY KEY, name TEXT NOT NULL, detail TEXT,
  status TEXT NOT NULL DEFAULT 'not_connected',  -- connected | disconnected | not_connected
  last_sync_at TEXT, note TEXT, stale_after_hours INTEGER NOT NULL DEFAULT 6, sort INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_rules (
  key TEXT PRIMARY KEY, kind TEXT NOT NULL,  -- alert | reminder
  title TEXT NOT NULL, detail TEXT, deliver_to TEXT, enabled INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY, rule_key TEXT NOT NULL, dedupe TEXT NOT NULL, title TEXT NOT NULL, detail TEXT,
  severity TEXT NOT NULL DEFAULT 'warn',  -- neg | warn | info
  created_at TEXT NOT NULL, resolved_at TEXT, UNIQUE (rule_key, dedupe)
);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY, week_start TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'draft',  -- draft | sent
  headline TEXT, body TEXT, next_steps TEXT, edited INTEGER NOT NULL DEFAULT 0,  -- 1 once someone has rewritten the draft
  sent_at TEXT, recipients INTEGER, opened INTEGER
);
CREATE TABLE IF NOT EXISTS report_recipients (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT, email TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member',
  salt TEXT NOT NULL, pw_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS benchmarks (
  key TEXT PRIMARY KEY, value REAL, watch INTEGER NOT NULL DEFAULT 1  -- value NULL = use the built-in starting figure
);
CREATE TABLE IF NOT EXISTS team_members (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, focus TEXT, email TEXT, active INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL REFERENCES team_members(id), title TEXT NOT NULL,
  metric TEXT NOT NULL DEFAULT 'manual',  -- 'manual', or a key Meridian counts by itself (see team.METRICS)
  period TEXT NOT NULL DEFAULT 'week',    -- week | month
  target REAL NOT NULL, unit TEXT, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS goal_log (
  id INTEGER PRIMARY KEY, goal_id INTEGER NOT NULL REFERENCES goals(id), day TEXT NOT NULL, amount REAL NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS goal_log_day ON goal_log (goal_id, day);
CREATE TABLE IF NOT EXISTS goal_notes (
  goal_id INTEGER NOT NULL REFERENCES goals(id), day TEXT NOT NULL, note TEXT, updated_at TEXT NOT NULL, PRIMARY KEY (goal_id, day)
);
CREATE TABLE IF NOT EXISTS team_tasks (
  id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL REFERENCES team_members(id), day TEXT NOT NULL, title TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS team_notes (
  member_id INTEGER NOT NULL, day TEXT NOT NULL, note TEXT, updated_at TEXT NOT NULL, PRIMARY KEY (member_id, day)
);
CREATE TABLE IF NOT EXISTS blockers (
  id INTEGER PRIMARY KEY, member_id INTEGER REFERENCES team_members(id), text TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS search_page_daily (
  date TEXT NOT NULL, page TEXT NOT NULL, clicks INTEGER NOT NULL DEFAULT 0, impressions INTEGER NOT NULL DEFAULT 0,
  position REAL, PRIMARY KEY (date, page)
);
CREATE TABLE IF NOT EXISTS semrush_files (file TEXT PRIMARY KEY, read_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS semrush_keywords (
  domain TEXT NOT NULL, country TEXT NOT NULL, day TEXT NOT NULL, keyword TEXT NOT NULL, position INTEGER NOT NULL,
  previous INTEGER, volume INTEGER NOT NULL DEFAULT 0, difficulty INTEGER, url TEXT, traffic INTEGER NOT NULL DEFAULT 0,
  intent TEXT, PRIMARY KEY (domain, country, day, keyword)
);
CREATE TABLE IF NOT EXISTS semrush_competitors (
  domain TEXT NOT NULL, country TEXT NOT NULL, day TEXT NOT NULL, competitor TEXT NOT NULL, relevance REAL,
  common INTEGER NOT NULL DEFAULT 0, keywords INTEGER NOT NULL DEFAULT 0, traffic INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (domain, country, day, competitor)
);
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL, to_addr TEXT, subject TEXT,
  body TEXT, sent_at TEXT
);
"""

TABLES = [
    "settings", "channels", "utm_map", "users", "leads", "scoring_criteria", "lead_score_items",
    "lead_events", "reminders", "deals", "channel_daily", "ad_campaigns", "ad_creatives", "ad_daily",
    "outbound_campaigns", "outbound_daily", "traffic_daily", "search_daily", "page_daily", "query_daily",
    "form_daily", "subscriptions", "subscription_history", "targets", "sources", "alert_rules", "alerts",
    "reports", "report_recipients", "outbox", "left_out_leads", "companies",
    "semrush_files", "semrush_keywords", "semrush_competitors", "search_page_daily",
    "accounts", "sessions", "benchmarks", "team_members", "goals", "goal_log", "goal_notes", "team_tasks", "team_notes", "blockers",
]


def connect(path=None):
    path = path or config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the first release: (table, column, type). upgrade() adds any that are missing.
ADDED_COLUMNS = [("leads", "company_size", "TEXT"), ("deals", "lead_source", "TEXT"),
                 ("utm_map", "excluded", "INTEGER NOT NULL DEFAULT 0"),
                 ("leads", "industry_via", "TEXT"), ("leads", "size_via", "TEXT"),
                 # the tool's own id for a campaign, and its lifetime counts at the last sync (sent, opened, replied, meetings)
                 ("outbound_campaigns", "ext_id", "TEXT"), ("outbound_campaigns", "lifetime", "TEXT"),
                 ("ad_campaigns", "ext_id", "TEXT"), ("ad_creatives", "ext_id", "TEXT"),
                 ("subscriptions", "email", "TEXT")]  # who to email when the renewal is near


def init_schema(conn):
    conn.executescript(SCHEMA)


def upgrade(conn):
    """Bring an existing database up to the current schema without touching its data."""
    conn.executescript(SCHEMA)
    for table, column, kind in ADDED_COLUMNS:
        if column not in {r["name"] for r in conn.execute("PRAGMA table_info({})".format(table))}:
            conn.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, column, kind))


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def now(conn):
    """Current time. Sample data pins the clock so its figures stay coherent."""
    pinned = get_setting(conn, "demo_now")
    return datetime.fromisoformat(pinned) if pinned else datetime.now().replace(microsecond=0)


def is_demo(conn):
    return get_setting(conn, "demo_now") is not None

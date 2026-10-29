import sqlite3
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, grp TEXT NOT NULL,  -- organic | paid | events | outbound
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
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, starts TEXT NOT NULL, ends TEXT, city TEXT, venue TEXT, partner TEXT, booth TEXT,
  goal TEXT, decision TEXT NOT NULL DEFAULT 'Considering', lessons TEXT, budget REAL,
  target_leads REAL, target_meetings REAL, target_qualified REAL, target_pipeline REAL,
  visitors REAL, meetings_held REAL,  -- typed in after the event: people captured at the booth, meetings actually held
  lead_sources TEXT NOT NULL DEFAULT '[]',  -- JSON list of Zoho lead sources that name this event; a source belongs to one event
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_steps (
  id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, phase TEXT NOT NULL, workstream TEXT, title TEXT NOT NULL, owner TEXT,
  due TEXT, status TEXT NOT NULL DEFAULT 'Not started', done_when TEXT, note TEXT, sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS playbook_steps (  -- the standard plan copied into every new event
  id INTEGER PRIMARY KEY, phase TEXT NOT NULL, workstream TEXT, title TEXT NOT NULL, offset_days INTEGER NOT NULL DEFAULT 0,
  done_when TEXT, owner TEXT, sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS event_promos (
  id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, channel TEXT NOT NULL, what TEXT NOT NULL, day TEXT, owner TEXT,
  status TEXT NOT NULL DEFAULT 'Not started'
);
CREATE TABLE IF NOT EXISTS event_creatives (
  id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, url TEXT NOT NULL, platform TEXT, title TEXT, image TEXT, posted_on TEXT, caption TEXT
);
CREATE TABLE IF NOT EXISTS event_targets (  -- companies the event is meant to reach; company names only, never people
  id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, company TEXT NOT NULL, tier INTEGER NOT NULL DEFAULT 2, domain TEXT
);
CREATE TABLE IF NOT EXISTS event_costs (
  id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, category TEXT NOT NULL, item TEXT NOT NULL, amount REAL NOT NULL, paid INTEGER NOT NULL DEFAULT 0
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
-- the same visit and search figures kept per website, for companies with more than one site
CREATE TABLE IF NOT EXISTS traffic_site_daily (
  date TEXT NOT NULL, site TEXT NOT NULL, source TEXT NOT NULL, medium TEXT NOT NULL, sessions INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (date, site, source, medium)
);
CREATE TABLE IF NOT EXISTS search_site_daily (
  date TEXT NOT NULL, site TEXT NOT NULL, clicks INTEGER NOT NULL DEFAULT 0, impressions INTEGER NOT NULL DEFAULT 0, position REAL,
  PRIMARY KEY (date, site)
);
CREATE TABLE IF NOT EXISTS query_site_daily (
  date TEXT NOT NULL, site TEXT NOT NULL, query TEXT NOT NULL, clicks INTEGER NOT NULL DEFAULT 0, impressions INTEGER NOT NULL DEFAULT 0,
  position REAL, PRIMARY KEY (date, site, query)
);
-- Meta Ads in full: the account's structure, a row per ad per day, who saw the ads, and what Meridian sends back
CREATE TABLE IF NOT EXISTS meta_campaigns (
  id TEXT PRIMARY KEY, account TEXT NOT NULL, name TEXT NOT NULL, status TEXT, objective TEXT, buying_type TEXT,
  daily_budget REAL, lifetime_budget REAL, bid_strategy TEXT, created TEXT, updated TEXT, seen_at TEXT
);
CREATE TABLE IF NOT EXISTS meta_adsets (
  id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL, name TEXT NOT NULL, status TEXT, optimization_goal TEXT, destination_type TEXT,
  billing_event TEXT, daily_budget REAL, lifetime_budget REAL, bid_strategy TEXT, promoted TEXT, targeting TEXT, learning TEXT,
  starts TEXT, ends TEXT, seen_at TEXT
);
CREATE TABLE IF NOT EXISTS meta_ads (
  id TEXT PRIMARY KEY, adset_id TEXT, campaign_id TEXT, name TEXT NOT NULL, status TEXT, creative_id TEXT, title TEXT, body TEXT, cta TEXT,
  image_url TEXT, video_id TEXT, format TEXT, preview TEXT, created TEXT, seen_at TEXT,
  quality_ranking TEXT, engagement_ranking TEXT, conversion_ranking TEXT
);
CREATE TABLE IF NOT EXISTS meta_ad_daily (
  date TEXT NOT NULL, ad_id TEXT NOT NULL, spend REAL NOT NULL DEFAULT 0, impressions INTEGER NOT NULL DEFAULT 0, reach INTEGER NOT NULL DEFAULT 0,
  clicks INTEGER NOT NULL DEFAULT 0, link_clicks INTEGER NOT NULL DEFAULT 0, chats INTEGER NOT NULL DEFAULT 0, first_replies INTEGER NOT NULL DEFAULT 0,
  leads INTEGER NOT NULL DEFAULT 0, video_plays INTEGER NOT NULL DEFAULT 0, video_3s INTEGER NOT NULL DEFAULT 0, thruplays INTEGER NOT NULL DEFAULT 0,
  video_p25 INTEGER NOT NULL DEFAULT 0, video_p50 INTEGER NOT NULL DEFAULT 0, video_p75 INTEGER NOT NULL DEFAULT 0, video_p100 INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (date, ad_id)
);
CREATE TABLE IF NOT EXISTS meta_breakdown_daily (
  date TEXT NOT NULL, adset_id TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL, spend REAL NOT NULL DEFAULT 0,
  impressions INTEGER NOT NULL DEFAULT 0, link_clicks INTEGER NOT NULL DEFAULT 0, chats INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (date, adset_id, kind, value)
);
CREATE TABLE IF NOT EXISTS meta_events (
  id INTEGER PRIMARY KEY, event_name TEXT NOT NULL, event_time INTEGER NOT NULL, ctwa_clid TEXT NOT NULL, lead_ref TEXT, value REAL, currency TEXT,
  status TEXT NOT NULL DEFAULT 'queued',  -- queued | tested | sent | failed | expired
  tries INTEGER NOT NULL DEFAULT 0, response TEXT, created_at TEXT NOT NULL, sent_at TEXT, UNIQUE (event_name, ctwa_clid)
);
CREATE TABLE IF NOT EXISTS meta_audiences (key TEXT PRIMARY KEY, ext_id TEXT, name TEXT, people INTEGER, synced_at TEXT);
-- competitor monitoring: who is watched, which of their pages, the links already seen there, and the signals found
CREATE TABLE IF NOT EXISTS competitors (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, domain TEXT NOT NULL, linkedin TEXT, needs_context INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0, press_at TEXT, press_note TEXT
);
CREATE TABLE IF NOT EXISTS competitor_sources (
  id INTEGER PRIMARY KEY, competitor_id INTEGER NOT NULL REFERENCES competitors(id), kind TEXT NOT NULL, url TEXT NOT NULL,
  checked_at TEXT, note TEXT, baseline_at TEXT, fingerprint TEXT
);
CREATE TABLE IF NOT EXISTS competitor_seen (source_id INTEGER NOT NULL, url TEXT NOT NULL, PRIMARY KEY (source_id, url));
CREATE TABLE IF NOT EXISTS competitor_signals (
  id INTEGER PRIMARY KEY, competitor_id INTEGER NOT NULL REFERENCES competitors(id), category TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
  source TEXT, origin TEXT NOT NULL,          -- press | site | watch
  published_at TEXT, first_seen TEXT NOT NULL,
  verification TEXT NOT NULL,                 -- dated | first_seen | verified | lead
  summary TEXT, hidden INTEGER NOT NULL DEFAULT 0, mentions INTEGER NOT NULL DEFAULT 1, UNIQUE (competitor_id, url)
);
CREATE INDEX IF NOT EXISTS competitor_signals_at ON competitor_signals (published_at, first_seen);
-- competitors' social pages and what they posted there
CREATE TABLE IF NOT EXISTS competitor_accounts (
  id INTEGER PRIMARY KEY, competitor_id INTEGER NOT NULL REFERENCES competitors(id), network TEXT NOT NULL, url TEXT NOT NULL,
  feed TEXT, checked_at TEXT, note TEXT, UNIQUE (competitor_id, network)
);
CREATE TABLE IF NOT EXISTS competitor_posts (
  id INTEGER PRIMARY KEY, competitor_id INTEGER NOT NULL REFERENCES competitors(id), network TEXT NOT NULL, url TEXT NOT NULL,
  title TEXT NOT NULL, kind TEXT, posted_at TEXT NOT NULL, views INTEGER, likes INTEGER, first_seen TEXT NOT NULL, UNIQUE (competitor_id, url)
);
CREATE INDEX IF NOT EXISTS competitor_posts_at ON competitor_posts (posted_at);
-- one line per export, counted the way Semrush's own screen counts (every listed position, map and AI results included)
CREATE TABLE IF NOT EXISTS semrush_totals (
  domain TEXT NOT NULL, country TEXT NOT NULL, day TEXT NOT NULL, positions INTEGER NOT NULL, traffic INTEGER NOT NULL,
  top3 INTEGER NOT NULL, top10 INTEGER NOT NULL, PRIMARY KEY (domain, country, day)
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
    "semrush_files", "semrush_keywords", "semrush_competitors", "semrush_totals", "search_page_daily",
    "traffic_site_daily", "search_site_daily", "query_site_daily",
    "competitors", "competitor_sources", "competitor_seen", "competitor_signals", "competitor_accounts", "competitor_posts",
    "meta_campaigns", "meta_adsets", "meta_ads", "meta_ad_daily", "meta_breakdown_daily", "meta_events", "meta_audiences",
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
ADDED_COLUMNS = [("events", "kind", "TEXT NOT NULL DEFAULT 'booth'"), ("event_steps", "critical", "INTEGER NOT NULL DEFAULT 0"),
                 ("playbook_steps", "kinds", "TEXT"),  # comma list of event kinds the step is for; empty = every kind
                 ("playbook_steps", "critical", "INTEGER NOT NULL DEFAULT 0"), ("event_costs", "planned", "REAL"),
                 ("leads", "first_touch_at", "TEXT"),  # the first time an owner touched the lead; written once, for follow-up speed
                 ("deals", "industry", "TEXT"), ("deals", "company_size", "TEXT"),  # labels given on the ideal customer page
                 ("traffic_daily", "engaged", "INTEGER NOT NULL DEFAULT 0"), ("traffic_site_daily", "engaged", "INTEGER NOT NULL DEFAULT 0"),
                 ("leads", "company_size", "TEXT"), ("deals", "lead_source", "TEXT"),
                 ("utm_map", "excluded", "INTEGER NOT NULL DEFAULT 0"),
                 ("leads", "industry_via", "TEXT"), ("leads", "size_via", "TEXT"),
                 # the tool's own id for a campaign, and its lifetime counts at the last sync (sent, opened, replied, meetings)
                 ("outbound_campaigns", "ext_id", "TEXT"), ("outbound_campaigns", "lifetime", "TEXT"),
                 ("ad_campaigns", "ext_id", "TEXT"), ("ad_creatives", "ext_id", "TEXT"),
                 ("competitor_posts", "comments", "INTEGER"), ("competitors", "own", "INTEGER NOT NULL DEFAULT 0"), ("leads", "qualify_override", "TEXT"), ("competitor_posts", "image", "TEXT"), ("competitor_accounts", "followers", "INTEGER"),
                 ("subscriptions", "email", "TEXT")]  # who to email when the renewal is near


def init_schema(conn):
    upgrade(conn)  # a new database also needs the columns added after the first release


def upgrade(conn):
    """Bring an existing database up to the current schema without touching its data."""
    conn.executescript(SCHEMA)
    for table, column, kind in ADDED_COLUMNS:
        if column not in {r["name"] for r in conn.execute("PRAGMA table_info({})".format(table))}:
            conn.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, column, kind))
    # there is one role now: a login made while there were two keeps the old "member" role, which would still limit it
    conn.execute("UPDATE accounts SET role = 'admin' WHERE role <> 'admin'")


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

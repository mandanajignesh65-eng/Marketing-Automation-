"""The assistant: answers a question about the marketing data in plain words.

The question goes to Google Gemini together with a list of the tables. Gemini asks for the figures it needs by
writing a read-only query, which is run here and the rows are sent back, until it can answer. It can only read:
the database is opened read-only, only the tables listed below are visible, and people's names, emails and
phone numbers on leads are never shown to it.

    GEMINI_API_KEY   from Google AI Studio
    GEMINI_MODEL     optional, which Gemini model to use
"""

import json
import sqlite3
import time
import urllib.error
import urllib.request

from . import config

URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
MODEL = "gemini-flash-latest"
STEPS = 6          # at most this many rounds of queries per question
MAX_ROWS = 60
MAX_WORK = 4_000_000  # database steps before a query is stopped

TABLES = ("leads", "deals", "channels", "channel_daily", "ad_campaigns", "ad_creatives", "ad_daily", "outbound_campaigns", "outbound_daily",
          "traffic_daily", "traffic_site_daily", "search_daily", "search_site_daily", "query_daily", "page_daily", "form_daily", "companies",
          "competitors", "competitor_signals", "competitor_posts", "subscriptions", "targets",
          "meta_campaigns", "meta_adsets", "meta_ads", "meta_ad_daily")
HIDDEN = {"leads": {"name", "email", "zoho_id", "deal_zoho_id"}, "deals": {"zoho_id"}, "subscriptions": {"email"}}

RULES = """You are the assistant inside Meridian, the marketing dashboard of Chat360, a company that sells AI chat and voice agents to businesses in India.
Answer the marketer's question from the data, using the query tool. Never guess a figure: look it up. If the data cannot answer it, say so in one line.

How to answer: plain simple words, short, the answer first. No jargon, no SQL, no table names, no markdown symbols. Use a short list with one item per line when comparing things. Money is in Indian rupees: write it like ₹4.2 lakh or ₹1.3 crore. Say which period a figure covers.

About the data (SQLite, dates are text like 2026-10-14 or 2026-10-14T09:30:00, today is {today}):
- leads: one row per lead. status is New, Contacted, Qualified or Unqualified. channel_id joins channels.id. created_at is when it came in. title is the job title. company, industry, company_size, lead_source describe it. score is 0 to 100.
- deals: one row per deal. stage is 'won', 'lost' or 'open'. amount is rupees. closed_at is when it was won or lost. Win rate = won / (won + lost). For a typical deal size use the middle value, not the average, because a few deals are very large.
- channels: where leads come from (name). channel_daily: impressions, clicks and spend per channel per day.
- ad_daily joins ad_creatives (creative_id) which joins ad_campaigns: paid ad spend, impressions, clicks, leads per day.
- outbound_daily joins outbound_campaigns: emails and LinkedIn messages sent, opened, replied, meetings per day.
- traffic_daily and traffic_site_daily: website visits (sessions) per day by source. search_daily, query_daily, page_daily: Google search clicks and impressions. form_daily: form views and submissions.
- competitors, competitor_signals (news and updates about them: category, title, published_at or first_seen), competitor_posts (their LinkedIn posts and YouTube videos: network, title, posted_at, likes, comments, views). The competitors row with own = 1 is Chat360 itself.
- subscriptions: the tools the team pays for. targets: monthly targets.

Tables and columns you can read:
{schema}"""

TOOL = [{"functionDeclarations": [{
    "name": "query", "description": "Run one read-only SQLite SELECT and get the rows back. At most {} rows come back, so count, sum and group in the query.".format(MAX_ROWS),
    "parameters": {"type": "OBJECT", "properties": {"sql": {"type": "STRING", "description": "One SELECT statement."}}, "required": ["sql"]}}]}]


class AssistantError(Exception):
    """A problem the person using this can act on."""


def ready():
    return bool(config.setting("GEMINI_API_KEY"))


# the screen each table is shown on, so an answer can say where its figures can be checked
PAGES = {"leads": ("Leads", "leads"), "companies": ("Leads", "leads"), "deals": ("Funnel", "funnel"), "channels": ("Channels", "channels"),
         "channel_daily": ("Channels", "channels"), "ad_campaigns": ("Paid ads", "paid"), "ad_creatives": ("Paid ads", "paid"), "ad_daily": ("Paid ads", "paid"),
         "meta_campaigns": ("Paid ads", "paid"), "meta_adsets": ("Paid ads", "paid"), "meta_ads": ("Paid ads", "paid"), "meta_ad_daily": ("Paid ads", "paid"),
         "outbound_campaigns": ("Outbound", "outbound"), "outbound_daily": ("Outbound", "outbound"),
         "traffic_daily": ("Website & organic", "web"), "traffic_site_daily": ("Website & organic", "web"), "search_daily": ("Website & organic", "web"),
         "search_site_daily": ("Website & organic", "web"), "query_daily": ("Website & organic", "web"), "page_daily": ("Website & organic", "web"),
         "form_daily": ("Website & organic", "web"), "competitors": ("Competitors", "competitors"), "competitor_signals": ("Competitors", "competitors"),
         "competitor_posts": ("Competitors", "competitors?view=social"), "subscriptions": ("Subscriptions", "subs"), "targets": ("Targets", "targets")}


def guard(action, first, second, database, trigger):
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and first in TABLES:
        return sqlite3.SQLITE_IGNORE if second in HIDDEN.get(first, ()) else sqlite3.SQLITE_OK  # a hidden column reads as empty
    return sqlite3.SQLITE_DENY


def reader(path=None):
    """A connection that can only read the listed tables."""
    conn = sqlite3.connect("file:{}?mode=ro".format(path or config.db_path()), uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def schema(conn):
    lines = []
    for t in TABLES:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info({})".format(t)) if r["name"] not in HIDDEN.get(t, ())]
        if cols:
            lines.append("{}({})".format(t, ", ".join(cols)))
    return "\n".join(lines)


def run(conn, sql, used=None):
    """Run one query under the guard. Returns what is sent back to the model: the rows, or why it did not run.

    used, when given, collects the tables a query that worked read from."""
    sql = (sql or "").strip().rstrip(";")
    if not sql.lower().startswith(("select", "with")) or ";" in sql:
        return dict(error="Only one SELECT statement is allowed.")
    work = [0]

    def tick():
        work[0] += 1
        return work[0] > MAX_WORK // 10000
    read = set()

    def watch(action, first, second, database, trigger):
        if action == sqlite3.SQLITE_READ and first in TABLES:
            read.add(first)
        return guard(action, first, second, database, trigger)
    conn.set_authorizer(watch)
    conn.set_progress_handler(tick, 10000)
    try:
        cur = conn.execute(sql)
        rows = cur.fetchmany(MAX_ROWS + 1)
        if used is not None:
            used.update(read)
        cols = [c[0] for c in cur.description or []]
        out = [[(v[:200] if isinstance(v, str) else v) for v in r] for r in rows[:MAX_ROWS]]
        return dict(columns=cols, rows=out, more_rows_not_shown=len(rows) > MAX_ROWS)
    except sqlite3.Error as err:
        return dict(error="interrupted: the query took too long, make it simpler" if "interrupt" in str(err) else str(err)[:300])
    finally:
        conn.set_authorizer(None)
        conn.set_progress_handler(None, 0)


FALLBACKS = ("gemini-flash-lite-latest", "gemini-2.5-flash")  # tried when the first model is too busy


def call(body):
    """One request to Gemini. A busy model is tried again, then the next model is tried."""
    models = list(dict.fromkeys((config.setting("GEMINI_MODEL", MODEL),) + FALLBACKS))
    last = None
    for model in models:
        for attempt in range(2):
            req = urllib.request.Request(URL.format(model), data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "x-goog-api-key": config.setting("GEMINI_API_KEY")})
            try:
                with urllib.request.urlopen(req, timeout=60) as res:
                    return json.load(res)
            except urllib.error.HTTPError as err:
                last = err.code
                if err.code in (401, 403) or (err.code == 400 and "API key" in err.read().decode("utf-8", "ignore")):
                    raise AssistantError("The assistant's key was not accepted.")
                if err.code in (500, 502, 503, 504) and attempt == 0:
                    time.sleep(1.5)
                    continue
                break  # busy, over its limit or not available: the next model
            except (urllib.error.URLError, OSError, ValueError):
                last = None
                break
    if last == 429:
        raise AssistantError("The free limit for today is used up. Try again in a while.")
    raise AssistantError("The assistant is busy just now. Try again in a minute.")


def ask(question, history=(), today="", path=None):
    """Answer one question. history is the earlier turns as (role, text) with role 'user' or 'assistant'."""
    if not ready():
        raise AssistantError("The assistant is not set up yet.")
    question = (question or "").strip()[:600]
    if not question:
        raise AssistantError("Type a question.")
    conn = reader(path)
    try:
        contents = [dict(role="model" if role == "assistant" else "user", parts=[dict(text=str(text)[:1500])]) for role, text in list(history)[-8:]]
        contents.append(dict(role="user", parts=[dict(text=question)]))
        body = dict(systemInstruction=dict(parts=[dict(text=RULES.replace("{today}", today).replace("{schema}", schema(conn)))]),
                    tools=TOOL, contents=contents, generationConfig=dict(temperature=0.2))
        used = set()

        def done(text):
            pages = list(dict.fromkeys(PAGES[t] for t in TABLES if t in used and t in PAGES))
            return dict(answer=text, sources=[dict(label=label, to=to) for label, to in pages])
        for _ in range(STEPS):
            found = (call(body).get("candidates") or [{}])[0].get("content") or {}
            parts = found.get("parts") or []
            asks = [p["functionCall"] for p in parts if p.get("functionCall")]
            if not asks:
                text = "".join(p.get("text") or "" for p in parts if not p.get("thought")).strip()
                return done(text or "I could not work that out from the data.")
            contents.append(found)
            contents.append(dict(role="user", parts=[dict(functionResponse=dict(name=a.get("name") or "query", response=run(conn, (a.get("args") or {}).get("sql"), used)))
                                                     for a in asks]))
        return dict(answer="That needed more steps than I am allowed. Try asking for one thing at a time.", sources=[])
    finally:
        conn.close()

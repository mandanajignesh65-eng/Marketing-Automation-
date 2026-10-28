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
STEPS = 10         # at most this many rounds of queries per question
MAX_ROWS = 60
MAX_WORK = 4_000_000  # database steps before a query is stopped

TABLES = ("leads", "deals", "channels", "channel_daily", "ad_campaigns", "ad_creatives", "ad_daily", "outbound_campaigns", "outbound_daily",
          "traffic_daily", "traffic_site_daily", "search_daily", "search_site_daily", "query_daily", "page_daily", "form_daily", "companies",
          "competitors", "competitor_signals", "competitor_posts", "subscriptions", "targets",
          "meta_campaigns", "meta_adsets", "meta_ads", "meta_ad_daily")
HIDDEN = {"leads": {"name", "email", "zoho_id", "deal_zoho_id"}, "deals": {"zoho_id"}, "subscriptions": {"email"}}

RULES = """You are the marketing analyst inside Meridian, the marketing dashboard of Chat360. Chat360 sells AI chat and voice agents (WhatsApp, voice, web) to businesses, mostly in India. The person asking is on the marketing team. They are not technical. Today is {today}.

YOUR JOB
Help them understand how marketing is doing and decide what to do next: which channels, industries, company sizes and job titles to go after, what is working, what is not, what changed, what competitors are doing. Act like a sharp colleague who has the data open, not like a search box.

HOW TO WORK
1. Understand what they really want. Fix typos and read follow-ups using the earlier messages ("and the second one?" continues the last question). Marketing shorthand is normal: ICP = ideal customer profile (the kind of company that buys most often and pays most), persona = the kind of person we talk to (job title, department, seniority), CPL = cost per lead, CAC = cost to win a customer, MQL/SQL = qualified lead, pipeline = value of open deals, win rate = won / (won + lost), conversion = share that moves to the next step, ROAS = revenue / ad spend.
2. Always look at the data before answering, with the query tool. Never guess or invent a figure, a name or a category. If you say it, a query must have shown it.
3. Use several queries when the question needs it. A question like "who should I target next" needs the win rate, deal size and volume by industry, by company size, by channel and by job title, then a conclusion. Run them, then answer. Do not stop after one query and do not give up because one query returned nothing: try another way (a different column, a wider period, a looser match).
4. Judge the evidence. Only call something the best or worst when it has enough behind it: at least 5 closed deals for a win rate, at least 20 leads for a lead figure. If the numbers are thin, say so in a few words and give the best reading anyway. Leave out groups named Unknown, Not available, Other or blank when ranking, and say how much of the data they cover if it is large. The data is typed by hand, so clean it as you read it: the same thing is often spelled several ways (BFSI, Banking, BANKING, Financial Services are one industry; "51-200 employees" and "SMB (<200 Emp)" are one size), so add them together; and a value that is plainly in the wrong field (a size word like Enterprise or SMB in the industry field) counts as unknown, not as an industry.
5. If no period is given, use the last 12 months for leads and all time for deals, and say which you used. "This month" means the calendar month so far. Compare with the period before when it helps.
6. Only if the question truly cannot be answered from this data (it needs something not stored here), say what is missing in one line and offer the nearest thing you can answer. Ask a short question back only when the request is genuinely ambiguous.

HOW TO ANSWER
- The answer first, in one or two plain sentences. Then the figures that back it, a few short lines, one fact per line starting with "- ". For advice questions end with one line that begins "Next:" saying what to do.
- Plain everyday words. No SQL, no table or column names, no markdown symbols like ** or #, no headings. Keep it under about 120 words unless they ask for detail.
- Always give the count behind a percentage (for example "31% win rate, 16 won of 52 closed").
- Money is Indian rupees: ₹4.2 lakh, ₹1.3 crore. Round sensibly.
- Do not show names or emails of individual people. Company names are fine.

THE DATA (SQLite; dates are text like 2026-10-14 or 2026-10-14T09:30:00, so compare with >= and <, and use substr(col,1,7) for a month)
- leads: one row per lead. created_at = when it came in. channel_id joins channels.id (channels.name is the source, channels.grp is organic, paid, outbound or events). status = the stage in Zoho CRM (New, Contacted, Qualified, Meeting booked or Unqualified); never use it to count qualified leads. score 0-100. A qualified lead is one where (COALESCE(qualify_override, '') = 'yes' OR (score >= {pass_mark} AND COALESCE(qualify_override, '') <> 'no')); always use exactly this for qualified. title = job title (use it for personas: group with LIKE, e.g. '%market%', '%founder%', '%ceo%', '%head%', '%manager%', '%director%'). company, industry, company_size (text band), employees, hq (city), lead_source, utm_source, utm_campaign.
- deals: one row per deal. stage = 'won', 'lost' or 'open'. amount in rupees. created_at = when it started, closed_at = when won or lost. channel_id joins channels. lead_id joins leads.id, which gives the job title, company and city behind a deal. Industry of a deal = COALESCE(deals.industry, the lead's industry); size = COALESCE(deals.company_size, the lead's company_size). For a typical deal size use the middle value (median), not the average, because a few deals are very large.
- channel_daily: impressions, clicks, spend per channel per day. ad_daily joins ad_creatives (creative_id) then ad_campaigns: paid spend, impressions, clicks, leads per day. meta_* tables: Meta ads in more detail.
- outbound_daily joins outbound_campaigns: messages sent, opened (for LinkedIn this means accepted), replied, meetings per day.
- traffic_daily, traffic_site_daily: website visits (sessions) by source. search_daily, query_daily, page_daily: Google search clicks and impressions. form_daily: form views and submissions.
- competitors (own = 1 is Chat360 itself), competitor_signals (their news: category, title, published_at or first_seen), competitor_posts (their LinkedIn posts and YouTube videos: network, title, posted_at, likes, comments, views).
- subscriptions: tools the team pays for. targets: monthly targets.

WHAT IS IN THE DATA RIGHT NOW
{profile}

TABLES AND COLUMNS YOU CAN READ
{schema}"""


def profile(conn):
    """A short picture of what the data holds today (sizes, date range, the values in use), so questions are read against real names."""
    def rows(sql):
        try:
            return conn.execute(sql).fetchall()
        except sqlite3.Error:
            return []

    def top(sql):
        return ", ".join("{} ({})".format(r[0], r[1]) for r in rows(sql)) or "none"
    span = (rows("SELECT COUNT(*), MIN(substr(created_at, 1, 10)), MAX(substr(created_at, 1, 10)) FROM leads") or [(0, None, None)])[0]
    return "\n".join([
        "- Leads: {} in all, from {} to {}.".format(span[0], span[1], span[2]),
        "- Deals by stage: " + top("SELECT stage, COUNT(*) FROM deals GROUP BY 1 ORDER BY 2 DESC") + ".",
        "- Channels (leads in the last 12 months): " + top(
            "SELECT c.name, COUNT(l.id) FROM channels c LEFT JOIN leads l ON l.channel_id = c.id AND l.created_at >= date('now', '-12 months') GROUP BY c.id ORDER BY 2 DESC") + ".",
        "- Lead status: " + top("SELECT status, COUNT(*) FROM leads GROUP BY 1 ORDER BY 2 DESC LIMIT 6") + ".",
        "- Most common industries on leads: " + top("SELECT industry, COUNT(*) FROM leads WHERE industry IS NOT NULL AND industry <> '' GROUP BY 1 ORDER BY 2 DESC LIMIT 15") + ".",
        "- Industries written on deals: " + top("SELECT industry, COUNT(*) FROM deals WHERE industry IS NOT NULL AND industry <> '' GROUP BY 1 ORDER BY 2 DESC LIMIT 12") + ".",
        "- Company size bands: " + top("SELECT company_size, COUNT(*) FROM leads WHERE company_size IS NOT NULL AND company_size <> '' GROUP BY 1 ORDER BY 2 DESC LIMIT 8") + ".",
        "- Leads with a job title: " + top("SELECT CASE WHEN title IS NULL OR title = '' THEN 'no title' ELSE 'has title' END, COUNT(*) FROM leads GROUP BY 1") + ".",
        "- Competitors watched: " + top("SELECT name, (SELECT COUNT(*) FROM competitor_posts p WHERE p.competitor_id = c.id) FROM competitors c WHERE active = 1") + " (posts held).",
    ])


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
        try:
            from . import db as _db, scoring
            live = _db.connect()
            try:
                pass_mark = str(scoring.threshold(live))
            finally:
                live.close()
        except Exception:
            pass_mark = "the pass mark"
        rules = RULES.replace("{today}", today).replace("{pass_mark}", pass_mark).replace("{profile}", profile(conn)).replace("{schema}", schema(conn))
        body = dict(systemInstruction=dict(parts=[dict(text=rules)]), tools=TOOL, contents=contents, generationConfig=dict(temperature=0.2))
        nudged = False
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
                if not text and not nudged:  # it stopped without saying anything: ask once for the answer
                    nudged = True
                    contents.append(dict(role="user", parts=[dict(text="Give your answer now from what you have found. If you have not looked yet, look first.")]))
                    continue
                return done(text or "I could not work that out. Try asking it another way.")
            contents.append(found)
            contents.append(dict(role="user", parts=[dict(functionResponse=dict(name=a.get("name") or "query", response=run(conn, (a.get("args") or {}).get("sql"), used)))
                                                     for a in asks]))
        body.pop("tools")  # out of rounds: answer from what was found, no more queries
        contents.append(dict(role="user", parts=[dict(text="Stop looking things up. Answer now from what you have found so far.")]))
        parts = ((call(body).get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return done("".join(p.get("text") or "" for p in parts if not p.get("thought")).strip() or "That needed more steps than I am allowed. Try asking for one thing at a time.")
    finally:
        conn.close()

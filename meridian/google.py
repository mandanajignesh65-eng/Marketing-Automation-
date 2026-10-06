"""Website figures from Google: sessions and page views from Google Analytics 4, search clicks, queries and
positions from Search Console.

    python -m meridian.google connect   sign in with Google, choose the property and site, then bring the history in
    python -m meridian.google sync      bring in the latest days now
    python -m meridian.google status    what is connected and how much it holds

Both are read with view-only permission and nothing in Google is changed. The first sync reaches back a year;
later ones re-read the last few days, because Google keeps revising recent figures (Search Console runs two to
three days behind). Only totals come in: sessions per source, views per page, clicks per search query. Google
does not hand over anything about individual visitors.
"""

import http.server
import json
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta

from . import config, db
from .periods import iso

SCOPES = "https://www.googleapis.com/auth/analytics.readonly https://www.googleapis.com/auth/webmasters.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GA_DATA = "https://analyticsdata.googleapis.com/v1beta"
GA_ADMIN = "https://analyticsadmin.googleapis.com/v1beta"
GSC = "https://www.googleapis.com/webmasters/v3"
EVERY_HOURS = 4
HISTORY_DAYS = 365
RELOOK_DAYS = 7
CHUNK_DAYS = 31
PAGE_ROWS = 25000
MAX_ROWS = 200000  # per month and report: a stop for a runaway, far above what a marketing site produces
NAMES = {"ga4": "Google Analytics", "gsc": "Search Console"}


class GoogleError(Exception):
    """A problem the person running the sync can act on."""


def credentials():
    return tuple(config.setting(k) for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"))


def targets():
    """Which source reads what: the Analytics property ids and the Search Console sites (several are separated by commas)."""
    return {"ga4": several(config.setting("GA4_PROPERTY_ID")), "gsc": several(config.setting("GSC_SITE_URL"))}


def several(text):
    return [part.strip() for part in text.split(",") if part.strip()]


def configured(source=None):
    if not all(credentials()):
        return False
    return bool(targets()[source]) if source else any(targets().values())


def fetch(method, url, body=None, token=None, form=None):
    headers = {"Accept": "application/json", "User-Agent": "Meridian/1.0"}
    data = None
    if form is not None:
        data, headers["Content-Type"] = urllib.parse.urlencode(form).encode(), "application/x-www-form-urlencoded"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            raw = res.read()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read())
        except ValueError:
            detail = {}
        error = detail.get("error")
        message = (error.get("message") if isinstance(error, dict) else detail.get("error_description") or error) or "error {}".format(err.code)
        if error == "invalid_grant":
            message = "Google no longer accepts the saved sign-in. Run ./connect-google.sh in Terminal to sign in again."
        elif "has not been used in project" in message or "is disabled" in message:
            message = "A Google API is not switched on for your project yet. " + message.split(" If you enabled")[0]
        raise GoogleError("Google: " + message)
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise GoogleError("Could not reach Google: {}".format(getattr(err, "reason", err)))


def access_token(creds=None):
    client_id, client_secret, refresh = creds or credentials()
    return fetch("POST", TOKEN_URL, form=dict(client_id=client_id, client_secret=client_secret, refresh_token=refresh,
                                             grant_type="refresh_token"))["access_token"]


def chunks(start, end):
    day = start
    while day <= end:
        until = min(day + timedelta(days=CHUNK_DAYS - 1), end)
        yield day, until
        day = until + timedelta(days=1)


def window(conn, source, now):
    """The days to read: a year the first time, the last week after that."""
    row = conn.execute("SELECT last_sync_at FROM sources WHERE key = ?", (source,)).fetchone()
    first = not (row and row["last_sync_at"])
    return now.date() - timedelta(days=HISTORY_DAYS if first else RELOOK_DAYS), now.date()


def mark(conn, source, now, status="connected", note=None):
    conn.execute("UPDATE sources SET status = ?, last_sync_at = COALESCE(?, last_sync_at), note = ? WHERE key = ?",
                 (status, iso(now) if status == "connected" else None, note, source))


# ------------------------------------------------------------------------------- Google Analytics

def ga_report(token, prop, start, end, dimensions, metric):
    rows, offset = [], 0
    while True:
        data = fetch("POST", "{}/properties/{}:runReport".format(GA_DATA, prop), dict(
            dateRanges=[dict(startDate=start.isoformat(), endDate=end.isoformat())],
            dimensions=[dict(name=d) for d in dimensions], metrics=[dict(name=metric)], limit=PAGE_ROWS, offset=offset), token)
        got = data.get("rows") or []
        for r in got:
            keys = [v.get("value", "") for v in r.get("dimensionValues") or []]
            keys[0] = "{}-{}-{}".format(keys[0][:4], keys[0][4:6], keys[0][6:8])  # 20261005 -> 2026-10-05
            rows.append((keys, int(float((r.get("metricValues") or [{}])[0].get("value") or 0))))
        offset += len(got)
        if not got or offset >= int(data.get("rowCount") or 0) or offset >= MAX_ROWS:
            return rows


def sync_ga4(conn, now, token):
    props = targets()["ga4"]
    start, end = window(conn, "ga4", now)
    traffic, pages = {}, {}
    for prop in props:
        for a, b in chunks(start, end):
            for (day, source, medium), n in ga_report(token, prop, a, b, ["date", "sessionSource", "sessionMedium"], "sessions"):
                key = (day, source or "(not set)", medium or "(not set)")
                traffic[key] = traffic.get(key, 0) + n
            for (day, host, path, title), n in ga_report(token, prop, a, b, ["date", "hostName", "pagePath", "pageTitle"], "screenPageViews"):
                if len(props) > 1:  # several sites: say which one a page belongs to, since each has its own "/"
                    path = host + path
                views, best, name = pages.get((day, path), (0, 0, ""))  # one row per page: views added up, the commonest title kept
                pages[(day, path)] = (views + n, max(best, n), title if n > best else name)
    # the same visits per website; the first time this needs the whole year, like any first sync
    fresh = not conn.execute("SELECT 1 FROM traffic_site_daily LIMIT 1").fetchone()
    site_start = now.date() - timedelta(days=HISTORY_DAYS) if fresh else start
    by_site = {}
    for prop in props:
        for a, b in chunks(site_start, end):
            for (day, host, source, medium), n in ga_report(token, prop, a, b, ["date", "hostName", "sessionSource", "sessionMedium"], "sessions"):
                key = (day, site_name(host) or "(not set)", source or "(not set)", medium or "(not set)")
                by_site[key] = by_site.get(key, 0) + n
    conn.execute("DELETE FROM traffic_site_daily WHERE date >= ?", (site_start.isoformat(),))
    conn.executemany("INSERT INTO traffic_site_daily (date, site, source, medium, sessions) VALUES (?,?,?,?,?)", [k + (v,) for k, v in by_site.items() if v])
    conn.execute("DELETE FROM traffic_daily WHERE date >= ?", (start.isoformat(),))
    conn.executemany("INSERT INTO traffic_daily (date, source, medium, sessions) VALUES (?,?,?,?)", [k + (v,) for k, v in traffic.items() if v])
    # Analytics knows views per page, not leads per page, so that column stays empty.
    conn.execute("DELETE FROM page_daily WHERE date >= ?", (start.isoformat(),))
    conn.executemany("INSERT INTO page_daily (date, path, title, views) VALUES (?,?,?,?)",
                     [(d, p, t if t and t != "(not set)" else None, v) for (d, p), (v, _, t) in pages.items() if v])
    mark(conn, "ga4", now)
    return dict(source="ga4", days=(end - start).days + 1, sessions=sum(traffic.values()), pages=len({p for _, p in pages}))


# ------------------------------------------------------------------------------- Search Console

def gsc_rows(token, site, start, end, dimensions):
    rows, at = [], 0
    url = "{}/sites/{}/searchAnalytics/query".format(GSC, urllib.parse.quote(site, safe=""))
    while True:
        data = fetch("POST", url, dict(startDate=start.isoformat(), endDate=end.isoformat(), dimensions=dimensions,
                                      rowLimit=PAGE_ROWS, startRow=at), token)
        got = data.get("rows") or []
        rows += got
        at += len(got)
        if len(got) < PAGE_ROWS or at >= MAX_ROWS:
            return rows


def combine(rows):
    """Rows for the same day (and query) from several sites become one: clicks and impressions added, position averaged by impressions."""
    out = {}
    for r in rows:
        key, imp = tuple(r["keys"]), int(r.get("impressions") or 0)
        o = out.setdefault(key, dict(keys=list(key), clicks=0, impressions=0, weight=0.0, position=None))
        o["clicks"] += int(r.get("clicks") or 0)
        o["impressions"] += imp
        if r.get("position") is not None:
            o["weight"] += r["position"] * max(imp, 1)
            o["position"] = o["weight"] / max(o["impressions"], 1) if o["impressions"] else r["position"]
    return list(out.values())


def site_name(text):
    """A site as it is named everywhere in Meridian: chat360.io, whether it came as sc-domain:chat360.io, https://www.chat360.io/ or a host name."""
    return re.sub(r"^(sc-domain:|https?://)", "", (text or "").strip().lower()).split("/")[0].replace("www.", "", 1)


def page_key(url):
    """A page's address without the scheme, "www.", query or trailing slash: chat360.io/blog/post. The same for Analytics and Search Console."""
    text = re.sub(r"^https?://", "", (url or "").strip().lower()).split("#")[0].split("?")[0]
    text = re.sub(r"^www\.", "", text)
    return text.rstrip("/") + ("/" if "/" not in text.rstrip("/") else "")


def sync_gsc(conn, now, token):
    start, end = window(conn, "gsc", now)
    # pages were added later than queries: the first time, they need the whole year like any first sync
    fresh = not conn.execute("SELECT 1 FROM search_page_daily LIMIT 1").fetchone()
    page_start = now.date() - timedelta(days=HISTORY_DAYS) if fresh else start
    days, queries, pages = [], [], []
    # each site's own figures are kept too; the first time they need the whole year
    site_fresh = not conn.execute("SELECT 1 FROM search_site_daily LIMIT 1").fetchone()
    site_start = now.date() - timedelta(days=HISTORY_DAYS) if site_fresh else start
    conn.execute("DELETE FROM search_site_daily WHERE date >= ?", (site_start.isoformat(),))
    conn.execute("DELETE FROM query_site_daily WHERE date >= ?", (site_start.isoformat(),))
    for site in targets()["gsc"]:
        name = site_name(site)
        for a, b in chunks(site_start, end):
            own_days, own_queries = gsc_rows(token, site, a, b, ["date"]), gsc_rows(token, site, a, b, ["date", "query"])
            conn.executemany("INSERT OR REPLACE INTO search_site_daily (date, site, clicks, impressions, position) VALUES (?,?,?,?,?)",
                             [(r["keys"][0], name, int(r.get("clicks") or 0), int(r.get("impressions") or 0), r.get("position")) for r in own_days])
            conn.executemany("INSERT OR REPLACE INTO query_site_daily (date, site, query, clicks, impressions, position) VALUES (?,?,?,?,?,?)",
                             [(r["keys"][0], name, r["keys"][1], int(r.get("clicks") or 0), int(r.get("impressions") or 0), r.get("position")) for r in own_queries])
            first_day = start.isoformat()  # the combined tables below are only refreshed for the usual window
            days += [r for r in own_days if r["keys"][0] >= first_day]
            queries += [r for r in own_queries if r["keys"][0] >= first_day]
        for a, b in chunks(page_start, end):
            pages += gsc_rows(token, site, a, b, ["date", "page"])
    for r in pages:
        r["keys"][1] = page_key(r["keys"][1])
    days, queries, pages = combine(days), combine(queries), combine(pages)
    conn.execute("DELETE FROM search_page_daily WHERE date >= ?", (page_start.isoformat(),))
    conn.executemany("INSERT OR REPLACE INTO search_page_daily (date, page, clicks, impressions, position) VALUES (?,?,?,?,?)",
                     [(r["keys"][0], r["keys"][1], r["clicks"], r["impressions"], r.get("position")) for r in pages])
    first = start.isoformat()
    conn.execute("DELETE FROM search_daily WHERE date >= ?", (first,))
    conn.executemany("INSERT OR REPLACE INTO search_daily (date, position) VALUES (?,?)",
                     [(r["keys"][0], r.get("position") or 0) for r in days if r.get("impressions")])
    conn.execute("UPDATE channel_daily SET impressions = 0, clicks = 0 WHERE channel_id = 'search' AND date >= ?", (first,))
    conn.executemany(
        "INSERT INTO channel_daily (date, channel_id, impressions, clicks) VALUES (?, 'search', ?, ?) "
        "ON CONFLICT (date, channel_id) DO UPDATE SET impressions = excluded.impressions, clicks = excluded.clicks",
        [(r["keys"][0], int(r.get("impressions") or 0), int(r.get("clicks") or 0)) for r in days])
    conn.execute("DELETE FROM query_daily WHERE date >= ?", (first,))
    conn.executemany("INSERT OR REPLACE INTO query_daily (date, query, clicks, impressions, position) VALUES (?,?,?,?,?)",
                     [(r["keys"][0], r["keys"][1], int(r.get("clicks") or 0), int(r.get("impressions") or 0), r.get("position")) for r in queries])
    mark(conn, "gsc", now, note="two to three days behind")
    return dict(source="gsc", days=(end - start).days + 1, clicks=sum(int(r.get("clicks") or 0) for r in days),
                queries=len({r["keys"][1] for r in queries}))


# ------------------------------------------------------------------------------- running

SYNCS = {"ga4": sync_ga4, "gsc": sync_gsc}


def sync(conn, now, source, token=None):
    if not configured(source):
        raise GoogleError("{} is not connected. Run ./connect-google.sh in Terminal.".format(NAMES[source]))
    try:
        summary = SYNCS[source](conn, now, token or access_token())
    except GoogleError as err:
        conn.rollback()
        mark(conn, source, now, "disconnected", str(err))
        conn.commit()
        raise
    conn.commit()
    return summary


def due(conn, now, source):
    row = conn.execute("SELECT status, last_sync_at FROM sources WHERE key = ?", (source,)).fetchone()
    if row and row["status"] == "disconnected":  # the last try failed: wait for "Reconnect" in Settings
        return False
    return not row or not row["last_sync_at"] or now - datetime.fromisoformat(row["last_sync_at"]) >= timedelta(hours=EVERY_HOURS)


def describe(s):
    if s["source"] == "ga4":
        return "Google Analytics {:,} sessions across {:,} pages in the {:,} days read".format(s["sessions"], s["pages"], s["days"])
    return "Search Console {:,} clicks from {:,} search queries in the {:,} days read".format(s["clicks"], s["queries"], s["days"])


# ------------------------------------------------------------------------------- command line

STEPS = """
Google asks for a small one-time setup so that only you can let Meridian read your figures.

1. Open https://console.cloud.google.com/projectcreate signed in with the Google account that can see your
   Analytics and Search Console. Name the project Meridian and click Create. Make sure it is selected at the top.
2. Switch on three APIs. Open each link and click "Enable":
     https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com
     https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com
     https://console.cloud.google.com/apis/library/searchconsole.googleapis.com
3. Open https://console.cloud.google.com/auth/overview and click "Get started". App name Meridian, your email,
   audience "Internal" (if only "External" is offered, choose it, and afterwards open "Audience" and click
   "Publish app"). Finish the form.
4. Open https://console.cloud.google.com/auth/clients and click "Create client". Application type "Desktop app",
   name Meridian, Create. Copy the Client ID and Client secret it shows and paste them below.
"""


def sign_in(client_id, client_secret):
    """Open Google's sign-in page and wait on this computer for Google to hand back the one-time code."""
    state, got = secrets.token_urlsafe(16), {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state:
                got.update(code=q.get("code", [""])[0], error=q.get("error", [""])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<p style='font:16px sans-serif;margin:40px'>Meridian has what it needs. You can close this tab and go back to Terminal.</p>".encode())

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = "http://127.0.0.1:{}".format(server.server_port)
    url = AUTH_URL + "?" + urllib.parse.urlencode(dict(client_id=client_id, redirect_uri=redirect, response_type="code", scope=SCOPES,
                                                       access_type="offline", prompt="consent", state=state))
    print("\nA browser window is opening. Choose your Google account and click Allow (view-only access).")
    print("If it does not open, copy this address into your browser:\n\n  {}\n".format(url))
    webbrowser.open(url)
    server.timeout, deadline = 5, time.time() + 600
    while not got and time.time() < deadline:
        server.handle_request()
    server.server_close()
    if not got.get("code"):
        raise GoogleError("Google sign-in was not completed ({}).".format(got.get("error") or "no answer"))
    tokens = fetch("POST", TOKEN_URL, form=dict(client_id=client_id, client_secret=client_secret, code=got["code"],
                                               redirect_uri=redirect, grant_type="authorization_code"))
    if not tokens.get("refresh_token"):
        raise GoogleError("Google did not give a lasting sign-in. Run the script again and click Allow on every box.")
    return tokens["refresh_token"]


def choose(what, options):
    """Pick one or more of (value, label) by number, e.g. 1 or 1,6; a single option is taken as it is."""
    if not options:
        print("\nThis Google account cannot see any {}. It will be left unconnected.".format(what))
        return ""
    if len(options) == 1:
        print("\n{}: {}".format(what.capitalize(), options[0][1]))
        return options[0][0]
    print("\nWhich {}? For more than one, separate the numbers with commas, like 1,6.".format(what))
    for i, (_, label) in enumerate(options, 1):
        print("  {}. {}".format(i, label))
    while True:
        answer = input("Type a number (or press Return to skip): ").strip()
        if not answer:
            return ""
        picks = answer.replace(",", " ").split()
        if picks and all(n.isdigit() and 1 <= int(n) <= len(options) for n in picks):
            return ",".join(dict.fromkeys(options[int(n) - 1][0] for n in picks))


def cmd_connect():
    import getpass
    from . import zoho
    print(__doc__.split("\n\n")[0])
    client_id, client_secret, _ = credentials()
    if client_id and client_secret and input("\nA Google project is already saved. Press Return to use it, or type N to enter a new one: ").strip().lower().startswith("n"):
        client_id = client_secret = ""
    if not (client_id and client_secret):
        print(STEPS)
        client_id = input("Client ID: ").strip()
        client_secret = getpass.getpass("Client secret (hidden as you paste): ").strip()
        if not (client_id and client_secret):
            sys.exit("Both values are needed. Nothing was saved.")
    refresh = sign_in(client_id, client_secret)
    creds = (client_id, client_secret, refresh)
    token = access_token(creds)
    properties = [(p["property"].split("/")[-1], "{} ({})".format(p.get("displayName") or p["property"], a.get("displayName") or "account"))
                  for a in fetch("GET", GA_ADMIN + "/accountSummaries?pageSize=200", token=token).get("accountSummaries") or []
                  for p in a.get("propertySummaries") or []]
    sites = [(s["siteUrl"], s["siteUrl"].replace("sc-domain:", "") + ("  (whole domain)" if s["siteUrl"].startswith("sc-domain:") else ""))
             for s in fetch("GET", GSC + "/sites", token=token).get("siteEntry") or [] if s.get("permissionLevel") != "siteUnverifiedUser"]
    prop = choose("Google Analytics property", properties)
    site = choose("Search Console site", sites)
    zoho.write_env(dict(GOOGLE_CLIENT_ID=client_id, GOOGLE_CLIENT_SECRET=client_secret, GOOGLE_REFRESH_TOKEN=refresh,
                        GA4_PROPERTY_ID=prop, GSC_SITE_URL=site))
    print("\nSaved to {} (readable only by you). Bringing in the past year; this can take a minute or two...".format(config.ENV_FILE))
    conn = zoho.live_database()
    for source in SYNCS:
        if targets()[source]:
            conn.execute("UPDATE sources SET last_sync_at = NULL WHERE key = ?", (source,))  # a new choice starts with the full year
            print("Synced:", describe(sync(conn, db.now(conn), source, token)) + ".")
    conn.close()
    print("Open the app and look at the Website screen.")


def main(argv):
    command = argv[0] if argv else ""
    if command not in ("connect", "sync", "status"):
        sys.exit(__doc__)
    try:
        if command == "connect":
            return cmd_connect()
        from . import zoho
        conn = zoho.live_database()
        if command == "sync":
            for source in SYNCS:
                if configured(source):
                    print("Synced:", describe(sync(conn, db.now(conn), source)) + ".")
        else:
            sessions, first = conn.execute("SELECT COALESCE(SUM(sessions), 0), MIN(date) FROM traffic_daily").fetchone()
            queries, qfirst = conn.execute("SELECT COUNT(DISTINCT query), MIN(date) FROM query_daily").fetchone()
            print("Google Analytics: {}, {:,} sessions since {}.".format("connected" if configured("ga4") else "not connected", sessions, first or "-"))
            print("Search Console: {}, {:,} search queries since {}.".format("connected" if configured("gsc") else "not connected", queries, qfirst or "-"))
        conn.close()
    except GoogleError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main(sys.argv[1:])

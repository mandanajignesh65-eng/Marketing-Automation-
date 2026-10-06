"""The Website and organic screen: visits (Google Analytics), Google search (Search Console) and rankings (Semrush).

Everything is worked out for the chosen period and the one before it. Searches are split into those that use the
company's name and those that do not, because only the second kind shows new people finding the site. Pages are
grouped by what they are (home, blog, case study, product...) and by site, so content can be judged as a group.
"""

import json
import re
from datetime import timedelta

from . import metrics, scoring, semrush
from .db import get_setting, is_demo, set_setting
from .google import page_key
from .periods import MONTHS

WEB_LEAD_CHANNELS = ("website", "chatbot")  # leads that came through the site itself
PAGE_LIMIT, QUERY_LIMIT = 300, 200

# (name, test on a visit's source and medium), first match wins
SEARCH_ENGINES = ("bing", "yahoo", "duckduckgo", "yandex", "brave", "ecosia", "baidu")
AI_TOOLS = ("chatgpt", "openai", "gemini", "perplexity", "claude", "copilot", "deepseek", "grok")
SOCIAL = ("linkedin", "lnkd.in", "facebook", "instagram", "twitter", "t.co", "x.com", "youtube", "whatsapp", "wl.co")
SOURCES = [
    ("Came directly", lambda s, m: s == "(direct)"),
    ("AI assistants", lambda s, m: m == "ai-assistant" or any(a in s for a in AI_TOOLS)),
    ("Paid ads", lambda s, m: m in ("cpc", "ppc", "paid", "paidsocial", "display")),
    ("Google search", lambda s, m: s == "google" and m == "organic"),
    ("Other search engines", lambda s, m: any(e in s for e in SEARCH_ENGINES)),
    ("Social media", lambda s, m: any(x in s for x in SOCIAL)),
    ("Email", lambda s, m: "email" in m or "email" in s or "newsletter" in s),
    ("Not known", lambda s, m: s.startswith("(") or not s),
    ("Other websites", lambda s, m: True),
]

# (name, pattern on the path after the site), first match wins
PAGE_TYPES = [
    ("Home page", r"^/$"),
    ("Blog", r"^/(blog|knowledge-center|resources)(/|$)"),
    ("Case studies", r"^/(case-stud|customer-stor|success-stor)"),
    ("Events", r"^/events?(/|$)"),
    ("Contact and sign-up", r"^/(contact|demo|partner|signup|sign-up|book|get-started|pricing)"),
    ("Product and solutions", r"^/(plaforms|platforms?|solutions?|integrations?|products?|features?|industr|voice|ai-|crm|email|whatsapp|rcs|payment)"),
    ("Company and legal", r"^/(about|terms|privacy|end-user|career|team|legal|refund|security)"),
]
OTHER_PAGES = "Other pages"
TEST_HOST = re.compile(r"^(test|staging|stage|dev|preview|demo)[.-]|lovable|framer|vercel|netlify")  # copies of the site, not the real one


def sites(conn):
    """The sites that count: taken from the Search Console sites chosen at connect time, else the busiest hosts."""
    from . import google
    chosen = [re.sub(r"^(sc-domain:|https?://)", "", s).strip("/").replace("www.", "") for s in google.targets()["gsc"]]
    return [s for s in chosen if "/" not in s and not s.startswith("app.")] or None


FORM_SITES = "form_sites"  # setting: which website each Zoho lead source (a form or a chatbot) sits on


def form_sites(conn):
    try:
        return dict(json.loads(get_setting(conn, FORM_SITES) or "{}"))
    except ValueError:
        return {}


def set_form_site(conn, source, site):
    """Remember which website a form is on ("" forgets it)."""
    known = sites(conn) or []
    if site and site not in known:
        raise ValueError("That is not one of the connected websites.")
    mapping = form_sites(conn)
    mapping.pop(source, None)
    if site:
        mapping[source] = site
    set_setting(conn, FORM_SITES, json.dumps(mapping))


def split_page(key, known):
    """(site, path) for a page key, or (None, path) when the page is not on one of the company's sites."""
    host, _, rest = key.partition("/")
    if not host:  # a bare path, as the sample data has: one unnamed site
        return "website", "/" + rest
    return (host if known is None or host in known else None), "/" + rest


def page_type(path):
    for name, pattern in PAGE_TYPES:
        if re.search(pattern, path):
            return name
    return OTHER_PAGES


def brand_test(conn):
    """Whether a search uses the company's name, including near misses such as "chatbot 360" or "cha 360" for Chat360."""
    words = [w for w in semrush.brand_words(conn) if w]
    parts = re.match(r"^([a-z]+)(\d+)$", words[0]) if words else None
    stem, digits = (parts.group(1)[:3], parts.group(2)) if parts else (None, None)

    def test(query):
        flat = query.replace(" ", "").replace(".", "")
        return any(w in flat for w in words) or bool(stem and digits in flat and stem in flat)
    return test


def weighted(total, weight):
    return total / weight if weight else None


def build(conn, now, p, site=None):
    """Everything on the screen, for every website together or (with `site`) for one of them."""
    thr = scoring.threshold(conn)
    s, e, ps, pe = p.s.isoformat(), p.e.isoformat(), p.ps.isoformat(), p.pe.isoformat()
    known = None if is_demo(conn) else sites(conn)
    site = site if site and known and site in known else None
    is_brand = brand_test(conn)
    marks = ",".join("?" for _ in WEB_LEAD_CHANNELS)
    on_site = form_sites(conn)
    # One site: read the per-site tables, and count only the leads whose form sits on that site.
    if site:
        traffic, t_and, t_args = "traffic_site_daily", " AND site = ?", (site,)
        queries_from = "query_site_daily"
        mine = [k for k, v in on_site.items() if v == site]
        lead_and = " AND channel_id IN ({}) AND lead_source IN ({})".format(marks, ",".join("?" for _ in mine) or "NULL")
        lead_args = WEB_LEAD_CHANNELS + tuple(mine)
    else:
        traffic, t_and, t_args = "traffic_daily", "", ()
        queries_from = "query_daily"
        lead_and, lead_args = " AND channel_id IN ({})".format(marks), WEB_LEAD_CHANNELS
    daily_search = ("SELECT date, clicks, impressions FROM search_site_daily WHERE site = ? AND date BETWEEN ? AND ?" if site else
                    "SELECT date, clicks, impressions FROM channel_daily WHERE channel_id = 'search' AND date BETWEEN ? AND ?")

    def one(sql, args):
        return conn.execute(sql, args).fetchone()

    def search_totals(a, b):
        if site:
            r = one("SELECT COALESCE(SUM(clicks), 0) AS c, COALESCE(SUM(impressions), 0) AS i, SUM(position * impressions) AS pw FROM search_site_daily "
                    "WHERE site = ? AND date BETWEEN ? AND ?", (site, a, b))
            return dict(clicks=r["c"], impressions=r["i"], position=weighted(r["pw"] or 0, r["i"]))
        r = one("SELECT COALESCE(SUM(clicks), 0) AS c, COALESCE(SUM(impressions), 0) AS i FROM channel_daily "
                "WHERE channel_id = 'search' AND date BETWEEN ? AND ?", (a, b))
        pos = one("SELECT SUM(position * 1.0) / COUNT(*) FROM search_daily WHERE date BETWEEN ? AND ?", (a, b))[0]
        return dict(clicks=r["c"], impressions=r["i"], position=pos)

    def web_leads(start_dt, end_dt):
        r = one("SELECT COUNT(*) AS n, COALESCE(SUM(score >= ?), 0) AS q FROM leads WHERE created_at >= ? AND created_at < ?" + lead_and,
                (thr, start_dt, end_dt) + lead_args)
        return r["n"], r["q"]

    visits = one("SELECT COALESCE(SUM(sessions), 0) FROM {} WHERE date BETWEEN ? AND ?{}".format(traffic, t_and), (s, e) + t_args)[0]
    visits_prev = one("SELECT COALESCE(SUM(sessions), 0) FROM {} WHERE date BETWEEN ? AND ?{}".format(traffic, t_and), (ps, pe) + t_args)[0]
    search, search_prev = search_totals(s, e), search_totals(ps, pe)
    leads, qualified = web_leads(p.start_dt, p.end_dt)
    leads_prev, _ = web_leads(p.pstart_dt, p.pend_dt)

    # ---- day by day, for the chart at the top
    by_day = {d.isoformat(): dict(visits=0, clicks=0, leads=0) for d in p.days}
    for r in conn.execute("SELECT date, SUM(sessions) AS n FROM {} WHERE date BETWEEN ? AND ?{} GROUP BY date".format(traffic, t_and), (s, e) + t_args):
        by_day[r["date"]]["visits"] = r["n"]
    for r in conn.execute(daily_search, ((site,) if site else ()) + (s, e)):
        by_day[r["date"]]["clicks"] = r["clicks"]
    for r in conn.execute("SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS n FROM leads WHERE created_at >= ? AND created_at < ?" + lead_and + " GROUP BY d",
                          (p.start_dt, p.end_dt) + lead_args):
        if r["d"] in by_day:
            by_day[r["d"]]["leads"] = r["n"]
    days = [dict(date=d, day=int(d[8:]), month=MONTHS[int(d[5:7]) - 1], **v) for d, v in sorted(by_day.items())]

    # ---- the six months up to the period's end
    y, m = p.e.year, p.e.month
    spans = [((y * 12 + m - 1 - back) // 12, (y * 12 + m - 1 - back) % 12 + 1) for back in range(5, -1, -1)]
    keys = ["{:04d}-{:02d}".format(*ym) for ym in spans]
    month = {k: dict(visits=0, clicks=0, impressions=0, leads=0, brand=0, other=0) for k in keys}
    first = keys[0] + "-01"
    for r in conn.execute("SELECT substr(date, 1, 7) AS k, SUM(sessions) AS n FROM {} WHERE date >= ? AND date <= ?{} GROUP BY 1".format(traffic, t_and), (first, e) + t_args):
        if r["k"] in month:
            month[r["k"]]["visits"] = r["n"]
    for r in conn.execute("SELECT substr(date, 1, 7) AS k, SUM(clicks) AS c, SUM(impressions) AS i FROM ({}) GROUP BY 1".format(
            daily_search.replace("BETWEEN ? AND ?", ">= ? AND date <= ?")), ((site,) if site else ()) + (first, e)):
        if r["k"] in month:
            month[r["k"]].update(clicks=r["c"] or 0, impressions=r["i"] or 0)
    for r in conn.execute("SELECT substr(created_at, 1, 7) AS k, COUNT(*) AS n FROM leads WHERE created_at >= ? AND created_at < ?" + lead_and + " GROUP BY 1",
                          (first, p.end_dt) + lead_args):
        if r["k"] in month:
            month[r["k"]]["leads"] = r["n"]
    for r in conn.execute("SELECT substr(date, 1, 7) AS k, query, SUM(clicks) AS c FROM {} WHERE date >= ? AND date <= ?{} "
                          "GROUP BY 1, 2 HAVING c > 0".format(queries_from, t_and), (first, e) + t_args):
        if r["k"] in month:
            month[r["k"]]["brand" if is_brand(r["query"]) else "other"] += r["c"]
    months = [dict(label=MONTHS[ym[1] - 1], **month[k]) for k, ym in zip(keys, spans)]

    # ---- where visitors came from
    def source_groups(a, b):
        out = {}
        for r in conn.execute("SELECT source, medium, SUM(sessions) AS n FROM {} WHERE date BETWEEN ? AND ?{} GROUP BY 1, 2".format(traffic, t_and), (a, b) + t_args):
            src, med = (r["source"] or "").lower(), (r["medium"] or "").lower()
            name = next(n for n, test in SOURCES if test(src, med))
            g = out.setdefault(name, dict(name=name, visits=0, parts={}))
            g["visits"] += r["n"]
            g["parts"][r["source"]] = g["parts"].get(r["source"], 0) + r["n"]
        return out
    cur_src, prev_src = source_groups(s, e), source_groups(ps, pe)
    sources = sorted((dict(name=g["name"], visits=g["visits"], prev=prev_src.get(g["name"], {}).get("visits", 0),
                           top=[k for k, _ in sorted(g["parts"].items(), key=lambda kv: -kv[1])[:3]])
                      for g in cur_src.values()), key=lambda g: -g["visits"])

    # ---- Google searches: with the company's name, and without
    def query_rows(a, b):
        return {r["query"]: r for r in conn.execute(
            "SELECT query, SUM(clicks) AS c, SUM(impressions) AS i, SUM(position * impressions) AS pw FROM {} "
            "WHERE date BETWEEN ? AND ?{} GROUP BY query".format(queries_from, t_and), (a, b) + t_args)}
    cur_q, prev_q = query_rows(s, e), query_rows(ps, pe)
    queries, split = [], dict(brand=dict(clicks=0, impressions=0, queries=0), other=dict(clicks=0, impressions=0, queries=0))
    buckets = [dict(label="Top 3", lo=0, hi=3.5, n=0), dict(label="4 to 10", lo=3.5, hi=10.5, n=0),
               dict(label="11 to 20", lo=10.5, hi=20.5, n=0), dict(label="Beyond 20", lo=20.5, hi=1e9, n=0)]
    for q, r in cur_q.items():
        brand = is_brand(q)
        side = split["brand" if brand else "other"]
        side["clicks"] += r["c"]
        side["impressions"] += r["i"]
        side["queries"] += 1
        pos = weighted(r["pw"] or 0, r["i"])
        if not brand and pos is not None:
            next(b for b in buckets if b["lo"] <= pos < b["hi"])["n"] += 1
        before = prev_q.get(q)
        queries.append(dict(query=q, brand=brand, clicks=r["c"], impressions=r["i"], position=pos,
                            prev_clicks=before["c"] if before else 0,
                            prev_position=weighted(before["pw"] or 0, before["i"]) if before else None))
    prev_split = dict(brand=0, other=0)
    for q, r in prev_q.items():
        prev_split["brand" if is_brand(q) else "other"] += r["c"]
    top_queries = sorted(queries, key=lambda r: (-r["clicks"], -r["impressions"]))[:QUERY_LIMIT]
    # shown often, not using our name, sitting just off the top: the cheapest places to win visits
    near = sorted((r for r in queries if not r["brand"] and r["position"] is not None and 4 <= r["position"] <= 20 and r["impressions"] >= 20),
                  key=lambda r: -r["impressions"])[:12]

    # ---- pages: views from Analytics, search clicks from Search Console, grouped by what the page is
    def page_views(a, b):
        out = {}
        for r in conn.execute("SELECT path, MAX(title) AS title, SUM(views) AS v FROM page_daily WHERE date BETWEEN ? AND ? GROUP BY path", (a, b)):
            key = page_key(r["path"])
            row = out.setdefault(key, dict(views=0, title=None))
            row["views"] += r["v"]
            row["title"] = row["title"] or r["title"]
        return out
    cur_pages, prev_pages = page_views(s, e), page_views(ps, pe)
    found = {r["page"]: r for r in conn.execute(
        "SELECT page, SUM(clicks) AS c, SUM(impressions) AS i, SUM(position * impressions) AS pw FROM search_page_daily "
        "WHERE date BETWEEN ? AND ? GROUP BY page", (s, e))}
    pages, types, elsewhere = [], {}, 0
    for key in set(cur_pages) | set(found):
        host, path = split_page(key, known)
        views = cur_pages.get(key, {}).get("views", 0)
        hit = found.get(key)
        if host is None:
            elsewhere += views
            continue
        if site and host != site:
            continue
        kind = page_type(path)
        t = types.setdefault((host, kind), dict(site=host, type=kind, pages=0, views=0, prev=0, clicks=0))
        t["pages"] += 1 if views else 0
        t["views"] += views
        t["prev"] += prev_pages.get(key, {}).get("views", 0)
        t["clicks"] += hit["c"] if hit else 0
        title = (cur_pages.get(key, {}).get("title") or "").split(" - Chat360")[0].split(" | Chat360")[0].strip()
        pages.append(dict(site=host, path=path, title=title or None, type=kind, views=views, prev=prev_pages.get(key, {}).get("views", 0),
                          clicks=hit["c"] if hit else 0, impressions=hit["i"] if hit else 0,
                          position=weighted(hit["pw"] or 0, hit["i"]) if hit else None))
    pages.sort(key=lambda r: (-r["views"], -r["clicks"]))
    # pages on test or copy addresses that Google is showing in search: these compete with the real site
    stray = sorted((dict(page=k, clicks=r["c"], impressions=r["i"]) for k, r in found.items()
                    if split_page(k, known)[0] is None and TEST_HOST.search(k.split("/")[0]) and r["i"] >= 50), key=lambda r: -r["impressions"])[:8]

    # ---- which form or chatbot each website lead came through, and which website that form sits on
    before = {r["k"]: r["n"] for r in conn.execute(
        "SELECT COALESCE(lead_source, '') AS k, COUNT(*) AS n FROM leads WHERE created_at >= ? AND created_at < ? AND channel_id IN ({}) GROUP BY 1".format(marks),
        (p.pstart_dt, p.pend_dt) + WEB_LEAD_CHANNELS)}
    forms = [dict(name=r["k"], kind="Chatbot" if r["ch"] == "chatbot" else "Form", site=on_site.get(r["k"], ""), leads=r["n"], qualified=r["q"] or 0,
                  prev=before.get(r["k"], 0))
             for r in conn.execute(
                 "SELECT COALESCE(lead_source, '') AS k, MAX(channel_id) AS ch, COUNT(*) AS n, SUM(score >= ?) AS q FROM leads "
                 "WHERE created_at >= ? AND created_at < ? AND channel_id IN ({}) GROUP BY 1 ORDER BY n DESC".format(marks),
                 (thr, p.start_dt, p.end_dt) + WEB_LEAD_CHANNELS)]

    # ---- the websites side by side
    by_site = []
    for name in (known or []) if len(known or []) > 1 else []:
        v = one("SELECT COALESCE(SUM(sessions), 0) FROM traffic_site_daily WHERE site = ? AND date BETWEEN ? AND ?", (name, s, e))[0]
        vp = one("SELECT COALESCE(SUM(sessions), 0) FROM traffic_site_daily WHERE site = ? AND date BETWEEN ? AND ?", (name, ps, pe))[0]
        g = one("SELECT COALESCE(SUM(clicks), 0) AS c, COALESCE(SUM(impressions), 0) AS i FROM search_site_daily WHERE site = ? AND date BETWEEN ? AND ?", (name, s, e))
        by_site.append(dict(site=name, visits=v, prev=vp, clicks=g["c"], impressions=g["i"],
                            leads=sum(f["leads"] for f in forms if f["site"] == name), qualified=sum(f["qualified"] for f in forms if f["site"] == name)))
    ready = bool(conn.execute("SELECT 1 FROM traffic_site_daily LIMIT 1").fetchone())

    return dict(
        period=p.as_json(), company=get_setting(conn, "company", ""), sites=known or [], site=site or "", site_ready=ready,
        forms=forms, by_site=by_site, unplaced=sum(f["leads"] for f in forms if not f["site"]),
        visits=dict(value=visits, prev=visits_prev), clicks=dict(value=search["clicks"], prev=search_prev["clicks"]),
        impressions=dict(value=search["impressions"], prev=search_prev["impressions"]),
        position=dict(value=search["position"], prev=search_prev["position"]),
        leads=dict(value=leads, prev=leads_prev, qualified=qualified),
        days=days, months=months, sources=sources,
        split=split, prev_split=prev_split, hidden_clicks=max(search["clicks"] - split["brand"]["clicks"] - split["other"]["clicks"], 0),
        queries=top_queries, query_count=len(queries), near=near, buckets=[dict(label=b["label"], n=b["n"]) for b in buckets],
        pages=pages[:PAGE_LIMIT], page_count=len(pages), types=sorted(types.values(), key=lambda t: -t["views"]),
        elsewhere=elsewhere, stray=stray,
        semrush=semrush.view(conn),
    )

"""Health checks: the figures marketing lives by, each set against a benchmark and against the 30 days before.

Every check looks at the last 30 days and the 30 before them. A rate (a "how many out of 100") has a benchmark:
a starting value taken from published B2B figures, which the team can replace with its own. A count (visits,
leads, replies) has no benchmark and is only compared with the earlier 30 days. Checks that read Search Console
stop three days short, because Search Console runs two to three days behind.

A check raises an alert when a rate sits clearly under its benchmark, or when any figure has fallen sharply
against the 30 days before. A rate measured on too few cases is shown but never alerts.
"""

from datetime import timedelta

from . import scoring, website

WINDOW_DAYS = 30
BELOW = 0.9      # under 90% of the benchmark counts as below it
ABOVE = 1.1      # over 110% counts as above it
DROP_PCT = 20    # a fall of this much against the earlier 30 days is a drop
SEARCH_LAG_DAYS = 3
WEB_LEADS = ("website", "chatbot")


def _one(conn, sql, args):
    return conn.execute(sql, args).fetchone()[0] or 0


def _outbound(conn, channel, column, a, b):
    return _one(conn, "SELECT SUM(d.{}) FROM outbound_daily d JOIN outbound_campaigns c ON c.id = d.campaign_id "
                      "WHERE c.channel_id = ? AND d.date BETWEEN ? AND ?".format(column), (channel, a, b))


def _leads(conn, a, b, extra="", args=()):
    return _one(conn, "SELECT COUNT(*) FROM leads WHERE substr(created_at, 1, 10) BETWEEN ? AND ? " + extra, (a, b) + tuple(args))


def _web_leads(conn, a, b):
    return _leads(conn, a, b, "AND channel_id IN ({})".format(",".join("?" for _ in WEB_LEADS)), WEB_LEADS)


def _visits(conn, a, b):
    return _one(conn, "SELECT SUM(sessions) FROM traffic_daily WHERE date BETWEEN ? AND ?", (a, b))


def _search(conn, column, a, b):
    return _one(conn, "SELECT SUM({}) FROM channel_daily WHERE channel_id = 'search' AND date BETWEEN ? AND ?".format(column), (a, b))


def _clicks_by_name(conn, a, b):
    """Google clicks split into searches that use the company's name and those that do not."""
    is_brand = website.brand_test(conn)
    ours = other = 0
    for r in conn.execute("SELECT query, SUM(clicks) AS c FROM query_daily WHERE date BETWEEN ? AND ? GROUP BY query HAVING c > 0", (a, b)):
        if is_brand(r["query"]):
            ours += r["c"]
        else:
            other += r["c"]
    return other, ours + other


def _deals(conn, a, b, won=False):
    if won:
        return _one(conn, "SELECT COUNT(*) FROM deals WHERE stage = 'won' AND substr(closed_at, 1, 10) BETWEEN ? AND ?", (a, b))
    return _one(conn, "SELECT COUNT(*) FROM deals WHERE substr(created_at, 1, 10) BETWEEN ? AND ?", (a, b))


def _qualified(conn, a, b):
    return _leads(conn, a, b, "AND score >= ?", (scoring.threshold(conn),))


# Each check: key, group, name, what it means in plain words, and how it is worked out.
#   count checks give one number; rate checks give (part, whole) and show part out of every 100 of whole.
#   benchmark: the starting figure and where it comes from. floor: the fewest cases a rate needs before it can alert.
CHECKS = [
    dict(key="visits", group="Website", name="Website visits", kind="count", unit="visits",
         says="How many times people came to the website.", count=_visits),
    dict(key="google_clicks", group="Website", name="Clicks from Google", kind="count", unit="clicks", lag=True,
         says="How many times someone clicked to us from a Google search.", count=lambda c, a, b: _search(c, "clicks", a, b)),
    dict(key="google_ctr", group="Website", name="Google click rate", kind="rate", lag=True, benchmark=2.0, floor=1000,
         says="Out of every 100 times Google showed us, how many times people clicked.",
         source="A whole site, counting every search it shows for, usually gets 1 to 3 clicks per 100 times shown.",
         rate=lambda c, a, b: (_search(c, "clicks", a, b), _search(c, "impressions", a, b))),
    dict(key="new_people", group="Website", name="Clicks from new people", kind="rate", lag=True, benchmark=50.0, floor=100,
         says="Out of every 100 Google clicks, how many came from people who did not type our name. These are new people finding us.",
         source="SEO guides put a healthy B2B site at 50 to 70 in every 100 clicks from searches without the brand name.",
         rate=_clicks_by_name),
    dict(key="visit_to_lead", group="Website", name="Visits that become leads", kind="rate", benchmark=2.0, floor=500,
         says="Out of every 100 website visits, how many became a lead.",
         source="B2B software sites average 1.5 to 2.5 leads per 100 visits across published 2026 studies.",
         rate=lambda c, a, b: (_web_leads(c, a, b), _visits(c, a, b))),

    dict(key="leads", group="Leads", name="New leads", kind="count", unit="leads",
         says="How many new marketing leads came in.", count=_leads),
    dict(key="qualified_rate", group="Leads", name="Leads that qualify", kind="rate", benchmark=30.0, floor=30,
         says="Out of every 100 leads, how many look like the customers we want.",
         source="Published B2B funnels show 31 to 41 in every 100 leads becoming marketing-qualified.",
         rate=lambda c, a, b: (_qualified(c, a, b), _leads(c, a, b))),
    dict(key="lead_to_deal", group="Leads", name="Leads that become deals", kind="rate", benchmark=3.0, floor=50,
         says="Out of every 100 leads, how many turned into a deal for sales.",
         source="Worked out from published stage rates: about 30 in 100 leads qualify, 13 to 20 in 100 of those are accepted by sales, and about half of those become a deal.",
         rate=lambda c, a, b: (_deals(c, a, b), _leads(c, a, b))),
    dict(key="win_rate", group="Leads", name="Deals won", kind="rate", benchmark=20.0, floor=10,
         says="Out of every 100 deals opened, how many were won.",
         source="Mid-market B2B software teams win 15 to 25 in every 100 deals.",
         rate=lambda c, a, b: (_deals(c, a, b, won=True), _deals(c, a, b))),

    dict(key="li_sent", group="LinkedIn outreach", name="Requests sent", kind="count", unit="requests",
         says="How many people we asked to connect with on LinkedIn.", count=lambda c, a, b: _outbound(c, "heyreach", "sent", a, b)),
    dict(key="li_accept", group="LinkedIn outreach", name="Requests accepted", kind="rate", benchmark=28.0, floor=100,
         says="Out of every 100 people we asked to connect, how many said yes.",
         source="The average across LinkedIn outreach is about 28 in 100, and 27.8 for B2B software, in 2026 benchmark reports.",
         rate=lambda c, a, b: (_outbound(c, "heyreach", "opened", a, b), _outbound(c, "heyreach", "sent", a, b))),
    dict(key="li_reply", group="LinkedIn outreach", name="Replies after accepting", kind="rate", benchmark=10.0, floor=50,
         says="Out of every 100 people who accepted, how many wrote back.",
         source="Messages sent after connecting get a reply about 10 times in 100 in 2026 benchmark reports.",
         rate=lambda c, a, b: (_outbound(c, "heyreach", "replied", a, b), _outbound(c, "heyreach", "opened", a, b))),

    dict(key="em_sent", group="Email outreach", name="Emails sent", kind="count", unit="emails",
         says="How many outreach emails we sent.", count=lambda c, a, b: _outbound(c, "apollo", "sent", a, b)),
    dict(key="em_open", group="Email outreach", name="Emails opened", kind="rate", benchmark=28.0, floor=100,
         says="Out of every 100 emails sent, how many were opened. Treat it as a rough guide: some mail programs open emails by themselves.",
         source="The average open rate for B2B cold email is about 28 in 100 in 2026.",
         rate=lambda c, a, b: (_outbound(c, "apollo", "opened", a, b), _outbound(c, "apollo", "sent", a, b))),
    dict(key="em_reply", group="Email outreach", name="Emails replied to", kind="rate", benchmark=3.5, floor=100,
         says="Out of every 100 emails sent, how many got a reply.",
         source="Large studies of cold email put the average at 3 to 4 replies in 100; above 5 is good.",
         rate=lambda c, a, b: (_outbound(c, "apollo", "replied", a, b), _outbound(c, "apollo", "sent", a, b))),
]
BY_KEY = {c["key"]: c for c in CHECKS}
GROUPS = ["Website", "Leads", "LinkedIn outreach", "Email outreach"]


def windows(now, lag=False):
    end = now.date() - timedelta(days=SEARCH_LAG_DAYS if lag else 0)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    return (start, end), (start - timedelta(days=WINDOW_DAYS), start - timedelta(days=1))


def run(conn, now):
    """Every check with its current figure, the earlier one, its benchmark and a verdict."""
    saved = {r["key"]: r for r in conn.execute("SELECT * FROM benchmarks")}
    out = []
    for c in CHECKS:
        (a, b), (pa, pb) = windows(now, c.get("lag", False))
        span, before = (a.isoformat(), b.isoformat()), (pa.isoformat(), pb.isoformat())
        row = saved.get(c["key"])
        watch = not row or bool(row["watch"])
        if c["kind"] == "count":
            value, prev, base, benchmark = c["count"](conn, *span), c["count"](conn, *before), None, None
            enough = prev >= 20  # a drop from almost nothing is noise
        else:
            part, base = c["rate"](conn, *span)
            ppart, pbase = c["rate"](conn, *before)
            value = part / base * 100 if base else None
            prev = ppart / pbase * 100 if pbase else None
            benchmark = row["value"] if row and row["value"] is not None else c["benchmark"]
            enough = base >= c["floor"]
        change = (value - prev) / prev * 100 if value is not None and prev else None
        if c["kind"] == "count":
            against = None
        elif value is None or not enough:
            against = "too_few"
        else:
            against = "below" if value < benchmark * BELOW else "above" if value > benchmark * ABOVE else "near"
        dropped = change is not None and change <= -DROP_PCT and enough and (c["kind"] == "count" or (prev is not None and pbase >= c["floor"]))
        out.append(dict(key=c["key"], group=c["group"], name=c["name"], kind=c["kind"], unit=c.get("unit", "%"), says=c["says"],
                        source=c.get("source"), value=value, prev=prev, base=base, floor=c.get("floor"), change=change,
                        benchmark=benchmark, default=c.get("benchmark"), custom=bool(row and row["value"] is not None),
                        against=against, dropped=dropped, watch=watch, has_data=bool(value) or bool(prev),
                        span="{} to {}".format(a.isoformat(), b.isoformat())))
    return out


def number(check, value):
    if value is None:
        return "nothing yet"
    if check["kind"] == "rate":
        return "{:.1f}%".format(value) if value < 10 else "{:.0f}%".format(value)
    return "{:,.0f}".format(value)


def alerts_below(conn, now):
    """One alert for each watched rate sitting clearly under its benchmark."""
    month = now.strftime("%Y-%m")
    return [dict(dedupe="{}:{}".format(c["key"], month), severity="warn",
                 title="{} is below the benchmark".format(c["name"]),
                 detail="{} in the last 30 days, against a benchmark of {}. {}".format(number(c, c["value"]), number(c, c["benchmark"]), c["says"]))
            for c in run(conn, now) if c["watch"] and c["against"] == "below"]


def alerts_dropped(conn, now):
    """One alert for each watched figure that fell sharply against the 30 days before."""
    week = now.date().isocalendar()
    return [dict(dedupe="{}:{}-W{}".format(c["key"], week[0], week[1]), severity="neg" if c["change"] <= -40 else "warn",
                 title="{} down {:.0f}% on the 30 days before".format(c["name"], -c["change"]),
                 detail="{} in the last 30 days, {} in the 30 days before. {}".format(number(c, c["value"]), number(c, c["prev"]), c["says"]))
            for c in run(conn, now) if c["watch"] and c["dropped"]]


def save(conn, key, value=None, watch=None, reset=False):
    """Change a check's benchmark, switch its alerts on or off, or put the benchmark back to the starting figure."""
    if key not in BY_KEY:
        raise ValueError("Unknown check")
    row = conn.execute("SELECT * FROM benchmarks WHERE key = ?", (key,)).fetchone()
    new_value = None if reset else value if value is not None else (row["value"] if row else None)
    new_watch = int(watch) if watch is not None else (row["watch"] if row else 1)
    if new_value is not None and not 0 < new_value <= 100:
        raise ValueError("A benchmark is a number between 0 and 100")
    conn.execute("INSERT INTO benchmarks (key, value, watch) VALUES (?,?,?) ON CONFLICT (key) DO UPDATE SET value = excluded.value, watch = excluded.watch",
                 (key, new_value, new_watch))

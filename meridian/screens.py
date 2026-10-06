"""Builds the data each screen needs. Numbers are returned raw; the front end formats them."""

import json
from datetime import date, datetime, timedelta

from . import config, health, ingest, insights, metrics, money, narrative, research, scoring, semrush
from .db import get_setting, is_demo
from .periods import (MONTHS, MONTHS_LONG, WEEKDAYS, WEEKDAYS_LONG, Period, age_short, ago, day_label, days_in_month,
                      fired_label, iso, midnight, month_key, next_month, span_label, stamp)

TONE = {"neg": "neg", "warn": "warn", "info": "ink3"}


def delta(cur, prev):
    return {"value": cur, "prev": prev, "pct": metrics.pct_change(cur, prev) if cur is not None and prev else None}


def initials(name):
    return "".join(w[0] for w in (name or "?").split()[:2]).upper()


def open_alerts(conn, now, limit=None):
    rows = conn.execute("SELECT * FROM alerts WHERE resolved_at IS NULL ORDER BY created_at DESC" +
                        (" LIMIT {}".format(int(limit)) if limit else "")).fetchall()
    return [dict(title=r["title"], detail=r["detail"], tone=TONE.get(r["severity"], "ink3"),
                 when=ago(now, r["created_at"])) for r in rows]


# ------------------------------------------------------------------------------- shell

def sync_summary(conn, now):
    """Overall data freshness for the top bar, plus a banner when a source needs attention."""
    sources = insights.source_states(conn, now)
    connected = [s for s in sources if s["status"] == "connected"]
    if not connected and not any(s["state"] == "disconnected" for s in sources):
        return dict(state="empty", tone="ink3", text="No sources connected", banner=None)
    for s in sources:
        if s["state"] == "disconnected":
            return dict(state="disconnected", tone="neg", text=s["name"] + " disconnected", banner=dict(
                tone="neg", source=s["key"], title=s["name"] + " is disconnected", action="Reconnect",
                detail=s["note"] or "Figures from this source stop at its last sync, {}.".format(ago(now, s["last_sync_at"]) if s["last_sync_at"] else "never")))
    for s in sources:
        if s["state"] == "stale":
            return dict(state="stale", tone="warn", text="{} last synced {:.0f} h ago".format(s["name"], s["hours"]), banner=dict(
                tone="warn", source=s["key"], title="{} data is {:.0f} hours old".format(s["name"], s["hours"]), action="Retry sync",
                detail=s["note"] or "The last sync did not complete. Figures from this source stop at {}.".format(
                    day_label(datetime.fromisoformat(s["last_sync_at"]).date()))))
    latest = max(s["last_sync_at"] for s in connected if s["last_sync_at"]) if any(s["last_sync_at"] for s in connected) else None
    primary = next((s for s in connected if s["key"] == "zoho" and s["last_sync_at"]), None)
    when = ago(now, primary["last_sync_at"] if primary else latest) if latest else "never"
    count = "All {} sources".format(len(sources)) if len(connected) == len(sources) else "{} of {} sources".format(len(connected), len(sources))
    return dict(state="live", tone="pos", text="{} synced · {}".format(count, when), banner=None)


def shell(conn, now):
    month = Period(now, "month")
    leads = conn.execute("SELECT COUNT(*) AS n FROM leads WHERE created_at >= ? AND created_at < ?",
                         (month.start_dt, month.end_dt)).fetchone()["n"]
    alerts_open = conn.execute("SELECT COUNT(*) AS n FROM alerts WHERE resolved_at IS NULL").fetchone()["n"]
    user = conn.execute("SELECT * FROM users WHERE name = ?", (get_setting(conn, "current_user"),)).fetchone()
    owners = [r["owner"] for r in conn.execute("SELECT DISTINCT owner FROM leads WHERE owner IS NOT NULL ORDER BY owner")]
    return dict(
        company=get_setting(conn, "company", "Your company"), product=get_setting(conn, "product", "Meridian"),
        user=dict(name=user["name"], role=user["team"], initials=initials(user["name"])) if user else None,
        demo=is_demo(conn), today=now.date().isoformat(), currency=money.spec(),
        channels=[dict(id=c["id"], name=c["name"], grp=c["grp"], color=c["color"]) for c in metrics.channels(conn)],
        groups=[dict(id=g, label=label) for g, label in metrics.GROUPS
                if conn.execute("SELECT 1 FROM channels WHERE grp = ?", (g,)).fetchone()],
        badges=dict(leads=leads, alerts=alerts_open), sync=sync_summary(conn, now),
        owners=owners, statuses=metrics.STATUSES,
    )


# ------------------------------------------------------------------------------- overview

def target_rows(conn, now):
    """Month-to-date progress against this month's targets."""
    month = Period(now, "month")
    cur = metrics.total(metrics.channel_stats(conn, month.cur, scoring.threshold(conn)))
    targets = narrative.targets_for(conn, month_key(now.date()))
    elapsed = now.day / days_in_month(now.date())
    budget = sum(v for k, v in targets.items() if k.startswith("budget_"))
    rows = []
    for key, label, actual, target in (("leads", "Leads", cur["leads"], targets.get("leads")),
                                       ("qualified", "Qualified leads", cur["qualified"], targets.get("qualified")),
                                       ("pipeline", "Pipeline", cur["pipeline"], targets.get("pipeline")),
                                       ("won", "Deals won", cur["won"], targets.get("won")),
                                       ("spend", "Spend", cur["spend"], budget or None)):
        if not target:
            continue
        projected = actual / elapsed
        share = projected / target
        if key == "spend":
            status, tone = ("Over budget", "warn") if share > 1.05 else ("On budget", "ink2") if share > 1 else ("Under budget", "ink2")
        else:
            status, tone = ("On pace", "pos") if share >= 1 else ("Slightly behind", "warn") if share >= 0.9 else ("Behind", "neg")
        rows.append(dict(key=key, label=label, actual=actual, target=target, pct=min(100, actual / target * 100),
                         projected=projected, status=status, tone=tone))
    return dict(rows=rows, month=MONTHS_LONG[now.month - 1], pace_pct=elapsed * 100)


def overview(conn, now, p, channel):
    thr = scoring.threshold(conn)
    ids = metrics.resolve_channels(conn, channel)
    cur_by = metrics.channel_stats(conn, p.cur, thr)
    cur, prev = metrics.total(cur_by, ids), metrics.total(metrics.channel_stats(conn, p.prev, thr), ids)

    lead_kpis = []
    for rng, label in (("day", "Leads today"), ("week", "This week"), ("month", "This month")):
        if p.rng == rng:
            c, v = cur, prev
        else:
            pp = Period(now, rng)
            c = metrics.total(metrics.channel_stats(conn, pp.cur, thr), ids)
            v = metrics.total(metrics.channel_stats(conn, pp.prev, thr), ids)
        lead_kpis.append(dict(label=label, **delta(c["leads"], v["leads"])))

    first = now.date() - timedelta(days=6) if p.rng == "day" else p.s
    clause, args = metrics.in_clause("channel_id", ids)
    counts = {}
    for r in conn.execute("SELECT substr(created_at, 1, 10) AS d, channel_id, COUNT(*) AS n FROM leads "
                          "WHERE created_at >= ? AND created_at < ?" + clause + " GROUP BY d, channel_id",
                          [iso(midnight(first)), p.end_dt] + args):
        counts.setdefault(r["d"], {})[r["channel_id"]] = r["n"]
    chart = []
    for i in range((p.e - first).days + 1):
        d = first + timedelta(days=i)
        segs = counts.get(d.isoformat(), {})
        chart.append(dict(date=d.isoformat(), day=d.day, month=MONTHS[d.month - 1], total=sum(segs.values()),
                          partial=d == now.date(), segs=[dict(id=k or "unmapped", n=n) for k, n in segs.items()]))

    range_name = {"month": "Month to date", "week": "Week to date", "day": "Today"}.get(p.rng, span_label(p.s, p.e))

    def outreach(window):
        a, b = window[2], window[3]
        return dict(linkedin=dict(sent=health._outbound(conn, "heyreach", "sent", a, b), accepted=health._outbound(conn, "heyreach", "opened", a, b),
                                  replied=health._outbound(conn, "heyreach", "replied", a, b)),
                    email=dict(sent=health._outbound(conn, "apollo", "sent", a, b), opened=health._outbound(conn, "apollo", "opened", a, b),
                               replied=health._outbound(conn, "apollo", "replied", a, b)))

    out_cur, out_prev = outreach(p.cur), outreach(p.prev)
    visits = health._visits(conn, p.cur[2], p.cur[3])
    by_channel = {cid or "unmapped": s["leads"] for cid, s in cur_by.items() if s["leads"] and (ids is None or cid in ids)}
    return dict(
        visits=delta(visits, health._visits(conn, p.prev[2], p.prev[3])),
        replies=delta(out_cur["linkedin"]["replied"] + out_cur["email"]["replied"], out_prev["linkedin"]["replied"] + out_prev["email"]["replied"]),
        deals=delta(cur["deals"], prev["deals"]), outreach=out_cur,
        journey=dict(visits=visits, web_leads=health._web_leads(conn, p.cur[2], p.cur[3]), leads=cur["leads"], qualified=cur["qualified"],
                     deals=cur["deals"], won=cur["won"]),
        period=p.as_json(),
        date_line="{}, {} {} · {}".format(WEEKDAYS_LONG[now.weekday()], now.day, MONTHS_LONG[now.month - 1], range_name),
        day_of="Day {} of {}".format(now.day, days_in_month(now.date())),
        summary=narrative.overview_summary(conn, now, p, cur, prev, ids is not None),
        lead_kpis=lead_kpis,
        kpis=dict(qualified=delta(cur["qualified"], prev["qualified"]), spend=delta(cur["spend"], prev["spend"]),
                  cpql=delta(metrics.cost_per(cur["spend"], cur["qualified"]), metrics.cost_per(prev["spend"], prev["qualified"])),
                  pipeline=delta(cur["pipeline"], prev["pipeline"])),
        chart=chart, chart_label="Daily · " + span_label(first, p.e),
        by_channel=by_channel,
        funnel=cur, alerts=open_alerts(conn, now, 4),
    )


# ------------------------------------------------------------------------------- funnel, channels

def funnel(conn, now, p, segment):
    thr = scoring.threshold(conn)
    ids = metrics.resolve_channels(conn, segment)
    cur = metrics.channel_stats(conn, p.cur, thr)
    steps = ("leads", "qualified", "deals", "won")
    # which channels fill each step, biggest first; leads with no channel yet are shown as unmapped
    mix = sorted((dict(id=cid, pipeline=row["pipeline"], **{k: row[k] for k in steps}) for cid, row in cur.items()
                  if (ids is None or cid in ids) and any(row[k] for k in steps)), key=lambda r: [-r[k] for k in steps])
    return dict(period=p.as_json(), threshold=thr, mix=mix, audience=audience(conn, p, ids, thr),
                cur=metrics.total(cur, ids),
                prev=metrics.total(metrics.channel_stats(conn, p.prev, thr), ids))


OTHER_INDUSTRY, NO_COMPANY = "Other industries", "Company not known"


def audience(conn, p, ids, thr):
    """Who the period's leads are: how many fall in each target segment, overall and per channel."""
    icp = scoring.profile(conn)
    names = list(icp["segments"]) + [OTHER_INDUSTRY, NO_COMPANY]
    clause, args = metrics.in_clause("channel_id", ids)
    total = {n: dict(name=n, leads=0, qualified=0) for n in names}
    by_channel = {}
    for r in conn.execute("SELECT channel_id, industry, score FROM leads WHERE created_at >= ? AND created_at < ?" + clause,
                          [p.start_dt, p.end_dt] + args):
        industry = (r["industry"] or "").strip()
        name = (scoring.in_segment(industry, icp) or OTHER_INDUSTRY) if industry else NO_COMPANY
        total[name]["leads"] += 1
        total[name]["qualified"] += r["score"] >= thr
        row = by_channel.setdefault(r["channel_id"], dict(id=r["channel_id"], leads=0, parts=dict.fromkeys(names, 0)))
        row["leads"] += 1
        row["parts"][name] += 1
    return dict(names=names, targets=len(icp["segments"]), total=[total[n] for n in names],
                by_channel=sorted(by_channel.values(), key=lambda r: -r["leads"]))


def lead_brief(r):
    return dict(id=r["id"], name=r["name"], company=r["company"], score=r["score"], initials=initials(r["name"]))


def channels(conn, now, p):
    thr = scoring.threshold(conn)
    stats, before = metrics.channel_stats(conn, p.cur, thr), metrics.channel_stats(conn, p.prev, thr)
    rows = [dict(id=ch["id"], prev=before.get(ch["id"], metrics.empty_stats()), **stats.get(ch["id"], metrics.empty_stats()))
            for ch in metrics.channels(conn)]

    # the six calendar months up to the period's end, so the direction of each channel is visible
    y, m = p.e.year, p.e.month
    months = [((y * 12 + m - 1 - back) // 12, (y * 12 + m - 1 - back) % 12 + 1) for back in range(5, -1, -1)]
    keys = ["{:04d}-{:02d}".format(*ym) for ym in months]
    trend = {k: {} for k in keys}
    for r in conn.execute(
            "SELECT substr(created_at, 1, 7) AS month, channel_id, COUNT(*) AS n, SUM(score >= ?) AS q FROM leads "
            "WHERE created_at >= ? AND created_at < ? AND channel_id IS NOT NULL GROUP BY 1, 2",
            (thr, keys[0] + "-01", p.end_dt)):
        if r["month"] in trend:
            trend[r["month"]][r["channel_id"]] = dict(leads=r["n"], qualified=r["q"] or 0)

    # what each channel is made of: the lead sources (an event, a form, a campaign) behind it
    source = "COALESCE(NULLIF(TRIM(lead_source), ''), NULLIF(TRIM(utm_campaign), ''), 'Source not recorded')"
    inside = {}
    for r in conn.execute(
            "SELECT channel_id, {} AS source, COUNT(*) AS n, SUM(score >= ?) AS q FROM leads "
            "WHERE created_at >= ? AND created_at < ? AND channel_id IS NOT NULL GROUP BY 1, 2".format(source), (thr, p.start_dt, p.end_dt)):
        inside.setdefault(r["channel_id"], {})[r["source"]] = dict(source=r["source"], leads=r["n"], qualified=r["q"] or 0, deals=0, pipeline=0)
    for r in conn.execute(
            "SELECT channel_id, COALESCE(NULLIF(TRIM(lead_source), ''), 'Source not recorded') AS source, COUNT(*) AS n, SUM(amount) AS amt FROM deals "
            "WHERE created_at >= ? AND created_at < ? AND channel_id IS NOT NULL GROUP BY 1, 2", (p.start_dt, p.end_dt)):
        row = inside.setdefault(r["channel_id"], {}).setdefault(r["source"], dict(source=r["source"], leads=0, qualified=0, deals=0, pipeline=0))
        row.update(deals=r["n"], pipeline=r["amt"] or 0)

    # what the outreach tools themselves report (Apollo, HeyReach), to set beside the leads that reached the CRM
    outreach = {}
    for r in conn.execute(
            "SELECT c.channel_id, c.name, COALESCE(SUM(d.sent), 0) AS sent, COALESCE(SUM(d.opened), 0) AS opened, COALESCE(SUM(d.replied), 0) AS replied "
            "FROM outbound_campaigns c JOIN outbound_daily d ON d.campaign_id = c.id AND d.date BETWEEN ? AND ? "
            "GROUP BY c.id HAVING sent + opened + replied > 0 ORDER BY sent DESC, replied DESC", (p.s.isoformat(), p.e.isoformat())):
        tool = outreach.setdefault(r["channel_id"], dict(sent=0, opened=0, replied=0, campaigns=[]))
        for k in ("sent", "opened", "replied"):
            tool[k] += r[k]
        tool["campaigns"].append(dict(name=r["name"], sent=r["sent"], opened=r["opened"], replied=r["replied"]))
    connected = {r["key"] for r in conn.execute("SELECT key FROM sources WHERE status <> 'not_connected'")}

    unmapped = stats.get(None)
    return dict(period=p.as_json(), rows=rows, unmapped=unmapped["leads"] if unmapped else 0, threshold=thr,
                outreach=outreach, connected=sorted(connected & {"apollo", "heyreach"}),
                months=[dict(key=k, label=MONTHS[ym[1] - 1][:3], by=trend[k]) for k, ym in zip(keys, months)],
                inside={cid: sorted(v.values(), key=lambda r: (-r["leads"], -r["deals"])) for cid, v in inside.items()},
                range_name="Month to date" if p.rng == "month" else "Week to date" if p.rng == "week" else "Today" if p.rng == "day" else "Custom range")


# ------------------------------------------------------------------------------- paid, outbound

def paid(conn, now, p):
    s, e = p.s.isoformat(), p.e.isoformat()
    platforms = []
    for platform, label in insights.PLATFORMS.items():
        camps = {}
        for r in conn.execute(
                "SELECT c.id, c.name, c.status, cr.id AS creative_id, cr.headline, cr.format, "
                "COALESCE(SUM(d.spend), 0) AS spend, COALESCE(SUM(d.impressions), 0) AS impressions, "
                "COALESCE(SUM(d.clicks), 0) AS clicks, COALESCE(SUM(d.leads), 0) AS leads "
                "FROM ad_campaigns c JOIN ad_creatives cr ON cr.campaign_id = c.id "
                "LEFT JOIN ad_daily d ON d.creative_id = cr.id AND d.date BETWEEN ? AND ? "
                "WHERE c.platform = ? GROUP BY cr.id ORDER BY c.id, cr.id", (s, e, platform)):
            camp = camps.setdefault(r["id"], dict(id=r["id"], name=r["name"], status=r["status"], spend=0,
                                                  impressions=0, clicks=0, leads=0, creatives=[]))
            camp["creatives"].append(dict(headline=r["headline"], format=r["format"], spend=r["spend"],
                                          impressions=r["impressions"], clicks=r["clicks"], leads=r["leads"]))
            for k in ("spend", "impressions", "clicks", "leads"):
                camp[k] += r[k]
        platforms.append(dict(id=platform, label=label, campaigns=list(camps.values()),
                              pacing=insights.pacing(conn, now, platform)))
    return dict(period=p.as_json(), platforms=platforms, month=MONTHS[now.month - 1],
                sub="{} · day {} of {}".format(span_label(p.s, p.e), now.day, days_in_month(now.date())))


def outbound(conn, now, p):
    """Outreach tools (Apollo, HeyReach): what was sent and what came back, per tool, per campaign and per month."""
    thr = scoring.threshold(conn)
    stats, before = metrics.channel_stats(conn, p.cur, thr), metrics.channel_stats(conn, p.prev, thr)
    connected = {r["key"] for r in conn.execute("SELECT key FROM sources WHERE status <> 'not_connected'")}
    y, m = p.e.year, p.e.month
    months = [((y * 12 + m - 1 - back) // 12, (y * 12 + m - 1 - back) % 12 + 1) for back in range(5, -1, -1)]
    keys = ["{:04d}-{:02d}".format(*ym) for ym in months]
    steps = ("sent", "opened", "replied", "meetings")
    sums = ", ".join("COALESCE(SUM(d.{0}), 0) AS {0}".format(k) for k in steps)
    groups = []
    for ch in metrics.channels(conn):
        if ch["grp"] != "outbound":
            continue

        def totals(a, b):
            row = conn.execute("SELECT {} FROM outbound_daily d JOIN outbound_campaigns c ON c.id = d.campaign_id "
                               "WHERE c.channel_id = ? AND d.date BETWEEN ? AND ?".format(sums), (ch["id"], a.isoformat(), b.isoformat())).fetchone()
            return {k: row[k] for k in steps}

        # per campaign: when it first and last did anything, the comparison period, and each of the six months,
        # so the screen can add up any hand-picked set of campaigns
        own = "d.campaign_id IN (SELECT id FROM outbound_campaigns WHERE channel_id = ?)"
        seen = {r["campaign_id"]: (r["first"], r["last"]) for r in conn.execute(
            "SELECT d.campaign_id, MIN(d.date) AS first, MAX(d.date) AS last FROM outbound_daily d WHERE {} GROUP BY 1".format(own), (ch["id"],))}
        earlier = {r["campaign_id"]: [r[k] for k in steps] for r in conn.execute(
            "SELECT d.campaign_id, {} FROM outbound_daily d WHERE {} AND d.date BETWEEN ? AND ? GROUP BY 1".format(sums, own),
            (ch["id"], p.ps.isoformat(), p.pe.isoformat()))}
        monthly = {}
        for r in conn.execute(
                "SELECT d.campaign_id, substr(d.date, 1, 7) AS month, {} FROM outbound_daily d WHERE {} AND d.date >= ? AND d.date <= ? GROUP BY 1, 2"
                .format(sums, own), (ch["id"], keys[0] + "-01", p.e.isoformat())):
            if r["month"] in keys:
                monthly.setdefault(r["campaign_id"], {})[keys.index(r["month"])] = [r[k] for k in steps]
        camps = []
        for r in conn.execute(
                "SELECT c.id, c.name, c.detail, c.lifetime, {} FROM outbound_campaigns c "
                "LEFT JOIN outbound_daily d ON d.campaign_id = c.id AND d.date BETWEEN ? AND ? "
                "WHERE c.channel_id = ? GROUP BY c.id ORDER BY sent DESC, replied DESC, c.id".format(sums),
                (p.s.isoformat(), p.e.isoformat(), ch["id"])):
            life = json.loads(r["lifetime"]) if r["lifetime"] else None
            first, last = seen.get(r["id"], (None, None))
            camps.append(dict(id=r["id"], name=r["name"], detail=r["detail"], steps=[r[k] for k in steps], lifetime=life,
                              first=first, last=last, prev=earlier.get(r["id"], [0, 0, 0, 0]),
                              months=[monthly.get(r["id"], {}).get(i, [0, 0, 0, 0]) for i in range(len(keys))]))
        by_month = {k: dict.fromkeys(steps, 0) for k in keys}
        for r in conn.execute(
                "SELECT substr(d.date, 1, 7) AS month, {} FROM outbound_daily d JOIN outbound_campaigns c ON c.id = d.campaign_id "
                "WHERE c.channel_id = ? AND d.date >= ? AND d.date <= ? GROUP BY 1".format(sums), (ch["id"], keys[0] + "-01", p.e.isoformat())):
            if r["month"] in by_month:
                by_month[r["month"]] = {k: r[k] for k in steps}
        st, pst = stats.get(ch["id"], metrics.empty_stats()), before.get(ch["id"], metrics.empty_stats())
        cur = totals(p.s, p.e)
        groups.append(dict(
            id=ch["id"], color=ch["color"], connected=ch["id"] in connected, campaigns=camps,
            totals=[cur[k] for k in steps], prev=[totals(p.ps, p.pe)[k] for k in steps],
            leads=st["leads"], qualified=st["qualified"], deals=st["deals"], prev_leads=pst["leads"], spend=st["spend"],
            months=[dict(label=MONTHS[ym[1] - 1][:3], **by_month[k]) for k, ym in zip(keys, months)]))
    return dict(period=p.as_json(), groups=groups, threshold=thr)


# ------------------------------------------------------------------------------- website

def web(conn, now, p):
    thr = scoring.threshold(conn)
    s, e, ps, pe = p.s.isoformat(), p.e.isoformat(), p.ps.isoformat(), p.pe.isoformat()

    def sessions(a, b):
        by = {r["date"]: r["n"] for r in conn.execute(
            "SELECT date, SUM(sessions) AS n FROM traffic_daily WHERE date BETWEEN ? AND ? GROUP BY date", (a.isoformat(), b.isoformat()))}
        return [by.get((a + timedelta(days=i)).isoformat(), 0) for i in range((b - a).days + 1)]

    def one(sql, args):
        return conn.execute(sql, args).fetchone()[0]

    def inbound(window):
        st = metrics.channel_stats(conn, window, thr)
        return sum(v["leads"] for k, v in st.items() if k and k not in outbound_ids)

    outbound_ids = set(metrics.resolve_channels(conn, "outbound"))
    cur, prev = sessions(p.s, p.e), sessions(p.ps, p.pe)
    # The chart compares day against day, so its earlier line is shifted by whole weeks to keep weekdays aligned.
    weeks = -(-len(cur) // 7)
    aligned = sessions(p.s - timedelta(weeks=weeks), p.e - timedelta(weeks=weeks))
    clicks = "SELECT COALESCE(SUM(clicks), 0) FROM channel_daily WHERE channel_id = 'search' AND date BETWEEN ? AND ?"
    pos = "SELECT AVG(position) FROM search_daily WHERE date BETWEEN ? AND ?"
    leads_cur, leads_prev = inbound(p.cur), inbound(p.prev)

    def recent_pos(end):
        a = (end - timedelta(days=2)).isoformat()
        return {r["query"]: r["p"] for r in conn.execute(
            "SELECT query, AVG(position) AS p FROM query_daily WHERE date BETWEEN ? AND ? GROUP BY query", (a, end.isoformat()))}

    now_pos, was_pos = recent_pos(p.e), recent_pos(p.pe)
    queries = [dict(query=r["query"], clicks=r["clicks"], impressions=r["impressions"],
                    position=now_pos.get(r["query"]), was=was_pos.get(r["query"]))
               for r in conn.execute("SELECT query, SUM(clicks) AS clicks, SUM(impressions) AS impressions FROM query_daily "
                                     "WHERE date BETWEEN ? AND ? GROUP BY query ORDER BY clicks DESC LIMIT 8", (s, e))]
    pages = [dict(r) for r in conn.execute(
        "SELECT path, MAX(title) AS title, SUM(views) AS views, SUM(leads) AS leads FROM page_daily "
        "WHERE date BETWEEN ? AND ? GROUP BY path ORDER BY views DESC LIMIT 8", (s, e))]
    forms = [dict(r) for r in conn.execute(
        "SELECT form, SUM(views) AS views, SUM(submissions) AS submissions FROM form_daily "
        "WHERE date BETWEEN ? AND ? GROUP BY form ORDER BY submissions DESC", (s, e))]

    slip = insights.ranking_drop(conn, p.e - timedelta(days=45), p.e)
    annotation = None
    if slip and s <= slip["date"] <= e and len(cur) > 1:
        annotation = dict(index=(date.fromisoformat(slip["date"]) - p.s).days, label=slip["label"],
                          text="“{}” falls from {:.0f} to {:.0f}".format(slip["query"], slip["before"], slip["after"]))
    return dict(
        period=p.as_json(),
        sessions=delta(sum(cur), sum(prev)), search_clicks=delta(one(clicks, (s, e)), one(clicks, (ps, pe))),
        position=dict(value=one(pos, (s, e)), prev=one(pos, (ps, pe))),
        visitor_to_lead=dict(value=metrics.ratio(leads_cur, sum(cur)), prev=metrics.ratio(leads_prev, sum(prev))),
        series=dict(cur=cur, prev=aligned, start=s, prev_label="{} week{} earlier".format(weeks, "" if weeks == 1 else "s")),
        annotation=annotation, pages=pages, queries=queries, forms=forms,
        form_leads=sum(f["submissions"] for f in forms), inbound_leads=leads_cur, semrush=semrush.view(conn),
    )


# ------------------------------------------------------------------------------- leads

def company_kind(industry, icp):
    """Which kind of company a lead is from: a target segment, another industry, or not known."""
    industry = (industry or "").strip()
    return (scoring.in_segment(industry, icp) or OTHER_INDUSTRY) if industry else NO_COMPANY


def lead_row(r, now, thr, icp=None):
    quiet = (now.date() - datetime.fromisoformat(r["owner_updated_at"] or r["created_at"]).date()).days
    waiting = r["status"] in metrics.OPEN_STATUSES and quiet >= 3
    if waiting:
        last = "No owner update · {}d".format(quiet)
    elif r["last_activity"]:
        last = "{} · {}".format(r["last_activity"], ago(now, r["last_activity_at"] or r["created_at"]))
    else:
        last = ""
    return dict(id=r["id"], name=r["name"], company=r["company"], initials=initials(r["name"]), channel_id=r["channel_id"],
                owner=r["owner"], status=r["status"], score=r["score"], qualified=r["score"] >= thr,
                industry=r["industry"], source=r["lead_source"], kind=company_kind(r["industry"], icp) if icp else None,
                age=age_short(now, r["created_at"]), age_tone="neg" if waiting and quiet >= 7 else "warn" if waiting else "ink2",
                last=last)


def leads(conn, now, p, q="", channel="", owner="", status="", score="", needs_update=False, limit=50, offset=0, segment="",
          age="", activity=""):
    thr = scoring.threshold(conn)
    icp = scoring.profile(conn)
    kinds = list(icp["segments"]) + [OTHER_INDUSTRY, NO_COMPANY]
    where, args = ["created_at >= ?", "created_at < ?"], [p.start_dt, p.end_dt]
    if needs_update:  # quiet leads matter whenever they arrived, so this filter ignores the date range
        where, args = [metrics.needs_update_sql()], [now.date().isoformat(), 3]
    if q:
        where.append("(name LIKE ? OR company LIKE ? OR lead_source LIKE ?)")
        args += ["%" + q + "%"] * 3
    ids = metrics.resolve_channels(conn, channel)
    if ids is not None:
        where.append("channel_id IN ({})".format(",".join("?" for _ in ids)))
        args += ids
    if owner:
        where.append("owner = ?")
        args.append(owner)
    if status:
        where.append("status = ?")
        args.append(status)
    if score in ("qualified", "unqualified"):
        where.append("score >= ?" if score == "qualified" else "score < ?")
        args.append(thr)
    elif score == "high":
        where.append("score >= 80")
    elif score == "zero":  # nothing known about the company, so nothing to score
        where.append("score = 0")
    day = lambda back: iso(midnight(now.date() - timedelta(days=back)))
    if age in ("today", "week", "month"):
        where.append("created_at >= ?")
        args.append(day({"today": 0, "week": 6, "month": 29}[age]))
    elif age == "older":
        where.append("created_at < ?")
        args.append(day(29))
    touched = "COALESCE(last_activity_at, owner_updated_at)"
    if activity == "recent":
        where.append(touched + " >= ?")
        args.append(day(6))
    elif activity == "none":
        where.append(touched + " IS NULL")
    cond = " AND ".join(where)
    if segment in kinds:  # the kind of company is worked out from the industry wording, so it is matched here, not in SQL
        every = [r for r in conn.execute("SELECT * FROM leads WHERE " + cond + " ORDER BY created_at DESC", args)
                 if company_kind(r["industry"], icp) == segment]
        total, rows = len(every), every[int(offset):int(offset) + int(limit)]
    else:
        total = conn.execute("SELECT COUNT(*) AS n FROM leads WHERE " + cond, args).fetchone()["n"]
        rows = conn.execute("SELECT * FROM leads WHERE " + cond + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                            args + [int(limit), int(offset)]).fetchall()

    # what the period holds, for the numbers at the top and the counts on the filter buttons
    span = (p.start_dt, p.end_dt)
    head = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(score >= ?), 0) AS q FROM leads WHERE created_at >= ? AND created_at < ?",
                        (thr,) + span).fetchone()
    by_kind = dict.fromkeys(kinds, 0)
    for r in conn.execute("SELECT industry, COUNT(*) AS n FROM leads WHERE created_at >= ? AND created_at < ? GROUP BY industry", span):
        by_kind[company_kind(r["industry"], icp)] += r["n"]
    count = lambda column: [dict(id=r[0], n=r[1]) for r in conn.execute(
        "SELECT {0}, COUNT(*) FROM leads WHERE created_at >= ? AND created_at < ? AND {0} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC".format(column), span)]
    return dict(period=p.as_json(), rows=[lead_row(r, now, thr, icp) for r in rows], total=total,
                period_total=head["n"], period_qualified=head["q"], waiting=metrics.count_needs_update(conn, now, 3),
                threshold=thr, targets=len(icp["segments"]),
                facets=dict(channels=count("channel_id"), statuses=count("status"), owners=count("owner"),
                            kinds=[dict(id=k, n=by_kind[k]) for k in kinds]))


def reminder_rows(conn, lead_id):
    rows = conn.execute("SELECT * FROM reminders WHERE lead_id = ? ORDER BY sent_at DESC", (lead_id,)).fetchall()
    out = []
    for i, r in enumerate(rows):
        sent = datetime.fromisoformat(r["sent_at"])
        days = 3 if r["rule"] == "r3" else 7
        if r["opened_at"]:
            opened = datetime.fromisoformat(r["opened_at"])
            read = "opened {:02d}:{:02d}".format(opened.hour, opened.minute) if opened.date() == sent.date() else "opened " + day_label(opened.date())
        else:
            read = "not opened"
        updated = datetime.fromisoformat(r["owner_updated_at"]) if r["owner_updated_at"] else None
        if updated and (updated - sent).total_seconds() <= 86400:
            outcome, tone = "Updated {:02d}:{:02d}".format(updated.hour, updated.minute), "pos"
        elif i == 0 and not updated:
            outcome, tone = ("No update", "neg") if r["rule"] == "r7" else ("Awaiting update", "warn")
        else:
            outcome, tone = "No update", "warn"
        out.append(dict(title="{}-day nudge · {}".format(days, stamp(sent)),
                        detail="Email to {} · {}".format(r["owner"] or "owner", read), outcome=outcome, tone=tone))
    return out


def lead_detail(conn, now, lead_id):
    r = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not r:
        return None
    thr = scoring.threshold(conn)
    items = {i["criterion_key"]: i for i in conn.execute("SELECT * FROM lead_score_items WHERE lead_id = ?", (lead_id,))}
    groups = {}
    for c in scoring.criteria(conn):
        item = items.get(c["key"])
        g = groups.setdefault(c["grp"], dict(label=c["grp"], points=0, max=0, items=[]))
        pts = scoring.points(c["weight"], item["fraction"]) if item else 0
        g["points"] += pts
        g["max"] += c["weight"]
        g["items"].append(dict(label=c["label"], why=item["why"] if item else "Not scored yet", points=pts, max=c["weight"]))
    events = conn.execute("SELECT * FROM lead_events WHERE lead_id = ? ORDER BY at DESC, id DESC", (lead_id,)).fetchall()

    def touch(prefix, label):
        if not r[prefix + "_at"]:
            return None
        return dict(label=label, channel_id=r[prefix + "_channel"], detail=r[prefix + "_detail"],
                    when=day_label(datetime.fromisoformat(r[prefix + "_at"]).date()))

    out = lead_row(r, now, thr)
    out.update(
        title=r["title"], threshold=thr, groups=list(groups.values()),
        company_facts=[dict(k="Employees", v="{:,}".format(r["employees"])) if r["employees"] is not None
                       else dict(k="Company size", v=r["company_size"] or "—"),
                       dict(k="Annual revenue", v=money.money_short(r["revenue"]) if r["revenue"] else "—"),
                       dict(k="Industry", v=r["industry"] or "—"), dict(k="Headquarters", v=r["hq"] or "—"),
                       dict(k="Website", v=r["website"] or "—"), dict(k="Founded", v=str(r["founded"]) if r["founded"] else "—")],
        enriched="Enriched via {} · {}".format(r["enriched_via"], day_label(datetime.fromisoformat(r["enriched_at"]).date()))
        if r["enriched_at"] else "Not enriched yet",
        touches=[t for t in (touch("ft", "First touch"), touch("lt", "Last touch")) if t],
        timeline=[dict(title=e["title"], detail=e["detail"], when=stamp(e["at"]), kind=e["kind"], channel_id=e["channel_id"])
                  for e in events],
        reminders=reminder_rows(conn, lead_id),
        zoho_url="{}/{}".format(config.ZOHO_LEAD_URL.rstrip("/"), r["zoho_id"]) if config.ZOHO_LEAD_URL and r["zoho_id"] else None,
    )
    return out


# ------------------------------------------------------------------------------- lead quality

def quality(conn, now, p):
    thr = scoring.threshold(conn)
    hist = [0] * 10
    for r in conn.execute("SELECT MIN(score / 10, 9) AS b, COUNT(*) AS n FROM leads WHERE created_at >= ? AND created_at < ? GROUP BY b",
                          (p.start_dt, p.end_dt)):
        hist[r["b"]] = r["n"]
    by = {r["channel_id"]: r for r in conn.execute(
        "SELECT channel_id, COUNT(*) AS n, AVG(score) AS avg, SUM(score >= ?) AS q FROM leads "
        "WHERE created_at >= ? AND created_at < ? GROUP BY channel_id", (thr, p.start_dt, p.end_dt))}
    chans = [dict(id=cid, avg=r["avg"], leads=r["n"], qualified=r["q"] or 0) for cid, r in by.items() if cid]
    changed_at = get_setting(conn, "scoring_changed_at")
    changed = "Last changed {} by {}".format(day_label(date.fromisoformat(changed_at)), get_setting(conn, "scoring_changed_by", "")) if changed_at else ""
    return dict(period=p.as_json(), threshold=thr, hist=hist, total=sum(hist), coverage=research.coverage(conn, p.start_dt, p.end_dt),
                qualified=sum(r["q"] or 0 for r in by.values()),
                channels=chans, criteria=scoring.criteria(conn), changed=changed, clarity=clarity(conn, p, thr))


# What can be said about each lead, in the order the checks are made. A lead lands in the first one that is true.
VERDICTS = [
    ("fits", "Qualified"),                      # scores at or above the bar
    ("no_fit", "Checked, not a fit"),           # company known, wrong industry or too small
    ("person", "Probably a person, not a company"),  # personal or no email and no real company name: nothing to check
    ("pending", "Company not checked yet"),     # a company name or work email is there, the lookup has not run
    ("not_found", "Company checked, not found"),  # the lookup ran and came back empty
]


def clarity(conn, p, thr):
    """How many of the period's leads can be judged, why the rest cannot, and what is known about each lead."""
    own = research.squash(get_setting(conn, "company", ""))
    looked = {r["key"]: r["status"] for r in conn.execute("SELECT key, status FROM companies")}
    keys = [k for k, _ in VERDICTS]
    total, by_channel = dict.fromkeys(keys, 0), {}
    known = dict(leads=0, email=0, work_email=0, company=0, industry=0, size=0, title=0, from_crm=0, from_lookup=0)
    for r in conn.execute("SELECT * FROM leads WHERE created_at >= ? AND created_at < ?", (p.start_dt, p.end_dt)):
        lead = dict(r)
        industry = (lead["industry"] or "").strip()
        domain = research.clean_domain((lead["email"] or "").split("@")[-1]) if "@" in (lead["email"] or "") else ""
        work = bool(domain) and research.usable(domain, own)
        named = research.company_key(dict(lead, email="", website=""), own) is not None
        key = research.company_key(lead, own)
        if lead["score"] >= thr:
            verdict = "fits"
        elif industry:
            verdict = "no_fit"
        elif key is None:
            verdict = "person"
        else:
            verdict = "not_found" if looked.get(key) == "not_found" else "pending"
        total[verdict] += 1
        row = by_channel.setdefault(lead["channel_id"], dict(id=lead["channel_id"], leads=0, **dict.fromkeys(keys, 0)))
        row["leads"] += 1
        row[verdict] += 1
        known["leads"] += 1
        known["email"] += bool(domain)
        known["work_email"] += work
        known["company"] += named
        known["industry"] += bool(industry)
        known["size"] += bool(lead["employees"] or (lead["company_size"] or "").strip())
        known["title"] += bool((lead["title"] or "").strip())
        if industry:
            known["from_lookup" if lead["industry_via"] == research.SOURCE else "from_crm"] += 1
    return dict(verdicts=[dict(id=k, label=label, n=total[k]) for k, label in VERDICTS], known=known,
                by_channel=sorted((r for r in by_channel.values() if r["id"]), key=lambda r: -r["leads"]),
                lookup_ready=research.configured())


# ------------------------------------------------------------------------------- subscriptions

def subscriptions(conn, now):
    tools = []
    for r in conn.execute("SELECT * FROM subscriptions ORDER BY renews_on IS NULL, renews_on, name"):
        t = dict(r)
        t["days"] = (date.fromisoformat(r["renews_on"]) - now.date()).days if r["renews_on"] else None
        t["renews_label"] = day_label(date.fromisoformat(r["renews_on"]), year=r["renews_on"][:4] != str(now.year)) if r["renews_on"] else "—"
        tools.append(t)
    history = [dict(month=MONTHS[int(r["month"][5:]) - 1], total=r["total"]) for r in
               conn.execute("SELECT * FROM subscription_history WHERE month < ? ORDER BY month DESC LIMIT 5", (month_key(now.date()),))][::-1]
    return dict(tools=tools, history=history, month=MONTHS[now.month - 1])


# ------------------------------------------------------------------------------- reports

def reports(conn, now):
    wk = insights.week_compare(conn, now)
    p = wk["period"]
    cur, prev = wk["cur"], wk["prev"]
    report = narrative.ensure_draft(conn, now)
    sunday = p.s + timedelta(days=6)
    week_label = ("{}–{} {}".format(p.s.day, sunday.day, MONTHS_LONG[sunday.month - 1]) if p.s.month == sunday.month
                  else "{} – {}".format(day_label(p.s), day_label(sunday)))
    next_send = p.s + timedelta(days=7)
    past = []
    for r in conn.execute("SELECT * FROM reports WHERE status = 'sent' ORDER BY week_start DESC LIMIT 6"):
        start = date.fromisoformat(r["week_start"])
        past.append(dict(label=span_label(start, start + timedelta(days=6)).replace(" – ", "–"), headline=r["headline"],
                         opened="Opened {} of {}".format(r["opened"], r["recipients"]) if r["recipients"] else ""))
    day_names = WEEKDAYS[p.s.weekday()] + ("–" + WEEKDAYS[p.e.weekday()] if p.e != p.s else "")
    return dict(
        company=get_setting(conn, "company", ""), week_label="Week of " + week_label,
        pill="{} · data to {} {}".format("Draft" if report["status"] == "draft" else "Sent", WEEKDAYS[now.weekday()], day_label(now.date())),
        kpis=dict(leads=delta(cur["leads"], prev["leads"]), qualified=delta(cur["qualified"], prev["qualified"]),
                  spend=delta(cur["spend"], prev["spend"]),
                  cpql=delta(metrics.cost_per(cur["spend"], cur["qualified"]), metrics.cost_per(prev["spend"], prev["qualified"]))),
        channels=sorted((dict(id=c["id"], leads=c["leads"], diff=c["diff"]) for c in wk["channels"]), key=lambda c: -c["leads"]),
        channel_label="Leads by channel, " + day_names,
        report=dict(headline=report["headline"], body=report["body"] or "", next_steps=report["next_steps"] or "", status=report["status"]),
        schedule=[("Sends", "{}s, {}".format(get_setting(conn, "report_day", "Monday"), get_setting(conn, "report_time", "08:00"))),
                  ("Next", "{} {}".format(WEEKDAYS[next_send.weekday()], day_label(next_send))),
                  ("Covers", "Previous Mon–Sun"), ("Summary", "Drafted from the data, editable")],
        recipients=[dict(r) for r in conn.execute("SELECT * FROM report_recipients ORDER BY id")], past=past,
    )


# ------------------------------------------------------------------------------- alerts and reminders

def alerts_page(conn, now):
    month_start = iso(midnight(now.date().replace(day=1)))
    sent = {r["rule"]: r for r in conn.execute(
        "SELECT rule, COUNT(*) AS n, SUM(owner_updated_at IS NOT NULL AND julianday(owner_updated_at) - julianday(sent_at) <= 1) AS quick "
        "FROM reminders WHERE sent_at >= ? GROUP BY rule", (month_start,))}
    fired = {r["rule_key"]: r["at"] for r in conn.execute("SELECT rule_key, MAX(created_at) AS at FROM alerts GROUP BY rule_key")}
    reminder_rules, alert_rules = [], []
    for r in conn.execute("SELECT * FROM alert_rules ORDER BY sort"):
        if r["kind"] == "reminder":
            s = sent.get(r["key"])
            reminder_rules.append(dict(key=r["key"], title=r["title"], detail=r["detail"], enabled=bool(r["enabled"]),
                                       sent=s["n"] if s else 0, rate=(s["quick"] or 0) / s["n"] * 100 if s and s["n"] else None))
        else:
            alert_rules.append(dict(key=r["key"], title=r["title"], detail=r["detail"], deliver_to=r["deliver_to"],
                                    enabled=bool(r["enabled"]), last=fired_label(now, fired.get(r["key"]))))
    open_now = [dict(title=r["title"], detail=r["detail"], tone=TONE.get(r["severity"], "ink3"), when=ago(now, r["created_at"]), rule=r["rule_key"])
                for r in conn.execute("SELECT * FROM alerts WHERE resolved_at IS NULL ORDER BY severity = 'neg' DESC, severity = 'warn' DESC, created_at DESC")]
    queued = conn.execute("SELECT COUNT(*) FROM outbox WHERE sent_at IS NULL").fetchone()[0]
    return dict(open=open_now, waiting=metrics.count_needs_update(conn, now, 3),
                reminder_rules=reminder_rules, alert_rules=alert_rules,
                health=health.run(conn, now), groups=health.GROUPS, drop_pct=health.DROP_PCT,
                email_ready=bool(config.SMTP_HOST), queued=queued,
                renewals=[dict(name=r["name"], renews_on=r["renews_on"], days=(date.fromisoformat(r["renews_on"]) - now.date()).days,
                               owner=r["owner"], email=r["email"]) for r in conn.execute(
                                   "SELECT * FROM subscriptions WHERE renews_on IS NOT NULL ORDER BY renews_on")])


# ------------------------------------------------------------------------------- settings

def settings(conn, now, p):
    sources = []
    for s in insights.source_states(conn, now):
        when = ago(now, s["last_sync_at"]) if s["last_sync_at"] else None
        if s["state"] == "connected":
            text, action = "Synced " + when + (" · " + s["note"] if s["note"] else ""), "Sync now"
        elif s["state"] == "stale":
            text, action = "Last sync {:.0f} h ago".format(s["hours"]) + (" · " + s["note"] if s["note"] else ""), "Retry"
        elif s["state"] == "disconnected":
            text, action = ("Last synced " + when) if when else "Disconnected", "Reconnect"
        else:
            text, action = ("Last run " + when) if when else "Never synced", "Connect"
        sources.append(dict(key=s["key"], name=s["name"], detail=s["detail"], state=s["state"], synced=text, action=action,
                            initials=initials(s["name"])))
    sess = {(r["source"], r["medium"]): r["n"] for r in conn.execute(
        "SELECT source, medium, SUM(sessions) AS n FROM traffic_daily WHERE date BETWEEN ? AND ? GROUP BY source, medium",
        (p.s.isoformat(), p.e.isoformat()))}
    by_tag = {(r["s"], r["m"]): r["n"] for r in conn.execute(
        "SELECT lower(utm_source) AS s, lower(utm_medium) AS m, COUNT(*) AS n FROM leads WHERE COALESCE(utm_source, '') <> '' GROUP BY 1, 2")}
    by_source = {r["s"]: r["n"] for r in conn.execute(
        "SELECT " + ingest.SOURCE_SQL.format("leads") + " AS s, COUNT(*) AS n FROM leads WHERE " + ingest.UNTAGGED_SQL.format("leads") + " GROUP BY 1")}
    left_out = {r["s"]: r["n"] for r in conn.execute("SELECT lower(source) AS s, COUNT(*) AS n FROM left_out_leads GROUP BY 1")}
    utm = []
    for r in conn.execute("SELECT * FROM utm_map ORDER BY id"):
        is_source = r["medium"] == ingest.LEAD_SOURCE
        low = r["source"].lower()
        utm.append(dict(
            id=r["id"], source=r["source"], medium=r["medium"], channel_id=r["channel_id"], is_source=is_source,
            label="No lead source in Zoho" if r["source"] == ingest.NO_SOURCE else r["source"] if is_source else "{} / {}".format(r["source"], r["medium"]),
            excluded=bool(r["excluded"]), left_out=left_out.get(low, 0) if is_source else 0,
            sessions=sess.get((r["source"], r["medium"]), 0),
            leads=by_source.get(low, 0) if is_source else by_tag.get((low, r["medium"].lower()), 0)))
    # sources waiting to be placed first, then placed ones by size, then the ones left out
    utm.sort(key=lambda u: (2 if u["excluded"] else 1 if u["channel_id"] else 0, -u["leads"] - u["left_out"], -u["sessions"]))

    this, nxt = now.date().replace(day=1), next_month(now.date())
    months = [dict(key=month_key(d), label=MONTHS_LONG[d.month - 1]) for d in (this, nxt)]
    values = {m["key"]: narrative.targets_for(conn, m["key"]) for m in months}
    labels = [("leads", "Leads", "int", None), ("qualified", "Qualified leads", "int", None), ("pipeline", "Pipeline", "money_m", None),
              ("won", "Deals won", "int", None), ("budget_meta", "Meta ads", "money", "meta"), ("budget_li", "LinkedIn ads", "money", "li"),
              ("budget_organic", "Organic and content", "money", "search"), ("budget_outbound", "Outbound", "money", "apollo")]
    targets = dict(months=months, rows=[dict(key=k, label=label, kind=kind, channel_id=ch, values=[values[m["key"]].get(k) for m in months])
                                        for k, label, kind, ch in labels])
    users = []
    for r in conn.execute("SELECT * FROM users ORDER BY id"):
        seen = datetime.fromisoformat(r["last_active_at"]) if r["last_active_at"] else None
        if not seen:
            last = "Never"
        elif (now - seen).total_seconds() < 300:
            last = "Now"
        elif (now.date() - seen.date()).days >= 2:
            last = "{} {}".format(WEEKDAYS[seen.weekday()], day_label(seen.date()))
        else:
            last = ago(now, seen)
        users.append(dict(name=r["name"], team=r["team"], role=r["role"], last=last, initials=initials(r["name"])))
    return dict(period=p.as_json(), company=get_setting(conn, "company", ""), sources=sources, utm=utm, targets=targets, users=users)

"""Derived findings shared by the screens, the alert rules and the report draft."""

from datetime import datetime, timedelta

from . import metrics, scoring
from .money import money
from .periods import Period, day_label, days_in_month, month_key

PLATFORMS = {"meta": "Meta", "li": "LinkedIn"}


def week_compare(conn, now):
    """Week to date against last week to the same point, with the per-channel gap."""
    p = Period(now, "week")
    thr = scoring.threshold(conn)
    cur, prev = metrics.channel_stats(conn, p.cur, thr), metrics.channel_stats(conn, p.prev, thr)
    rows = []
    for ch in metrics.channels(conn):
        c, v = cur.get(ch["id"], metrics.empty_stats()), prev.get(ch["id"], metrics.empty_stats())
        rows.append(dict(id=ch["id"], name=ch["name"], narrative=ch["narrative"], grp=ch["grp"],
                         leads=c["leads"], prev=v["leads"], diff=c["leads"] - v["leads"]))
    tc, tp = metrics.total(cur), metrics.total(prev)
    return dict(period=p, cur=tc, prev=tp, channels=rows, pct=metrics.pct_change(tc["leads"], tp["leads"]))


def cost_spikes(conn, now, min_spend=1000, min_rise=25):
    """Campaigns whose cost per lead over the last 3 days is well above the 3 days before."""
    today = now.date()
    recent = (today - timedelta(days=2), today)
    before = (today - timedelta(days=5), today - timedelta(days=3))
    out = []

    def window(a, b):
        return {r["id"]: r for r in conn.execute(
            "SELECT c.id, c.name, c.platform, SUM(d.spend) AS spend, SUM(d.leads) AS leads FROM ad_daily d "
            "JOIN ad_creatives cr ON cr.id = d.creative_id JOIN ad_campaigns c ON c.id = cr.campaign_id "
            "WHERE d.date BETWEEN ? AND ? GROUP BY c.id", (a.isoformat(), b.isoformat()))}

    now_rows, old_rows = window(*recent), window(*before)
    for cid, r in now_rows.items():
        o = old_rows.get(cid)
        if not o or r["spend"] < min_spend or not r["leads"] or not o["leads"]:
            continue
        cpl, was = r["spend"] / r["leads"], o["spend"] / o["leads"]
        rise = (cpl - was) / was * 100
        if rise > min_rise:
            out.append(dict(campaign_id=cid, campaign=r["name"], platform=r["platform"], before=was, after=cpl, pct=rise))
    return sorted(out, key=lambda x: -x["pct"])


def pacing(conn, now, platform):
    """Month-to-date ad spend against the monthly plan, with a projection to month end."""
    today = now.date()
    first, dim, day = today.replace(day=1), days_in_month(today), today.day
    by_day = {r["date"]: r["spend"] for r in conn.execute(
        "SELECT d.date, SUM(d.spend) AS spend FROM ad_daily d JOIN ad_creatives cr ON cr.id = d.creative_id "
        "JOIN ad_campaigns c ON c.id = cr.campaign_id WHERE c.platform = ? AND d.date BETWEEN ? AND ? GROUP BY d.date",
        (platform, first.isoformat(), today.isoformat()))}
    cumulative, running = [], 0
    for i in range(day):
        running += by_day.get((first + timedelta(days=i)).isoformat(), 0)
        cumulative.append(running)
    spent = running
    row = conn.execute("SELECT value FROM targets WHERE month = ? AND key = ?",
                       (month_key(today), "budget_" + platform)).fetchone()
    plan = row["value"] if row else None
    projected = spent / day * dim
    out = dict(platform=platform, spent=spent, plan=plan, projected=projected, cumulative=cumulative, day=day,
               days_in_month=dim, elapsed_pct=day / dim * 100, status=None, tone="ink2", note="", daily_cap=None)
    if not plan:
        out["note"] = "No budget set for this month. Add one in Settings."
        return out

    over = projected > plan * 1.03
    diff = abs(projected - plan)
    out["status"], out["tone"] = ("Over-pacing", "warn") if over else ("On pace", "pos")
    left = dim - day
    if over and left:
        out["daily_cap"] = max(0, round((plan - spent) / left / 10) * 10)
        top = conn.execute(
            "SELECT c.name, SUM(d.spend) AS spend FROM ad_daily d JOIN ad_creatives cr ON cr.id = d.creative_id "
            "JOIN ad_campaigns c ON c.id = cr.campaign_id WHERE c.platform = ? AND c.status = 'Active' "
            "AND d.date BETWEEN ? AND ? GROUP BY c.id ORDER BY spend DESC LIMIT 1",
            (platform, first.isoformat(), today.isoformat())).fetchone()
        note = "Projected to finish {} over plan.".format(money(diff))
        if top:
            cap = round(((plan - spent) / left - (spent - top["spend"]) / day) / 10) * 10
            if cap > 0:
                note += " Capping “{}” at {} a day would land on plan.".format(top["name"], money(cap))
            else:
                note += " Total spend needs to fall to {} a day to land on plan.".format(money(out["daily_cap"]))
        out["note"] = note
    elif over:
        out["note"] = "Finishing {} over plan.".format(money(diff))
    else:
        out["note"] = "Projected to finish {} under plan. No change needed.".format(money(diff))
    return out


def ranking_drop(conn, start, end, min_slip=3.0):
    """The sharpest search-ranking slip in a date range: {date, query, before, after} or None."""
    best = None
    by_query = {}
    for r in conn.execute("SELECT query, date, position FROM query_daily WHERE date BETWEEN ? AND ? "
                          "AND position IS NOT NULL ORDER BY query, date", (start.isoformat(), end.isoformat())):
        by_query.setdefault(r["query"], []).append((r["date"], r["position"]))
    for query, series in by_query.items():
        for i in range(3, len(series) - 2):
            before = sum(p for _, p in series[i - 3:i]) / 3
            after = sum(p for _, p in series[i:i + 3]) / 3
            if after - before >= min_slip and (best is None or after - before > best["slip"]):
                best = dict(date=series[i][0], query=query, before=before, after=after, slip=after - before)
    if best:
        best["label"] = day_label(datetime.fromisoformat(best["date"]).date())
    return best


def stale_by_owner(conn, now, days=7):
    """[(owner, count)] for open leads with no owner update in `days` calendar days."""
    return [(r["owner"], r["n"]) for r in conn.execute(
        "SELECT owner, COUNT(*) AS n FROM leads WHERE " + metrics.needs_update_sql() +
        " GROUP BY owner ORDER BY n DESC, owner", (now.date().isoformat(), days))]


def source_states(conn, now):
    """Each data source with its effective state: connected, stale, disconnected or not_connected."""
    out = []
    for r in conn.execute("SELECT * FROM sources ORDER BY sort"):
        s = dict(r)
        s["state"] = s["status"]
        s["hours"] = None
        if s["last_sync_at"]:
            s["hours"] = (now - datetime.fromisoformat(s["last_sync_at"])).total_seconds() / 3600
            if s["status"] == "connected" and s["hours"] > s["stale_after_hours"]:
                s["state"] = "stale"
        out.append(s)
    return out

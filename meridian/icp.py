"""The ideal customer page: who actually buys, worked out from every deal in the CRM.

Eight questions are answered from the deals and the leads behind them: who buys, who is worth most, who buys
fastest, who takes effort and rarely buys, where the good ones come from, who inside the company says yes, how
big the market is, and what to do next. Each answer says how many deals it rests on, and says "cannot tell yet"
when too little is recorded, so nobody reads a pattern into a handful of deals.
"""

import re
from datetime import date, timedelta

from . import metrics, scoring

NOT_RECORDED = "Not recorded"
SMALL = "Other (few deals each)"
MIN_CLOSED = 10      # closed deals a group needs before its win rate is quoted
MIN_WON = 3          # won deals a group needs before its value or speed is quoted
SPANS = {"all": None, "24": 730, "12": 365}
SIZES = ["Over 500 staff", "200 to 500 staff", "Under 200 staff", NOT_RECORDED]
SENIOR = [("Owner or C-level", r"\b(ceo|cfo|coo|cmo|cto|cio|cbo|cxo|chief|founder|owner|president|managing director|md|partner|proprietor)\b"),
          ("Head, VP or director", r"\b(head|vp|vice president|director|gm|general manager|avp|svp)\b"),
          ("Manager", r"\b(manager|lead|mgr)\b")]
DIMENSIONS = {"industry": "Industry", "size": "Company size", "channel": "Channel", "source": "Lead source", "role": "Buyer's role"}


def size_band(lead):
    """Company size from an employee count, or from the size label typed in the CRM ("201-500 employees", "Enterprise", "SMB")."""
    n = lead["employees"]
    label = (lead["company_size"] or "").lower()
    if n is None:
        if re.search(r"enterp|entrep", label):
            return SIZES[0]
        if "mid" in label:
            return SIZES[1]
        if re.search(r"smb|small|start|<\s*200", label):
            return SIZES[2]
        m = re.search(r"\d[\d,]*", label)
        if not m:
            return NOT_RECORDED
        n = int(m.group(0).replace(",", ""))
    return SIZES[0] if n > 500 else SIZES[1] if n >= 200 else SIZES[2]


def role_band(title):
    text = (title or "").strip().lower()
    if not text:
        return NOT_RECORDED
    return next((name for name, pattern in SENIOR if re.search(pattern, text)), "Other staff")


def median(values):
    values = sorted(values)
    return values[len(values) // 2] if values else None


def days_between(a, b):
    try:
        return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days
    except (TypeError, ValueError):
        return None


def view(conn, now, span="all"):
    span = span if span in SPANS else "all"
    since = (now.date() - timedelta(days=SPANS[span])).isoformat() if SPANS[span] else "0000"
    profile = scoring.profile(conn)
    names = {c["id"]: c["name"] for c in metrics.channels(conn)}
    deals = [dict(r) for r in conn.execute(
        "SELECT d.stage, d.amount, d.created_at, d.closed_at, COALESCE(d.lead_source, l.lead_source) AS source, COALESCE(l.channel_id, d.channel_id) AS channel, "
        "l.industry, l.company_size, l.employees, l.title FROM deals d LEFT JOIN leads l ON l.id = d.lead_id WHERE d.created_at >= ?", (since,))]
    for d in deals:
        industry = (d["industry"] or "").strip()
        segment = scoring.in_segment(industry, profile) if industry else None
        d["keys"] = dict(industry=segment or (industry.title() if industry else NOT_RECORDED), size=size_band(d), channel=names.get(d["channel"], NOT_RECORDED),
                         source=(d["source"] or "").strip() or NOT_RECORDED, role=role_band(d["title"]))
        d["target"] = bool(segment)
        d["days"] = days_between(d["created_at"], d["closed_at"]) if d["stage"] == "won" and d["closed_at"] else None

    def summarise(rows, name, target=False):
        won = [r for r in rows if r["stage"] == "won"]
        lost = sum(1 for r in rows if r["stage"] == "lost")
        closed = len(won) + lost
        value = sum(r["amount"] or 0 for r in won)
        valued = [r["amount"] for r in won if r["amount"]]
        return dict(name=name, target=target, deals=len(rows), won=len(won), lost=lost, open=len(rows) - closed, closed=closed,
                    win_rate=len(won) / closed * 100 if closed else None, won_value=value, avg_value=median(valued),  # the middle deal, so one giant deal cannot bend the picture
                    largest=max(valued) if valued else None,
                    median_days=median([r["days"] for r in won if r["days"] is not None and r["days"] >= 0]))

    def grouped(dim):
        groups = {}
        for d in deals:
            groups.setdefault(d["keys"][dim], []).append(d)
        rows, small = [], []
        for name, members in groups.items():
            if dim in ("industry", "source") and name != NOT_RECORDED and len(members) < 5 and not any(m["target"] for m in members if dim == "industry"):
                small += members  # a long tail of one-off labels says nothing by itself
            else:
                rows.append(summarise(members, name, dim == "industry" and any(m["target"] for m in members)))
        rows.sort(key=lambda r: (r["name"] == NOT_RECORDED, -r["deals"]))
        if small:
            rows.append(summarise(small, SMALL))
        return rows

    tables = {dim: grouped(dim) for dim in DIMENSIONS}
    total = summarise(deals, "All deals")
    won = [d for d in deals if d["stage"] == "won"]
    recorded = {dim: sum(1 for d in won if d["keys"][dim] != NOT_RECORDED) for dim in DIMENSIONS}

    def named(dim):
        return [r for r in tables[dim] if r["name"] not in (NOT_RECORDED, SMALL)]

    def best(dim, field, floor_field, floor, lowest=False):
        rows = [r for r in named(dim) if r[floor_field] >= floor and r[field] is not None]
        return (min if lowest else max)(rows, key=lambda r: r[field]) if rows else None

    base = total["win_rate"] or 0
    avoid = sorted((r for dim in ("industry", "size", "channel") for r in [dict(x, dim=DIMENSIONS[dim]) for x in named(dim)]
                    if r["closed"] >= 15 and r["win_rate"] is not None and r["win_rate"] < base * 0.6), key=lambda r: r["win_rate"])
    # leads of the last 12 months that match the profile on industry, and on industry and size together
    year = (now.date() - timedelta(days=365)).isoformat()
    lead_count = in_industry = in_both = 0
    for l in conn.execute("SELECT industry, company_size, employees FROM leads WHERE created_at >= ?", (year,)):
        lead_count += 1
        if (l["industry"] or "").strip() and scoring.in_segment(l["industry"], profile):
            in_industry += 1
            in_both += size_band(l) in SIZES[:2]
    return dict(span=span, total=total, tables=tables, dimensions=DIMENSIONS, recorded=recorded, won=len(won),
                segments=list(profile["segments"]), min_closed=MIN_CLOSED, min_won=MIN_WON,
                answers=dict(
                    buys=best("industry", "win_rate", "closed", MIN_CLOSED), buys_size=best("size", "win_rate", "closed", MIN_CLOSED),
                    worth=best("industry", "avg_value", "won", MIN_WON), worth_size=best("size", "avg_value", "won", MIN_WON),
                    fastest=best("industry", "median_days", "won", MIN_WON, lowest=True), fastest_channel=best("channel", "median_days", "won", MIN_WON, lowest=True),
                    avoid=avoid[:5],
                    channel=best("channel", "win_rate", "closed", MIN_CLOSED), channel_value=best("channel", "won_value", "won", MIN_WON),
                    role=best("role", "won", "won", MIN_WON),
                    market=dict(leads=lead_count, in_industry=in_industry, in_both=in_both)))

"""The ideal customer page.

Three things, each worked out from the CRM:
  1. a picture of the best customer (the kind of company that buys most often, what a deal is worth, how long it takes)
  2. where deals are won and lost, by industry, company size and how the customer found us
  3. whether the leads coming in now are that kind of company

Most won deals have no industry written down, so a leader can label them here. Labels are kept on the deal in
Meridian and are not written back to the CRM.
"""

import re

from . import metrics, scoring

MIN_DEALS = 10   # finished deals a group needs before it is listed
SIZES = ["More than 500 staff", "200 to 500 staff", "Fewer than 200 staff"]
INDUSTRIES = ["Healthcare", "Automobile", "BFSI", "Retail", "Real estate", "Travel and hospitality", "Education", "Technology", "Manufacturing", "Other"]
WEB = ("website", "chatbot")


class IcpError(Exception):
    pass


def size_band(row):
    """Company size from an employee count or from the label in the CRM ("201-500 employees", "Enterprise", "SMB"). None when unknown."""
    label = (row["company_size"] or "").strip()
    if label in SIZES:
        return label
    n, low = row["employees"], label.lower()
    if n is None:
        if re.search(r"enterp|entrep", low):
            return SIZES[0]
        if "mid" in low:
            return SIZES[1]
        if re.search(r"smb|small|start|<\s*200", low):
            return SIZES[2]
        m = re.search(r"\d[\d,]*", low)
        if not m:
            return None
        n = int(m.group(0).replace(",", ""))
    return SIZES[0] if n > 500 else SIZES[1] if n >= 200 else SIZES[2]


def middle(values):
    values = sorted(values)
    return values[len(values) // 2] if values else None


def view(conn, now, p):
    profile = scoring.profile(conn)
    names = {c["id"]: c["name"] for c in metrics.channels(conn)}
    deals = [dict(r) for r in conn.execute(
        "SELECT d.id, d.name, d.stage, d.amount, d.created_at, d.closed_at, COALESCE(l.channel_id, d.channel_id) AS channel, "
        "COALESCE(NULLIF(d.industry, ''), l.industry) AS industry, COALESCE(NULLIF(d.company_size, ''), l.company_size) AS company_size, l.employees "
        "FROM deals d LEFT JOIN leads l ON l.id = d.lead_id")]
    for d in deals:
        text = (d["industry"] or "").strip()
        d["group"] = dict(industry=(scoring.in_segment(text, profile) or text[:1].upper() + text[1:].lower()) if text else None, size=size_band(d), channel=names.get(d["channel"]))

    def rows(key):
        """Each group with enough finished deals: how many of every 100 it wins. Best first."""
        groups = {}
        for d in deals:
            if d["stage"] in ("won", "lost") and d["group"][key]:
                g = groups.setdefault(d["group"][key], [0, 0])
                g[0] += 1
                g[1] += d["stage"] == "won"
        out = [dict(name=k, deals=n, won=w, per_100=round(w / n * 100)) for k, (n, w) in groups.items() if n >= MIN_DEALS]
        out.sort(key=lambda r: (-r["per_100"], -r["deals"]))
        return out, sum(1 for n, _ in groups.values() if n < MIN_DEALS)

    industry, small_industries = rows("industry")
    size, _ = rows("size")
    channel, _ = rows("channel")
    won = [d for d in deals if d["stage"] == "won"]
    labelled = [d for d in won if d["group"]["industry"]]
    days = []
    for d in won:
        try:
            from datetime import date
            days.append((date.fromisoformat(d["closed_at"][:10]) - date.fromisoformat(d["created_at"][:10])).days)
        except (TypeError, ValueError):
            pass
    best = [r["name"] for r in industry[:2] if r["per_100"] > 0]
    card = dict(industry=best, size=size[0]["name"] if size else None, channel=channel[0]["name"] if channel else None,
                deal=middle([d["amount"] for d in won if d["amount"]]), days=middle([x for x in days if x >= 0]))

    # the period's leads: do they look like the customer we want? (a target industry, and 200 or more staff)
    leads = {}
    for l in conn.execute("SELECT channel_id, industry, company_size, employees FROM leads WHERE created_at >= ? AND created_at < ?", (p.start_dt, p.end_dt)):
        text, band = (l["industry"] or "").strip(), size_band(l)
        kind = "unknown" if not text or not band else "match" if scoring.in_segment(text, profile) and band in SIZES[:2] else "other"
        row = leads.setdefault(names.get(l["channel_id"], "Channel not known"), dict(match=0, other=0, unknown=0))
        row[kind] += 1
    by_channel = sorted((dict(name=k, total=sum(v.values()), **v) for k, v in leads.items()), key=lambda r: -r["total"])
    totals = {k: sum(r[k] for r in by_channel) for k in ("match", "other", "unknown", "total")}

    return dict(period=p.as_json(), card=card, industry=industry, size=size, channel=channel, small_industries=small_industries,
                no_industry=sum(1 for d in deals if d["stage"] in ("won", "lost") and not d["group"]["industry"]),
                customers=len(won), labelled=len(labelled), targets=list(profile["segments"]),
                to_label=[dict(id=d["id"], name=d["name"] or "Deal with no name", size=d["group"]["size"] or "") for d in
                          sorted(won, key=lambda d: d["closed_at"] or "", reverse=True) if not d["group"]["industry"]],
                industries=INDUSTRIES, sizes=SIZES, leads=by_channel, lead_totals=totals)


def label(conn, deal_id, industry, size):
    """Write a won customer's industry and size on its deal."""
    if industry not in INDUSTRIES:
        raise IcpError("Pick the industry.")
    if size and size not in SIZES:
        raise IcpError("Pick the company size from the list.")
    if not conn.execute("UPDATE deals SET industry = ?, company_size = COALESCE(NULLIF(?, ''), company_size) WHERE id = ?", (industry, size or "", deal_id)).rowcount:
        raise IcpError("That deal is no longer there.")

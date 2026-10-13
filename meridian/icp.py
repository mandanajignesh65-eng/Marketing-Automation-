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


# ------------------------------------------------------------------------------- planning: every segment in detail

NOT_KNOWN = "Not known"
KINDS = {"industry": "Industry", "size": "Company size", "department": "Department", "seniority": "Seniority", "channel": "How they found us", "city": "City"}
SENIORITY = [("Owner or C-level", r"\b(ceo|cfo|coo|cmo|cto|cio|cbo|cxo|chief|founder|co-founder|cofounder|owner|president|chairman|managing director|md|proprietor|partner)\b"),
             ("Head, VP or director", r"\b(head|vp|vice president|director|gm|general manager|avp|svp|evp)\b"),
             ("Manager", r"\b(manager|lead|mgr|supervisor)\b")]
DEPARTMENTS = [("Marketing", r"marketing|brand|growth|digital|content|seo\b|communications?|\bcmo\b|advertis|social media|demand"),
               ("Sales and business", r"sales|business development|\bbd\b|\bbdm\b|revenue|partnership|account|commercial|\bcro\b"),
               ("Customer service", r"customer|\bcx\b|support|service|success|contact cent|call cent|experience"),
               ("Technology", r"\bit\b|technolog|tech\b|engineer|developer|\bcto\b|\bcio\b|software|data\b|architect|automation"),
               ("Product", r"product"),
               ("Operations", r"operations?|\bops\b|\bcoo\b|process|supply|admin"),
               ("Finance", r"financ|\bcfo\b|accounts?\b|treasury"),
               ("People and HR", r"\bhr\b|human|people|talent|recruit"),
               ("Owner or general management", r"founder|\bceo\b|owner|managing director|\bmd\b|president|chairman|proprietor|partner|director|general manager|chief executive")]
PRODUCTS = [("WhatsApp", r"whatsapp|\bwa\b|waba"), ("Chatbot or AI agent", r"chatbot|\bbot\b|agent|\bai\b"), ("Voice", r"voice|ivr|calling"), ("RCS", r"\brcs\b"),
            ("SMS", r"\bsms\b"), ("Campaigns", r"campaign|marketing"), ("Customer support", r"support|\bcx\b|service")]
CITY = {"gurugram": "Delhi NCR", "gurgaon": "Delhi NCR", "delhi": "Delhi NCR", "new delhi": "Delhi NCR", "noida": "Delhi NCR", "delhi/ncr": "Delhi NCR", "delhi ncr": "Delhi NCR",
        "ncr": "Delhi NCR", "bengaluru": "Bangalore", "bombay": "Mumbai", "navi mumbai": "Mumbai", "thane": "Mumbai"}
BLANK = {"", "na", "n/a", "n.a", "n.a.", "-", "--", "none", "null", "nil", ".", "test", "not applicable", "not available"}


def seniority(title):
    text = (title or "").strip().lower()
    if text in BLANK:
        return None
    return next((name for name, pattern in SENIORITY if re.search(pattern, text)), "Other staff")


def department(title):
    text = (title or "").strip().lower()
    if text in BLANK:
        return None
    return next((name for name, pattern in DEPARTMENTS if re.search(pattern, text)), "Other")


def city(text):
    first = (text or "").split(",")[0].strip().lower()
    if first in BLANK:
        return None
    return CITY.get(first, first.title())


_kept = {}  # the labelled leads and deals, kept for a short while so opening one segment after another is quick
KEEP_SECONDS = 180


def forget():
    _kept.clear()


def records(conn, now):
    """Every lead and every deal with the labels used for planning: industry, size, department, seniority, channel, city."""
    import time
    from . import config
    key = str(config.db_path())
    if key in _kept and time.time() - _kept[key][0] < KEEP_SECONDS:
        return _kept[key][1]
    profile = scoring.profile(conn)
    names = {c["id"]: c["name"] for c in metrics.channels(conn)}
    seen = {}  # each industry, title and city is worked out once however many leads carry it

    def once(kind, text, fn):
        if (kind, text) not in seen:
            seen[(kind, text)] = fn(text)
        return seen[(kind, text)]

    def tags(row, industry, size_row):
        text = (industry or "").strip()
        return dict(industry=once("i", text, lambda t: scoring.in_segment(t, profile) or t[:1].upper() + t[1:].lower()) if text else None,
                    size=size_band(size_row), department=once("d", row["title"], department), seniority=once("s", row["title"], seniority),
                    channel=names.get(row["channel"]), city=once("c", row["hq"], city))
    leads = []
    for r in conn.execute("SELECT id, title, hq, industry, company_size, employees, channel_id AS channel, created_at FROM leads"):
        leads.append(dict(tags(r, r["industry"], r), month=r["created_at"][:7], title=(r["title"] or "").strip()))
    deals = []
    for r in conn.execute(
            "SELECT d.name, d.stage, d.amount, d.created_at, d.closed_at, COALESCE(l.channel_id, d.channel_id) AS channel, l.title, l.hq, l.employees, "
            "COALESCE(NULLIF(d.industry, ''), l.industry) AS industry, COALESCE(NULLIF(d.company_size, ''), l.company_size) AS company_size "
            "FROM deals d LEFT JOIN leads l ON l.id = d.lead_id"):
        row = dict(tags(r, r["industry"], r), stage=r["stage"], amount=r["amount"] or 0, name=r["name"] or "", opened=r["created_at"][:7],
                   closed=(r["closed_at"] or "")[:7], closed_at=r["closed_at"] or "", days=None)
        if r["stage"] == "won" and r["closed_at"]:
            try:
                from datetime import date
                gap = (date.fromisoformat(r["closed_at"][:10]) - date.fromisoformat(r["created_at"][:10])).days
                row["days"] = gap if gap >= 0 else None
            except ValueError:
                pass
        deals.append(row)
    y, m = now.year, now.month
    months = ["{:04d}-{:02d}".format((y * 12 + m - 1 - back) // 12, (y * 12 + m - 1 - back) % 12 + 1) for back in range(11, -1, -1)]
    _kept[key] = (time.time(), (leads, deals, months, set(profile["segments"])))
    return _kept[key][1]


def figures(leads, deals, months):
    """The headline numbers for any set of leads and deals. Lead counts are the last twelve months; deals are every deal."""
    won = [d for d in deals if d["stage"] == "won"]
    lost = sum(1 for d in deals if d["stage"] == "lost")
    open_deals = [d for d in deals if d["stage"] == "open"]
    closed = len(won) + lost
    recent = set(months)
    return dict(leads=sum(1 for l in leads if l["month"] in recent), leads_ever=len(leads), deals=len(deals), won=len(won), lost=lost, closed=closed,
                per_100=round(len(won) / closed * 100) if closed >= 5 else None, typical=middle([d["amount"] for d in won if d["amount"]]),
                total_won=sum(d["amount"] for d in won), days=middle([d["days"] for d in won if d["days"] is not None]),
                open=len(open_deals), open_value=sum(d["amount"] for d in open_deals))


def split(leads, deals, months, key, targets=()):
    """One row per value of `key` (an industry, a size, a department...), biggest first, with the unknown ones last."""
    groups = {}
    for l in leads:
        groups.setdefault(l[key] or NOT_KNOWN, ([], []))[0].append(l)
    for d in deals:
        groups.setdefault(d[key] or NOT_KNOWN, ([], []))[1].append(d)
    rows = [dict(name=name, target=name in targets, **figures(ls, ds, months)) for name, (ls, ds) in groups.items()]
    rows = [r for r in rows if r["name"] == NOT_KNOWN or r["leads"] >= 5 or r["deals"] >= 3]
    rows.sort(key=lambda r: (r["name"] == NOT_KNOWN, -r["leads"], -r["deals"]))
    return rows


def compare(conn, now):
    leads, deals, months, targets = records(conn, now)
    return dict(industry=split(leads, deals, months, "industry", targets), department=split(leads, deals, months, "department"),
                seniority=split(leads, deals, months, "seniority"), kinds=KINDS,
                all=figures(leads, deals, months))


def profile(conn, now, kind, value):
    """Everything known about one segment: its numbers, its flow by month, and how it splits every other way."""
    if kind not in KINDS:
        raise IcpError("There is no such view.")
    leads, deals, months, targets = records(conn, now)
    mine_l = [l for l in leads if (l[kind] or NOT_KNOWN) == value]
    mine_d = [d for d in deals if (d[kind] or NOT_KNOWN) == value]
    if not mine_l and not mine_d:
        raise IcpError("There is nothing recorded for “{}”.".format(value))
    flow = [dict(month=m, leads=sum(1 for l in mine_l if l["month"] == m), deals=sum(1 for d in mine_d if d["opened"] == m),
                 won=sum(1 for d in mine_d if d["stage"] == "won" and d["closed"] == m)) for m in months]
    splits = {k: [r for r in split(mine_l, mine_d, months, k, targets if k == "industry" else ())][:9] for k in KINDS if k != kind}
    titles = {}
    for l in mine_l:
        if l["title"].lower() not in BLANK:
            titles[l["title"].lower()] = titles.get(l["title"].lower(), 0) + 1
    won = sorted((d for d in mine_d if d["stage"] == "won"), key=lambda d: d["closed_at"], reverse=True)
    bought = []
    for name, pattern in PRODUCTS:
        hits = [d for d in mine_d if re.search(pattern, d["name"].lower())]
        if hits:
            bought.append(dict(name=name, deals=len(hits), won=sum(1 for d in hits if d["stage"] == "won")))
    bought.sort(key=lambda r: -r["deals"])
    return dict(kind=kind, kind_label=KINDS[kind], value=value, target=kind == "industry" and value in targets, figures=figures(mine_l, mine_d, months),
                all=figures(leads, deals, months), flow=flow, splits=splits, kinds=KINDS,
                titles=[dict(name=k.title(), n=n) for k, n in sorted(titles.items(), key=lambda kv: -kv[1])[:10]], titled=sum(titles.values()),
                customers=[dict(name=d["name"] or "Deal with no name", amount=d["amount"], month=d["closed"]) for d in won[:20]], customer_count=len(won),
                bought=bought, named=sum(1 for d in mine_d if any(re.search(p, d["name"].lower()) for _, p in PRODUCTS)))


def label(conn, deal_id, industry, size):
    """Write a won customer's industry and size on its deal."""
    if industry not in INDUSTRIES:
        raise IcpError("Pick the industry.")
    if size and size not in SIZES:
        raise IcpError("Pick the company size from the list.")
    forget()
    if not conn.execute("UPDATE deals SET industry = ?, company_size = COALESCE(NULLIF(?, ''), company_size) WHERE id = ?", (industry, size or "", deal_id)).rowcount:
        raise IcpError("That deal is no longer there.")

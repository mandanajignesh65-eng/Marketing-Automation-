"""Lead scoring: weighted criteria, a qualifying threshold, and rules for new leads."""

import re

from .db import get_setting, is_demo, set_setting
from .money import money_short

DEFAULT_THRESHOLD = 65

# The ideal customer profile the fit criteria score against. Full points inside the range, half in the band below it.
# This one belongs to the sample company; LIVE_ICP below is Chat360's own.
ICP = dict(
    employees=(200, 2000), employees_half=(50, 199),
    revenue=(50e6, 500e6), revenue_half=(20e6, 50e6),
    # Priority segments: name -> wording that places an industry in it (see in_segment).
    segments={"Logistics": ["logistics"], "Healthcare": ["healthcare"], "Manufacturing": ["manufacturing"],
              "Construction": ["construction"], "Energy": ["energy"]},
    exact=True,  # the sample's industries are clean, so they must equal a segment's name
    # CRM size bands, used when there is no employee count: (wording found in the label, share of the points).
    # Labels are typed by hand in the CRM, so matching is loose ("Enterpise", "Mid- Market", "SMBs").
    size_bands=[("enterp", 1.0), ("entrep", 1.0), ("mid", 1.0), ("smb", 0.5), ("small", 0.5), ("start", 0.5)],
)
# Chat360's ideal customers: four segments, mid-market and enterprise. Industry is typed by hand in Zoho
# ("Hospitals and Health Care", "INSURANCE", "Ecomm / Retail"), so each segment lists the wording that belongs to it:
# whole words, or the start of a word when it ends in * ("insur*" finds "insurance" but "hospital" skips "hospitality").
LIVE_ICP = dict(
    ICP, employees=(200, None), employees_half=(1, 199), exact=False,
    segments={
        "Healthcare": ["health*", "hospital", "hospitals", "pharma*", "medical", "diagnostic*", "clinic*"],
        "Retail": ["retail*", "ecom*", "e-com*", "apparel", "fashion", "fmcg", "consumer goods", "jewel*", "garment*", "cosmetic*"],
        "Automobile": ["automo*", "vehicle*", "ev"],
        "BFSI": ["bfsi", "bank*", "financ*", "insur*", "nbfc*", "fintech", "lending", "investment*"],
    },
)
FIT_KEYS = ("size", "industry", "revenue")
REQUEST_FORMS = {"demo", "contact", "trial"}


def profile(conn):
    """The ideal customer profile for this database: the sample company's, or Chat360's on live data."""
    return ICP if is_demo(conn) else LIVE_ICP


def revenue_range(icp=ICP):
    return "{}–{}".format(money_short(icp["revenue"][0]), money_short(icp["revenue"][1]))


def span(lo, hi):
    return "{:,}–{:,}".format(lo, hi) if hi else "{:,}+".format(lo)


def in_segment(industry, icp):
    """The priority segment an industry belongs to, or None."""
    text = industry.strip().lower()
    for name, words in icp["segments"].items():
        if icp.get("exact"):
            if text == name.lower():
                return name
        elif any(re.search(r"\b" + re.escape(w.rstrip("*")) + ("" if w.endswith("*") else r"\b"), text) for w in words):
            return name
    return None


# Weights for a database fed by the CRM alone: it knows the company, not web or email behaviour,
# so fit carries the whole score until intent signals are connected.
# Being in a priority segment is enough to qualify; company size refines it. Revenue is not recorded in the CRM.
FIT_ONLY_WEIGHTS = dict(size=30, industry=70, revenue=0, demo=0, pricing=0, email=0)


def default_criteria(fit_only=False):
    """(key, group, label, rule text shown in the editor, default weight). Call after the currency is set.

    fit_only is a live database fed by the CRM alone, which is also the one scored against Chat360's profile.
    """
    rows = _criteria(LIVE_ICP if fit_only else ICP)
    return [(k, g, label, rule, FIT_ONLY_WEIGHTS[k] if fit_only else w) for k, g, label, rule, w in rows]


def _criteria(icp):
    names = [n if n.isupper() else n.lower() for n in icp["segments"]]
    industries = ", ".join(names)
    return [
        ("size", "Fit", "Company size", "{} employees for full points, {} for half".format(span(*icp["employees"]), span(*icp["employees_half"]))
         if icp["employees"][1] else "Mid-market or enterprise ({} employees) for full points, smaller companies for half".format(span(*icp["employees"])), 20),
        ("industry", "Fit", "Industry", industries[0].upper() + industries[1:], 15),
        ("revenue", "Fit", "Annual revenue", "{} for full points, {}–{} for half".format(
            revenue_range(icp), money_short(icp["revenue_half"][0]), money_short(icp["revenue_half"][1])), 15),
        ("demo", "Intent", "Demo or contact request", "Any demo, contact sales or trial form", 20),
        ("pricing", "Intent", "Pricing page", "5 points per visit in the last 14 days", 15),
        ("email", "Intent", "Email engagement", "Opens and replies across sequences and newsletters", 15),
    ]

# SQLite ROUND and points() below must agree, so previews match saved scores.
SCORE_SQL = "CAST(ROUND({w} * i.fraction) AS INTEGER)"


def points(weight, fraction):
    return int(weight * fraction + 0.5)


def threshold(conn):
    return int(get_setting(conn, "qualify_threshold", DEFAULT_THRESHOLD))


def criteria(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM scoring_criteria ORDER BY sort")]


def evaluate(lead, icp=ICP):
    """Score a new lead from its enrichment data and intent signals, against an ideal customer profile.

    Returns [(criterion_key, fraction, why)]. Missing data scores zero rather than guessing.
    """
    out = []

    emp = lead.get("employees")
    band = (lead.get("company_size") or "").strip()
    counted = None  # the band's own wording, when the headcount was read from it
    if emp is None and band:  # a headcount range such as "501-1,000 employees" counts as its lower bound
        first = re.search(r"\d[\d,]*", band)
        emp = int(first.group().replace(",", "")) if first and "emp" in band.lower() and not re.search("[a-z]", band.lower().split("emp")[0]) else None
        counted = band if emp is not None else None
    if emp is None and band:
        frac = next((f for word, f in icp["size_bands"] if word in band.lower()), None)
        out.append(("size", frac or 0.0, band if frac is not None else "Size not recorded"))
    elif emp is None:
        out.append(("size", 0.0, "Company size unknown"))
    else:
        (lo, hi), (half_lo, half_hi) = icp["employees"], icp["employees_half"]
        frac = 1.0 if lo <= emp <= (hi or emp) else 0.5 if half_lo <= emp <= half_hi else 0.0
        out.append(("size", frac, "{} · ICP is {}".format(counted or "{:,} employees".format(emp), span(lo, hi))))

    industry = (lead.get("industry") or "").strip()
    if not industry:
        out.append(("industry", 0.0, "Industry unknown"))
    else:
        segment = in_segment(industry, icp)
        named = segment and segment.lower() != industry.lower()
        out.append(("industry", 1.0 if segment else 0.0,
                    industry + (" · priority vertical" + (" ({})".format(segment) if named else "") if segment else " · not a priority vertical")))

    rev = lead.get("revenue")
    if rev is None:
        out.append(("revenue", 0.0, "Revenue unknown"))
    else:
        (lo, hi), (half_lo, half_hi) = icp["revenue"], icp["revenue_half"]
        frac = 1.0 if lo <= rev <= hi else 0.5 if half_lo <= rev < lo else 0.0
        out.append(("revenue", frac, money_short(rev) + " · ICP is " + revenue_range(icp)))

    form = (lead.get("form") or "").lower()
    out.append(("demo", 1.0 if form in REQUEST_FORMS else 0.0,
                "Submitted" if form in REQUEST_FORMS else "Not yet"))

    visits = int(lead.get("pricing_visits") or 0)
    out.append(("pricing", min(1.0, visits / 3.0),
                "{} visit{} in 14 days".format(visits, "" if visits == 1 else "s") if visits else "No visits"))

    sent = int(lead.get("emails_sent") or 0)
    opened = int(lead.get("emails_opened") or 0)
    out.append(("email", (opened / sent) if sent else 0.0,
                "Opened {} of {}".format(opened, sent) if sent else "No emails yet"))
    return out


def refresh_fit(conn):
    """Re-judge company fit for every lead from its stored company details, then rescore.

    Run after the ideal-customer profile changes. Intent items are left as they are.
    """
    icp = profile(conn)
    rows = conn.execute("SELECT id, employees, revenue, industry, company_size FROM leads").fetchall()
    conn.executemany(
        "INSERT OR REPLACE INTO lead_score_items (lead_id, criterion_key, fraction, why) VALUES (?, ?, ?, ?)",
        [(r["id"], k, f, why) for r in rows for k, f, why in evaluate(dict(r), icp) if k in FIT_KEYS])
    rescore(conn)
    return len(rows)


def store_items(conn, lead_id, items):
    conn.executemany(
        "INSERT OR REPLACE INTO lead_score_items (lead_id, criterion_key, fraction, why) VALUES (?, ?, ?, ?)",
        [(lead_id, k, f, why) for k, f, why in items],
    )


def rescore(conn, lead_id=None):
    """Recompute score, fit and intent from stored fractions and current weights."""
    where = "WHERE leads.id = ?" if lead_id is not None else ""
    args = (lead_id,) if lead_id is not None else ()
    part = SCORE_SQL.format(w="c.weight")
    sub = ("COALESCE((SELECT SUM(" + part + ") FROM lead_score_items i "
           "JOIN scoring_criteria c ON c.key = i.criterion_key WHERE i.lead_id = leads.id{grp}), 0)")
    conn.execute(
        "UPDATE leads SET score = {all}, fit = {fit}, intent = {intent} {where}".format(
            all=sub.format(grp=""), fit=sub.format(grp=" AND c.grp = 'Fit'"),
            intent=sub.format(grp=" AND c.grp = 'Intent'"), where=where),
        args,
    )


def count_qualified(conn, weights, thr, start_dt, end_dt):
    """How many leads created in the window would qualify under trial weights and threshold."""
    values = ",".join("(?, ?)" for _ in weights)
    args = [x for kv in weights.items() for x in kv] + [start_dt, end_dt, thr]
    row = conn.execute(
        "WITH w (key, weight) AS (VALUES " + values + ") "
        "SELECT COUNT(*) AS n FROM (SELECT l.id, SUM(" + SCORE_SQL.format(w="w.weight") + ") AS s "
        "FROM leads l JOIN lead_score_items i ON i.lead_id = l.id JOIN w ON w.key = i.criterion_key "
        "WHERE l.created_at >= ? AND l.created_at < ? GROUP BY l.id) WHERE s >= ?",
        args,
    ).fetchone()
    return row["n"]


def save(conn, weights, thr):
    for key, weight in weights.items():
        conn.execute("UPDATE scoring_criteria SET weight = ? WHERE key = ?", (int(weight), key))
    set_setting(conn, "qualify_threshold", int(thr))
    rescore(conn)

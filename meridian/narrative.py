"""Plain-language summaries written from the figures: the Overview sentence and the weekly report draft.

These are template-based first drafts. The weekly draft is stored and can be edited before it is sent.
"""

from . import insights, metrics, scoring
from .money import money
from .periods import MONTHS_LONG, Period, days_in_month, month_key


def ordinal(n):
    n = int(round(n))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "{}{}".format(n, suffix)


def targets_for(conn, month):
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM targets WHERE month = ?", (month,))}


def cap(text):
    return text[0].upper() + text[1:]


def pace_phrase(actual, target, now):
    """'on pace', 'slightly behind' or 'behind target' for a month-to-date figure, or None without a target."""
    if not target:
        return None
    share = actual / (now.day / days_in_month(now.date())) / target
    return "on pace" if share >= 1 else "slightly behind" if share >= 0.9 else "behind target"


def week_sentence(wk):
    """Segments describing week to date against last week."""
    pct = wk["pct"]
    if pct is None:
        return []
    if abs(pct) < 5:
        return [{"t": " This week is level with last week."}]
    behind = pct < 0
    segs = [{"t": " This week is "},
            {"t": "{:.0f}% {} last week".format(abs(pct), "behind" if behind else "ahead of"), "tone": "neg" if behind else "pos"}]
    mover = (min if behind else max)(wk["channels"], key=lambda c: c["diff"])
    if (mover["diff"] < 0) == behind and mover["diff"]:
        segs.append({"t": ", mostly from {}.".format(mover["narrative"])})
    else:
        segs.append({"t": "."})
    return segs


def overview_summary(conn, now, period, cur, prev, filtered):
    """The Overview's one-paragraph read of the period, as [{t, tone?}] segments."""
    leads = "{:,} lead{}".format(cur["leads"], "" if cur["leads"] == 1 else "s")
    change = metrics.pct_change(cur["leads"], prev["leads"])
    if change is not None:
        leads += ", {} {:.0f}% on {}".format("up" if change >= 0 else "down", abs(change), period.prev_name())

    if period.rng == "month":
        month = MONTHS_LONG[now.month - 1]
        pace = None if filtered else pace_phrase(cur["leads"], targets_for(conn, month_key(now.date())).get("leads"), now)
        segs = [{"t": "{} is {}: ".format(month, pace) if pace else "{} so far: ".format(month)}, {"t": leads, "tone": "ink"}]
    else:
        segs = [{"t": {"day": "Today so far: ", "week": "This week so far: "}.get(period.rng, "In this range: ")},
                {"t": leads, "tone": "ink"}]

    a, b = metrics.ratio(cur["spend"], cur["qualified"]), metrics.ratio(prev["spend"], prev["qualified"])
    if a and b and abs(a - b) / b >= 0.01:
        segs.append({"t": ", at a {} cost per qualified lead.".format("lower" if a < b else "higher")})
    else:
        segs.append({"t": "."})
    if period.rng == "month" and not filtered:
        segs += week_sentence(insights.week_compare(conn, now))
    return segs


def weekly_draft(conn, now):
    """First draft of the weekly leadership report: headline, body paragraphs and next steps."""
    thr = scoring.threshold(conn)
    wk = insights.week_compare(conn, now)
    cur, prev, pct = wk["cur"]["leads"], wk["prev"]["leads"], wk["pct"]
    month = Period(now, "month")
    m_cur = metrics.total(metrics.channel_stats(conn, month.cur, thr))
    m_prev = metrics.total(metrics.channel_stats(conn, month.prev, thr))
    targets = targets_for(conn, month_key(now.date()))
    lead_pace = pace_phrase(m_cur["leads"], targets.get("leads"), now)
    qual_pace = pace_phrase(m_cur["qualified"], targets.get("qualified"), now)
    on_pace = lead_pace == "on pace"
    slip = insights.ranking_drop(conn, now.date().replace(day=1), now.date())
    paras, steps = [], []

    # 1. Volume this week
    if pct is None:
        p = "{} leads so far this week.".format(cur)
    elif abs(pct) < 5:
        p = "Leads are level with last week: {} against {} at the same point.".format(cur, prev)
    else:
        behind = pct < 0
        p = "Leads are running {:.0f}% {} last week: {} against {} at the same point.".format(
            abs(pct), "behind" if behind else "ahead of", cur, prev)
        mover = (min if behind else max)(wk["channels"], key=lambda c: c["diff"])
        if behind and mover["diff"] < 0:
            p += " {} accounts for {} of the {}-lead gap.".format(cap(mover["narrative"]), min(prev - cur, -mover["diff"]), prev - cur)
            if slip and mover["id"] == "search":
                p += " On {} our ranking for “{}” slipped from {} to {}.".format(
                    slip["label"], slip["query"], ordinal(slip["before"]), ordinal(slip["after"]))
                steps.append("Refresh the page that ranks for “{}” and rebuild internal links to recover the position.".format(slip["query"]))
        elif not behind and mover["diff"] > 0:
            p += " {} added the most, up {} leads.".format(cap(mover["narrative"]), mover["diff"])
    paras.append(p)

    # 2. Paid
    paid_cur = sum(c["leads"] for c in wk["channels"] if c["grp"] == "paid")
    paid_prev = sum(c["prev"] for c in wk["channels"] if c["grp"] == "paid")
    paid = metrics.pct_change(paid_cur, paid_prev)
    if not paid_cur and not paid_prev:
        p = ""
    elif paid is None or abs(paid) < 10:
        p = "Paid is steady on volume."
    else:
        p = "Paid volume is {} {:.0f}% on last week.".format("up" if paid > 0 else "down", abs(paid))
    for spike in insights.cost_spikes(conn, now)[:1]:
        p += " {} cost per lead rose {:.0f}% on “{}”, from {} to {} over three days.".format(
            insights.PLATFORMS.get(spike["platform"], spike["platform"]), spike["pct"], spike["campaign"],
            money(spike["before"]), money(spike["after"]))
    if p:
        paras.append(p.strip())
    for platform, label in insights.PLATFORMS.items():
        pace = insights.pacing(conn, now, platform)
        if pace["status"] == "Over-pacing" and pace["daily_cap"]:
            steps.append("Hold {} spend at {} a day so the month lands on plan.".format(label, money(pace["daily_cap"])))

    # 3. The month
    if targets.get("leads") and targets.get("qualified"):
        if on_pace and qual_pace == "on pace":
            p = "For the month, we remain on pace for {:,.0f} leads and {:,.0f} qualified.".format(targets["leads"], targets["qualified"])
        else:
            p = "For the month, leads are {} and qualified leads are {} against targets of {:,.0f} and {:,.0f}.".format(
                lead_pace, qual_pace, targets["leads"], targets["qualified"])
    else:
        p = "For the month so far: {:,} leads and {:,} qualified.".format(m_cur["leads"], m_cur["qualified"])
    a, b = metrics.ratio(m_cur["spend"], m_cur["qualified"]), metrics.ratio(m_prev["spend"], m_prev["qualified"])
    if a and b:
        p += " Cost per qualified lead is {} {:.0f}% on {} at {}.".format(
            "down" if a < b else "up", abs(a - b) / b * 100, month.prev_name(), money(a))
    paras.append(p)

    stale = sum(n for _, n in insights.stale_by_owner(conn, now, 7))
    if stale:
        steps.append("Clear the {} lead{} that have had no owner update for a week.".format(stale, "" if stale == 1 else "s"))

    if pct is not None and pct <= -10:
        headline = "A softer week for leads, still on pace for the month" if on_pace else "A softer week for leads, and the month is behind"
    elif pct is not None and pct >= 10:
        headline = "A strong week for leads" + (", and the month is on pace" if on_pace else "")
    else:
        headline = "A steady week" + (", on pace for the month" if on_pace else "")
    return dict(headline=headline, body="\n\n".join(paras), next_steps="\n".join(steps))


def ensure_draft(conn, now, rewrite=False):
    """This week's report row. Until someone edits the draft, its text is rewritten from the latest figures."""
    week = Period(now, "week").s.isoformat()
    row = conn.execute("SELECT * FROM reports WHERE week_start = ?", (week,)).fetchone()
    if row and (row["edited"] or row["status"] != "draft") and not rewrite:
        return row
    d = weekly_draft(conn, now)
    conn.execute("INSERT INTO reports (week_start, status, headline, body, next_steps) VALUES (?, 'draft', ?, ?, ?) "
                 "ON CONFLICT (week_start) DO UPDATE SET headline = excluded.headline, body = excluded.body, "
                 "next_steps = excluded.next_steps, edited = 0", (week, d["headline"], d["body"], d["next_steps"]))
    return conn.execute("SELECT * FROM reports WHERE week_start = ?", (week,)).fetchone()

"""Core figures: per-channel funnel counts for a window, and the helpers built on them."""

GROUPS = [("organic", "Inbound · organic"), ("paid", "Inbound · paid"), ("events", "Events"), ("outbound", "Outbound")]
# Open leads older than this are history, not work waiting on an owner, so they are not chased.
REMINDER_WINDOW_DAYS = 60
GROUP_LABEL = dict(GROUPS)
STAT_KEYS = ["impressions", "clicks", "spend", "leads", "qualified", "deals", "won", "pipeline"]
OPEN_STATUSES = ("New", "Contacted")
STATUSES = ["New", "Contacted", "Qualified", "Meeting booked", "Unqualified"]


def channels(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM channels ORDER BY sort")]


def resolve_channels(conn, value):
    """'all' -> None; a group or a channel id -> list of channel ids."""
    if not value or value == "all":
        return None
    if value in GROUP_LABEL:
        return [r["id"] for r in conn.execute("SELECT id FROM channels WHERE grp = ? ORDER BY sort", (value,))]
    return [value]


def in_clause(column, ids):
    """SQL fragment and args restricting a column to channel ids (none = no restriction)."""
    if ids is None:
        return "", []
    return " AND {} IN ({})".format(column, ",".join("?" for _ in ids)), list(ids)


def empty_stats():
    return dict.fromkeys(STAT_KEYS, 0)


def channel_stats(conn, window, threshold):
    """Funnel counts per channel for a window (start_dt, end_dt, start_date, end_date).

    Leads with no channel yet are returned under the key None.
    """
    start_dt, end_dt, s, e = window
    out = {}

    def slot(cid):
        return out.setdefault(cid, empty_stats())

    for r in conn.execute(
            "SELECT channel_id, SUM(impressions) AS i, SUM(clicks) AS c, SUM(spend) AS sp FROM channel_daily "
            "WHERE date BETWEEN ? AND ? GROUP BY channel_id", (s, e)):
        slot(r["channel_id"]).update(impressions=r["i"] or 0, clicks=r["c"] or 0, spend=r["sp"] or 0)
    for r in conn.execute(
            "SELECT channel_id, COUNT(*) AS n, SUM(score >= ?) AS q FROM leads "
            "WHERE created_at >= ? AND created_at < ? GROUP BY channel_id", (threshold, start_dt, end_dt)):
        slot(r["channel_id"]).update(leads=r["n"], qualified=r["q"] or 0)
    for r in conn.execute(
            "SELECT channel_id, COUNT(*) AS n, SUM(amount) AS amt FROM deals "
            "WHERE created_at >= ? AND created_at < ? GROUP BY channel_id", (start_dt, end_dt)):
        slot(r["channel_id"]).update(deals=r["n"], pipeline=r["amt"] or 0)
    for r in conn.execute(
            "SELECT channel_id, COUNT(*) AS n FROM deals WHERE stage = 'won' "
            "AND closed_at >= ? AND closed_at < ? GROUP BY channel_id", (start_dt, end_dt)):
        slot(r["channel_id"])["won"] = r["n"]
    return out


def total(stats, ids=None):
    """Sum per-channel stats, optionally restricted to some channel ids."""
    out = empty_stats()
    for cid, row in stats.items():
        if ids is None or cid in ids:
            for k in STAT_KEYS:
                out[k] += row[k]
    return out


def ratio(a, b):
    return a / b if b else None


def cost_per(spend, count):
    """Cost per lead, deal and so on. None when nothing was spent, so screens show a dash rather than a free result."""
    return spend / count if spend and count else None


def pct_change(cur, prev):
    return (cur - prev) / prev * 100 if prev else None


def needs_update_sql(alias="leads"):
    """SQL predicate for open leads whose owner has gone quiet. Parameters: ?1 today's date, ?2 minimum days.
    Queries using it must number any further parameters from ?3.

    Gaps are counted in calendar days, so a lead touched on the 17th is 3 days quiet on the 20th.
    """
    return ("{a}.status IN ('New', 'Contacted') "
            "AND julianday(date(?1)) - julianday(date(COALESCE({a}.owner_updated_at, {a}.created_at))) >= ?2 "
            "AND julianday(date(?1)) - julianday(date({a}.created_at)) <= {window}"
            ).format(a=alias, window=REMINDER_WINDOW_DAYS)


def count_needs_update(conn, now, days):
    row = conn.execute("SELECT COUNT(*) AS n FROM leads WHERE " + needs_update_sql(),
                       (now.date().isoformat(), days)).fetchone()
    return row["n"]

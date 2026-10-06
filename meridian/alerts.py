"""Alert rules. `run` evaluates the enabled rules, records new alerts and resolves cleared ones."""

from datetime import date

from . import health, insights, mailer
from .money import money
from .periods import iso


def _drop(conn, now):
    wk = insights.week_compare(conn, now)
    cur, prev = wk["cur"]["leads"], wk["prev"]["leads"]
    if not prev or cur >= prev * 0.85:
        return []
    gap = prev - cur
    worst = min(wk["channels"], key=lambda c: c["diff"])
    detail = "{} vs {} at this point last week.".format(cur, prev)
    if worst["diff"] < 0:
        label = worst["narrative"][0].upper() + worst["narrative"][1:]
        detail += " {} accounts for {} of the {}-lead gap.".format(label, min(gap, -worst["diff"]), gap)
    return [dict(dedupe=wk["period"].s.isoformat(), severity="neg",
                 title="Leads down {:.0f}% this week".format(-wk["pct"]), detail=detail)]


def _cost(conn, now):
    week = now.date().isocalendar()
    return [dict(dedupe="{}:{}-W{}".format(s["campaign_id"], week[0], week[1]), severity="warn",
                 title="{} ads cost per lead up {:.0f}%".format(insights.PLATFORMS.get(s["platform"], s["platform"]), s["pct"]),
                 detail="“{}” went from {} to {} over 3 days.".format(s["campaign"], money(s["before"]), money(s["after"])))
            for s in insights.cost_spikes(conn, now)]


def _stale(conn, now):
    owners = insights.stale_by_owner(conn, now, 7)
    n = sum(c for _, c in owners)
    if not n:
        return []
    return [dict(dedupe=now.date().isoformat(), severity="warn",
                 title="{} lead{} with no update for 7+ days".format(n, "" if n == 1 else "s"),
                 detail=", ".join("{} {}".format(o or "Unassigned", c) for o, c in owners[:3])
                 + (" and {} more owners".format(len(owners) - 3) if len(owners) > 3 else "") + ". Reminders go out at 09:00.")]


RENEWAL_NOTICE_DAYS = 30   # first warning
RENEWAL_LATE_DAYS = 14     # how long a passed date keeps being flagged, in case nobody updated it after renewing


def _renew(conn, now):
    """A tool whose renewal date is close, or has passed. It gets louder as the day nears: a lapsed tool can take the website down."""
    out = []
    for r in conn.execute("SELECT * FROM subscriptions WHERE renews_on IS NOT NULL ORDER BY renews_on"):
        left = (date.fromisoformat(r["renews_on"]) - now.date()).days
        if not -RENEWAL_LATE_DAYS <= left <= RENEWAL_NOTICE_DAYS:
            continue
        annual = r["billing"] == "Annual" and r["annual_cost"]
        plan = "Annual plan, " + money(r["annual_cost"]) if annual else "Monthly plan, " + money(r["monthly_cost"])
        seats = " · {} seats".format(r["seats"]) if r["seats"] else ""
        if left < 0:
            title, severity, stage = "{} renewal date passed {} day{} ago".format(r["name"], -left, "" if left == -1 else "s"), "neg", "late"
        elif left == 0:
            title, severity, stage = "{} renews today".format(r["name"]), "neg", "today"
        else:
            title = "{} renews in {} day{}".format(r["name"], left, "" if left == 1 else "s")
            severity, stage = ("neg", "3") if left <= 3 else ("warn", "7") if left <= 7 else ("info", "14") if left <= 14 else ("info", "30")
        check = " Check the card on file and that it will not lapse." if left <= 7 else ""
        # one alert per stage, so it shows up again as new at 30, 14, 7 and 3 days, on the day, and if the date passes
        when = date.fromisoformat(r["renews_on"])
        out.append(dict(dedupe="{}:{}:{}".format(r["id"], r["renews_on"], stage), severity=severity, title=title,
                        detail="{}{} · owner {}.{}".format(plan, seats, r["owner"] or "unassigned", check),
                        email=r["email"] if "email" in r.keys() else None,
                        email_body="Hello{},\n\n{}. The renewal date is {} {} {}.\n{}.\n\nPlease make sure it is renewed and that the card on file "
                                   "will not be declined, so the service does not stop.\n\nSent by Meridian.".format(
                                       " " + r["owner"] if r["owner"] else "", title, when.day, when.strftime("%B"), when.year, plan + seats)))
    return out


def _sync(conn, now):
    out = []
    for s in insights.source_states(conn, now):
        if s["state"] == "stale":
            out.append(dict(dedupe="{}:{}".format(s["key"], now.date().isoformat()), severity="warn",
                            title="{} has not synced for {:.0f} hours".format(s["name"], s["hours"]),
                            detail=s["note"] or "The last sync did not complete."))
        elif s["state"] == "disconnected":
            out.append(dict(dedupe="{}:{}".format(s["key"], now.date().isoformat()), severity="neg",
                            title="{} is disconnected".format(s["name"]),
                            detail=s["note"] or "Reconnect it in Settings."))
    return out


def _budget(conn, now):
    out = []
    for platform, label in insights.PLATFORMS.items():
        p = insights.pacing(conn, now, platform)
        if p["plan"] and p["projected"] > p["plan"] * 1.05:
            out.append(dict(dedupe="{}:{}".format(platform, now.strftime("%Y-%m")), severity="warn",
                            title="{} ads projected {:.0f}% over plan".format(label, (p["projected"] / p["plan"] - 1) * 100),
                            detail=p["note"]))
    return out


RULES = {"benchmark": health.alerts_below, "trend": health.alerts_dropped, "drop": _drop, "cost": _cost, "r7": _stale,
         "renew": _renew, "sync": _sync, "budget": _budget}


def run(conn, now):
    """Evaluate enabled rules. Returns the alerts that are new this run."""
    enabled = {r["key"] for r in conn.execute("SELECT key FROM alert_rules WHERE enabled = 1")}
    fresh = []
    for key, rule in RULES.items():
        found = rule(conn, now) if key in enabled else []
        live = {a["dedupe"] for a in found}
        for a in found:
            cur = conn.execute(
                "INSERT OR IGNORE INTO alerts (rule_key, dedupe, title, detail, severity, created_at) VALUES (?,?,?,?,?,?)",
                (key, a["dedupe"], a["title"], a["detail"], a["severity"], iso(now)))
            if cur.rowcount:
                fresh.append(dict(a, rule_key=key))
                if a.get("email"):  # queued now; it is only sent once outgoing email has been set up
                    mailer.queue(conn, now, "renewal", a["email"], a["title"], a["email_body"])
            else:  # still firing: keep the wording current
                conn.execute("UPDATE alerts SET title = ?, detail = ?, resolved_at = NULL WHERE rule_key = ? AND dedupe = ?",
                             (a["title"], a["detail"], key, a["dedupe"]))
        for row in conn.execute("SELECT id, dedupe FROM alerts WHERE rule_key = ? AND resolved_at IS NULL", (key,)).fetchall():
            if row["dedupe"] not in live:
                conn.execute("UPDATE alerts SET resolved_at = ? WHERE id = ?", (iso(now), row["id"]))
    return fresh

"""Targets and the daily checklist: who is aiming for what this week and month, how far along they are, and what is in the way.

A target belongs to one person and one period (a week or a month). It is either counted by Meridian itself from
connected data (requests sent, replies, leads, visits...) or counted by hand, where the person logs what they did
(a post published, a blog written). Each working day a target asks for a fair share of what is still left, and
that share is the person's checklist for the day, next to any one-off tasks. A blocker is a note that stays open
until someone marks it solved.
"""

import math
from datetime import date, timedelta

from . import scoring
from .db import get_setting, set_setting
from .periods import MONTHS, iso

WORKING_DAYS = (0, 1, 2, 3, 4)  # Monday to Friday
WEB_LEADS, OUTREACH_LEADS = ("website", "chatbot"), ("apollo", "heyreach", "outbound_other")


def _outbound(channel, column):
    return ("SELECT d.date AS day, SUM(d.{}) AS n FROM outbound_daily d JOIN outbound_campaigns c ON c.id = d.campaign_id "
            "WHERE c.channel_id = '{}' AND d.date BETWEEN ? AND ? GROUP BY 1".format(column, channel))


def _leads(extra=""):
    return ("SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM leads WHERE substr(created_at, 1, 10) BETWEEN ? AND ? "
            + extra + " GROUP BY 1")


def _in(ids):
    return "AND channel_id IN ({})".format(",".join("'{}'".format(i) for i in ids))


# What Meridian can count by itself: key -> (name, unit, where it comes from, SQL giving one row per day)
METRICS = {
    "heyreach_sent": ("LinkedIn requests sent", "requests", "HeyReach", _outbound("heyreach", "sent")),
    "heyreach_accepted": ("LinkedIn requests accepted", "accepted", "HeyReach", _outbound("heyreach", "opened")),
    "heyreach_replied": ("LinkedIn replies", "replies", "HeyReach", _outbound("heyreach", "replied")),
    "apollo_sent": ("Emails sent", "emails", "Apollo", _outbound("apollo", "sent")),
    "apollo_replied": ("Email replies", "replies", "Apollo", _outbound("apollo", "replied")),
    "leads": ("New leads, all channels", "leads", "Zoho", _leads()),
    "leads_outreach": ("Leads from outreach", "leads", "Zoho", _leads(_in(OUTREACH_LEADS))),
    "leads_website": ("Leads from the website", "leads", "Zoho", _leads(_in(WEB_LEADS))),
    "qualified": ("Qualified leads", "leads", "Zoho", None),  # needs the threshold, built in series()
    "visits": ("Website visits", "visits", "Google Analytics",
               "SELECT date AS day, SUM(sessions) AS n FROM traffic_daily WHERE date BETWEEN ? AND ? GROUP BY 1"),
    "google_clicks": ("Clicks from Google", "clicks", "Search Console",
                      "SELECT date AS day, SUM(clicks) AS n FROM channel_daily WHERE channel_id = 'search' AND date BETWEEN ? AND ? GROUP BY 1"),
    "blog_views": ("Blog views", "views", "Google Analytics",
                   "SELECT date AS day, SUM(views) AS n FROM page_daily WHERE date BETWEEN ? AND ? AND path LIKE '%/blog/%' GROUP BY 1"),
    "deals": ("Deals opened", "deals", "Zoho",
              "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM deals WHERE substr(created_at, 1, 10) BETWEEN ? AND ? GROUP BY 1"),
}


DEMO_FLAG = "team_demo"  # set while the targets hold made-up example data


class TeamError(Exception):
    """Something the person filling in the form can put right."""


def span(today, period):
    """First and last day of the week or month that today falls in."""
    if period == "month":
        first = today.replace(day=1)
        nxt = (first + timedelta(days=32)).replace(day=1)
        return first, nxt - timedelta(days=1)
    first = today - timedelta(days=today.weekday())
    return first, first + timedelta(days=6)


def working(first, last):
    return [first + timedelta(days=i) for i in range((last - first).days + 1) if (first + timedelta(days=i)).weekday() in WORKING_DAYS]


def series(conn, goal, first, last):
    """What was done for a target on each day of a span: {date: amount}."""
    a, b = first.isoformat(), last.isoformat()
    if goal["metric"] == "manual":
        return {r["day"]: r["n"] for r in conn.execute(
            "SELECT day, SUM(amount) AS n FROM goal_log WHERE goal_id = ? AND day BETWEEN ? AND ? GROUP BY day", (goal["id"], a, b))}
    if goal["metric"] == "qualified":
        return {r["day"]: r["n"] for r in conn.execute(
            _leads("AND score >= {}".format(int(scoring.threshold(conn)))), (a, b))}
    sql = METRICS.get(goal["metric"], (None, None, None, None))[3]
    return {r["day"]: r["n"] or 0 for r in conn.execute(sql, (a, b))} if sql else {}


def progress(conn, goal, today):
    """Where a target stands: done so far, what the pace says it should be, and what today asks for."""
    first, last = span(today, goal["period"])
    days = working(first, last) or [first]
    by_day = series(conn, goal, first, last)
    done = sum(by_day.values())
    past = [d for d in days if d <= today]
    left = [d for d in days if d >= today] or [today]
    before_today = sum(v for k, v in by_day.items() if k < today.isoformat())
    today_done = by_day.get(today.isoformat(), 0)
    # today's share: what is still open, spread evenly over the working days that remain (today included)
    share = max(math.ceil((goal["target"] - before_today) / len(left)), 0) if today.weekday() in WORKING_DAYS else 0
    expected = goal["target"] * len(past) / len(days)
    pct = done / goal["target"] * 100 if goal["target"] else 0
    if done >= goal["target"]:
        status = "done"
    elif done >= expected * 0.9:
        status = "on_track"
    elif done >= expected * 0.6:
        status = "behind"
    else:
        status = "far_behind"
    return dict(done=done, pct=pct, expected=expected, pace_pct=len(past) / len(days) * 100, status=status,
                today_done=today_done, today_share=share, today_met=share == 0 or today_done >= share,
                first=first.isoformat(), last=last.isoformat(),
                days=[dict(day=d.isoformat(), label=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday()], n=by_day.get(d.isoformat(), 0),
                           future=d > today) for d in (days if goal["period"] == "week" else [])])


def view(conn, now):
    """Everything the Targets screen shows."""
    today = now.date()
    members = [dict(r) for r in conn.execute("SELECT * FROM team_members WHERE active = 1 ORDER BY sort, id")]
    goals = [dict(r) for r in conn.execute("SELECT * FROM goals WHERE active = 1 ORDER BY period DESC, sort, id")]
    tasks = [dict(r) for r in conn.execute("SELECT * FROM team_tasks WHERE day = ? ORDER BY id", (today.isoformat(),))]
    notes = {r["member_id"]: r["note"] for r in conn.execute("SELECT member_id, note FROM team_notes WHERE day = ?", (today.isoformat(),))}
    blockers = [dict(r) for r in conn.execute("SELECT * FROM blockers ORDER BY resolved_at IS NOT NULL, created_at DESC LIMIT 60")]
    for b in blockers:
        b["age_days"] = (today - date.fromisoformat(b["created_at"][:10])).days
    said = {r["goal_id"]: r["note"] for r in conn.execute("SELECT goal_id, note FROM goal_notes WHERE day = ?", (today.isoformat(),))}
    for g in goals:
        name, unit, source, _ = METRICS.get(g["metric"], (None, g["unit"] or "", "Logged by hand", None))
        g.update(progress(conn, g, today), auto=g["metric"] != "manual", source=source, unit=g["unit"] or unit, today_note=said.get(g["id"], ""))
    # the last five working days, for each person: how many of their daily shares were met
    recent = []
    day = today
    while len(recent) < 5:
        if day.weekday() in WORKING_DAYS:
            recent.append(day)
        day -= timedelta(days=1)
    recent.reverse()
    history = {}
    for m in members:
        mine = [g for g in goals if g["member_id"] == m["id"]]
        rows = []
        for d in recent:
            met = total = 0
            for g in mine:
                if g["created_at"][:10] > d.isoformat():  # the target did not exist yet on that day
                    continue
                p = progress(conn, g, d)
                if p["today_share"]:
                    total += 1
                    met += p["today_done"] >= p["today_share"]
            done_tasks = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(done), 0) AS d FROM team_tasks WHERE member_id = ? AND day = ?",
                                      (m["id"], d.isoformat())).fetchone()
            rows.append(dict(day=d.isoformat(), label="{} {}".format(d.day, MONTHS[d.month - 1]), met=met + done_tasks["d"], total=total + done_tasks["n"]))
        history[m["id"]] = rows
    week = span(today, "week")
    month = span(today, "month")
    return dict(today=today.isoformat(), working_day=today.weekday() in WORKING_DAYS, demo=get_setting(conn, DEMO_FLAG) == "1",
                week_label="{} {} to {} {}".format(week[0].day, MONTHS[week[0].month - 1], week[1].day, MONTHS[week[1].month - 1]),
                month_label="{} {}".format(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                                            "November", "December"][today.month - 1], today.year),
                members=members, goals=goals, tasks=tasks, notes=notes, blockers=blockers, history=history,
                metrics=[dict(key=k, name=v[0], unit=v[1], source=v[2]) for k, v in METRICS.items()])


def report(conn, now, back=0):
    """One week, day by day: what each person did on each target, what they wrote, their one-off tasks and their blockers.

    back counts weeks before the current one (0 is this week, 1 is last week).
    """
    today = now.date()
    first = today - timedelta(days=today.weekday()) - timedelta(weeks=max(int(back), 0))
    last = first + timedelta(days=6)
    days = working(first, last)
    a, b = first.isoformat(), last.isoformat()
    people = []
    for m in conn.execute("SELECT * FROM team_members WHERE active = 1 ORDER BY sort, id"):
        goals = []
        for g in conn.execute("SELECT * FROM goals WHERE member_id = ? AND active = 1 AND substr(created_at, 1, 10) <= ? ORDER BY period DESC, sort, id", (m["id"], b)):
            g = dict(g)
            unit = g["unit"] or METRICS.get(g["metric"], (None, ""))[1]
            by_day = series(conn, g, first, last)
            notes = {r["day"]: r["note"] for r in conn.execute("SELECT day, note FROM goal_notes WHERE goal_id = ? AND day BETWEEN ? AND ? AND note <> ''", (g["id"], a, b))}
            total = sum(by_day.values())
            # a monthly target is judged over its whole month; the week only shows what was added to it
            if g["period"] == "month":
                mfirst, mlast = span(min(last, today) if first <= today else first, "month")
                so_far = sum(series(conn, g, mfirst, min(mlast, last)).values())
            else:
                so_far = total
            goals.append(dict(id=g["id"], title=g["title"], period=g["period"], target=g["target"], unit=unit, auto=g["metric"] != "manual",
                              total=total, so_far=so_far, pct=so_far / g["target"] * 100 if g["target"] else 0,
                              days=[dict(day=d.isoformat(), n=by_day.get(d.isoformat(), 0), note=notes.get(d.isoformat(), ""), future=d > today) for d in days]))
        notes = {r["day"]: r["note"] for r in conn.execute("SELECT day, note FROM team_notes WHERE member_id = ? AND day BETWEEN ? AND ? AND note <> ''", (m["id"], a, b))}
        tasks = {}
        for t in conn.execute("SELECT day, title, done FROM team_tasks WHERE member_id = ? AND day BETWEEN ? AND ? ORDER BY id", (m["id"], a, b)):
            tasks.setdefault(t["day"], []).append(dict(title=t["title"], done=bool(t["done"])))
        raised = [dict(text=r["text"], day=r["created_at"][:10], solved=bool(r["resolved_at"])) for r in conn.execute(
            "SELECT * FROM blockers WHERE member_id = ? AND substr(created_at, 1, 10) BETWEEN ? AND ? ORDER BY created_at", (m["id"], a, b))]
        people.append(dict(id=m["id"], name=m["name"], focus=m["focus"], goals=goals, notes=notes, tasks=tasks, blockers=raised))
    return dict(back=max(int(back), 0), first=a, last=b, current=first <= today <= last,
                label="{} {} to {} {} {}".format(first.day, MONTHS[first.month - 1], last.day, MONTHS[last.month - 1], last.year),
                days=[dict(day=d.isoformat(), label="{} {} {}".format(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday()], d.day, MONTHS[d.month - 1]),
                           future=d > today) for d in days], people=people)


# ------------------------------------------------------------------------------- changes

def clear_demo(conn):
    """Remove the made-up example targets and everything logged against them. The people stay."""
    if get_setting(conn, DEMO_FLAG) != "1":
        raise TeamError("There is no example data to remove.")
    for table in ("goal_log", "goal_notes", "goals", "team_tasks", "team_notes", "blockers"):
        conn.execute("DELETE FROM " + table)
    set_setting(conn, DEMO_FLAG, "0")


def need(text, what):
    text = (text or "").strip()
    if not text:
        raise TeamError("{} is needed.".format(what))
    return text


def save_member(conn, member_id, name, focus, email):
    values = (need(name, "A name"), (focus or "").strip() or None, (email or "").strip() or None)
    if member_id:
        conn.execute("UPDATE team_members SET name = ?, focus = ?, email = ? WHERE id = ?", values + (member_id,))
    else:
        conn.execute("INSERT INTO team_members (name, focus, email, sort) VALUES (?,?,?, (SELECT COALESCE(MAX(sort), 0) + 1 FROM team_members))", values)


def remove_member(conn, member_id):
    conn.execute("UPDATE team_members SET active = 0 WHERE id = ?", (member_id,))
    conn.execute("UPDATE goals SET active = 0 WHERE member_id = ?", (member_id,))


def save_goal(conn, now, goal_id, member_id, title, metric, period, target, unit):
    if metric != "manual" and metric not in METRICS:
        raise TeamError("That is not something Meridian can count.")
    if period not in ("week", "month"):
        raise TeamError("A target is for a week or a month.")
    try:
        target = float(target)
    except (TypeError, ValueError):
        raise TeamError("The target must be a number.")
    if target <= 0:
        raise TeamError("The target must be more than zero.")
    if not conn.execute("SELECT 1 FROM team_members WHERE id = ? AND active = 1", (member_id,)).fetchone():
        raise TeamError("Choose who the target is for.")
    title = (title or "").strip() or (METRICS[metric][0] if metric in METRICS else "")
    values = (member_id, need(title, "A name for the target"), metric, period, target, (unit or "").strip() or None)
    if goal_id:
        conn.execute("UPDATE goals SET member_id = ?, title = ?, metric = ?, period = ?, target = ?, unit = ? WHERE id = ?", values + (goal_id,))
    else:
        conn.execute("INSERT INTO goals (member_id, title, metric, period, target, unit, created_at, sort) VALUES (?,?,?,?,?,?,?, "
                     "(SELECT COALESCE(MAX(sort), 0) + 1 FROM goals))", values + (iso(now),))


def remove_goal(conn, goal_id):
    conn.execute("UPDATE goals SET active = 0 WHERE id = ?", (goal_id,))


def log(conn, now, goal_id, amount):
    """Add to (or take from) what was done today on a hand-counted target. The day's total never goes below zero."""
    goal = conn.execute("SELECT * FROM goals WHERE id = ? AND active = 1", (goal_id,)).fetchone()
    if not goal or goal["metric"] != "manual":
        raise TeamError("Only hand-counted targets are logged here; the others are counted from connected data.")
    day = now.date().isoformat()
    have = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM goal_log WHERE goal_id = ? AND day = ?", (goal_id, day)).fetchone()[0]
    amount = max(float(amount), -have)
    if amount:
        conn.execute("INSERT INTO goal_log (goal_id, day, amount, created_at) VALUES (?,?,?,?)", (goal_id, day, amount, iso(now)))


def save_goal_note(conn, now, goal_id, note):
    """What the person wrote about a target today: how they did it, or why not."""
    conn.execute("INSERT INTO goal_notes (goal_id, day, note, updated_at) VALUES (?,?,?,?) "
                 "ON CONFLICT (goal_id, day) DO UPDATE SET note = excluded.note, updated_at = excluded.updated_at",
                 (goal_id, now.date().isoformat(), (note or "").strip(), iso(now)))


def add_task(conn, now, member_id, title):
    conn.execute("INSERT INTO team_tasks (member_id, day, title, created_at) VALUES (?,?,?,?)",
                 (member_id, now.date().isoformat(), need(title, "What the task is"), iso(now)))


def toggle_task(conn, task_id):
    conn.execute("UPDATE team_tasks SET done = 1 - done WHERE id = ?", (task_id,))


def remove_task(conn, task_id):
    conn.execute("DELETE FROM team_tasks WHERE id = ?", (task_id,))


def save_note(conn, now, member_id, note):
    conn.execute("INSERT INTO team_notes (member_id, day, note, updated_at) VALUES (?,?,?,?) "
                 "ON CONFLICT (member_id, day) DO UPDATE SET note = excluded.note, updated_at = excluded.updated_at",
                 (member_id, now.date().isoformat(), (note or "").strip(), iso(now)))


def add_blocker(conn, now, member_id, text):
    conn.execute("INSERT INTO blockers (member_id, text, created_at) VALUES (?,?,?)", (member_id, need(text, "What is in the way"), iso(now)))


def resolve_blocker(conn, now, blocker_id, solved=True):
    conn.execute("UPDATE blockers SET resolved_at = ? WHERE id = ?", (iso(now) if solved else None, blocker_id))

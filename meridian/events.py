"""Events: each event the team goes to, from the first decision to what it brought in.

An event gets a copy of the standard plan (the playbook) when it is made, with due dates counted from its first
day. It also holds its promotion plan, the posts that went live, and what it cost. What it brought in is counted
from Zoho leads and deals whose lead source is one of the event's sources. Only counts and money are shown, never
who came.
"""

import json
import re
import urllib.request
from datetime import date, timedelta
from html import unescape

from . import scoring
from .db import get_setting, set_setting
from .periods import iso

PHASES = [("plan", "Decide & plan"), ("promote", "Promote & invite"), ("live", "Event days"), ("follow", "Follow up & measure")]
STATUSES = ["Not started", "In progress", "Waiting on others", "Done"]
CHANNELS = ["LinkedIn post", "LinkedIn ads", "Meta ads", "Instagram post", "Email", "Personal invites", "Landing page", "WhatsApp", "PR", "Other"]
COST_KINDS = ["Space or sponsorship", "Booth build and graphics", "Screen, power and Wi-Fi", "Travel and stay", "Print and swag", "Ads", "Other"]
DECISIONS = ["Considering", "Go", "No-go"]


class EventError(ValueError):
    pass


# The standard plan, made general from the SFF 2026 tracker: (phase, workstream, step, days from the first day, done when)
PLAYBOOK = [
    ("plan", "Planning", "Write the event brief: goal, audience, targets and budget", -42, "Brief agreed by the leaders"),
    ("plan", "Planning", "Decide go or no-go with the leaders", -40, "Decision written down"),
    ("plan", "Booth & logistics", "Book the space, booth or sponsorship package and pay the invoice", -35, "Invoice paid; organiser confirms"),
    ("plan", "Message", "Agree the message and value proposition (joint with the partner, if any)", -30, "One page signed off"),
    ("plan", "Customer outreach", "Build the target-account list, with an owner for each account", -30, "List with an owner per row"),
    ("plan", "Booth & logistics", "Register passes and confirm the attendee process with the organiser", -21, "Passes issued"),
    ("promote", "Lead capture", "Build the lead form (QR) with consent wording", -21, "Form live and tested"),
    ("promote", "Lead capture", "Agree lead rules: hot, warm, cold, who follows up and how fast", -21, "Rules written down"),
    ("promote", "Landing page", "Launch the event landing page with a meeting-booking form", -21, "Page live and tracked"),
    ("promote", "Customer outreach", "Set up a meeting calendar so invitees can book a slot", -21, "Booking link on the page and invites"),
    ("promote", "Promotion", "Publish the content calendar and the teaser post", -21, "Calendar agreed; first post live"),
    ("promote", "Customer outreach", "Send personal invites to every target account (email and LinkedIn)", -18, "Every target account invited"),
    ("promote", "Promotion", "Start paid ads to the event audience", -18, "Campaign live"),
    ("promote", "Promotion", "Add event banners and email signatures for the team", -18, "Whole team updated"),
    ("promote", "Booth & logistics", "Order booth graphics and get the artwork accepted", -18, "Written confirmation from the printer"),
    ("promote", "Booth & logistics", "Book furniture, screen, power and Wi-Fi", -18, "Order confirmed"),
    ("promote", "Message", "Make the one-pager, booth videos and the demo script", -10, "Print files sent; demo rehearsed"),
    ("promote", "Promotion", "Submit a media or PR announcement, if the organiser offers it", -10, "Submitted before the deadline"),
    ("promote", "Booth & logistics", "Send the pass list and access names to the organiser", -7, "Access confirmed"),
    ("promote", "Customer outreach", "Send reminders and confirm booked meetings", -3, "Confirmed meeting list shared"),
    ("promote", "Booth team", "Brief the booth team: message, demo, lead form and rota", -3, "Rota and briefing note shared"),
    ("promote", "Booth & logistics", "Pack swag and printed material", -2, "Ready to bring"),
    ("live", "Booth & logistics", "Set up and check the booth: graphics, screen, power, Wi-Fi", -1, "Booth signed off the evening before"),
    ("live", "Booth team", "Run the booked meetings and live demos", 0, "Every booked meeting held"),
    ("live", "Lead capture", "Capture every visitor through the lead form, no paper", 0, "No untracked leads"),
    ("live", "Lead capture", "Sync leads each evening: tag hot leads and assign an owner", 0, "Lead list updated each evening"),
    ("live", "Promotion", "Post live updates, photos and short videos each day", 0, "At least one post a day"),
    ("live", "Booth team", "Hold a 15-minute team debrief at the end of each day", 0, "Actions written down daily"),
    ("follow", "Lead capture", "Clean the lead list and load it into Zoho", 1, "All leads in Zoho within 24 hours"),
    ("follow", "Follow-up", "Send thank-you and follow-up emails; personal follow-up for hot leads", 3, "Every lead contacted on time"),
    ("follow", "Promotion", "Publish the recap post", 4, "Recap live with photos"),
    ("follow", "Promotion", "Run retargeting ads to visitors", 5, "Campaign live"),
    ("follow", "Results", "Review results against targets and share them", 7, "Results shared"),
    ("follow", "Results", "Review pipeline: which deals moved", 28, "Pipeline value agreed"),
]

EVENT_FIELDS = ("name", "starts", "ends", "city", "venue", "partner", "booth", "goal", "budget", "decision", "lessons",
                "target_leads", "target_meetings", "target_qualified", "target_pipeline", "visitors", "meetings_held")
NUMBERS = ("budget", "target_leads", "target_meetings", "target_qualified", "target_pipeline", "visitors", "meetings_held")


def seed_playbook(conn):
    """The standard plan goes in once; after that it is the team's to change."""
    if get_setting(conn, "playbook_seeded"):
        return
    conn.executemany("INSERT INTO playbook_steps (phase, workstream, title, offset_days, done_when, sort) VALUES (?,?,?,?,?,?)",
                     [(p, w, t, o, d, i) for i, (p, w, t, o, d) in enumerate(PLAYBOOK)])
    set_setting(conn, "playbook_seeded", "1")


def need(text, what):
    text = (text or "").strip()
    if not text:
        raise EventError("{} is needed.".format(what))
    return text


def day_of(text, what):
    try:
        return date.fromisoformat((text or "").strip()).isoformat()
    except ValueError:
        raise EventError("{} needs a date.".format(what))


def number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise EventError("A number is needed.")


# ------------------------------------------------------------------------------- results

def results(conn, ev, threshold):
    """What the event brought in, per lead source and in total: leads, qualified, deals started, their value, deals won."""
    sources = json.loads(ev["lead_sources"] or "[]")  # the source names the event, so every lead and deal with it counts
    rows = {s: dict(source=s, leads=0, qualified=0, deals=0, pipeline=0, won=0, won_value=0) for s in sources}
    if sources:
        marks = ",".join("?" for _ in sources)
        for r in conn.execute("SELECT TRIM(lead_source) AS s, COUNT(*) AS n, SUM({}) AS q FROM leads WHERE TRIM(lead_source) IN ({}) "
                              "GROUP BY 1".format(scoring.qualified_sql(), marks), [threshold] + sources):
            rows[r["s"]].update(leads=r["n"], qualified=r["q"] or 0)
        for r in conn.execute("SELECT TRIM(lead_source) AS s, COUNT(*) AS n, SUM(amount) AS amt, SUM(stage = 'won') AS w, "
                              "SUM(CASE WHEN stage = 'won' THEN amount ELSE 0 END) AS wv FROM deals "
                              "WHERE TRIM(lead_source) IN ({}) GROUP BY 1".format(marks), sources):
            rows[r["s"]].update(deals=r["n"], pipeline=r["amt"] or 0, won=r["w"] or 0, won_value=r["wv"] or 0)
        # which channel group the source's leads sit in, so the page can say when Overview's Events row will not count them
        for r in conn.execute("SELECT TRIM(l.lead_source) AS s, c.grp FROM leads l LEFT JOIN channels c ON c.id = l.channel_id "
                              "WHERE TRIM(l.lead_source) IN ({}) GROUP BY 1".format(marks), sources):
            rows[r["s"]]["group"] = r["grp"]
    total = {k: sum(r[k] for r in rows.values()) for k in ("leads", "qualified", "deals", "pipeline", "won", "won_value")}
    return dict(sources=list(rows.values()), total=total)


def money_back(total, cost):
    """Cost per lead, per qualified lead, and what came back for each rupee spent. None where it cannot be worked out."""
    per = lambda n: cost / n if cost and n else None
    times = lambda v: v / cost if cost else None
    return dict(per_lead=per(total["leads"]), per_qualified=per(total["qualified"]),
                pipeline_x=times(total["pipeline"]), won_x=times(total["won_value"]))


def phase_now(ev, today):
    starts, ends = date.fromisoformat(ev["starts"]), date.fromisoformat(ev["ends"] or ev["starts"])
    if today < starts - timedelta(days=28):
        return "Planning"
    if today < starts:
        return "Promoting"
    if today <= ends:
        return "Live"
    if today <= ends + timedelta(days=30):
        return "Follow-up"
    return "Done"


def progress(steps, today):
    done = sum(s["status"] == "Done" for s in steps)
    late = sum(s["status"] != "Done" and s["due"] and s["due"] < today.isoformat() for s in steps)
    return dict(done=done, total=len(steps), overdue=late)


# ------------------------------------------------------------------------------- views

def listing(conn, now, threshold):
    seed_playbook(conn)
    today = now.date()
    out = []
    for ev in conn.execute("SELECT * FROM events ORDER BY starts"):
        steps = [dict(r) for r in conn.execute("SELECT status, due FROM event_steps WHERE event_id = ?", (ev["id"],))]
        cost = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM event_costs WHERE event_id = ?", (ev["id"],)).fetchone()[0]
        res = results(conn, ev, threshold)
        out.append(dict(id=ev["id"], name=ev["name"], starts=ev["starts"], ends=ev["ends"], city=ev["city"], partner=ev["partner"],
                        phase=phase_now(ev, today), days_to_go=(date.fromisoformat(ev["starts"]) - today).days,
                        progress=progress(steps, today), cost=cost, budget=ev["budget"], total=res["total"],
                        money=money_back(res["total"], cost), has_sources=bool(json.loads(ev["lead_sources"] or "[]"))))
    # upcoming and live first (soonest first), then the finished ones (latest first)
    out.sort(key=lambda e: (e["phase"] == "Done", e["days_to_go"] if e["phase"] != "Done" else -e["days_to_go"]))
    playbook = [dict(r) for r in conn.execute("SELECT * FROM playbook_steps ORDER BY sort, id")]
    return dict(events=out, playbook=playbook, phases=PHASES, today=today.isoformat())


def source_options(conn):
    """Lead sources Zoho already has, most used first, so an event's sources are picked rather than typed."""
    rows = conn.execute("SELECT TRIM(lead_source) AS s, COUNT(*) AS n FROM leads WHERE TRIM(COALESCE(lead_source, '')) <> '' "
                        "GROUP BY 1 ORDER BY n DESC LIMIT 400").fetchall()
    return [dict(source=r["s"], leads=r["n"]) for r in rows]


def detail(conn, now, event_id, threshold):
    seed_playbook(conn)
    ev = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not ev:
        raise EventError("That event is not there any more.")
    today = now.date()
    steps = [dict(r) for r in conn.execute("SELECT * FROM event_steps WHERE event_id = ? ORDER BY sort, due, id", (event_id,))]
    costs = [dict(r) for r in conn.execute("SELECT * FROM event_costs WHERE event_id = ? ORDER BY id", (event_id,))]
    cost = sum(c["amount"] or 0 for c in costs)
    res = results(conn, ev, threshold)
    sources = json.loads(ev["lead_sources"] or "[]")
    taken = {s: o["name"] for o in conn.execute("SELECT name, lead_sources FROM events WHERE id <> ?", (event_id,))
             for s in json.loads(o["lead_sources"] or "[]")}
    return dict(
        event=dict(ev, lead_sources=sources), phase=phase_now(ev, today), today=today.isoformat(),
        days_to_go=(date.fromisoformat(ev["starts"]) - today).days,
        steps=steps, progress=progress(steps, today),
        by_phase=[dict(key=k, label=l, **progress([s for s in steps if s["phase"] == k], today)) for k, l in PHASES],
        promos=[dict(r) for r in conn.execute("SELECT * FROM event_promos WHERE event_id = ? ORDER BY day, id", (event_id,))],
        creatives=[dict(r) for r in conn.execute("SELECT * FROM event_creatives WHERE event_id = ? ORDER BY COALESCE(posted_on, '') DESC, id DESC", (event_id,))],
        costs=costs, cost=cost, results=res, money=money_back(res["total"], cost), taken=taken, decisions=DECISIONS,
        team=[r["name"] for r in conn.execute("SELECT name FROM team_members WHERE active = 1 ORDER BY sort, name")],
        phases=PHASES, statuses=STATUSES, channels=CHANNELS, cost_kinds=COST_KINDS, source_options=source_options(conn),
    )


# ------------------------------------------------------------------------------- changes

def save_event(conn, now, event_id, d):
    values = {k: d.get(k) for k in EVENT_FIELDS}
    values["name"] = need(values["name"], "A name for the event")
    values["starts"] = day_of(values["starts"], "The first day")
    values["ends"] = day_of(values["ends"], "The last day") if values.get("ends") else values["starts"]
    if values["ends"] < values["starts"]:
        raise EventError("The last day is before the first day.")
    for k in NUMBERS:
        values[k] = number(values[k])
    for k in ("city", "venue", "partner", "booth", "goal", "lessons"):
        values[k] = (values[k] or "").strip() or None
    values["decision"] = values["decision"] if values.get("decision") in DECISIONS else "Considering"
    if event_id:
        old = conn.execute("SELECT starts FROM events WHERE id = ?", (event_id,)).fetchone()
        conn.execute("UPDATE events SET {} WHERE id = ?".format(", ".join(k + " = ?" for k in EVENT_FIELDS)),
                     [values[k] for k in EVENT_FIELDS] + [event_id])
        # a moved event moves the due dates of the steps that came from the playbook and are not done yet
        shift = (date.fromisoformat(values["starts"]) - date.fromisoformat(old["starts"])).days if old else 0
        if shift:
            for s in conn.execute("SELECT id, due FROM event_steps WHERE event_id = ? AND status <> 'Done' AND due IS NOT NULL", (event_id,)).fetchall():
                conn.execute("UPDATE event_steps SET due = ? WHERE id = ?", ((date.fromisoformat(s["due"]) + timedelta(days=shift)).isoformat(), s["id"]))
        return event_id
    cur = conn.execute("INSERT INTO events ({}, lead_sources, created_at) VALUES ({})".format(", ".join(EVENT_FIELDS), ",".join("?" for _ in range(len(EVENT_FIELDS) + 2))),
                       [values[k] for k in EVENT_FIELDS] + ["[]", iso(now)])
    new_id = cur.lastrowid
    if d.get("from_playbook", True):
        seed_playbook(conn)
        first = date.fromisoformat(values["starts"])
        conn.executemany("INSERT INTO event_steps (event_id, phase, workstream, title, owner, due, status, done_when, sort) VALUES (?,?,?,?,?,?,?,?,?)",
                         [(new_id, r["phase"], r["workstream"], r["title"], r["owner"], (first + timedelta(days=r["offset_days"])).isoformat(),
                           "Not started", r["done_when"], i) for i, r in enumerate(conn.execute("SELECT * FROM playbook_steps ORDER BY sort, id"))])
    return new_id


def remove_event(conn, event_id):
    for table in ("event_steps", "event_promos", "event_creatives", "event_costs"):
        conn.execute("DELETE FROM {} WHERE event_id = ?".format(table), (event_id,))
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))


def save_sources(conn, event_id, sources):
    """An event's lead sources. A source belongs to one event only, or its leads would be counted twice."""
    clean = sorted({(s or "").strip() for s in sources or [] if (s or "").strip()})
    for o in conn.execute("SELECT name, lead_sources FROM events WHERE id <> ?", (event_id,)):
        both = set(clean) & set(json.loads(o["lead_sources"] or "[]"))
        if both:
            raise EventError("{} already belongs to {}. A lead source can belong to one event only.".format(", ".join(sorted(both)), o["name"]))
    conn.execute("UPDATE events SET lead_sources = ? WHERE id = ?", (json.dumps(clean), event_id))


def save_step(conn, step_id, event_id, d):
    phase = d.get("phase") if d.get("phase") in dict(PHASES) else "plan"
    status = d.get("status") if d.get("status") in STATUSES else "Not started"
    values = (phase, (d.get("workstream") or "").strip() or None, need(d.get("title"), "What the step is"), (d.get("owner") or "").strip() or None,
              day_of(d["due"], "The due date") if d.get("due") else None, status, (d.get("done_when") or "").strip() or None, (d.get("note") or "").strip() or None)
    if step_id:
        conn.execute("UPDATE event_steps SET phase = ?, workstream = ?, title = ?, owner = ?, due = ?, status = ?, done_when = ?, note = ? WHERE id = ?", values + (step_id,))
    else:
        conn.execute("INSERT INTO event_steps (phase, workstream, title, owner, due, status, done_when, note, event_id, sort) "
                     "VALUES (?,?,?,?,?,?,?,?,?, (SELECT COALESCE(MAX(sort), 0) + 1 FROM event_steps WHERE event_id = ?))", values + (event_id, event_id))


def set_status(conn, step_id, status):
    if status not in STATUSES:
        raise EventError("Unknown status.")
    conn.execute("UPDATE event_steps SET status = ? WHERE id = ?", (status, step_id))


def save_playbook_step(conn, step_id, d):
    phase = d.get("phase") if d.get("phase") in dict(PHASES) else "plan"
    try:
        offset = int(d.get("offset_days") or 0)
    except (TypeError, ValueError):
        raise EventError("Days from the event need a whole number, for example -21 or 3.")
    values = (phase, (d.get("workstream") or "").strip() or None, need(d.get("title"), "What the step is"), offset,
              (d.get("done_when") or "").strip() or None, (d.get("owner") or "").strip() or None)
    if step_id:
        conn.execute("UPDATE playbook_steps SET phase = ?, workstream = ?, title = ?, offset_days = ?, done_when = ?, owner = ? WHERE id = ?", values + (step_id,))
    else:
        conn.execute("INSERT INTO playbook_steps (phase, workstream, title, offset_days, done_when, owner, sort) "
                     "VALUES (?,?,?,?,?,?, (SELECT COALESCE(MAX(sort), 0) + 1 FROM playbook_steps))", values)


def save_promo(conn, promo_id, event_id, d):
    channel = d.get("channel") if d.get("channel") in CHANNELS else "Other"
    status = d.get("status") if d.get("status") in STATUSES else "Not started"
    values = (channel, need(d.get("what"), "What goes out"), day_of(d["day"], "The date") if d.get("day") else None, (d.get("owner") or "").strip() or None, status)
    if promo_id:
        conn.execute("UPDATE event_promos SET channel = ?, what = ?, day = ?, owner = ?, status = ? WHERE id = ?", values + (promo_id,))
    else:
        conn.execute("INSERT INTO event_promos (channel, what, day, owner, status, event_id) VALUES (?,?,?,?,?,?)", values + (event_id,))


def save_cost(conn, cost_id, event_id, d):
    kind = d.get("category") if d.get("category") in COST_KINDS else "Other"
    amount = number(d.get("amount"))
    if amount is None:
        raise EventError("An amount is needed.")
    values = (kind, need(d.get("item"), "What the cost is for"), amount, 1 if d.get("paid") else 0)
    if cost_id:
        conn.execute("UPDATE event_costs SET category = ?, item = ?, amount = ?, paid = ? WHERE id = ?", values + (cost_id,))
    else:
        conn.execute("INSERT INTO event_costs (category, item, amount, paid, event_id) VALUES (?,?,?,?,?)", values + (event_id,))


# ------------------------------------------------------------------------------- creatives

PLATFORMS = [("instagram.com", "Instagram"), ("linkedin.com", "LinkedIn"), ("facebook.com", "Facebook"), ("fb.watch", "Facebook"),
             ("x.com", "X"), ("twitter.com", "X"), ("youtube.com", "YouTube"), ("youtu.be", "YouTube")]


def platform_of(url):
    host = re.sub(r"^https?://(www\.)?", "", url.lower()).split("/")[0]
    return next((name for key, name in PLATFORMS if host.endswith(key)), "Web")


def preview(url):
    """The page's own preview picture and title (Open Graph), where the site lets us read it. Many social sites do not."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; MeridianPreview/1.0)", "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=8) as res:
            page = res.read(400000).decode("utf-8", "ignore")
    except Exception:
        return None, None

    def meta(name):
        m = re.search(r'<meta[^>]+(?:property|name)=["\']{}["\'][^>]*content=["\']([^"\']+)'.format(re.escape(name)), page, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{}["\']'.format(re.escape(name)), page, re.I)
        return unescape(m.group(1)).strip() if m else None

    return meta("og:image") or meta("twitter:image"), meta("og:title") or meta("twitter:title")


def save_creative(conn, creative_id, event_id, d):
    url = need(d.get("url"), "The link to the post")
    if not re.match(r"^https?://", url):
        url = "https://" + url
    image, title = (d.get("image") or "").strip() or None, (d.get("title") or "").strip() or None
    if not creative_id and not (image and title):
        found_image, found_title = preview(url)
        image, title = image or found_image, title or found_title
    values = (url, platform_of(url), title, image, day_of(d["posted_on"], "The date") if d.get("posted_on") else None, (d.get("caption") or "").strip() or None)
    if creative_id:
        conn.execute("UPDATE event_creatives SET url = ?, platform = ?, title = ?, image = ?, posted_on = ?, caption = ? WHERE id = ?", values + (creative_id,))
    else:
        conn.execute("INSERT INTO event_creatives (url, platform, title, image, posted_on, caption, event_id) VALUES (?,?,?,?,?,?,?)", values + (event_id,))


REMOVE = {"remove_step": "event_steps", "remove_promo": "event_promos", "remove_creative": "event_creatives", "remove_cost": "event_costs",
          "remove_playbook_step": "playbook_steps"}


def change(conn, now, what, item_id, event_id, d):
    """One change from the Events screens. Returns the event id it touched (a new event's id when one is made)."""
    if what == "event":
        return save_event(conn, now, item_id, d)
    if what == "remove_event":
        remove_event(conn, item_id)
    elif what == "sources":
        save_sources(conn, event_id, d.get("sources"))
    elif what == "step":
        save_step(conn, item_id, event_id, d)
    elif what == "status":
        set_status(conn, item_id, d.get("status"))
    elif what == "playbook_step":
        save_playbook_step(conn, item_id, d)
    elif what == "promo":
        save_promo(conn, item_id, event_id, d)
    elif what == "cost":
        save_cost(conn, item_id, event_id, d)
    elif what == "creative":
        save_creative(conn, item_id, event_id, d)
    elif what in REMOVE:
        conn.execute("DELETE FROM {} WHERE id = ?".format(REMOVE[what]), (item_id,))
    else:
        raise EventError("Unknown change.")
    return event_id

"""Events: each event the team goes to, from the first decision to what it brought in.

An event gets a copy of the standard plan (the playbook) when it is made, with due dates counted from its first
day. It also holds its promotion plan, the posts that went live, and what it cost. What it brought in is counted
from Zoho leads and deals whose lead source is one of the event's sources. Only counts and money are shown, never
who came.
"""

import json
import re
import urllib.request
from datetime import date, datetime, timedelta
from html import unescape

from . import scoring
from .db import get_setting, set_setting
from .periods import iso

PHASES = [("plan", "Decide & plan"), ("promote", "Promote & invite"), ("live", "Event days"), ("follow", "Follow up & measure")]
STATUSES = ["Not started", "In progress", "Waiting on others", "Done"]
CHANNELS = ["LinkedIn post", "LinkedIn ads", "Meta ads", "Instagram post", "Email", "Personal invites", "Landing page", "WhatsApp", "PR", "Other"]
COST_KINDS = ["Space or sponsorship", "Booth build and graphics", "Screen, power and Wi-Fi", "Travel and stay", "Print and swag", "Ads", "Other"]
DECISIONS = ["Considering", "Go", "No-go"]
KINDS = [("booth", "Booth / exhibition"), ("sponsor", "Sponsorship + speaking slot"), ("partner", "Partner co-hosted event"),
         ("roundtable", "Roundtable / dinner"), ("webinar", "Webinar")]
IN_PERSON = "booth,sponsor,partner,roundtable"
BOOTH = "booth,sponsor,partner"
RESULT_DAYS = 90      # an event is compared with others only once its deals have had this long to move
RISK_DAYS = 7        # a critical task due within this many days and not done is at risk
OWNER_LOAD = 6       # more open tasks than this due in the next two weeks means an owner is overloaded


class EventError(ValueError):
    pass


# The standard plan, made general from the SFF 2026 tracker: (phase, workstream, step, days from the first day, done when)
# The standard plan, generalised from the SFF 2026 tracker:
# (phase, workstream, task, days from the first day (follow-up: from the last day), done when, event kinds ("" = all), critical)
PLAYBOOK = [
    ("plan", "Planning", "Event brief: objective, audience, KPIs and budget", -42, "Brief approved", "", 1),
    ("plan", "Planning", "Go / no-go decision", -40, "Decision recorded", "", 1),
    ("plan", "Booth & logistics", "Book space or sponsorship package; pay the invoice", -35, "Invoice paid, organiser confirms", BOOTH, 1),
    ("plan", "Planning", "Book the venue and agree the menu", -35, "Venue confirmed", "roundtable", 1),
    ("plan", "Planning", "Set up the webinar platform and registration page", -30, "Registration page live", "webinar", 1),
    ("plan", "Messaging", "Value proposition and key messages (joint with the partner, if any)", -30, "One-pager signed off", "", 0),
    ("plan", "Speaking", "Submit the talk abstract and speaker bio", -30, "Accepted by the organiser", "sponsor", 1),
    ("plan", "ABM", "Target account list with tiers and an account owner each", -30, "List complete", "", 1),
    ("plan", "Booth & logistics", "Register passes; confirm the attendee process", -21, "Passes issued", IN_PERSON, 0),
    ("promote", "Lead capture", "Lead capture form (QR) with consent wording", -21, "Form live and tested", IN_PERSON, 1),
    ("promote", "Lead capture", "Lead routing rules: hot / warm / cold, owner and follow-up SLA", -21, "Rules shared with sales", "", 1),
    ("promote", "Landing page", "Event landing page with meeting booking", -21, "Page live and tracked", "", 0),
    ("promote", "ABM", "Meeting booking calendar", -21, "Booking link live", IN_PERSON, 0),
    ("promote", "Promotion", "Content calendar and teaser post", -21, "First post live", "", 0),
    ("promote", "ABM", "Personal invites to every target account (email + LinkedIn)", -18, "100% of target accounts invited", "", 1),
    ("promote", "Promotion", "Paid campaign to the event audience", -18, "Campaign live", "", 0),
    ("promote", "Promotion", "Event banners and email signatures", -18, "Team updated", IN_PERSON, 0),
    ("promote", "Booth & logistics", "Booth graphics ordered; artwork approved", -18, "Printer confirms artwork", BOOTH, 1),
    ("promote", "Booth & logistics", "Furniture, screen, power and Wi-Fi ordered", -18, "Order confirmed", BOOTH, 0),
    ("promote", "Speaking", "Slides for the talk; rehearsal", -10, "Slides final, rehearsed", "sponsor,webinar", 1),
    ("promote", "Messaging", "Collateral: one-pager, booth video, demo script", -10, "Files final; demo rehearsed", BOOTH, 0),
    ("promote", "Promotion", "PR / media announcement (if offered)", -10, "Submitted", BOOTH, 0),
    ("promote", "Planning", "Guest list confirmed; RSVPs chased", -7, "Seats filled", "roundtable", 1),
    ("promote", "Booth & logistics", "Pass list and access names to the organiser", -7, "Access confirmed", IN_PERSON, 0),
    ("promote", "ABM", "Meeting reminders; confirm booked meetings", -3, "Meeting list confirmed", "", 1),
    ("promote", "Promotion", "Registration reminders", -2, "Reminders sent", "webinar", 0),
    ("promote", "Booth team", "Booth team briefing: messaging, demo, lead form, rota", -3, "Rota shared", IN_PERSON, 1),
    ("promote", "Booth & logistics", "Pack swag and print", -2, "Packed", BOOTH, 0),
    ("live", "Booth & logistics", "Booth build and check: graphics, screen, power, Wi-Fi", -1, "Booth signed off", BOOTH, 1),
    ("live", "ABM", "Booked meetings and live demos", 0, "Every booked meeting held", "", 1),
    ("live", "Lead capture", "Capture every visitor through the form", 0, "No paper or untracked leads", IN_PERSON, 1),
    ("live", "Lead capture", "Daily lead sync: tag hot leads, assign owners", 0, "Leads updated each evening", "", 1),
    ("live", "Promotion", "Live posts: photos and short video each day", 0, "One post per day", "", 0),
    ("live", "Booth team", "End-of-day debrief", 0, "Actions logged", IN_PERSON, 0),
    ("follow", "Lead capture", "Leads cleaned and loaded into Zoho", 1, "All leads in Zoho within 24 hours", "", 1),
    ("follow", "Follow-up", "Thank-you emails; personal follow-up on hot leads", 2, "Every lead contacted within SLA", "", 1),
    ("follow", "Promotion", "Recap post", 3, "Recap live", "", 0),
    ("follow", "Promotion", "Send the recording to registrants", 2, "Recording sent", "webinar", 0),
    ("follow", "Promotion", "Retargeting campaign", 5, "Campaign live", "", 0),
    ("follow", "Reporting", "Post-event report against KPIs", 7, "Report shared", "", 1),
    ("follow", "Reporting", "Pipeline review", 30, "Pipeline agreed with sales", "", 0),
]

EVENT_FIELDS = ("name", "kind", "starts", "ends", "city", "venue", "partner", "booth", "goal", "budget", "decision", "lessons",
                "target_leads", "target_meetings", "target_qualified", "target_pipeline", "visitors", "meetings_held")
NUMBERS = ("budget", "target_leads", "target_meetings", "target_qualified", "target_pipeline", "visitors", "meetings_held")


PLAYBOOK_VERSION = "2"


def seed_playbook(conn):
    """The standard plan goes in once; after that it is the team's to change."""
    if get_setting(conn, "playbook_seeded") == PLAYBOOK_VERSION:
        return
    conn.execute("DELETE FROM playbook_steps")  # version 1 was never used live
    conn.executemany("INSERT INTO playbook_steps (phase, workstream, title, offset_days, done_when, kinds, critical, sort) VALUES (?,?,?,?,?,?,?,?)",
                     [row + (i,) for i, row in enumerate(PLAYBOOK)])
    set_setting(conn, "playbook_seeded", PLAYBOOK_VERSION)


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
    by_day = []
    if sources:
        by_day = [dict(day=r["d"], leads=r["n"], qualified=r["q"] or 0) for r in conn.execute(
            "SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS n, SUM({}) AS q FROM leads WHERE TRIM(lead_source) IN ({}) GROUP BY 1 ORDER BY 1".format(
                scoring.qualified_sql(), ",".join("?" for _ in sources)), [threshold] + sources)]
    return dict(sources=list(rows.values()), total=total, by_day=by_day, speed=follow_up(conn, ev, sources))


def follow_up(conn, ev, sources):
    """How fast an owner first touched the event's leads, counted from the later of the lead's arrival and the event's last day.
    Only leads Meridian saw first touched (first_touch_at) can be timed; the rest are counted as not yet timed."""
    out = dict(leads=0, timed=0, h24=0, h72=0, d7=0, untouched=0)
    if not sources:
        return out
    ends = (ev["ends"] or ev["starts"]) + "T23:59:59"
    for r in conn.execute("SELECT created_at, first_touch_at FROM leads WHERE TRIM(lead_source) IN ({})".format(",".join("?" for _ in sources)), sources):
        out["leads"] += 1
        if not r["first_touch_at"]:
            out["untouched"] += 1
            continue
        start = datetime.fromisoformat(max(r["created_at"], ends)[:19])
        hours = (datetime.fromisoformat(r["first_touch_at"][:19]) - start).total_seconds() / 3600
        out["timed"] += 1
        out["h24"] += hours <= 24
        out["h72"] += hours <= 72
        out["d7"] += hours <= 168
    return out


def squash(name):
    words = re.sub(r"[^a-z0-9]+", " ", (name or "").lower().replace("&", " and ")).split()
    noise = {"ltd", "limited", "pvt", "private", "inc", "llc", "plc", "co", "corp", "corporation", "company", "group", "the", "bhd", "berhad", "pte", "sa", "ag"}
    return " ".join(w for w in words if w not in noise)


def accounts(conn, ev, threshold):
    """Target accounts by tier: engaged at this event (a lead with the event's source), already in Zoho, and with an open or won deal.
    Matched by company name with legal suffixes removed, or by email / website domain when the list gives one."""
    targets = [dict(r) for r in conn.execute("SELECT * FROM event_targets WHERE event_id = ? ORDER BY tier, company", (ev["id"],))]
    if not targets:
        return dict(targets=[], tiers=[], influenced=0, influenced_deals=0)
    sources = set(json.loads(ev["lead_sources"] or "[]"))
    starts, ends = ev["starts"], (ev["ends"] or ev["starts"]) + "T23:59:59"
    by_name, by_domain = {}, {}
    for t in targets:
        t.update(engaged=False, known=False, deal=None, pipeline=0)
        by_name.setdefault(squash(t["company"]), []).append(t)
        if t["domain"]:
            by_domain.setdefault(t["domain"].lower().lstrip("@").replace("www.", ""), []).append(t)
    lead_target = {}
    for l in conn.execute("SELECT id, company, email, website, lead_source FROM leads WHERE COALESCE(company, '') <> '' OR COALESCE(email, '') <> ''"):
        dom = (l["email"] or "").split("@")[-1].lower() if "@" in (l["email"] or "") else re.sub(r"^https?://(www\.)?", "", (l["website"] or "").lower()).split("/")[0]
        hits = by_name.get(squash(l["company"]), []) + by_domain.get(dom, [])
        for t in hits:
            t["known"] = True
            if (l["lead_source"] or "").strip() in sources:
                t["engaged"] = True
            lead_target[l["id"]] = t
    influenced, deals = 0, 0
    if lead_target:
        ids = list(lead_target)
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            for d in conn.execute("SELECT lead_id, amount, stage, created_at, closed_at FROM deals WHERE lead_id IN ({})".format(",".join("?" for _ in chunk)), chunk):
                t = lead_target[d["lead_id"]]
                t["deal"] = "won" if d["stage"] == "won" else t["deal"] or d["stage"]
                # influenced: the account's deal was open while the event ran
                if d["created_at"] <= ends and (d["closed_at"] is None or d["closed_at"] >= starts):
                    t["pipeline"] += d["amount"] or 0
                    influenced += d["amount"] or 0
                    deals += 1
    tiers = []
    for tier in sorted({t["tier"] for t in targets}):
        group = [t for t in targets if t["tier"] == tier]
        tiers.append(dict(tier=tier, total=len(group), engaged=sum(t["engaged"] for t in group), known=sum(t["known"] for t in group),
                          deals=sum(bool(t["deal"]) for t in group)))
    return dict(targets=targets, tiers=tiers, influenced=influenced, influenced_deals=deals)


def money_back(total, cost):
    """Cost per lead (CPL), cost per qualified lead, pipeline and revenue for each rupee spent (ROI). None where it cannot be worked out."""
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
    """Readiness is the share of tasks due by today that are done; overdue tasks and critical tasks at risk are counted apart."""
    t = today.isoformat()
    soon = (today + timedelta(days=RISK_DAYS)).isoformat()
    done = sum(s["status"] == "Done" for s in steps)
    due = [s for s in steps if s["due"] and s["due"] <= t]
    late = sum(s["status"] != "Done" for s in due)
    risk = [s for s in steps if s.get("critical") and s["status"] != "Done" and s["due"] and s["due"] <= soon]
    return dict(done=done, total=len(steps), overdue=late, due=len(due), due_done=len(due) - late,
                readiness=round((len(due) - late) / len(due) * 100) if due else (100 if not steps else round(done / len(steps) * 100)),
                at_risk=len(risk))


def owner_load(steps, today):
    """Open tasks per owner due in the next two weeks (overdue included), heaviest first."""
    until = (today + timedelta(days=14)).isoformat()
    load = {}
    for s in steps:
        if s["status"] != "Done" and s["due"] and s["due"] <= until:
            row = load.setdefault(s["owner"] or "Unassigned", dict(owner=s["owner"] or "Unassigned", open=0, overdue=0, critical=0))
            row["open"] += 1
            row["overdue"] += s["due"] < today.isoformat()
            row["critical"] += bool(s.get("critical"))
    return sorted(load.values(), key=lambda r: -r["open"])


EMBEDS = [
    (r"linkedin\.com/.*(?:activity|ugcPost|share)[-:](\d{15,})", lambda m, u: "https://www.linkedin.com/embed/feed/update/urn:li:{}:{}".format(
        "ugcPost" if "ugcPost" in u else "share" if "share" in u and "activity" not in u else "activity", m.group(1))),
    (r"instagram\.com/(?:[\w.]+/)?(p|reel|tv)/([\w-]+)", lambda m, u: "https://www.instagram.com/{}/{}/embed/captioned/".format(m.group(1), m.group(2))),
    (r"(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)([\w-]{6,})", lambda m, u: "https://www.youtube.com/embed/" + m.group(1)),
]


def embed_url(url):
    """The platform's own embed for a public post, shown in a locked-down frame. None when the platform needs a token or script."""
    for pattern, build in EMBEDS:
        m = re.search(pattern, url or "")
        if m:
            return build(m, url)
    return None


# ------------------------------------------------------------------------------- views

def listing(conn, now, threshold):
    seed_playbook(conn)
    today = now.date()
    out = []
    for ev in conn.execute("SELECT * FROM events ORDER BY starts"):
        steps = [dict(r) for r in conn.execute("SELECT status, due, critical, owner FROM event_steps WHERE event_id = ?", (ev["id"],))]
        cost = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM event_costs WHERE event_id = ?", (ev["id"],)).fetchone()[0]
        res = results(conn, ev, threshold)
        out.append(dict(id=ev["id"], name=ev["name"], starts=ev["starts"], ends=ev["ends"], city=ev["city"], partner=ev["partner"],
                        phase=phase_now(ev, today), days_to_go=(date.fromisoformat(ev["starts"]) - today).days,
                        kind=dict(KINDS).get(ev["kind"], "Booth / exhibition"), ends_on=ev["ends"] or ev["starts"],
                        result_age=(today - date.fromisoformat(ev["ends"] or ev["starts"])).days,
                        progress=progress(steps, today), cost=cost, budget=ev["budget"], total=res["total"],
                        money=money_back(res["total"], cost), has_sources=bool(json.loads(ev["lead_sources"] or "[]"))))
    # upcoming and live first (soonest first), then the finished ones (latest first)
    out.sort(key=lambda e: (e["phase"] == "Done", e["days_to_go"] if e["phase"] != "Done" else -e["days_to_go"]))
    playbook = [dict(r) for r in conn.execute("SELECT * FROM playbook_steps ORDER BY sort, id")]
    return dict(events=out, playbook=playbook, phases=PHASES, kinds=KINDS, today=today.isoformat(), result_days=RESULT_DAYS)


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
    steps = [dict(r) for r in conn.execute("SELECT * FROM event_steps WHERE event_id = ? ORDER BY due, sort, id", (event_id,))]
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
        creatives=[dict(r, embed=embed_url(r["url"])) for r in conn.execute("SELECT * FROM event_creatives WHERE event_id = ? ORDER BY COALESCE(posted_on, '') DESC, id DESC", (event_id,))],
        costs=costs, cost=cost, planned=sum(c["planned"] or 0 for c in costs) or ev["budget"], results=res, money=money_back(res["total"], cost),
        accounts=accounts(conn, ev, threshold), load=owner_load(steps, today), kinds=KINDS,
        taken=taken, decisions=DECISIONS,
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
    values["kind"] = values["kind"] if values.get("kind") in dict(KINDS) else "booth"
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
        first, last = date.fromisoformat(values["starts"]), date.fromisoformat(values["ends"])
        rows = [r for r in conn.execute("SELECT * FROM playbook_steps ORDER BY sort, id") if not r["kinds"] or values["kind"] in r["kinds"].split(",")]
        conn.executemany("INSERT INTO event_steps (event_id, phase, workstream, title, owner, due, status, done_when, critical, sort) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         [(new_id, r["phase"], r["workstream"], r["title"], r["owner"],
                           ((last if r["phase"] == "follow" else first) + timedelta(days=r["offset_days"])).isoformat(),
                           "Not started", r["done_when"], r["critical"], i) for i, r in enumerate(rows)])
    return new_id


def remove_event(conn, event_id):
    for table in ("event_steps", "event_promos", "event_creatives", "event_costs", "event_targets"):
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
              day_of(d["due"], "The due date") if d.get("due") else None, status, (d.get("done_when") or "").strip() or None, (d.get("note") or "").strip() or None,
              1 if d.get("critical") else 0)
    if step_id:
        conn.execute("UPDATE event_steps SET phase = ?, workstream = ?, title = ?, owner = ?, due = ?, status = ?, done_when = ?, note = ?, critical = ? WHERE id = ?", values + (step_id,))
    else:
        conn.execute("INSERT INTO event_steps (phase, workstream, title, owner, due, status, done_when, note, critical, event_id, sort) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?, (SELECT COALESCE(MAX(sort), 0) + 1 FROM event_steps WHERE event_id = ?))", values + (event_id, event_id))


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
              (d.get("done_when") or "").strip() or None, (d.get("owner") or "").strip() or None,
              ",".join(k for k, _ in KINDS if d.get("kind_" + k)) or None, 1 if d.get("critical") else 0)
    if step_id:
        conn.execute("UPDATE playbook_steps SET phase = ?, workstream = ?, title = ?, offset_days = ?, done_when = ?, owner = ?, kinds = ?, critical = ? WHERE id = ?", values + (step_id,))
    else:
        conn.execute("INSERT INTO playbook_steps (phase, workstream, title, offset_days, done_when, owner, kinds, critical, sort) "
                     "VALUES (?,?,?,?,?,?,?,?, (SELECT COALESCE(MAX(sort), 0) + 1 FROM playbook_steps))", values)


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
    amount, planned = number(d.get("amount")) or 0, number(d.get("planned"))
    values = (kind, need(d.get("item"), "What the cost is for"), amount, planned, 1 if d.get("paid") else 0)
    if cost_id:
        conn.execute("UPDATE event_costs SET category = ?, item = ?, amount = ?, planned = ?, paid = ? WHERE id = ?", values + (cost_id,))
    else:
        conn.execute("INSERT INTO event_costs (category, item, amount, planned, paid, event_id) VALUES (?,?,?,?,?,?)", values + (event_id,))


def save_targets(conn, event_id, text):
    """The target account list, pasted as lines: company, tier (1-3), optional domain. Only company names are kept, never people."""
    rows = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in re.split(r"\t|,|;", line) if p.strip()]
        if not parts or parts[0].lower() in ("company", "#", "name"):
            continue
        tier = next((int(p[-1]) for p in parts[1:] if re.fullmatch(r"(tier\s*)?[1-3]", p.lower())), 2)
        domain = next((p.lower() for p in parts[1:] if re.fullmatch(r"[\w.-]+\.[a-z]{2,}", p.lower())), None)
        rows.append((event_id, parts[0][:120], tier, domain))
    conn.execute("DELETE FROM event_targets WHERE event_id = ?", (event_id,))
    conn.executemany("INSERT INTO event_targets (event_id, company, tier, domain) VALUES (?,?,?,?)", rows)


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


REMOVE = {"remove_target": "event_targets", "remove_step": "event_steps", "remove_promo": "event_promos", "remove_creative": "event_creatives", "remove_cost": "event_costs",
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
    elif what == "targets":
        save_targets(conn, event_id, d.get("text"))
    elif what == "critical":
        conn.execute("UPDATE event_steps SET critical = ? WHERE id = ?", (1 if d.get("critical") else 0, item_id))
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

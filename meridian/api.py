"""HTTP API and static front end. Run with: uvicorn meridian.api:app"""

import hmac
from contextlib import contextmanager
from datetime import date, datetime
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import accounts, ads, alerts, backup, config, db, google, health, ingest, mailer, metrics, money, narrative, outbound, people, reminders, research, scheduler, scoring, screens, semrush, team, website, zoho
from .periods import Period, iso

app = FastAPI(title="Meridian")


@app.on_event("startup")
def start_up():
    try:  # a host with no lasting disk starts empty: fetch the stored copy of the data first
        if backup.restore():
            print("Restored the stored copy of the data.")
    except backup.BackupError as err:
        print("Could not restore the stored data:", err)
    backup.start()
    if not config.LIVE_DB.exists() and not config.SAMPLE_DB.exists():  # a brand-new host with nothing stored yet: start empty
        zoho.live_database().close()
    for path in (config.SAMPLE_DB, config.LIVE_DB):  # bring databases made by an older version up to date
        if path.exists():
            conn = db.connect(path)
            db.upgrade(conn)
            conn.commit()
            conn.close()
    scheduler.start()

@app.on_event("shutdown")
def shut_down():
    backup.flush()


TARGET_KEYS = {"leads", "qualified", "pipeline", "won", "budget_meta", "budget_li", "budget_organic", "budget_outbound"}


@contextmanager
def session():
    conn = db.connect()
    try:
        money.load(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def period(conn, range="month", start=None, end=None):
    return Period(db.now(conn), range, start, end)


@app.middleware("http")
async def no_stale_assets(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# ------------------------------------------------------------------------------- sign-in

OPEN_PATHS = ("/api/login", "/api/logout", "/static/", "/webhooks/", "/tasks/", "/healthz")  # webhooks and tasks carry their own token


WRITES = ("POST", "PUT", "PATCH", "DELETE")
LEADER_ONLY = ("/api/people",)                                                                   # not even to look at
MEMBER_WRITES = ("/api/login", "/api/logout", "/api/account/", "/api/targets", "/api/leads/", "/api/sources/")  # what a team member may change


@app.middleware("http")
async def signed_in_only(request: Request, call_next):
    """Once sign-in is on, every page of data needs a signed-in person; anyone else gets the sign-in page."""
    path = request.url.path
    conn = db.connect()
    try:
        needed = accounts.required(conn)
        person = accounts.who(conn, datetime.now().replace(microsecond=0), request.cookies.get(accounts.COOKIE)) if needed else None
    finally:
        conn.close()
    request.state.person = person
    if needed and not person and not path.startswith(OPEN_PATHS):
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Please sign in."}, status_code=401)
        return FileResponse(str(config.STATIC_DIR / "login.html"), headers={"Cache-Control": "no-store"})
    if person and person["role"] != "admin":  # a team member sees the figures and fills in their own day; the rest is for leaders
        write = request.method in WRITES
        if path.startswith(LEADER_ONLY) or (write and not (path.startswith(MEMBER_WRITES) and not (path == "/api/targets" and request.method == "PUT"))):
            return JSONResponse({"detail": "Only a leader can do this."}, status_code=403)
    response = await call_next(request)
    if request.method in WRITES and response.status_code < 400:
        backup.changed()  # something was saved: the stored copy needs refreshing
    return response


@app.get("/healthz")
def health_check():
    return {"ok": True}


@app.api_route("/tasks/sync", methods=["GET", "POST"])
def task_sync(token: str = "", request: Request = None):
    """For an outside timer: wakes the app and pulls fresh data from every connected source. Answers at once; the sync runs on."""
    wanted = config.setting("MERIDIAN_TASK_TOKEN")
    if not wanted:
        raise HTTPException(503, "Timed syncs are off. Set MERIDIAN_TASK_TOKEN to enable them.")
    given = token or (request.headers.get("x-meridian-token") if request else "")
    given = given or ""
    # A "+" inside a web address arrives as a space, so a token holding one is tried both ways.
    if not any(hmac.compare_digest(g, wanted) for g in (given, given.replace(" ", "+"))):
        raise HTTPException(401, "Bad token")
    started = scheduler.sync_now()
    return {"ok": True, "started": started, "note": "Syncing in the background." if started else "A sync is already running."}


class SignIn(BaseModel):
    email: str
    password: str


@app.post("/api/login")
def sign_in(body: SignIn, request: Request):
    address = request.client.host if request.client else ""
    if accounts.blocked(address):
        raise HTTPException(429, "Too many wrong tries. Wait five minutes and try again.")
    with session() as conn:
        token = accounts.sign_in(conn, datetime.now().replace(microsecond=0), body.email, body.password, address)
    if not token:
        raise HTTPException(401, "That email and password do not match.")
    response = JSONResponse({"ok": True})
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(accounts.COOKIE, token, max_age=accounts.SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=secure)
    return response


@app.post("/api/logout")
def sign_out(request: Request):
    with session() as conn:
        accounts.sign_out(conn, request.cookies.get(accounts.COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(accounts.COOKIE)
    return response


# ------------------------------------------------------------------------------- people

class PersonChange(BaseModel):
    account_id: Optional[int] = None
    member_id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    focus: Optional[str] = None
    targets: bool = False


class NewPassword(BaseModel):
    current: str
    new: str


@app.get("/api/people")
def get_people(request: Request):
    with session() as conn:
        return people.view(conn, getattr(request.state, "person", None))


@app.post("/api/people")
def save_person(b: PersonChange, request: Request):
    with session() as conn:
        try:
            people.save(conn, datetime.now().replace(microsecond=0), getattr(request.state, "person", None), b.account_id, b.member_id,
                        b.name, b.email, b.role, b.password, b.focus, b.targets)
        except (accounts.AccountError, team.TeamError) as err:
            raise HTTPException(400, str(err))
        return {"ok": True}


@app.post("/api/people/remove")
def remove_person(b: PersonChange, request: Request):
    with session() as conn:
        try:
            people.remove(conn, getattr(request.state, "person", None), b.account_id, b.member_id)
        except accounts.AccountError as err:
            raise HTTPException(400, str(err))
        return {"ok": True}


@app.post("/api/account/password")
def change_own_password(b: NewPassword, request: Request):
    person = getattr(request.state, "person", None)
    if not person:
        raise HTTPException(400, "Nobody is signed in.")
    with session() as conn:
        try:
            accounts.change_password(conn, person["id"], b.current, b.new, request.cookies.get(accounts.COOKIE))
        except accounts.AccountError as err:
            raise HTTPException(400, str(err))
        return {"ok": True}


# ------------------------------------------------------------------------------- screens

@app.get("/api/shell")
def get_shell(request: Request):
    with session() as conn:
        shell = screens.shell(conn, db.now(conn))
        person = getattr(request.state, "person", None)
        if person:  # the signed-in person replaces the placeholder shown when sign-in is off
            shell["user"] = dict(name=person["name"], role="Leader" if person["role"] == "admin" else "Team member", email=person["email"],
                                 initials="".join(w[0] for w in person["name"].split()[:2]).upper(), signed_in=True,
                                 admin=person["role"] == "admin", member_id=people.member_for(conn, person["email"]))
        return shell


@app.get("/api/overview")
def get_overview(request: Request, range: str = "month", start: Optional[str] = None, end: Optional[str] = None, channel: str = "all"):
    with session() as conn:
        data = screens.overview(conn, db.now(conn), period(conn, range, start, end), channel)
        data["team"] = team_summary(targets_view(conn, request))
        return data


@app.get("/api/funnel")
def get_funnel(range: str = "month", start: Optional[str] = None, end: Optional[str] = None, segment: str = "all"):
    with session() as conn:
        return screens.funnel(conn, db.now(conn), period(conn, range, start, end), segment)


@app.get("/api/channels")
def get_channels(range: str = "month", start: Optional[str] = None, end: Optional[str] = None):
    with session() as conn:
        return screens.channels(conn, db.now(conn), period(conn, range, start, end))


@app.get("/api/paid")
def get_paid(range: str = "month", start: Optional[str] = None, end: Optional[str] = None):
    with session() as conn:
        return screens.paid(conn, db.now(conn), period(conn, range, start, end))


@app.get("/api/outbound")
def get_outbound(range: str = "month", start: Optional[str] = None, end: Optional[str] = None):
    with session() as conn:
        return screens.outbound(conn, db.now(conn), period(conn, range, start, end))


@app.get("/api/web")
def get_web(range: str = "month", start: Optional[str] = None, end: Optional[str] = None, site: Optional[str] = None):
    with session() as conn:
        return website.build(conn, db.now(conn), period(conn, range, start, end), site)


class FormSite(BaseModel):
    source: str
    site: str = ""


@app.put("/api/web/forms")
def put_form_site(body: FormSite):
    """Say which website a form or chatbot sits on. Zoho records the form's name but not the site."""
    with session() as conn:
        try:
            website.set_form_site(conn, body.source, body.site)
        except ValueError as err:
            raise HTTPException(400, str(err))
        return {"ok": True}


@app.get("/api/quality")
def get_quality(range: str = "month", start: Optional[str] = None, end: Optional[str] = None):
    with session() as conn:
        return screens.quality(conn, db.now(conn), period(conn, range, start, end))


@app.get("/api/subscriptions")
def get_subscriptions():
    with session() as conn:
        return screens.subscriptions(conn, db.now(conn))


@app.get("/api/reports")
def get_reports():
    with session() as conn:
        return screens.reports(conn, db.now(conn))


@app.get("/api/alerts")
def get_alerts():
    with session() as conn:
        return screens.alerts_page(conn, db.now(conn))


@app.get("/api/settings")
def get_settings(range: str = "month", start: Optional[str] = None, end: Optional[str] = None):
    with session() as conn:
        return screens.settings(conn, db.now(conn), period(conn, range, start, end))


# ------------------------------------------------------------------------------- leads

@app.get("/api/leads")
def get_leads(range: str = "month", start: Optional[str] = None, end: Optional[str] = None, q: str = "",
              channel: str = "", owner: str = "", status: str = "", score: str = "", needs_update: bool = False,
              segment: str = "", age: str = "", activity: str = "", limit: int = 50, offset: int = 0):
    with session() as conn:
        return screens.leads(conn, db.now(conn), period(conn, range, start, end), q.strip(), channel, owner, status,
                             score, needs_update or activity == "waiting", max(1, min(limit, 200)), max(0, offset), segment, age, activity)


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: int):
    with session() as conn:
        lead = screens.lead_detail(conn, db.now(conn), lead_id)
        if not lead:
            raise HTTPException(404, "Lead not found")
        return lead


class LeadPatch(BaseModel):
    owner: Optional[str] = None
    status: Optional[str] = None


@app.patch("/api/leads/{lead_id}")
def patch_lead(lead_id: int, body: LeadPatch):
    """Change a lead's owner or status here. This does not write back to Zoho CRM."""
    with session() as conn:
        now = db.now(conn)
        lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "Lead not found")
        if body.status and body.status not in metrics.STATUSES:
            raise HTTPException(400, "Unknown status")
        if body.owner and body.owner != lead["owner"]:
            conn.execute("UPDATE leads SET owner = ? WHERE id = ?", (body.owner, lead_id))
            conn.execute("INSERT INTO lead_events (lead_id, at, kind, title, detail) VALUES (?,?,?,?,?)",
                         (lead_id, iso(now), "crm", "Reassigned to " + body.owner, "Was " + (lead["owner"] or "unassigned")))
        if body.status and body.status != lead["status"]:
            who = db.get_setting(conn, "current_user", "owner")
            conn.execute("UPDATE leads SET status = ?, last_activity = ?, last_activity_at = ? WHERE id = ?",
                         (body.status, "Status changed", iso(now), lead_id))
            conn.execute("INSERT INTO lead_events (lead_id, at, kind, title, detail) VALUES (?,?,?,?,?)",
                         (lead_id, iso(now), "crm", "Status → " + body.status, "Updated by " + who))
            reminders.record_owner_update(conn, lead_id, now)
        return screens.lead_detail(conn, now, lead_id)


# ------------------------------------------------------------------------------- scoring

class Scoring(BaseModel):
    weights: Dict[str, int]
    threshold: int
    range: str = "month"
    start: Optional[str] = None
    end: Optional[str] = None


def check_scoring(conn, body):
    keys = {c["key"] for c in scoring.criteria(conn)}
    if set(body.weights) != keys or any(w < 0 for w in body.weights.values()):
        raise HTTPException(400, "Weights must cover every criterion and be zero or more")
    if not 1 <= body.threshold <= 100:
        raise HTTPException(400, "Threshold must be between 1 and 100")


@app.post("/api/scoring/preview")
def preview_scoring(body: Scoring):
    with session() as conn:
        check_scoring(conn, body)
        p = period(conn, body.range, body.start, body.end)
        return {"qualified": scoring.count_qualified(conn, body.weights, body.threshold, p.start_dt, p.end_dt)}


@app.put("/api/scoring")
def save_scoring(body: Scoring):
    with session() as conn:
        check_scoring(conn, body)
        if sum(body.weights.values()) != 100:
            raise HTTPException(400, "Weights must total 100")
        scoring.save(conn, body.weights, body.threshold)
        now = db.now(conn)
        db.set_setting(conn, "scoring_changed_at", now.date().isoformat())
        db.set_setting(conn, "scoring_changed_by", db.get_setting(conn, "current_user", ""))
        alerts.run(conn, now)
        return {"ok": True}


# ------------------------------------------------------------------------------- targets and the daily checklist

class TeamChange(BaseModel):
    """One change on the Targets screen. `what` names it; the other fields are used as that change needs."""
    what: str
    id: Optional[int] = None
    member_id: Optional[int] = None
    name: Optional[str] = None
    focus: Optional[str] = None
    email: Optional[str] = None
    title: Optional[str] = None
    metric: Optional[str] = None
    period: Optional[str] = None
    target: Optional[float] = None
    unit: Optional[str] = None
    amount: Optional[float] = None
    text: Optional[str] = None
    solved: Optional[bool] = None


def own_member(conn, request):
    """For a signed-in team member: the id of their own place on the Targets screen (0 when they have none). None for a leader."""
    person = getattr(request.state, "person", None)
    if not person or person["role"] == "admin":
        return None
    return people.member_for(conn, person["email"]) or 0


MEMBER_CHANGES = {  # what a team member may change on Targets, and the table that says whose it is
    "log": "goals", "goal_note": "goals", "toggle_task": "team_tasks", "remove_task": "team_tasks", "resolve": "blockers",
    "task": None, "note": None, "blocker": None,
}


def targets_view(conn, request):
    """The Targets screen's data, cut down to their own targets for a team member."""
    view = team.view(conn, db.now(conn))
    mine = own_member(conn, request)
    if mine is not None:
        view["members"] = [m for m in view["members"] if m["id"] == mine]
        for key in ("goals", "tasks", "blockers"):
            view[key] = [x for x in view[key] if x["member_id"] == mine]
        for key in ("notes", "history"):
            view[key] = {k: v for k, v in view[key].items() if k == mine}
        view["demo"] = False
    return view


def team_summary(view):
    """For the Overview: one line per person on how their targets are going."""
    people_rows = []
    for m in view["members"]:
        goals = [g for g in view["goals"] if g["member_id"] == m["id"]]
        tasks = [t for t in view["tasks"] if t["member_id"] == m["id"]]
        due = [g for g in goals if g["today_share"] > 0]
        people_rows.append(dict(
            id=m["id"], name=m["name"], focus=m["focus"] or "", targets=len(goals),
            on_track=sum(g["status"] in ("done", "on_track") for g in goals),
            pct=round(sum(min(g["pct"], 100) for g in goals) / len(goals)) if goals else 0,
            pace=round(sum(min(g["pace_pct"], 100) for g in goals) / len(goals)) if goals else 0,
            today_done=sum(bool(g["today_met"]) for g in due) + sum(bool(t["done"]) for t in tasks), today_all=len(due) + len(tasks)))
    return dict(people=people_rows, blockers=sum(1 for b in view["blockers"] if not b["resolved_at"]), demo=view["demo"], week=view["week_label"])


@app.get("/api/targets")
def get_targets(request: Request):
    with session() as conn:
        return targets_view(conn, request)


@app.get("/api/targets/report")
def get_targets_report(request: Request, back: int = 0):
    with session() as conn:
        report = team.report(conn, db.now(conn), back)
        mine = own_member(conn, request)
        if mine is not None:
            report["people"] = [p for p in report["people"] if p["id"] == mine]
        return report


@app.post("/api/targets")
def change_targets(b: TeamChange, request: Request):
    with session() as conn:
        now = db.now(conn)
        mine = own_member(conn, request)
        if mine is not None:
            if b.what not in MEMBER_CHANGES:
                raise HTTPException(403, "Only a leader can do this.")
            table = MEMBER_CHANGES[b.what]
            row = conn.execute("SELECT member_id FROM {} WHERE id = ?".format(table), (b.id,)).fetchone() if table else None
            if (row["member_id"] if row else b.member_id) != mine or not mine:
                raise HTTPException(403, "You can only fill in your own targets.")
        try:
            if b.what == "member":
                team.save_member(conn, b.id, b.name, b.focus, b.email)
            elif b.what == "remove_member":
                team.remove_member(conn, b.id)
            elif b.what == "goal":
                team.save_goal(conn, now, b.id, b.member_id, b.title, b.metric or "manual", b.period or "week", b.target, b.unit)
            elif b.what == "remove_goal":
                team.remove_goal(conn, b.id)
            elif b.what == "log":
                team.log(conn, now, b.id, b.amount or 0)
            elif b.what == "clear_demo":
                team.clear_demo(conn)
            elif b.what == "goal_note":
                team.save_goal_note(conn, now, b.id, b.text)
            elif b.what == "task":
                team.add_task(conn, now, b.member_id, b.title)
            elif b.what == "toggle_task":
                team.toggle_task(conn, b.id)
            elif b.what == "remove_task":
                team.remove_task(conn, b.id)
            elif b.what == "note":
                team.save_note(conn, now, b.member_id, b.text)
            elif b.what == "blocker":
                team.add_blocker(conn, now, b.member_id, b.text)
            elif b.what == "resolve":
                team.resolve_blocker(conn, now, b.id, b.solved is not False)
            else:
                raise HTTPException(400, "Unknown change")
        except team.TeamError as err:
            raise HTTPException(400, str(err))
        return {"ok": True}


# ------------------------------------------------------------------------------- subscriptions

class Subscription(BaseModel):
    name: str
    category: Optional[str] = None
    monthly_cost: int = 0
    seats: Optional[int] = None
    owner: Optional[str] = None
    renews_on: Optional[str] = None
    billing: str = "Monthly"
    annual_cost: Optional[int] = None
    email: Optional[str] = None


def subscription_values(body):
    if not body.name.strip():
        raise HTTPException(400, "A tool needs a name")
    if body.billing not in ("Monthly", "Annual"):
        raise HTTPException(400, "Billing is Monthly or Annual")
    if body.renews_on:
        try:
            date.fromisoformat(body.renews_on)
        except ValueError:
            raise HTTPException(400, "Renewal date must be YYYY-MM-DD")
    return (body.name.strip(), body.category, max(0, body.monthly_cost), body.seats, body.owner, body.renews_on or None,
            body.billing, body.annual_cost if body.billing == "Annual" else None, (body.email or "").strip() or None)


@app.post("/api/subscriptions")
def add_subscription(body: Subscription):
    with session() as conn:
        conn.execute("INSERT INTO subscriptions (name, category, monthly_cost, seats, owner, renews_on, billing, annual_cost, email) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", subscription_values(body))
        alerts.run(conn, db.now(conn))
        return {"ok": True}


@app.put("/api/subscriptions/{sub_id}")
def update_subscription(sub_id: int, body: Subscription):
    with session() as conn:
        cur = conn.execute("UPDATE subscriptions SET name = ?, category = ?, monthly_cost = ?, seats = ?, owner = ?, "
                           "renews_on = ?, billing = ?, annual_cost = ?, email = ? WHERE id = ?", subscription_values(body) + (sub_id,))
        if not cur.rowcount:
            raise HTTPException(404, "Subscription not found")
        alerts.run(conn, db.now(conn))
        return {"ok": True}


@app.delete("/api/subscriptions/{sub_id}")
def delete_subscription(sub_id: int):
    with session() as conn:
        conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        alerts.run(conn, db.now(conn))
        return {"ok": True}


# ------------------------------------------------------------------------------- reports

class ReportText(BaseModel):
    headline: str
    body: str
    next_steps: str = ""


class Recipient(BaseModel):
    name: str
    role: Optional[str] = None
    email: Optional[str] = None


@app.put("/api/reports/current")
def save_report(body: ReportText):
    with session() as conn:
        row = narrative.ensure_draft(conn, db.now(conn))
        conn.execute("UPDATE reports SET headline = ?, body = ?, next_steps = ?, edited = 1 WHERE id = ?",
                     (body.headline.strip(), body.body.strip(), body.next_steps.strip(), row["id"]))
        return {"ok": True}


@app.post("/api/reports/current/redraft")
def redraft_report():
    """Throw away edits and write the summary again from the current figures."""
    with session() as conn:
        narrative.ensure_draft(conn, db.now(conn), rewrite=True)
        return {"ok": True}


@app.post("/api/reports/current/test")
def send_test_report():
    with session() as conn:
        now = db.now(conn)
        row = narrative.ensure_draft(conn, now)
        user = conn.execute("SELECT * FROM users WHERE name = ?", (db.get_setting(conn, "current_user"),)).fetchone()
        to = user["email"] if user else None
        mailer.queue(conn, now, "report_test", to, "[Test] " + (row["headline"] or "Weekly marketing report"),
                     (row["body"] or "") + ("\n\nNext week\n" + row["next_steps"] if row["next_steps"] else ""))
        sent = mailer.flush(conn, now)
        if sent:
            return {"ok": True, "message": "Test sent to " + to}
        return {"ok": False, "message": "Saved to the outbox. Email is not set up yet, so nothing was sent."}


@app.post("/api/reports/recipients")
def add_recipient(body: Recipient):
    with session() as conn:
        if not body.name.strip():
            raise HTTPException(400, "A recipient needs a name or email")
        conn.execute("INSERT INTO report_recipients (name, role, email) VALUES (?,?,?)",
                     (body.name.strip(), body.role, body.email or (body.name.strip() if "@" in body.name else None)))
        return {"ok": True}


@app.delete("/api/reports/recipients/{rid}")
def delete_recipient(rid: int):
    with session() as conn:
        conn.execute("DELETE FROM report_recipients WHERE id = ?", (rid,))
        return {"ok": True}


# ------------------------------------------------------------------------------- rules, targets, tags, sources

class Toggle(BaseModel):
    enabled: bool


class Benchmark(BaseModel):
    value: Optional[float] = None
    watch: Optional[bool] = None
    reset: bool = False


@app.put("/api/benchmarks/{key}")
def set_benchmark(key: str, body: Benchmark):
    with session() as conn:
        try:
            health.save(conn, key, body.value, body.watch, body.reset)
        except ValueError as err:
            raise HTTPException(400, str(err))
        alerts.run(conn, db.now(conn))
        return {"ok": True}


@app.put("/api/alert-rules/{key}")
def toggle_rule(key: str, body: Toggle):
    with session() as conn:
        cur = conn.execute("UPDATE alert_rules SET enabled = ? WHERE key = ?", (int(body.enabled), key))
        if not cur.rowcount:
            raise HTTPException(404, "Rule not found")
        alerts.run(conn, db.now(conn))
        return {"ok": True}


class Target(BaseModel):
    month: str
    key: str
    value: float


@app.put("/api/targets")
def set_target(body: Target):
    with session() as conn:
        if body.key not in TARGET_KEYS or body.value < 0 or len(body.month) != 7:
            raise HTTPException(400, "Unknown target")
        conn.execute("INSERT INTO targets (month, key, value) VALUES (?,?,?) "
                     "ON CONFLICT (month, key) DO UPDATE SET value = excluded.value", (body.month, body.key, body.value))
        alerts.run(conn, db.now(conn))
        return {"ok": True}


class TagMap(BaseModel):
    channel_id: Optional[str] = None
    left_out: bool = False


@app.put("/api/utm/{map_id}")
def map_tag(map_id: int, body: TagMap):
    """Point a tracking-tag pair or a lead source at a channel, or leave a lead source out. Existing leads follow."""
    with session() as conn:
        row = conn.execute("SELECT * FROM utm_map WHERE id = ?", (map_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Tag not found")
        is_source, live = row["medium"] == ingest.LEAD_SOURCE, not db.is_demo(conn)
        if body.left_out:
            if not is_source:
                raise HTTPException(400, "Only a lead source can be left out")
            gone = ingest.leave_out(conn, row["source"])
            if live:
                zoho.remember(row["source"], excluded=True)
            alerts.run(conn, db.now(conn))
            return {"ok": True, "message": "{:,} leads left out. New ones from this source are skipped from now on.".format(gone)}
        if body.channel_id and not conn.execute("SELECT 1 FROM channels WHERE id = ?", (body.channel_id,)).fetchone():
            raise HTTPException(400, "Unknown channel")
        message = "Mapping saved."
        if row["excluded"]:
            ingest.bring_back(conn, row["source"])
            if live:
                db.set_setting(conn, zoho.REFETCH, "1")
                message = "Saved. Its leads return with the next Zoho sync, which fetches everything again and takes a few minutes."
        conn.execute("UPDATE utm_map SET channel_id = ? WHERE id = ?", (body.channel_id, map_id))
        if is_source:  # a CRM lead source: applies to leads that carry no tracking tags
            key = ingest.source_key(row["source"]).lower()
            conn.execute("UPDATE leads SET channel_id = ? WHERE " + ingest.SOURCE_SQL.format("leads") + " = ? AND "
                         + ingest.UNTAGGED_SQL.format("leads"), (body.channel_id, key))
            conn.execute("UPDATE deals SET channel_id = ? WHERE lead_id IS NULL AND " + ingest.SOURCE_SQL.format("deals") + " = ?",
                         (body.channel_id, key))
            if live:
                zoho.remember(row["source"], body.channel_id)
        else:
            conn.execute("UPDATE leads SET channel_id = ? WHERE lower(COALESCE(utm_source, '')) = ? AND lower(COALESCE(utm_medium, '')) = ?",
                         (body.channel_id, row["source"].lower(), row["medium"].lower()))
        conn.execute("UPDATE deals SET channel_id = (SELECT channel_id FROM leads WHERE leads.id = deals.lead_id) WHERE lead_id IS NOT NULL")
        return {"ok": True, "message": message}


@app.post("/api/sources/{key}/sync")
def sync_source(key: str):
    with session() as conn:
        row = conn.execute("SELECT * FROM sources WHERE key = ?", (key,)).fetchone()
        if not row:
            raise HTTPException(404, "Source not found")
        if key == "crustdata":
            if not research.configured():
                return {"ok": False, "message": "Company research needs a Crustdata API key. Run ./connect-crustdata.sh in Terminal."}
            try:
                summary = research.run(conn, db.now(conn), limit=250)
            except research.ResearchError as err:
                return {"ok": False, "message": str(err)}
            return {"ok": True, "message": "Company research: " + research.describe(summary) + "."}
        if key in outbound.KEYS:
            if db.is_demo(conn):
                return {"ok": False, "message": "This is sample data. Outbound tools connect to your own data."}
            try:
                summary = outbound.sync(conn, db.now(conn), key)
            except outbound.OutboundError as err:
                return {"ok": False, "message": str(err)}
            return {"ok": True, "message": "Synced: " + outbound.describe(summary) + "."}
        if key == "semrush":
            added = semrush.load(conn, db.now(conn))
            return {"ok": True, "message": "Semrush: " + semrush.describe(added) + "."}
        if key in ads.SYNCS:
            if db.is_demo(conn):
                return {"ok": False, "message": "This is sample data. Ad platforms connect to your own data."}
            try:
                summary = ads.sync(conn, db.now(conn), key)
            except ads.AdsError as err:
                return {"ok": False, "message": str(err)}
            return {"ok": True, "message": "Synced: " + ads.describe(summary) + "."}
        if key in google.SYNCS:
            if db.is_demo(conn):
                return {"ok": False, "message": "This is sample data. Google connects to your own data."}
            try:
                summary = google.sync(conn, db.now(conn), key)
            except google.GoogleError as err:
                return {"ok": False, "message": str(err)}
            return {"ok": True, "message": "Synced: " + google.describe(summary) + "."}
        if key != "zoho":
            return {"ok": False, "message": "The {} connector is not built yet.".format(row["name"])}
        if db.is_demo(conn):
            return {"ok": False, "message": "This is sample data. Run ./connect-zoho.sh in Terminal to bring in your own Zoho leads."}
        now = db.now(conn)
        try:
            summary = zoho.sync(conn, now)
        except zoho.ZohoError as err:
            return {"ok": False, "message": str(err)}
        alerts.run(conn, now)
        return {"ok": True, "message": "Zoho CRM synced: " + zoho.describe(summary) + "."}


@app.post("/api/jobs/{name}")
def run_job(name: str):
    """Run a background job now: 'alerts' or 'reminders'. Schedule these with cron in production."""
    with session() as conn:
        now = db.now(conn)
        if name == "alerts":
            return {"new_alerts": len(alerts.run(conn, now))}
        if name == "reminders":
            return {"reminders": reminders.run(conn, now)}
        raise HTTPException(404, "Unknown job")


# ------------------------------------------------------------------------------- webhooks

@app.post("/webhooks/lead")
async def webhook_lead(request: Request, token: str = ""):
    """Receives a new or changed lead as JSON, e.g. from a Zoho CRM workflow rule or a Framer form."""
    if not config.WEBHOOK_TOKEN:
        raise HTTPException(503, "Webhooks are off. Set MERIDIAN_WEBHOOK_TOKEN to enable them.")
    if token != config.WEBHOOK_TOKEN and request.headers.get("x-meridian-token") != config.WEBHOOK_TOKEN:
        raise HTTPException(401, "Bad token")
    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(400, "Expected a JSON object")
    with session() as conn:
        now = db.now(conn)
        try:
            tagged = bool(data.get("utm_source") or data.get("utm_medium"))
            if ingest.is_left_out(ingest.excluded_sources(conn), data.get("lead_source"), tagged):
                return {"id": None, "created": False, "left_out": True}
            lead_id, created = ingest.upsert_lead(conn, now, data)
        except ValueError as err:
            raise HTTPException(400, str(err))
        conn.execute("UPDATE sources SET status = 'connected', last_sync_at = ? WHERE key = ?",
                     (iso(now), "framer" if data.get("form_name") else "zoho"))
        return {"id": lead_id, "created": created}


# ------------------------------------------------------------------------------- front end

@app.get("/")
def index():
    return FileResponse(str(config.STATIC_DIR / "index.html"))


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

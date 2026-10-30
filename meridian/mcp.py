"""MCP server: lets Claude (claude.ai, Desktop, Code) and ChatGPT read and change Meridian for a signed-in person.

The assistant app adds https://<meridian>/mcp as a connector. On first use it registers itself (/oauth/register), sends
the person to /oauth/authorize, where they sign in with their Meridian login and allow access, then swaps the code for
a token (/oauth/token, PKCE). Every tool call then runs as that person, through the same API the screens use, so
the same checks apply. Tokens are stored as hashes only; an access token lasts an hour, a refresh token 30 days.
An admin can disconnect any app in Settings. Logins and passwords cannot be changed through MCP.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from html import escape
from urllib.parse import parse_qsl, urlencode, urlparse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from . import accounts, config, db
from .periods import iso

router = APIRouter()
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
ACCESS_HOURS, REFRESH_DAYS, CODE_MINUTES = 1, 30, 10
MAX_CLIENTS = 500  # registration is open to any app, as the connector standard expects; this caps it
# no assistant may change who can sign in or anyone's password
BLOCKED = ("/api/login", "/api/logout", "/api/account", "/api/people", "/api/mcp")
SECURE_PAGE = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Content-Security-Policy": "frame-ancestors 'none'"}


def now():
    return datetime.now().replace(microsecond=0)


def hashed(token):
    return hashlib.sha256(token.encode()).hexdigest()


def base(request):
    """Meridian's public address, as the assistant app sees it."""
    return (config.setting("MERIDIAN_PUBLIC_URL") or str(request.base_url)).rstrip("/")


# ------------------------------------------------------------------------------- discovery

@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
def resource_metadata(request: Request):
    b = base(request)
    return dict(resource=b + "/mcp", authorization_servers=[b], bearer_methods_supported=["header"], resource_name="Meridian")


@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/mcp")
def server_metadata(request: Request):
    b = base(request)
    return dict(issuer=b, authorization_endpoint=b + "/oauth/authorize", token_endpoint=b + "/oauth/token",
                registration_endpoint=b + "/oauth/register", revocation_endpoint=b + "/oauth/revoke",
                response_types_supported=["code"], grant_types_supported=["authorization_code", "refresh_token"],
                code_challenge_methods_supported=["S256"], scopes_supported=["meridian"],
                token_endpoint_auth_methods_supported=["none", "client_secret_post", "client_secret_basic"])


# ------------------------------------------------------------------------------- app registration

async def form_of(request):
    """A form-encoded body as a dict (the OAuth pages and token endpoint send nothing else)."""
    return dict(parse_qsl((await request.body()).decode("utf-8", "replace"), keep_blank_values=True))


def oauth_error(code, text, status=400):
    return JSONResponse(dict(error=code, error_description=text), status_code=status, headers={"Cache-Control": "no-store"})


def allowed_redirect(uri):
    u = urlparse(uri or "")
    return (u.scheme == "https" and u.netloc) or (u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1")) \
        or (u.scheme not in ("", "http", "https", "javascript", "data", "file") and "." in u.scheme)  # an app's own scheme, e.g. com.example.app


@router.post("/oauth/register")
async def register(request: Request):
    try:
        d = await request.json()
    except ValueError:
        return oauth_error("invalid_client_metadata", "The request body must be JSON.")
    uris = d.get("redirect_uris") or []
    if not isinstance(uris, list) or not uris or not all(isinstance(u, str) and allowed_redirect(u) for u in uris):
        return oauth_error("invalid_redirect_uri", "Each redirect URI must use https, or http on localhost.")
    method = d.get("token_endpoint_auth_method") or "none"
    if method not in ("none", "client_secret_post", "client_secret_basic"):
        return oauth_error("invalid_client_metadata", "Unsupported token_endpoint_auth_method.")
    name = str(d.get("client_name") or "AI assistant")[:80]
    client_id, secret = secrets.token_urlsafe(24), (secrets.token_urlsafe(32) if method != "none" else None)
    conn = db.connect()
    try:
        if conn.execute("SELECT COUNT(*) FROM mcp_clients").fetchone()[0] >= MAX_CLIENTS:
            return oauth_error("temporarily_unavailable", "Too many registered apps.", 503)
        conn.execute("INSERT INTO mcp_clients (client_id, secret_hash, name, redirect_uris, auth_method, created_at) VALUES (?,?,?,?,?,?)",
                     (client_id, hashed(secret) if secret else None, name, json.dumps(uris), method, iso(now())))
        conn.commit()
    finally:
        conn.close()
    out = dict(client_id=client_id, client_id_issued_at=int(now().timestamp()), client_name=name, redirect_uris=uris,
               token_endpoint_auth_method=method, grant_types=["authorization_code", "refresh_token"], response_types=["code"])
    if secret:
        out.update(client_secret=secret, client_secret_expires_at=0)
    return JSONResponse(out, status_code=201, headers={"Cache-Control": "no-store"})


def client_of(conn, client_id):
    return conn.execute("SELECT * FROM mcp_clients WHERE client_id = ?", (client_id or "",)).fetchone()


# ------------------------------------------------------------------------------- sign-in and consent

AUTH_FIELDS = ("client_id", "redirect_uri", "state", "code_challenge", "code_challenge_method", "scope", "resource")


def page(title, body, status=200):
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t} · Meridian</title><style>
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#f5f5f7;color:#1d1d1f;display:grid;place-items:center;min-height:100vh;margin:0}}
main{{background:#fff;border-radius:18px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:32px;width:min(420px,92vw)}}
h1{{font-size:21px;margin:0 0 12px}} p{{color:#6e6e73;font-size:14px;line-height:1.5;margin:0 0 14px}} b{{color:#1d1d1f}}
label{{display:block;font-size:13px;margin:12px 0 4px}} input[type=email],input[type=password]{{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #d2d2d7;border-radius:10px;font-size:14px}}
.row{{display:flex;gap:10px;margin-top:20px}} button{{flex:1;padding:11px;border-radius:10px;border:0;font-size:14px;font-weight:600;cursor:pointer}}
.go{{background:#0071e3;color:#fff}} .no{{background:#ececef;color:#1d1d1f}} .err{{color:#d1362f}}
</style></head><body><main><h1>{t}</h1>{b}</main></body></html>""".format(t=escape(title), b=body), status_code=status, headers=SECURE_PAGE)


def checked_request(conn, p):
    """The client and its redirect address, or an error text. Nothing is sent back to an address that is not registered."""
    client = client_of(conn, p.get("client_id"))
    if not client:
        return None, "This app is not registered with Meridian. Remove the connector and add it again."
    if p.get("redirect_uri") not in json.loads(client["redirect_uris"]):
        return None, "The app's return address does not match the one it registered."
    return client, None


def consent(client, p, person, needed, error=""):
    hidden = "".join('<input type="hidden" name="{}" value="{}">'.format(k, escape(p.get(k) or "")) for k in AUTH_FIELDS)
    login = "" if person or not needed else (
        '<label>Email</label><input type="email" name="email" autocomplete="username" required autofocus>'
        '<label>Password</label><input type="password" name="password" autocomplete="current-password" required>')
    who = "as <b>{}</b>".format(escape(person["name"])) if person else ("with your Meridian login" if needed else "")
    return page("Connect {} to Meridian".format(client["name"]), """
<p><b>{app}</b> is asking to use Meridian {who}. After you allow, you return to <b>{dest}</b>; continue only if that is the app you are connecting.</p>
<p>It will be able to read and change everything in Meridian that you can: events, tasks, leads, targets, settings and the rest.
It cannot change logins or passwords. You can disconnect it at any time in Settings.</p>
{err}<form method="post" action="/oauth/authorize">{hidden}{login}
<div class="row"><button class="no" name="decision" value="deny">Cancel</button><button class="go" name="decision" value="allow">Allow</button></div></form>""".format(
        app=escape(client["name"]), who=who, dest=escape(urlparse(p.get("redirect_uri") or "").netloc or p.get("redirect_uri") or ""), err='<p class="err">{}</p>'.format(escape(error)) if error else "", hidden=hidden, login=login))


@router.get("/oauth/authorize")
def authorize_page(request: Request):
    p = dict(request.query_params)
    conn = db.connect()
    try:
        client, error = checked_request(conn, p)
        if error:
            return page("Cannot connect", "<p>{}</p>".format(escape(error)), 400)
        if p.get("response_type") != "code" or not p.get("code_challenge") or p.get("code_challenge_method") != "S256":
            return back(p, "invalid_request", "PKCE with S256 is required.")
        needed = accounts.required(conn)
        person = accounts.who(conn, now(), request.cookies.get(accounts.COOKIE)) if needed else None
        return consent(client, p, person, needed)
    finally:
        conn.close()


def back(p, error=None, text="", code=None):
    q = dict(code=code) if code else dict(error=error, error_description=text)
    if p.get("state"):
        q["state"] = p["state"]
    sep = "&" if "?" in p["redirect_uri"] else "?"
    return RedirectResponse(p["redirect_uri"] + sep + urlencode(q), status_code=302, headers={"Cache-Control": "no-store"})


@router.post("/oauth/authorize")
async def authorize(request: Request):
    form = await form_of(request)
    p = {k: form.get(k) for k in AUTH_FIELDS}
    conn = db.connect()
    try:
        client, error = checked_request(conn, p)
        if error:
            return page("Cannot connect", "<p>{}</p>".format(escape(error)), 400)
        if form.get("decision") != "allow":
            return back(p, "access_denied", "The person cancelled.")
        if not p.get("code_challenge") or p.get("code_challenge_method") != "S256":
            return back(p, "invalid_request", "PKCE with S256 is required.")
        needed = accounts.required(conn)
        person = accounts.who(conn, now(), request.cookies.get(accounts.COOKIE)) if needed else None
        if needed and not person:
            address = request.client.host if request.client else ""
            if accounts.blocked(address):
                return consent(client, p, None, needed, "Too many wrong tries. Wait five minutes and try again.")
            token = accounts.sign_in(conn, now(), form.get("email"), form.get("password"), address)
            if not token:
                return consent(client, p, None, needed, "That email and password do not match.")
            person = accounts.who(conn, now(), token)
            accounts.sign_out(conn, token)  # the sign-in was only to check the password; no browser session is left behind
        code = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO mcp_codes (code_hash, client_id, account_id, redirect_uri, challenge, expires_at) VALUES (?,?,?,?,?,?)",
                     (hashed(code), client["client_id"], person["id"] if person else None, p["redirect_uri"], p["code_challenge"],
                      iso(now() + timedelta(minutes=CODE_MINUTES))))
        conn.commit()
        return back(p, code=code)
    finally:
        conn.close()


# ------------------------------------------------------------------------------- tokens

def client_auth(conn, request, form):
    """The calling app, checked against its secret when it registered with one."""
    client_id, secret = form.get("client_id"), form.get("client_secret")
    head = request.headers.get("authorization", "")
    if head.lower().startswith("basic "):
        try:
            client_id, secret = base64.b64decode(head[6:]).decode().split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return None
    client = client_of(conn, client_id)
    if not client:
        return None
    if client["secret_hash"] and not hmac.compare_digest(hashed(secret or ""), client["secret_hash"]):
        return None
    return client


def issue(conn, client_id, account_id):
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    t = now()
    conn.executemany("INSERT INTO mcp_tokens (token_hash, kind, client_id, account_id, created_at, expires_at) VALUES (?,?,?,?,?,?)",
                     [(hashed(access), "access", client_id, account_id, iso(t), iso(t + timedelta(hours=ACCESS_HOURS))),
                      (hashed(refresh), "refresh", client_id, account_id, iso(t), iso(t + timedelta(days=REFRESH_DAYS)))])
    conn.execute("DELETE FROM mcp_tokens WHERE expires_at < ?", (iso(t),))
    conn.execute("DELETE FROM mcp_codes WHERE expires_at < ?", (iso(t),))
    return JSONResponse(dict(access_token=access, token_type="Bearer", expires_in=ACCESS_HOURS * 3600, refresh_token=refresh, scope="meridian"),
                        headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


@router.post("/oauth/token")
async def token(request: Request):
    form = await form_of(request)
    conn = db.connect()
    try:
        client = client_auth(conn, request, form)
        if not client:
            return oauth_error("invalid_client", "Unknown app or wrong secret.", 401)
        grant = form.get("grant_type")
        if grant == "authorization_code":
            row = conn.execute("SELECT * FROM mcp_codes WHERE code_hash = ?", (hashed(form.get("code") or ""),)).fetchone()
            conn.execute("DELETE FROM mcp_codes WHERE code_hash = ?", (hashed(form.get("code") or ""),))  # a code works once
            conn.commit()
            verifier = form.get("code_verifier") or ""
            proof = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            if (not row or row["client_id"] != client["client_id"] or row["expires_at"] < iso(now())
                    or row["redirect_uri"] != form.get("redirect_uri") or not hmac.compare_digest(proof, row["challenge"])):
                return oauth_error("invalid_grant", "The code is wrong, used or expired.")
            out = issue(conn, client["client_id"], row["account_id"])
        elif grant == "refresh_token":
            h = hashed(form.get("refresh_token") or "")
            row = conn.execute("SELECT * FROM mcp_tokens WHERE token_hash = ? AND kind = 'refresh'", (h,)).fetchone()
            if not row or row["client_id"] != client["client_id"] or row["expires_at"] < iso(now()):
                return oauth_error("invalid_grant", "The refresh token is wrong or expired.")
            conn.execute("DELETE FROM mcp_tokens WHERE token_hash = ?", (h,))  # each refresh token works once
            out = issue(conn, client["client_id"], row["account_id"])
        else:
            return oauth_error("unsupported_grant_type", "Use authorization_code or refresh_token.")
        conn.commit()
        return out
    finally:
        conn.close()


@router.post("/oauth/revoke")
async def revoke(request: Request):
    form = await form_of(request)
    conn = db.connect()
    try:
        client = client_auth(conn, request, form)
        if client:
            conn.execute("DELETE FROM mcp_tokens WHERE token_hash = ? AND client_id = ?", (hashed(form.get("token") or ""), client["client_id"]))
            conn.commit()
    finally:
        conn.close()
    return Response(status_code=200)


def bearer(request):
    """The person behind the request's access token: (found, person). Person is None when sign-in is off."""
    head = request.headers.get("authorization", "")
    if not head.lower().startswith("bearer "):
        return False, None, None
    conn = db.connect()
    try:
        row = conn.execute("SELECT t.account_id, t.client_id, c.name AS app FROM mcp_tokens t JOIN mcp_clients c ON c.client_id = t.client_id "
                           "WHERE t.token_hash = ? AND t.kind = 'access' AND t.expires_at > ?", (hashed(head[7:].strip()), iso(now()))).fetchone()
        if not row:
            return False, None, None
        if row["account_id"] is None:
            return (not accounts.required(conn)), None, row
        person = conn.execute("SELECT id, name, email, role FROM accounts WHERE id = ?", (row["account_id"],)).fetchone()
        return bool(person), dict(person) if person else None, row
    finally:
        conn.close()


# ------------------------------------------------------------------------------- calling Meridian's own API

async def call_api(method, path, query=None, body=None, person=None):
    """Run one request through Meridian's API in this process, as `person`: the same checks as the screens."""
    from .api import app
    raw = json.dumps(body).encode() if body is not None else b""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method.upper(), "scheme": "http",
             "path": path, "raw_path": path.encode(), "root_path": "", "query_string": urlencode(query or {}, doseq=True).encode(),
             "headers": [(b"host", b"meridian"), (b"content-type", b"application/json"), (b"content-length", str(len(raw)).encode())],
             "client": ("127.0.0.1", 0), "server": ("meridian", 80), "meridian.person": person}
    done, status, chunks = asyncio.Event(), [0], []

    async def receive():
        if not done.is_set():
            done.set()
            return {"type": "http.request", "body": raw, "more_body": False}
        await asyncio.sleep(3600)  # nothing more to read; the app never waits here for a plain JSON reply

    async def send(message):
        if message["type"] == "http.response.start":
            status[0] = message["status"]
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    text = b"".join(chunks).decode("utf-8", "replace")
    try:
        return status[0], json.loads(text) if text else None
    except ValueError:
        return status[0], text[:2000]


def endpoints():
    """Every API route an assistant may use, with its inputs, from the API's own description."""
    from .api import app
    spec, out = app.openapi(), []
    schemas = spec.get("components", {}).get("schemas", {})
    for path, ops in sorted(spec["paths"].items()):
        if not path.startswith("/api/") or path.startswith(BLOCKED):
            continue
        for method, op in ops.items():
            e = dict(method=method.upper(), path=path, about=(op.get("description") or op.get("summary") or "").strip().split("\n")[0])
            params = [p["name"] + ("" if p.get("required") else "?") for p in op.get("parameters", []) if p.get("in") == "query"]
            if params:
                e["query"] = params
            ref = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("$ref", "")
            if ref:
                props = schemas.get(ref.split("/")[-1], {}).get("properties", {})
                e["body"] = {k: v.get("type") or "any" for k, v in props.items()}
            out.append(e)
    return out


# ------------------------------------------------------------------------------- tools

EVENT_CHANGES = """Change anything in Events. `what` picks the change; `data` holds its fields.
- event: create (no id) or edit (id) an event. data: name, kind (event type key from list_events.kinds), starts, ends (YYYY-MM-DD), city, venue,
  partner, booth, goal, budget, decision (Considering/Go/No-go), target_leads, target_qualified, target_meetings, target_pipeline,
  meetings_held, visitors, lessons; on create also start_from: "playbook" (default), "empty" or "event:<id>" (copy a past event).
  When editing, send every field you want to keep: fields left out are cleared.
- remove_event: id = event id.
- sources: event_id; data.sources = list of Zoho Lead Source values (from get_event.source_options). Each value belongs to one event.
- step: add (no id) or edit (id) a task. event_id; data: title, phase (plan/promote/live/follow), workstream, owner, due, status,
  done_when, note, critical (true/false), auto (rule key from get_event.auto_rules, or "" for off). Edit replaces every field.
- step_field: change one field of one task. id = task id; data: field (status, phase, due, title, owner, workstream), value.
- steps: many tasks at once. event_id; data.ids = task ids, then one of: field + value; shift = days (e.g. 7 or -3); delete = true.
- status: id = task id; data.status (Not started, In progress, Waiting on others, Done, Skipped).
- critical: id = task id; data.critical true/false.
- promo: promotion activity. id to edit; event_id; data: channel, what, day, owner, status.
- cost: cost line. id to edit; event_id; data: category, item, amount (actual), planned (budgeted), paid (true/false).
- creative: published post. id to edit; event_id; data: url, posted_on, caption, title, image.
- goal: custom goal. id to edit; event_id; data: name, target, actual.
- info: key detail. id to edit; event_id; data: label, value.
- targets: replace the target account list. event_id; data.text = lines "company, tier (1-3), domain".
- setup: event tabs. event_id; data: show_<tab> (true to show), name_<tab> (own name), ws_booth / ws_leads (workstream lists), new_workstreams (comma text).
  Tabs: overview, plan, promotion, content, booth, accounts, leads, budget, results. Send show_ for every tab to keep.
- playbook_step: standard plan task. id to edit; data: title, phase, workstream, owner, offset_days, done_when, critical, auto, kind_<type key> (true for the types it applies to).
- kind / remove_kind: event type. data: key (to rename or remove), label.
- remove_step, remove_promo, remove_cost, remove_creative, remove_goal, remove_info, remove_target, remove_playbook_step: id = item id.
Dates are YYYY-MM-DD. Read get_event first to find ids and current values."""

TOOLS = [
    dict(name="list_events", title="List events",
         description="All events with dates, stage, readiness, overdue tasks, leads, budget and ROI, plus the standard task plan (playbook) and event types.",
         inputSchema=dict(type="object", properties={}), annotations=dict(readOnlyHint=True)),
    dict(name="get_event", title="Get an event",
         description="One event in full: details, tasks (with ids, owners, due dates, status), promotion plan, posts, costs, goals, key details, "
                     "target accounts, Zoho results by Lead Source, follow-up speed, team members, and the allowed values for each field.",
         inputSchema=dict(type="object", properties=dict(event_id=dict(type="integer")), required=["event_id"]), annotations=dict(readOnlyHint=True)),
    dict(name="change_event", title="Change events", description=EVENT_CHANGES,
         inputSchema=dict(type="object", properties=dict(what=dict(type="string"), id=dict(type="integer"), event_id=dict(type="integer"), data=dict(type="object")),
                          required=["what"]), annotations=dict(destructiveHint=True)),
    dict(name="list_endpoints", title="List Meridian API",
         description="Every Meridian API endpoint outside Events (leads, pipeline, channels, ads, website, outbound, competitors, targets, alerts, "
                     "subscriptions, settings and more): method, path, query parameters and body fields. Use it to find what call_api can do.",
         inputSchema=dict(type="object", properties=dict(filter=dict(type="string", description="Only paths containing this text, e.g. leads"))),
         annotations=dict(readOnlyHint=True)),
    dict(name="call_api", title="Call Meridian API",
         description="Read or change anything in Meridian through its API, as the signed-in person. Find the path and fields with list_endpoints first. "
                     "Many reads take range (week, month, quarter, year, custom) with start and end (YYYY-MM-DD). Logins and passwords cannot be changed.",
         inputSchema=dict(type="object", properties=dict(method=dict(type="string", enum=["GET", "POST", "PUT", "PATCH", "DELETE"]),
                                                         path=dict(type="string", description="Starts with /api/"),
                                                         query=dict(type="object"), body=dict(type="object")), required=["method", "path"]),
         annotations=dict(destructiveHint=True)),
]


async def run_tool(name, args, person):
    if name == "list_events":
        return await call_api("GET", "/api/events", person=person)
    if name == "get_event":
        return await call_api("GET", "/api/events/{}".format(int(args.get("event_id") or 0)), person=person)
    if name == "change_event":
        body = dict(what=args.get("what"), id=args.get("id"), event_id=args.get("event_id"), data=args.get("data") or {})
        return await call_api("POST", "/api/events", body=body, person=person)
    if name == "list_endpoints":
        q = (args.get("filter") or "").lower()
        return 200, [e for e in endpoints() if q in e["path"].lower()]
    if name == "call_api":
        path = "/" + str(args.get("path") or "").lstrip("/")
        method = str(args.get("method") or "GET").upper()
        if not path.startswith("/api/") or ".." in path or path.startswith(BLOCKED):
            return 400, "This path cannot be used from an assistant. Use a path from list_endpoints."
        return await call_api(method, path, args.get("query"), args.get("body"), person=person)
    return 400, "Unknown tool."


def log(person, app, tool, args, status):
    conn = db.connect()
    try:
        conn.execute("INSERT INTO mcp_log (at, account_id, app, tool, detail, status) VALUES (?,?,?,?,?,?)",
                     (iso(now()), person["id"] if person else None, app, tool, json.dumps(args)[:500], status))
        conn.execute("DELETE FROM mcp_log WHERE at < ?", (iso(now() - timedelta(days=90)),))
        conn.commit()
    finally:
        conn.close()


async def answer(msg, person, token_row):
    """One JSON-RPC message: its reply, or None for a notification."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return dict(jsonrpc="2.0", id=msg.get("id") if isinstance(msg, dict) else None, error=dict(code=-32600, message="Invalid request"))
    method, rid, params = msg["method"], msg.get("id"), msg.get("params") or {}
    if rid is None:
        return None
    reply = lambda result: dict(jsonrpc="2.0", id=rid, result=result)
    if method == "initialize":
        asked = params.get("protocolVersion")
        return reply(dict(protocolVersion=asked if asked in PROTOCOLS else PROTOCOLS[0], capabilities=dict(tools=dict(listChanged=False)),
                          serverInfo=dict(name="meridian", title="Meridian", version="1.0"),
                          instructions="Meridian is the marketing team's workspace: events, leads from Zoho, pipeline, channels, ads, website and targets. "
                                       "For events use list_events, get_event and change_event. For everything else use list_endpoints, then call_api. "
                                       "Money is in the workspace currency. Changes are saved at once and recorded under the signed-in person."))
    if method == "ping":
        return reply({})
    if method == "tools/list":
        return reply(dict(tools=TOOLS))
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in {t["name"] for t in TOOLS}:
            return dict(jsonrpc="2.0", id=rid, error=dict(code=-32602, message="Unknown tool: {}".format(name)))
        try:
            status, data = await run_tool(name, args, person)
        except (TypeError, ValueError) as err:
            status, data = 400, str(err)
        log(person, token_row["app"], name, args, status)
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
        if status >= 400 and isinstance(data, dict) and "detail" in data:
            text = str(data["detail"])
        return reply(dict(content=[dict(type="text", text=text)], isError=status >= 400))
    return dict(jsonrpc="2.0", id=rid, error=dict(code=-32601, message="Method not found: {}".format(method)))


@router.post("/mcp")
async def mcp(request: Request):
    found, person, token_row = bearer(request)
    if not found:
        return JSONResponse(dict(error="invalid_token", error_description="Sign in to Meridian to use this connector."), status_code=401,
                            headers={"WWW-Authenticate": 'Bearer resource_metadata="{}/.well-known/oauth-protected-resource"'.format(base(request))})
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(dict(jsonrpc="2.0", id=None, error=dict(code=-32700, message="Parse error")), status_code=400)
    if isinstance(body, list):
        replies = [r for r in [await answer(m, person, token_row) for m in body] if r]
        return JSONResponse(replies) if replies else Response(status_code=202)
    reply = await answer(body, person, token_row)
    return JSONResponse(reply) if reply else Response(status_code=202)


@router.get("/mcp")
@router.delete("/mcp")
def mcp_other():
    return Response(status_code=405, headers={"Allow": "POST"})


# ------------------------------------------------------------------------------- Settings: connected apps

def connections(conn):
    """Each app a person has connected, with when it was last used."""
    rows = conn.execute("""SELECT c.client_id, c.name AS app, t.account_id, a.name AS person, MIN(t.created_at) AS since,
        (SELECT MAX(at) FROM mcp_log l WHERE l.app = c.name AND l.account_id IS t.account_id) AS last_used
        FROM mcp_tokens t JOIN mcp_clients c ON c.client_id = t.client_id LEFT JOIN accounts a ON a.id = t.account_id
        WHERE t.kind = 'refresh' AND t.expires_at > ? GROUP BY c.client_id, t.account_id ORDER BY since DESC""", (iso(now()),)).fetchall()
    return [dict(r) for r in rows]


def disconnect(conn, client_id, account_id):
    conn.execute("DELETE FROM mcp_tokens WHERE client_id = ? AND account_id IS ?", (client_id, account_id))

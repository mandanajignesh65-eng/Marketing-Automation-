"""Zoho CRM connection: pulls leads and deals through Zoho's API.

    python -m meridian.zoho connect     one-time setup: saves credentials, then runs the first full sync
    python -m meridian.zoho sync        fetch what changed since the last sync (add --full for everything)
    python -m meridian.zoho fields      show how Zoho's fields, statuses and lead sources are being read

Credentials come from a Zoho "Self Client" and are kept in .env beside this app. How Zoho's fields
map onto Meridian's is kept in data/zoho_mapping.json, which can be edited by hand.
"""

import getpass
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import config, db, ingest, money
from .periods import iso

SCOPES = "ZohoCRM.modules.leads.READ,ZohoCRM.modules.deals.READ,ZohoCRM.settings.fields.READ"
API = "/crm/v6"
MAPPING_FILE = config.DATA_DIR / "zoho_mapping.json"

MAPPING_VERSION = 2
REFETCH = "zoho_refetch"  # setting: "1" when the next sync must fetch everything again

DEFAULT_MAPPING = {
    # Meridian field -> Zoho API name, or a list of names to try in order (accounts differ).
    # check_fields() settles each on the first one that exists; a field Zoho does not have becomes null.
    "fields": {
        "name": "Full_Name", "first_name": "First_Name", "last_name": "Last_Name",
        "title": ["Designation", "Contact_Designation", "Title"],
        "company": "Company", "email": "Email", "owner": "Owner", "status": "Lead_Status", "lead_source": "Lead_Source",
        "employees": "No_of_Employees", "company_size": ["Company_Size", "Company_Type"], "revenue": "Annual_Revenue",
        "industry": "Industry", "city": "City", "state": "State", "website": "Website",
        "converted": ["Converted__s"], "converted_deal": ["Converted_Deal"],
        "utm_source": None, "utm_medium": None, "utm_campaign": None,
    },
    "deal_fields": {"lead_source": ["Lead_Source", "Lead_Source2"], "exchange_rate": ["Exchange_Rate"]},
    # Zoho lead status -> one of: New, Contacted, Qualified, Meeting booked, Unqualified.
    # A status missing here is placed by its wording (see place_status).
    "status": {
        "Not Contacted": "New", "Attempted to Contact": "Contacted", "Contacted": "Contacted",
        "Contact in Future": "Contacted", "Pre-Qualified": "Qualified", "Qualified": "Qualified",
        "Not Qualified": "Unqualified", "Junk Lead": "Unqualified", "Lost Lead": "Unqualified",
    },
    # Zoho deal stage -> won or lost. Anything else is an open deal. Stages not listed are placed by
    # their wording ("won", "lost").
    "deal_stages": {"Closed Won": "won", "Closed Lost": "lost"},
    # Lead source -> channel id, for sources whose wording does not give the channel away. These fill in
    # sources that have no channel yet; a channel picked in Settings is never overwritten.
    "lead_source_channels": {},
    "exclude_deal_stages": [],
    # Leads with these sources are left out: sales activity rather than marketing, or test records.
    # "(no lead source)" stands for a blank source. Settings changes this list too.
    "exclude_lead_sources": ["Cold Call"],
}


class ZohoError(Exception):
    pass


# ------------------------------------------------------------------------------- credentials and HTTP

def credentials():
    c = {k: config.setting(k) for k in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN")}
    return c if all(c.values()) else None


def configured():
    return credentials() is not None


def accounts_url():
    return config.setting("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.{}".format(config.setting("ZOHO_DC", "in")))


def request(method, url, params=None, headers=None):
    """One HTTP call. Returns (status, parsed JSON or None). Zoho answers 204/304 with no body."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            body = res.read()
            return res.status, json.loads(body) if body else None
    except urllib.error.HTTPError as err:
        if err.code == 304:
            return 304, None
        body = err.read()
        try:
            detail = json.loads(body)
        except ValueError:
            detail = body.decode("utf-8", "replace")[:200]
        raise ZohoError("Zoho answered {} for {}: {}".format(err.code, url.split("?")[0], detail))
    except urllib.error.URLError as err:
        raise ZohoError("Could not reach Zoho: {}".format(err.reason))


def token_call(params):
    _, data = request("POST", accounts_url() + "/oauth/v2/token", params)
    if not data or data.get("error"):
        raise ZohoError("Zoho refused the credentials ({}). Run ./connect-zoho.sh in Terminal to connect again."
                        .format((data or {}).get("error", "no response")))
    return data


def exchange_grant(client_id, client_secret, code):
    """Swap a one-time grant code for a long-lived refresh token."""
    data = token_call(dict(grant_type="authorization_code", client_id=client_id, client_secret=client_secret, code=code))
    if not data.get("refresh_token"):
        raise ZohoError("Zoho did not return a refresh token. Generate a new code and try again.")
    return data["refresh_token"]


def session():
    """(request headers, API base URL) for this sync."""
    c = credentials()
    if not c:
        raise ZohoError("Zoho CRM is not connected yet. Run ./connect-zoho.sh in Terminal.")
    data = token_call(dict(grant_type="refresh_token", client_id=c["ZOHO_CLIENT_ID"],
                           client_secret=c["ZOHO_CLIENT_SECRET"], refresh_token=c["ZOHO_REFRESH_TOKEN"]))
    base = data.get("api_domain") or "https://www.zohoapis.{}".format(config.setting("ZOHO_DC", "in"))
    return {"Authorization": "Zoho-oauthtoken " + data["access_token"]}, base + API


def records(auth, base, module, fields, since=None, extra=None):
    """Every record of a module, optionally only those modified since an ISO timestamp."""
    params = dict(fields=",".join(fields), per_page=200, page=1, **(extra or {}))
    headers = dict(auth, **({"If-Modified-Since": since} if since else {}))
    while True:
        status, data = request("GET", "{}/{}".format(base, module), params, headers)
        if status in (204, 304) or not data:
            return
        for rec in data.get("data", []):
            yield rec
        info = data.get("info") or {}
        if not info.get("more_records"):
            return
        if info.get("next_page_token"):  # required beyond the first 2,000 records
            params.pop("page", None)
            params["page_token"] = info["next_page_token"]
        else:
            params["page"] = params.get("page", 1) + 1


def module_fields(auth, base, module):
    _, data = request("GET", base + "/settings/fields", dict(module=module), auth)
    return (data or {}).get("fields", [])


# ------------------------------------------------------------------------------- mapping

def load_mapping():
    mapping = json.loads(json.dumps(DEFAULT_MAPPING))
    if MAPPING_FILE.exists():
        saved = json.loads(MAPPING_FILE.read_text())
        current = saved.get("version") == MAPPING_VERSION
        for section in ("fields", "deal_fields"):
            # an older file's nulls may be fields this version knows other names for, so those are looked up again
            mapping[section].update({k: v for k, v in saved.get(section, {}).items() if v or current})
        for section in ("status", "deal_stages", "lead_source_channels"):
            mapping[section].update(saved.get(section, {}))
        for key in ("exclude_lead_sources", "exclude_deal_stages"):
            if key in saved:
                mapping[key] = saved[key]
        mapping["checked_fields"] = bool(saved.get("checked_fields")) and current
    return mapping


def save_mapping(mapping):
    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_FILE.write_text(json.dumps(dict(mapping, version=MAPPING_VERSION), indent=2, ensure_ascii=False) + "\n")


def remember(source, channel_id=None, excluded=False):
    """Record a choice made in Settings in the mapping file as well, so it survives a rebuilt database."""
    mapping, low = load_mapping(), source.lower()
    mapping["exclude_lead_sources"] = [x for x in mapping["exclude_lead_sources"] if x.lower() != low] + ([source] if excluded else [])
    mapping["lead_source_channels"] = {k: v for k, v in mapping["lead_source_channels"].items() if k.lower() != low}
    if channel_id and not excluded:
        mapping["lead_source_channels"][source] = channel_id
    save_mapping(mapping)


def settle(section, fields):
    """Reduce each mapping entry to the one API name this account has, or None."""
    names = {f.get("api_name") for f in fields}
    for key, wanted in list(section.items()):
        options = wanted if isinstance(wanted, list) else [wanted] if wanted else []
        section[key] = next((name for name in options if name in names), None)


def check_fields(mapping, lead_fields, deal_fields):
    """Fit the mapping to this Zoho account: find the tracking-tag fields and settle on fields that exist."""
    for key in ("utm_source", "utm_medium", "utm_campaign"):
        if mapping["fields"].get(key):
            continue
        want = key.split("_")[1]
        for f in lead_fields:
            text = "{} {}".format(f.get("api_name", ""), f.get("field_label", "")).lower().replace("_", " ")
            if "utm" in text and want in text:
                mapping["fields"][key] = f["api_name"]
                break
    settle(mapping["fields"], lead_fields)
    settle(mapping["deal_fields"], deal_fields)
    mapping["checked_fields"] = True
    return mapping


def tidy(text):
    """Lead-source values as people see them: stray HTML and entities from old imports removed."""
    if not isinstance(text, str):
        return text
    text = re.sub(r"<[^>]*>?", " ", html.unescape(text))
    return re.sub(r"\s+", " ", text).strip() or None


def place_status(raw, mapping):
    """Meridian status for a Zoho lead status. Returns (status, whether it was an explicit mapping)."""
    if not raw:
        return "New", True
    if raw in mapping["status"]:
        return mapping["status"][raw], True
    text = raw.lower()
    if any(k in text for k in ("junk", "lost", "not qualified", "unqualified", "disqualif", "invalid", "spam", "not interested",
                               "duplicate", "competitor", "icebox", "ice box")):
        return "Unqualified", False
    if any(k in text for k in ("meeting", "demo", "appointment")):
        return "Meeting booked", False
    if "qualif" in text or "convert" in text or "deal" in text:
        return "Qualified", False
    if "not contacted" in text or "untouched" in text or text in ("new", "open", "fresh", "new lead"):
        return "New", False
    if any(k in text for k in ("contact", "attempt", "follow", "progress", "working", "nurtur", "call", "connect", "respon", "interested", "warm")):
        return "Contacted", False
    return "New", False


def local(ts):
    """Zoho timestamp ('2026-10-01T15:04:05+05:30') as local time in Meridian's format."""
    if not ts:
        return None
    try:
        return iso(datetime.fromisoformat(ts).astimezone().replace(tzinfo=None))
    except ValueError:
        return None


def lead_payload(rec, mapping, loose_statuses):
    """A Zoho lead record as the dictionary ingest.upsert_lead expects, or None when it has no name to show."""
    f = mapping["fields"]

    def get(key):
        value = rec.get(f[key]) if f.get(key) else None
        return value.get("name") if isinstance(value, dict) else value

    source = tidy(get("lead_source"))
    name = get("name") or " ".join(x for x in (get("first_name"), get("last_name")) if x) or get("company") or get("email")
    if not name:
        return None
    converted = bool(get("converted")) or bool(rec.get("$converted"))
    status, exact = ("Qualified", True) if converted else place_status(get("status"), mapping)
    if not exact:
        loose_statuses[get("status")] = status
    deal = rec.get(f["converted_deal"]) if f.get("converted_deal") else (rec.get("$converted_detail") or {}).get("deal")
    size, industry = get("company_size"), get("industry")
    blank = {"to be updated", "null", "-none-", "none", "n/a", "na", ""}  # placeholders people leave in picklists
    return dict(
        id=rec["id"], name=name, title=get("title"), company=get("company"), email=get("email"), owner=get("owner"),
        status=status, lead_source=source, utm_source=get("utm_source"), utm_medium=get("utm_medium"),
        utm_campaign=get("utm_campaign"), employees=get("employees"), revenue=get("revenue"),
        industry=industry if industry and industry.strip().lower() not in blank else None,
        company_size=size if size and size.strip().lower() not in blank else None,
        hq=", ".join(x for x in (get("city"), get("state")) if x) or None, website=get("website"),
        created_at=local(rec.get("Created_Time")), modified_at=local(rec.get("Modified_Time")),
        activity_at=local(rec.get("Last_Activity_Time")), deal_zoho_id=deal.get("id") if isinstance(deal, dict) else deal,
        enriched_via="Zoho CRM",
    )


def place_stage(raw, mapping):
    """open, won or lost for a Zoho deal stage."""
    if raw in mapping["deal_stages"]:
        return mapping["deal_stages"][raw]
    text = (raw or "").lower()
    return "won" if "won" in text else "lost" if "lost" in text else "open"


# ------------------------------------------------------------------------------- sync

def sync_deals(conn, auth, base, since, mapping, excluded=()):
    count = 0
    source_field, rate_field = mapping["deal_fields"].get("lead_source"), mapping["deal_fields"].get("exchange_rate")
    fields = ["Deal_Name", "Amount", "Stage", "Closing_Date", "Created_Time", "Modified_Time"] + [x for x in (source_field, rate_field) if x]
    skipped = {s.lower() for s in mapping["exclude_deal_stages"]}
    today = datetime.now().date().isoformat()
    for rec in records(auth, base, "Deals", fields, since):
        if (rec.get("Stage") or "").lower() in skipped:
            conn.execute("DELETE FROM deals WHERE zoho_id = ?", (rec["id"],))
            continue
        stage = place_stage(rec.get("Stage"), mapping)
        closed = None
        if stage != "open":  # the closing date is a forecast until the deal closes, so a future one is not trusted
            closing = rec.get("Closing_Date")
            closed = closing + "T12:00:00" if closing and closing <= today else local(rec.get("Modified_Time"))
        source = tidy(rec.get(source_field)) if source_field else None
        lead = conn.execute("SELECT id, channel_id FROM leads WHERE deal_zoho_id = ?", (rec["id"],)).fetchone()
        if not lead and (ingest.is_left_out(excluded, source) or conn.execute(
                "SELECT 1 FROM left_out_leads WHERE deal_zoho_id = ?", (rec["id"],)).fetchone()):
            conn.execute("DELETE FROM deals WHERE zoho_id = ?", (rec["id"],))  # sales activity, or it came from a left-out lead
            continue
        if lead:
            lead_id, channel = lead["id"], lead["channel_id"]
        else:  # a deal created directly, without a lead behind it
            lead_id, channel = None, ingest.classify(conn, None, None, source)
        # amounts are stored in the home currency; Zoho's rate is "one home unit in the deal's currency"
        rate = float(rec.get(rate_field) or 1) if rate_field else 1
        amount = int(round(float(rec.get("Amount") or 0) / (rate or 1)))
        conn.execute(
            "INSERT INTO deals (zoho_id, name, lead_id, channel_id, amount, stage, created_at, closed_at, lead_source) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (zoho_id) DO UPDATE SET name = excluded.name, lead_id = excluded.lead_id, channel_id = excluded.channel_id, "
            "amount = excluded.amount, stage = excluded.stage, closed_at = excluded.closed_at, lead_source = excluded.lead_source",
            (rec["id"], rec.get("Deal_Name"), lead_id, channel, amount, stage,
             local(rec.get("Created_Time")) or iso(datetime.now()), closed, source))
        count += 1
    return count


def sync(conn, now, full=False):
    """Pull leads and deals from Zoho into the database. Returns a summary of what changed."""
    if db.is_demo(conn):
        raise ZohoError("This is the sample database. Real Zoho leads go into the live one; run ./connect-zoho.sh.")
    started = datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()
    full = full or db.get_setting(conn, REFETCH) == "1"  # a source was brought back, so its leads must be fetched again
    since = None if full else db.get_setting(conn, "zoho_synced_at")
    try:
        auth, base = session()
        mapping = load_mapping()
        if not mapping.get("checked_fields"):
            save_mapping(check_fields(mapping, module_fields(auth, base, "Leads"), module_fields(auth, base, "Deals")))

        known = {r["id"] for r in conn.execute("SELECT id FROM channels")}
        for source, channel in mapping["lead_source_channels"].items():
            if channel in known:
                conn.execute("INSERT INTO utm_map (source, medium, channel_id) VALUES (?, ?, ?) ON CONFLICT (source, medium) "
                             "DO UPDATE SET channel_id = excluded.channel_id WHERE utm_map.channel_id IS NULL",
                             (source, ingest.LEAD_SOURCE, channel))

        for source in mapping["exclude_lead_sources"]:
            conn.execute("INSERT INTO utm_map (source, medium, excluded) VALUES (?, ?, 1) ON CONFLICT (source, medium) "
                         "DO UPDATE SET excluded = 1, channel_id = NULL", (source, ingest.LEAD_SOURCE))
        excluded = ingest.excluded_sources(conn)
        if full:
            conn.execute("DELETE FROM left_out_leads")  # counted afresh below

        wanted = sorted({v for v in mapping["fields"].values() if v} | {"Created_Time", "Modified_Time", "Last_Activity_Time"})
        summary = dict(leads=0, created=0, updated=0, left_out=0, deals=0, loose_statuses={})
        for rec in records(auth, base, "Leads", wanted, since, dict(converted="both")):
            summary["leads"] += 1
            payload = lead_payload(rec, mapping, summary["loose_statuses"])
            if payload is None:
                continue
            if ingest.is_left_out(excluded, payload["lead_source"], bool(payload["utm_source"] or payload["utm_medium"])):
                ingest.note_left_out(conn, payload["id"], payload["lead_source"], payload["deal_zoho_id"])
                summary["left_out"] += 1
                continue
            _, created = ingest.upsert_lead(conn, now, payload)
            summary["created" if created else "updated"] += 1
            owner = rec.get(mapping["fields"]["owner"]) if mapping["fields"].get("owner") else None
            if isinstance(owner, dict) and owner.get("name") and owner.get("email"):
                if not conn.execute("SELECT 1 FROM users WHERE name = ?", (owner["name"],)).fetchone():
                    conn.execute("INSERT INTO users (name, team, role, email) VALUES (?, 'Sales', 'Lead owner', ?)",
                                 (owner["name"], owner["email"]))
            if summary["leads"] % 500 == 0:
                conn.commit()
        summary["deals"] = sync_deals(conn, auth, base, since, mapping, excluded)
        ingest.reapply_sources(conn)
    except ZohoError as err:
        conn.rollback()
        if "refused the credentials" in str(err):  # needs reconnecting; anything else may pass on the next run
            conn.execute("UPDATE sources SET status = 'disconnected', note = ? WHERE key = 'zoho'", (str(err)[:300],))
        else:
            conn.execute("UPDATE sources SET note = ? WHERE key = 'zoho'", (str(err)[:300],))
        conn.commit()
        raise
    summary["unmapped_sources"] = [r["source"] for r in conn.execute(
        "SELECT source FROM utm_map WHERE channel_id IS NULL AND excluded = 0 ORDER BY source")]
    conn.execute("UPDATE sources SET status = 'connected', last_sync_at = ?, note = NULL WHERE key = 'zoho'", (iso(now),))
    db.set_setting(conn, "zoho_synced_at", started)
    db.set_setting(conn, REFETCH, "0")
    conn.commit()
    return summary


def describe(summary):
    """One line for the app's toast or the terminal."""
    text = "{} new, {} updated".format(summary["created"], summary["updated"])
    if summary["left_out"]:
        text += ", {} left out as not marketing".format(summary["left_out"])
    if summary["deals"]:
        text += ", {} deals".format(summary["deals"])
    return text


# ------------------------------------------------------------------------------- command line

def write_env(values):
    kept = [line for line in (config.ENV_FILE.read_text().splitlines() if config.ENV_FILE.exists() else [])
            if line.split("=", 1)[0].strip() not in values]
    config.ENV_FILE.write_text("\n".join(kept + ["{}={}".format(k, v) for k, v in values.items()]) + "\n")
    os.chmod(str(config.ENV_FILE), 0o600)


def live_database():
    """Open the live database, creating an empty one the first time."""
    from . import seed
    path = config.db_path() if os.environ.get("MERIDIAN_DB") else config.LIVE_DB
    if not path.exists():
        seed.run(empty=True)
    conn = db.connect(path)
    db.upgrade(conn)
    seed.add_live_channels(conn)
    money.load(conn)
    return conn


def report(summary):
    print("\nSynced with Zoho CRM:", describe(summary))
    if summary["loose_statuses"]:
        print("\nLead statuses placed by their wording (edit \"status\" in {} to change):".format(MAPPING_FILE))
        for raw, status in sorted(summary["loose_statuses"].items()):
            print("  {:<32} -> {}".format(raw, status))
    if summary["unmapped_sources"]:
        print("\nLead sources and tags not yet tied to a channel (map them in Settings):")
        print("  " + ", ".join(summary["unmapped_sources"]))


def cmd_connect():
    dc = config.setting("ZOHO_DC", "in")
    print(__doc__.split("\n\n")[0])
    print("""
1. Open https://api-console.zoho.{dc} and sign in with the Zoho account that can see your CRM leads.
2. Click "Add Client", choose "Self Client", then "Create".
3. On the "Client Secret" tab, copy the Client ID and Client Secret.
4. On the "Generate Code" tab, paste this as the scope:

     {scopes}

   Set the duration to 10 minutes, type any description, click "Create", and pick your CRM organisation.
5. Copy the code it shows and paste the three values below. The code works once and expires in 10 minutes.
""".format(dc=dc, scopes=SCOPES))
    client_id = input("Client ID: ").strip()
    client_secret = getpass.getpass("Client Secret (hidden as you paste): ").strip()
    code = getpass.getpass("Generated code (hidden as you paste): ").strip()
    if not (client_id and client_secret and code):
        sys.exit("All three values are needed. Nothing was saved.")
    refresh = exchange_grant(client_id, client_secret, code)
    write_env(dict(ZOHO_DC=dc, ZOHO_CLIENT_ID=client_id, ZOHO_CLIENT_SECRET=client_secret, ZOHO_REFRESH_TOKEN=refresh))
    print("\nConnected. Credentials saved to {} (readable only by you).".format(config.ENV_FILE))
    print("Fetching every lead and deal. This can take a few minutes for a large CRM...")
    conn = live_database()
    report(sync(conn, db.now(conn), full=True))
    conn.close()
    print("\nOpen the app and refresh the page to see your leads.")


def cmd_sync(full):
    conn = live_database()
    report(sync(conn, db.now(conn), full=full))
    conn.close()


def cmd_fields():
    auth, base = session()
    fields = module_fields(auth, base, "Leads")
    mapping = check_fields(load_mapping(), fields, module_fields(auth, base, "Deals"))
    by_name = {f["api_name"]: f for f in fields}
    print("How Meridian reads the Leads module:\n")
    for key, api_name in mapping["fields"].items():
        label = by_name[api_name]["field_label"] if api_name in by_name else None
        print("  {:<13} <- {}".format(key, "{} ({})".format(label, api_name) if api_name else "not found in Zoho"))
    for key, title in (("status", "Lead statuses"), ("lead_source", "Lead sources")):
        field = by_name.get(mapping["fields"].get(key) or "")
        values = [v.get("display_value") for v in (field or {}).get("pick_list_values", []) if v.get("display_value") not in (None, "-None-")]
        print("\n{}:".format(title))
        for value in values:
            if key == "status":
                print("  {:<32} -> {}".format(value, place_status(value, mapping)[0]))
            else:
                left_out = value.lower() in {s.lower() for s in mapping["exclude_lead_sources"]}
                print("  {:<32} {}".format(value, "left out (not marketing)" if left_out else ""))
    print("\nAll Leads fields (label: API name):")
    for f in sorted(fields, key=lambda f: f.get("field_label", "")):
        print("  {}: {}".format(f.get("field_label"), f.get("api_name")))


def main(argv):
    command = argv[0] if argv else ""
    try:
        if command == "connect":
            cmd_connect()
        elif command == "sync":
            cmd_sync("--full" in argv)
        elif command == "fields":
            cmd_fields()
        else:
            sys.exit(__doc__)
    except ZohoError as err:
        sys.exit("\n" + str(err))


if __name__ == "__main__":
    main(sys.argv[1:])

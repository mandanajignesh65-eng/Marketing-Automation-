"""Outbound tools: brings in Apollo email sequences and HeyReach LinkedIn campaigns with their daily counts.

    python -m meridian.outbound connect apollo|heyreach   save an API key, then bring the campaigns in
    python -m meridian.outbound sync [apollo|heyreach]    bring in the latest counts now
    python -m meridian.outbound status                    what is connected and how much it holds

Both connections only read. HeyReach reports each campaign day by day, so its history comes in with the dates
it happened on. Apollo reports one running total per sequence, so Meridian remembers the total at each sync and
books the increase on the day it sees it: Apollo activity from before the connection shows as an all-time
figure on the sequence, not inside a date range. Neither tool is asked for contact names, emails or messages.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from . import config, db
from .periods import iso

APOLLO_URL = "https://api.apollo.io/api/v1"
HEYREACH_URL = "https://api.heyreach.io/api/public"
KEYS = {"apollo": "APOLLO_API_KEY", "heyreach": "HEYREACH_API_KEY"}
NAMES = {"apollo": "Apollo", "heyreach": "HeyReach"}
EVERY_HOURS = 3
HEYREACH_HISTORY_DAYS = 365   # how far back the first HeyReach sync reaches
HEYREACH_RELOOK_DAYS = 14     # later syncs re-read this many days: acceptances and replies arrive late
HEYREACH_CHUNK_DAYS = 90
COUNTS = ("sent", "opened", "replied", "meetings")


class OutboundError(Exception):
    """A problem the person running the sync can act on."""


def api_key(tool):
    return config.setting(KEYS[tool])


def slots(tool):
    return [KEYS[tool]] + ["{}_{}".format(KEYS[tool], n) for n in range(2, 10)]


def accounts(tool):
    """Every saved account of a tool as (key, label): the first key, then KEY_2, KEY_3 and so on."""
    return [(config.setting(name), config.setting(name.replace("_API_KEY", "_LABEL"))) for name in slots(tool) if config.setting(name)]


def configured(tool=None):
    return bool(api_key(tool)) if tool else any(api_key(t) for t in KEYS)


def call(tool, method, url, body=None, key=None):
    headers = {"X-Api-Key": key or api_key(tool), "Accept": "application/json", "Content-Type": "application/json",
               "User-Agent": "Meridian/1.0"}
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                raw = res.read()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < 3:  # asked too quickly: wait and ask again
                time.sleep(20 * (attempt + 1))
                continue
            if err.code in (401, 403):
                hint = (" Apollo needs a master API key for sequence figures: when creating the key, switch on \"Set as master key\"."
                        if tool == "apollo" else "")
                raise OutboundError("{} did not accept the API key.{}".format(NAMES[tool], hint))
            raise OutboundError("{} answered with an error ({}).".format(NAMES[tool], err.code))
        except (urllib.error.URLError, OSError, ValueError) as err:
            raise OutboundError("Could not reach {}: {}".format(NAMES[tool], getattr(err, "reason", err)))


# ------------------------------------------------------------------------------- shared

def campaign(conn, tool, ext_id, name, detail=None):
    """The local row for one of the tool's campaigns, created the first time it is seen."""
    row = conn.execute("SELECT * FROM outbound_campaigns WHERE channel_id = ? AND ext_id = ?", (tool, str(ext_id))).fetchone()
    if row:
        conn.execute("UPDATE outbound_campaigns SET name = ?, detail = COALESCE(?, detail) WHERE id = ?", (name, detail, row["id"]))
        return row["id"], row
    cid = conn.execute("INSERT INTO outbound_campaigns (channel_id, name, detail, ext_id) VALUES (?,?,?,?)",
                       (tool, name, detail, str(ext_id))).lastrowid
    return cid, None


def mark(conn, tool, now, status="connected", note=None):
    conn.execute("UPDATE sources SET status = ?, last_sync_at = COALESCE(?, last_sync_at), note = ? WHERE key = ?",
                 (status, iso(now) if status == "connected" else None, note, tool))


def number(value):
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


# ------------------------------------------------------------------------------- Apollo

def apollo_sequences(key=None):
    out, page = [], 1
    while True:
        url = "{}/emailer_campaigns/search?{}".format(APOLLO_URL, urllib.parse.urlencode(dict(page=page, per_page=100)))
        data = call("apollo", "POST", url, {}, key)
        rows = data.get("emailer_campaigns") or []
        out += rows
        pages = number((data.get("pagination") or {}).get("total_pages"))
        if not rows or page >= max(pages, 1) or page >= 50:
            return out
        page += 1


def sync_apollo(conn, now):
    """Each sequence's running totals; the increase since the last sync is booked on today."""
    today, seen, added = now.date().isoformat(), 0, 0
    sequences = [(label, seq) for key, label in accounts("apollo") for seq in apollo_sequences(key)]
    for label, seq in sequences:
        if not seq.get("id") or seq.get("loaded_stats") is False:  # Apollo sometimes answers before it has counted: wait for real figures
            continue
        totals = [number(seq.get(f)) for f in ("unique_delivered", "unique_opened", "unique_replied", "unique_demoed")]
        steps = number(seq.get("num_steps"))
        detail = " · ".join(filter(None, [label, "{} step{}".format(steps, "" if steps == 1 else "s") if steps else "",
                                          "archived" if seq.get("archived") else ("" if seq.get("active") else "paused"),
                                          "{:,} sent all-time".format(totals[0])]))
        cid, known = campaign(conn, "apollo", seq["id"], seq.get("name") or "Untitled sequence", detail)
        seen += 1
        if known is not None and known["lifetime"]:
            before = json.loads(known["lifetime"])
            gain = [max(new - old, 0) for new, old in zip(totals, before)]
            if any(gain):
                conn.execute(
                    "INSERT INTO outbound_daily (date, campaign_id, sent, opened, replied, meetings) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT (date, campaign_id) DO UPDATE SET sent = sent + excluded.sent, opened = opened + excluded.opened, "
                    "replied = replied + excluded.replied, meetings = meetings + excluded.meetings", [today, cid] + gain)
                added += gain[0]
        conn.execute("UPDATE outbound_campaigns SET lifetime = ? WHERE id = ?", (json.dumps(totals), cid))
    mark(conn, "apollo", now)
    return dict(tool="apollo", campaigns=seen, sent=added)


# ------------------------------------------------------------------------------- HeyReach

def heyreach_campaigns(key=None):
    out, offset = [], 0
    while True:
        data = call("heyreach", "POST", HEYREACH_URL + "/campaign/GetAll", dict(offset=offset, limit=100), key)
        rows = data.get("items") or []
        out += rows
        offset += len(rows)
        if not rows or offset >= number(data.get("totalCount")) or offset >= 5000:
            return out


def sync_heyreach(conn, now):
    """Every campaign's day-by-day counts, re-read for recent days because acceptances and replies arrive late."""
    last = conn.execute("SELECT last_sync_at FROM sources WHERE key = 'heyreach'").fetchone()
    first_time = not (last and last["last_sync_at"]) or not conn.execute(
        "SELECT 1 FROM outbound_campaigns WHERE channel_id = 'heyreach' LIMIT 1").fetchone()
    start = now.date() - timedelta(days=HEYREACH_HISTORY_DAYS if first_time else HEYREACH_RELOOK_DAYS)
    ids = {}
    for c in heyreach_campaigns():
        if c.get("id") is None:
            continue
        status = str(c.get("status") or "").replace("_", " ").lower()
        detail = " · ".join(filter(None, [c.get("linkedInUserListName") or "", status]))
        ids[str(c["id"])] = campaign(conn, "heyreach", c["id"], c.get("name") or "Untitled campaign", detail or None)[0]
    rows, day = {}, start
    while day <= now.date():
        until = min(day + timedelta(days=HEYREACH_CHUNK_DAYS - 1), now.date())
        data = call("heyreach", "POST", HEYREACH_URL + "/stats/GetOverallStatsByCampaign", dict(
            accountIds=[], campaignIds=[], startDate=day.isoformat() + "T00:00:00.000Z", endDate=until.isoformat() + "T23:59:59.999Z"))
        for stamp, entries in (data.get("byDayStats") or {}).items():
            for e in entries or []:
                ext = str(e.get("campaignId"))
                if ext not in ids:  # a campaign since deleted in HeyReach still has its history
                    ids[ext] = campaign(conn, "heyreach", ext, e.get("campaignName") or "Deleted campaign", "deleted")[0]
                counts = (number(e.get("connectionsSent")), number(e.get("connectionsAccepted")),
                          number(e.get("totalMessageReplies")) + number(e.get("totalInmailReplies")), 0)
                if any(counts):
                    rows[(stamp[:10], ids[ext])] = counts
        day = until + timedelta(days=1)
    conn.execute("DELETE FROM outbound_daily WHERE date >= ? AND campaign_id IN (SELECT id FROM outbound_campaigns WHERE channel_id = 'heyreach')",
                 (start.isoformat(),))
    conn.executemany("INSERT INTO outbound_daily (date, campaign_id, sent, opened, replied, meetings) VALUES (?,?,?,?,?,?)",
                     [k + v for k, v in rows.items()])
    mark(conn, "heyreach", now)
    return dict(tool="heyreach", campaigns=len(ids), sent=sum(v[0] for v in rows.values()))


# ------------------------------------------------------------------------------- running

SYNCS = {"apollo": sync_apollo, "heyreach": sync_heyreach}


def sync(conn, now, tool):
    if not configured(tool):
        raise OutboundError("{} is not connected. Run ./connect-{}.sh in Terminal.".format(NAMES[tool], tool))
    try:
        summary = SYNCS[tool](conn, now)
    except OutboundError as err:
        conn.rollback()
        mark(conn, tool, now, "disconnected", str(err))
        conn.commit()
        raise
    conn.commit()
    return summary


def due(conn, now, tool):
    row = conn.execute("SELECT status, last_sync_at FROM sources WHERE key = ?", (tool,)).fetchone()
    if row and row["status"] == "disconnected":  # the last try failed: wait for "Reconnect" in Settings, do not keep knocking
        return False
    return not row or not row["last_sync_at"] or now - datetime.fromisoformat(row["last_sync_at"]) >= timedelta(hours=EVERY_HOURS)


def describe(summary):
    name, n = NAMES[summary["tool"]], summary["campaigns"]
    kind = ("sequence" if summary["tool"] == "apollo" else "campaign") + ("" if n == 1 else "s")
    if summary["tool"] == "apollo":
        return "{} {:,} {}, {:,} new emails since the last sync".format(name, n, kind, summary["sent"])
    return "{} {:,} {}, {:,} connection requests in the days read".format(name, n, kind, summary["sent"])


# ------------------------------------------------------------------------------- command line

STEPS = {
    "apollo": """
1. Sign in to Apollo as an admin and open Settings, then Integrations, then API (app.apollo.io/#/settings/integrations/api).
2. Click "API keys", then "Create new key". Name it Meridian and switch on "Set as master key":
   sequence figures are only given to a master key.
3. Copy the key and paste it below.
""",
    "heyreach": """
1. Sign in to HeyReach and open Integrations in the left menu.
2. Find "HeyReach API" (or "Public API"), click "New API key", and name it Meridian.
3. Copy the key and paste it below.
""",
}


def cmd_connect(tool):
    import getpass
    from . import zoho
    print("Connect {} to Meridian. This only reads campaign figures; nothing in {} is changed.".format(NAMES[tool], NAMES[tool]))
    print(STEPS[tool])
    key = getpass.getpass("{} API key (hidden as you paste): ".format(NAMES[tool])).strip()
    if not key:
        sys.exit("No key entered. Nothing was saved.")
    if tool == "apollo":  # try the key before saving it
        call("apollo", "POST", APOLLO_URL + "/emailer_campaigns/search?page=1&per_page=1", {}, key)
    else:
        call("heyreach", "GET", HEYREACH_URL + "/auth/CheckApiKey", None, key)
    slot, label = KEYS[tool], ""
    if tool == "apollo" and api_key(tool) and key not in [k for k, _ in accounts(tool)]:
        answer = input("\nAn Apollo account is already connected. Type A to add this one as another account, or R to replace the first: ").strip().lower()
        if answer.startswith("a"):
            free = [name for name in slots(tool) if not config.setting(name)]
            if not free:
                sys.exit("Nine Apollo accounts are already connected. Nothing was saved.")
            slot = free[0]
            label = input("A short name for this account, shown on its sequences (for example the team or owner): ").strip()
        elif not answer.startswith("r"):
            sys.exit("Nothing was saved.")
    zoho.write_env({slot: key, slot.replace("_API_KEY", "_LABEL"): label} if slot != KEYS[tool] else {slot: key})
    print("\nKey accepted and saved to {} (readable only by you).".format(config.ENV_FILE))
    conn = zoho.live_database()
    print("Synced:", describe(sync(conn, db.now(conn), tool)) + ".")
    conn.close()
    if tool == "apollo":
        print("Apollo gives running totals, so each sequence shows its all-time figure now and day-by-day counts from today on.")
    print("Open the app and look at the Outbound screen.")


def main(argv):
    command = argv[0] if argv else ""
    tool = argv[1] if len(argv) > 1 else None
    if tool and tool not in KEYS or command not in ("connect", "sync", "status") or (command == "connect" and not tool):
        sys.exit(__doc__)
    try:
        if command == "connect":
            return cmd_connect(tool)
        from . import zoho
        conn = zoho.live_database()
        if command == "sync":
            for t in ([tool] if tool else [t for t in KEYS if configured(t)]):
                print("Synced:", describe(sync(conn, db.now(conn), t)) + ".")
        else:
            for t in KEYS:
                n, sent = conn.execute(
                    "SELECT COUNT(DISTINCT c.id), COALESCE(SUM(d.sent), 0) FROM outbound_campaigns c "
                    "LEFT JOIN outbound_daily d ON d.campaign_id = c.id WHERE c.channel_id = ?", (t,)).fetchone()
                print("{}: {}, {:,} campaigns, {:,} sent by day.".format(NAMES[t], "key saved" if configured(t) else "not connected", n, sent))
        conn.close()
    except OutboundError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main(sys.argv[1:])

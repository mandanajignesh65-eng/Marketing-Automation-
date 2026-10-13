"""Everything Meridian exchanges with Meta directly.

Reading (runs with the Meta Ads sync, needs the "ads_read" permission):
  - the account's structure: campaigns, ad sets and ads, with budgets, goals, learning status and each ad's creative
  - one row per ad per day: spend, reach, clicks, WhatsApp chats started, first replies, video views
  - Meta's own three quality rankings per ad
  - who saw the ads: by placement, by age and gender, by region (per ad set per day)

Sending (off until switched on; see MODE below):
  - conversion events for ads that click to WhatsApp ("LeadSubmitted" for a qualified lead, "Purchase" for a meeting
    held), matched by the click id WhatsApp hands over with the first message
  - customer-list audiences built from Zoho: people to leave out (customers, junk, people already talking to us)
    and people to find more of (qualified leads, customers)

    python -m meridian.meta status          what is set up, what is queued, how big each audience would be
    python -m meridian.meta send            send the queued events now (does nothing while sending is off)

Sending is controlled by META_SEND_MODE: "off" (the default: nothing leaves), "test" (events go to Meta's Test
Events tool with META_TEST_EVENT_CODE and are not used for anything) or "live". Audiences are only ever uploaded when
a leader presses the button for one; emails are hashed (SHA-256) before they leave, as Meta requires.
"""

import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from . import config, db, money, scoring
from .periods import iso

URL = "https://graph.facebook.com"
MODES = ("off", "test", "live")
EVENTS = ("LeadSubmitted", "Purchase")       # what Meta accepts for chats that started from an ad
MAX_AGE_DAYS = 7                             # Meta refuses events older than this
BATCH = 1000
CHATS = ("onsite_conversion.messaging_conversation_started_7d", "onsite_conversion.total_messaging_connection")
FIRST_REPLY = "onsite_conversion.messaging_first_reply"
LEADS = ("lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead")
VIDEO = {"video_p25": "video_p25_watched_actions", "video_p50": "video_p50_watched_actions", "video_p75": "video_p75_watched_actions",
         "video_p100": "video_p100_watched_actions", "thruplays": "video_thruplay_watched_actions"}
BREAKDOWNS = {"placement": "publisher_platform,platform_position", "age_gender": "age,gender", "region": "region"}
RANK = {"ABOVE_AVERAGE": "Above average", "AVERAGE": "Average", "BELOW_AVERAGE_35": "Below average (bottom 35%)",
        "BELOW_AVERAGE_20": "Below average (bottom 20%)", "BELOW_AVERAGE_10": "Below average (bottom 10%)"}

# The lists Meridian can keep in Meta. `use` says what each is for; `sql` picks the leads (it must return email).
AUDIENCES = {
    "customers": dict(name="Meridian · Customers", use="exclude",
                      why="People from companies that already bought. Ads should not be spent on them.",
                      sql="SELECT DISTINCT l.email FROM leads l JOIN deals d ON d.lead_id = l.id WHERE d.stage = 'won'"),
    "junk": dict(name="Meridian · Not a fit", use="exclude",
                 why="Leads sales marked as junk or not qualified. Leaving them out stops paying for them twice.",
                 sql="SELECT email FROM leads WHERE status = 'Unqualified'"),
    "talking": dict(name="Meridian · Already talking to us", use="exclude",
                    why="Everyone who became a lead in the last 90 days. They do not need to see the first ad again.",
                    sql="SELECT email FROM leads WHERE created_at >= :recent"),
    "qualified": dict(name="Meridian · Qualified leads", use="lookalike",
                      why="Leads that fit the customer we want. Meta can look for more people like them.",
                      sql="SELECT email FROM leads WHERE score >= :threshold AND status <> 'Unqualified'"),
}


class MetaError(Exception):
    """A problem the person running this can act on."""


def mode():
    value = config.setting("META_SEND_MODE", "off").strip().lower()
    return value if value in MODES else "off"


def token(sending=False):
    """Sending may use its own token (made for the dataset in Events Manager); otherwise the ads token is used."""
    return (sending and config.setting("META_CAPI_TOKEN")) or config.setting("META_ACCESS_TOKEN")


def accounts():
    return [a.strip() for a in config.setting("META_AD_ACCOUNT_IDS").split(",") if a.strip()]


def setup():
    """What is in place, as plain yes/no facts for the screen and the status command."""
    return dict(reading=bool(token() and accounts()), mode=mode(), dataset=bool(config.setting("META_DATASET_ID")),
                whatsapp=bool(config.setting("META_WABA_ID")), test_code=bool(config.setting("META_TEST_EVENT_CODE")),
                can_send=bool(token(True) and config.setting("META_DATASET_ID") and config.setting("META_WABA_ID")))


def request(method, path, params=None, sending=False):
    """One call to Meta. GET puts the parameters in the address; POST and DELETE send them as a form."""
    key = token(sending)
    if not key:
        raise MetaError("Meta is not connected. Run ./connect-meta.sh in Terminal.")
    url = path if path.startswith("http") else "{}/{}".format(URL, path.lstrip("/"))
    data = None
    params = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in (params or {}).items() if v is not None}
    if method == "GET" and params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    elif params:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": "Bearer " + key, "Accept": "application/json",
                                                                         "User-Agent": "Meridian/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                raw = res.read()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as err:
            try:
                error = (json.loads(err.read()) or {}).get("error") or {}
            except ValueError:
                error = {}
            if (err.code == 429 or error.get("code") in (4, 17, 32, 613, 80000, 80004)) and attempt < 3:  # asked too quickly
                time.sleep(30 * (attempt + 1))
                continue
            if error.get("code") == 190:
                raise MetaError("Meta no longer accepts the saved access token. Run ./connect-meta.sh in Terminal to enter a new one.")
            if error.get("code") in (10, 200) or error.get("type") == "OAuthException" and "permission" in (error.get("message") or "").lower():
                raise MetaError("Meta refused this: the access token does not have the permission it needs. ({})".format(error.get("message")))
            raise MetaError("Meta: {}".format(error.get("error_user_msg") or error.get("message") or "error {}".format(err.code)))
        except (urllib.error.URLError, OSError, ValueError) as err:
            raise MetaError("Could not reach Meta: {}".format(getattr(err, "reason", err)))


def pages(path, params):
    data = request("GET", path, params)
    while True:
        for row in data.get("data") or []:
            yield row
        nxt = (data.get("paging") or {}).get("next")
        if not nxt:
            return
        data = request("GET", nxt)


def number(value):
    try:
        return max(int(float(value or 0)), 0)
    except (TypeError, ValueError):
        return 0


def rupees(minor):
    """Meta gives budgets in the currency's smallest unit (paise, cents)."""
    return float(minor) / 100 if minor not in (None, "", "0") else None


def action(row, names, field="actions"):
    found = {x.get("action_type"): number(x.get("value")) for x in row.get(field) or []}
    return next((found[n] for n in names if n in found), 0)


# ------------------------------------------------------------------------------- reading

def pull(conn, now, start, end):
    """Bring in the structure, the daily figures per ad, the rankings and the audience breakdowns. Returns a small summary."""
    span = dict(since=start.isoformat(), until=end.isoformat())
    stamp, ads_seen, spend = iso(now), 0, 0.0
    for account in accounts():
        base = "act_{}".format(account)
        for c in pages(base + "/campaigns", dict(limit=200, fields="id,name,effective_status,objective,buying_type,daily_budget,lifetime_budget,"
                                                                   "bid_strategy,created_time,updated_time")):
            conn.execute("INSERT OR REPLACE INTO meta_campaigns (id, account, name, status, objective, buying_type, daily_budget, lifetime_budget, "
                         "bid_strategy, created, updated, seen_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (c["id"], account, c.get("name") or "Untitled campaign", c.get("effective_status"), c.get("objective"), c.get("buying_type"),
                          rupees(c.get("daily_budget")), rupees(c.get("lifetime_budget")), c.get("bid_strategy"), c.get("created_time"),
                          c.get("updated_time"), stamp))
        for a in pages(base + "/adsets", dict(limit=200, fields="id,name,campaign_id,effective_status,optimization_goal,destination_type,billing_event,"
                                                                "daily_budget,lifetime_budget,bid_strategy,promoted_object,targeting,learning_stage_info,"
                                                                "start_time,end_time")):
            t = a.get("targeting") or {}
            geo = t.get("geo_locations") or {}
            who = dict(countries=geo.get("countries") or [], regions=[r.get("name") for r in geo.get("regions") or []],
                       cities=[c.get("name") for c in geo.get("cities") or []], age_min=t.get("age_min"), age_max=t.get("age_max"),
                       advantage=bool((t.get("targeting_automation") or {}).get("advantage_audience")),
                       included=len(t.get("custom_audiences") or []), excluded=len(t.get("excluded_custom_audiences") or []))
            conn.execute("INSERT OR REPLACE INTO meta_adsets (id, campaign_id, name, status, optimization_goal, destination_type, billing_event, "
                         "daily_budget, lifetime_budget, bid_strategy, promoted, targeting, learning, starts, ends, seen_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (a["id"], a.get("campaign_id"), a.get("name") or "Untitled ad set", a.get("effective_status"), a.get("optimization_goal"),
                          a.get("destination_type"), a.get("billing_event"), rupees(a.get("daily_budget")), rupees(a.get("lifetime_budget")),
                          a.get("bid_strategy"), json.dumps(a.get("promoted_object") or {}), json.dumps(who),
                          (a.get("learning_stage_info") or {}).get("status"), a.get("start_time"), a.get("end_time"), stamp))
        for a in pages(base + "/ads", dict(limit=200, fields="id,name,adset_id,campaign_id,effective_status,created_time,preview_shareable_link,"
                                                             "creative{id,title,body,call_to_action_type,image_url,thumbnail_url,video_id,object_type}")):
            cr = a.get("creative") or {}
            conn.execute("INSERT INTO meta_ads (id, adset_id, campaign_id, name, status, creative_id, title, body, cta, image_url, video_id, format, "
                         "preview, created, seen_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (id) DO UPDATE SET adset_id = excluded.adset_id, "
                         "campaign_id = excluded.campaign_id, name = excluded.name, status = excluded.status, creative_id = excluded.creative_id, "
                         "title = excluded.title, body = excluded.body, cta = excluded.cta, image_url = excluded.image_url, video_id = excluded.video_id, "
                         "format = excluded.format, preview = excluded.preview, seen_at = excluded.seen_at",
                         (a["id"], a.get("adset_id"), a.get("campaign_id"), a.get("name") or "Untitled ad", a.get("effective_status"), cr.get("id"),
                          cr.get("title"), cr.get("body"), cr.get("call_to_action_type"), cr.get("image_url") or cr.get("thumbnail_url"),
                          cr.get("video_id"), "Video" if cr.get("video_id") else "Image", a.get("preview_shareable_link"), a.get("created_time"), stamp))

        # one row per ad per day
        conn.execute("DELETE FROM meta_ad_daily WHERE date >= ? AND ad_id IN (SELECT a.id FROM meta_ads a JOIN meta_campaigns c ON c.id = a.campaign_id "
                     "WHERE c.account = ?)", (start.isoformat(), account))
        fields = "ad_id,adset_id,campaign_id,spend,impressions,reach,clicks,inline_link_clicks,actions,video_play_actions," + ",".join(VIDEO.values())
        for r in pages(base + "/insights", dict(level="ad", time_increment=1, limit=500, time_range=span, fields=fields)):
            if not r.get("ad_id"):
                continue
            ads_seen += 1
            spend += float(r.get("spend") or 0)
            conn.execute("INSERT OR REPLACE INTO meta_ad_daily (date, ad_id, spend, impressions, reach, clicks, link_clicks, chats, first_replies, leads, "
                         "video_plays, video_3s, thruplays, video_p25, video_p50, video_p75, video_p100) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (r["date_start"], r["ad_id"], float(r.get("spend") or 0), number(r.get("impressions")), number(r.get("reach")),
                          number(r.get("clicks")), number(r.get("inline_link_clicks")), action(r, CHATS), action(r, (FIRST_REPLY,)), action(r, LEADS),
                          action(r, ("video_view",), "video_play_actions"), action(r, ("video_view",)), action(r, ("video_view",), VIDEO["thruplays"]),
                          action(r, ("video_view",), VIDEO["video_p25"]), action(r, ("video_view",), VIDEO["video_p50"]),
                          action(r, ("video_view",), VIDEO["video_p75"]), action(r, ("video_view",), VIDEO["video_p100"])))

        # Meta's own verdict on each ad against others competing for the same people (needs about 500 impressions)
        for r in pages(base + "/insights", dict(level="ad", date_preset="last_30d", limit=500,
                                                fields="ad_id,quality_ranking,engagement_rate_ranking,conversion_rate_ranking")):
            conn.execute("UPDATE meta_ads SET quality_ranking = ?, engagement_ranking = ?, conversion_ranking = ? WHERE id = ?",
                         (r.get("quality_ranking"), r.get("engagement_rate_ranking"), r.get("conversion_rate_ranking"), r.get("ad_id")))

        # who saw the ads, per ad set per day
        conn.execute("DELETE FROM meta_breakdown_daily WHERE date >= ? AND adset_id IN (SELECT s.id FROM meta_adsets s JOIN meta_campaigns c "
                     "ON c.id = s.campaign_id WHERE c.account = ?)", (start.isoformat(), account))
        for kind, by in BREAKDOWNS.items():
            for r in pages(base + "/insights", dict(level="adset", time_increment=1, limit=500, time_range=span, breakdowns=by,
                                                    fields="adset_id,spend,impressions,inline_link_clicks,actions")):
                value = " · ".join(str(r.get(k) or "unknown").replace("_", " ") for k in by.split(","))
                conn.execute("INSERT OR REPLACE INTO meta_breakdown_daily (date, adset_id, kind, value, spend, impressions, link_clicks, chats) "
                             "VALUES (?,?,?,?,?,?,?,?)", (r["date_start"], r.get("adset_id"), kind, value, float(r.get("spend") or 0),
                                                          number(r.get("impressions")), number(r.get("inline_link_clicks")), action(r, CHATS)))
    return dict(rows=ads_seen, spend=spend)


# ------------------------------------------------------------------------------- what the screen shows

SUMS = ("spend", "impressions", "clicks", "link_clicks", "chats", "first_replies", "leads", "video_plays", "video_3s", "thruplays",
        "video_p25", "video_p50", "video_p75", "video_p100")


def view(conn, now, p):
    """Campaign, ad set and ad figures for the period and the one before, the daily line, the breakdowns and the sending side."""
    s, e, ps, pe = p.s.isoformat(), p.e.isoformat(), p.ps.isoformat(), p.pe.isoformat()
    sums = ", ".join("COALESCE(SUM(d.{0}), 0) AS {0}".format(k) for k in SUMS)

    def figures(a, b):
        return {r["ad_id"]: dict(r) for r in conn.execute(
            "SELECT d.ad_id, {}, COALESCE(MAX(d.reach), 0) AS reach_day, COALESCE(SUM(d.reach), 0) AS reach_sum FROM meta_ad_daily d "
            "WHERE d.date BETWEEN ? AND ? GROUP BY d.ad_id".format(sums), (a, b))}
    cur, prev = figures(s, e), figures(ps, pe)
    blank = dict({k: 0 for k in SUMS}, reach_sum=0)
    ads = []
    for a in conn.execute("SELECT * FROM meta_ads ORDER BY created DESC, id DESC"):
        row = dict(a)
        row.update({k: cur.get(a["id"], blank)[k] for k in SUMS}, reach=cur.get(a["id"], blank)["reach_sum"],
                   prev_spend=prev.get(a["id"], blank)["spend"], prev_chats=prev.get(a["id"], blank)["chats"],
                   quality=RANK.get(a["quality_ranking"]), engagement=RANK.get(a["engagement_ranking"]), conversion=RANK.get(a["conversion_ranking"]))
        ads.append(row)
    adsets = []
    for a in conn.execute("SELECT * FROM meta_adsets ORDER BY starts DESC, id DESC"):
        row = dict(a, targeting=json.loads(a["targeting"] or "{}"))
        row.pop("promoted", None)
        adsets.append(row)
    campaigns = [dict(c) for c in conn.execute("SELECT * FROM meta_campaigns ORDER BY created DESC, id DESC")]
    days = {d.isoformat(): dict(date=d.isoformat(), spend=0, impressions=0, link_clicks=0, chats=0) for d in p.days}
    for r in conn.execute("SELECT date, SUM(spend) AS spend, SUM(impressions) AS impressions, SUM(link_clicks) AS link_clicks, SUM(chats) AS chats "
                          "FROM meta_ad_daily WHERE date BETWEEN ? AND ? GROUP BY date", (s, e)):
        if r["date"] in days:
            days[r["date"]].update(spend=r["spend"], impressions=r["impressions"], link_clicks=r["link_clicks"], chats=r["chats"])
    breakdowns = {}
    for r in conn.execute("SELECT kind, value, SUM(spend) AS spend, SUM(impressions) AS impressions, SUM(link_clicks) AS link_clicks, SUM(chats) AS chats "
                          "FROM meta_breakdown_daily WHERE date BETWEEN ? AND ? GROUP BY kind, value ORDER BY spend DESC", (s, e)):
        breakdowns.setdefault(r["kind"], []).append(dict(value=r["value"], spend=r["spend"], impressions=r["impressions"],
                                                         link_clicks=r["link_clicks"], chats=r["chats"]))
    source = conn.execute("SELECT status, last_sync_at, note FROM sources WHERE key = 'meta'").fetchone()
    return dict(period=p.as_json(), connected=bool(source and source["status"] == "connected"), note=source["note"] if source else None,
                campaigns=campaigns, adsets=adsets, ads=ads, days=sorted(days.values(), key=lambda d: d["date"]), breakdowns=breakdowns,
                sending=sending(conn, now))


# ------------------------------------------------------------------------------- sending: conversion events

def queue_event(conn, now, name, ctwa_clid, when=None, value=None, lead_ref=None):
    """Put one event in the outbox. The same event for the same click is only ever kept once. Returns True when it was new."""
    if name not in EVENTS:
        raise MetaError("Meta accepts {} for WhatsApp ads, not “{}”.".format(" and ".join(EVENTS), name))
    if not (ctwa_clid or "").strip():
        raise MetaError("The event has no click id, so Meta could not match it to an ad.")
    when = when or now
    if now - when > timedelta(days=MAX_AGE_DAYS):
        raise MetaError("The event is more than {} days old, which Meta refuses.".format(MAX_AGE_DAYS))
    return conn.execute("INSERT OR IGNORE INTO meta_events (event_name, event_time, ctwa_clid, lead_ref, value, currency, status, created_at) "
                        "VALUES (?,?,?,?,?,?,'queued',?)", (name, int(when.timestamp()), ctwa_clid.strip(), lead_ref, value,
                                                            money.spec()["code"] if value is not None else None, iso(now))).rowcount == 1


def payload(row):
    """One event in the shape Meta's Conversions API wants for a chat that started from an ad."""
    event = dict(event_name=row["event_name"], event_time=row["event_time"], action_source="business_messaging", messaging_channel="whatsapp",
                 user_data=dict(whatsapp_business_account_id=config.setting("META_WABA_ID"), ctwa_clid=row["ctwa_clid"]))
    if row["value"] is not None:
        event["custom_data"] = dict(currency=row["currency"] or "INR", value=row["value"])
    return event


def flush(conn, now):
    """Send what is queued. Does nothing while sending is off. Returns how many went, failed and were too old."""
    done = dict(mode=mode(), sent=0, failed=0, expired=0)
    if done["mode"] == "off":
        return done
    if not setup()["can_send"]:
        raise MetaError("Sending needs the dataset id (META_DATASET_ID) and the WhatsApp account id (META_WABA_ID).")
    if done["mode"] == "test" and not config.setting("META_TEST_EVENT_CODE"):
        raise MetaError("Test mode needs the test code from Events Manager (META_TEST_EVENT_CODE).")
    oldest = int((now - timedelta(days=MAX_AGE_DAYS)).timestamp())
    done["expired"] = conn.execute("UPDATE meta_events SET status = 'expired', response = 'Older than 7 days before it could be sent' "
                                   "WHERE status IN ('queued', 'failed') AND event_time < ?", (oldest,)).rowcount
    rows = conn.execute("SELECT * FROM meta_events WHERE status IN ('queued', 'failed') AND tries < 5 ORDER BY event_time LIMIT ?", (BATCH,)).fetchall()
    for row in rows:  # one at a time, so one bad event never holds back the rest
        body = dict(data=[payload(row)])
        if done["mode"] == "test":
            body["test_event_code"] = config.setting("META_TEST_EVENT_CODE")
        try:
            answer = request("POST", "{}/events".format(config.setting("META_DATASET_ID")), body, sending=True)
            ok = number(answer.get("events_received")) >= 1
            status, note = ("tested" if done["mode"] == "test" else "sent") if ok else "failed", json.dumps(answer)[:300]
        except MetaError as err:
            ok, status, note = False, "failed", str(err)[:300]
        done["sent" if ok else "failed"] += 1
        conn.execute("UPDATE meta_events SET status = ?, tries = tries + 1, response = ?, sent_at = ? WHERE id = ?", (status, note, iso(now) if ok else None, row["id"]))
        conn.commit()
    return done


# ------------------------------------------------------------------------------- sending: audiences

def people(conn, now, key):
    """The hashed emails in one list. Meta wants each email trimmed, lower-cased and hashed with SHA-256."""
    spec = AUDIENCES[key]
    rows = conn.execute(spec["sql"], dict(threshold=scoring.threshold(conn), recent=iso(now - timedelta(days=90))))
    emails = {(r[0] or "").strip().lower() for r in rows}
    return sorted(hashlib.sha256(e.encode()).hexdigest() for e in emails if "@" in e)


def push_audience(conn, now, key):
    """Create the list in Meta if it is new, then replace who is in it. Only ever called when a leader asks for it."""
    if key not in AUDIENCES:
        raise MetaError("There is no such list.")
    if mode() == "off":
        raise MetaError("Sending to Meta is switched off. Set META_SEND_MODE to live first.")
    spec, hashed = AUDIENCES[key], people(conn, now, key)
    if len(hashed) < 100:
        raise MetaError("This list has {} people. Meta needs at least 100 that it can match before a list can be used.".format(len(hashed)))
    row = conn.execute("SELECT ext_id FROM meta_audiences WHERE key = ?", (key,)).fetchone()
    ext = row["ext_id"] if row else None
    if not ext:
        made = request("POST", "act_{}/customaudiences".format(accounts()[0]), dict(
            name=spec["name"], subtype="CUSTOM", customer_file_source="USER_PROVIDED_ONLY", description="Kept up to date by Meridian. " + spec["why"]))
        ext = made.get("id")
        if not ext:
            raise MetaError("Meta did not create the list.")
    session = int(time.time())
    parts = [hashed[i:i + 10000] for i in range(0, len(hashed), 10000)]
    for n, part in enumerate(parts, 1):
        request("POST", "{}/usersreplace".format(ext), dict(
            session=dict(session_id=session, batch_seq=n, last_batch_flag=n == len(parts), estimated_num_total=len(hashed)),
            payload=dict(schema=["EMAIL_SHA256"], data=[[h] for h in part])))
    conn.execute("INSERT INTO meta_audiences (key, ext_id, name, people, synced_at) VALUES (?,?,?,?,?) ON CONFLICT (key) DO UPDATE SET "
                 "ext_id = excluded.ext_id, name = excluded.name, people = excluded.people, synced_at = excluded.synced_at",
                 (key, ext, spec["name"], len(hashed), iso(now)))
    return dict(key=key, people=len(hashed))


def sending(conn, now):
    """The sending side for the screen: the switch, what has gone or is waiting, and each list with its size."""
    counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) AS n FROM meta_events GROUP BY status")}
    by_name = [dict(r) for r in conn.execute("SELECT event_name, status, COUNT(*) AS n FROM meta_events GROUP BY 1, 2 ORDER BY 1, 2")]
    recent = [dict(r) for r in conn.execute("SELECT event_name, event_time, status, response, lead_ref, value, sent_at FROM meta_events ORDER BY id DESC LIMIT 25")]
    saved = {r["key"]: dict(r) for r in conn.execute("SELECT * FROM meta_audiences")}
    lists = [dict(key=k, name=v["name"], use=v["use"], why=v["why"], people=len(people(conn, now, k)),
                  in_meta=saved.get(k, {}).get("people"), synced_at=saved.get(k, {}).get("synced_at")) for k, v in AUDIENCES.items()]
    return dict(setup=setup(), counts=counts, by_name=by_name, recent=recent, audiences=lists, events=list(EVENTS))


# ------------------------------------------------------------------------------- command line

def main(argv):
    from . import zoho
    command = argv[0] if argv else ""
    if command not in ("status", "send"):
        sys.exit(__doc__)
    conn = zoho.live_database()
    now = db.now(conn)
    try:
        if command == "send":
            done = flush(conn, now)
            print("Sending is {}. Sent {}, failed {}, too old {}.".format(done["mode"], done["sent"], done["failed"], done["expired"]))
        else:
            info = sending(conn, now)
            s = info["setup"]
            print("Reading from Meta: {}.".format("connected" if s["reading"] else "not connected"))
            print("Sending to Meta: {} (dataset id {}, WhatsApp account id {}).".format(s["mode"], "set" if s["dataset"] else "missing",
                                                                                         "set" if s["whatsapp"] else "missing"))
            print("Events:", ", ".join("{} {}".format(n, k) for k, n in info["counts"].items()) or "none yet")
            for a in info["audiences"]:
                print("  {}: {:,} people ({})".format(a["name"], a["people"], "to leave out" if a["use"] == "exclude" else "to find more of"))
    except MetaError as err:
        sys.exit(str(err))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])

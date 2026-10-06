"""Ad platforms: brings in Meta Ads and LinkedIn Ads campaigns with their daily spend, impressions, clicks and leads.

    python -m meridian.ads connect meta|linkedin   save an access token, choose the ad accounts, bring the history in
    python -m meridian.ads sync [meta|linkedin]    bring in the latest days now
    python -m meridian.ads status                  what is connected and how much it holds

Both connections only read reports; no campaign, budget or ad is changed. The first sync reaches back a year,
later ones re-read the last ten days because both platforms keep revising recent figures. Meta comes in ad by
ad; LinkedIn comes in campaign by campaign. "Leads" here are the leads the platform itself counted (lead forms);
the leads that count everywhere else in Meridian still come from Zoho.
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from . import config, db
from .periods import iso

META_URL = "https://graph.facebook.com"      # no version in the address: Meta then uses the oldest one still supported
LINKEDIN_URL = "https://api.linkedin.com/rest"
PLATFORM = {"meta": "meta", "linkedin": "li"}  # source key -> the channel its campaigns belong to
NAMES = {"meta": "Meta Ads", "linkedin": "LinkedIn Ads"}
TOKENS = {"meta": "META_ACCESS_TOKEN", "linkedin": "LINKEDIN_ACCESS_TOKEN"}
ACCOUNTS = {"meta": "META_AD_ACCOUNT_IDS", "linkedin": "LINKEDIN_AD_ACCOUNT_IDS"}
EVERY_HOURS = 4
HISTORY_DAYS = 365
RELOOK_DAYS = 10
CHUNK_DAYS = 30
META_LEADS = ("lead", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead")  # first one present wins
STATUS = {"ACTIVE": "Active", "PAUSED": "Paused", "CAMPAIGN_PAUSED": "Paused", "ADSET_PAUSED": "Paused", "ARCHIVED": "Archived",
          "DELETED": "Deleted", "COMPLETED": "Completed", "CANCELED": "Cancelled", "DRAFT": "Draft"}


class AdsError(Exception):
    """A problem the person running the sync can act on."""


def token(source):
    return config.setting(TOKENS[source])


def accounts(source):
    return [a.strip() for a in config.setting(ACCOUNTS[source]).split(",") if a.strip()]


def configured(source):
    return bool(token(source) and accounts(source))


def call(source, url, key=None, headers=None):
    req = urllib.request.Request(url, headers=dict({"Authorization": "Bearer " + (key or token(source)), "Accept": "application/json",
                                                    "User-Agent": "Meridian/1.0"}, **(headers or {})))
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                raw = res.read()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as err:
            try:
                detail = json.loads(err.read())
            except ValueError:
                detail = {}
            error = detail.get("error") if isinstance(detail.get("error"), dict) else {}
            message = error.get("message") or detail.get("message") or "error {}".format(err.code)
            busy = err.code == 429 or error.get("code") in (4, 17, 32, 613, 80000, 80004)  # asked too quickly
            if busy and attempt < 3:
                time.sleep(30 * (attempt + 1))
                continue
            if err.code == 401 or error.get("code") == 190 or detail.get("code") in ("EXPIRED_ACCESS_TOKEN", "REVOKED_ACCESS_TOKEN", "INVALID_ACCESS_TOKEN"):
                raise AdsError("{} no longer accepts the saved access token. Run ./connect-{}.sh in Terminal to enter a new one.".format(
                    NAMES[source], source))
            err.detail, err.message = detail, message
            raise AdsError("{}: {}".format(NAMES[source], message)) from err
        except (urllib.error.URLError, OSError, ValueError) as err:
            raise AdsError("Could not reach {}: {}".format(NAMES[source], getattr(err, "reason", err)))


def number(value):
    try:
        return max(int(float(value or 0)), 0)
    except (TypeError, ValueError):
        return 0


def window(conn, source, now):
    row = conn.execute("SELECT last_sync_at FROM sources WHERE key = ?", (source,)).fetchone()
    first = not (row and row["last_sync_at"])
    return now.date() - timedelta(days=HISTORY_DAYS if first else RELOOK_DAYS), now.date()


def chunks(start, end):
    day = start
    while day <= end:
        until = min(day + timedelta(days=CHUNK_DAYS - 1), end)
        yield day, until
        day = until + timedelta(days=1)


def mark(conn, source, now, status="connected", note=None):
    conn.execute("UPDATE sources SET status = ?, last_sync_at = COALESCE(?, last_sync_at), note = ? WHERE key = ?",
                 (status, iso(now) if status == "connected" else None, note, source))


class Book:
    """Collects one platform's rows, then replaces the days read in one go."""

    def __init__(self, conn, source):
        self.conn, self.platform, self.rows = conn, PLATFORM[source], {}

    def campaign(self, ext_id, name, status=None):
        row = self.conn.execute("SELECT id FROM ad_campaigns WHERE platform = ? AND ext_id = ?", (self.platform, str(ext_id))).fetchone()
        if row:
            self.conn.execute("UPDATE ad_campaigns SET name = COALESCE(?, name), status = COALESCE(?, status) WHERE id = ?", (name, status, row["id"]))
            return row["id"]
        return self.conn.execute("INSERT INTO ad_campaigns (platform, name, status, ext_id) VALUES (?,?,?,?)",
                                 (self.platform, name or "Untitled campaign", status or "Paused", str(ext_id))).lastrowid

    def creative(self, campaign_id, ext_id, headline, kind=None):
        row = self.conn.execute("SELECT id FROM ad_creatives WHERE campaign_id = ? AND ext_id = ?", (campaign_id, str(ext_id))).fetchone()
        if row:
            self.conn.execute("UPDATE ad_creatives SET headline = ? WHERE id = ?", (headline, row["id"]))
            return row["id"]
        return self.conn.execute("INSERT INTO ad_creatives (campaign_id, headline, format, ext_id) VALUES (?,?,?,?)",
                                 (campaign_id, headline, kind, str(ext_id))).lastrowid

    def add(self, day, creative_id, spend, impressions, clicks, leads):
        old = self.rows.get((day, creative_id), (0, 0, 0, 0))
        self.rows[(day, creative_id)] = (old[0] + spend, old[1] + impressions, old[2] + clicks, old[3] + leads)

    def save(self, start):
        """Replace everything from `start` on, then roll the platform's days up for the channel screens."""
        own = "SELECT cr.id FROM ad_creatives cr JOIN ad_campaigns c ON c.id = cr.campaign_id WHERE c.platform = ?"
        self.conn.execute("DELETE FROM ad_daily WHERE date >= ? AND creative_id IN ({})".format(own), (start.isoformat(), self.platform))
        self.conn.executemany("INSERT INTO ad_daily (date, creative_id, spend, impressions, clicks, leads) VALUES (?,?,?,?,?,?)",
                              [(d, c, int(round(v[0])), v[1], v[2], v[3]) for (d, c), v in self.rows.items() if any(v)])
        self.conn.execute("DELETE FROM channel_daily WHERE channel_id = ? AND date >= ?", (self.platform, start.isoformat()))
        self.conn.execute(
            "INSERT INTO channel_daily (date, channel_id, impressions, clicks, spend) "
            "SELECT d.date, c.platform, SUM(d.impressions), SUM(d.clicks), SUM(d.spend) FROM ad_daily d "
            "JOIN ad_creatives cr ON cr.id = d.creative_id JOIN ad_campaigns c ON c.id = cr.campaign_id "
            "WHERE c.platform = ? AND d.date >= ? GROUP BY d.date", (self.platform, start.isoformat()))
        return dict(spend=sum(v[0] for v in self.rows.values()), leads=sum(v[3] for v in self.rows.values()),
                    campaigns=len({c for _, c in self.rows}))


# ------------------------------------------------------------------------------- Meta

def meta_pages(url, key=None):
    while url:
        data = call("meta", url, key)
        for row in data.get("data") or []:
            yield row
        url = (data.get("paging") or {}).get("next")


def meta_accounts(key):
    url = "{}/me/adaccounts?{}".format(META_URL, urllib.parse.urlencode(dict(fields="name,account_id,currency", limit=200)))
    return [(a["account_id"], "{} ({}, {})".format(a.get("name") or "Ad account", a["account_id"], a.get("currency") or "?"), a.get("currency"))
            for a in meta_pages(url, key) if a.get("account_id")]


def sync_meta(conn, now):
    start, end = window(conn, "meta", now)
    book = Book(conn, "meta")
    for account in accounts("meta"):
        base = "{}/act_{}".format(META_URL, account)
        status = {c["id"]: (c.get("name"), STATUS.get(c.get("effective_status"), "Paused")) for c in meta_pages(
            "{}/campaigns?{}".format(base, urllib.parse.urlencode(dict(fields="id,name,effective_status", limit=500))))}
        for cid, (name, state) in status.items():
            book.campaign(cid, name, state)
        for a, b in chunks(start, end):
            query = dict(level="ad", time_increment=1, limit=500, time_range=json.dumps(dict(since=a.isoformat(), until=b.isoformat())),
                         fields="campaign_id,campaign_name,ad_id,ad_name,spend,impressions,inline_link_clicks,actions")
            for r in meta_pages("{}/insights?{}".format(base, urllib.parse.urlencode(query))):
                if not r.get("ad_id"):
                    continue
                actions = {x.get("action_type"): number(x.get("value")) for x in r.get("actions") or []}
                leads = next((actions[k] for k in META_LEADS if k in actions), 0)
                camp = book.campaign(r["campaign_id"], r.get("campaign_name"), status.get(r["campaign_id"], (None, None))[1])
                ad = book.creative(camp, r["ad_id"], r.get("ad_name") or "Untitled ad")
                book.add(r["date_start"], ad, float(r.get("spend") or 0), number(r.get("impressions")), number(r.get("inline_link_clicks")), leads)
    summary = book.save(start)
    mark(conn, "meta", now)
    return dict(summary, source="meta", days=(end - start).days + 1)


# ------------------------------------------------------------------------------- LinkedIn

def linkedin_call(path, key=None):
    """LinkedIn wants a dated API version and retires old ones, so the newest month that answers is used."""
    today, last = date.today(), None
    for back in range(1, 13):
        month = (today.year * 12 + today.month - 1) - back
        version = "{}{:02d}".format(month // 12, month % 12 + 1)
        try:
            return call("linkedin", LINKEDIN_URL + path, key, {"LinkedIn-Version": version, "X-Restli-Protocol-Version": "2.0.0"})
        except AdsError as err:
            cause = err.__cause__
            if cause is not None and (cause.code == 426 or "version" in str(getattr(cause, "message", "")).lower()):
                last = err
                continue
            raise
    raise last or AdsError("LinkedIn Ads did not accept any API version.")


def linkedin_accounts(key):
    rows = linkedin_call("/adAccounts?q=search", key).get("elements") or []
    return [(str(a["id"]), "{} ({}, {})".format(a.get("name") or "Ad account", a["id"], a.get("currency") or "?"), a.get("currency"))
            for a in rows if a.get("id") and not a.get("test")]


def linkedin_campaigns(account):
    out, page = {}, ""
    for _ in range(50):
        data = linkedin_call("/adAccounts/{}/adCampaigns?q=search&pageSize=500{}".format(account, page))
        for c in data.get("elements") or []:
            out[str(c.get("id"))] = (c.get("name"), STATUS.get(c.get("status"), "Paused"), (c.get("format") or c.get("type") or "").replace("_", " ").capitalize() or None)
        nxt = (data.get("metadata") or {}).get("nextPageToken")
        if not nxt:
            break
        page = "&pageToken=" + urllib.parse.quote(nxt, safe="")
    return out


def sync_linkedin(conn, now):
    start, end = window(conn, "linkedin", now)
    book = Book(conn, "linkedin")
    part = lambda d: "(year:{},month:{},day:{})".format(d.year, d.month, d.day)
    for account in accounts("linkedin"):
        known = linkedin_campaigns(account)
        ids = {ext: book.campaign(ext, name, state) for ext, (name, state, _) in known.items()}
        for a, b in chunks(start, end):
            path = ("/adAnalytics?q=analytics&pivot=CAMPAIGN&timeGranularity=DAILY&dateRange=(start:{},end:{})"
                    "&accounts=List({})&fields=dateRange,pivotValues,impressions,clicks,costInLocalCurrency,oneClickLeads").format(
                        part(a), part(b), urllib.parse.quote("urn:li:sponsoredAccount:" + account, safe=""))
            for r in linkedin_call(path).get("elements") or []:
                ext = str((r.get("pivotValues") or [""])[0]).rsplit(":", 1)[-1]
                day = (r.get("dateRange") or {}).get("start") or {}
                if not ext or not day:
                    continue
                if ext not in ids:  # a campaign the list no longer shows still has its history
                    ids[ext] = book.campaign(ext, "Campaign " + ext, "Archived")
                # LinkedIn is read per campaign, so each campaign carries one line holding all of its ads.
                line = book.creative(ids[ext], ext, "All ads in this campaign", known.get(ext, (None, None, None))[2])
                book.add("{:04d}-{:02d}-{:02d}".format(day["year"], day["month"], day["day"]), line,
                         float(r.get("costInLocalCurrency") or 0), number(r.get("impressions")), number(r.get("clicks")), number(r.get("oneClickLeads")))
    summary = book.save(start)
    mark(conn, "linkedin", now)
    return dict(summary, source="linkedin", days=(end - start).days + 1)


# ------------------------------------------------------------------------------- running

SYNCS = {"meta": sync_meta, "linkedin": sync_linkedin}


def sync(conn, now, source):
    if not configured(source):
        raise AdsError("{} is not connected. Run ./connect-{}.sh in Terminal.".format(NAMES[source], source))
    try:
        summary = SYNCS[source](conn, now)
    except AdsError as err:
        conn.rollback()
        mark(conn, source, now, "disconnected", str(err))
        conn.commit()
        raise
    conn.commit()
    return summary


def due(conn, now, source):
    row = conn.execute("SELECT status, last_sync_at FROM sources WHERE key = ?", (source,)).fetchone()
    if row and row["status"] == "disconnected":  # the last try failed: wait for "Reconnect" in Settings
        return False
    return not row or not row["last_sync_at"] or now - datetime.fromisoformat(row["last_sync_at"]) >= timedelta(hours=EVERY_HOURS)


def describe(s):
    from . import money
    return "{} {} spent across {:,} ads or campaigns, {:,} platform leads in the {:,} days read".format(
        NAMES[s["source"]], money.money(s["spend"]), s["campaigns"], s["leads"], s["days"])


# ------------------------------------------------------------------------------- command line

STEPS = {
    "meta": """
You need to be an admin of the Meta business that owns the ad account.

1. Open https://developers.facebook.com/apps and click "Create app". Choose "Other", then "Business", name it
   Meridian and pick your business. (If you already have an app in the business, you can use that one.)
2. Open https://business.facebook.com/settings/system-users and click "Add". Name it Meridian, role "Employee".
3. With that system user selected, click "Assign assets", choose "Ad accounts", tick your ad account and switch
   on "View performance" only. Save.
4. Click "Generate token", pick the Meridian app, choose "Never" for expiry, tick the permission "ads_read"
   and nothing else, then Generate.
5. Copy the token and paste it below.
""",
    "linkedin": """
You need to be an admin of the LinkedIn company page, with access to the ad account in Campaign Manager.
LinkedIn has to approve access to ad reports, which can take a few days.

1. Open https://www.linkedin.com/developers/apps and click "Create app". Name it Meridian, choose your company
   page, add any logo, Create. On the Settings tab, click "Verify" next to the company and follow the link.
2. On the Products tab, find "Advertising API" and click "Request access". Fill in the form: say it is for
   internal reporting of your own ad account. Wait for LinkedIn's approval email before the next step.
3. Once approved, open https://www.linkedin.com/developers/tools/oauth/token-generator , choose the Meridian
   app, tick "r_ads" and "r_ads_reporting", click "Request access token" and Allow.
4. Copy the token and paste it below. LinkedIn tokens last 60 days; run this script again to renew.
""",
}


def choose(what, options):
    if not options:
        sys.exit("\nThis token cannot see any {}. Nothing was saved. Check that the ad account was assigned to it.".format(what))
    if len(options) == 1:
        print("\n{}: {}".format(what.capitalize(), options[0][1]))
        return [options[0]]
    print("\nWhich {}? For more than one, separate the numbers with commas, like 1,3.".format(what))
    for i, (_, label, _) in enumerate(options, 1):
        print("  {}. {}".format(i, label))
    while True:
        picks = input("Type a number: ").strip().replace(",", " ").split()
        if picks and all(n.isdigit() and 1 <= int(n) <= len(options) for n in picks):
            return [options[int(n) - 1] for n in dict.fromkeys(picks)]


def cmd_connect(source):
    import getpass
    from . import money, zoho
    print("Connect {} to Meridian. This only reads reports; nothing in your ad account is changed.".format(NAMES[source]))
    print(STEPS[source])
    key = getpass.getpass("{} access token (hidden as you paste): ".format(NAMES[source])).strip()
    if not key:
        sys.exit("No token entered. Nothing was saved.")
    picked = choose("ad account", meta_accounts(key) if source == "meta" else linkedin_accounts(key))
    zoho.write_env({TOKENS[source]: key, ACCOUNTS[source]: ",".join(p[0] for p in picked)})
    print("\nSaved to {} (readable only by you). Bringing in the past year; this can take a few minutes...".format(config.ENV_FILE))
    conn = zoho.live_database()
    conn.execute("UPDATE sources SET last_sync_at = NULL WHERE key = ?", (source,))  # a new choice starts with the full year
    print("Synced:", describe(sync(conn, db.now(conn), source)) + ".")
    other = sorted({p[2] for p in picked if p[2] and p[2] != money.spec()["code"]})
    if other:
        print("Note: this ad account is billed in {}, while Meridian shows {}. Spend is shown as the plain number, not converted."
              .format(", ".join(other), money.spec()["code"]))
    conn.close()
    print("Open the app and look at the Paid ads screen.")


def main(argv):
    command = argv[0] if argv else ""
    source = argv[1] if len(argv) > 1 else None
    if source and source not in SYNCS or command not in ("connect", "sync", "status") or (command == "connect" and not source):
        sys.exit(__doc__)
    try:
        if command == "connect":
            return cmd_connect(source)
        from . import zoho
        conn = zoho.live_database()
        if command == "sync":
            for s in ([source] if source else [s for s in SYNCS if configured(s)]):
                print("Synced:", describe(sync(conn, db.now(conn), s)) + ".")
        else:
            for s in SYNCS:
                n, spend = conn.execute(
                    "SELECT COUNT(DISTINCT c.id), COALESCE(SUM(d.spend), 0) FROM ad_campaigns c LEFT JOIN ad_creatives cr ON cr.campaign_id = c.id "
                    "LEFT JOIN ad_daily d ON d.creative_id = cr.id WHERE c.platform = ?", (PLATFORM[s],)).fetchone()
                print("{}: {}, {:,} campaigns, {:,} spent.".format(NAMES[s], "connected" if configured(s) else "not connected", n, spend))
        conn.close()
    except AdsError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main(sys.argv[1:])

"""Turn an incoming lead (Zoho CRM sync or webhook, Framer form, or any JSON post) into a scored lead."""

from . import metrics, reminders, scoring
from .periods import iso

ENRICHMENT = ("employees", "revenue", "industry", "company_size")
SIGNALS = ("form", "pricing_visits", "emails_sent", "emails_opened")
TEXT_FIELDS = ("title", "company", "email", "owner", "industry", "hq", "website", "utm_source", "utm_medium",
               "utm_campaign", "lead_source", "deal_zoho_id", "company_size")

# Leads without tracking tags are placed by the CRM's "lead source". These pairs sit beside the
# tag pairs in Settings, under this medium, so they are mapped to channels in the same place.
LEAD_SOURCE = "lead source"
# Stands in for a blank lead source, so those leads and deals can be placed or left out like any other source.
NO_SOURCE = "(no lead source)"
SOURCE_SQL = "lower(COALESCE(NULLIF(trim({}.lead_source), ''), '" + NO_SOURCE + "'))"
UNTAGGED_SQL = "COALESCE({0}.utm_source, '') = '' AND COALESCE({0}.utm_medium, '') = ''"
# Lead-source wording that points to one channel without much doubt, first match wins. Events come first
# so "Meta Event Mumbai" is an event, not a Meta ad. Anything unmatched waits to be mapped by hand.
SOURCE_HINTS = [
    ("event", "events"), ("summit", "events"), ("expo", "events"), ("fest", "events"), ("webinar", "events"),
    ("conference", "events"), ("awards", "events"), ("trade show", "events"), ("seminar", "events"),
    ("google ad", "google"), ("adwords", "google"), ("linkedin ad", "li"),
    ("facebook", "meta"), ("instagram", "meta"), ("meta", "meta"),
    ("chatbot", "chatbot"), ("apollo", "apollo"), ("heyreach", "heyreach"),
    ("referral", "referral"), ("reference", "referral"), ("partner", "referral"),
    ("organic", "search"), ("seo", "search"),
    ("contact us", "website"), ("sign-up", "website"), ("signup", "website"), ("registration", "website"), ("website", "website"),
    ("direct", "direct"),
]


def guess_channel(conn, lead_source):
    text = lead_source.strip().lower()
    row = conn.execute("SELECT id FROM channels WHERE lower(id) = ? OR lower(name) = ?", (text, text)).fetchone()
    if row:
        return row["id"]
    known = {r["id"] for r in conn.execute("SELECT id FROM channels")}
    return next((ch for hint, ch in SOURCE_HINTS if hint in text and ch in known), None)


def lookup(conn, source, medium, guess=None):
    """Channel for a (source, medium) pair. A pair seen for the first time is recorded so it shows up in Settings."""
    row = conn.execute("SELECT channel_id FROM utm_map WHERE lower(source) = lower(?) AND lower(medium) = lower(?)",
                       (source, medium)).fetchone()
    if row:
        return row["channel_id"]
    conn.execute("INSERT INTO utm_map (source, medium, channel_id) VALUES (?, ?, ?)", (source, medium, guess))
    return guess


def source_key(lead_source):
    return (lead_source or "").strip() or NO_SOURCE


def classify(conn, utm_source, utm_medium, lead_source=None):
    """Channel for a lead: its tracking tags if it has any, otherwise the CRM's lead source."""
    if utm_source or utm_medium:
        return lookup(conn, (utm_source or "").strip().lower(), (utm_medium or "").strip().lower())
    key = source_key(lead_source)
    return lookup(conn, key, LEAD_SOURCE, None if key == NO_SOURCE else guess_channel(conn, key))


def reapply_sources(conn):
    """Re-place every untagged lead, and every deal, from the current lead-source mapping."""
    for table in ("leads", "deals"):  # every source in use gets a row, so it can be seen and mapped in Settings
        for row in conn.execute("SELECT DISTINCT COALESCE(NULLIF(trim(lead_source), ''), ?) AS s FROM {}".format(table), (NO_SOURCE,)).fetchall():
            lookup(conn, row["s"], LEAD_SOURCE, None if row["s"] == NO_SOURCE else guess_channel(conn, row["s"]))
    by_source = "(SELECT m.channel_id FROM utm_map m WHERE m.medium = ? AND lower(m.source) = {})"
    conn.execute("UPDATE leads SET channel_id = " + by_source.format(SOURCE_SQL.format("leads")) +
                 " WHERE " + UNTAGGED_SQL.format("leads"), (LEAD_SOURCE,))
    conn.execute("UPDATE deals SET channel_id = (SELECT channel_id FROM leads WHERE leads.id = deals.lead_id) WHERE lead_id IS NOT NULL")
    conn.execute("UPDATE deals SET channel_id = " + by_source.format(SOURCE_SQL.format("deals")) +
                 " WHERE lead_id IS NULL", (LEAD_SOURCE,))


# ------------------------------------------------------------------------------- sources left out

def excluded_sources(conn):
    """Lead sources being left out as not marketing, lower-cased."""
    return {r["source"].lower() for r in conn.execute("SELECT source FROM utm_map WHERE medium = ? AND excluded = 1", (LEAD_SOURCE,))}


def is_left_out(excluded, lead_source, tagged=False):
    """Whether a lead or deal with this lead source is left out. A blank source only counts when there are no tracking tags either."""
    key = source_key(lead_source)
    return key.lower() in excluded and not (key == NO_SOURCE and tagged)


def note_left_out(conn, zoho_id, lead_source, deal_zoho_id=None):
    """Record a lead that is not being kept, and drop any copy of it and of the deal it became."""
    conn.execute("INSERT OR REPLACE INTO left_out_leads (zoho_id, source, deal_zoho_id) VALUES (?, ?, ?)",
                 (zoho_id, source_key(lead_source), deal_zoho_id))
    conn.execute("DELETE FROM leads WHERE zoho_id = ?", (zoho_id,))
    if deal_zoho_id:
        conn.execute("DELETE FROM deals WHERE zoho_id = ?", (deal_zoho_id,))


def leave_out(conn, source):
    """Stop keeping a lead source: removes its leads, the deals they became and deals that name it. Returns how many leads went."""
    key = source_key(source).lower()
    leads = SOURCE_SQL.format("leads") + " = ?" + (" AND " + UNTAGGED_SQL.format("leads") if key == NO_SOURCE else "")
    conn.execute("INSERT OR REPLACE INTO left_out_leads (zoho_id, source, deal_zoho_id) "
                 "SELECT COALESCE(zoho_id, 'local-' || id), ?, deal_zoho_id FROM leads WHERE " + leads, (source_key(source), key))
    conn.execute("DELETE FROM deals WHERE lead_id IN (SELECT id FROM leads WHERE " + leads + ")", (key,))
    conn.execute("DELETE FROM deals WHERE zoho_id IN (SELECT deal_zoho_id FROM left_out_leads WHERE lower(source) = ?)", (key,))
    conn.execute("DELETE FROM deals WHERE lead_id IS NULL AND " + SOURCE_SQL.format("deals") + " = ?", (key,))
    gone = conn.execute("DELETE FROM leads WHERE " + leads, (key,)).rowcount
    conn.execute("INSERT INTO utm_map (source, medium, excluded) VALUES (?, ?, 1) ON CONFLICT (source, medium) "
                 "DO UPDATE SET excluded = 1, channel_id = NULL", (source_key(source), LEAD_SOURCE))
    conn.execute("UPDATE utm_map SET excluded = 1, channel_id = NULL WHERE medium = ? AND lower(source) = ?", (LEAD_SOURCE, key))
    return gone


def bring_back(conn, source):
    """Start keeping a lead source again. Its leads return when they are next fetched from the CRM."""
    key = source_key(source).lower()
    conn.execute("UPDATE utm_map SET excluded = 0 WHERE medium = ? AND lower(source) = ?", (LEAD_SOURCE, key))
    conn.execute("DELETE FROM left_out_leads WHERE lower(source) = ?", (key,))


def number(value):
    try:
        return int(float(str(value).replace(",", ""))) if value not in (None, "") else None
    except ValueError:
        return None


def event(conn, lead_id, at, kind, title, detail, channel=None):
    conn.execute("INSERT INTO lead_events (lead_id, at, kind, channel_id, title, detail) VALUES (?,?,?,?,?,?)",
                 (lead_id, at, kind, channel, title, detail))


def upsert_lead(conn, now, data):
    """Create or update a lead. Returns (lead_id, created).

    Optional timestamps (ISO, local time): created_at, modified_at (last change in the CRM) and
    activity_at (last logged call, email or note). They keep the "no owner update" clock honest
    when leads arrive in bulk rather than as they happen.
    """
    name = (data.get("name") or " ".join(x for x in (data.get("first_name"), data.get("last_name")) if x)).strip()
    if not name:
        raise ValueError("A lead needs a name")
    zoho_id = str(data.get("zoho_id") or data.get("id") or "").strip() or None
    if zoho_id:
        conn.execute("DELETE FROM left_out_leads WHERE zoho_id = ?", (zoho_id,))  # it is being kept now
    existing = conn.execute("SELECT * FROM leads WHERE zoho_id = ?", (zoho_id,)).fetchone() if zoho_id else None

    fields = dict(name=name)
    for key in TEXT_FIELDS:
        if data.get(key):
            fields[key] = str(data[key]).strip()
    for key in ("employees", "revenue", "founded"):
        if number(data.get(key)) is not None:
            fields[key] = number(data[key])
    if data.get("status") in metrics.STATUSES:
        fields["status"] = data["status"]
    modified = data.get("modified_at") or iso(now)
    activity = data.get("activity_at")

    if fields.get("industry"):  # the CRM's own value takes over from anything company research filled in
        fields["industry_via"] = None
    if fields.get("company_size") or fields.get("employees") is not None:
        fields["size_via"] = None

    if existing:
        lead_id = existing["id"]
        merged = {k: fields.get(k, existing[k]) for k in ("utm_source", "utm_medium", "lead_source")}
        if existing["channel_id"] is None or any(merged[k] != existing[k] for k in merged):
            fields["channel_id"] = classify(conn, merged["utm_source"], merged["utm_medium"], merged["lead_source"])
        touched = any(fields.get(k) and fields[k] != existing[k] for k in ("status", "owner"))
        conn.execute("UPDATE leads SET {} WHERE id = ?".format(", ".join(k + " = ?" for k in fields)),
                     list(fields.values()) + [lead_id])
        quiet_since = existing["owner_updated_at"] or existing["created_at"]
        if touched:
            reminders.record_owner_update(conn, lead_id, modified)
            conn.execute("UPDATE leads SET last_activity = ?, last_activity_at = ? WHERE id = ?", ("Updated in Zoho CRM", modified, lead_id))
            event(conn, lead_id, modified, "crm", "Status → " + (fields.get("status") or existing["status"]),
                  "Updated by " + (fields.get("owner") or existing["owner"] or "owner"))
        elif activity and activity > quiet_since:
            reminders.record_owner_update(conn, lead_id, activity)
            conn.execute("UPDATE leads SET last_activity = ?, last_activity_at = ? WHERE id = ?", ("Activity logged in Zoho CRM", activity, lead_id))
        rescored = any(k in data for k in ENRICHMENT + SIGNALS)
    else:
        created = data.get("created_at") or iso(now)
        channel = classify(conn, data.get("utm_source"), data.get("utm_medium"), data.get("lead_source"))
        detail = data.get("form_name") or data.get("lead_source") or "Lead received"
        fields.setdefault("status", "New")
        updated = activity or (modified if fields["status"] != "New" and modified > created else None)
        fields.update(zoho_id=zoho_id, channel_id=channel, created_at=created, owner_updated_at=updated,
                      last_activity="Updated in Zoho CRM" if updated else "Lead created", last_activity_at=updated or created,
                      ft_channel=channel, ft_at=created, ft_detail=detail, lt_channel=channel, lt_at=created, lt_detail=detail)
        if any(k in fields for k in ENRICHMENT):
            fields.update(enriched_at=iso(now), enriched_via=data.get("enriched_via") or "webhook")
        cur = conn.execute("INSERT INTO leads ({}) VALUES ({})".format(", ".join(fields), ", ".join("?" for _ in fields)),
                           list(fields.values()))
        lead_id = cur.lastrowid
        event(conn, lead_id, created, "touch", "Lead created", detail, channel)
        if updated and fields["status"] != "New":
            event(conn, lead_id, updated, "crm", "Status → " + fields["status"], "Updated by " + (fields.get("owner") or "owner"))
        rescored = True

    if rescored:
        row = dict(conn.execute("SELECT employees, revenue, industry, company_size FROM leads WHERE id = ?", (lead_id,)).fetchone())
        row.update({k: data.get(k) for k in SIGNALS})
        scoring.store_items(conn, lead_id, scoring.evaluate(row, scoring.profile(conn)))
        scoring.rescore(conn, lead_id)
    return lead_id, existing is None

"""Owner reminders: nudge the lead owner when an open lead has had no update for 3 and 7 days."""

from . import mailer, metrics
from .db import get_setting
from .periods import iso

RULE_DAYS = {"r3": 3, "r7": 7}


def due(conn, now):
    """(rule, lead) pairs that should be reminded now: quiet long enough, and not yet nudged since the last update."""
    enabled = {r["key"] for r in conn.execute("SELECT key FROM alert_rules WHERE kind = 'reminder' AND enabled = 1")}
    out = []
    for rule, days in RULE_DAYS.items():
        if rule not in enabled:
            continue
        rows = conn.execute(
            "SELECT l.* FROM leads l WHERE " + metrics.needs_update_sql("l") +
            " AND NOT EXISTS (SELECT 1 FROM reminders r WHERE r.lead_id = l.id AND r.rule = ?3 "
            "AND r.sent_at >= COALESCE(l.owner_updated_at, l.created_at))",
            (now.date().isoformat(), days, rule)).fetchall()
        out += [(rule, dict(r)) for r in rows]
    return out


def run(conn, now):
    """Record and queue reminders that are due. Returns how many were created."""
    emails = {r["name"]: r["email"] for r in conn.execute("SELECT name, email FROM users")}
    admin = emails.get(get_setting(conn, "current_user"))
    pending = due(conn, now)
    for rule, lead in pending:
        days = RULE_DAYS[rule]
        conn.execute("INSERT INTO reminders (lead_id, rule, owner, sent_at) VALUES (?,?,?,?)",
                     (lead["id"], rule, lead["owner"], iso(now)))
        conn.execute("INSERT INTO lead_events (lead_id, at, kind, title, detail) VALUES (?,?,?,?,?)",
                     (lead["id"], iso(now), "reminder", "Reminder sent to {}".format(lead["owner"] or "owner"),
                      "{} days without an update".format(days)))
        to = [a for a in (emails.get(lead["owner"]), admin if rule == "r7" else None) if a]
        mailer.queue(
            conn, now, "reminder", ", ".join(dict.fromkeys(to)) or None,
            "{} at {} has had no update for {} days".format(lead["name"], lead["company"] or "unknown company", days),
            "Lead: {} ({})\nStatus: {}\nScore: {}\n\nPlease log a call, email, note or status change in Zoho CRM."
            .format(lead["name"], lead["company"] or "-", lead["status"], lead["score"]))
    if pending:
        mailer.flush(conn, now)
    return len(pending)


def record_owner_update(conn, lead_id, when):
    """An owner touched the lead (at `when`, a datetime or ISO string): reset its quiet clock and
    mark the reminders sent before then as answered."""
    at = when if isinstance(when, str) else iso(when)
    conn.execute("UPDATE leads SET owner_updated_at = ? WHERE id = ?", (at, lead_id))
    conn.execute("UPDATE reminders SET owner_updated_at = ? WHERE lead_id = ? AND owner_updated_at IS NULL AND sent_at <= ?",
                 (at, lead_id, at))

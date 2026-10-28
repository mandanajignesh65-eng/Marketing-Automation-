"""People: who can sign in, and who has targets.

A person can have a login (the accounts table), a place on the Targets screen (team_members), or both. The two are
matched by email address, so one row on the People screen stands for one human.
"""

from . import accounts, team


def member_for(conn, email):
    """The Targets person who signs in with this email, or None."""
    row = conn.execute("SELECT id FROM team_members WHERE active = 1 AND lower(email) = ? ORDER BY id LIMIT 1", ((email or "").lower(),)).fetchone()
    return row["id"] if row else None


def view(conn, me):
    logins = {r["email"]: dict(r) for r in conn.execute("SELECT id, name, email, role FROM accounts")}
    rows = []
    for m in conn.execute("SELECT * FROM team_members WHERE active = 1 ORDER BY sort, id"):
        login = logins.pop((m["email"] or "").lower(), None)
        rows.append(dict(name=login["name"] if login else m["name"], email=m["email"] or "", focus=m["focus"] or "", member_id=m["id"],
                         account_id=login["id"] if login else None, role=login["role"] if login else None))
    for login in logins.values():
        rows.append(dict(name=login["name"], email=login["email"], focus="", member_id=None, account_id=login["id"], role=login["role"]))
    for r in rows:
        r["you"] = bool(me and r["account_id"] == me["id"])
        r["targets"] = conn.execute("SELECT COUNT(*) FROM goals WHERE active = 1 AND member_id = ?", (r["member_id"],)).fetchone()[0] if r["member_id"] else 0
    rows.sort(key=lambda r: r["name"].lower())
    return dict(people=rows, min_password=10)


def save(conn, now, account_id, member_id, name, email, password, focus):
    """Add or change a person. There is one role: everyone who signs in can do everything, and everyone has a place on Targets."""
    password = (password or "").strip() or None
    if not (account_id or password):
        raise accounts.AccountError("Give this person a password so they can sign in.")
    accounts.save(conn, now, account_id, name, email, password)
    email = (email or "").strip().lower()
    member_id = member_id or member_for(conn, email)
    team.save_member(conn, member_id, name, focus, email)


def remove(conn, me, account_id, member_id):
    if me and account_id == me["id"]:
        raise accounts.AccountError("You cannot remove yourself.")
    if account_id:
        accounts.remove(conn, account_id)
    if member_id:
        team.remove_member(conn, member_id)

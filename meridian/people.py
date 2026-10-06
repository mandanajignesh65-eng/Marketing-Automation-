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
    rows.sort(key=lambda r: (r["role"] != "admin", r["name"].lower()))
    return dict(people=rows, min_password=10)


def save(conn, now, me, account_id, member_id, name, email, role, password, focus, targets):
    """Add or change a person. `targets` gives a new person a place on the Targets screen."""
    password = (password or "").strip() or None
    login = bool(account_id or password)
    if not login and not (member_id or targets):
        raise accounts.AccountError("Give this person a password so they can sign in, or tick the box to give them targets.")
    if me and account_id == me["id"] and role != "admin":
        raise accounts.AccountError("You cannot take your own leader rights away. Ask another leader to do it.")
    if login:
        accounts.save(conn, now, account_id, name, email, role or "member", password)
    email = (email or "").strip().lower()
    if member_id and focus is None:  # not sent: keep what is written
        focus = conn.execute("SELECT focus FROM team_members WHERE id = ?", (member_id,)).fetchone()["focus"]
    if member_id or targets:
        team.save_member(conn, member_id, name, focus, email)


def remove(conn, me, account_id, member_id):
    if me and account_id == me["id"]:
        raise accounts.AccountError("You cannot remove yourself.")
    if account_id:
        accounts.remove(conn, account_id)
    if member_id:
        team.remove_member(conn, member_id)

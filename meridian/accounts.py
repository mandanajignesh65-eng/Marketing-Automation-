"""Sign-in: who may open Meridian.

    python -m meridian.accounts add       add a person (asks for name, email and a password)
    python -m meridian.accounts list      who can sign in
    python -m meridian.accounts remove EMAIL

Sign-in is switched on as soon as one person has been added, or always when MERIDIAN_REQUIRE_LOGIN=1 (set that on
any copy reachable from the internet, so an empty database is never left open). Passwords are never stored: only
a salted, slow hash of each one is kept. Signing in gives the browser a random token in a cookie that scripts
cannot read; it lasts 14 days.
"""

import hashlib
import hmac
import re
import secrets
import sys
import time
from datetime import datetime, timedelta

from . import config, db
from .periods import iso

ROUNDS = 240000
SESSION_DAYS = 14
COOKIE = "meridian_session"
ROLES = ("admin", "member")
MAX_TRIES, TRY_WINDOW = 8, 300   # wrong passwords allowed per address in five minutes
_tries = {}


def required(conn):
    return config.setting("MERIDIAN_REQUIRE_LOGIN") == "1" or bool(conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone())


def digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ROUNDS).hex()


class AccountError(ValueError):
    pass


def tidy(name, email, role):
    name, email = (name or "").strip(), (email or "").strip().lower()
    if not name or not re.match(r"^[^@\s,;]+@[^@\s,;]+\.[a-z]{2,}$", email):
        raise AccountError("A name and a proper email address are needed (check for a comma where a dot should be).")
    if role not in ROLES:
        raise AccountError("The role is admin or member.")
    return name, email


def strong(password):
    if len(password or "") < 10:
        raise AccountError("The password needs at least 10 characters.")
    return password


def add(conn, now, name, email, password, role="member"):
    name, email = tidy(name, email, role)
    salt = secrets.token_hex(16)
    conn.execute("INSERT INTO accounts (email, name, role, salt, pw_hash, created_at) VALUES (?,?,?,?,?,?) "
                 "ON CONFLICT (email) DO UPDATE SET name = excluded.name, role = excluded.role, salt = excluded.salt, pw_hash = excluded.pw_hash",
                 (email, name, role, salt, digest(strong(password), salt), iso(now)))


def admins(conn, besides=None):
    return conn.execute("SELECT COUNT(*) FROM accounts WHERE role = 'admin' AND id <> ?", (besides or 0,)).fetchone()[0]


def save(conn, now, account_id, name, email, role, password=None):
    """Add a login, or change one. A password is needed for a new login; for an old one it is replaced only when given."""
    name, email = tidy(name, email, role)
    clash = conn.execute("SELECT id FROM accounts WHERE email = ?", (email,)).fetchone()
    if clash and clash["id"] != account_id:
        raise AccountError("Somebody already signs in with that email.")
    if not account_id:
        add(conn, now, name, email, password, role)
        return conn.execute("SELECT id FROM accounts WHERE email = ?", (email,)).fetchone()["id"]
    if role != "admin" and not admins(conn, besides=account_id):
        raise AccountError("At least one leader is needed, so this person has to stay a leader.")
    conn.execute("UPDATE accounts SET name = ?, email = ?, role = ? WHERE id = ?", (name, email, role, account_id))
    if password:
        set_password(conn, account_id, password)
    return account_id


def set_password(conn, account_id, password, keep_token=None):
    """Replace a password and sign that person out everywhere (except the browser that made the change)."""
    salt = secrets.token_hex(16)
    conn.execute("UPDATE accounts SET salt = ?, pw_hash = ? WHERE id = ?", (salt, digest(strong(password), salt), account_id))
    keep = hashlib.sha256(keep_token.encode()).hexdigest() if keep_token else ""
    conn.execute("DELETE FROM sessions WHERE account_id = ? AND token_hash <> ?", (account_id, keep))


def change_password(conn, account_id, current, new, keep_token=None):
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if not row or not hmac.compare_digest(digest(current or "", row["salt"]), row["pw_hash"]):
        raise AccountError("The current password is not right.")
    set_password(conn, account_id, new, keep_token)


def remove(conn, account_id):
    if not admins(conn, besides=account_id):
        raise AccountError("At least one leader is needed, so this login cannot be removed.")
    conn.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))
    conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


def blocked(address):
    """Too many wrong passwords from one address lately."""
    recent = [t for t in _tries.get(address, []) if time.time() - t < TRY_WINDOW]
    _tries[address] = recent
    return len(recent) >= MAX_TRIES


def sign_in(conn, now, email, password, address=""):
    """A new session token, or None when the email and password do not match."""
    row = conn.execute("SELECT * FROM accounts WHERE email = ?", ((email or "").strip().lower(),)).fetchone()
    # the hash is worked out even for an unknown email, so a wrong guess takes the same time either way
    given = digest(password or "", row["salt"] if row else "00" * 16)
    if not row or not hmac.compare_digest(given, row["pw_hash"]):
        _tries.setdefault(address, []).append(time.time())
        return None
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (iso(now),))
    conn.execute("INSERT INTO sessions (token_hash, account_id, created_at, expires_at) VALUES (?,?,?,?)",
                 (hashlib.sha256(token.encode()).hexdigest(), row["id"], iso(now), iso(now + timedelta(days=SESSION_DAYS))))
    return token


def who(conn, now, token):
    """The signed-in person for a session token, or None."""
    if not token:
        return None
    row = conn.execute("SELECT a.id, a.name, a.email, a.role FROM sessions s JOIN accounts a ON a.id = s.account_id "
                       "WHERE s.token_hash = ? AND s.expires_at > ?", (hashlib.sha256(token.encode()).hexdigest(), iso(now))).fetchone()
    return dict(row) if row else None


def sign_out(conn, token):
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))


def main(argv):
    import getpass
    from . import zoho
    command = argv[0] if argv else ""
    if command not in ("add", "list", "remove"):
        sys.exit(__doc__)
    conn = zoho.live_database()
    if command == "add":
        print("Add a person who can sign in to Meridian.\n")
        name, email = input("Name: "), input("Email: ")
        role = "admin" if input("Can this person change settings and add people? Type Y for yes, or press Return for no: ").strip().lower().startswith("y") else "member"
        password = getpass.getpass("Password, at least 10 characters (hidden as you type): ")
        if password != getpass.getpass("The same password again: "):
            sys.exit("The two passwords were different. Nothing was saved.")
        try:
            add(conn, datetime.now().replace(microsecond=0), name, email, password, role)
        except ValueError as err:
            sys.exit(str(err) + " Nothing was saved.")
        conn.commit()
        print("\n{} can now sign in with {}.".format(name.strip(), email.strip().lower()))
    elif command == "remove":
        gone = conn.execute("DELETE FROM accounts WHERE email = ?", ((argv[1] if len(argv) > 1 else "").lower(),)).rowcount
        conn.execute("DELETE FROM sessions WHERE account_id NOT IN (SELECT id FROM accounts)")
        conn.commit()
        print("Removed." if gone else "Nobody has that email.")
    else:
        rows = conn.execute("SELECT name, email, role FROM accounts ORDER BY name").fetchall()
        for r in rows:
            print("{}  {}  ({})".format(r["name"], r["email"], r["role"]))
        print("Nobody yet: Meridian is open to anyone who can reach it." if not rows else "")
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])

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


def add(conn, now, name, email, password, role="member"):
    name, email = (name or "").strip(), (email or "").strip().lower()
    if not name or not re.match(r"^[^@\s,;]+@[^@\s,;]+\.[a-z]{2,}$", email):
        raise ValueError("A name and a proper email address are needed (check for a comma where a dot should be).")
    if len(password or "") < 10:
        raise ValueError("The password needs at least 10 characters.")
    if role not in ROLES:
        raise ValueError("The role is admin or member.")
    salt = secrets.token_hex(16)
    conn.execute("INSERT INTO accounts (email, name, role, salt, pw_hash, created_at) VALUES (?,?,?,?,?,?) "
                 "ON CONFLICT (email) DO UPDATE SET name = excluded.name, role = excluded.role, salt = excluded.salt, pw_hash = excluded.pw_hash",
                 (email, name, role, salt, digest(password, salt), iso(now)))


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

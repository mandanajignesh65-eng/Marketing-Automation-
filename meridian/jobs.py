"""Scheduled jobs: `python -m meridian.jobs [alerts|reminders|all]`.

While the app is running it syncs Zoho CRM and checks the alert rules by itself (see scheduler.py).
Reminders send email to lead owners, so they only go out when this job is run.

Run `alerts` hourly and `reminders` once each morning, for example from cron:

    0 * * * *  cd /path/to/app && .venv/bin/python -m meridian.jobs alerts
    0 9 * * *  cd /path/to/app && .venv/bin/python -m meridian.jobs reminders
"""

import sys

from . import alerts, db, money, reminders


def main(which="all"):
    if which not in ("alerts", "reminders", "all"):
        sys.exit(__doc__)
    conn = db.connect()
    money.load(conn)
    now = db.now(conn)
    if which in ("reminders", "all"):
        print("Reminders created:", reminders.run(conn, now))
    if which in ("alerts", "all"):
        print("New alerts:", len(alerts.run(conn, now)))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main(*sys.argv[1:2])

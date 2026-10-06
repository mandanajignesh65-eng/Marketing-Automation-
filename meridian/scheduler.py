"""Keeps live data fresh while the app is running: syncs Zoho CRM and re-checks the alert rules."""

import threading
import time
from datetime import datetime, timedelta

from . import ads, alerts, backup, config, db, google, money, outbound, research, semrush, zoho

CHECK_SECONDS = 60
RESEARCH_PER_PASS = 100


def due(conn, now, every):
    row = conn.execute("SELECT last_sync_at FROM sources WHERE key = 'zoho'").fetchone()
    last = row["last_sync_at"] if row else None
    if db.get_setting(conn, zoho.REFETCH) == "1":  # a lead source was brought back in Settings
        return True
    return not last or now - datetime.fromisoformat(last) >= timedelta(minutes=every)


_running = threading.Lock()  # one pass at a time, whether the timer or the background loop started it


def tick(force=False):
    """One pass. Does nothing for the sample database or before Zoho is connected. force syncs everything now, due or not.

    Returns True when anything was synced.
    """
    if not zoho.configured() or config.db_path() == config.SAMPLE_DB:
        return False
    if not _running.acquire(blocking=False):
        return False
    conn = db.connect()
    did = False
    try:
        if db.is_demo(conn):
            return False
        money.load(conn)
        now = db.now(conn)
        if force or due(conn, now, int(config.setting("MERIDIAN_ZOHO_EVERY_MINUTES", "15"))):
            did = True
            zoho.sync(conn, now)
            alerts.run(conn, now)
            conn.commit()
            if research.configured():  # new leads' companies, a few at a time so a backlog never holds up the sync
                research.run(conn, now, limit=RESEARCH_PER_PASS)
                conn.commit()
        for tool in outbound.KEYS:  # Apollo and HeyReach, every few hours
            if outbound.configured(tool) and (force or outbound.due(conn, now, tool)):
                did = True
                try:
                    outbound.sync(conn, now, tool)
                except outbound.OutboundError as err:  # recorded on the source; the other tool still runs
                    print("Background sync:", err)
        semrush.load(conn, now)  # any export newly dropped into the semrush folder
        for source in ads.SYNCS:  # Meta Ads and LinkedIn Ads
            if ads.configured(source) and (force or ads.due(conn, now, source)):
                did = True
                try:
                    ads.sync(conn, now, source)
                except ads.AdsError as err:
                    print("Background sync:", err)
        for source in google.SYNCS:  # Google Analytics and Search Console, a few times a day
            if google.configured(source) and (force or google.due(conn, now, source)):
                did = True
                try:
                    google.sync(conn, now, source)
                except google.GoogleError as err:
                    print("Background sync:", err)
        if did:
            alerts.run(conn, now)
            conn.commit()
        return did
    finally:
        conn.close()
        _running.release()
        if did:
            backup.changed()  # fresh data: the stored copy needs refreshing


def sync_now():
    """Start a full sync in the background, for the outside timer. False when one is already running."""
    if _running.locked():
        return False

    def run():
        try:
            tick(force=True)
        except Exception as err:
            print("Timed sync:", err)
    threading.Thread(target=run, name="meridian-timed-sync", daemon=True).start()
    return True


def loop():
    while True:
        try:
            tick()
        except Exception as err:  # a failed sync must not stop later ones; zoho.sync has already recorded why
            print("Background sync:", err)
        time.sleep(CHECK_SECONDS)


def start():
    threading.Thread(target=loop, name="meridian-sync", daemon=True).start()

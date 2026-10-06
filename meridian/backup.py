"""Keeps the data file safe on a host whose disk does not last (Render's free plan wipes it on every restart).

    python -m meridian.backup connect   save the storage address and key, make the storage folder, upload a first copy
    python -m meridian.backup save      upload a copy of the data now
    python -m meridian.backup restore   download the stored copy (only when there is no data file here)
    python -m meridian.backup status    what is stored, and when it was saved

The copy lives in Supabase Storage, in a private bucket: the SQLite database zipped, and the Zoho rules file. On
start-up, if this machine has no data file, the stored copy is downloaded. While running with
MERIDIAN_BACKUP_AUTO=1 (set that on the hosted copy only), a fresh copy is uploaded shortly after anything
changes and after every sync. A laptop without that setting never uploads by itself, so it cannot overwrite the
hosted copy by accident.
"""

import gzip
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

from . import config

DB_NAME, MAPPING_NAME = "meridian.db.gz", "zoho_mapping.json"
QUIET_SECONDS = 20     # upload this long after the last change, so a burst of clicks is one upload
MAX_WAIT_SECONDS = 180  # but never leave a change unsaved longer than this
_state = dict(dirty_since=None, last_change=None, saving=threading.Lock(), last_saved=None, last_error=None, stamp=None)


class BackupError(Exception):
    """A problem the person setting this up can act on."""


def settings():
    return config.setting("SUPABASE_URL").rstrip("/"), config.setting("SUPABASE_SERVICE_KEY"), config.setting("SUPABASE_BUCKET", "meridian")


def configured():
    url, key, _ = settings()
    return bool(url and key)


def automatic():
    return configured() and config.setting("MERIDIAN_BACKUP_AUTO") == "1"


def call(method, path, data=None, content_type="application/json", creds=None):
    url, key, _ = creds or settings()
    req = urllib.request.Request(url + "/storage/v1" + path, data=data, method=method, headers={
        "Authorization": "Bearer " + key, "apikey": key, "Content-Type": content_type, "x-upsert": "true", "User-Agent": "Meridian/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            return res.read()
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")[:300]
        if err.code in (401, 403):
            raise BackupError("Supabase did not accept the key. It needs the secret (service role) key, not the public one.")
        raise NotFound(body) if err.code in (400, 404) and ("not found" in body.lower() or "not_found" in body.lower()) else BackupError(
            "Supabase Storage answered with an error ({}): {}".format(err.code, body))
    except (urllib.error.URLError, OSError) as err:
        raise BackupError("Could not reach Supabase: {}".format(getattr(err, "reason", err)))


class NotFound(BackupError):
    pass


def ensure_bucket(creds=None):
    bucket = (creds or settings())[2]
    try:
        call("POST", "/bucket", json.dumps(dict(id=bucket, name=bucket, public=False)).encode(), creds=creds)
    except BackupError as err:
        if "exist" not in str(err).lower() and "duplicate" not in str(err).lower():
            raise


def stored_stamp(creds=None):
    """When the stored copy was last written, as Supabase reports it, or None when nothing is stored."""
    bucket = (creds or settings())[2]
    try:
        rows = json.loads(call("POST", "/object/list/" + bucket, json.dumps(dict(prefix="", limit=100)).encode(), creds=creds))
    except NotFound:
        return None
    return next((r.get("updated_at") for r in rows if r.get("name") == DB_NAME), None)


def save(creds=None, careful=False):
    """Upload a consistent copy of the live database and the Zoho rules file. Returns the zipped size in bytes.

    careful is how the hosted copy saves by itself: if someone else has uploaded a copy since this one last looked
    (a password reset or a fix made on a laptop), it leaves that copy alone and returns 0. The next restart loads it.
    """
    if not config.LIVE_DB.exists():
        raise BackupError("There is no data file here to save.")
    bucket = (creds or settings())[2]
    with _state["saving"]:
        if careful and _state["stamp"] is not None and stored_stamp(creds) != _state["stamp"]:
            _state.update(dirty_since=None, last_error="A newer copy was uploaded from elsewhere. Restart the service to load it.")
            return 0
        work = tempfile.mkdtemp(prefix="meridian-backup-")
        try:
            plain, packed = os.path.join(work, "copy.db"), os.path.join(work, DB_NAME)
            src, dst = sqlite3.connect(str(config.LIVE_DB), timeout=60), sqlite3.connect(plain)
            try:
                src.backup(dst)  # a clean copy even while the app is writing
            finally:
                src.close()
                dst.close()
            with open(plain, "rb") as fin, gzip.open(packed, "wb", compresslevel=6) as fout:
                shutil.copyfileobj(fin, fout, 1 << 20)
            with open(packed, "rb") as f:
                data = f.read()
            call("POST", "/object/{}/{}".format(bucket, DB_NAME), data, "application/gzip", creds)
            mapping = config.DATA_DIR / MAPPING_NAME
            if mapping.exists():
                call("POST", "/object/{}/{}".format(bucket, MAPPING_NAME), mapping.read_bytes(), "application/json", creds)
            _state.update(dirty_since=None, last_saved=time.time(), last_error=None, stamp=stored_stamp(creds))
            return len(data)
        finally:
            shutil.rmtree(work, ignore_errors=True)


def restore(force=False):
    """Download the stored copy when this machine has no data file. Returns True when something was restored."""
    if not configured() or (config.LIVE_DB.exists() and not force):
        return False
    bucket = settings()[2]
    try:
        data = call("GET", "/object/{}/{}".format(bucket, DB_NAME))
    except NotFound:
        return False  # nothing has been saved yet: start empty
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    part = str(config.LIVE_DB) + ".part"
    with open(part, "wb") as f:
        f.write(gzip.decompress(data))
    check = sqlite3.connect(part)
    try:
        if check.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise BackupError("The stored copy is damaged. It was not put in place.")
    finally:
        check.close()
    os.replace(part, str(config.LIVE_DB))
    _state["stamp"] = stored_stamp()
    try:
        (config.DATA_DIR / MAPPING_NAME).write_bytes(call("GET", "/object/{}/{}".format(bucket, MAPPING_NAME)))
    except NotFound:
        pass
    return True


def changed():
    """Note that the data changed, so the background saver uploads a fresh copy soon."""
    now = time.time()
    _state["last_change"] = now
    _state["dirty_since"] = _state["dirty_since"] or now


def due():
    since, last = _state["dirty_since"], _state["last_change"]
    return bool(since) and (time.time() - last >= QUIET_SECONDS or time.time() - since >= MAX_WAIT_SECONDS)


def loop():
    while True:
        time.sleep(5)
        if automatic() and due():
            try:
                save(careful=True)
            except Exception as err:  # keep trying: the next pass uploads again
                _state["last_error"] = str(err)
                print("Backup:", err)


def start():
    threading.Thread(target=loop, name="meridian-backup", daemon=True).start()


def flush():
    """Upload now if anything is waiting; called when the app is shutting down."""
    if automatic() and _state["dirty_since"]:
        try:
            save(careful=True)
        except Exception as err:
            print("Backup on shutdown:", err)


def status():
    return dict(configured=configured(), automatic=automatic(), waiting=bool(_state["dirty_since"]),
                last_saved=_state["last_saved"], last_error=_state["last_error"])


def cmd_connect():
    import getpass
    from . import zoho
    print(__doc__.split("\n\n")[0])
    print("""
1. In Supabase, open your project and click the gear (Project Settings) at the bottom left.
2. Open "Data API" (or "API"). Copy the Project URL. It looks like https://abcdefgh.supabase.co
3. Open "API Keys". Copy the secret key (also called service_role). Do not use the publishable or anon key.
   This key can read and write everything in the project, so treat it like a password.
""")
    url = input("Project URL: ").strip().rstrip("/")
    key = getpass.getpass("Secret key (hidden as you paste): ").strip()
    if not (url.startswith("https://") and key):
        sys.exit("Both values are needed, and the address starts with https://. Nothing was saved.")
    creds = (url, key, config.setting("SUPABASE_BUCKET", "meridian"))
    ensure_bucket(creds)
    zoho.write_env(dict(SUPABASE_URL=url, SUPABASE_SERVICE_KEY=key))
    print("\nStorage is ready and the details are saved to {} (readable only by you).".format(config.ENV_FILE))
    print("Uploading a first copy of the data...")
    print("Saved: {:.1f} MB.".format(save(creds) / 1e6))


def main(argv):
    command = argv[0] if argv else ""
    if command not in ("connect", "save", "restore", "status"):
        sys.exit(__doc__)
    try:
        if command == "connect":
            return cmd_connect()
        if not configured():
            sys.exit("Storage is not set up. Run ./connect-storage.sh first.")
        if command == "save":
            print("Saved: {:.1f} MB.".format(save() / 1e6))
        elif command == "restore":
            print("Restored the stored copy." if restore() else "Nothing was restored: a data file is already here, or nothing is stored yet.")
        else:
            bucket = settings()[2]
            rows = json.loads(call("POST", "/object/list/" + bucket, json.dumps(dict(prefix="", limit=20)).encode()))
            for r in rows:
                print("{}  {:.1f} MB  saved {}".format(r["name"], (r.get("metadata") or {}).get("size", 0) / 1e6, r.get("updated_at", "")[:19].replace("T", " ")))
            print("" if rows else "Nothing is stored yet.")
    except BackupError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main(sys.argv[1:])

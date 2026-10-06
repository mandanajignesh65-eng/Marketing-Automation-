"""Semrush by file: reads the reports exported from Semrush into the `semrush` folder next to the app.

    python -m meridian.semrush import    read any new export files now
    python -m meridian.semrush status    which snapshots are held

The Semrush plan in use has no API, so the figures arrive as files. In Semrush open Organic Research for the
domain, and on the Positions and Competitors tabs use Export, CSV. Put the files in the folder as they are:
the file name says which domain, report, country and date it is. Each export is kept as a dated snapshot, so
a new one every month shows what moved. A file already read is not read twice.
"""

import csv
import re
import sys

from . import config, db
from .periods import iso

FOLDER = config.BASE_DIR.parent / "semrush"
# chat360.io-organic.Positions-in-20261004-2026-10-05T11_57_19Z.csv
NAME = re.compile(r"^(?P<domain>.+)-organic\.(?P<report>Positions|Competitors)-(?P<country>[a-z]{2})-(?P<day>\d{8})-", re.I)
GIANT_KEYWORDS = 1000000  # youtube.com, google.com and the like share keywords with everyone and are not competitors


def folder():
    return config.Path(config.setting("MERIDIAN_SEMRUSH_DIR")) if config.setting("MERIDIAN_SEMRUSH_DIR") else FOLDER


def number(value, kind=int):
    try:
        return kind(float(str(value or 0).replace(",", "")))
    except ValueError:
        return kind(0)


def read(path):
    with open(str(path), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load(conn, now):
    """Read every export in the folder that has not been read yet. Returns what was added."""
    added = dict(files=0, keywords=0, competitors=0, skipped=[])
    if not folder().is_dir():
        return added
    seen = {r["file"] for r in conn.execute("SELECT file FROM semrush_files")}
    for path in sorted(folder().glob("*.csv")):
        if path.name in seen:
            continue
        m = NAME.match(path.name)
        if not m:
            added["skipped"].append(path.name)
            continue
        domain, country = m["domain"].lower(), m["country"].lower()
        day = "{}-{}-{}".format(m["day"][:4], m["day"][4:6], m["day"][6:])
        rows = read(path)
        key = (domain, country, day)
        if m["report"].lower() == "positions":
            conn.execute("DELETE FROM semrush_keywords WHERE domain = ? AND country = ? AND day = ?", key)
            best = {}
            for r in rows:  # a keyword can be listed again for a map or an AI answer: keep its ordinary result, best position first
                if (r.get("Position Type") or "Organic") != "Organic" or not r.get("Keyword"):
                    continue
                pos = number(r.get("Position"))
                if r["Keyword"] not in best or pos < best[r["Keyword"]][0]:
                    best[r["Keyword"]] = (pos, r)
            conn.executemany(
                "INSERT INTO semrush_keywords (domain, country, day, keyword, position, previous, volume, difficulty, url, traffic, intent) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [key + (k, pos, number(r.get("Previous position")) or None, number(r.get("Search Volume")), number(r.get("Keyword Difficulty")),
                        r.get("URL"), number(r.get("Traffic")), r.get("Keyword Intents")) for k, (pos, r) in best.items()])
            added["keywords"] += len(best)
        else:
            conn.execute("DELETE FROM semrush_competitors WHERE domain = ? AND country = ? AND day = ?", key)
            conn.executemany(
                "INSERT OR REPLACE INTO semrush_competitors (domain, country, day, competitor, relevance, common, keywords, traffic) VALUES (?,?,?,?,?,?,?,?)",
                [key + (r["Domain"].lower(), number(r.get("Competitor Relevance"), float), number(r.get("Common Keywords")),
                        number(r.get("Organic Keywords")), number(r.get("Organic Traffic"))) for r in rows if r.get("Domain")])
            added["competitors"] += len(rows)
        conn.execute("INSERT INTO semrush_files (file, read_at) VALUES (?,?)", (path.name, iso(now)))
        added["files"] += 1
    if added["files"]:
        latest = conn.execute("SELECT MAX(day) FROM semrush_keywords").fetchone()[0]
        conn.execute("UPDATE sources SET status = 'connected', last_sync_at = ?, note = ? WHERE key = 'semrush'",
                     (iso(now), "export of {}".format(latest) if latest else None))
    conn.commit()
    return added


def describe(added):
    if not added["files"]:
        text = "no new export files in the semrush folder"
    else:
        text = "{} new file{} read: {:,} keywords, {:,} competitor rows".format(
            added["files"], "" if added["files"] == 1 else "s", added["keywords"], added["competitors"])
    if added["skipped"]:
        text += ". Not recognised (keep Semrush's own file names): " + ", ".join(added["skipped"])
    return text


def brand_words(conn):
    name = re.sub(r"[^a-z0-9]", "", (db.get_setting(conn, "company", "") or "").lower())
    return [name, re.sub(r"^([a-z]+)(\d+)$", r"\2\1", name)] if name else []  # chat360, and 360chat


def view(conn):
    """The newest snapshot per domain for the Website screen, or None when nothing has been imported."""
    latest = [tuple(r) for r in conn.execute("SELECT domain, country, MAX(day) FROM semrush_keywords GROUP BY domain, country ORDER BY domain")]
    if not latest:
        return None
    brand = brand_words(conn)
    is_brand = lambda k: any(w and w in k.replace(" ", "") for w in brand)
    sites = []
    for domain, country, day in latest:
        rows = [dict(r) for r in conn.execute(
            "SELECT keyword, position, previous, volume, url, traffic, intent FROM semrush_keywords WHERE domain = ? AND country = ? AND day = ? "
            "ORDER BY traffic DESC, volume DESC", (domain, country, day))]
        for r in rows:
            r["brand"] = is_brand(r["keyword"])
            r["path"] = re.sub(r"^https?://[^/]+", "", r["url"] or "") or "/"
        traffic = sum(r["traffic"] for r in rows)
        rivals = [dict(r) for r in conn.execute(
            "SELECT competitor, relevance, common, keywords, traffic FROM semrush_competitors WHERE domain = ? AND country = ? "
            "AND day = (SELECT MAX(day) FROM semrush_competitors WHERE domain = ? AND country = ?) AND keywords < ? AND relevance > 0 "
            "ORDER BY common DESC, relevance DESC LIMIT 10", (domain, country, domain, country, GIANT_KEYWORDS))]
        other = [r for r in rows if not r["brand"]]
        sites.append(dict(
            domain=domain, country=country.upper(), day=day, keywords=len(rows), traffic=traffic,
            top3=sum(1 for r in rows if r["position"] <= 3), top10=sum(1 for r in rows if r["position"] <= 10),
            brand_traffic=sum(r["traffic"] for r in rows if r["brand"]),
            # where the non-brand visits come from, and the searches with real demand that sit just off page one
            earning=other[:8],
            within_reach=sorted([r for r in other if 11 <= r["position"] <= 30], key=lambda r: -r["volume"])[:8],
            competitors=rivals, own=dict(keywords=len(rows), traffic=traffic)))
    return dict(sites=sites)


def main(argv):
    from . import zoho
    command = argv[0] if argv else ""
    if command not in ("import", "status"):
        sys.exit(__doc__)
    conn = zoho.live_database()
    if command == "import":
        print("Semrush:", describe(load(conn, db.now(conn))) + ".")
    for r in conn.execute("SELECT domain, country, day, COUNT(*) AS n FROM semrush_keywords GROUP BY 1,2,3 ORDER BY 1,3"):
        print("  {} ({}) {}: {:,} keywords".format(r["domain"], r["country"].upper(), r["day"], r["n"]))
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])

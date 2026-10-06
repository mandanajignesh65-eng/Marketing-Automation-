"""Company research: finds each lead's company in Crustdata and fills in the industry and size Zoho is missing.

    python -m meridian.research connect          save a Crustdata API key, then research every waiting company
    python -m meridian.research run [--limit N]  research waiting companies now (newest leads first)
    python -m meridian.research status           how many leads have company details, and where they came from
    python -m meridian.research pending [--since YYYY-MM-DD]   the waiting companies, as JSON
    python -m meridian.research load FILE...     record lookup results saved as JSON (Crustdata's identify response)

A lead's company is recognised by its website or work-email domain, or failing that by its company name.
Crustdata's "identify" lookup is free and returns the industry and an employee-count range. Only the domain
or the company name typed on the lead is sent, never an email address, and a company field that just repeats
the lead's own name is skipped. What comes back is kept per company in the
`companies` table, so a company is looked up once however many leads it has. Values typed into Zoho are never
overwritten: research only fills in blanks.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import timedelta

from . import config, db, money, scoring
from .periods import iso

API_URL = "https://api.crustdata.com/company/identify"
API_VERSION = "2025-11-01"
BATCH = 25                 # identifiers per request, Crustdata's maximum
PAUSE_SECONDS = 2.2        # the endpoint allows 30 requests a minute
RETRY_NOT_FOUND_DAYS = 90
SOURCE = "Crustdata"

# Mailbox providers: an address here says nothing about the company.
FREE_MAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "yahoo.co.uk", "ymail.com", "rocketmail.com",
    "hotmail.com", "hotmail.co.uk", "outlook.com", "outlook.in", "live.com", "live.in", "msn.com", "rediffmail.com", "rediff.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "protonmail.com", "proton.me", "pm.me", "mail.com", "gmx.com", "zoho.com",
    "zohomail.in", "zohomail.com", "yandex.com", "qq.com", "163.com", "duck.com", "hey.com", "fastmail.com", "tutanota.com",
}
# The same providers under other endings (yahoo.fr), common misspellings, and made-up addresses typed into forms.
FREE_LABELS = {"gmail", "gmial", "gamil", "gmai", "gmal", "gmaill", "fgmail", "googlemail", "yahoo", "hotmail", "outlook", "live", "rediffmail",
               "icloud", "test", "testing", "example", "abc", "xyz", "company", "com", "email", "mail", "demo", "none", "na"}
SHARED_ENDINGS = {"co", "com", "org", "net", "gov", "nic", "ac", "edu", "res", "gen", "ind", "firm", "bank"}
# Addresses on these are pages about a company, not the company's own site.
NOT_A_SITE = {"linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "wa.me", "linktr.ee",
              "google.com", "bit.ly", "calendly.com", "wixsite.com", "wordpress.com", "blogspot.com", "github.io"}
# What people type when they have no company to give.
NO_COMPANY = {"na", "n a", "none", "nil", "no", "test", "testing", "self", "self employed", "individual", "personal", "freelance",
              "freelancer", "student", "retired", "home", "unknown", "not applicable", "company", "abc", "xyz", "demo", "private",
              "business", "own business", "startup", "nothing", "other", "others"}
# Legal forms and filler that differ between how a company is typed and how it is listed.
NAME_NOISE = {"pvt", "private", "ltd", "limited", "llp", "llc", "inc", "incorporated", "corp", "corporation", "co", "company",
              "plc", "gmbh", "the", "india", "group", "p", "and"}
SIZE_ORDER = ["1", "2-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"]


class ResearchError(Exception):
    pass


class Rejected(ResearchError):
    """Crustdata refused some identifiers in a request (the whole request fails when one is malformed)."""

    def __init__(self, values):
        super().__init__("Crustdata could not read: " + ", ".join(values))
        self.values = values


# ------------------------------------------------------------------------------- recognising a lead's company

def clean_domain(value):
    """'https://www.Example.com/contact' or 'someone@example.com' -> 'example.com'. None when there is no usable domain."""
    text = (value or "").strip().lower()
    if "@" in text:
        text = text.rsplit("@", 1)[1]
    text = re.sub(r"^[a-z]+://", "", text).split("/")[0].split("?")[0].split(":")[0]
    text = re.sub(r"^www\d?\.", "", text).strip(".")
    return text if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", text) else None


def squash(name):
    """A company name reduced to its distinctive words, for comparing how it was typed with how it is listed."""
    words = re.sub(r"[^a-z0-9]+", " ", (name or "").lower().replace("&", " and ")).split()
    return " ".join(w for w in words if w not in NAME_NOISE)


def tidy_name(name):
    """A company name as typed, without bracketed notes ("Citi (Citibank)", "(per card logo)") or stray spacing."""
    return " ".join(re.sub(r"\([^)]*\)?", " ", name or "").split()).strip(" -,./")


def usable(domain, own=""):
    """Whether a domain can stand for the lead's company: not a mailbox provider, a placeholder, or our own."""
    label = (domain or "").split(".")[0]
    if domain and domain.count(".") == 1 and label in SHARED_ENDINGS:  # "nic.in", "co.in": an ending many organisations share
        return False
    return bool(domain) and domain not in FREE_MAIL and domain not in NOT_A_SITE and label not in FREE_LABELS \
        and not label.startswith("test") and not (own and label == own)


def company_key(lead, own=""):
    """How a lead's company is looked up: its domain, or ('name:' + company name), or None when there is nothing to go on.

    own is our own company's name squashed ("chat360"): colleagues testing a form are not leads' companies.
    """
    site = clean_domain(lead["website"])
    if usable(site, own):
        return site
    mail = clean_domain(lead["email"]) if "@" in (lead["email"] or "") else None
    if usable(mail, own):
        return mail
    name = tidy_name(lead["company"])
    plain = squash(name)
    if len(plain) < 3 or plain in NO_COMPANY or plain.isdigit() or "@" in name or (own and plain.replace(" ", "").startswith(own)):
        return None
    person = squash(lead["name"])  # people often type their own name where the company goes; that is not a company
    if plain == person or plain in person.split() or set(plain.split()) <= set(person.split()):
        return None
    return "name:" + name.lower()


def needs_research(lead):
    return not (lead["industry"] or "").strip() or (lead["employees"] is None and not (lead["company_size"] or "").strip())


def own_name(conn):
    return squash(db.get_setting(conn, "company", "")).replace(" ", "")


def waiting(conn, now, since=None):
    """Companies still to look up, newest lead first: {key: the domain or the name as typed}."""
    own = own_name(conn)
    cutoff = iso(now - timedelta(days=RETRY_NOT_FOUND_DAYS))
    done = {r["key"] for r in conn.execute("SELECT key FROM companies WHERE status = 'found' OR researched_at >= ?", (cutoff,))}
    out = {}
    for lead in conn.execute("SELECT name, company, email, website, industry, employees, company_size FROM leads "
                             "WHERE created_at >= ? ORDER BY created_at DESC", (since or "",)):
        if not needs_research(lead):
            continue
        key = company_key(lead, own)
        if key and key not in done and key not in out:
            out[key] = tidy_name(lead["company"]) if key.startswith("name:") else key
    return out


# ------------------------------------------------------------------------------- reading Crustdata's answer

def size_rank(info):
    label = (info.get("employee_count_range") or "").replace(",", "").replace(" ", "")
    return SIZE_ORDER.index(label) if label in SIZE_ORDER else -1


def choose(key, matches):
    """The match to trust for a lookup, or None. Wrong details are worse than none.

    Crustdata lists its best match first, but also returns near misses (other banks on "bank.in" for
    "indianbank.bank.in"), so the first listing that really carries the domain, or the name, is the one taken.
    """
    infos = [m.get("company_data", {}).get("basic_info") or {} for m in matches or []]
    infos = [i for i in infos if i.get("industries") or i.get("employee_count_range")]
    if key.startswith("name:"):
        # A name alone is weak evidence ("Amit", "Metro", "Zouk"), so it must be the listing's own name and an
        # established company: 51 or more people, or 1,001 or more when the name is a single word.
        want = squash(key[5:])
        floor = SIZE_ORDER.index("51-200" if " " in want else "1001-5000")
        infos = [i for i in infos if want and want in (squash(i.get("name")), squash(i.get("profile_name"))) and size_rank(i) >= floor]
    else:
        infos = [i for i in infos if key == clean_domain(i.get("primary_domain")) or key in [clean_domain(d) for d in i.get("all_domains") or []]]
    return infos[0] if infos else None


def record(conn, now, key, match):
    info = match or {}
    industries = [x for x in info.get("industries") or [] if x]
    conn.execute(
        "INSERT OR REPLACE INTO companies (key, status, name, domain, industry, industries, employee_range, founded, website, profile_url, "
        "source, researched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (key, "found" if match else "not_found", info.get("name"), clean_domain(info.get("primary_domain")),
         industries[0] if industries else None, ", ".join(industries) or None, info.get("employee_count_range"),
         info.get("year_founded"), info.get("website"), info.get("professional_network_url"), SOURCE, iso(now)))


def absorb(conn, now, response, keys=None, ordered=False):
    """Record one identify response (a list with an entry per identifier). Returns (found, not found).

    keys are the lookups the answers may belong to. Crustdata answers for the main domain when asked about a
    sub-domain ("dealer.example.com" comes back as "example.com"), so an answer is matched to its key by
    position when the response lines up with what was asked (ordered), and otherwise by the domain's ending.
    """
    keys = list(keys) if keys is not None else None
    ordered = ordered and keys is not None and len(response or []) == len(keys)
    found = missing = 0
    for i, entry in enumerate(response or []):
        raw = " ".join(str(entry.get("matched_on") or "").split()).lower()
        if not raw:
            continue
        by_domain = entry.get("match_type") == "domain"
        asked = raw if by_domain else "name:" + raw
        if ordered:
            targets = [keys[i]]
        elif keys is not None:
            targets = [k for k in keys if k == asked or (by_domain and not k.startswith("name:") and k.endswith("." + asked))]
        else:
            targets = [asked]
        match = choose(asked, entry.get("matches"))
        for key in targets:
            record(conn, now, key, match)
            found, missing = found + bool(match), missing + (not match)
    return found, missing


def apply(conn, now):
    """Bring leads in line with what is known about their companies, then score them again. Returns leads changed.

    A field is filled when the CRM left it blank, and kept up to date afterwards for as long as research is
    still where it came from (industry_via / size_via). A value typed into the CRM always wins.
    """
    known = {r["key"]: r for r in conn.execute("SELECT * FROM companies WHERE status = 'found'")}
    own, changed = own_name(conn), 0
    for lead in conn.execute("SELECT id, name, company, email, website, industry, employees, company_size, founded, "
                             "industry_via, size_via FROM leads").fetchall():
        ours_industry, ours_size = lead["industry_via"] == SOURCE, lead["size_via"] == SOURCE
        if not (needs_research(lead) or ours_industry or ours_size):
            continue
        key = company_key(lead, own)
        company = known.get(key)
        if not company:  # nothing is known (any more): take back whatever research had filled in
            if ours_industry or ours_size:
                gone = dict(industry=None, industry_via=None) if ours_industry else {}
                gone.update(dict(company_size=None, size_via=None) if ours_size else {})
                gone.update(enriched_at=None, enriched_via=None)
                conn.execute("UPDATE leads SET {} WHERE id = ?".format(", ".join(k + " = ?" for k in gone)), list(gone.values()) + [lead["id"]])
                changed += 1
            continue
        fill = {}
        if (ours_industry or not (lead["industry"] or "").strip()) and company["industry"] and company["industry"] != lead["industry"]:
            fill.update(industry=company["industry"], industry_via=SOURCE)
        size = company["employee_range"] + " employees" if company["employee_range"] else None
        if (ours_size or (lead["employees"] is None and not (lead["company_size"] or "").strip())) and size and size != lead["company_size"]:
            fill.update(company_size=size, size_via=SOURCE)
        if not fill:
            continue
        # (the website is left alone: it is one of the things a lead's company is recognised by)
        if lead["founded"] is None and company["founded"]:
            fill["founded"] = company["founded"]
        # a match on the company name alone is less certain than one on its domain, so the lead says which it was
        fill.update(enriched_at=iso(now), enriched_via=company["source"] + (" (matched by company name)" if key.startswith("name:") else ""))
        conn.execute("UPDATE leads SET {} WHERE id = ?".format(", ".join(k + " = ?" for k in fill)), list(fill.values()) + [lead["id"]])
        changed += 1
    if changed:
        scoring.refresh_fit(conn)
    return changed


# ------------------------------------------------------------------------------- Crustdata's API

def api_key():
    return config.setting("CRUSTDATA_API_KEY")


def configured():
    return bool(api_key())


def identify(kind, values):
    """One free lookup of up to 25 domains or names."""
    body = json.dumps({kind: values}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + api_key(), "Content-Type": "application/json", "x-api-version": API_VERSION})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.loads(res.read() or b"[]")
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < 2:  # too many requests: the header says how long until the window resets
                time.sleep(min(60, int(err.headers.get("X-RateLimit-Reset") or 20)) + 1)
                continue
            if err.code in (401, 403):
                raise ResearchError("Crustdata refused the API key. Run ./connect-crustdata.sh in Terminal to enter it again.")
            detail = err.read().decode("utf-8", "replace")
            bad = re.search(r"Invalid company (?:domains|names): ([^\[\"}]+)", detail)
            if err.code == 400 and bad:
                raise Rejected([v.strip() for v in bad.group(1).split(",") if v.strip()])
            raise ResearchError("Crustdata answered {}: {}".format(err.code, detail[:200]))
        except urllib.error.URLError as err:
            raise ResearchError("Could not reach Crustdata: {}".format(err.reason))


def run(conn, now, limit=None, since=None, progress=None):
    """Look up waiting companies through the API, then fill in their leads. Returns a summary."""
    if not configured():
        raise ResearchError("Company research needs a Crustdata API key. Run ./connect-crustdata.sh in Terminal.")
    todo = waiting(conn, now, since)
    keys = list(todo)[:limit] if limit else list(todo)
    summary = dict(asked=len(keys), found=0, not_found=0, left=len(todo) - len(keys), leads=0)
    try:
        for kind, group in (("domains", [k for k in keys if not k.startswith("name:")]), ("names", [k for k in keys if k.startswith("name:")])):
            for i in range(0, len(group), BATCH):
                part = group[i:i + BATCH]
                try:
                    answer = identify(kind, [todo[k] for k in part])
                except Rejected as err:  # drop what it could not read and ask once more for the rest
                    part = [k for k in part if todo[k] not in err.values] or part[:0]
                    answer = identify(kind, [todo[k] for k in part]) if part else []
                    time.sleep(PAUSE_SECONDS)
                found, missing = absorb(conn, now, answer, part, ordered=True)
                for key in group[i:i + BATCH]:  # anything unanswered counts as not found, so it is not asked again tomorrow
                    conn.execute("INSERT OR IGNORE INTO companies (key, status, source, researched_at) VALUES (?, 'not_found', ?, ?)",
                                 (key, SOURCE, iso(now)))
                summary["found"] += found
                summary["not_found"] += len(group[i:i + BATCH]) - found
                conn.commit()
                if progress:
                    progress(summary)
                time.sleep(PAUSE_SECONDS)
    finally:
        summary["leads"] = apply(conn, now)
        mark_source(conn, now, "connected")
        conn.commit()
    return summary


def mark_source(conn, now, status=None):
    conn.execute("UPDATE sources SET last_sync_at = ?, status = COALESCE(?, status), note = NULL WHERE key = 'crustdata'", (iso(now), status))


def coverage(conn, start=None, end=None):
    """How many leads have the company details scoring needs, and how many of those came from research."""
    row = conn.execute(
        "SELECT COUNT(*) AS leads, "
        "COALESCE(SUM(COALESCE(industry, '') <> ''), 0) AS with_industry, "
        "COALESCE(SUM(employees IS NOT NULL OR COALESCE(company_size, '') <> ''), 0) AS with_size, "
        "COALESCE(SUM(industry_via = ? OR size_via = ?), 0) AS researched "
        "FROM leads WHERE created_at >= ? AND created_at < ?", (SOURCE, SOURCE, start or "", end or "9999")).fetchone()
    return dict(row)


def describe(summary):
    text = "{:,} companies looked up, {:,} found".format(summary["asked"], summary["found"])
    text += ", {:,} leads filled in".format(summary["leads"])
    if summary["left"]:
        text += ", {:,} companies still waiting".format(summary["left"])
    return text


# ------------------------------------------------------------------------------- command line

def open_db():
    from . import zoho
    conn = zoho.live_database()
    money.load(conn)
    return conn


def cmd_connect():
    import getpass
    from . import zoho
    print(__doc__.split("\n\n")[0])
    print("""
1. Sign in at https://app.crustdata.com with the account your team uses.
2. Open the API keys page (under Settings or API) and create a key.
3. Copy the key and paste it below. Looking companies up is free; it does not use credits.
""")
    key = getpass.getpass("Crustdata API key (hidden as you paste): ").strip()
    if not key:
        sys.exit("No key entered. Nothing was saved.")
    zoho.write_env(dict(CRUSTDATA_API_KEY=key))
    conn = open_db()
    todo = waiting(conn, db.now(conn))
    print("\nKey saved to {} (readable only by you).".format(config.ENV_FILE))
    print("Looking up {:,} companies. This takes about {:.0f} minutes; it is safe to stop and run again.".format(
        len(todo), len(todo) / BATCH * (PAUSE_SECONDS + 1) / 60 + 1))
    report(run(conn, db.now(conn), progress=show_progress))
    conn.close()


def show_progress(summary):
    print("\r  {:,} of {:,} looked up, {:,} found".format(summary["found"] + summary["not_found"], summary["asked"], summary["found"]), end="", flush=True)


def report(summary):
    print("\nCompany research:", describe(summary))


def main(argv):
    command = argv[0] if argv else ""

    def option(name):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None

    try:
        if command == "connect":
            return cmd_connect()
        if command not in ("run", "status", "pending", "load"):
            sys.exit(__doc__)
        conn = open_db()
        now = db.now(conn)
        if command == "run":
            report(run(conn, now, limit=int(option("--limit") or 0) or None, progress=show_progress))
        elif command == "status":
            c = coverage(conn)
            done = dict(conn.execute("SELECT status, COUNT(*) FROM companies GROUP BY status").fetchall())
            print("{:,} leads: {:,} have an industry, {:,} a company size; {:,} were filled in by research.".format(
                c["leads"], c["with_industry"], c["with_size"], c["researched"]))
            print("{:,} companies found, {:,} not found, {:,} waiting.".format(
                done.get("found", 0), done.get("not_found", 0), len(waiting(conn, now))))
        elif command == "pending":
            todo = waiting(conn, now, option("--since"))
            print(json.dumps(dict(domains=[v for k, v in todo.items() if not k.startswith("name:")],
                                  names=[v for k, v in todo.items() if k.startswith("name:")]), ensure_ascii=False))
        elif command == "load":
            found = missing = 0
            own = own_name(conn)  # every lead's company, so a better answer can replace an earlier one
            keys = sorted({k for k in (company_key(r, own) for r in conn.execute("SELECT name, company, email, website FROM leads")) if k})
            for path in argv[1:]:
                with open(path) as fh:
                    a, b = absorb(conn, now, json.load(fh), keys)
                found, missing = found + a, missing + b
            leads = apply(conn, now)
            mark_source(conn, now)
            conn.commit()
            print("{:,} companies found, {:,} not found, {:,} leads filled in.".format(found, missing, leads))
        conn.close()
    except ResearchError as err:
        sys.exit("\n" + str(err))


if __name__ == "__main__":
    main(sys.argv[1:])

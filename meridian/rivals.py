"""Competitor monitoring: a dated, sourced list of what each competitor did.

Three feeds fill it, all from public pages (no paid data, no logged-in LinkedIn):

  press      Google News, searched by the competitor's name. Every item carries the date it was published.
  their site Pages on the competitor's own site (newsroom, blog, product updates, customer stories, events, careers,
             pricing). Each page is read on a timer; a link that was not there before is a new signal. These pages
             rarely show dates, so such a signal carries the day Meridian first saw it, and says so. A pricing page
             is compared as a whole: any change to its text is one signal.
  watch      The weekly competitor-watch run's findings file, added by hand. These are the checked findings, with
             their evidence, and unverified leads are kept apart from them.

The first time a page is read, everything on it is taken as already known, so a new page never floods the list.
A page that suddenly shows many new links (a redesign) gives one signal, not dozens.

    python -m meridian.rivals sync      read every feed now
    python -m meridian.rivals status    competitors, pages watched, signals held
"""

import hashlib
import html as htmllib
import json
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from . import config, db
from .periods import iso

EVERY_HOURS = 12
AGENT = "Mozilla/5.0 (compatible; Meridian/1.0; competitor page monitor)"
NEWS = "https://news.google.com/rss/search?q={}&hl=en-IN&gl=IN&ceid=IN:en"
MAX_BYTES = 2_000_000
FLOOD = 15  # more new links than this on one page in one read is a redesign, not news

CATEGORIES = {"product": "Product", "pricing": "Pricing", "customers": "Customers", "partnership": "Partnerships", "funding": "Funding and deals",
              "hiring": "People and hiring", "events": "Events", "recognition": "Recognition", "content": "Content", "news": "Other news"}
KINDS = {"news": "Newsroom", "press": "Press wire", "blog": "Blog", "product": "Product updates", "customers": "Customer stories",
         "events": "Events and webinars", "careers": "Careers", "pricing": "Pricing page"}
KIND_CATEGORY = {"blog": "content", "product": "product", "customers": "customers", "events": "events", "careers": "hiring", "pricing": "pricing"}
# what a headline is about, first match wins
RULES = [
    ("recognition", r"\b(named (a |as a )?leader|leader ratings?|gartner|forrester|everest group|magic quadrant|\bwins? .{0,30}award|recogni[sz]ed)"),
    ("funding", r"\b(raises?|raised|funding|series [a-f]\b|valuation|invest(s|ed|ment|ors?)\b|ipo\b|acquir\w+|acquisition|merger|stake)"),
    ("hiring", r"\b(appoints?|appointed|joins? as|named? .{0,40} as|names? .{0,60}(head|chief|ceo|officer|president|director)\b|hires?\b|hiring|layoffs?|lays? off|steps? down|elevates?|new (ceo|cfo|cto|cmo|cro|coo)\b|chief \w+ officer)"),
    ("partnership", r"\b(partners?\b|partnership|collaborat\w+|alliance|ties? up|tie-up|teams? up|integrat\w+ with|joins? hands)"),
    ("customers", r"\b(selects?|chooses?|deploys?|goes live|case study|customer story|powered by|adopts?|wins? .{0,30}(deal|contract|mandate))"),
    ("events", r"\b(summit|conference|webinar|expo\b|gitex|fintech fest|\bgff\b|booth|keynote|meetup|roundtable|awards?\b)"),
    ("pricing", r"\b(pricing|price cut|price hike|per minute|per conversation)"),
    ("product", r"\b(launch\w*|unveil\w*|introduc\w*|releas\w*|rolls? out|debuts?|new (feature|platform|agent|product)|now available)"),
]
CONTEXT = r"\b(ai\b|a\.i\.|whatsapp|conversational|chatbot|messaging|voice|agent|cpaas|rcs\b|saas|startup|platform|customer (experience|engagement|support)|" \
          r"funding|raises|launch|partner|acquir|appoint|ceo\b|unicorn)"
SKIP_SOURCES = ("youtube", "facebook", "instagram", "reddit", "quora", "tracxn", "crunchbase", "pitchbook", "glassdoor", "ambitionbox", "quasa", "g2.com")
NAMES = {"jio", "india", "indias", "firm", "company", "launches", "launch", "launched", "unveils", "announces", "introduces", "rolls", "out"}  # words every such headline has
STOP = set("a an the of for to in on and with by from at as is its it into new that this their our your how why what when".split())


def words(title):
    """The telling words of a headline, for noticing that two papers ran the same story."""
    return {w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 2 and w not in STOP} - NAMES


def same_story(conn, competitor_id, title, when):
    """An earlier signal about the same thing within a few days: several outlets covering one announcement are one signal."""
    mine = words(title)
    if not mine or not when:
        return None
    day = datetime.fromisoformat(when)
    for r in conn.execute("SELECT id, title FROM competitor_signals WHERE competitor_id = ? AND origin = 'press' AND published_at BETWEEN ? AND ?",
                          (competitor_id, iso(day - timedelta(days=10)), iso(day + timedelta(days=10)))):
        shared = mine & words(r["title"])
        # at least three telling words in common, covering most of the shorter headline
        if len(shared) >= 3 and len(shared) / min(len(mine), len(words(r["title"]))) >= 0.6:
            return r["id"]
    return None
NAV = re.compile(r"^(home|about|about us|contact|contact us|login|log in|sign in|sign up|get started|book a demo|request a demo|learn more|read more|"
                 r"privacy policy|terms|terms of use|careers|pricing|blog|resources|products?|solutions?|customers|partners|company|support|docs|"
                 r"view all|see all|next|previous|menu|search|cookie policy|subscribe|talk to sales|try for free|watch demo)$", re.I)

# The five competitors and their verified pages, from the Chat360 competitor-watch source registry (5 Sep 2026).
SEED = [
    dict(name="Engati", youtube="https://www.youtube.com/@engati", domain="engati.ai", linkedin="https://www.linkedin.com/company/engati", sources=[
        ("news", "https://www.engati.ai/news-old"), ("blog", "https://www.engati.ai/blog"), ("customers", "https://www.engati.ai/customers"),
        ("events", "https://www.engati.ai/webinars"), ("careers", "https://www.engati.ai/careers"), ("pricing", "https://www.engati.ai/pricing")]),
    dict(name="Yellow.ai", youtube="https://www.youtube.com/@yellowdotai", domain="yellow.ai", linkedin="https://www.linkedin.com/company/yellowdotai", sources=[
        ("product", "https://docs.yellow.ai/whats-new"), ("blog", "https://yellow.ai/blog/"), ("news", "https://yellow.ai/newsroom/"),
        ("pricing", "https://yellow.ai/pricing/")]),
    dict(name="Kore.ai", youtube="https://www.youtube.com/@koreai", domain="kore.ai", linkedin="https://www.linkedin.com/company/kore-inc", sources=[
        ("news", "https://www.kore.ai/news"), ("customers", "https://www.kore.ai/customer-stories"), ("events", "https://www.kore.ai/webinar"),
        ("careers", "https://www.kore.ai/careers")]),
    dict(name="Gupshup", domain="gupshup.ai", linkedin="https://www.linkedin.com/company/gupshup", context=True, sources=[
        ("news", "https://www.gupshup.ai/resources/newsroom/"), ("press", "https://www.prnewswire.com/news/gupshup-technologies/"),
        ("customers", "https://www.gupshup.ai/resources/case-studies/"), ("events", "https://www.gupshup.ai/resources/events-webinars/"),
        ("careers", "https://www.gupshup.ai/careers"), ("pricing", "https://www.gupshup.ai/isv-partners/whatsapp-api/pricing")]),
    dict(name="Haptik", domain="haptik.ai", linkedin="https://www.linkedin.com/company/haptik-inc", sources=[
        ("news", "https://www.haptik.ai/company/news-and-media"), ("press", "https://www.prnewswire.com/news/haptik/"),
        ("blog", "https://www.haptik.ai/blog"), ("events", "https://www.haptik.ai/resources/webinars"), ("careers", "https://www.haptik.ai/careers")]),
]


class RivalError(Exception):
    """A problem the person using this can act on."""


def seed(conn):
    """Put the five known competitors in, once, on a database that has none."""
    if db.is_demo(conn) or conn.execute("SELECT 1 FROM competitors LIMIT 1").fetchone():
        return
    for n, c in enumerate(SEED):
        cid = conn.execute("INSERT INTO competitors (name, domain, linkedin, needs_context, sort) VALUES (?,?,?,?,?)",
                           (c["name"], c["domain"], c["linkedin"], 1 if c.get("context") else 0, n)).lastrowid
        conn.executemany("INSERT INTO competitor_sources (competitor_id, kind, url) VALUES (?,?,?)", [(cid, k, u) for k, u in c["sources"]])


def seed_social(conn):
    """Add the known YouTube channels, once. A channel taken off the list afterwards stays off."""
    if db.is_demo(conn) or db.get_setting(conn, "competitor_social_seeded"):
        return
    for c in SEED:
        row = conn.execute("SELECT id FROM competitors WHERE name = ?", (c["name"],)).fetchone()
        if row and c.get("youtube"):
            conn.execute("INSERT OR IGNORE INTO competitor_accounts (competitor_id, network, url) VALUES (?,?,?)", (row["id"], "youtube", c["youtube"]))
    db.set_setting(conn, "competitor_social_seeded", "1")


def seed_own(conn):
    """Our own pages, once, so the social tables show us next to the competitors. Nothing else is read for this row."""
    if db.is_demo(conn) or db.get_setting(conn, "competitor_own_seeded"):
        return
    cid = conn.execute("INSERT INTO competitors (name, domain, linkedin, own, sort) VALUES ('Chat360', 'chat360.io', 'https://www.linkedin.com/company/chat360', 1, -1)").lastrowid
    conn.executemany("INSERT OR IGNORE INTO competitor_accounts (competitor_id, network, url) VALUES (?,?,?)",
                     [(cid, "linkedin", "https://www.linkedin.com/company/chat360"), (cid, "youtube", "https://www.youtube.com/@Chat360_io")])
    db.set_setting(conn, "competitor_own_seeded", "1")


def seed_linkedin(conn):
    """Start reading the LinkedIn page already written on each competitor, once."""
    if db.is_demo(conn) or db.get_setting(conn, "competitor_linkedin_seeded"):
        return
    conn.execute("UPDATE competitors SET linkedin = 'https://www.linkedin.com/company/kore-inc' WHERE linkedin LIKE '%/company/koredotai%'")  # their page's real address
    for c in conn.execute("SELECT id, linkedin FROM competitors WHERE active = 1 AND own = 0 AND linkedin LIKE '%linkedin.com/company/%'").fetchall():
        conn.execute("INSERT OR IGNORE INTO competitor_accounts (competitor_id, network, url) VALUES (?,?,?)", (c["id"], "linkedin", c["linkedin"].rstrip("/")))
    db.set_setting(conn, "competitor_linkedin_seeded", "1")


def classify(title, fallback="news"):
    text = (title or "").lower()
    return next((cat for cat, pattern in RULES if re.search(pattern, text)), fallback)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            return res.read(MAX_BYTES).decode("utf-8", "ignore"), res.geturl()
    except urllib.error.HTTPError as err:
        raise RivalError("the page answered with error {}".format(err.code))
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise RivalError("could not be reached ({})".format(getattr(err, "reason", err)))


def clean(text):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def page_links(page, base, kind):
    """The article-like links on a page: (address, text). Menus, buttons and links to other sites are left out."""
    host = urllib.parse.urlparse(base).netloc.lower().replace("www.", "")
    root = ".".join(host.split(".")[-2:])
    floor = 8 if kind == "careers" else 18
    found = {}
    for href, inner in re.findall(r"<a\b[^>]*?href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", page, flags=re.S | re.I):
        text = clean(inner)
        if len(text) < floor or len(text) > 220 or NAV.match(text):
            continue
        url = urllib.parse.urljoin(base, href.strip())
        parts = urllib.parse.urlparse(url)
        if parts.scheme not in ("http", "https") or not parts.netloc.lower().endswith(root):
            continue
        url = "{}://{}{}".format(parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"))
        if url.rstrip("/") == base.split("?")[0].rstrip("/") or len(parts.path.strip("/")) < 3:
            continue
        if url not in found or len(text) > len(found[url]):
            found[url] = text
    return found


def page_text(page):
    """The words a visitor reads, for noticing that a pricing page changed."""
    body = re.sub(r"<(script|style|noscript|svg)\b.*?</\1>", " ", page, flags=re.S | re.I)
    return clean(body)


def add_signal(conn, now, competitor_id, category, title, url, source, origin, published=None, verification=None, summary=None):
    """Record one signal unless this competitor already has this address. Returns True when it was new."""
    return conn.execute(
        "INSERT OR IGNORE INTO competitor_signals (competitor_id, category, title, url, source, origin, published_at, first_seen, verification, summary) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (competitor_id, category, title[:300], url, source, origin, published, iso(now), verification or ("dated" if published else "first_seen"),
         summary)).rowcount == 1


def read_press(conn, now, comp, first):
    """Google News for the competitor's name. Only headlines that name the company are kept, so a word like "gupshup" in passing is not."""
    query = '"{}" when:{}d'.format(comp["name"], 60 if first else 10)
    page, _ = fetch(NEWS.format(urllib.parse.quote(query)))
    added = 0
    name = comp["name"].lower()
    for item in ET.fromstring(page).findall(".//item"):
        title, link = (item.findtext("title") or "").strip(), (item.findtext("link") or "").strip()
        source = item.find("source")
        publisher = (source.text if source is not None else "") or ""
        headline = re.sub(r"\s+-\s+{}$".format(re.escape(publisher)), "", title) if publisher else title
        low = headline.lower()
        if not link or name not in low or any(s in publisher.lower() for s in SKIP_SOURCES):
            continue
        if comp["needs_context"] and not re.search(CONTEXT, low):
            continue
        try:
            when = iso(parsedate_to_datetime(item.findtext("pubDate")).astimezone().replace(tzinfo=None))
        except (TypeError, ValueError):
            when = None
        # an article already recorded, as its own signal or as one more outlet on a story, is never counted again
        if (conn.execute("SELECT 1 FROM competitor_signals WHERE competitor_id = ? AND url = ?", (comp["id"], link)).fetchone()
                or conn.execute("SELECT 1 FROM competitor_seen WHERE source_id = ? AND url = ?", (-comp["id"], link)).fetchone()):
            continue
        # the same announcement is carried by many outlets: it is one signal, with a count of how many covered it
        twin = same_story(conn, comp["id"], headline, when)
        if twin:
            conn.execute("UPDATE competitor_signals SET mentions = mentions + 1 WHERE id = ?", (twin,))
            conn.execute("INSERT OR IGNORE INTO competitor_seen (source_id, url) VALUES (?,?)", (-comp["id"], link))
            continue
        added += add_signal(conn, now, comp["id"], classify(headline), headline, link, publisher or "Press", "press", when)
    return added


def read_page(conn, now, comp, src):
    """One page on the competitor's site. Returns how many signals it gave."""
    page, final = fetch(src["url"])
    added = 0
    if src["kind"] == "pricing":
        mark = hashlib.sha256(page_text(page).encode()).hexdigest()
        if src["fingerprint"] and src["fingerprint"] != mark:
            added += add_signal(conn, now, comp["id"], "pricing", "{}'s pricing page changed".format(comp["name"]),
                                "{}#seen-{}".format(src["url"], now.date().isoformat()), KINDS["pricing"], "site")
        conn.execute("UPDATE competitor_sources SET fingerprint = ? WHERE id = ?", (mark, src["id"]))
        return added
    links = page_links(page, final, src["kind"])
    known = {r["url"] for r in conn.execute("SELECT url FROM competitor_seen WHERE source_id = ?", (src["id"],))}
    fresh = {u: t for u, t in links.items() if u not in known}
    conn.executemany("INSERT OR IGNORE INTO competitor_seen (source_id, url) VALUES (?,?)", [(src["id"], u) for u in fresh])
    if not src["baseline_at"]:
        conn.execute("UPDATE competitor_sources SET baseline_at = ? WHERE id = ?", (iso(now), src["id"]))
        return 0
    if len(fresh) > FLOOD:
        return add_signal(conn, now, comp["id"], KIND_CATEGORY.get(src["kind"], "news"),
                          "{}'s {} page was rebuilt ({} new links)".format(comp["name"], KINDS[src["kind"]].lower(), len(fresh)),
                          "{}#rebuilt-{}".format(src["url"], now.date().isoformat()), KINDS[src["kind"]], "site")
    for url, text in fresh.items():
        fallback = KIND_CATEGORY.get(src["kind"], "news")
        category = fallback if src["kind"] in ("customers", "events", "careers") else classify(text, fallback)
        added += add_signal(conn, now, comp["id"], category, text, url, KINDS[src["kind"]], "site")
    return added


# ------------------------------------------------------------------------------- social pages

NETWORKS = {"linkedin": "LinkedIn", "instagram": "Instagram", "facebook": "Facebook", "x": "X", "youtube": "YouTube"}
APIFY_RUN = "https://api.apify.com/v2/acts/harvestapi~linkedin-company-posts/run-sync-get-dataset-items"
LINKEDIN_HOURS = 20  # LinkedIn is read once a day: every post read is paid for
YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
ATOM = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/"}


def read_youtube(conn, now, acc):
    """A channel's public video feed: its newest videos with their dates, views and likes. Returns how many were new."""
    feed = acc["feed"]
    if not feed:
        found = re.search(r"/channel/(UC[\w-]{20,})", acc["url"]) or re.search(r"feeds/videos\.xml\?channel_id=(UC[\w-]{20,})", fetch(acc["url"])[0])
        if not found:
            raise RivalError("no channel was found at that address")
        feed = found.group(1)
        conn.execute("UPDATE competitor_accounts SET feed = ? WHERE id = ?", (feed, acc["id"]))
    added = 0
    for e in ET.fromstring(fetch(YT_FEED.format(feed))[0]).findall("a:entry", ATOM):
        link, stats, stars = e.find("a:link", ATOM), e.find(".//m:statistics", ATOM), e.find(".//m:starRating", ATOM)
        title, posted = e.findtext("a:title", "", ATOM).strip(), e.findtext("a:published", "", ATOM)
        if link is None or not title or not posted:
            continue
        url = link.get("href")
        thumb = e.find(".//m:thumbnail", ATOM)
        image = thumb.get("url") if thumb is not None else None
        views, likes = (int(x.get(k) or 0) if x is not None else None for x, k in ((stats, "views"), (stars, "count")))
        added += conn.execute(
            "INSERT OR IGNORE INTO competitor_posts (competitor_id, network, url, title, kind, posted_at, first_seen) VALUES (?,?,?,?,?,?,?)",
            (acc["competitor_id"], "youtube", url, title[:300], "Short" if "/shorts/" in url else "Video", posted[:19], iso(now))).rowcount
        conn.execute("UPDATE competitor_posts SET views = ?, likes = ?, image = COALESCE(?, image) WHERE competitor_id = ? AND url = ?",
                     (views, likes, image, acc["competitor_id"], url))
    return added


def first_image(obj, depth=0):
    """The first picture address inside a post's data (image, video thumbnail, document cover), or None."""
    if depth > 4 or obj is None:
        return None
    if isinstance(obj, list):
        return next((x for x in (first_image(v, depth + 1) for v in obj) if x), None)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("https://") and re.search(r"thumbnail|image|poster|cover|media_url|displayurl|^url$", k, re.I) \
                    and re.search(r"\.(jpe?g|png|webp)|/image|media\.licdn|fbcdn|cdninstagram|pbs\.twimg", v, re.I):
                return v
        return next((x for x in (first_image(v, depth + 1) for v in obj.values() if isinstance(v, (dict, list))) if x), None)
    return None


def slug(url):
    found = re.search(r"linkedin\.com/company/([^/?#]+)", url or "", re.I)
    return found.group(1).lower() if found else None


def post_kind(p):
    return next((label for key, label in (("postVideo", "Video"), ("document", "Document"), ("article", "Article"), ("poll", "Poll"), ("repost", "Repost")) if p.get(key)),
                "Image" if p.get("postImages") else "Text")


def linkedin_posts(token, urls, first):
    body = dict(targetUrls=urls, maxPosts=30 if first else 10, postedLimit="month" if first else "week")
    req = urllib.request.Request(APIFY_RUN, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=280) as res:
            items = json.load(res)
    except urllib.error.HTTPError as err:
        raise RivalError("Apify answered with error {}{}".format(err.code, ": the key was not accepted" if err.code == 401 else ""))
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise RivalError("Apify could not be reached ({})".format(getattr(err, "reason", err)))
    return [p for p in items if isinstance(p, dict)] if isinstance(items, list) else []


def read_linkedin(conn, now, force=False):
    """Every competitor's LinkedIn page in one paid read through Apify: the week's posts with their likes and comments.

    A page read for the first time goes back a month. Posts already held get their numbers refreshed.
    """
    accounts = conn.execute("SELECT a.* FROM competitor_accounts a JOIN competitors c ON c.id = a.competitor_id WHERE c.active = 1 AND a.network = 'linkedin'").fetchall()
    fresh = iso(now - timedelta(hours=LINKEDIN_HOURS))
    if not accounts or (not force and all(a["checked_at"] and a["checked_at"] > fresh and not a["note"] for a in accounts)):
        return dict(posts=0, failed=0)
    token = config.setting("APIFY_TOKEN")
    try:
        if not token:
            raise RivalError("the Apify key has not been added")
        added, got = 0, set()
        for first in (True, False):  # new pages need a longer look back than the daily read
            batch = [a for a in accounts if (not a["checked_at"] or not conn.execute(
                "SELECT 1 FROM competitor_posts WHERE competitor_id = ? AND network = 'linkedin' LIMIT 1", (a["competitor_id"],)).fetchone()) == first]
            if not batch:
                continue
            by = {slug(a["url"]): a for a in batch}
            items = linkedin_posts(token, [a["url"] for a in batch], first)
            for missed in set(by) - {slug((p.get("query") or {}).get("targetUrl")) for p in items}:  # a page sometimes drops out of a shared read
                items += linkedin_posts(token, [by[missed]["url"]], first)
            for p in items:
                acc = by.get(slug((p.get("query") or {}).get("targetUrl")))
                url, text, when = p.get("linkedinUrl"), (p.get("content") or "").strip(), (p.get("postedAt") or {}).get("date")
                if not acc or not url or not when:
                    continue
                got.add(acc["id"])
                eng, author = p.get("engagement") or {}, p.get("author") or {}
                title = re.sub(r"\s+", " ", text)[:300] or "({})".format(post_kind(p))
                added += conn.execute(
                    "INSERT OR IGNORE INTO competitor_posts (competitor_id, network, url, title, kind, posted_at, first_seen) VALUES (?,?,?,?,?,?,?)",
                    (acc["competitor_id"], "linkedin", url, title, post_kind(p), when[:19], iso(now))).rowcount
                image = first_image(p.get("postImages")) or first_image({k: p.get(k) for k in ("postVideo", "document", "article", "repost")})
                conn.execute("UPDATE competitor_posts SET likes = ?, comments = ?, image = COALESCE(?, image) WHERE competitor_id = ? AND url = ?",
                             (eng.get("likes"), eng.get("comments"), image, acc["competitor_id"], url))
                followers = re.match(r"([\d,]+) followers", author.get("info") or "")
                if followers and (author.get("universalName") or "").lower() == slug(acc["url"]):
                    conn.execute("UPDATE competitor_accounts SET followers = ? WHERE id = ?", (int(followers.group(1).replace(",", "")), acc["id"]))
        conn.execute("UPDATE competitor_accounts SET checked_at = ?, note = NULL WHERE network = 'linkedin'", (iso(now),))
        conn.commit()
        return dict(posts=added, failed=0)
    except RivalError as err:  # the time of the last good read is left alone, so the next sync tries again
        conn.execute("UPDATE competitor_accounts SET note = ? WHERE network = 'linkedin'", (str(err)[:200],))
        conn.commit()
        return dict(posts=0, failed=len(accounts))


# Instagram, Facebook and X through Apify: (actor, hours between reads, posts per page on a first read and after it).
# Each post read is paid for, so these are read every few days and only the newest few posts are asked for.
APIFY_NETWORKS = {
    "instagram": ("apify~instagram-post-scraper", 70, 12, 6),
    "facebook": ("apify~facebook-posts-scraper", 160, 6, 3),
    "x": ("apidojo~tweet-scraper", 70, 15, 8),
}
HANDLE = {
    "instagram": re.compile(r"instagram\.com/([A-Za-z0-9_.]+)", re.I),
    "facebook": re.compile(r"facebook\.com/([A-Za-z0-9_.\-]+)", re.I),
    "x": re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)", re.I),
}
# The pages each company links to from its own website (October 2026).
SOCIAL_SEED = {
    "Engati": {"instagram": "getengati", "facebook": "getengati", "x": "getengati"},
    "Yellow.ai": {"facebook": "YellowDotAI", "x": "yellowdotai"},
    "Gupshup": {"instagram": "gupshup.ai", "facebook": "gupshupai", "x": "gupshup"},
    "Haptik": {"instagram": "hellohaptik", "facebook": "haptik", "x": "haptik"},
    "Chat360": {"instagram": "chat360_io", "facebook": "chat360.io"},
}
PROFILE = {"instagram": "https://www.instagram.com/{}", "facebook": "https://www.facebook.com/{}", "x": "https://x.com/{}"}


def handle(network, url):
    found = HANDLE[network].search(url or "")
    return found.group(1).strip(".").lower() if found else None


# Added later (19 Oct 2026): pages found after the first round.
SOCIAL_SEED_2 = {
    "Kore.ai": {"instagram": "https://www.instagram.com/kore.ai"},
    "Haptik": {"youtube": "https://www.youtube.com/channel/UCEeT8gTq3PKhbA-vB7k7GiQ"},
}


def seed_more_social(conn):
    """Once each: the Instagram, Facebook and X pages of the known companies, then the ones found later."""
    if db.is_demo(conn):
        return
    if not db.get_setting(conn, "competitor_social_seeded_2"):
        for name, pages in SOCIAL_SEED_2.items():
            row = conn.execute("SELECT id FROM competitors WHERE name = ? AND active = 1", (name,)).fetchone()
            for network, url in pages.items():
                if row:
                    conn.execute("INSERT OR IGNORE INTO competitor_accounts (competitor_id, network, url) VALUES (?,?,?)", (row["id"], network, url))
        db.set_setting(conn, "competitor_social_seeded_2", "1")
    if db.get_setting(conn, "competitor_more_social_seeded"):
        return
    for name, pages in SOCIAL_SEED.items():
        row = conn.execute("SELECT id FROM competitors WHERE name = ? AND active = 1", (name,)).fetchone()
        for network, user in pages.items():
            if row:
                conn.execute("INSERT OR IGNORE INTO competitor_accounts (competitor_id, network, url) VALUES (?,?,?)",
                             (row["id"], network, PROFILE[network].format(user)))
    db.set_setting(conn, "competitor_more_social_seeded", "1")


def apify_run(actor, body):
    token = config.setting("APIFY_TOKEN")
    if not token:
        raise RivalError("the Apify key has not been added")
    req = urllib.request.Request("https://api.apify.com/v2/acts/{}/run-sync-get-dataset-items".format(actor), data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=280) as res:
            items = json.load(res)
    except urllib.error.HTTPError as err:
        raise RivalError("Apify answered with error {}{}".format(err.code, ": the key was not accepted" if err.code == 401 else ""))
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise RivalError("Apify could not be reached ({})".format(getattr(err, "reason", err)))
    return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []


def x_date(text):
    try:
        return datetime.strptime(text, "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None


def apify_posts(network, accounts, first):
    """Ask Apify for the newest posts of these pages. Returns {account id: [post dict]} and the follower counts found."""
    actor, _, many, few = APIFY_NETWORKS[network]
    limit = many if first else few
    by = {handle(network, a["url"]): a for a in accounts}
    out, followers = {a["id"]: [] for a in accounts}, {}
    if network == "instagram":
        items = apify_run(actor, dict(username=list(by), resultsLimit=limit, skipPinnedPosts=True))
        for p in items:
            acc = by.get(handle("instagram", p.get("inputUrl") or "")) or by.get((p.get("ownerUsername") or "").lower())
            if acc and p.get("url") and p.get("timestamp"):
                kind = {"Sidecar": "Carousel"}.get(p.get("type"), p.get("type") or "Post")
                out[acc["id"]].append(dict(url=p["url"], text=p.get("caption"), at=p["timestamp"][:19], kind=kind,
                                           likes=p.get("likesCount"), second=p.get("commentsCount"), views=p.get("videoViewCount"), image=p.get("displayUrl")))
    elif network == "facebook":
        items = apify_run(actor, dict(startUrls=[dict(url=a["url"]) for a in accounts], resultsLimit=limit))
        for p in items:
            acc = by.get(handle("facebook", p.get("inputUrl") or p.get("facebookUrl") or ""))
            when = p.get("time") or (datetime.utcfromtimestamp(p["timestamp"]).isoformat() if p.get("timestamp") else None)
            if acc and p.get("url") and when:
                out[acc["id"]].append(dict(url=p["url"], text=p.get("text"), at=when[:19], kind="Video" if any((m or {}).get("__typename") == "Video" for m in p.get("media") or []) else "Post",
                                           likes=p.get("likes"), second=p.get("shares"), views=None, image=first_image(p.get("media"))))
    else:  # X: one run per account, so one busy account cannot crowd out the rest
        for user, acc in by.items():
            for p in apify_run(actor, dict(twitterHandles=[user], maxItems=limit, sort="Latest")):
                author = p.get("author") or {}
                if (author.get("userName") or "").lower() != user:
                    continue
                if author.get("followers") is not None:
                    followers[acc["id"]] = author["followers"]
                when = x_date(p.get("createdAt"))
                if p.get("url") and when:
                    out[acc["id"]].append(dict(url=p["url"], text=p.get("fullText") or p.get("text"), at=when, kind="Repost" if p.get("isRetweet") else "Post",
                                               likes=p.get("likeCount"), second=p.get("replyCount"), views=p.get("viewCount"),
                                               image=next((m.get("media_url_https") for m in ((p.get("extendedEntities") or {}).get("media") or []) if m.get("media_url_https")), None)))
    return out, followers


def read_apify_network(conn, now, network, force=False):
    _, hours, _, _ = APIFY_NETWORKS[network]
    accounts = conn.execute("SELECT a.* FROM competitor_accounts a JOIN competitors c ON c.id = a.competitor_id WHERE c.active = 1 AND a.network = ?",
                            (network,)).fetchall()
    fresh = iso(now - timedelta(hours=hours))
    due_now = [a for a in accounts if force or not a["checked_at"] or a["checked_at"] <= fresh or a["note"]]
    if not due_now:
        return dict(posts=0, failed=0)
    added = 0
    try:
        for first in (True, False):
            batch = [a for a in due_now if (not a["checked_at"]) == first]
            if not batch:
                continue
            found, followers = apify_posts(network, batch, first)
            for acc in batch:
                for p in found[acc["id"]]:
                    title = re.sub(r"\s+", " ", (p["text"] or "").strip())[:300] or "({})".format(p["kind"])
                    added += conn.execute(
                        "INSERT OR IGNORE INTO competitor_posts (competitor_id, network, url, title, kind, posted_at, first_seen) VALUES (?,?,?,?,?,?,?)",
                        (acc["competitor_id"], network, p["url"], title, p["kind"], p["at"], iso(now))).rowcount
                    conn.execute("UPDATE competitor_posts SET likes = ?, comments = ?, views = ?, image = COALESCE(?, image) WHERE competitor_id = ? AND url = ?",
                                 (p["likes"], p["second"], p["views"], p.get("image"), acc["competitor_id"], p["url"]))
                if acc["id"] in followers:
                    conn.execute("UPDATE competitor_accounts SET followers = ? WHERE id = ?", (followers[acc["id"]], acc["id"]))
                conn.execute("UPDATE competitor_accounts SET checked_at = ?, note = ? WHERE id = ?",
                             (iso(now), None if found[acc["id"]] else "no posts came back: check the page address", acc["id"]))
        conn.commit()
        return dict(posts=added, failed=0)
    except RivalError as err:
        conn.execute("UPDATE competitor_accounts SET note = ? WHERE network = ?", (str(err)[:200], network))
        conn.commit()
        return dict(posts=added, failed=len(due_now))


READERS = {"youtube": read_youtube}


def read_social(conn, now, force=False):
    done = read_linkedin(conn, now, force)
    for network in APIFY_NETWORKS:
        more = read_apify_network(conn, now, network)  # paid per post: read on their own timer, never forced
        done.update(posts=done["posts"] + more["posts"], failed=done["failed"] + more["failed"])
    for acc in conn.execute("SELECT a.* FROM competitor_accounts a JOIN competitors c ON c.id = a.competitor_id WHERE c.active = 1 AND a.network = 'youtube' ORDER BY a.id").fetchall():
        try:
            done["posts"] += READERS[acc["network"]](conn, now, acc)
            conn.execute("UPDATE competitor_accounts SET checked_at = ?, note = NULL WHERE id = ?", (iso(now), acc["id"]))
        except (RivalError, ET.ParseError) as err:
            conn.execute("UPDATE competitor_accounts SET checked_at = ?, note = ? WHERE id = ?", (iso(now), str(err)[:200], acc["id"]))
            done["failed"] += 1
        conn.commit()
    return done


def social(conn, comps, since):
    """Per competitor and network: the page, how much was posted in the period, and the posts themselves."""
    accounts = [dict(r) for r in conn.execute("SELECT id, competitor_id, network, url, checked_at, note, followers FROM competitor_accounts ORDER BY id")]
    posts = [dict(r) for r in conn.execute(
        "SELECT p.* FROM competitor_posts p JOIN competitors c ON c.id = p.competitor_id WHERE c.active = 1 AND p.posted_at >= ? ORDER BY p.posted_at DESC LIMIT 400", (since,))]
    last = {(r["competitor_id"], r["network"]): r["at"] for r in conn.execute("SELECT competitor_id, network, MAX(posted_at) AS at FROM competitor_posts GROUP BY 1, 2")}
    rows = []
    for c in [dict(r) for r in conn.execute("SELECT id, name, own FROM competitors WHERE active = 1 ORDER BY own DESC, sort, id")]:
        for a in (a for a in accounts if a["competitor_id"] == c["id"]):
            mine = [p for p in posts if p["competitor_id"] == c["id"] and p["network"] == a["network"]]
            rows.append(dict(competitor_id=c["id"], name=c["name"], own=c["own"], network=a["network"], url=a["url"], posts=len(mine),
                             views=sum(p["views"] or 0 for p in mine), likes=sum(p["likes"] or 0 for p in mine),
                             comments=sum(p["comments"] or 0 for p in mine), followers=a["followers"], last=last.get((c["id"], a["network"])), note=a["note"]))
    return dict(networks=NETWORKS, accounts=accounts, rows=rows, posts=posts)


def add_account(conn, competitor_id, url):
    network = "youtube" if re.match(r"^https?://(www\.)?youtube\.com/(@|channel/)[\w.-]+", url) else "linkedin" if slug(url) else \
        next((n for n in ("instagram", "facebook", "x") if handle(n, url)), None)
    if not network:
        raise RivalError("Give the address of the page: LinkedIn, Instagram, Facebook, X or a YouTube channel.")
    if network in PROFILE:
        url = PROFILE[network].format(handle(network, url))
    if network == "linkedin":
        url = "https://www.linkedin.com/company/" + slug(url)
        conn.execute("UPDATE competitors SET linkedin = ? WHERE id = ?", (url, competitor_id))
    if not conn.execute("SELECT 1 FROM competitors WHERE id = ? AND active = 1", (competitor_id,)).fetchone():
        raise RivalError("Choose which competitor the page belongs to.")
    conn.execute("INSERT INTO competitor_accounts (competitor_id, network, url) VALUES (?,?,?) "
                 "ON CONFLICT (competitor_id, network) DO UPDATE SET url = excluded.url, feed = NULL, note = NULL, checked_at = NULL", (competitor_id, network, url))


def remove_account(conn, account_id):
    acc = conn.execute("SELECT competitor_id, network FROM competitor_accounts WHERE id = ?", (account_id,)).fetchone()
    if acc:
        conn.execute("DELETE FROM competitor_posts WHERE competitor_id = ? AND network = ?", tuple(acc))
        conn.execute("DELETE FROM competitor_accounts WHERE id = ?", (account_id,))


def due(conn, now):
    last = db.get_setting(conn, "competitors_synced_at")
    if conn.execute("SELECT 1 FROM competitor_accounts WHERE checked_at IS NULL AND note IS NULL LIMIT 1").fetchone():
        return True  # a social page that has never been read is read straight away
    return bool(conn.execute("SELECT 1 FROM competitors WHERE active = 1 AND own = 0 LIMIT 1").fetchone()) and (
        not last or now - datetime.fromisoformat(last) >= timedelta(hours=EVERY_HOURS))


def sync(conn, now, force=False):
    """Read every feed. One page failing never stops the rest; each page records how its last read went.

    force also reads LinkedIn again even when it was read today (the "Read all now" button)."""
    done = dict(signals=0, pages=0, failed=0)
    for comp in conn.execute("SELECT * FROM competitors WHERE active = 1 AND own = 0 ORDER BY sort, id").fetchall():
        try:
            done["signals"] += read_press(conn, now, comp, first=not comp["press_at"])
            conn.execute("UPDATE competitors SET press_at = ?, press_note = NULL WHERE id = ?", (iso(now), comp["id"]))
        except (RivalError, ET.ParseError) as err:
            conn.execute("UPDATE competitors SET press_note = ? WHERE id = ?", (str(err)[:200], comp["id"]))
            done["failed"] += 1
        for src in conn.execute("SELECT * FROM competitor_sources WHERE competitor_id = ? ORDER BY id", (comp["id"],)).fetchall():
            done["pages"] += 1
            try:
                done["signals"] += read_page(conn, now, comp, src)
                conn.execute("UPDATE competitor_sources SET checked_at = ?, note = NULL WHERE id = ?", (iso(now), src["id"]))
            except RivalError as err:
                conn.execute("UPDATE competitor_sources SET checked_at = ?, note = ? WHERE id = ?", (iso(now), str(err)[:200], src["id"]))
                done["failed"] += 1
        conn.commit()
    seen = read_social(conn, now, force)
    done.update(posts=seen["posts"], pages=done["pages"] + len(conn.execute("SELECT 1 FROM competitor_accounts").fetchall()), failed=done["failed"] + seen["failed"])
    db.set_setting(conn, "competitors_synced_at", iso(now))
    conn.commit()
    return done


_reading = threading.Lock()


def sync_in_background():
    """Start a full read without making the screen wait for it. False when one is already running."""
    if not _reading.acquire(blocking=False):
        return False

    def run():
        conn = db.connect()
        try:
            sync(conn, datetime.now().replace(microsecond=0), force=True)
        except Exception as err:
            conn.rollback()
            print("Competitor read:", err)
        finally:
            conn.close()
            _reading.release()
            try:
                from . import backup
                backup.changed()
            except Exception:
                pass
    threading.Thread(target=run, name="meridian-competitors", daemon=True).start()
    return True


# ------------------------------------------------------------------------------- the weekly watch's findings

WATCH_CATEGORY = {"product": "product", "pricing": "pricing", "customer": "customers", "customers": "customers", "partnership": "partnership",
                  "partnerships": "partnership", "funding": "funding", "news_people": "hiring", "people": "hiring", "hiring": "hiring",
                  "event": "events", "events": "events", "content": "content"}


def take_findings(conn, now, data):
    """Add a weekly competitor-watch findings file. Checked findings and unverified leads are kept apart."""
    if not isinstance(data, dict) or "observations" not in data or "run" not in data:
        raise RivalError("This is not a competitor-watch findings file (it should have “run” and “observations”).")
    ids = {r["name"].lower(): r["id"] for r in conn.execute("SELECT id, name FROM competitors")}
    run = (data.get("run") or {}).get("run_id") or "weekly watch"
    added = skipped = 0
    for o in data.get("observations") or []:
        cid = ids.get((o.get("competitor") or "").lower())
        if not cid or not o.get("source_url"):
            skipped += 1
            continue
        when = (o.get("publication_date") or {}).get("value") if isinstance(o.get("publication_date"), dict) else o.get("publication_date")
        summary = (o.get("factual_summary") or "").strip()
        title = summary.split(". ")[0][:200] or "Finding {}".format(o.get("finding_id") or "")
        # a checked finding replaces what the automatic feeds knew about the same address
        conn.execute("DELETE FROM competitor_signals WHERE competitor_id = ? AND url = ? AND origin <> 'watch'", (cid, o["source_url"]))
        category = WATCH_CATEGORY.get((o.get("category") or "").lower(), "news")
        url = o["source_url"]
        if conn.execute("SELECT 1 FROM competitor_signals WHERE competitor_id = ? AND url = ? AND category <> ?", (cid, url, category)).fetchone():
            url += "#" + category  # one release can carry two findings (a launch and its price): both are kept
        added += add_signal(conn, now, cid, category, title, url, run, "watch",
                            (when + "T00:00:00") if when and len(when) == 10 else when, "verified", summary)
    for lead in data.get("unverified_leads") or []:
        cid = ids.get((lead.get("competitor") or "").lower())
        if not cid or not lead.get("post_url"):
            skipped += 1
            continue
        where = "LinkedIn post" if "linkedin.com" in lead["post_url"] else "Lead"
        added += add_signal(conn, now, cid, "content", "{} found by search, not read".format(where), lead["post_url"], run, "watch", None, "lead", lead.get("note"))
    return dict(added=added, skipped=skipped, run=run)


# ------------------------------------------------------------------------------- what the screen shows

def view(conn, now, days=30):
    days = days if days in (7, 30, 90) else 30
    since = iso(now - timedelta(days=days))
    comps = [dict(r) for r in conn.execute("SELECT * FROM competitors WHERE active = 1 AND own = 0 ORDER BY sort, id")]
    signals = [dict(r) for r in conn.execute(
        "SELECT s.*, COALESCE(s.published_at, s.first_seen) AS at FROM competitor_signals s JOIN competitors c ON c.id = s.competitor_id "
        "WHERE c.active = 1 AND s.hidden = 0 AND COALESCE(s.published_at, s.first_seen) >= ? ORDER BY at DESC LIMIT 600", (since,))]
    matrix = {c["id"]: {k: 0 for k in CATEGORIES} for c in comps}
    for s in signals:
        if s["verification"] != "lead" and s["competitor_id"] in matrix:
            matrix[s["competitor_id"]][s["category"] if s["category"] in CATEGORIES else "news"] += 1
    # twelve weeks of activity per competitor, whatever period is chosen, so a quiet or busy stretch is visible
    start = (now - timedelta(days=now.weekday(), weeks=11)).date()
    weeks = [(start + timedelta(weeks=i)).isoformat() for i in range(12)]
    weekly = {c["id"]: [0] * 12 for c in comps}
    for r in conn.execute("SELECT competitor_id, substr(COALESCE(published_at, first_seen), 1, 10) AS d FROM competitor_signals "
                          "WHERE hidden = 0 AND verification <> 'lead' AND COALESCE(published_at, first_seen) >= ?", (start.isoformat(),)):
        if r["competitor_id"] in weekly:
            at = (datetime.fromisoformat(r["d"]).date() - start).days // 7
            if 0 <= at < 12:
                weekly[r["competitor_id"]][at] += 1
    for c in comps:
        stem = c["domain"].split(".")[0]
        seo = conn.execute("SELECT competitor, common, keywords, traffic FROM semrush_competitors WHERE competitor LIKE ? ORDER BY day DESC, keywords DESC LIMIT 1",
                           (stem + ".%",)).fetchone()
        sources = [dict(r) for r in conn.execute("SELECT id, kind, url, checked_at, note, baseline_at FROM competitor_sources WHERE competitor_id = ? ORDER BY id", (c["id"],))]
        last = {r["category"]: r["at"] for r in conn.execute(
            "SELECT category, MAX(COALESCE(published_at, first_seen)) AS at FROM competitor_signals WHERE competitor_id = ? AND hidden = 0 "
            "AND verification <> 'lead' GROUP BY category", (c["id"],))}
        c.update(counts=matrix[c["id"]], total=sum(matrix[c["id"]].values()), weekly=weekly[c["id"]], sources=sources, last=last,
                 seo=dict(seo) if seo else None, failing=sum(1 for s in sources if s["note"]) + (1 if c["press_note"] else 0))
    return dict(days=days, competitors=comps, signals=signals, social=social(conn, comps, since), categories=CATEGORIES, kinds=KINDS, weeks=weeks,
                synced_at=db.get_setting(conn, "competitors_synced_at"), every_hours=EVERY_HOURS)


# ------------------------------------------------------------------------------- changes made on the screen

def add_competitor(conn, name, domain, linkedin=None):
    name = (name or "").strip()
    domain = re.sub(r"^https?://(www\.)?", "", (domain or "").strip().lower()).strip("/")
    if not name or not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        raise RivalError("A name and a website address like example.com are needed.")
    if conn.execute("SELECT 1 FROM competitors WHERE lower(name) = ? AND active = 1", (name.lower(),)).fetchone():
        raise RivalError("{} is already on the list.".format(name))
    conn.execute("INSERT INTO competitors (name, domain, linkedin, sort) VALUES (?,?,?, (SELECT COALESCE(MAX(sort), 0) + 1 FROM competitors))",
                 (name, domain, (linkedin or "").strip() or None))
    if slug(linkedin):
        add_account(conn, conn.execute("SELECT MAX(id) FROM competitors").fetchone()[0], linkedin.strip())


def add_source(conn, competitor_id, kind, url):
    url = (url or "").strip()
    if any(site in url.lower() for site in ("youtube.com", "linkedin.com", "instagram.com", "facebook.com", "twitter.com", "x.com/")):
        return add_account(conn, competitor_id, url)
    if kind not in KINDS or not re.match(r"^https?://[^\s]+\.[^\s]+$", url):
        raise RivalError("Choose what kind of page it is and give its full address.")
    if not conn.execute("SELECT 1 FROM competitors WHERE id = ? AND active = 1", (competitor_id,)).fetchone():
        raise RivalError("Choose which competitor the page belongs to.")
    conn.execute("INSERT INTO competitor_sources (competitor_id, kind, url) VALUES (?,?,?)", (competitor_id, kind, url))


def remove_source(conn, source_id):
    conn.execute("DELETE FROM competitor_seen WHERE source_id = ?", (source_id,))
    conn.execute("DELETE FROM competitor_sources WHERE id = ?", (source_id,))


def hide(conn, signal_id, hidden=True):
    conn.execute("UPDATE competitor_signals SET hidden = ? WHERE id = ?", (1 if hidden else 0, signal_id))


def main(argv):
    from . import zoho
    command = argv[0] if argv else ""
    if command not in ("sync", "status"):
        sys.exit(__doc__)
    conn = zoho.live_database()
    seed(conn)
    seed_social(conn)
    seed_linkedin(conn)
    seed_own(conn)
    seed_more_social(conn)
    conn.commit()
    if command == "sync":
        done = sync(conn, datetime.now().replace(microsecond=0))
        print("Read {} pages: {} new signals, {} could not be read.".format(done["pages"], done["signals"], done["failed"]))
    for c in conn.execute("SELECT c.name, (SELECT COUNT(*) FROM competitor_sources s WHERE s.competitor_id = c.id) AS pages, "
                          "(SELECT COUNT(*) FROM competitor_signals g WHERE g.competitor_id = c.id) AS signals FROM competitors c WHERE active = 1 AND own = 0 ORDER BY sort"):
        print("  {}: {} pages watched, {} signals".format(c["name"], c["pages"], c["signals"]))
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])

"""Build the database.

    python -m meridian.seed            sample data (replaces an existing sample database)
    python -m meridian.seed --empty    an empty database, ready for real data
    add --force to replace a database that already holds real data

The sample data is the design's made-up company (an AP-automation business, shown under our own name) as of
Thursday 24 Sep 2026, 13:00. Headline figures are fixed (812 leads, 214 qualified, $48,620 spend,
46 deals, 11 won for 1-24 Sep) and every row is generated so the screens add up to them.
"""

import math
import os
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import alerts, config, db, money, narrative, scoring
from .alloc import matrix, split
from .periods import iso

NOW = datetime(2026, 9, 24, 13, 0, 0)
RNG = random.Random(7)

CHANNELS = [
    ("search", "Search", "organic", "oklch(0.60 0.11 165)", "organic search"),
    ("direct", "Direct", "organic", "oklch(0.74 0.09 178)", "direct traffic"),
    ("referral", "Referral", "organic", "oklch(0.48 0.08 196)", "referrals"),
    ("social", "Organic social", "organic", "oklch(0.83 0.08 150)", "organic social"),
    ("meta", "Meta ads", "paid", "oklch(0.55 0.13 262)", "Meta ads"),
    ("li", "LinkedIn ads", "paid", "oklch(0.73 0.10 245)", "LinkedIn ads"),
    ("apollo", "Email · Apollo", "outbound", "oklch(0.66 0.13 48)", "Apollo email"),
    ("heyreach", "LinkedIn · HeyReach", "outbound", "oklch(0.81 0.10 80)", "HeyReach outreach"),
]
ORDER = [c[0] for c in CHANNELS]
OWNERS = ["Priya Raman", "Tom Becker", "Lena Ortiz"]


def days(a, b):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


SEP = days(date(2026, 9, 1), date(2026, 9, 24))
AUG = days(date(2026, 8, 1), date(2026, 8, 24))
AUG_REST = days(date(2026, 8, 25), date(2026, 8, 31))


def weekend(d):
    return d.weekday() >= 5


def wts(ds, weekday=1.0, wkend=0.45):
    return [wkend if weekend(d) else weekday for d in ds]


def wavy(ds, phase=0.0):
    """Weekday/weekend pattern with a gentle day-to-day ripple, so traffic lines do not look ruled."""
    return [w * (1 + 0.06 * math.sin(d.toordinal() * 1.3 + phase)) for d, w in zip(ds, wts(ds))]


def insert(conn, table, rows):
    if not rows:
        return
    cols = list(rows[0].keys())
    conn.executemany(
        "INSERT INTO {} ({}) VALUES ({})".format(table, ", ".join(cols), ", ".join("?" for _ in cols)),
        [[r[c] for c in cols] for r in rows],
    )


# --------------------------------------------------------------------------- leads

SEP_DAILY = [41, 43, 40, 35, 12, 10, 44, 46, 45, 42, 36, 13, 11, 50, 52, 48, 46, 34, 12, 10, 41, 39, 39, 23]
SEP_17_AM = 27  # leads by 13:00 on the 17th: "same point last week" for today's 23

# Per channel, in ORDER. Month = this week (A) + last week to the same point (B) + the rest (C).
MONTH, MONTH_Q = [186, 74, 41, 52, 168, 121, 108, 62], [61, 22, 18, 9, 26, 38, 24, 16]
WEEK_A, WEEK_A_Q = [21, 13, 8, 9, 31, 24, 23, 13], [6, 4, 3, 1, 5, 8, 6, 4]
WEEK_B, WEEK_B_Q = [52, 16, 9, 10, 30, 25, 22, 13], [15, 5, 4, 2, 4, 7, 3, 2]
AUG_TOTAL, AUG_Q = [172, 70, 38, 51, 152, 110, 96, 55], [54, 20, 16, 8, 23, 34, 19, 13]

Q_BINS = [(65, 69, 44), (70, 79, 96), (80, 89, 56), (90, 97, 18)]
U_BINS = [(4, 9, 14), (10, 19, 42), (20, 29, 78), (30, 39, 109), (40, 49, 128), (50, 59, 139), (60, 64, 88)]

FIRST = ["Aaron", "Abena", "Aditi", "Alicia", "Amara", "Andre", "Anika", "Beatriz", "Ben", "Bianca", "Callum",
         "Carmen", "Chen", "Claire", "Dara", "David", "Deepak", "Elif", "Emeka", "Erin", "Farah", "Felix",
         "Grace", "Hana", "Hugo", "Imani", "Ingrid", "Ivan", "Jamal", "Jasmine", "Jonas", "Julia", "Karan",
         "Kate", "Kofi", "Laila", "Leo", "Lucia", "Malik", "Marco", "Mei", "Nadia", "Naveen", "Nora", "Oscar",
         "Paolo", "Rafael", "Rhea", "Rosa", "Sara", "Sean", "Simone", "Tariq", "Tessa", "Victor", "Wei",
         "Yara", "Yusuf", "Zoe"]
LAST = ["Abbott", "Acheampong", "Alvarez", "Bauer", "Bose", "Brennan", "Castillo", "Chaudhry", "Coleman",
        "Costa", "Dalton", "Demir", "Eriksen", "Farouk", "Fischer", "Gallagher", "Gupta", "Hale", "Hoang",
        "Ibrahim", "Jensen", "Kapoor", "Kowalski", "Lambert", "Lindgren", "Madsen", "Mbeki", "Morales",
        "Nakamura", "Novak", "Obi", "Olsen", "Park", "Petrov", "Quinn", "Rahman", "Reyes", "Rossi", "Sato",
        "Schmidt", "Sharp", "Silva", "Tanaka", "Thackeray", "Udoka", "Vargas", "Walsh", "Yilmaz", "Zhou"]
CO_A = ["North", "Silver", "Iron", "Blue", "Stone", "Harbor", "Cedar", "Summit", "Red", "Lake", "Maple",
        "Granite", "Copper", "Bay", "Fox", "Oak", "Pine", "River", "Sun", "West", "East", "High", "Clear",
        "Gold", "Elm", "Ash", "Mill", "Kings", "Fair", "Glen"]
CO_B = ["field", "gate", "ridge", "line", "brook", "well", "mont", "crest", "wood", "haven", "view", "ford",
        "point", "vale", "path", "bridge", "mark", "shore", "port", "wick"]
INDUSTRY_SUFFIX = {
    "Logistics": ["Logistics", "Freight", "Transport"], "Healthcare": ["Health", "Clinics", "Medical Group"],
    "Manufacturing": ["Manufacturing", "Industries", "Works"], "Construction": ["Construction", "Builders"],
    "Energy": ["Energy", "Power"], "Retail": ["Retail Group", "Stores"], "Software": ["Software", "Labs"],
    "Insurance": ["Insurance", "Mutual"], "Food & beverage": ["Foods", "Provisions"],
    "Financial services": ["Capital", "Advisors"], "Education": ["Academy", "Learning"],
    "Hospitality": ["Hotels", "Hospitality"],
}
PRIORITY = ["Logistics", "Healthcare", "Manufacturing", "Construction", "Energy"]
OTHER = ["Retail", "Software", "Insurance", "Food & beverage", "Financial services", "Education", "Hospitality"]
CITIES = ["Columbus, OH", "Nashville, TN", "Austin, TX", "Seattle, WA", "Phoenix, AZ", "Grand Rapids, MI",
          "Hartford, CT", "Denver, CO", "Houston, TX", "Boston, MA", "Charlotte, NC", "San Diego, CA",
          "Chicago, IL", "Atlanta, GA", "Minneapolis, MN", "Portland, OR", "Kansas City, MO", "Tampa, FL",
          "Salt Lake City, UT", "Pittsburgh, PA", "Raleigh, NC", "Milwaukee, WI"]
SENIOR = ["CFO", "VP Finance", "Controller", "Director of Finance", "Head of Finance Ops", "Finance Manager",
          "AP Manager", "Director, Accounts Payable"]
JUNIOR = ["AP Specialist", "Accounting Clerk", "Operations Analyst", "Office Manager", "Bookkeeper",
          "Staff Accountant", "Finance Intern", "Consultant"]

SEARCHES = ["ap automation software", "invoice approval workflow", "three way matching",
            "accounts payable automation", "ap automation for logistics"]
PARTNERS = ["NetSuite consultant", "Sage reseller", "accounting firm newsletter", "ERP integration partner"]
UTM = {"search": ("google", "organic"), "direct": ("(direct)", "(none)"), "referral": ("partner", "referral"),
       "social": ("linkedin", "social"), "meta": ("facebook", "paid"), "li": ("linkedin", "paid"),
       "apollo": ("apollo", "email"), "heyreach": ("heyreach", "linkedin_dm")}

# id order matters: these are the twelve leads the design shows.
NAMED = [
    dict(name="Daniel Okafor", title="VP Finance", company="Brightwater Logistics", ch="li", owner="Priya Raman",
         status="Meeting booked", score=82, created="2026-09-17T11:26:00", updated="2026-09-24T10:12:00",
         last=("Status changed", "2026-09-24T10:12:00"), employees=420, revenue=96e6, industry="Logistics",
         hq="Columbus, OH", website="brightwater.io", founded=2009,
         ft=("search", "2026-08-29T10:05:00", "Searched “ap automation for logistics”, read “Three-way matching, explained”"),
         lt=("li", "2026-09-17T11:26:00", "Ad “Close the books 5 days faster” → demo request")),
    dict(name="Maren Holt", title="Director, Revenue Cycle", company="Corvane Health", ch="search", owner="Tom Becker",
         status="Qualified", score=76, created="2026-09-23T12:20:00", updated="2026-09-23T16:00:00",
         last=("Viewed pricing", "2026-09-24T12:20:00"), employees=1150, revenue=210e6, industry="Healthcare",
         hq="Nashville, TN", website="corvane.com", founded=2004,
         ft=("search", "2026-09-23T12:02:00", "Searched “invoice approval workflow”"),
         lt=("search", "2026-09-23T12:20:00", "Pricing page → contact form")),
    dict(name="Arjun Mehta", title="Head of Finance Ops", company="Tessellate Foods", ch="apollo", owner="Priya Raman",
         status="New", score=58, created="2026-09-24T09:00:00", updated=None,
         last=("Replied to step 3", "2026-09-24T09:00:00"), employees=260, revenue=54e6, industry="Food & beverage",
         hq="Austin, TX", website="tessellatefoods.com", founded=2014,
         ft=("apollo", "2026-09-15T08:10:00", "Sequence “Finance Ops · Mid-market”, step 1"),
         lt=("apollo", "2026-09-24T09:00:00", "Replied to step 3: “Send me a short demo”")),
    dict(name="Sofia Lindqvist", title="CFO", company="Nordhavn Freight", ch="heyreach", owner="Lena Ortiz",
         status="Contacted", score=71, created="2026-09-21T10:15:00", updated="2026-09-22T11:00:00",
         last=("Accepted connection", "2026-09-23T12:30:00"), employees=310, revenue=72e6, industry="Logistics",
         hq="Seattle, WA", website="nordhavn.com", founded=2011,
         ft=("heyreach", "2026-09-14T09:40:00", "Connection request, campaign “CFOs · Freight & logistics”"),
         lt=("heyreach", "2026-09-21T10:15:00", "Replied to message 2, asked for case study")),
    dict(name="Gabriel Ruiz", title="AP Specialist", company="Halcyon Retail Group", ch="meta", owner="Tom Becker",
         status="Unqualified", score=31, created="2026-09-22T11:40:00", updated="2026-09-22T15:00:00",
         last=("Downloaded ebook", "2026-09-22T11:40:00"), employees=85, revenue=12e6, industry="Retail",
         hq="Phoenix, AZ", website="halcyonretail.com", founded=2017,
         ft=("meta", "2026-09-22T11:32:00", "Lead ad “AP month-end checklist”"),
         lt=("meta", "2026-09-22T11:40:00", "Ebook download via lead form")),
    dict(name="Chloe Barrett", title="Controller", company="Fernway Manufacturing", ch="referral", owner="Lena Ortiz",
         status="Qualified", score=79, created="2026-09-19T10:30:00", updated="2026-09-23T12:00:00",
         last=("Demo held", "2026-09-23T12:00:00"), employees=640, revenue=138e6, industry="Manufacturing",
         hq="Grand Rapids, MI", website="fernway.com", founded=1998,
         ft=("referral", "2026-09-19T10:12:00", "Partner link from NetSuite consultant"),
         lt=("referral", "2026-09-19T10:30:00", "Demo request form")),
    dict(name="Kenji Watanabe", title="Finance Manager", company="Aldermoor Insurance", ch="li", owner="Priya Raman",
         status="Contacted", score=68, created="2026-09-16T12:00:00", updated=None,
         last=("Document ad → gated guide", "2026-09-16T12:00:00"), employees=520, revenue=160e6, industry="Insurance",
         hq="Hartford, CT", website="aldermoor.com", founded=1987,
         ft=("li", "2026-09-10T15:20:00", "Ad “Approve invoices from Slack”"),
         lt=("li", "2026-09-16T12:00:00", "Document ad → gated guide")),
    dict(name="Hannah Weiss", title="Practice Ops Lead", company="Pinecrest Dental Partners", ch="meta", owner="Tom Becker",
         status="New", score=44, created="2026-09-24T07:00:00", updated=None,
         last=("Form submitted", "2026-09-24T07:00:00"), employees=190, revenue=31e6, industry="Healthcare",
         hq="Denver, CO", website="pinecrestdental.com", founded=2015,
         ft=("meta", "2026-09-20T19:05:00", "Retargeting ad, pricing visitors"),
         lt=("meta", "2026-09-24T07:00:00", "Lead form “See it in 2 minutes”")),
    dict(name="Omar Haddad", title="VP Finance", company="Saltmarsh Energy", ch="direct", owner="Lena Ortiz",
         status="Qualified", score=74, created="2026-09-22T09:30:00", updated="2026-09-23T10:00:00",
         last=("Opened proposal", "2026-09-24T10:00:00"), employees=880, revenue=245e6, industry="Energy",
         hq="Houston, TX", website="saltmarsh.energy", founded=2006,
         ft=("direct", "2026-09-08T14:00:00", "Direct visit, homepage"),
         lt=("direct", "2026-09-22T09:30:00", "Contact sales form")),
    dict(name="Elena Popescu", title="Operations Analyst", company="Quarry Lane Analytics", ch="social", owner="Tom Becker",
         status="New", score=39, created="2026-09-23T11:00:00", updated=None,
         last=("Webinar signup", "2026-09-23T11:00:00"), employees=45, revenue=6e6, industry="Software",
         hq="Boston, MA", website="quarrylane.io", founded=2020,
         ft=("social", "2026-09-23T10:48:00", "LinkedIn company post, webinar"),
         lt=("social", "2026-09-23T11:00:00", "Webinar registration")),
    dict(name="Marcus Freeman", title="CFO", company="Ironbridge Construction", ch="apollo", owner="Priya Raman",
         status="Meeting booked", score=77, created="2026-09-13T10:00:00", updated="2026-09-22T13:00:00",
         last=("Meeting set for 29 Sep", "2026-09-22T13:00:00"), employees=730, revenue=190e6, industry="Construction",
         hq="Charlotte, NC", website="ironbridge.build", founded=2001,
         ft=("apollo", "2026-09-02T08:05:00", "Sequence “CFO · Construction”, step 1"),
         lt=("apollo", "2026-09-13T10:00:00", "Replied to step 2, booked via Calendly")),
    dict(name="Isabel Moreno", title="Revenue Ops Manager", company="Vantage Clinics", ch="search", owner="Lena Ortiz",
         status="Contacted", score=63, created="2026-09-20T11:00:00", updated=None,
         last=("Free trial signup", "2026-09-20T11:00:00"), employees=340, revenue=48e6, industry="Healthcare",
         hq="San Diego, CA", website="vantageclinics.com", founded=2012,
         ft=("search", "2026-09-12T16:30:00", "Searched “ap automation software”"),
         lt=("search", "2026-09-20T11:00:00", "Free trial signup")),
]

# Daniel's score breakdown and history, as designed. Reminder entries are added with the reminders.
def daniel_items():
    return [("size", 18 / 20, "420 employees · ICP is 200–2,000"), ("industry", 1.0, "Logistics · priority vertical"),
            ("revenue", 12 / 15, "{} · ICP is {}".format(money.money_short(96e6), scoring.revenue_range())),
            ("demo", 1.0, "Submitted 17 Sep"), ("pricing", 10 / 15, "3 visits in 14 days"),
            ("email", 7 / 15, "Opened 2 of 4 emails, no clicks")]


DANIEL_EVENTS = [
    ("2026-09-24T10:12:00", "crm", None, "Status → Meeting booked", "Priya Raman set a demo for 29 Sep, 14:00"),
    ("2026-09-22T16:41:00", "touch", "direct", "Visited pricing page", "Third visit · 2 pages · 3m 40s"),
    ("2026-09-17T11:26:00", "touch", "li", "Demo request · lead created", "LinkedIn ad “Close the books 5 days faster”"),
    ("2026-09-12T08:03:00", "touch", "li", "Clicked LinkedIn ad", "Campaign “CFO – AP Automation – Q3”"),
    ("2026-09-09T07:51:00", "touch", "apollo", "Opened email", "Apollo · “Finance Ops · Mid-market”, step 2"),
    ("2026-09-03T14:20:00", "touch", "direct", "Direct visit", "Pricing, Customers · 4m 12s"),
    ("2026-08-29T10:05:00", "touch", "search", "First visit from search", "“ap automation for logistics” → blog"),
]


def rand_time(part):
    lo, hi = {"am": (7 * 60, 12 * 60 + 55), "pm": (13 * 60 + 5, 21 * 60)}.get(part, (7 * 60, 21 * 60))
    m = RNG.randint(lo, hi)
    return time(m // 60, m % 60, RNG.randint(0, 59))


def lead_block(rows, col_totals, q_totals):
    """rows [(date, part, n)] -> lead slots with a channel and a qualified flag, matching all totals."""
    counts = matrix([r[2] for r in rows], col_totals, RNG, jitter=0.5)
    slots = []
    for (d, part, _), row in zip(rows, counts):
        for ci, n in enumerate(row):
            slots += [{"date": d, "part": part, "ch": ORDER[ci], "q": False} for _ in range(n)]
    for ci, q in enumerate(q_totals):
        for s in RNG.sample([s for s in slots if s["ch"] == ORDER[ci]], q):
            s["q"] = True
    return slots


def score_pool(bins, counts):
    scores = [RNG.randint(lo, hi) for (lo, hi, _), n in zip(bins, counts) for _ in range(n)]
    RNG.shuffle(scores)
    return scores


def bin_index(bins, score):
    return next(i for i, (lo, hi, _) in enumerate(bins) if lo <= score <= hi)


def gen_items(score, lead):
    """Spread a target score across the six criteria (the design's method), as fractions of each maximum."""
    f = score / 100.0
    hi = score >= 65
    spec = [("size", 20, 1.05, "{:,} employees".format(lead["employees"])),
            ("industry", 15, 1.10, lead["industry"]),
            ("revenue", 15, 0.95, money.money_short(lead["revenue"])),
            ("demo", 20, 0.95, "Submitted" if hi else "Not yet"),
            ("pricing", 15, 0.90, "2 visits in 14 days" if hi else "No visits"),
            ("email", 15, 1.00, "Opened 3 of 5" if score >= 50 else "Opened 1 of 5")]
    pts = [max(0, min(mx, int(mx * f * j + 0.5))) for _, mx, j, _ in spec]
    diff = score - sum(pts)
    for i, (_, mx, _, _) in enumerate(spec):
        if not diff:
            break
        step = min(diff, mx - pts[i]) if diff > 0 else max(diff, -pts[i])
        pts[i] += step
        diff -= step
    return [(key, p / mx, why) for (key, mx, _, why), p in zip(spec, pts)]


class Names:
    def __init__(self):
        self.people, self.companies = {n["name"] for n in NAMED}, {n["company"] for n in NAMED}
        self.firsts = []

    def person(self):
        while True:
            if not self.firsts:  # deal first names like a shuffled deck so none clusters
                self.firsts = RNG.sample(FIRST, len(FIRST))
            name = self.firsts.pop() + " " + RNG.choice(LAST)
            if name not in self.people:
                self.people.add(name)
                return name

    def company(self, industry):
        while True:
            name = RNG.choice(CO_A) + RNG.choice(CO_B) + " " + RNG.choice(INDUSTRY_SUFFIX[industry])
            if name not in self.companies:
                self.companies.add(name)
                return name


def touches(ch, created, ads, seqs):
    """First and last touch for a generated lead: (channel, datetime, detail) each."""
    def back(lo, hi):
        return created - timedelta(days=RNG.randint(lo, hi), minutes=RNG.randint(5, 600))

    if ch == "search":
        return (ch, back(0, 10), "Searched “{}”".format(RNG.choice(SEARCHES))), \
               (ch, created, RNG.choice(["Demo request form", "Contact sales form", "Free trial signup", "Guide download"]))
    if ch == "direct":
        return (ch, back(0, 8), "Direct visit, homepage"), (ch, created, RNG.choice(["Contact sales form", "Demo request form"]))
    if ch == "referral":
        return (ch, back(0, 1), "Partner link from " + RNG.choice(PARTNERS)), (ch, created, "Demo request form")
    if ch == "social":
        return (ch, back(0, 3), "LinkedIn company post"), (ch, created, RNG.choice(["Webinar registration", "Newsletter signup"]))
    if ch in ("meta", "li"):
        headline = RNG.choice(ads[ch])
        last = "Lead form “{}”".format(headline) if ch == "meta" else RNG.choice(["Demo request", "Document ad → gated guide"])
        return (ch, back(0, 6), "Ad “{}”".format(headline)), (ch, created, last)
    name = RNG.choice(seqs[ch])
    if ch == "apollo":
        return (ch, back(3, 10), "Sequence “{}”, step 1".format(name)), (ch, created, "Replied to step {}".format(RNG.randint(2, 4)))
    return (ch, back(3, 9), "Connection request, campaign “{}”".format(name)), (ch, created, "Replied to message 2")


def status_for(score, created, cutoff):
    """Status and last owner update for a generated lead, as things stood at `cutoff`."""
    q = score >= 65
    gap = (cutoff.date() - created.date()).days
    age = (cutoff - created).total_seconds() / 86400
    r = RNG.random()
    if age < 1:
        status = "New" if r < 0.7 else "Contacted"
    elif gap < 3:
        if q:
            status = "Contacted" if r < 0.45 else "Qualified" if r < 0.8 else "Meeting booked" if r < 0.9 else "New"
        else:
            status = "Contacted" if r < 0.5 else "Unqualified" if r < 0.8 else "New"
    else:
        open_share = 0.05 if gap > 14 else 0.2
        if q:
            status = "Contacted" if r < open_share else "Qualified" if r < 0.6 else "Meeting booked"
        else:
            status = "Contacted" if r < open_share else "Unqualified"

    if status == "New":
        return status, None
    if status == "Contacted" and gap >= 3:  # still open, so the owner must have touched it recently
        lo = max(created, cutoff - timedelta(days=2))
    else:
        lo = created + timedelta(minutes=30)
    hi = min(cutoff, created + timedelta(days=4)) if status != "Contacted" else cutoff
    lo = min(lo, hi)
    return status, lo + timedelta(seconds=RNG.randint(0, max(1, int((hi - lo).total_seconds()))))


LAST_ACTIVITY = {"New": ["Form submitted", "Replied", "Signed up"], "Contacted": ["Call logged", "Email sent"],
                 "Qualified": ["Status changed", "Demo held", "Opened proposal"],
                 "Meeting booked": ["Meeting set", "Status changed"], "Unqualified": ["Marked unqualified"]}


def make_lead(slot, score, names, ads, seqs, cutoff):
    created = datetime.combine(slot["date"], rand_time(slot["part"]))
    ch = slot["ch"]
    if score >= 55:
        industry = RNG.choice(PRIORITY) if RNG.random() < 0.8 else RNG.choice(OTHER)
        employees = RNG.randint(200, 2000) if score >= 65 else RNG.randint(90, 700)
    else:
        industry = RNG.choice(OTHER) if RNG.random() < 0.7 else RNG.choice(PRIORITY)
        employees = RNG.randint(3000, 9000) if RNG.random() < 0.08 else RNG.randint(8, 160)
    revenue = round(employees * RNG.uniform(0.18, 0.32)) * 1e6 if employees >= 40 else round(employees * 0.2, 1) * 1e6
    name, company = names.person(), names.company(industry)
    website = company.lower().replace(" & ", "").replace(" ", "")[:22] + RNG.choice([".com", ".com", ".io", ".co"])
    status, updated = status_for(score, created, cutoff)
    ft, lt = touches(ch, created, ads, seqs)
    return dict(
        name=name, title=RNG.choice(SENIOR if score >= 50 else JUNIOR), company=company, ch=ch,
        owner=RNG.choice(OWNERS), status=status, score=score, created=iso(created),
        updated=iso(updated) if updated else None,
        last=(RNG.choice(LAST_ACTIVITY[status]), iso(updated or created)),
        employees=employees, revenue=revenue, industry=industry, hq=RNG.choice(CITIES), website=website,
        founded=RNG.randint(1985, 2021), ft=(ft[0], iso(ft[1]), ft[2]), lt=(lt[0], iso(lt[1]), lt[2]),
    )


def save_lead(conn, lead, items=None, events=None):
    """Insert a lead with its score items and timeline; returns the lead with its id."""
    utm = UTM[lead["ch"]]
    first, last = lead["name"].lower().split(" ", 1)
    items = items or gen_items(lead["score"], lead)
    defaults = scoring.default_criteria()
    weights = {k: w for k, _, _, _, w in defaults}
    grp = {k: g for k, g, _, _, _ in defaults}
    pts = {k: scoring.points(weights[k], f) for k, f, _ in items}
    cur = conn.execute(
        "INSERT INTO leads (name, title, company, email, channel_id, owner, status, score, fit, intent, created_at, "
        "last_activity_at, last_activity, owner_updated_at, employees, revenue, industry, hq, website, founded, "
        "enriched_at, enriched_via, utm_source, utm_medium, ft_channel, ft_at, ft_detail, lt_channel, lt_at, lt_detail) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (lead["name"], lead["title"], lead["company"],
         "{}.{}@{}".format(first, last.replace(" ", ""), lead["website"]), lead["ch"], lead["owner"],
         lead["status"], sum(pts.values()), sum(p for k, p in pts.items() if grp[k] == "Fit"),
         sum(p for k, p in pts.items() if grp[k] == "Intent"), lead["created"], lead["last"][1], lead["last"][0],
         lead["updated"], lead["employees"], int(lead["revenue"]), lead["industry"], lead["hq"], lead["website"],
         lead["founded"], lead["lt"][1], "Apollo", utm[0], utm[1],
         lead["ft"][0], lead["ft"][1], lead["ft"][2], lead["lt"][0], lead["lt"][1], lead["lt"][2]))
    lead["id"] = cur.lastrowid
    scoring.store_items(conn, lead["id"], items)
    if events is None:
        events = [(lead["lt"][1], "touch", lead["lt"][0], "Lead created", lead["lt"][2])]
        if lead["ft"][1][:10] != lead["lt"][1][:10]:
            events.append((lead["ft"][1], "touch", lead["ft"][0], "First touch", lead["ft"][2]))
        if lead["updated"]:
            events.append((lead["updated"], "crm", None, "Status → " + lead["status"], "Updated by " + lead["owner"]))
    conn.executemany("INSERT INTO lead_events (lead_id, at, kind, channel_id, title, detail) VALUES (?,?,?,?,?,?)",
                     [(lead["id"],) + e for e in events])
    return lead


def add_reminder(conn, lead, rule, sent, opened=None, updated=None):
    n = 3 if rule == "r3" else 7
    conn.execute("INSERT INTO reminders (lead_id, rule, owner, sent_at, opened_at, owner_updated_at) VALUES (?,?,?,?,?,?)",
                 (lead["id"], rule, lead["owner"], iso(sent), iso(opened) if opened else None,
                  iso(updated) if updated else None))
    conn.execute("INSERT INTO lead_events (lead_id, at, kind, channel_id, title, detail) VALUES (?,?,?,?,?,?)",
                 (lead["id"], iso(sent), "reminder", None, "Reminder sent to " + lead["owner"],
                  "{} days without an update".format(n)))


def nine(d, plus_days):
    return datetime.combine(d + timedelta(days=plus_days), time(9, 0))


def set_update(conn, lead, when, status=None):
    """Record the owner's first update after a reminder."""
    lead["updated"] = iso(when)
    if status:
        lead["status"] = status
    conn.execute("UPDATE leads SET owner_updated_at = ?, status = ?, last_activity_at = ?, last_activity = ? WHERE id = ?",
                 (lead["updated"], lead["status"], lead["updated"], "Status changed", lead["id"]))
    conn.execute("DELETE FROM lead_events WHERE lead_id = ? AND kind = 'crm'", (lead["id"],))
    conn.execute("INSERT INTO lead_events (lead_id, at, kind, channel_id, title, detail) VALUES (?,?,?,?,?,?)",
                 (lead["id"], lead["updated"], "crm", None, "Status → " + lead["status"], "Updated by " + lead["owner"]))


def seed_leads(conn, ads, seqs):
    names = Names()

    # September, to 13:00 on the 24th. Three blocks so week-to-date comparisons land on the design's figures.
    blocks = {
        "A": dict(rows=[[SEP[20], "full", 41], [SEP[21], "full", 39], [SEP[22], "full", 39], [SEP[23], "am", 23]],
                  cols=list(WEEK_A), q=list(WEEK_A_Q)),
        "B": dict(rows=[[SEP[13], "full", 50], [SEP[14], "full", 52], [SEP[15], "full", 48], [SEP[16], "am", SEP_17_AM]],
                  cols=list(WEEK_B), q=list(WEEK_B_Q)),
    }
    rest = [[d, "full", n] for d, n in zip(SEP[:13], SEP_DAILY[:13])]
    rest += [[SEP[16], "pm", SEP_DAILY[16] - SEP_17_AM]] + [[d, "full", n] for d, n in zip(SEP[17:20], SEP_DAILY[17:20])]
    blocks["C"] = dict(rows=rest, cols=[m - a - b for m, a, b in zip(MONTH, WEEK_A, WEEK_B)],
                       q=[m - a - b for m, a, b in zip(MONTH_Q, WEEK_A_Q, WEEK_B_Q)])

    q_counts, u_counts = [b[2] for b in Q_BINS], [b[2] for b in U_BINS]
    for lead in NAMED:  # the named leads take their places in the totals first
        created = datetime.fromisoformat(lead["created"])
        ci, qual = ORDER.index(lead["ch"]), lead["score"] >= 65
        for blk in blocks.values():
            row = next((r for r in blk["rows"] if r[0] == created.date()
                        and (r[1] == "full" or (r[1] == "am") == (created.hour < 13))), None)
            if row:
                row[2] -= 1
                blk["cols"][ci] -= 1
                blk["q"][ci] -= qual
        if qual:
            q_counts[bin_index(Q_BINS, lead["score"])] -= 1
        else:
            u_counts[bin_index(U_BINS, lead["score"])] -= 1

    saved = []
    for i, lead in enumerate(NAMED):
        lead = dict(lead)
        saved.append(save_lead(conn, lead, items=daniel_items() if i == 0 else None,
                               events=DANIEL_EVENTS if i == 0 else None))
    named = {lead["name"]: lead for lead in saved}

    q_pool, u_pool = score_pool(Q_BINS, q_counts), score_pool(U_BINS, u_counts)
    sep = []
    for blk in blocks.values():
        for slot in lead_block([tuple(r) for r in blk["rows"]], blk["cols"], blk["q"]):
            sep.append(make_lead(slot, q_pool.pop() if slot["q"] else u_pool.pop(), names, ads, seqs, NOW))
    assert not q_pool and not u_pool

    # August 1-24 to 13:00 (the comparison month), then the rest of August.
    aug_rows = [(d, "full", 0) for d in AUG[:-1]] + [(AUG[-1], "am", 0)]
    aug_n = split(sum(AUG_TOTAL), wts(AUG[:-1], 1.0, 0.27) + [0.55])
    aug_slots = lead_block([(d, p, n) for (d, p, _), n in zip(aug_rows, aug_n)], AUG_TOTAL, AUG_Q)
    rest_rows = [(AUG[-1], "pm", 18)] + [(d, "full", 11 if weekend(d) else 41) for d in AUG_REST]
    rest_cols = split(sum(r[2] for r in rest_rows), AUG_TOTAL)
    rest_q = [int(n * q / t) for n, q, t in zip(rest_cols, AUG_Q, AUG_TOTAL)]
    aug_slots += lead_block(rest_rows, rest_cols, rest_q)
    nq = sum(s["q"] for s in aug_slots)
    q_pool = score_pool(Q_BINS, split(nq, [b[2] for b in Q_BINS]))
    u_pool = score_pool(U_BINS, split(len(aug_slots) - nq, [b[2] for b in U_BINS]))
    aug = [make_lead(s, q_pool.pop() if s["q"] else u_pool.pop(), names, ads, seqs, NOW) for s in aug_slots]

    # Leads whose owners went quiet, and the reminder history behind this month's totals
    # (41 three-day nudges, 26 answered within a day; 17 seven-day nudges, 8 answered within a day).
    def pick(pool, n, lo, hi, cond=lambda l: True):
        found = [l for l in pool if lo <= l["created"][:10] <= hi and not l.get("used") and cond(l)]
        chosen = RNG.sample(found, n)
        for l in chosen:
            l["used"] = True
        return chosen

    terminal = {"Qualified": "Qualified", "Meeting booked": "Meeting booked", "Unqualified": "Unqualified"}
    stale = pick(sep, 5, "2026-09-09", "2026-09-15")
    for lead, owner in zip(stale, ["Priya Raman", "Priya Raman", "Priya Raman", "Tom Becker", "Tom Becker"]):
        created = datetime.fromisoformat(lead["created"])
        lead.update(owner=owner, status="Contacted", updated=iso(created + timedelta(hours=3)),
                    last=("Email sent", iso(created + timedelta(hours=3))))
    answered = pick(sep, 25, "2026-09-01", "2026-09-18", lambda l: l["status"] in terminal)
    slow = pick(sep, 7, "2026-09-01", "2026-09-15", lambda l: l["status"] in terminal)
    slow_aug = pick(aug, 3, "2026-08-25", "2026-08-28", lambda l: l["status"] in terminal)

    for lead in aug + sep:
        save_lead(conn, lead)

    for lead in stale:
        d = date.fromisoformat(lead["created"][:10])
        add_reminder(conn, lead, "r3", nine(d, 3), opened=nine(d, 3) + timedelta(hours=RNG.randint(1, 6)))
        add_reminder(conn, lead, "r7", nine(d, 7))
    for lead in answered:
        d = date.fromisoformat(lead["created"][:10])
        reply = nine(d, 3) + timedelta(minutes=RNG.randint(40, 20 * 60))
        add_reminder(conn, lead, "r3", nine(d, 3), opened=nine(d, 3) + timedelta(minutes=RNG.randint(5, 35)), updated=reply)
        set_update(conn, lead, reply)
    for lead in slow + slow_aug:
        d = date.fromisoformat(lead["created"][:10])
        late = lead in slow_aug
        reply = nine(d, 7) + (timedelta(hours=RNG.randint(30, 60)) if late else timedelta(minutes=RNG.randint(40, 8 * 60)))
        add_reminder(conn, lead, "r3", nine(d, 3), opened=nine(d, 3) + timedelta(hours=RNG.randint(1, 5)), updated=reply)
        add_reminder(conn, lead, "r7", nine(d, 7), opened=nine(d, 7) + timedelta(minutes=RNG.randint(5, 50)), updated=reply)
        set_update(conn, lead, reply)

    daniel, kenji, marcus, isabel = (named[n] for n in ("Daniel Okafor", "Kenji Watanabe", "Marcus Freeman", "Isabel Moreno"))
    met = datetime(2026, 9, 24, 10, 12)
    add_reminder(conn, daniel, "r3", datetime(2026, 9, 20, 9), opened=datetime(2026, 9, 20, 11, 2), updated=met)
    add_reminder(conn, daniel, "r7", datetime(2026, 9, 24, 9), opened=datetime(2026, 9, 24, 9, 14), updated=met)
    add_reminder(conn, kenji, "r3", datetime(2026, 9, 19, 9), opened=datetime(2026, 9, 19, 13, 40))
    add_reminder(conn, kenji, "r7", datetime(2026, 9, 23, 9))
    add_reminder(conn, marcus, "r3", datetime(2026, 9, 16, 9), opened=datetime(2026, 9, 16, 9, 20),
                 updated=datetime(2026, 9, 16, 14, 0))
    add_reminder(conn, isabel, "r3", datetime(2026, 9, 23, 9), opened=datetime(2026, 9, 23, 9, 31))
    return sep, aug


# --------------------------------------------------------------------------- deals

SEP_DEALS, SEP_WON = [13, 5, 6, 1, 5, 9, 5, 2], [3, 2, 2, 0, 1, 2, 1, 0]
AUG_DEALS, AUG_WON = [11, 5, 5, 1, 4, 8, 4, 1], [3, 1, 2, 0, 1, 1, 1, 0]


def seed_deals(conn, leads, counts, won, pipeline, lead_by, window_end):
    """Open a deal for some qualified leads per channel; the earliest ones are won inside the window."""
    rows = []
    for ci, ch in enumerate(ORDER):
        pool = sorted((l for l in leads if l["ch"] == ch and l["score"] >= 65 and l["created"][:10] <= lead_by
                       and l["status"] != "Contacted"), key=lambda l: l["created"])
        early, later = pool[:won[ci]], pool[won[ci]:]
        for i, lead in enumerate(early + RNG.sample(later, counts[ci] - won[ci])):
            created = min(datetime.fromisoformat(lead["created"]) + timedelta(days=RNG.randint(1, 4), hours=RNG.randint(0, 6)),
                          window_end - timedelta(hours=3))
            closed, stage = None, "open"
            if i < won[ci]:
                stage = "won"
                closed = min(created + timedelta(days=RNG.randint(2, 6)), window_end - timedelta(hours=1))
            elif RNG.random() < 0.15:
                stage = "lost"
                closed = min(created + timedelta(days=RNG.randint(2, 5)), window_end - timedelta(hours=1))
            rows.append(dict(lead_id=lead["id"], channel_id=ch, amount=0, stage=stage, created_at=iso(created),
                             closed_at=iso(closed) if closed else None))
    for row, amount in zip(rows, split(pipeline // 1000, [RNG.uniform(0.6, 1.6) for _ in rows])):
        row["amount"] = amount * 1000
    insert(conn, "deals", rows)


def seed_late_aug_deals(conn, aug):
    """A few deals opened 25-31 Aug, outside both comparison windows."""
    pool = [l for l in aug if l["score"] >= 65 and "2026-08-15" <= l["created"][:10] <= "2026-08-24"]
    rows = []
    for i, lead in enumerate(RNG.sample(pool, 6)):
        created = datetime(2026, 8, 25 + i, RNG.randint(9, 17), RNG.randint(0, 59))
        won = i < 2
        rows.append(dict(lead_id=lead["id"], channel_id=lead["ch"], amount=RNG.randint(28, 58) * 1000,
                         stage="won" if won else "open", created_at=iso(created),
                         closed_at=iso(datetime(2026, 8, 31, 15, 0)) if won else None))
    insert(conn, "deals", rows)


# --------------------------------------------------------------------------- ads

HEADLINES = ["See every invoice in one queue", "Cut AP processing cost by 60%",
             "The month-end checklist finance teams use", "Three-way matching without the spreadsheets",
             "From invoice to approved in 4 hours"]
# name, status, spend, impressions, clicks, leads (1-24 Sep)
CAMPAIGNS = {
    "meta": [("Lead form · AP month-end checklist", "Active", 4610, 241000, 2870, 61),
             ("Retargeting · Pricing visitors", "Active", 3920, 98400, 1610, 52),
             ("Prospecting · Finance leaders lookalike", "Active", 3480, 196800, 1950, 34),
             ("Video · 2-minute product tour", "Paused", 2270, 75800, 710, 21)],
    "li": [("CFO – AP Automation – Q3", "Active", 8610, 102400, 820, 41),
           ("Controllers · Document ad guide", "Active", 5240, 74300, 590, 36),
           ("Retargeting · Website visitors 90d", "Active", 3860, 51900, 470, 29),
           ("Conversation ad · Demo invite", "Active", 4230, 57400, 330, 15)],
}
CFO_CREATIVES = [("Close the books 5 days faster", "Single image", 3980, 46200, 410, 22),
                 ("Approve invoices from Slack", "Single image", 2640, 31800, 240, 12),
                 ("Your AP team, minus the spreadsheets", "Carousel · 4 cards", 1990, 24400, 170, 7)]
# The CFO campaign's last six days (19-24 Sep): cost per lead climbs from $214 to $287.
CFO_TAIL_SPEND, CFO_TAIL_LEADS = [250, 250, 570, 390, 380, 378], [1, 1, 3, 2, 1, 1]
AUG_ADS = {"meta": (13400, 540000, 6050, 152), "li": (20490, 252000, 1880, 110)}  # 1-24 Aug totals


def two_creatives(row, ci):
    _, _, sp, im, cl, ld = row
    a = (round(sp * 0.58), round(im * 0.55), round(cl * 0.62), round(ld * 0.64))
    return [(HEADLINES[ci % 5], "Single image") + a,
            (HEADLINES[(ci + 2) % 5], "Single image", sp - a[0], im - a[1], cl - a[2], ld - a[3])]


def seed_ads(conn):
    """Campaigns, creatives and daily figures. Returns {platform: [headlines]} for lead touches."""
    headlines, daily = {"meta": [], "li": []}, []
    for platform, rows in CAMPAIGNS.items():
        creatives = []  # (id, paused, sep totals)
        for ci, row in enumerate(rows):
            camp = conn.execute("INSERT INTO ad_campaigns (platform, name, status) VALUES (?,?,?)",
                                (platform, row[0], row[1])).lastrowid
            cfo = platform == "li" and ci == 0
            ids = []
            for cr in (CFO_CREATIVES if cfo else two_creatives(row, ci)):
                cid = conn.execute("INSERT INTO ad_creatives (campaign_id, headline, format) VALUES (?,?,?)",
                                   (camp, cr[0], cr[1])).lastrowid
                headlines[platform].append(cr[0])
                creatives.append((cid, row[1] == "Paused", cr[2:]))
                ids.append(cid)

            if cfo:  # shape spend and leads by day so the last six days tell the cost-spike story
                head = wts(SEP[:18], 1.12, 0.6)
                spend_days = split(row[2] - sum(CFO_TAIL_SPEND), head) + CFO_TAIL_SPEND
                lead_days = split(row[5] - sum(CFO_TAIL_LEADS), head) + CFO_TAIL_LEADS
                spend = matrix(spend_days, [c[2] for c in CFO_CREATIVES])
                leads = matrix(lead_days, [c[5] for c in CFO_CREATIVES], RNG, jitter=0.9)
                for k, cid in enumerate(ids):
                    im = split(CFO_CREATIVES[k][3], wts(SEP, 1.12, 0.6))
                    cl = split(CFO_CREATIVES[k][4], wts(SEP, 1.12, 0.6))
                    daily += [dict(date=d.isoformat(), creative_id=cid, spend=spend[i][k], impressions=im[i],
                                   clicks=cl[i], leads=leads[i][k]) for i, d in enumerate(SEP)]
                creatives = [c for c in creatives if c[0] not in ids] + [(cid, None, None) for cid in ids]

        # Everything except the CFO campaign: smooth weekday/weekend pattern; the paused campaign stops on the 12th.
        for cid, paused, tot in creatives:
            if tot is None:
                continue
            w = [0.0 if paused and d.day > 12 else x for d, x in zip(SEP, wts(SEP, 1.12, 0.6))]
            cols = [split(t, w) for t in tot]
            daily += [dict(date=d.isoformat(), creative_id=cid, spend=cols[0][i], impressions=cols[1][i],
                           clicks=cols[2][i], leads=cols[3][i]) for i, d in enumerate(SEP) if w[i]]

        # August: the same creatives scaled to the platform's August totals, 1-24 and then 25-31.
        ids = [c[0] for c in creatives]
        sep_tot = {cid: [0, 0, 0, 0] for cid in ids}
        for r in daily:
            if r["creative_id"] in sep_tot:
                for k, key in enumerate(("spend", "impressions", "clicks", "leads")):
                    sep_tot[r["creative_id"]][k] += r[key]
        for ds, scale in ((AUG, 1.0), (AUG_REST, 7 / 24)):
            per = [split(round(AUG_ADS[platform][k] * scale), [sep_tot[c][k] for c in ids]) for k in range(4)]
            for j, cid in enumerate(ids):
                cols = [split(per[k][j], wts(ds, 1.12, 0.6)) for k in range(4)]
                daily += [dict(date=d.isoformat(), creative_id=cid, spend=cols[0][i], impressions=cols[1][i],
                               clicks=cols[2][i], leads=cols[3][i]) for i, d in enumerate(ds)]
    insert(conn, "ad_daily", daily)
    return headlines


# --------------------------------------------------------------------------- outbound

# name, detail, [sent, opened/accepted, replied, meetings] for 1-24 Sep
OUTBOUND = {
    "apollo": [("Finance Ops · Mid-market", "5 steps", [2140, 1005, 86, 14]),
               ("CFO · Construction", "4 steps", [1260, 630, 52, 9]),
               ("Controllers · Healthcare", "5 steps", [1420, 582, 41, 6])],
    "heyreach": [("CFOs · Freight & logistics", "3 senders", [520, 224, 61, 6]),
                 ("VP Finance · Healthcare", "2 senders", [410, 150, 34, 3]),
                 ("Heads of AP · Manufacturing", "1 sender", [250, 98, 23, 2])],
}
AUG_SENT = {"apollo": 4500, "heyreach": 1100}


def seed_outbound(conn):
    names, daily = {}, []
    for ch, rows in OUTBOUND.items():
        names[ch] = [r[0] for r in rows]
        sep_sent = sum(r[2][0] for r in rows)
        for name, detail, steps in rows:
            cid = conn.execute("INSERT INTO outbound_campaigns (channel_id, name, detail) VALUES (?,?,?)",
                               (ch, name, detail)).lastrowid
            for ds, scale in ((SEP, 1.0), (AUG, AUG_SENT[ch] / sep_sent), (AUG_REST, AUG_SENT[ch] / sep_sent * 7 / 24)):
                cols = [split(round(v * scale), wts(ds, 1.0, 0.12)) for v in steps]
                daily += [dict(date=d.isoformat(), campaign_id=cid, sent=cols[0][i], opened=cols[1][i],
                               replied=cols[2][i], meetings=cols[3][i]) for i, d in enumerate(ds)]
    insert(conn, "outbound_daily", daily)
    return names


# --------------------------------------------------------------------------- funnel feeds and website

# impressions, clicks, spend for the channels that are not ad platforms. Outbound impressions are sends.
SEP_FEED = {"search": (1290000, 18960, 3460), "direct": (0, 0, 0), "referral": (36000, 1390, 1240),
            "social": (180000, 1480, 1070), "apollo": (None, 520, 4150), "heyreach": (None, 180, 2480)}
AUG_FEED = {"search": (1185000, 20190, 3300), "direct": (0, 0, 0), "referral": (33400, 120, 1200),
            "social": (164000, 100, 1020), "apollo": (None, 450, 3600), "heyreach": (None, 150, 2100)}
# source, medium, channel, sessions 1-24 Sep
TRAFFIC = [("google", "organic", "search", 18960), ("bing", "organic", "search", 640),
           ("(direct)", "(none)", "direct", 7606), ("partner", "referral", "referral", 2310),
           ("linkedin", "social", "social", 1480), ("facebook", "paid", "meta", 5260),
           ("instagram", "paid", "meta", 1880), ("linkedin", "paid", "li", 2210), ("apollo", "email", "apollo", 520),
           ("heyreach", "linkedin_dm", "heyreach", 180), ("newsletter", "email", None, 214)]
AUG_SESSIONS, AUG_GOOGLE = 39600, 20190
PAGES = [("/", "Home", 9140, 61), ("/blog/three-way-matching-explained", "Three-way matching, explained", 6420, 38),
         ("/pricing", "Pricing", 4880, 142), ("/blog/ap-automation-software-guide", "AP automation software guide", 3210, 24),
         ("/customers", "Customers", 1960, 21), ("/product/approvals", "Approvals", 1740, 29)]
# query, clicks, impressions, position now, position before
QUERIES = [("chat360", 2410, 3020, 1.0, 1.0), ("ap automation software", 1840, 52300, 9.1, 4.2),
           ("three way matching", 1520, 38900, 2.8, 3.1), ("invoice approval workflow", 980, 21600, 3.4, 3.6),
           ("accounts payable automation", 860, 34100, 6.7, 6.9), ("ap automation for logistics", 240, 2900, 1.9, 2.4)]
FORMS = [("Demo request", 1480, 214), ("Contact sales", 690, 126), ("Free trial", 940, 118), ("Guides & ebooks", 1120, 98)]
DROP_DAY = 18  # the "ap automation software" ranking slips on 18 Sep


def search_wts(ds):
    """Search traffic by day: quieter weekends, and about a quarter lower after the ranking slip."""
    return [w * (0.74 if d.month == 9 and d.day >= DROP_DAY else 1.0) for d, w in zip(ds, wavy(ds))]


def seed_feeds(conn):
    rows = []
    for ds, feed, scale in ((SEP, SEP_FEED, 1.0), (AUG, AUG_FEED, 1.0), (AUG_REST, AUG_FEED, 7 / 24)):
        for ch, (impr, clicks, spend) in feed.items():
            w = search_wts(ds) if ch == "search" else wts(ds, 1.0, 0.12 if ch in OUTBOUND else 0.5)
            if impr is None:  # outbound: impressions are the day's sends
                sent = dict(conn.execute(
                    "SELECT d.date, SUM(d.sent) FROM outbound_daily d JOIN outbound_campaigns c ON c.id = d.campaign_id "
                    "WHERE c.channel_id = ? GROUP BY d.date", (ch,)).fetchall())
                im = [sent.get(d.isoformat(), 0) for d in ds]
            else:
                im = split(round(impr * scale), w)
            cl, sp = split(round(clicks * scale), w), split(round(spend * scale), [1.0] * len(ds))
            rows += [dict(date=d.isoformat(), channel_id=ch, impressions=im[i], clicks=cl[i], spend=sp[i])
                     for i, d in enumerate(ds)]
    insert(conn, "channel_daily", rows)
    conn.execute(  # ad platforms roll up from their creatives
        "INSERT INTO channel_daily (date, channel_id, impressions, clicks, spend) "
        "SELECT d.date, c.platform, SUM(d.impressions), SUM(d.clicks), SUM(d.spend) FROM ad_daily d "
        "JOIN ad_creatives cr ON cr.id = d.creative_id JOIN ad_campaigns c ON c.id = cr.campaign_id "
        "GROUP BY d.date, c.platform")


def seed_web(conn):
    others = [t for t in TRAFFIC if t[:2] != ("google", "organic")]
    aug_others = split(AUG_SESSIONS - AUG_GOOGLE, [t[3] for t in others])
    traffic, pages, queries, forms, positions = [], [], [], [], []
    for ds, scale, google, other_tot in ((SEP, 1.0, 18960, [t[3] for t in others]),
                                         (AUG, 1.0, AUG_GOOGLE, aug_others),
                                         (AUG_REST, 7 / 24, AUG_GOOGLE, aug_others)):
        aug = ds is not SEP
        g = split(round(google * scale), search_wts(ds))
        traffic += [dict(date=d.isoformat(), source="google", medium="organic", sessions=g[i]) for i, d in enumerate(ds)]
        for k, (t, tot) in enumerate(zip(others, other_tot)):
            col = split(round(tot * scale), wavy(ds, phase=k + 1.0))
            traffic += [dict(date=d.isoformat(), source=t[0], medium=t[1], sessions=col[i]) for i, d in enumerate(ds)]
        for path, title, views, leads in PAGES:
            f = scale * (0.96 if aug else 1.0)
            v, l = split(round(views * f), wts(ds)), split(round(leads * f), wts(ds))
            pages += [dict(date=d.isoformat(), path=path, title=title, views=v[i], leads=l[i]) for i, d in enumerate(ds)]
        for query, clicks, impr, pos, was in QUERIES:
            slipped = query == "ap automation software"
            w = [x * (0.45 if slipped and d.month == 9 and d.day >= DROP_DAY else 1.0) for d, x in zip(ds, wts(ds))]
            f = scale * (1.05 if aug else 1.0)
            c, im = split(round(clicks * f), w), split(round(impr * f), wts(ds))
            for i, d in enumerate(ds):
                p = was if aug or (slipped and d.day < DROP_DAY) else pos
                queries.append(dict(date=d.isoformat(), query=query, clicks=c[i], impressions=im[i], position=p))
        for name, views, subs in FORMS:
            f = scale * (0.93 if aug else 1.0)
            v, s = split(round(views * f), wts(ds)), split(round(subs * f), wts(ds))
            forms += [dict(date=d.isoformat(), form=name, views=v[i], submissions=s[i]) for i, d in enumerate(ds)]
        for i, d in enumerate(ds):  # site-wide average position: 6.1 in August, 6.2 then 10.3 after the slip
            base = 6.1 if aug else (10.3 if d.day >= DROP_DAY else 6.2)
            positions.append(dict(date=d.isoformat(), position=round(base + (0.1 if i % 2 else -0.1), 1)))
    insert(conn, "traffic_daily", traffic)
    insert(conn, "page_daily", pages)
    insert(conn, "query_daily", queries)
    insert(conn, "form_daily", forms)
    insert(conn, "search_daily", positions)


# --------------------------------------------------------------------------- everything else

TOOLS = [("Apollo", "Outbound & data", 990, 5, "Anya Sharma", "2026-10-03", "Annual", 11880),
         ("HeyReach", "LinkedIn outreach", 549, 6, "Lena Ortiz", "2026-10-12", "Monthly", None),
         ("Calendly Teams", "Scheduling", 192, 12, "Priya Raman", "2026-10-14", "Monthly", None),
         ("Zapier", "Automation", 69, 1, "Anya Sharma", "2026-10-17", "Monthly", None),
         ("Lusha", "Enrichment", 300, 3, "Tom Becker", "2026-10-29", "Monthly", None),
         ("LinkedIn Sales Navigator", "Social selling", 1000, 10, "Lena Ortiz", "2026-11-01", "Monthly", None),
         ("Framer", "Website", 120, 4, "Sam Cole", "2026-11-18", "Monthly", None),
         ("Hotjar", "Analytics", 171, None, "Sam Cole", "2026-12-08", "Monthly", None),
         ("Zoho CRM", "CRM", 1120, 14, "Anya Sharma", "2027-01-01", "Annual", 13440),
         ("Descript", "Video", 48, 2, "Mia Torres", "2027-01-09", "Monthly", None),
         ("Semrush", "SEO", 499, 2, "Sam Cole", "2027-02-05", "Annual", 5988),
         ("Canva Teams", "Design", 100, 8, "Mia Torres", "2027-03-22", "Annual", 1200)]
SUB_HISTORY = [("2026-04", 4310), ("2026-05", 4420), ("2026-06", 4690), ("2026-07", 4880), ("2026-08", 5010)]
TARGETS = {"2026-09": dict(leads=1000, qualified=260, pipeline=2400000, won=14, budget_meta=18000,
                           budget_li=26000, budget_organic=7500, budget_outbound=10500),
           "2026-10": dict(leads=1050, qualified=275, pipeline=2500000, won=15, budget_meta=18000,
                           budget_li=24000, budget_organic=8000, budget_outbound=10500)}
# key, name, detail, minutes since last sync, hours before a feed counts as stale
SOURCES = [("zoho", "Zoho CRM", "Leads, owners, deals", 4, 6), ("meta", "Meta Ads", "Campaigns, spend, lead forms", 4, 6),
           ("linkedin", "LinkedIn Ads", "Campaigns, spend, conversions", 6, 6),
           ("apollo", "Apollo", "Sequences, email events", 4, 6), ("heyreach", "HeyReach", "LinkedIn campaigns, replies", 12, 6),
           ("ga4", "Google Analytics 4", "Sessions, events, forms", 18, 6),
           ("gsc", "Search Console", "Queries, pages, positions", 120, 36), ("framer", "Framer", "Site forms via webhook", 1, 48)]
USERS = [("Anya Sharma", "Marketing lead", "Admin", 0), ("Priya Raman", "Sales development", "Lead owner", 12),
         ("Tom Becker", "Sales development", "Lead owner", 60), ("Lena Ortiz", "Sales development", "Lead owner", 180),
         ("Sam Cole", "Web & SEO", "Editor", 60 * 26), ("Mia Torres", "Content", "Editor", 60 * 50),
         ("Rachel Kim", "CEO", "Viewer", 60 * 76), ("David Lin", "CRO", "Viewer", 60 * 77)]
RULES = [("benchmark", "alert", "Below benchmark", "A rate that sits under its benchmark over the last 30 days. Checked with every sync.", "Dashboard", 1),
         ("trend", "alert", "Down on the last 30 days", "Any figure that fell 20% or more against the 30 days before.", "Dashboard", 1),
         ("r3", "reminder", "No update after 3 days", "Email the lead owner at 09:00 in their time zone", "Lead owner", 1),
         ("r7", "reminder", "No update after 7 days", "Email the owner and copy Anya Sharma", "Lead owner, Anya Sharma", 1),
         ("drop", "alert", "Lead drop", "Leads more than 15% below the same point last week. Checked hourly.", "Slack #marketing, email", 1),
         ("cost", "alert", "Cost spike", "Cost per lead up more than 25% over 3 days, on any campaign with {min_spend}+ spend.", "Slack #marketing", 1),
         ("renew", "alert", "Upcoming renewal", "30, 14, 7 and 3 days before any subscription renews, on the day, and if the date passes.", "Email to tool owner", 1),
         ("sync", "alert", "Sync failure", "Any data source not synced for 6 hours.", "Email to admins", 1),
         ("budget", "alert", "Budget pacing", "Projected monthly spend above 105% of plan.", "Slack #marketing", 0)]
RECIPIENTS = [("Rachel Kim", "CEO"), ("David Lin", "CRO"), ("Marta Nowak", "CFO"), ("Anya Sharma", "Marketing lead"),
              ("marketing@chat360.io", "6 people")]
PAST_REPORTS = [("2026-09-14", "Best week of the quarter: 252 leads", 5), ("2026-09-07", "Meta retargeting halves cost per lead", 5),
                ("2026-08-31", "A slow start to September, as expected", 4), ("2026-08-24", "August closes 4% above target", 5)]
ALERT_TIMES = {"drop": "2026-09-24T11:00:00", "cost": "2026-09-24T08:00:00", "r7": "2026-09-24T09:00:00",
               "renew": "2026-09-23T09:00:00"}


# Channels added for real data, beyond the design's eight: (id, name, group, colour, wording for summaries, sort).
# The two outreach channels are also renamed, because real outreach is not tied to one tool.
LIVE_CHANNELS = [
    ("website", "Website forms", "organic", "oklch(0.68 0.12 135)", "website forms", 4),
    ("chatbot", "Website chatbot", "organic", "oklch(0.56 0.07 215)", "the website chatbot", 5),
    ("google", "Google ads", "paid", "oklch(0.62 0.12 222)", "Google ads", 12),
    ("events", "Events", "events", "oklch(0.62 0.13 315)", "events", 20),
    ("outbound_other", "Outbound · other", "outbound", "oklch(0.55 0.10 62)", "other outbound", 32),
]
LIVE_NAMES = {"apollo": ("Email outreach", "email outreach", 30), "heyreach": ("LinkedIn outreach", "LinkedIn outreach", 31),
              "meta": ("Meta ads", "Meta ads", 10), "li": ("LinkedIn ads", "LinkedIn ads", 11)}


def add_live_channels(conn):
    """Give a live database its extra channels and the company-research source. Safe to run again."""
    if db.is_demo(conn):
        return
    conn.execute("INSERT OR IGNORE INTO sources (key, name, detail, status, stale_after_hours, sort) "
                 "VALUES ('crustdata', 'Crustdata', 'Company research: industry, size', 'not_connected', 48, 20)")
    conn.execute("INSERT OR IGNORE INTO sources (key, name, detail, status, stale_after_hours, sort) "
                 "VALUES ('semrush', 'Semrush', 'Keyword rankings, competitors (file import)', 'not_connected', 1080, 8)")
    # The mock-ups assumed a Framer site; the form webhook works for any site builder.
    conn.execute("UPDATE sources SET name = 'Website forms', detail = 'Form submissions by webhook' WHERE key = 'framer'")
    for cid, name, grp, color, wording, sort in LIVE_CHANNELS:
        conn.execute("INSERT OR IGNORE INTO channels (id, name, grp, color, narrative, sort) VALUES (?,?,?,?,?,?)",
                     (cid, name, grp, color, wording, sort))
    for cid, (name, wording, sort) in LIVE_NAMES.items():
        conn.execute("UPDATE channels SET name = ?, narrative = ?, sort = ? WHERE id = ?", (name, wording, sort, cid))


def seed_structure(conn, connected):
    """What every database needs: channels, tag mappings, scoring criteria, rules and the list of sources."""
    insert(conn, "channels", [dict(id=c[0], name=c[1], grp=c[2], color=c[3], narrative=c[4], sort=i)
                              for i, c in enumerate(CHANNELS)])
    insert(conn, "utm_map", [dict(source=t[0], medium=t[1], channel_id=t[2]) for t in TRAFFIC if connected or t[2]])
    insert(conn, "scoring_criteria", [dict(key=k, grp=g, label=l, rule=r, weight=w, sort=i)
                                      for i, (k, g, l, r, w) in enumerate(scoring.default_criteria(fit_only=not connected))])
    insert(conn, "sources", [dict(key=k, name=n, detail=d, status="connected" if connected else "not_connected",
                                  last_sync_at=iso(NOW - timedelta(minutes=m)) if connected else None,
                                  note="daily feed" if k == "gsc" else None, stale_after_hours=h, sort=i)
                             for i, (k, n, d, m, h) in enumerate(SOURCES)])
    insert(conn, "alert_rules", [dict(key=k, kind=kind, title=t, detail=d.format(min_spend=money.money(1000)),
                                      deliver_to=to, enabled=on, sort=i)
                                 for i, (k, kind, t, d, to, on) in enumerate(RULES)])
    for key, value in [("product", "Meridian"), ("company", config.COMPANY), ("currency", money.DEFAULT),
                       ("qualify_threshold", scoring.DEFAULT_THRESHOLD), ("report_day", "Monday"), ("report_time", "08:00")]:
        db.set_setting(conn, key, value)


def seed_reference(conn):
    seed_structure(conn, connected=True)
    insert(conn, "users", [dict(name=n, team=t, role=r, email=n.lower().replace(" ", ".") + "@chat360.io",
                                last_active_at=iso(NOW - timedelta(minutes=m))) for n, t, r, m in USERS])
    insert(conn, "subscriptions", [dict(name=n, category=c, monthly_cost=m, seats=s, owner=o, renews_on=r, billing=b,
                                        annual_cost=a) for n, c, m, s, o, r, b, a in TOOLS])
    insert(conn, "subscription_history", [dict(month=m, total=t) for m, t in SUB_HISTORY])
    insert(conn, "targets", [dict(month=m, key=k, value=v) for m, kv in TARGETS.items() for k, v in kv.items()])
    insert(conn, "report_recipients", [dict(name=n, role=r, email=n if "@" in n else None) for n, r in RECIPIENTS])
    for key, value in [("demo_now", iso(NOW)), ("scoring_changed_at", "2026-09-02"),
                       ("scoring_changed_by", "Anya Sharma"), ("report_time", "08:00 ET"), ("current_user", "Anya Sharma")]:
        db.set_setting(conn, key, value)


def seed_alerts_and_reports(conn):
    alerts.run(conn, NOW)
    for rule, at in ALERT_TIMES.items():  # spread today's alerts over the morning, as they would have fired
        conn.execute("UPDATE alerts SET created_at = ? WHERE rule_key = ?", (at, rule))
    conn.execute("INSERT INTO alerts (rule_key, dedupe, title, detail, severity, created_at, resolved_at) VALUES (?,?,?,?,?,?,?)",
                 ("sync", "heyreach:2026-09-22", "HeyReach has not synced for 7 hours", "The API rate limit was hit at 12:40.",
                  "warn", "2026-09-22T12:40:00", "2026-09-22T15:10:00"))
    for week, headline, opened in PAST_REPORTS:
        sent = datetime.fromisoformat(week) + timedelta(days=7, hours=8)
        conn.execute("INSERT INTO reports (week_start, status, headline, sent_at, recipients, opened) VALUES (?,?,?,?,?,?)",
                     (week, "sent", headline, iso(sent), 5, opened))
    narrative.ensure_draft(conn, NOW)


def target_path(empty):
    """Sample data and real data live in separate files, so building one never touches the other."""
    if os.environ.get("MERIDIAN_DB"):
        return Path(os.environ["MERIDIAN_DB"])
    return config.LIVE_DB if empty else config.SAMPLE_DB


def run(empty=False, force=False):
    path = target_path(empty)
    money.use(money.DEFAULT)
    if path.exists():
        conn = db.connect(path)
        try:
            real = not db.is_demo(conn) and conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] > 0
        except Exception:  # not a Meridian database yet
            real = False
        conn.close()
        if real and not force:
            sys.exit("{} holds real data. Re-run with --force to replace it.".format(path))
        path.unlink()
    conn = db.connect(path)
    db.init_schema(conn)
    if empty:
        seed_structure(conn, connected=False)
        add_live_channels(conn)
        conn.commit()
        conn.close()
        print("Empty database written to", path)
        return
    seed_reference(conn)
    headlines = seed_ads(conn)
    sequences = seed_outbound(conn)
    seed_feeds(conn)
    seed_web(conn)
    sep, aug = seed_leads(conn, headlines, sequences)
    seed_deals(conn, sep, SEP_DEALS, SEP_WON, 1860000, "2026-09-19", NOW)
    seed_deals(conn, aug, AUG_DEALS, AUG_WON, 1620000, "2026-08-19", datetime(2026, 8, 24, 13, 0))
    seed_late_aug_deals(conn, aug)
    seed_alerts_and_reports(conn)
    conn.commit()
    conn.close()
    print("Sample data written to", path)


if __name__ == "__main__":
    run(empty="--empty" in sys.argv, force="--force" in sys.argv)

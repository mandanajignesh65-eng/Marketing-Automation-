# Meridian

A marketing command centre: one place to see leads, spend, outbound, website traffic, lead quality,
subscriptions and the weekly leadership report. Built from the Claude Design project in
`../Meridian Direction UI mockups` (twelve screens, light and dark).

## Run it

```bash
./run.sh
```

Then open http://localhost:8321. The first run installs two Python packages and builds the sample database.
It shows your own data once Zoho CRM is connected, and the sample company until then.
It needs Python 3.9 or later and nothing else: no Node, no build step.

## What is real and what is sample

Everything on screen is calculated from a database by the Python back end. Nothing is hard-coded in the pages.
There are two databases, kept apart so one never pollutes the other:

- `data/sample.db` is a made-up company's data, shown under the Chat360 name and pinned to Thursday 24 Sep 2026.
  The top bar shows a "Sample data" tag. Its amounts were written in dollars for the design and are simply shown
  with the rupee sign, so they are not realistic rupee figures.
- `data/meridian.db` is your own data. It is created the first time Zoho CRM is connected, and from then on the
  app opens it by default. `./run.sh --sample` shows the sample company again.

| Part | State |
|---|---|
| All twelve screens, date ranges, comparison, channel filter, light/dark | Working |
| Zoho CRM leads and deals | Working against the Chat360 account. Marketing leads only: cold calling, old lists and leads with no source are left out |
| Lead scoring editor (weights, threshold, live preview, rescore) | Working. Live data is scored against Chat360's four segments (see below) |
| Subscriptions, targets and budgets, lead-source and tracking-tag mapping, leaving sources out | Working |
| Alert rules and owner-reminder rules | Working. Alerts are checked automatically while the app runs |
| Weekly report draft, editing, recipients | Working. The draft is template-written from the figures |
| Apollo sequences and HeyReach campaigns (Outbound screen) | Built, read-only. Tested against stand-ins, not yet with real keys. Connect with `./connect-apollo.sh` and `./connect-heyreach.sh` (see below) |
| Google Analytics 4 and Search Console (Website screen) | Built, view-only. Tested against stand-ins, not yet with a real Google account. Connect with `./connect-google.sh` (see below) |
| Meta Ads and LinkedIn Ads (Paid ads screen) | Built, read-only. Tested against stand-ins, not yet with real accounts. Connect with `./connect-meta.sh` and `./connect-linkedin.sh` (see below) |
| Semrush keyword rankings and competitors (Website screen) | Working by file import; the plan in use has no API. First export read 2026-10-05 |
| Google Ads | **Not built.** |
| Sending email (reminders, weekly report) | Queued in the `outbox` table. Sent only when SMTP is configured. Untested against a real mail server |
| Slack delivery of alerts | **Not built.** "Delivered to" on the rules is a label only |
| Sign-in and roles | **Not built.** Anyone who can reach the page can use it |
| Writing back to Zoho CRM (e.g. Reassign) | **Not built.** Changes stay in Meridian |
| Company research (Crustdata) | Working. Fills in a lead's industry and company size when Zoho has none. Run so far for leads from July 2026 on; the rest, and new leads, need an API key (see below) |

## Connecting Zoho CRM

```bash
./connect-zoho.sh
```

The script walks through creating a "Self Client" in Zoho's API console (about two minutes), asks for its
Client ID, Client Secret and a one-time code, then fetches every lead and deal. It only reads from Zoho.
The credentials are saved in `.env` in this folder, readable only by you.

After that, while the app is running it fetches changes from Zoho every 15 minutes
(`MERIDIAN_ZOHO_EVERY_MINUTES` in `.env` changes this), and "Sync now" in Settings fetches straight away.

How Zoho's data is read (all of it is recorded in `data/zoho_mapping.json`, which can be edited by hand):

- **Channel.** Chat360's Zoho has no UTM fields, so a lead's channel comes from its Lead Source. Each source is
  tied to a channel once: by its wording, by the `lead_source_channels` list in the mapping file, or by picking a
  channel for it in Settings. A source nobody has placed shows as "Unmapped", at the top of that list.
  A blank Lead Source appears there as "No lead source in Zoho".
- **Channels.** Live data has five channels beyond the design's eight: Website forms, Website chatbot, Google ads,
  Events (its own group) and "Outbound · other". Apollo and HeyReach are named Email outreach and LinkedIn outreach.
- **Left out.** Meridian shows marketing's leads only. A lead source marked "Leave out" in Settings is not kept:
  its leads, the deals they became and deals that name it are dropped from every screen, and new ones are skipped.
  Left out today: "Outbound" (sales cold calling), old campaign lists (HubSpot Leads, Zoho Global, Sai Leads and
  so on), test records, and leads with no Lead Source at all. Only their Zoho ids are kept, to count them.
  Picking a channel for a left-out source brings it back: the next sync fetches everything again (a few minutes).
  The same list is kept in `exclude_lead_sources`. Nothing is changed in Zoho.
  Deals in a stage listed in `exclude_deal_stages` are skipped (Junk).
- **Status.** Zoho's lead statuses are reduced to five: New, Contacted, Qualified, Meeting booked, Unqualified,
  using the `status` list. Converted leads count as Qualified.
- **Deals.** "Converted" is the won stage; "Closed-Lost" and "Ice Box" count as lost (`deal_stages`). A deal takes
  the channel of the lead it was converted from, or of its own lead source. Amounts in other currencies are
  converted to rupees with Zoho's exchange rate.
- **Company size.** Zoho's "Company Size" band (Enterprise, Mid-market, SMB) stands in for an employee count.
- **Owner updates.** A change of status or owner, or a newer "Last Activity Time", resets the "no update" clock.
  Only leads created in the last 60 days are chased; older open leads are treated as history.

`.venv/bin/python -m meridian.zoho fields` shows exactly which Zoho fields, statuses and lead sources are being read.
`.venv/bin/python -m meridian.zoho sync --full` fetches everything again, for example after editing the mapping file.

What to expect on live data:

- Paid ads, Outbound and Website fill once their tools are connected.
- **"Qualified" depends on company research.** With only Zoho connected, the score is company fit against
  Chat360's profile (`LIVE_ICP` in `meridian/scoring.py`): industry in healthcare, retail, automobile or BFSI is
  worth 70, company size 30, and a lead qualifies at 65. Inbound leads arrive in Zoho with no industry or company
  size (9 of 568 in September 2026 had an industry), so they score 0 until company research fills those in.
- **Reminder emails are never sent by the app on its own.** They go out only when the reminders job is run.

## Company research

Meridian looks up each lead's company in Crustdata and fills in the industry and company size that Zoho is
missing. The lookup it uses ("identify") is free: it does not use Crustdata credits.

```bash
./connect-crustdata.sh
```

The script asks for a Crustdata API key (created in your Crustdata account), saves it in `.env`, then looks up
every company still waiting, about 25 a time and 30 requests a minute. After that the app researches new leads
on its own, after each Zoho sync. Until a key is added, nothing new is researched; Settings shows the Crustdata
card as "Not connected". The API path is tested against a stand-in for Crustdata, not yet with a real key.

How it works:

- **Which company.** A lead's company is recognised by its website or work-email domain; failing that, by the
  company name typed on the lead. Gmail-style addresses, made-up domains, Chat360's own addresses and a company
  field that just repeats the lead's own name are skipped. Only the domain or company name is sent to Crustdata.
- **Which match.** A domain must belong to the listing Crustdata returns. A name must equal the listing's name
  and the company must have 51 or more people (1,001 or more for a one-word name such as "Metro"), because names
  alone are easily mistaken. A lead matched this way says "matched by company name" in its Company section.
  One-word names are still the weakest matches; treat them as a hint.
- **What changes.** Only blanks are filled: the industry and the employee range ("501-1000 employees"). A value
  typed into Zoho always wins and takes over. Each company is looked up once and kept in the `companies` table;
  a company that is not found is tried again after 90 days.
- **What it cannot do.** Leads with a personal email and no company name cannot be researched (about one in five
  in September 2026), and small local businesses are often not listed.

`.venv/bin/python -m meridian.research status` shows how many leads have company details and how many companies
are waiting. `... research run --limit 500` looks up the next 500.

### Other ways in

Leads can also be pushed to `POST /webhooks/lead?token=<secret>` as JSON (set `MERIDIAN_WEBHOOK_TOKEN` in `.env`
first), for example from a Framer form. It accepts `id`, `name` (or `first_name` + `last_name`), `title`, `company`,
`email`, `owner`, `status`, `utm_source`, `utm_medium`, `utm_campaign`, `lead_source`, `employees`, `revenue`,
`industry`, `form`, `pricing_visits`, `emails_sent`, `emails_opened`. This needs the app on a public address.

Each remaining source needs a small connector that fills these tables on a schedule:

| Source | Tables |
|---|---|
| Meta Ads, LinkedIn Ads | `ad_campaigns`, `ad_creatives`, `ad_daily`, and the paid rows of `channel_daily` |
| Apollo, HeyReach | `outbound_campaigns`, `outbound_daily`, and their rows of `channel_daily` |
| Google Analytics | `traffic_daily`, `page_daily`, `form_daily` |
| Search Console | `query_daily`, `search_daily`, and the search row of `channel_daily` |

After a sync, set `last_sync_at` on the matching row of `sources` so the top bar and Settings show it as fresh.

## Scheduled jobs

Zoho sync and alert checks run inside the app. Owner reminders send email, so they are a separate job:

```bash
.venv/bin/python -m meridian.jobs reminders   # every morning
```

## Connecting Apollo and HeyReach

```bash
./connect-apollo.sh
./connect-heyreach.sh
```

Each script explains where to create an API key, checks it, saves it in `.env` and brings the campaigns in.
After that they refresh every three hours while the app runs, or on "Sync now" in Settings. Only campaign
names and counts are read: no contact names, emails or messages.

- **HeyReach** reports day by day, so the past year arrives with its real dates (requests sent, accepted,
  replies). It does not know about meetings, so that step is not shown.
- **Apollo** reports one running total per sequence and needs a master API key. Meridian books the increase
  since the last sync on the day it sees it, so activity from before connecting shows as "sent all-time" on
  the sequence and date ranges fill in from the connection day on.
- A refused key marks the source "Disconnected"; it is not retried until "Reconnect" is pressed.

## Connecting Google Analytics and Search Console

```bash
./connect-google.sh
```

The script walks through a one-time Google Cloud setup (a project, three APIs switched on, a "Desktop app"
client), opens Google's sign-in page for view-only access, then lets you pick the Analytics property and the
Search Console site. The first sync reads the past year; after that the last week is re-read every four hours,
because Google revises recent days and Search Console runs two to three days behind.

- From Analytics: sessions per day by source and medium, and views per page.
- From Search Console: clicks, impressions and average position per day, and the same per search query.
- Not available: leads per page and form views. Analytics does not know which visit became a Zoho lead, so
  those parts of the Website screen stay hidden. Only totals are read, nothing about individual visitors.

## Connecting Meta Ads and LinkedIn Ads

```bash
./connect-meta.sh
./connect-linkedin.sh
```

Each script explains how to create a read-only access token, asks which ad accounts to read, and brings in the
past year. After that the last ten days are re-read every four hours.

- **Meta** uses a system-user token with only `ads_read`, set never to expire. It comes in ad by ad: spend,
  impressions, link clicks, and the leads Meta counted.
- **LinkedIn** first needs LinkedIn to approve "Advertising API" for an app you create (a few days). Its token
  lasts 60 days; run the script again to renew. It comes in campaign by campaign, with lead-form leads.
- Spend is taken as the plain number in the ad account's currency. It is not converted if that differs from
  Meridian's currency; the connect script says so when it does.
- "Leads" on the Paid ads screen are the platform's own count. Leads everywhere else still come from Zoho.

## Semrush (file import)

The Semrush plan has no API units, so its figures arrive as exported files. In Semrush open Organic Research
for the domain (country India), and on the **Positions** and **Competitors** tabs use the table's **Export**,
**CSV** (not "Export to PDF"). Put the files, with the names Semrush gives them, in the `semrush` folder next
to `app`. They are read within a minute while the app runs, on "Sync now" for Semrush in Settings, or with
`./.venv/bin/python -m meridian.semrush import`. Each export is kept as a dated snapshot; the Website screen
shows the newest one per domain. Sites with over a million keywords (YouTube, Google and the like) are left
out of the competitor table.

## Sign-in

```bash
./add-user.sh
```

Asks for a name, email and password and adds a person who can sign in. Sign-in switches on once one person
exists, or always when `MERIDIAN_REQUIRE_LOGIN=1`. Only a salted hash of each password is kept.
`python -m meridian.accounts list` shows who can sign in; `remove EMAIL` takes someone off.

## Hosting on Render's free plan

`render.yaml` describes the service. The free plan sleeps when idle and wipes its disk on restart, so:

- **Data** is kept in Supabase Storage. `./connect-storage.sh` (run once on the machine that has the data)
  saves the storage address and secret key and uploads the first copy. The hosted copy downloads it on start-up
  and, with `MERIDIAN_BACKUP_AUTO=1`, uploads a fresh one about 20 seconds after any change and after each sync.
  A machine without that setting never uploads by itself.
- **Syncs** run while the service is awake. An outside timer calls
  `https://<service>.onrender.com/tasks/sync?token=<MERIDIAN_TASK_TOKEN>` two or three times a day; that wakes
  it and pulls every connected source.
- **Keys** (Zoho, Google, Apollo, HeyReach, Supabase) are entered in Render's Environment page, never in the repository.
- `TZ=Asia/Kolkata` keeps dates on India time.

## Settings

These go in `.env` in this folder (one `NAME=value` per line) or in the environment.

| Variable | Purpose |
|---|---|
| `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`, `ZOHO_DC` | Written by `./connect-zoho.sh`. `ZOHO_DC` is `in` for crm.zoho.in |
| `MERIDIAN_ZOHO_EVERY_MINUTES` | Minutes between automatic Zoho syncs. Default 15 |
| `CRUSTDATA_API_KEY` | Written by `./connect-crustdata.sh`. Lets the app research new leads' companies |
| `APOLLO_API_KEY`, `HEYREACH_API_KEY` | Written by `./connect-apollo.sh` and `./connect-heyreach.sh` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GA4_PROPERTY_ID`, `GSC_SITE_URL` | Written by `./connect-google.sh` |
| `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_IDS`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AD_ACCOUNT_IDS` | Written by `./connect-meta.sh` and `./connect-linkedin.sh` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET` | Where the hosted copy keeps its data file. Written by `./connect-storage.sh` |
| `MERIDIAN_BACKUP_AUTO` | `1` on the hosted copy: upload the data file after every change |
| `MERIDIAN_REQUIRE_LOGIN` | `1` to require sign-in even before anyone has been added |
| `MERIDIAN_TASK_TOKEN` | Secret for `/tasks/sync`, the address the timer calls |
| `MERIDIAN_WEBHOOK_TOKEN` | Secret for `/webhooks/lead`. Webhooks are refused while this is unset |
| `MERIDIAN_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FROM` | Outgoing email |
| `MERIDIAN_DB` | Use a specific database file |
| `PORT` | Port for `run.sh`. Default 8321 |

Company name, product name and currency live in the `settings` table (`company`, `product`, `currency`).
Currency is `INR` (rupees with lakh and crore) or `USD`.

## Layout

```
meridian/
  api.py        HTTP endpoints and static files
  screens.py    builds the data each screen shows
  metrics.py    per-channel funnel counts for a date window
  periods.py    date ranges and comparison windows
  insights.py   week-on-week gap, cost spikes, budget pacing, ranking slips, source freshness
  alerts.py     alert rules          reminders.py  owner reminders       mailer.py  email outbox
  narrative.py  Overview sentence and weekly report draft
  scoring.py    criteria, threshold, ideal-customer ranges, rules for new leads
  zoho.py       Zoho CRM connection  scheduler.py  background sync while the app runs
  research.py   company research: industry and size from Crustdata
  outbound.py   Apollo sequences and HeyReach campaigns
  google.py     Google Analytics 4 and Search Console
  ads.py        Meta Ads and LinkedIn Ads
  semrush.py    Semrush exports read from the semrush folder
  health.py     health checks: each key figure against a benchmark and against the 30 days before; raises the benchmark and drop alerts
  accounts.py   sign-in: people, password hashes, sessions
  backup.py     saves the data file to Supabase Storage and restores it on a host with no lasting disk
  team.py       targets per person (week or month), the daily checklist worked out from them, and blockers
  website.py    the Website and organic screen: visits, Google searches with and without the company name, pages by type
  ingest.py     incoming leads       seed.py       sample or empty database
  money.py      currency formatting
static/
  css/styles.css   design tokens and components
  js/main.js       shell, routing, events      js/screens/*.js  one file per screen
```

How comparisons work: lead and deal counts for a range that runs to today are compared with the previous
range up to the same time of day (so "142 this week vs 177" is like for like). Daily feeds such as spend
and sessions are compared by whole dates.

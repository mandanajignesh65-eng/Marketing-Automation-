# Event Hub: more than a tracker

* **Author:** jignesh2619
* **Date:** 2026-10-29
* **Status:** Brainstorm, step 1: working hypothesis, before the Goldfish review. Nothing built from this yet.

## Why the first version failed

The first version copied the SFF Excel file into Meridian's table style: tabs, rows, text. That is a tracker in another place. A marketer already has the sheet, so it gives them no reason to switch. A manager sees a wall of text and closes it.

**The test for this version:** every screen has to show something the sheet cannot. That means one of three things:
- something Meridian **knows by itself** (Zoho leads and deals, follow-up speed, company fit, post engagement read through Apify);
- something it **works out** (risk of slipping, return on money, comparison across events);
- something it **shows** that a sheet cannot (real posts, a timeline, a map of accounts).

## What a marketer actually struggles with at events

From the SFF tracker and from how B2B event teams work:

1. **Before:** "Will we be ready, and who is behind?" Fifty steps, five owners, deadlines bunching up in the last week. A sheet shows statuses, but not the *risk*: three critical steps due in two days, all owned by one person.
2. **Before:** "Are the right companies coming?" The point of the event is to meet target accounts, such as Tier 1 banks. Today the target list and the meetings booked live in separate places.
3. **During:** "Are we capturing everyone, and are our posts landing?" Leads pile up on paper or in a form. Posts go out, but nobody sees them together or knows which one worked.
4. **After:** "Did we follow up fast?" Most event value is lost in the first 72 hours after the event. No sheet shows how many leads were contacted within a day.
5. **After:** "Was it worth it, and should we go again?" The cost is in finance's files and the results are in Zoho, and nobody joins the two. Next year the same debate starts from zero.
6. **Across events:** "Which events are worth it?" With several events a month, the manager needs one comparison, not five sheets.

## The idea: an Event Hub with a live "event room" per event

### 1. Events home: the month at a glance (visual, not a list)
- **A timeline across the month.** Each event is a bar from its first planning day to its last follow-up day, coloured by stage, with a "today" line. Overlaps between events are visible at once.
- **One card per event.**
  - **Readiness:** a ring showing how ready the plan is.
  - **Risk:** for example "3 critical steps at risk".
  - **Leads so far, and return on money.**
- **A ranking table.** Every past event ranked by cost per qualified lead and money back. This answers "which events are worth it", and the list grows with every event.

### 2. Event room: one event, from decision to ROI
A visual page that changes with the stage:
- **Before the event:** a countdown, a readiness score, and the **risk radar**: what will slip and who is overloaded. Below it, the **plan as a timeline**: phases as swim lanes, steps as dots, overdue steps in red, with a lane for each owner.
- **During the event:** today's leads coming in, hot leads flagged, booth meetings held against the target, and the post wall.
- **After the event:** a **follow-up speed meter** showing the share of event leads that an owner touched within 24 hours, 72 hours and 7 days. The figures come from Zoho owner activity, which Meridian already tracks. Next to it, the **money funnel**: cost → leads → qualified → deals → won, with the cost per step and the money back.

### 3. Target accounts: who we wanted, who we met
- Paste or upload the target-company list with its tiers, as in the SFF "Target companies" tab.
- Meridian matches each company against Zoho leads and deals by company name, using the matching it already has. It shows a **coverage map**: for example, "Tier 1: 7 of 18 met · 3 now have deals".
- Only company names appear, never people.

### 4. Creatives wall: the real posts, not links
- Paste a post's link and Meridian shows **the post itself**, using each platform's own embed:
  - Instagram and LinkedIn show the real post card.
  - YouTube shows the player.
  - Facebook and X use their own embed.
  - These embeds work for public posts with no login.
- Engagement (likes, comments, views) is read on a timer through Apify, which Meridian already uses for competitors' Instagram, Facebook and X. LinkedIn engagement is read through the existing LinkedIn connection where it allows.
- The wall is sorted by engagement, with a **best post** badge, and can be filtered by platform and by phase (teaser, live, recap).

### 5. Plan from a standard playbook, by event type
- The standard steps come in templates by event type: Booth or exhibition, Sponsor plus speaking slot, Partner joint event (such as with Vonage), Roundtable or dinner, and Webinar.
- Each template sets due dates from the event dates. Each step has a "critical" flag, which feeds the risk radar.
- Owners are picked from the team. Each person gets **"my event steps this week"** on the Targets screen, so steps reach the people doing them instead of sitting in a list.

### 6. Budget: planned against spent, with return on money
- A budget split by kind (space, booth, travel, print, ads) shown as a bar or ring of planned against spent.
- Return on money worked out live from Zoho:
  - Cost per lead and cost per qualified lead.
  - Value of new deals for each ₹1, and money won for each ₹1.
  - The same figures compared with the average of past events.

### 7. One-click manager report
- A clean, printable recap page: headline numbers, money funnel, follow-up speed, best posts, target accounts met, cost, lessons and the go-again decision.
- It can be sent through Meridian's existing weekly report email.

### 8. Ask about the event
- The existing Ask assistant gets the event's data, so a manager can ask "how is SFF going?" or "which Tier 1 banks did we meet?" and get an answer from the same figures.

## Design direction
- **Visual first.** Rings, timelines, funnels, post embeds and coverage maps. Text only for labels and one-line explanations.
- **Its own look,** not Meridian's table style. It still shares the sign-in and the data. The design will go through the design skills: `/impeccable` to shape the look, and `/cast` for motion such as the countdown and readiness ring.
- **Works on a laptop at 1366x768.** The event room's top part answers "how is it going" with no scrolling.

## What it reuses from Meridian
- Zoho leads and deals, matched by lead source.
- Company matching and the ideal-customer score, for target accounts.
- Owner activity timestamps, for follow-up speed.
- Apify, for post engagement.
- The LinkedIn connection.
- The Ask assistant.
- Sign-in and the team list.

## Open questions for the owner
1. **Event types:** which types does the team run most often (booth, sponsor with talk, partner joint, roundtable, webinar)?
2. **Target lists:** does every event have a target-company list like SFF, or only big ones?
3. **Report readers:** does the manager want the report as a page, a PDF, or an email?
4. **Event lead tagging:** are event leads always tagged with a lead source in Zoho (like "GFF 2026")? Or do some arrive with no source, entered by sales after the event?

## Proposed first build (the smallest version that is clearly more than a tracker)
- Events home: timeline, event cards and ranking.
- Event room: stage-aware top section, plan timeline with risk radar, money funnel, follow-up speed.
- Creatives wall with real embeds. Engagement comes in step 2.
- Target accounts coverage.
- One-click report.

The Ask assistant hookup and engagement reading come right after.

## Analysis: the Goldfish review (six reviewers, 2026-10-29)

The direction holds, but three of the brief's claims did not survive a check against the code.

1. **Follow-up speed has no data yet.** Meridian keeps only the *latest* owner touch on a lead, not the first. Booth leads are also loaded into Zoho a day or more after the event.
   - Fix: store a first-touch time, written once, from now on.
   - Start the clock at the event's last day.
   - Show how many leads each number covers.
   - It will work for upcoming events, not past ones.
2. **Counting only leads tagged with the event undercounts B2B events.** A Tier 1 bank with an open deal that we met at the booth adds nothing.
   - Fix: two numbers. **Sourced** is leads and deals whose source is the event. **Influenced** is target accounts that already had an open deal during the event window.
   - Untagged leads need a fallback.
3. **The ranking of events is unfair unless the figures are frozen.** A change to the scoring rule rewrites history, and recent events always rank low because deals close months later.
   - Fix: freeze each event's figures when it closes.
   - Compare all events at the same age, for example 90 days after.
   - Mark small samples, and show "too early" for recent events.
4. **Target-account matching must be honest.**
   - Match by cleaned company name or domain.
   - Let the user confirm matches.
   - Say "in Zoho" or "engaged", not "met".
   - Strip people's names when the list is pasted in.
5. **Post embeds:**
   - Instagram and Facebook's official embeds need a Meta app token, and X needs its own script.
   - Apify reads whole profiles, not single post links. Our own LinkedIn and YouTube are already read as an "own" account, so engagement can be matched from those reads.
   - Run embeds in a locked-down frame, limited to known sites.
   - Rank the best post within each platform, never across platforms.
6. **Risk radar needs data the plan does not have yet:** event types, a "critical" flag on steps, and after-event steps counted from the last day, not the first.
7. **Costs:** add a planned amount per kind. Link event ads to the event rather than typing them in again, so Overview does not count the same spend twice.
8. **Every number needs a written definition:** readiness, at risk, money back and touched. Each number gets one main place on screen.
9. **The "during the event" view would be mostly empty,** because leads reach Meridian only after they are entered in Zoho. Cut it down.

**What a marketer and manager would still miss:**
- Influenced pipeline.
- Meetings booked against held.
- Accounts engaged but not followed up after 7 days.
- Event cost per qualified lead next to paid ads and outbound.
- A go-again call based on pipeline that has had time to grow.

## Staging after review

1. **Stage 1:** event room top section: stage, money funnel (sourced and influenced) and target-account coverage. Plus the cross-event ranking with frozen figures. The printable event room is the manager's report.
2. **Stage 2:** start storing first touch now, then the follow-up speed meter.
3. **Stage 3:** event types, critical steps, readiness and risk radar, and the month timeline.
4. **Stage 4:**
   - Post wall with embeds in safe frames.
   - Engagement matched from our own account reads, with a monthly Apify spending cap.
   - The Ask assistant.
   - A recap in the weekly email.

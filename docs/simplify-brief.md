# Simplify Meridian: brief for the design doc

Written 2026-10-29 from the owner's answers. Input for `/egm:egm-brainstorm`.

## The problem

Meridian has 16 screens. The same figures (leads, qualified, deals, won, spend per channel) appear on
Overview, Funnel, Channels and each channel page. The owner built it and still finds it confusing.

## Decisions already made by the owner

- Remove **Funnel** and **Channels** as screens.
- Channel pages stay: **Paid ads**, **Outbound**, **Website & organic**.
- Fold **Lead quality** and **Ideal customer** into **Leads** (as tabs or sections), not separate screens.
- Keep **Competitors**, **Subscriptions**, **Reports**, **Alerts & reminders**, **Targets**, **People**, **Settings**.
- Remove the **All channels** filter from the top bar. Each channel page shows only its channel.
- **Overview** must answer three things at a glance:
  1. Which channel is working (and which is not).
  2. Are we on track (team targets and month targets).
  3. Which alerts need watching.

## Proposed sidebar (16 screens to 11)

- Overview
- Channels: Paid ads, Outbound, Website & organic
- Leads (tabs: All leads, Quality, Ideal customer)
- Competitors
- Team: Targets, People
- Operations: Subscriptions, Reports, Alerts & reminders
- Settings (also gets the score rules)

## Proposed Overview, top to bottom

1. Five headline numbers: Leads, Qualified, Deals started, Deals won, Value of new deals, each against last period.
2. **Channels table**: one row each for Paid, Outbound, Website, Organic. Columns: Leads, Qualified,
   Qualified %, Deals, Won, Spend, Cost per qualified lead, change against last period. Best and worst row marked.
   Each row opens its channel page. This replaces Funnel's "Conversion by channel" and "Cost per stage",
   and the Channels screen's ranking.
3. **On track**: team targets (as now) and the month's marketing targets.
4. **Needs attention**: open alerts and renewals due soon.
5. Leads per day chart, smaller, at the bottom.

## What must not be lost

- Anything only Funnel or Channels shows today must move to Overview or a channel page, or be dropped on purpose.
  The outreach steps (people reached, messages, replies) already live on Outbound.
- Figures must still agree across screens (see the data audit of 2026-10-28).
- Old links such as `#/funnel` and `#/channels` should open Overview, not an error.

## Open questions for the brainstorm

- Website and Organic: one page or two? Overview shows them as two rows.
- Where the Leads "Quality" and "Ideal customer" tabs go when a team member only wants the list.
- Do the Overview channel rows need a small trend line, or is the change figure enough?

## Answers taken as working assumptions (owner said "go with recommendations", 2026-10-29)

1. **Daily use:** the owner opens Overview first, then the page of whichever channel looks weak. Team members
   mostly use Targets and Leads.
2. **What confuses today:** the same figures on several screens, and too many screens to choose from.
3. **Organic:** every inbound lead that is not paid: website forms, Google search, social posts, referrals.
   This matches the data: each channel belongs to one group, `paid`, `outbound` or `organic`
   (`channels.grp` in `meridian/db.py`). So Overview shows three channel rows (Paid, Outbound, Website & organic)
   plus a "No channel" row for leads whose source has no channel, so totals add up. Website & organic stays one page.
4. **On track means two things:** each person's targets (Targets screen) and the company's monthly targets for
   leads, qualified leads, pipeline, deals won and spend, which are typed in on Settings. The code that measures
   month progress against those (`target_rows` in `meridian/screens.py`) exists but no screen shows it today.
5. **Success:** the owner can answer "which channel works, are we on track, what needs watching" from Overview
   alone, without scrolling past one screen height on a laptop, in under two minutes; the sidebar goes from 16
   items to 11; no figure appears on two screens under two different names.
6. Leads gets tabs: **All leads** (the default, unchanged list), **Quality**, **Ideal customer**.
   Score rules move to Settings.

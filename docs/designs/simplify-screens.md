# Simplify Meridian's screens

*   **Author:** jignesh2619
*   **Status:** Proposed (revised after Stage 5 zoom-out review)
*   **Date:** 2026-10-29

--------------------------------------------------------------------------------

## Overview

Meridian is Chat360's internal marketing dashboard. The code is in `D:\meridian` on branch `gcp`, and the live site is meridian.sendwise.co.in. It reads leads and deals from Zoho, ad figures from Meta and Google, outreach figures from Apollo and HeyReach, and website figures from Google Analytics and Search Console. The marketing team uses it for three things: to see which channel brings good leads, how each person is doing on their targets, and what needs attention.

This design cuts the sidebar from 16 items to 12. It rebuilds the Overview screen so that the three daily questions are answered on one screen. How figures are counted does not change, with one exception: "Website & organic", which today means different things on different screens.

## Terms

*   **Lead source**: the text Zoho stores on a lead saying where it came from, for example "Website form" or "AI Summit 2026".
*   **Channel**: Meridian's grouping of lead sources, for example "Meta ads" or "Search". Settings decides which lead source belongs to which channel. A lead whose source is not given a channel has "No channel".
*   **Channel group**: every channel belongs to one of four groups: Paid ads (`paid`), Outbound (`outbound`), Website & organic (`organic`), Events (`events`).
*   **Score rule**: Meridian scores each lead from 0 to 100. A lead is "qualified" when its score reaches the pass mark (the threshold) or someone marked it by hand. The rules live on the Quality screen.
*   **Quality preview**: on the Quality screen, changing a rule shows how many leads would qualify before saving.
*   **Comparison period**: what the top-bar compare switch sets each figure against (today: the 3-month average, scaled to the same length).
*   **On track** (people's targets): a weekly target is on track when its progress is at or ahead of where it should be by today, as the Targets screen already works it out.
*   **Ask assistant**: the "Ask" panel on the right of every screen. Its answers end with a link to the screen where the figures can be checked.
*   **Segmented control**: Meridian's existing row of joined buttons, one highlighted, used for Day / Week / Month.
*   **Render**: an old hosting copy of Meridian that publishes the `main` branch by itself.
*   **EGM, Stage 5 review**: the design-review process used to write and check this document. Stage reports are in `D:\ICP`.
*   **`/dembrandt`, `/impeccable`, `/ponytail-review`**: review tools for layout rules, visual polish and code that can be deleted.

## Where this came from

This design replaces `docs/simplify-brief.md`. That brief said "11 screens", but its own list counts to 12. It also listed Website and Organic as two separate rows; the data has only one organic group, so this design uses one row. The brainstorm notes behind this design are in `D:\ICP\concepts_brief_simplify.md`. Every table this design needs is repeated below, so this file stands on its own.

## The Problem

The same figures appear on four screens: Overview, Funnel, Channels and each channel page. These are leads, qualified leads, deals, deals won and spend, split by channel. Each screen lays them out differently, sometimes under different names, and "Website & organic" means two things. The owner built Meridian and still finds it confusing. A new team member has no way to know which screen to look at.

What the code shows today:

*   **Repeated figures.** Overview's "Results by source" table, the Channels screen's ranking and Funnel's "Conversion by channel" show the same counts per channel.
*   **Too many places to look.** A leader's sidebar has 16 items; a team member's has 14.
*   **One thing, several names.** Leads with no channel are called "No channel", "Unattributed", "Not known", "Channel not known" and "Unmapped" on different screens. The organic group is called "Inbound" on Overview and "Website & organic" in the sidebar. "Value of new deals" and "Pipeline" are the same figure.
*   **One name, two meanings.** The sidebar calls the page "Website & organic", and Overview's matching row counts every organic lead (search, direct, referral, organic social, website forms). The Website page's headline "Website leads" counts only website-form and chatbot leads. Both are right, but they share a name.
*   **A control that mostly does nothing.** The top-bar "All channels" filter only changes the Funnel screen. Every other screen greys it out.
*   **Built but never shown.** Meridian has code that measures this month's progress against the monthly targets typed into Settings (`target_rows`), but no screen shows the result. So no screen answers "are we on track for the month?".

The fix: remove the Funnel and Channels screens, and move Lead quality and Ideal customer behind a switcher on Leads. Remove the top-bar channel filter. Make Overview answer three questions, each with a short answer and a link to the detail:

1.  Which channel works, and which does not?
2.  Are we on track: for each person this week, and for the company this month?
3.  What needs watching?

## Goals

*   **G1. Overview fits one screen.** The owner answers the three questions from Overview alone, without scrolling, in under two minutes. The test runs on a 1366x768 screen at 100% browser zoom. The owner does it once, timed, answering out loud.
*   **G2. 12 sidebar items.** A leader's sidebar has exactly these 12 items: Overview · Paid ads, Outbound, Website & organic · Leads, Competitors · Targets, People · Subscriptions, Reports, Alerts & reminders · Settings. A team member sees the same list without People and Settings (10 items).
*   **G3. Rows add up.** Each lead in the chosen period is counted in exactly one Overview channel row: Paid ads, Outbound, Website & organic, Events or No channel. The rows add up to the headline figures.
*   **G4. One name per figure.** Every screen uses the names in the Glossary below.
*   **G5. Nothing lost by accident.** Each item that today appears only on Funnel or Channels is either moved or dropped, as listed in the "What moves where" table below.
*   **G6. No link leads nowhere.** Overview's cards, the chart legend and the Ask assistant's links no longer point to a removed screen. Old bookmarks to `#/funnel` or `#/channels` open the same fallback as any unknown address does today: Overview for a leader, Targets for a team member.
*   **G7. Figures do not move.** For one fixed date, and for Day, Week and Month, each figure that exists both before and after the change keeps its value. Only names change. A one-off before-and-after comparison shows this.

## Non-Goals

*   No change to how any figure is calculated.
*   No new charts. The daily leads chart on Overview is removed, not shrunk. The six-month trend from the Channels screen is not moved.
*   No separate Website page and Organic page.
*   No change to who may see or change what. Since 2026-10-28 Meridian has one role: everyone who signs in is a leader and can open Settings. So the Settings links on Overview, and the monthly targets and ad budgets in the "On track" block, are visible only to people who could already see them in Settings. **Score rules stay on the Quality screen**: moving them is not needed to reach the goals, and Quality is where people already look for them.
*   No redesign of the screens that stay, beyond taking in the moved items.
*   The Leads screen keeps its own channel filter.
*   No database changes.
*   The organic and outbound budget fields in Settings stay, even though nothing uses them today. Removing them is a separate clean-up.
*   No work on the Claude/ChatGPT connector (separate brief, `D:\ICP\concepts_brief.md`).

## Glossary (one name each)

| Name | Means | Old names to replace |
|---|---|---|
| Leads | Leads in Zoho created in the period | |
| Qualified leads | Leads whose score reaches the pass mark, or that someone marked qualified by hand | |
| Qualified % | Qualified leads divided by leads | |
| Deals started | Deals created in Zoho in the period | Deals |
| Deals won | Deals marked won in the period | Won |
| Value of new deals | Total value of deals started | Pipeline |
| Spend | Money spent on ads in the period | |
| Cost per qualified lead | Spend divided by qualified leads | |
| Paid ads / Outbound / Website & organic / Events | The four channel groups (`paid`, `outbound`, `organic`, `events`) | "Inbound", "Inbound · organic", "Inbound · paid" |
| No channel | Leads whose lead source has no channel | Unattributed, Not known, Channel not known, Unmapped |
| Website form leads | Leads from the website forms and the chatbot only (the Website page's headline figure and its visitor-to-lead rate) | Website leads |
| Leads reported by Meta / LinkedIn | Leads counted by the ad platforms, on Paid ads only | (shown as "Leads" on Paid ads today) |

## What moves where

| Item | Today on | After |
|---|---|---|
| Counts by channel (leads, qualified, deals, won, value, spend) | Funnel, Channels, Overview | Overview channel table only |
| Qualified %, lead-to-deal %, win rate | Funnel cards | Overview table has Qualified %. Lead-to-deal % and win rate are dropped |
| Pipeline value per channel | Funnel | Overview table, "Value of new deals" column |
| Sources inside each channel (one event's or one campaign's results) | Channels | The matching channel page. For Events: a "Sources inside" summary at the top of Leads when Leads is filtered to the Events group |
| Warning that some leads have no channel, with a link to Settings | Channels | The No channel row on Overview |
| Cost per 1,000 impressions, per click, per lead, per deal, per won deal | Funnel | Dropped. Paid ads keeps its own per-lead figures, and Overview shows cost per qualified lead |
| Audience split by type of company | Funnel | Dropped. Ideal customer's "Leads matching the profile" answers the same question with Meridian's profile rule |
| "People reached" (visits plus outreach messages) | Funnel | Dropped. Outbound and Website show their own parts |
| Channel mix at each stage | Funnel | Dropped |
| Six-month trend per channel | Channels | Dropped |
| "Most leads / Best fit / Most deals" rankings | Channels | Dropped. Overview's best and weakest markers replace them |
| Outreach tool figures per channel (sent, opened, replied) | Channels | Already on Outbound; nothing to move |
| Leads per day chart | Overview | Dropped |
| Headline spend and headline cost per qualified lead | Overview cards | Overview channel table, per row |

## Open Questions

*   None. (Q1, whether Overview hides the targets block on sample data, is closed: the "On track" block shows on sample data too, so the checks below can be run locally.)

## Critical User Journeys (CUJs)

### CUJ 1: Monday morning check

*   **Given**: The owner is signed in on a 1366x768 laptop. The date picker is set to "Month".
*   **When**: They open Meridian. It opens on Overview.
*   **Then**: Without scrolling, they see:
    *   the five headline numbers, with the change against the comparison period;
    *   a channel table with one row each for Paid ads, Outbound, Website & organic, Events and No channel, with the best and weakest rows marked;
    *   the month's company targets as bars labelled "October so far";
    *   each person's "X of Y weekly targets on track", labelled "This week" (monthly personal targets are not counted here; they stay on Targets);
    *   up to three open alerts.

    Clicking the weakest row opens that channel's page.

### CUJ 2: Which channel is not working

*   **Given**: Overview is open for the current month. Paid ads spent money, but no lead qualified.
*   **When**: The owner reads the channel table.
*   **Then**:
    *   The Paid ads row shows "spent, none qualified" in red.
    *   A channel with fewer than 20 leads in the period is never marked best or weakest.
    *   The No channel row is never marked.
    *   A row with no spend shows "no spend recorded" where the cost would be.

### CUJ 3: Finding the score rules

*   **Given**: A team member wants to see why a lead is "Not qualified".
*   **When**: They click Leads in the sidebar, then "Quality" in the switcher at the top.
*   **Then**: The Quality screen opens with its rules, as today, and "Leads" stays highlighted in the sidebar. Old bookmarks to `#/quality` and `#/icp` still work, because those screens still exist.

### CUJ 4: Looking at one event's results

*   **Given**: The team ran a webinar last week. Today, only the Channels screen's "Sources inside" list shows it.
*   **When**: The owner clicks the Events row on Overview.
*   **Then**: Leads opens, filtered to the Events group, and shows that webinar's leads.

### CUJ 5: No monthly targets typed in

*   **Given**: Nobody has entered this month's targets in Settings.
*   **When**: The owner opens Overview.
*   **Then**: The "On track" block says "No monthly targets yet", with a link to Settings. The rest of Overview is unaffected.

### CUJ 6: First days of the month

*   **Given**: It is the 3rd of the month and targets are set.
*   **When**: The owner opens Overview.
*   **Then**: The monthly bars show the figures so far, but no status label ("Behind", "Slightly behind", "On pace", "Over budget", "On budget", "Under budget") appears before the 7th. Labels show from the 7th of the month on, so slow first days do not set off a false alarm.

## Technical Plan (Architecture)

### How Meridian is put together today

Meridian is one Python web server (FastAPI, `meridian/api.py`) and one browser app made of plain JavaScript files (`static/js/`). There is no build step: the browser loads the files as they are.

*   Each screen is one JavaScript file in `static/js/screens/`. It has a `load` step, which asks the server for data, and a `render` step, which draws the HTML.
*   `static/js/main.js` holds three things:
    *   the sidebar list;
    *   the top bar: date picker, compare switch and channel filter;
    *   the routing, which reads the part of the web address after `#/` and picks the screen. An unknown address opens Overview for a leader and Targets for a team member.
*   Each screen has one server address, for example `/api/overview`. That address calls one function in `meridian/screens.py`.
*   All per-channel counts come from one function, `metrics.channel_stats` (in `meridian/metrics.py`).
    *   Each channel belongs to one of four groups in the `channels` table: `organic`, `paid`, `events` or `outbound`.
    *   A lead whose lead source has no channel has an empty `channel_id`.

```text
 browser                                   server
 ───────                                   ──────
 main.js  ── routing (#/overview) ──┐
                                    ▼
 screens/overview.js  ── GET /api/overview ──►  api.get_overview
        ▲                                         ├─ screens.overview ─► metrics.channel_stats ─► SQLite
        │                                         └─ team_summary(targets_view)
        └──────────── JSON ◄───────────────────────┘
```

The design keeps this shape. It adds no new server addresses and no new mechanism in `main.js`.

### Change 1: Sidebar and top bar (`static/js/main.js`)

*   **Sidebar.** Funnel, Channels, Ideal customer and Lead quality leave the sidebar. The headings become: Overview · **Channels**: Paid ads, Outbound, Website & organic · **Leads & market**: Leads, Competitors · **Team**: Targets, People · **Operations**: Subscriptions, Reports, Alerts & reminders · Settings.
*   **Highlighting.** The Quality and Ideal customer screens still exist. While either is open, the sidebar highlights "Leads".
*   **Top bar.** The channel filter is deleted, together with the app's `channel` setting, its menu and its action. The date picker and the compare switch stay.
*   **Funnel and Channels.** These are removed from the screen list. No redirect is added: an old link falls back the way any unknown address already does.

### Change 2: Overview data (`meridian/screens.py`, `overview`)

The function keeps its name and its address.

*   **Channel rows.** The existing results-by-group table (`by_kind`, shown today as "Results by source") becomes the channel table. Today it always lists organic, outbound and paid, and lists Events and "Not known" only when they have figures; the new table always has five rows.
    *   It always returns five rows, in this order: `paid`, `outbound`, `organic`, `events`, `none`. Each row uses the glossary name.
    *   Each row has these figures, for the chosen period and for the comparison period: leads, qualified, deals started, deals won, value of new deals and spend.
    *   The server also works out, for each row:
        *   **Qualified %**: qualified divided by leads.
        *   **Cost per qualified lead**: only when spend and qualified are both above 0.
        *   **`rank`**: `best`, `weakest` or empty.
            *   Only rows other than `none` with at least 20 leads, and not `spent_none`, take part.
            *   `best` goes to the highest Qualified %, `weakest` to the lowest. Tied rows all get the mark.
            *   No marks if fewer than two rows take part, or if the highest and lowest Qualified % are less than 5 percentage points apart.
        *   **`spend`**: `spent_none` (spend above 0, qualified 0), `no_spend` (spend 0) or `normal`. This is separate from `rank`, so a row with no spend can still be best or weakest.
        *   **Empty numbers**: with 0 leads, Qualified % is shown as "—". With spend above 0 and none qualified, the cost cell shows "—" next to the red text.
        *   **A no-channel note** on the `none` row whenever it has leads.
*   **Monthly targets.** Meridian's existing month-progress code (`target_rows`), which no screen uses today, is used here and added as `month_targets`. Three fixes inside it:
    *   **Spend.** The spend bar compares all paid ad spend with the Meta ads budget plus the LinkedIn ads budget (`budget_meta`, `budget_li`). Today Meridian only receives spend from Meta and LinkedIn, so the two sides cover the same thing. If Google ads spend is added later, it will show against a budget only once a Google budget field exists. The organic and outbound budget fields are left out.
    *   **Early days.** Before the 7th of the month every status label is empty, including the spend labels.
    *   **Name.** Its "Pipeline" row is renamed "Value of new deals".
    *   With no targets set, the list is empty, and the screen shows the "No monthly targets yet" message.
*   **Alerts.** Up to three open alerts (today four), to fit the height budget. Renewals reach Overview only as renewal alerts, which already exist.
*   **Headline figures.** Five stay: leads, qualified, deals started, deals won, value of new deals. The headline spend and headline cost per qualified lead are removed; they are shown per row in the table.
*   **Removed from the response.** These are calculated today but never shown: visits, replies, outreach, journey, funnel and "day of". The per-day chart data and the per-channel counts behind the chart are removed too. The `channel` argument goes, because the filter is gone.
*   **Team targets.** `api.get_overview` keeps adding each person's targets, but the per-person count uses weekly targets only, so the "This week" label is true.

### Change 3: Overview screen (`static/js/screens/overview.js`)

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Leads │ Qualified leads │ Deals started │ Deals won │ Value of new deals │  ← follow date picker
├──────────────────────────────────────────────┬───────────────────────────┤
│ Channels · Month to date                     │ On track                  │
│ Paid ads            … flag                   │  October so far: bars     │
│ Outbound                                     │  This week: one line per  │
│ Website & organic                            │  person "X of Y on track" │
│ Events                                       ├───────────────────────────┤
│ No channel   (note + Settings link)          │ Needs attention (up to 3) │
└──────────────────────────────────────────────┴───────────────────────────┘
```

*   **Headline cards.** Leads links to Leads. Qualified links to the Quality screen. The three deal cards have no link, because no screen lists deals.
*   **Channel row links.**
    *   Paid ads opens Paid ads. Outbound opens Outbound. Website & organic opens Website & organic.
    *   Events opens `#/leads?channel=events`. Leads already accepts a group as its channel filter.
    *   The No channel row has no link of its own, because Leads cannot filter to "no channel". Its note links to Settings, where lead sources are given a channel.
*   **Table columns.** Leads, Qualified, Qualified %, Deals started, Deals won, Value of new deals, Spend, Cost per qualified lead. The change against the comparison period shows under Leads and Qualified only, to keep the table narrow.
*   **Period labels.** Every block names its period in its title: "Channels · Month to date", "October so far", "This week".
*   **Height budget for 1366x768.** The right column holds at most: the monthly targets as five one-line bars; up to six people (then "See all on Targets"); up to three alerts (then "All alerts"). If a sync-warning banner is shown, the page may scroll; G1 is tested without it. The layout is checked at 1366x768 with the real team size before step 2 is called done.

### Change 4: Leads switcher (`leads.js`, `quality.js`, `icp.js`)

*   Leads, Quality and Ideal customer each show the same switcher at the top of the page: **All leads · Quality · Ideal customer**. Each choice is a plain link: to `#/leads`, `#/quality` and `#/icp`.
*   The switcher is one small shared function in `static/js/ui.js`. It uses the existing segmented control and marks the current page.
*   It replaces only the page heading (the big title) on those three screens. Everything else in that row stays: on Leads, the search box and the lead and qualified counts. Quality's and Ideal customer's own inner tabs (for example "Summary · Scoring rules") stay below it, as today.
*   Nothing else in those screens changes. Their addresses, data and buttons stay as they are.

### Change 5: Channel pages take in moved items

*   **Sources inside.** Paid ads, Outbound and Website & organic each get a "Sources inside" card, and Leads shows the same card above its list when it is filtered to the Events group. The card is a table with one row per lead source in that channel group, and the columns Source, Leads, Qualified, Deals started, Value of new deals.
    *   A source with the same name in two channels of the group is one row (figures added).
    *   Leads and deals are both grouped by their lead source text only (today leads fall back to the campaign name and deals do not, which can split one source over two rows). Rows are sorted by leads, then deals, highest first. Anything with no lead source is counted under "Source not recorded".
    *   With no rows: "No leads from this channel in the period."
    *   The server code is the "sources inside" part of today's `channels()` function. It moves into a shared helper that takes the page's group.
*   **Website & organic** (built by `website.build` in `meridian/website.py`; the older `web()` in `screens.py` is not used by any screen). The headline "Website leads" is renamed "Website form leads". Its count, the visitor-to-lead rate and the per-website picker do not change.
*   **Paid ads.** The headline lead figure is labelled "Leads reported by Meta / LinkedIn". Its per-lead costs are labelled "per lead reported by Meta / LinkedIn", so they cannot be mistaken for CRM figures.

### Change 6: The assistant's links (`meridian/assistant.py`)

The assistant's "check it here" table points three kinds of data at Funnel or Channels: deals, channels and channel daily. All three now point to Overview. It has no Quality or Ideal customer entries today, so nothing else changes.

### Change 7: Names

The group labels in `metrics.py` become the glossary names. Every word listed in the Glossary's "Old names to replace" column is searched for across `static/js` and `meridian`, and replaced where a user sees it.

### Order of changes

Each step is one commit. Each leaves a working app and can be undone on its own with `git revert`. The work happens on branch `simplify-screens`, made from `gcp`. It is deployed only after the owner has seen it, by merging into `gcp`. It never goes to `main`, because Render publishes `main` automatically.

0.  **Before figures.** Run Meridian on its built-in sample data (`MERIDIAN_SAMPLE=1`). The sample data pins Meridian's clock to a stored date (the `demo_now` setting), so figures saved on different days are comparable. The sample data has no sign-in, so no account is needed. Save the answers of `/api/overview`, `/api/paid`, `/api/outbound` and `/api/web` with `range=day`, `range=week` and `range=month` to a scratch folder outside the repository.
1.  **Changes 1 and 6.** Sidebar, top-bar filter removed, assistant links, and Overview's chart-legend link to Channels removed. Quality and Ideal customer stay in the sidebar for now. Funnel and Channels leave the screen list, but their files stay.
2.  **Changes 2, 3 and 7.** Overview data and screen, and the names. Compare: the new five rows must equal the old results-by-group rows, and the headline figures must not change.
3.  **Change 4.** Leads switcher. Quality and Ideal customer leave the sidebar in this same step.
4.  **Change 5.** Channel pages. Compare: only the Website & organic figures may change.
5.  **Delete the leftovers.** Remove `funnel.js`, `channels.js`, the `funnel()` and `channels()` server functions, the `/api/funnel` and `/api/channels` addresses, and `audience()`. Also remove the unused `overview_summary` in `meridian/narrative.py` and the funnel styles. Compare once more.

## Alternatives Considered

### Alternative A: Only hide Funnel and Channels from the sidebar

*   **Pros**: About ten lines of change. No risk to any figure. Undone in seconds.
*   **Cons**: Fixes only the "too many screens" part. Overview still cannot say whether the month is on track, names still differ, and "Website & organic" is still counted two ways.
*   **Reason for Rejection**: Rejected as the whole solution, because it does not answer "are we on track", does not fix the names, and leaves dead code. Its sidebar change is reused as step 1.

### Alternative B: Keep Funnel as a Leads tab

*   **Pros**: Nothing on Funnel is lost, and deal figures keep a home.
*   **Cons**: Funnel's main content repeats Overview's channel table, so the repetition stays, one level deeper.
*   **Reason for Rejection**: Moves the clutter instead of removing it.

### Alternative C: Real tabs inside Leads, handled by `main.js`

*   **Pros**: One address (`#/leads?tab=…`) for all three views.
*   **Cons**: It would add a new mechanism to the core of the app: tab lookup for loading, drawing, clicks, pop-ups and per-screen memory. The Quality preview would need a code change to keep working. Old `#/quality` links would need redirects, and the step order would leave the score-rules editor unreachable for a while.
*   **Reason for Rejection**: A shared switcher on three existing screens gives the user the same result with no change to `main.js`'s core. (Raised in Stage 5 review.)

### Alternative D: Overview as cards each person can arrange

*   **Pros**: Each person picks what they see.
*   **Cons**: Needs saved layouts (a database change) and drag-and-drop code, and gives everyone a different Overview.
*   **Reason for Rejection**: The problem is already too much choice.

### Alternative E: Split "Website" and "Organic" into two rows and two pages

*   **Pros**: Matches how the owner first described the channels.
*   **Cons**: The data has one `organic` group. Splitting it needs a new rule for which sources are "website", a new mapping, and a second page, and it changes past figures.
*   **Reason for Rejection**: Changes how figures are counted (against G7). It can be done later on its own.

### Alternative F: Fold Events into Website & organic

*   **Pros**: One row fewer.
*   **Cons**: Event leads would hide inside organic figures, and "Website & organic" would mean a third thing.
*   **Reason for Rejection**: Breaks G4. A separate row costs one line.

### Alternative G: Keep the top-bar channel filter

*   **Pros**: No change for anyone used to it.
*   **Cons**: It only changes Funnel, which is being removed. Leads has its own filter.
*   **Reason for Rejection**: After Funnel goes, it does nothing anywhere.

### Alternative H: Rank channels by cost per qualified lead

*   **Pros**: The usual marketing measure.
*   **Cons**: Only Paid ads records spend. The other channels could not be ranked, and a blank cost looks the same as "spent, none qualified".
*   **Reason for Rejection**: Qualified % works for every channel. Cost per qualified lead is still shown as a column where spend exists.

### Alternative I: A permanent figure-check script in the repository

*   **Pros**: Can be re-run on any later change.
*   **Cons**: Overview's rows are renamed, so a script that matches figures by name cannot prove them unchanged. A "rows add up" check is true by construction. Nobody has asked for a lasting check.
*   **Reason for Rejection**: A one-off before-and-after save, plus one comparison by hand of the rows, proves the same thing for this change. (Raised in Stage 5 review.)

--------------------------------------------------------------------------------

## Risks & Mitigations

| Risk | What limits it |
|---|---|
| Overview does not fit 1366x768 with the real team and alerts (G1 fails late). | Height budget in Change 3: five one-line bars, up to six people, up to three alerts. Checked at 1366x768 with the real team size before step 2 is called done. |
| The sample data has no Events, Website form, chatbot or Google ads channels, so the local before-and-after check cannot test the Events row, the Events "Sources inside" card or CUJ 4. | These are checked on the live site right after deploy, with the owner, before the change is called done. The local check still proves the four other rows and the headline figures. |
| Old `#/funnel` and `#/channels` bookmarks land on Overview with no message. | Accepted: Overview now holds what those screens showed. |
| A merge into `main` by mistake would publish the change through Render. | All work is on `simplify-screens`, merged only into `gcp`. |
| In months with few leads, no channel has 20 leads, so no best or weakest marks show. | Accepted: a mark on a handful of leads would mislead. The table still shows every figure. |
| People who used the top-bar channel filter lose it. | Only Funnel used it. Leads keeps its own channel filter, and each channel has its own page. |
| The "Sources inside" grouping changes from "lead source, else campaign" to "lead source" only, so a campaign without a lead source now shows under "Source not recorded". | Accepted: leads and deals now land in the same row. The Leads list can still be searched by campaign. |

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security & Privacy**: No change to who can see what (see Non-Goals: everyone who signs in is a leader). The before-and-after figures come from the built-in sample data, so no customer data is copied to a PC.
*   **Performance**: Overview gets lighter. It stops calculating figures it never showed, and the daily chart query goes. It adds one month of channel figures for the monthly targets.
*   **Rollout & Rollback**:
    *   Deploy by merging `simplify-screens` into `gcp`, then running on the server: `cd /opt/meridian && sudo git pull && sudo docker compose up -d --build`.
    *   Roll back with `git revert` of the merge, and the same deploy command.
    *   There is no database change, so no data needs undoing.
    *   Open browser tabs reload themselves when the app version changes.

--------------------------------------------------------------------------------

## Future Improvements

*   A deals list, so the deal cards on Overview can link somewhere.
*   A "no channel" filter on Leads, so the No channel row can link to its leads.
*   Remove the unused organic and outbound budget fields from Settings, or give them a spend source.
*   A Website / Organic split, if the owner needs it (Alternative E).

--------------------------------------------------------------------------------

## Detailed Implementation Plan

All paths are inside `D:\meridian`, on branch `simplify-screens` (made from `gcp`).

### Target Files to Create/Modify

#### 1. `static/js/main.js` (Modify)

*   **Type / Scope**: Browser app shell.
*   **Proposed Changes**:
    *   **Sidebar list:** the new headings and items from Change 1. In step 1, Quality and Ideal customer stay under "Leads & market". In step 3 they leave it.
    *   **Highlighting:** the sidebar marks "Leads" as current while the Quality or Ideal customer screen is open.
    *   **Screen list:** remove the `funnel` and `channels` imports and entries (step 1).
    *   **Top bar:** delete the channel filter, meaning the menu, its label, the `channel` value in the app state, the `uses.channel` block and the `setChannel` action.
    *   **Fallback name:** change the name `ctx.channel` gives an unknown channel from "Unmapped" to "No channel".
    *   **Legend link (step 1):** Overview's chart-legend link to Channels goes in step 1, before the chart itself goes in step 2.
*   **Why**: Changes 1 and 7.

#### 2. `static/js/ui.js` (Modify)

*   **Proposed Changes**: Add `leadsSwitch(current)`. It returns the segmented control with three links: "All leads" to `#/leads`, "Quality" to `#/quality`, "Ideal customer" to `#/icp`. The one passed as `current` is marked.
*   **Why**: Change 4, one shared switcher.

#### 3. `static/js/screens/leads.js`, `static/js/screens/quality.js`, `static/js/screens/icp.js` (Modify)

*   **Proposed Changes**:
    *   Each screen's page header shows `leadsSwitch(...)` in place of its title row. Inner tabs and everything else stay.
    *   `icp.js`: replace "Channel not known" (where it reaches the screen) with "No channel".
*   **Why**: Changes 4 and 7.

#### 3a. Events "Sources inside" on Leads (`static/js/screens/leads.js`, `meridian/screens.py` `leads`)

*   **Proposed Changes**: When the Leads channel filter is a channel group, `leads()` also returns `inside = sources_inside(...)` for that group, and `leads.js` draws the "Sources inside" card above the list. Overview's Events row links here.
*   **Why**: Change 5; keeps per-event results after the Channels screen goes (CUJ 4).

#### 3b. `meridian/api.py` `team_summary` (Modify)

*   **Proposed Changes**: Count only weekly targets for each person (`period == 'week'`).
*   **Why**: Overview labels the count "This week".

#### 4. `meridian/screens.py` (Modify)

*   **Proposed Changes**:
    *   **`overview(conn, now, p)`:**
        *   Drop the `channel` argument and its filtering.
        *   Return the five channel rows with glossary names, current and comparison figures, Qualified %, cost per qualified lead, the flag, and the no-channel note. The rules are in Change 2; the minimum is 20 leads.
        *   Add `month_targets`.
        *   Keep the five headline figures, `period`, `date_line` and `alerts`.
        *   Remove visits, replies, outreach, journey, funnel, "day of", the chart and the per-channel chart counts.
    *   **`target_rows`:**
        *   Build the spend bar from the budget-to-channel link that `settings()` already uses. Pull that link into one shared list so both functions use it.
        *   Before day 7, leave `status` and `tone` empty.
    *   **New `sources_inside(conn, p, thr, ids)`:** the "sources inside" query lifted from `channels()`, with a filter for the given channel ids.
    *   **`paid(...)`, `outbound(...)`, `web(...)`:** each adds `inside = sources_inside(...)` for its group.
        *   **`web(...)`:** not used by any screen; deleted in step 5 with the other unused functions.
    *   **Step 5:** delete `funnel()`, `channels()`, `audience()` and `OUTREACH_TOOLS`. Search for each first, to confirm nothing else uses it.
*   **Why**: Changes 2 and 5, and the step 5 clean-up.

#### 5. `meridian/api.py` (Modify)

*   **Proposed Changes**: `get_overview` drops its `channel` parameter. In step 5, delete `/api/funnel` and `/api/channels`.
*   **Why**: The filter and the screens are gone.

#### 6. `meridian/assistant.py` (Modify)

*   **Proposed Changes**: In the page table, `deals`, `channels` and `channel_daily` point to `("Overview", "overview")`.
*   **Why**: Change 6.

#### 7. `meridian/metrics.py` (Modify)

*   **Proposed Changes**: Rename the group labels: organic to "Website & organic", paid to "Paid ads", events to "Events", outbound to "Outbound". No calculation changes.
*   **Why**: Change 7. These labels show in the Leads channel filter.

#### 8. `meridian/db.py` (Modify, comment only)

*   **Proposed Changes**: The `channels.grp` comment lists all four groups: `organic | paid | events | outbound`.
*   **Why**: The old comment lists three and misled the brainstorm.

#### 9. `static/js/screens/overview.js` (Modify)

*   **Proposed Changes**: Rewrite `render` to the Change 3 layout:
    *   **Headline cards:** links as listed in Change 3; the three deal cards have no link.
    *   **Channel table:** five rows with flags.
        *   `best`: a green dot and "Best".
        *   `weakest`: a red dot and "Weakest".
        *   `spent_none`: red text, "spent, none qualified".
        *   `no_spend`: "no spend recorded" in the cost cell.
        *   Row links as listed in Change 3.
    *   **"On track" card:**
        *   The month's bars, labelled "<Month> so far". The status shows only when the server sends one.
        *   The block shows on sample data too (today the team panel is hidden on sample data).
        *   With no targets: "No monthly targets yet · Set them in Settings".
        *   Below them, the existing team lines, labelled "This week".
    *   **"Needs attention" card:** up to three alerts, then "All alerts".
    *   **Height budget:** up to six people in the team lines, then "See all on Targets".
    *   **Delete:** `chart()`, `legend()` and the `only` and `openChannel` actions.
*   **Why**: Change 3.

#### 10. `static/js/screens/paid.js`, `static/js/screens/outbound.js`, `static/js/screens/web.js` (Modify)

*   **Proposed Changes**:
    *   **All three:** a "Sources inside" card at the bottom. It is a table with source, leads, qualified, deals started and value of new deals, laid out the way `channels.js` lays it out today.
    *   **`paid.js`:** the headline lead figure becomes "Leads reported by Meta / LinkedIn", and "Per lead" becomes "Per lead reported by Meta / LinkedIn".
    *   **`web.js`:** the headline "Website leads" becomes "Website form leads". Nothing else changes.
*   **Why**: Change 5 and the Glossary.

#### 10a. `static/js/screens/settings.js` and the Settings data in `meridian/screens.py` (Modify)

*   **Proposed Changes**: "Unmapped" becomes "No channel". The monthly targets table's "Pipeline" row becomes "Value of new deals".
*   **Why**: Change 7 (Glossary).

#### 11. `meridian/narrative.py` (Modify)

*   **Proposed Changes**: In step 5, delete `overview_summary`, which nothing calls.
*   **Why**: Dead code.

#### 12. `static/js/screens/funnel.js`, `static/js/screens/channels.js` (Delete)

*   **Proposed Changes**: Delete both files in step 5, after a text search shows no remaining reference.
*   **Why**: The screens are removed.

#### 13. `static/css/styles.css` (Modify)

*   **Proposed Changes**: In step 5, delete the `.funnel-row`, `.funnel-slice` and `.funnel-part` rules if nothing else uses them.
*   **Why**: Dead styles.

#### 14. `README.md` (Modify)

*   **Proposed Changes**:
    *   The opening list and the "Layout" section name the 12 sidebar items and the Leads switcher.
    *   `metrics.py`'s line says "per-channel counts" instead of "funnel counts".
*   **Why**: The README is the map of the code.

#### 15. `docs/simplify-brief.md` (Modify)

*   **Proposed Changes**: Add one line at the top: "Replaced by `docs/designs/simplify-screens.md`."
*   **Why**: So no one builds from the old brief.

### Verification Plan

*   **Syntax:**
    *   `python -m py_compile meridian/*.py` passes.
    *   `node --input-type=module --check < <file>` passes for every changed `.js` file.
*   **Before-and-after figures** (sample data, `MERIDIAN_SAMPLE=1`):
    *   Save before step 1, and compare after steps 2, 4 and 5.
    *   **After step 2:** the five headline figures are unchanged. Each new channel row equals the old results-by-group row with the same group. The sum of the five rows equals the headline Leads.
    *   **After step 4:** new entries (the "Sources inside" data) are expected. No value that existed before may change.
    *   **After step 5:** nothing differs from after step 4.
*   **Manual checks** (local run on sample data, browser at 1366x768, 100% zoom):
    *   CUJ 1 to 6 from this document, once each.
    *   The sidebar shows 12 items for a leader and 10 for a team member.
    *   `#/funnel` and `#/channels` open Overview for a leader and Targets for a team member.
    *   `#/quality` and `#/icp` open with the switcher, and the sidebar highlights Leads.
    *   On the Quality screen, changing a score weight updates the preview count.
    *   Light and dark theme are both readable.
*   **After deploy:** on meridian.sendwise.co.in, repeat the sidebar checks. Compare Overview's headline numbers with the same date range before the deploy.
*   **Owner check (G1):** the owner answers the three questions from Overview, out loud and timed once, on their laptop.
*   **Design polish:** once step 2 and step 3 work, run `/dembrandt` for layout rules and `/impeccable` on the local copy. Before the pull request, run `/ponytail-review`.

--------------------------------------------------------------------------------

*Drafted with EGM*


## Build decisions from the review (2026-10-29)

The stage 9 review settled the open build questions. Where this section and the file list above differ, this section wins. Full table: `D:\ICP\consolidated_review_report.md`.


| # | Level | Finding | Decision |
|---|---|---|---|
| 1 | Blocker | The Website "Sources inside" card was wired to `screens.web()`, which no screen uses. The Website page is built by `website.build`. | `website.build` (in `meridian/website.py`) returns `inside` for the `organic` group. `web.js` shows the card on its main tab. |
| 2 | Major | Paid ads has no headline lead figure. The Meta tab returns early with its own view. | The "Sources inside" card is added after both the Meta and the LinkedIn views. On the LinkedIn tab, the "Leads" column is relabelled "LinkedIn leads". Nothing else on Paid ads changes. |
| 3 | Major | The spend bar was defined two ways. | All spend in the `paid` channel group, compared with `budget_meta` + `budget_li`. There is no shared list, and the Settings screen is not touched. |
| 4 | Major | The Overview data format was not written down, and `spend` named two things. | The headline keys stay (`leads`, `deals`, `won`, `kpis.qualified`, `kpis.pipeline`). `kpis.spend` and `kpis.cpql` are removed. Each row has `key, name, leads, qualified, deals, won, pipeline, spend, qualified_pct, cpql, prev{…}, rank, spend_flag, note`. |
| 5 | Major | A search-and-replace of old names would also rename things that are not channels. "Channel not known" lives in `icp.py`. | No search-and-replace. Exact list only: the `metrics.GROUPS` labels; the Overview row names; "Unmapped" in `main.js` and `settings.js` (three spots); "Channel not known" in `icp.py`; "Pipeline" in `target_rows` and the Settings targets table; "Website leads" in `web.js`. |
| 6 | Major | The switcher cannot be plain links in the existing segmented control. Quality's and Ideal customer's inner tabs share the heading row. | The switcher is the existing segmented control with one global click action, `openScreen`, in `main.js`. It sits on its own row above the page heading. Headings, the small text above them and the inner tabs stay exactly as they are. |
| 7 | Major | It was unclear whether the "Sources inside" card on Leads shows for every channel group or only Events. | For any channel group (the code is simpler). Overview's Events row links there. |
| 8 | Major | Counting only weekly targets also affects the progress bar and today's counts. | Every figure in a person's Overview line uses weekly targets only, so they agree. |
| 9 | Major | Nothing tests the ranking rules. | The ranking is one small function. It is checked by hand with fixed inputs: ties, the 20-lead minimum, fewer than two rows, the 5-point gap, `spent_none`, the No channel row, and no labels before the 7th. |
| 10–17 | Nits | When the sidebar highlighting happens. Commands that fail in PowerShell. Two different pass rules for step 4. Team-member checks that cannot run. The note text. Old deal-card links during step 1. The alert limit. README spots. "Leads" labels on the Website page. | Highlighting happens in step 3. Commands run in bash. The step 4 rule is "no existing value changes". Team-member checks are dropped, because there is one role. The note reuses the Channels screen's wording. Step 1 also removes the deal-card links. `open_alerts(…, 3)`. README: the channel-filter and "Unmapped" lines. The Website page's own "Leads" labels stay, because inside that page they clearly mean form leads. |


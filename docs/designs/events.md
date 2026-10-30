# Events in Meridian

*   **Author:** jignesh2619
*   **Status:** Proposed
*   **Date:** 2026-10-29

## The problem

Chat360's marketing team is going to several events this month. Each event is run from its own Excel tracker. The SFF 2026 tracker, run with Vonage, has four tabs: Task plan, Promotion calendar, Booth & logistics and Target companies.

The tracker works for one event, but it has four gaps:

*   **Every event starts from a blank sheet.** Most steps are the same for every event: the brief, the lead form, the invites, the booth, the follow-up and the results review. Each new event has to rebuild the list by hand, so steps get missed.
*   **No one place shows how the events are going.** To see which event is behind, someone has to open each sheet.
*   **The tracker ends at "tasks done".** It does not show what the event brought in: leads, qualified leads, deals, value of deals, deals won. It also does not show what the event cost, so nobody can say whether it was worth it. These numbers already exist in Meridian (Zoho leads and deals by lead source); they are just not joined to the event.
*   **The posts made for an event are scattered** across LinkedIn, Instagram and other places, with no single view of them.

## The idea

A new **Events** screen in Meridian. Each event has one page with everything about it, from the first decision to the final results. A standard plan (the **playbook**) is copied into every new event, so nobody starts from a blank sheet.

Meridian never shows the names of people who came to an event. It shows counts and money only, as the owner asked.

## What a marketer needs to see for one event

Questions, in the order they come up:

1.  **What is it, and why are we going?** Name, dates, city and venue, partner (for example Vonage), booth or stand, and the goal in one line.
2.  **What does success look like?** Targets for leads, meetings booked, qualified leads and value of new deals, plus the budget.
3.  **Are we ready?** Plan progress by phase, what is overdue, who owns what, and days left until the event.
4.  **What are we putting out?** The promotion plan (posts, ads, invites, emails, landing page, by week) and the posts that went live, with links and pictures.
5.  **What did it cost?** Every cost line (space, booth build, screen, travel, print, swag, ads) and the total against the budget.
6.  **What did we get?** Leads, qualified leads, deals started, value of new deals and deals won from the event's lead sources in Zoho, against the targets.
7.  **Was it worth it?** Cost per lead, cost per qualified lead, value of new deals against cost, and money won against cost.

## The standard playbook

Taken from the SFF tracker and made general. Each step has a phase, a workstream, a day offset from the event's first day (negative means before), a "done when" line, and an optional default owner. A new event copies every step, with due date = first day + offset. Steps that do not apply to an event can be removed from that event. Event-only steps can be added.

**Phase 1 · Decide & plan (about 6 to 4 weeks before)**
*   Write the event brief: goal, audience, targets and budget (−42)
*   Decide go or no-go with the leaders (−40)
*   Book the space, booth or sponsorship package and pay the invoice (−35)
*   Agree the message and value proposition, joint with the partner if there is one (−30)
*   Build the target-account list, with an owner for each account (−30)
*   Register passes and confirm the attendee process with the organiser (−21)

**Phase 2 · Promote & invite (4 to 1 weeks before)**
*   Build the lead form (QR) with consent wording (−21)
*   Agree lead rules: hot, warm and cold, who owns follow-up, and how fast (−21)
*   Launch the event landing page with a meeting-booking form (−21)
*   Set up a meeting calendar so invitees can book a slot (−21)
*   Publish the content calendar and the teaser post (−21)
*   Send personal invites to every target account (−18)
*   Start paid ads to the event audience (−18)
*   Add event banners and email signatures for the team (−18)
*   Order booth graphics and confirm the artwork is accepted (−18)
*   Book furniture, screen, power and Wi-Fi (−18)
*   Make the one-pager, booth videos and demo script (−10)
*   Submit a media or PR announcement, if offered (−10)
*   Send the pass list and access names to the organiser (−7)
*   Send reminders and confirm booked meetings (−3)
*   Brief the booth team: message, demo, lead form and rota (−3)
*   Pack swag and printed material (−2)

**Phase 3 · Event days**
*   Set up and check the booth: graphics, screen, power, Wi-Fi (−1)
*   Run the booked meetings and live demos (0)
*   Capture every visitor through the lead form, no paper (0)
*   Sync leads each evening: tag hot leads and assign an owner (0)
*   Post live updates, photos and short videos each day (0)
*   Hold a 15-minute team debrief at the end of each day (0)

**Phase 4 · Follow up & measure (after)**
*   Clean the lead list and load it into Zoho, within 24 hours (+1)
*   Send thank-you and follow-up emails; personal follow-up for hot leads (+3)
*   Publish the recap post (+4)
*   Run retargeting ads to visitors (+5)
*   Review results against targets and share them (+7)
*   Review pipeline: which deals moved (+28)

## The Events screens

**Events list** (sidebar: a new "Events" item under "Leads & market").
One row per event: name, dates, place, partner, phase (Planning, Promoting, Live, Follow-up, Done), plan progress ("24 of 40 steps done · 3 overdue"), leads, cost and money back. Upcoming events come first. A "Playbook" tab on the same screen holds the standard steps, which can be edited.

**One event's page**, with five tabs:

1.  **Summary**
    *   Header: name, dates, place, partner, days to go.
    *   Cards: targets against actuals for leads, qualified leads, value of new deals and deals won.
    *   Cost and money back: total cost, cost per lead, cost per qualified lead, value of new deals ÷ cost.
    *   Plan progress per phase, and the next five steps due.
2.  **Plan**
    *   The steps grouped by phase. Each step shows owner, due date, status (Not started, In progress, Waiting on others, Done) and "done when".
    *   Overdue steps are marked red. Status changes with one click.
    *   Steps can be added, removed and edited.
3.  **Marketing**
    *   The promotion plan: one row per activity, with channel (LinkedIn post, LinkedIn ads, Meta ads, email, personal invites, landing page, PR, other), what goes out, date, owner and status.
4.  **Creatives**
    *   A grid of the posts that went live. Paste a link (Instagram, LinkedIn, Facebook, X, YouTube or any page).
    *   Meridian reads the page's preview picture and title where the site allows it. Otherwise the card shows the platform and the link.
    *   Each card has the date and a short caption. A filter picks the platform.
5.  **Costs & results**
    *   Cost lines with category, item, amount and paid or not, against the budget.
    *   Results: the event's lead sources (picked from the lead sources Zoho already has, for example "GFF 2026"). For those sources Meridian counts leads, qualified leads, deals started, value of new deals and deals won, from the event's first day to today. It shows them per source and in total, with cost per lead, cost per qualified lead and money back.

## Data

New tables. None of the existing ones change.

*   `events`: id, name, starts, ends, city, venue, partner, booth, goal, budget, target_leads, target_meetings, target_qualified, target_pipeline, lead_sources (a list of source texts), created_at.
*   `event_steps`: id, event_id, phase, workstream, title, owner, due, status, done_when, note, sort.
*   `playbook_steps`: id, phase, workstream, title, offset_days, done_when, owner, sort. Filled with the steps above the first time.
*   `event_promos`: id, event_id, channel, what, day, owner, status.
*   `event_creatives`: id, event_id, url, platform, title, image, posted_on, caption.
*   `event_costs`: id, event_id, category, item, amount, paid.

Results are counted when the page loads, from `leads` and `deals`. Two rules:
*   The source text matches one of the event's lead sources.
*   The lead or deal was created on or after the event's first day minus 30 days. Pre-event bookings count.

## Goals

*   A new event gets the standard plan, with due dates, in one click.
*   One page answers the seven questions above for any event.
*   The Events list shows every event's readiness and results without opening any of them.
*   No personal data about visitors appears anywhere on the Events screens.
*   The page works on the existing Meridian stack: FastAPI, SQLite, plain JavaScript screens. No new libraries.

## Non-goals

*   No import of the SFF Excel file. The SFF event is entered by hand once, with its steps from the playbook.
*   No writing to Zoho.
*   No target-company scoring list in the first version. The SFF tab with tiered companies is kept in Excel for now.
*   No automatic reading of post likes or comments. That can come later from Apify, which Competitors already uses.
*   No reminder emails for overdue steps in the first version.

## Risks

*   **Social sites often block preview pictures,** Instagram and LinkedIn especially. The card then shows the platform and the link, and a picture link can be pasted by hand.
*   **Leads only count if Zoho's lead source names the event.** The Costs & results tab shows a warning when an event has no lead sources picked.
*   **Matching by lead source can miss leads, or count the same source twice across events.** A source picked for two events is flagged.

## Decisions after review (2026-10-29)

One reviewer (zoom-out) read this design against the code. What changed:

*   **Counting leads:** the lead source names the event, so every lead and deal with that source counts. There is no date window. A source can belong to one event only; picking it twice is blocked, not just flagged.
*   **Events channel:** the Cost & results tab warns when a picked source is not in the Events channel, because Overview's Events row would then not count it.
*   **Added for the marketer:** a decision (Considering, Go, No-go), a "Go again? Lessons" note, and two numbers typed in after the event: meetings held and people captured at the booth.
*   **Sidebar:** Events sits under Channels. Overview's Events row opens it.
*   **Owners:** typed, with the team's names offered as suggestions.
*   **Stage on the list:** worked out from today's date and the event dates. Planning is more than 4 weeks before; Promoting is the 4 weeks before; then Live, Follow-up (30 days after) and Done. Money is in rupees.
*   **Privacy:** the Events screens never link to lead lists.
*   **Kept, against the reviewer, because the owner asked for them:** separate Marketing and Creatives tabs, and an editable standard plan.
*   **Left for later:** adding event costs into Overview's Events spend, post likes and comments from Apify, and reminder emails for overdue steps.

## What can change from event to event (2026-10-30)

Every event is different, so these are now set per event instead of fixed in code:

*   **Tabs:** each event can hide tabs it does not need and rename the rest (Customise tabs). A webinar starts without the Booth & logistics tab. The Booth and Leads tabs list the tasks of the workstreams the event picks for them.
*   **Workstreams:** typed freely, offered back as suggestions; new ones can be added in Customise tabs.
*   **Goals:** besides the standard lead, qualified, meeting and pipeline targets, an event can have its own goals (talk attendees, demos, registrations) with a target and the number reached, typed in.
*   **Key details:** a list of label and value per event (organiser contact, hall and stand, platform, shared folder). A new event starts with labels for its type; links and emails open.
*   **Event types:** the team can rename types and add their own on the Playbook tab; a type can be deleted once no event uses it. The playbook can be viewed per type.
*   **Promotion channels and cost categories:** typed freely, with the standard list and earlier entries as suggestions.
*   **Start a new event from a past one:** tasks, promotion plan, budget lines (as budgeted amounts), goals, key details, target accounts and tab setup are copied. Dates move by the gap between the events; statuses, spend and results start again.

The task list on the Plan tab: search, show (all, open, overdue, due in 7 days, done, skipped), group by phase, workstream, owner, week due or status, and filter by owner and workstream. Due date, owner and status change in place. Ticked tasks can get a status, owner, phase or workstream at once, have their dates moved by a number of days, or be deleted. A new status, **Skipped**, keeps a task that does not apply to this event on record but leaves it out of every count.

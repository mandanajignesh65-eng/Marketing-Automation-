# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Chat360's marketing team** (a handful of people, India and Singapore) runs digital channels and several B2B events a month: booths, sponsor slots, partner joint events (for example SFF 2026 with Vonage). They use Meridian daily to see what each channel brings, log their targets and, for events, to plan, promote and follow up.
- **Their manager** checks progress, asks "are we ready, and was it worth it?", and decides which events to attend again.

## Product Purpose

Meridian is Chat360's internal marketing dashboard. It joins Zoho CRM leads and deals with ad, outreach, website and social data so the team sees which channel works, whether they are on track, and what needs attention. The Event Hub extends this to events: one place where an event goes from the decision to attend to a proven return: readiness, posts, target accounts reached, leads and deals from Zoho, cost and ROI.

Success: the manager can tell, without opening a spreadsheet, how ready each event is and what each event returned for its cost.

## Positioning

Unlike a spreadsheet tracker, Meridian reads Zoho, ad and social data by itself and works out risk, return and comparisons across events. Typed-in status alone is never the point.

## Operating Context

- Laptops at 1366x768 are the common screen; light and dark themes are both used.
- Today each event runs from an Excel tracker on SharePoint (task plan by phase, promotion calendar by week, booth and logistics checklist, scored target-company list with tiers).
- Event leads are always tagged in Zoho with the event's name as Lead Source (confirmed by the owner, 2026-10-29).
- Everyone who signs in is a leader and can do everything (one role since 2026-10-28).

## Capabilities and Constraints

- Stack: FastAPI + SQLite server, plain JavaScript screens with no build step, CSS tokens in `static/css/styles.css`. Hosted on a GCP VM; the `gcp` branch is live, `main` must not receive deploy changes.
- Zoho is read-only: Meridian never writes to Zoho.
- Apify already reads public Instagram, Facebook and X posts (Competitors); Chat360's own LinkedIn and YouTube are read as an "own" account.
- "Qualified" means Meridian's score rule only; one name per figure across screens.

## Evidence on Hand

- The SFF 2026 tracker (SharePoint Excel) as the model of what a team plans for an event.
- Live Zoho data with event lead sources such as "GFF 2026".
- No testimonials, benchmarks or invented figures may be shown.

## Product Principles

1. Show what a sheet cannot: data Meridian knows or works out, not retyped status.
2. Visual first: a number, a shape or the real artefact before a sentence.
3. One name per figure, one main place per figure.
4. Never show visitor or lead names on event screens; counts, companies and money only.
5. Honest numbers: say how many records a figure rests on, and say "too early" rather than guess.

import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, segmented, info, switcher } from '../ui.js';

// Events: the list of events (and the standard plan every event starts from), and one page per event.
// The page answers, in order: what is it, are we ready, what are we putting out, what did it cost, what came back.

const LIST_TABS = [['events', 'Events'], ['playbook', 'Standard plan']];
const TABS = [['summary', 'Summary'], ['plan', 'Plan'], ['marketing', 'Marketing'], ['creatives', 'Creatives'], ['results', 'Cost & results']];
const STATUS_TONE = { 'Not started': 'ink3', 'In progress': 'warn', 'Waiting on others': 'neg', Done: 'pos' };
const PHASE_TONE = { Planning: 'ink3', Promoting: 'accent', Live: 'pos', 'Follow-up': 'warn', Done: 'ink3' };
const PLATFORM_COLOR = { Instagram: '#d6249f', LinkedIn: '#0a66c2', Facebook: '#1877f2', X: '#111', YouTube: '#ff0000', Web: 'var(--ink3)' };
const TIPS = {
  money: 'Value of new deals and money won, each divided by the total cost. 3× means three rupees came back for every rupee spent.',
  sources: 'Pick the lead sources in Zoho that name this event, for example "GFF 2026". Every lead and deal with that source counts for this event. A source can belong to one event only.',
  playbook: 'Every new event gets a copy of these steps. The due date is the event\'s first day plus the number of days shown (minus means before). Changes here only affect events made afterwards.',
  creatives: 'Paste the link to a post. Meridian reads the post\'s picture and title where the site allows it; Instagram and LinkedIn often do not, and then the card shows the link.',
};

const day = iso => (iso ? new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '—');
const span = e => (e.ends && e.ends !== e.starts ? `${day(e.starts)} – ${day(e.ends)}` : day(e.starts));
const pill = (text, tone) => html`<span class="pill sm" style="color:var(--${tone})"><span class="dot" style="background:var(--${tone})"></span>${text}</span>`;
const bar = (done, total, tone = 'pos') => html`<div class="track" style="height:6px;border-radius:3px"><div class="fill" style="width:${total ? done / total * 100 : 0}%;background:var(--${tone})"></div></div>`;
const times = x => (x == null ? '—' : x.toFixed(1) + '×');
const money = v => (v == null ? '—' : f.moneyShort(v));
const toGo = n => (n > 1 ? `${n} days to go` : n === 1 ? 'Tomorrow' : n === 0 ? 'Starts today' : `${-n} days ago`);

// ------------------------------------------------------------------------------- the list

function listView(d, ctx) {
  const view = ctx.ui().list === 'playbook' ? 'playbook' : 'events';
  const head = pageHead(`${d.events.length} event${d.events.length === 1 ? '' : 's'}`, 'Events', html`<div class="row" style="gap:10px">
    ${segmented(LIST_TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'listTab', 16)}
    ${view === 'events' ? html`<span class="btn primary" data-act="newEvent">New event</span>` : html`<span class="btn primary" data-act="newPlaybookStep">Add step</span>`}</div>`);
  if (view === 'playbook') return html`${head}${playbook(d)}`;
  const cols = 'minmax(0,2fr) 120px 110px minmax(150px,1fr) 70px 90px 90px';
  return html`${head}
    ${d.events.length ? html`<div class="card clipped" style="--cols:${cols}">
      <div class="thead right"><span style="text-align:left">Event</span><span style="text-align:left">When</span><span style="text-align:left">Stage</span><span style="text-align:left">Plan</span><span>Leads</span><span>Cost</span><span>Value back</span></div>
      ${d.events.map(e => html`<a class="trow right" href="#/events?id=${e.id}" style="color:inherit;text-decoration:none">
        <span class="stack" style="gap:2px;text-align:left;min-width:0"><span class="medium clip">${e.name}</span><span class="tiny muted clip">${[e.city, e.partner && 'with ' + e.partner].filter(Boolean).join(' · ') || '—'}</span></span>
        <span class="stack" style="gap:2px;text-align:left"><span class="small">${span(e)}</span><span class="tiny muted">${e.phase === 'Done' ? '' : toGo(e.days_to_go)}</span></span>
        <span style="text-align:left">${pill(e.phase, PHASE_TONE[e.phase])}</span>
        <span class="stack" style="gap:4px;text-align:left"><span class="tiny muted">${e.progress.done} of ${e.progress.total} steps${e.progress.overdue ? html` · <span style="color:var(--neg)">${e.progress.overdue} overdue</span>` : ''}</span>${bar(e.progress.done, e.progress.total)}</span>
        <span class="medium">${e.has_sources ? f.num(e.total.leads) : html`<span class="faint" title="No lead sources picked yet">—</span>`}</span>
        <span>${e.cost ? f.moneyShort(e.cost) : '—'}</span><span>${times(e.money.pipeline_x)}</span></a>`)}
    </div>` : html`<div class="card pad stack" style="gap:8px"><span class="title">No events yet</span>
      <span class="small muted">Click “New event”. It gets the standard plan, with due dates counted from its first day.</span></div>`}`;
}

function playbook(d) {
  return html`<div class="small muted row" style="gap:6px">The plan every new event starts with${info(TIPS.playbook)}</div>
    ${d.phases.map(([key, label]) => { const steps = d.playbook.filter(s => s.phase === key); return html`<div class="card" style="padding:14px 20px 6px">
      <div class="title" style="margin-bottom:6px">${label}</div>
      ${steps.map(s => html`<div class="row" style="gap:14px;padding:9px 0;border-top:1px solid var(--line2)">
        <span class="tiny muted right" style="width:64px;flex:none">${s.offset_days === 0 ? 'Day 1' : s.offset_days < 0 ? `${-s.offset_days} days before` : `${s.offset_days} days after`}</span>
        <span class="stack" style="flex:1;min-width:0;gap:1px"><span class="medium editable" data-act="editPlaybookStep" data-arg="${s.id}" title="Click to change">${s.title}</span>
          <span class="tiny muted">${[s.workstream, s.done_when && 'Done when: ' + s.done_when, s.owner].filter(Boolean).join(' · ')}</span></span></div>`)}
      ${steps.length ? '' : html`<div class="small muted" style="padding:8px 0 12px">No steps.</div>`}</div>`; })}`;
}

// ------------------------------------------------------------------------------- one event

function summary(d) {
  const e = d.event, t = d.results.total, m = d.money;
  const target = (label, actual, goal, fmt = f.num) => html`<div class="card kpi" style="padding:16px 18px">
    <span class="kpi-v md">${fmt(actual)}</span><span class="eyebrow">${label}</span>
    ${goal ? html`<div class="stack" style="gap:4px;margin-top:6px"><span class="tiny muted">Target ${fmt(goal)} · ${Math.round(actual / goal * 100)}%</span>${bar(Math.min(actual, goal), goal, actual >= goal ? 'pos' : 'warn')}</div>` : html`<span class="kpi-d faint">No target set</span>`}</div>`;
  const next = d.steps.filter(s => s.status !== 'Done').sort((a, b) => (a.due || '9').localeCompare(b.due || '9')).slice(0, 6);
  return html`
    <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">
      ${target('Leads', t.leads, e.target_leads)}
      ${target('Qualified leads', t.qualified, e.target_qualified)}
      ${target('Meetings held', e.meetings_held || 0, e.target_meetings)}
      ${target('Value of new deals', t.pipeline, e.target_pipeline, f.moneyShort)}
      <div class="card kpi" style="padding:16px 18px"><span class="kpi-v md">${f.num(t.won)}</span><span class="eyebrow">Deals won</span><span class="kpi-d faint">${t.won_value ? f.moneyShort(t.won_value) + ' won' : 'Nothing won yet'}</span></div>
    </div>
    <div class="grid start" style="grid-template-columns:minmax(0,1fr) 360px">
      <div class="card pad stack" style="gap:12px">
        <div class="baseline"><span class="title">Are we ready?</span><span class="small muted">${d.progress.done} of ${d.progress.total} steps done${d.progress.overdue ? html` · <span style="color:var(--neg)">${d.progress.overdue} overdue</span>` : ''}</span></div>
        ${d.by_phase.map(p => html`<div style="display:grid;grid-template-columns:150px minmax(0,1fr) 90px;gap:12px;align-items:center">
          <span class="small medium">${p.label}</span>${bar(p.done, p.total)}<span class="tiny muted right">${p.done}/${p.total}${p.overdue ? html` · <span style="color:var(--neg)">${p.overdue} late</span>` : ''}</span></div>`)}
        <div class="small faint" style="padding-top:10px;border-top:1px solid var(--line2)">Next up</div>
        ${next.length ? next.map(s => html`<div class="row" style="gap:12px"><span class="tiny ${s.due && s.due < d.today ? '' : 'muted'} nowrap" style="width:54px;${s.due && s.due < d.today ? 'color:var(--neg)' : ''}">${day(s.due)}</span>
          <span class="small clip" style="flex:1" title="${s.title}">${s.title}</span><span class="tiny muted nowrap">${s.owner || 'No owner'}</span></div>`) : html`<span class="small muted">Every step is done.</span>`}
      </div>
      <div class="card pad stack" style="gap:10px">
        <div class="row" style="gap:7px"><span class="title">Cost and money back</span>${info(TIPS.money, { end: true })}</div>
        ${[['Total cost', d.cost ? f.money(d.cost) : '—'], ['Budget', e.budget ? f.money(e.budget) : '—'], ['Cost per lead', money(m.per_lead)], ['Cost per qualified lead', money(m.per_qualified)],
          ['Value of new deals for each ₹1', times(m.pipeline_x)], ['Money won for each ₹1', times(m.won_x)], ['People captured at the booth', e.visitors == null ? '—' : f.num(e.visitors)]]
          .map(([k, v]) => html`<div class="between small"><span class="muted">${k}</span><span class="medium">${v}</span></div>`)}
        ${e.budget && d.cost > e.budget ? html`<div class="small" style="color:var(--neg)">Over budget by ${f.money(d.cost - e.budget)}</div>` : ''}
        ${e.goal ? html`<div class="small" style="padding-top:10px;border-top:1px solid var(--line2)"><span class="muted">Goal:</span> ${e.goal}</div>` : ''}
        ${e.lessons ? html`<div class="small"><span class="muted">Go again? Lessons:</span> ${e.lessons}</div>` : ''}
      </div>
    </div>`;
}

function plan(d, ctx) {
  const ui = ctx.ui(), only = ui.stepFilter || '';
  const late = s => s.status !== 'Done' && s.due && s.due < d.today;
  const shown = s => (only === 'open' ? s.status !== 'Done' : only === 'late' ? late(s) : true);
  const statusSelect = s => html`<select class="input" data-change="stepStatus" data-id="${s.id}" style="font-size:12px;padding:4px 8px;width:150px;color:var(--${STATUS_TONE[s.status]})">
    ${d.statuses.map(x => html`<option ${x === s.status ? 'selected' : ''}>${x}</option>`)}</select>`;
  return html`
    <div class="row" style="gap:12px;flex-wrap:wrap">${switcher([{ arg: '', label: 'All steps', on: !only }, { arg: 'open', label: 'Not done', on: only === 'open' }, { arg: 'late', label: `Overdue · ${d.progress.overdue}`, on: only === 'late' }], 'stepFilter')}
      <span style="flex:1"></span><span class="btn primary" data-act="newStep">Add step</span></div>
    ${d.phases.map(([key, label]) => { const steps = d.steps.filter(s => s.phase === key && shown(s)); const all = d.by_phase.find(p => p.key === key); return steps.length ? html`<div class="card" style="padding:14px 20px 6px">
      <div class="baseline" style="margin-bottom:6px"><span class="title">${label}</span><span class="small muted">${all.done} of ${all.total} done</span></div>
      ${steps.map(s => html`<div style="display:grid;grid-template-columns:62px minmax(0,1fr) 140px 160px;gap:14px;align-items:center;padding:10px 0;border-top:1px solid var(--line2)">
        <span class="small nowrap" style="color:var(--${late(s) ? 'neg' : 'ink3'})">${day(s.due)}</span>
        <span class="stack" style="gap:1px;min-width:0"><span class="medium editable ${s.status === 'Done' ? 'muted' : ''}" data-act="editStep" data-arg="${s.id}" title="Click to change">${s.title}</span>
          <span class="tiny muted clip">${[s.workstream, s.done_when && 'Done when: ' + s.done_when, s.note].filter(Boolean).join(' · ')}</span></span>
        <span class="small ${s.owner ? '' : 'faint'} clip">${s.owner || 'No owner'}</span>${statusSelect(s)}</div>`)}
    </div>` : ''; })}`;
}

function marketing(d) {
  const cols = '90px 150px minmax(0,1fr) 140px 160px';
  return html`
    <div class="row"><span class="muted small">Everything that goes out for this event: posts, ads, invites, emails, the landing page</span><span style="flex:1"></span><span class="btn primary" data-act="newPromo">Add activity</span></div>
    <div class="card clipped" style="--cols:${cols}">
      <div class="thead"><span>Date</span><span>Channel</span><span>What goes out</span><span>Owner</span><span>Status</span></div>
      ${d.promos.map(p => html`<div class="trow"><span class="small">${day(p.day)}</span><span class="small medium">${p.channel}</span>
        <span class="small editable clip" data-act="editPromo" data-arg="${p.id}" title="${p.what}">${p.what}</span><span class="small clip ${p.owner ? '' : 'faint'}">${p.owner || 'No owner'}</span>
        <select class="input" data-change="promoStatus" data-id="${p.id}" style="font-size:12px;padding:4px 8px;color:var(--${STATUS_TONE[p.status]})">${d.statuses.map(x => html`<option ${x === p.status ? 'selected' : ''}>${x}</option>`)}</select></div>`)}
      ${d.promos.length ? '' : html`<div class="small muted" style="padding:14px 16px">Nothing planned yet. Add the teaser post, the invites, the ads and the recap.</div>`}
    </div>`;
}

function creatives(d, ctx) {
  const pick = ctx.ui().platform || '';
  const platforms = [...new Set(d.creatives.map(c => c.platform))];
  const shown = d.creatives.filter(c => !pick || c.platform === pick);
  return html`
    <div class="row" style="gap:12px;flex-wrap:wrap">${platforms.length > 1 ? switcher([{ arg: '', label: 'All', on: !pick }, ...platforms.map(p => ({ arg: p, label: p, color: PLATFORM_COLOR[p], on: pick === p }))], 'platform') : html`<span class="small muted row" style="gap:6px">Posts made for this event${info(TIPS.creatives)}</span>`}
      <span style="flex:1"></span><span class="btn primary" data-act="newCreative">Add a post</span></div>
    ${shown.length ? html`<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px">${shown.map(c => html`<div class="card clipped stack" style="gap:0">
      <a href="${c.url}" target="_blank" rel="noopener" style="display:block;aspect-ratio:1.91/1;background:${c.image ? `center/cover no-repeat url('${c.image}')` : `color-mix(in oklch, ${PLATFORM_COLOR[c.platform] || 'var(--ink3)'} 14%, var(--surface))`};display:grid;place-items:center;text-decoration:none">
        ${c.image ? '' : html`<span class="semi" style="color:${PLATFORM_COLOR[c.platform] || 'var(--ink3)'};font-size:18px">${c.platform}</span>`}</a>
      <div class="stack" style="gap:4px;padding:12px 14px">
        <div class="between"><span class="tiny semi" style="color:${PLATFORM_COLOR[c.platform] || 'var(--ink3)'}">${c.platform}</span><span class="tiny muted">${c.posted_on ? day(c.posted_on) : ''}</span></div>
        <span class="small medium clip2" title="${c.title || ''}">${c.caption || c.title || c.url}</span>
        <div class="row" style="gap:12px;margin-top:4px"><a class="link tiny" href="${c.url}" target="_blank" rel="noopener" style="text-decoration:none">Open post</a>
          <span class="tiny faint" data-act="editCreative" data-arg="${c.id}" style="cursor:pointer">Edit</span></div></div></div>`)}</div>`
      : html`<div class="card pad small muted">No posts yet. Click “Add a post” and paste its link.</div>`}`;
}

function results(d) {
  const r = d.results, e = d.event, t = r.total;
  const cols = 'minmax(0,1.6fr) 70px 80px 70px 100px 70px';
  const notEvents = r.sources.filter(s => s.leads && s.group !== 'events');
  return html`
    <div class="grid start" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
      <div class="card clipped" style="--cols:minmax(0,1.4fr) 130px 110px 70px">
        <div class="baseline" style="padding:16px 16px 12px"><span class="title">What it cost</span><span class="row" style="gap:10px"><span class="small muted">${f.money(d.cost)}${e.budget ? ` of ${f.money(e.budget)} budget` : ''}</span><span class="btn xs primary" data-act="newCost">Add cost</span></span></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Item</span><span>Kind</span><span class="right">Amount</span><span class="right">Paid</span></div>
        ${d.costs.map(c => html`<div class="trow"><span class="small editable clip" data-act="editCost" data-arg="${c.id}">${c.item}</span><span class="tiny muted clip">${c.category}</span>
          <span class="small medium right">${f.money(c.amount)}</span><span class="tiny right ${c.paid ? '' : 'faint'}">${c.paid ? 'Paid' : 'Not yet'}</span></div>`)}
        ${d.costs.length ? '' : html`<div class="small muted" style="padding:14px 16px">No costs yet: space, booth, screen, travel, print, swag, ads.</div>`}
      </div>
      <div class="card pad stack" style="gap:10px">
        <div class="title">Money back</div>
        ${[['Leads', f.num(t.leads)], ['Qualified leads', f.num(t.qualified)], ['Deals started', f.num(t.deals)], ['Value of new deals', f.money(t.pipeline)],
          ['Deals won', `${f.num(t.won)}${t.won_value ? ' · ' + f.money(t.won_value) : ''}`], ['Cost per lead', money(d.money.per_lead)],
          ['Cost per qualified lead', money(d.money.per_qualified)], ['Value of new deals for each ₹1', times(d.money.pipeline_x)], ['Money won for each ₹1', times(d.money.won_x)]]
          .map(([k, v]) => html`<div class="between small"><span class="muted">${k}</span><span class="medium">${v}</span></div>`)}
      </div>
    </div>
    <div class="card clipped" style="--cols:${cols}">
      <div class="baseline" style="padding:16px 16px 12px"><span class="row" style="gap:7px"><span class="title">Where the leads came from</span>${info(TIPS.sources)}</span><span class="btn xs" data-act="pickSources">Pick lead sources</span></div>
      ${r.sources.length ? html`<div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Lead source in Zoho</span><span>Leads</span><span>Qualified</span><span>Deals</span><span>Value</span><span>Won</span></div>
        ${r.sources.map(s => html`<div class="trow right"><span class="small medium clip" style="text-align:left">${s.source}</span><span>${f.num(s.leads)}</span><span>${f.num(s.qualified)}</span><span>${f.num(s.deals)}</span><span>${money(s.pipeline)}</span><span>${f.num(s.won)}</span></div>`)}`
        : html`<div class="small" style="padding:0 16px 16px;color:var(--warn)">No lead sources picked, so no leads are counted for this event yet. Click “Pick lead sources”.</div>`}
      ${notEvents.length ? html`<div class="small" style="padding:10px 16px 14px;color:var(--warn)">${notEvents.map(s => s.source).join(', ')} ${notEvents.length === 1 ? 'is' : 'are'} not in the Events channel, so Overview's Events row does not count ${notEvents.length === 1 ? 'it' : 'them'}. <a class="link" href="#/settings" style="text-decoration:none">Change the channel in Settings</a></div>` : ''}
    </div>`;
}

function eventView(d, ctx) {
  const e = d.event, view = TABS.some(t => t[0] === ctx.app.params.tab) ? ctx.app.params.tab : 'summary';
  const where = [span(e), e.city && [e.venue, e.city].filter(Boolean).join(', '), e.partner && 'with ' + e.partner, e.booth && 'booth ' + e.booth].filter(Boolean).join(' · ');
  return html`
    <a class="small link" href="#/events" style="text-decoration:none">← All events</a>
    ${pageHead(where, e.name, html`<div class="row" style="gap:10px">${pill(d.phase, PHASE_TONE[d.phase])}<span class="small muted">${d.phase === 'Done' ? '' : toGo(d.days_to_go)}</span>
      <span class="small muted">${e.decision}</span><span class="btn" data-act="editEvent">Edit event</span></div>`)}
    <div class="row">${segmented(TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'tab', 16)}</div>
    ${{ summary, plan, marketing, creatives, results }[view](d, ctx)}`;
}

// ------------------------------------------------------------------------------- forms

const field = (label, name, value, extra = '') => html`<label class="field">${label}<input class="input" name="${name}" value="${value == null ? '' : value}" ${extra}></label>`;
const select = (label, name, options, value) => html`<label class="field">${label}<select class="input" name="${name}">${options.map(o => html`<option ${o === value ? 'selected' : ''}>${o}</option>`)}</select></label>`;
const buttons = (removeAct, id) => html`<div class="between" style="margin-top:4px">${id ? html`<button type="button" class="btn danger" data-act="${removeAct}" data-arg="${id}">Delete</button>` : html`<span></span>`}
  <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div></div>`;
const owners = d => html`<datalist id="owners">${(d.team || []).map(n => html`<option value="${n}">`)}</datalist>`;

export default {
  uses: {},
  load: ctx => (ctx.app.params.id ? ctx.api.get('events/' + ctx.app.params.id) : ctx.api.get('events')),
  render: (d, ctx) => (d.event ? eventView(d, ctx) : listView(d, ctx)),

  modal(m, ctx) {
    const d = ctx.app.data;
    if (m.kind === 'event') {
      const e = m.event || {};
      return html`<form class="modal" data-submit="saveEvent" style="width:640px">
        <span class="section">${m.event ? 'Edit event' : 'New event'}</span>
        ${m.event ? '' : html`<span class="small muted">It gets the standard plan, with due dates counted from the first day.</span>`}
        ${field('Name', 'name', e.name, 'required data-autofocus placeholder="e.g. SFF 2026"')}
        <div class="grid" style="grid-template-columns:1fr 1fr 1fr">${field('First day', 'starts', e.starts, 'type="date" required')}${field('Last day', 'ends', e.ends, 'type="date"')}${select('Decision', 'decision', ['Considering', 'Go', 'No-go'], e.decision || 'Considering')}</div>
        <div class="grid" style="grid-template-columns:1fr 1fr">${field('City', 'city', e.city)}${field('Venue', 'venue', e.venue)}${field('Partner (if any)', 'partner', e.partner, 'placeholder="e.g. Vonage"')}${field('Booth or stand', 'booth', e.booth)}</div>
        ${field('Goal, in one line', 'goal', e.goal, 'placeholder="Why we are going"')}
        <div class="grid" style="grid-template-columns:repeat(3,1fr)">${field('Budget (₹)', 'budget', e.budget, 'type="number" min="0" step="any"')}${field('Target leads', 'target_leads', e.target_leads, 'type="number" min="0"')}${field('Target qualified leads', 'target_qualified', e.target_qualified, 'type="number" min="0"')}
          ${field('Target meetings', 'target_meetings', e.target_meetings, 'type="number" min="0"')}${field('Target value of new deals (₹)', 'target_pipeline', e.target_pipeline, 'type="number" min="0" step="any"')}<span></span>
          ${field('Meetings held', 'meetings_held', e.meetings_held, 'type="number" min="0" placeholder="After the event"')}${field('People captured at the booth', 'visitors', e.visitors, 'type="number" min="0" placeholder="After the event"')}</div>
        ${field('Go again? Lessons', 'lessons', e.lessons, 'placeholder="After the event: would we go again, and what to change"')}
        ${buttons('removeEvent', e.id)}</form>`;
    }
    if (m.kind === 'step') {
      const s = m.step || { phase: 'plan', status: 'Not started' };
      return html`<form class="modal" data-submit="saveStep">${owners(d)}
        <span class="section">${m.step ? 'Change this step' : 'Add a step'}</span>
        ${field('What needs doing', 'title', s.title, 'required data-autofocus')}
        <div class="grid" style="grid-template-columns:1fr 1fr">
          <label class="field">Phase<select class="input" name="phase">${d.phases.map(([k, l]) => html`<option value="${k}" ${k === s.phase ? 'selected' : ''}>${l}</option>`)}</select></label>
          ${field('Due', 'due', s.due, 'type="date"')}${field('Owner', 'owner', s.owner, 'list="owners"')}${select('Status', 'status', d.statuses, s.status)}</div>
        ${field('Workstream', 'workstream', s.workstream, 'placeholder="e.g. Promotion, Booth & logistics"')}${field('Done when', 'done_when', s.done_when)}${field('Note', 'note', s.note)}
        ${buttons('removeStep', s.id)}</form>`;
    }
    if (m.kind === 'playbook') {
      const s = m.step || { phase: 'plan', offset_days: -14 };
      return html`<form class="modal" data-submit="savePlaybookStep">
        <span class="section">${m.step ? 'Change this standard step' : 'Add a standard step'}</span>
        ${field('What needs doing', 'title', s.title, 'required data-autofocus')}
        <div class="grid" style="grid-template-columns:1fr 1fr">
          <label class="field">Phase<select class="input" name="phase">${d.phases.map(([k, l]) => html`<option value="${k}" ${k === s.phase ? 'selected' : ''}>${l}</option>`)}</select></label>
          ${field('Days from the first day (−21 = three weeks before)', 'offset_days', s.offset_days, 'type="number" step="1" required')}${field('Workstream', 'workstream', s.workstream)}${field('Usual owner', 'owner', s.owner)}</div>
        ${field('Done when', 'done_when', s.done_when)}
        ${buttons('removePlaybookStep', s.id)}</form>`;
    }
    if (m.kind === 'promo') {
      const p = m.promo || { channel: 'LinkedIn post', status: 'Not started' };
      return html`<form class="modal" data-submit="savePromo">${owners(d)}
        <span class="section">${m.promo ? 'Change this activity' : 'Add an activity'}</span>
        ${field('What goes out', 'what', p.what, 'required data-autofocus placeholder="e.g. Teaser: Meet us at booth 6H02"')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${select('Channel', 'channel', d.channels, p.channel)}${field('Date', 'day', p.day, 'type="date"')}${field('Owner', 'owner', p.owner, 'list="owners"')}${select('Status', 'status', d.statuses, p.status)}</div>
        ${buttons('removePromo', p.id)}</form>`;
    }
    if (m.kind === 'creative') {
      const c = m.creative || {};
      return html`<form class="modal" data-submit="saveCreative">
        <span class="section">${m.creative ? 'Change this post' : 'Add a post'}</span>
        ${field('Link to the post', 'url', c.url, 'required data-autofocus placeholder="https://www.linkedin.com/posts/…"')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${field('Posted on', 'posted_on', c.posted_on, 'type="date"')}${field('Picture link (optional)', 'image', c.image, 'placeholder="Used when the site hides its picture"')}</div>
        ${field('Short caption', 'caption', c.caption, 'placeholder="e.g. Day 1 at the booth"')}
        ${buttons('removeCreative', c.id)}</form>`;
    }
    if (m.kind === 'cost') {
      const c = m.cost || { category: d.cost_kinds[0] };
      return html`<form class="modal" data-submit="saveCost">
        <span class="section">${m.cost ? 'Change this cost' : 'Add a cost'}</span>
        ${field('What it is for', 'item', c.item, 'required data-autofocus placeholder="e.g. Booth back wall print"')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${select('Kind', 'category', d.cost_kinds, c.category)}${field('Amount (₹)', 'amount', c.amount, 'type="number" min="0" step="any" required')}</div>
        <label class="row small" style="gap:8px"><input type="checkbox" name="paid" ${c.paid ? 'checked' : ''}> Paid</label>
        ${buttons('removeCost', c.id)}</form>`;
    }
    if (m.kind === 'sources') {
      const mine = new Set(d.event.lead_sources), q = (ctx.ui().sourceQ || '').toLowerCase();
      const options = d.source_options.filter(o => mine.has(o.source) || !q || o.source.toLowerCase().includes(q));
      return html`<form class="modal" data-submit="saveSources" style="width:560px">
        <span class="section">Lead sources for ${d.event.name}</span>
        <span class="small muted">Tick the Zoho lead sources that name this event. Sources that belong to another event are greyed out.</span>
        <input class="input" placeholder="Search lead sources" value="${ctx.ui().sourceQ || ''}" data-input="sourceQ" autocomplete="off">
        <div class="stack" style="gap:2px;max-height:320px;overflow:auto">${options.slice(0, 120).map(o => { const other = d.taken[o.source]; return html`<label class="row small" style="gap:8px;padding:4px 2px;${other ? 'opacity:.45' : ''}">
          <input type="checkbox" name="s::${o.source}" ${mine.has(o.source) ? 'checked' : ''} ${other ? 'disabled' : ''}><span style="flex:1" class="clip">${o.source}</span>
          <span class="tiny muted">${other ? 'in ' + other : f.num(o.leads) + ' leads'}</span></label>`; })}</div>
        ${buttons(null, null)}</form>`;
    }
    return '';
  },

  actions: {
    listTab(ctx, d) { ctx.ui().list = d.arg; ctx.render(); },
    tab: (ctx, d) => ctx.setParams({ ...ctx.app.params, tab: d.arg }),
    stepFilter(ctx, d) { ctx.ui().stepFilter = d.arg; ctx.render(); },
    platform(ctx, d) { ctx.ui().platform = d.arg; ctx.render(); },
    newEvent: ctx => ctx.openModal({ kind: 'event' }),
    editEvent: ctx => ctx.openModal({ kind: 'event', event: ctx.app.data.event }),
    newStep: ctx => ctx.openModal({ kind: 'step' }),
    editStep: (ctx, d) => ctx.openModal({ kind: 'step', step: ctx.app.data.steps.find(s => String(s.id) === d.arg) }),
    newPlaybookStep: ctx => ctx.openModal({ kind: 'playbook' }),
    editPlaybookStep: (ctx, d) => ctx.openModal({ kind: 'playbook', step: ctx.app.data.playbook.find(s => String(s.id) === d.arg) }),
    newPromo: ctx => ctx.openModal({ kind: 'promo' }),
    editPromo: (ctx, d) => ctx.openModal({ kind: 'promo', promo: ctx.app.data.promos.find(p => String(p.id) === d.arg) }),
    newCreative: ctx => ctx.openModal({ kind: 'creative' }),
    editCreative: (ctx, d) => ctx.openModal({ kind: 'creative', creative: ctx.app.data.creatives.find(c => String(c.id) === d.arg) }),
    newCost: ctx => ctx.openModal({ kind: 'cost' }),
    editCost: (ctx, d) => ctx.openModal({ kind: 'cost', cost: ctx.app.data.costs.find(c => String(c.id) === d.arg) }),
    pickSources(ctx) { ctx.ui().sourceQ = ''; ctx.openModal({ kind: 'sources' }); },
    async removeEvent(ctx, d) {
      ctx.app.modal = null;
      await ctx.save(() => ctx.api.post('events', { what: 'remove_event', id: Number(d.arg) }), 'Event deleted.');
      ctx.go('events');
    },
    removeStep: (ctx, d) => remove(ctx, 'remove_step', d.arg),
    removePlaybookStep: (ctx, d) => remove(ctx, 'remove_playbook_step', d.arg),
    removePromo: (ctx, d) => remove(ctx, 'remove_promo', d.arg),
    removeCreative: (ctx, d) => remove(ctx, 'remove_creative', d.arg),
    removeCost: (ctx, d) => remove(ctx, 'remove_cost', d.arg),
  },

  changes: {
    stepStatus: (ctx, value, el) => ctx.save(() => ctx.api.post('events', { what: 'status', id: Number(el.dataset.id), data: { status: value } })),
    promoStatus(ctx, value, el) {
      const p = ctx.app.data.promos.find(x => String(x.id) === el.dataset.id);
      return ctx.save(() => ctx.api.post('events', { what: 'promo', id: p.id, event_id: p.event_id, data: { ...p, status: value } }));
    },
  },

  inputs: {
    sourceQ(ctx, value) { ctx.ui().sourceQ = value; ctx.render(); },
  },

  submits: {
    async saveEvent(ctx, v) {
      const old = ctx.app.modal.event;
      ctx.app.modal = null;
      const r = await ctx.save(() => ctx.api.post('events', { what: 'event', id: old ? old.id : null, data: v }), old ? 'Saved.' : 'Event made, with the standard plan.');
      if (r && !old) ctx.go('events', { id: r.event_id });
    },
    saveStep: (ctx, v) => saveItem(ctx, 'step', 'step', v),
    savePlaybookStep: (ctx, v) => saveItem(ctx, 'playbook_step', 'step', v),
    savePromo: (ctx, v) => saveItem(ctx, 'promo', 'promo', v),
    saveCreative: (ctx, v) => saveItem(ctx, 'creative', 'creative', v, 'Post added.'),
    saveCost: (ctx, v) => saveItem(ctx, 'cost', 'cost', { ...v, paid: !!v.paid }),
    saveSources(ctx, v) {
      ctx.app.modal = null;
      const sources = Object.keys(v).filter(k => k.startsWith('s::')).map(k => k.slice(3));
      return ctx.save(() => ctx.api.post('events', { what: 'sources', event_id: ctx.app.data.event.id, data: { sources } }), 'Lead sources saved.');
    },
  },
};

function saveItem(ctx, what, key, v, done = 'Saved.') {
  const item = ctx.app.modal[key];
  ctx.app.modal = null;
  const eventId = ctx.app.data.event ? ctx.app.data.event.id : null;
  return ctx.save(() => ctx.api.post('events', { what, id: item ? item.id : null, event_id: eventId, data: v }), done);
}

function remove(ctx, what, id) {
  ctx.app.modal = null;
  return ctx.save(() => ctx.api.post('events', { what, id: Number(id) }), 'Deleted.');
}

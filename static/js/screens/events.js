import { html, raw } from '../html.js';
import * as f from '../format.js';
import { pageHead, segmented, info, switcher } from '../ui.js';

// Event Hub. The home screen shows every event on one calendar and ranks finished events by return. Each event opens as a
// room: a pinned event pass (who, when, countdown, stage, headline KPIs) beside sections for readiness, promotion,
// content, target accounts, and results and ROI. Figures come from Zoho and are worked out here; typed status is the minority.

const HOME_TABS = [['calendar', 'All events'], ['performance', 'Performance'], ['playbook', 'Playbook']];
const STAGES = [['Planning', 'Planning'], ['Promoting', 'Promotion'], ['Live', 'Event days'], ['Follow-up', 'Follow-up'], ['Done', 'Results']];
const STATUS_TONE = { 'Not started': 'ink3', 'In progress': 'warn', 'Waiting on others': 'neg', Done: 'pos', Skipped: 'ink3' };
const SKIPPED = 'Skipped';
const PLATFORM_COLOR = { Instagram: '#d6249f', LinkedIn: '#0a66c2', Facebook: '#1877f2', X: '#111111', YouTube: '#ff0000', Web: '#6e6e73' };
const TIPS = {
  sourced: 'Leads and opportunities with this event as their Zoho Lead Source.',
  influenced: 'Value of target-account opportunities that were open during the event.',
  sla: 'Time from lead creation in Zoho (or the event end date, if later) to the owner\'s first activity.',
  accounts: 'Accounts are matched to Zoho by company name (legal suffixes ignored) or domain.',
  roi: 'Pipeline ROI = sourced pipeline ÷ event cost. Revenue ROI = closed-won value ÷ event cost.',
  playbook: 'Tasks added to each new event of the matching type. Offsets are relative to the start date (follow-up tasks: the end date). ◆ = critical.',
};

const day = iso => (iso ? new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '—');
const span = e => (e.ends && e.ends !== e.starts ? `${day(e.starts)} – ${day(e.ends)}` : day(e.starts));
const toDays = iso => Math.round(new Date(iso.slice(0, 10) + 'T00:00:00') / 864e5);
const addDays = (iso, n) => new Date((toDays(iso) + n) * 864e5).toISOString().slice(0, 10);
const moneyOr = v => (v == null || !isFinite(v) ? '—' : f.moneyShort(v));
const times = x => (x == null ? '—' : x.toFixed(1) + '×');
const pct = (a, b) => (b ? Math.round(a / b * 100) : 0);

// ------------------------------------------------------------------------------- home: calendar, performance, playbook

function home(d, ctx) {
  const view = HOME_TABS.some(t => t[0] === ctx.ui().home) ? ctx.ui().home : 'calendar';
  const head = pageHead('', 'Events', html`<div class="row" style="gap:10px">
    ${segmented(HOME_TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'home', 16)}
    ${view === 'playbook' ? html`<span class="btn primary" data-act="newPlaybookStep">Add task</span>` : html`<span class="btn primary" data-act="newEvent">New event</span>`}</div>`);
  if (view === 'playbook') return html`${head}${playbook(d, ctx)}`;
  if (view === 'performance') return html`${head}${performance(d)}`;
  return html`${head}${calendar(d)}`;
}

function calendar(d) {
  if (!d.events.length) return html`<div class="ev-sec stack" style="gap:8px;padding:28px"><span class="title">No events yet</span>
    <span class="small muted">Create an event to generate its task plan from the playbook.</span>
    <span><span class="btn primary" data-act="newEvent">New event</span></span></div>`;
  // across every event: what is coming, what is committed, what came back
  const upcoming = d.events.filter(e => e.days_to_go > 0), next = [...upcoming].sort((a, b) => a.days_to_go - b.days_to_go)[0];
  const sum = k => d.events.reduce((t, e) => t + (k(e) || 0), 0);
  const cost = sum(e => e.cost), qualified = sum(e => e.total.qualified), pipeline = sum(e => e.total.pipeline);
  return html`<div class="ev-sec" style="padding:20px 24px"><div class="ev-stats">
      <div class="ev-stat"><b>${next ? next.days_to_go : '—'}<span class="muted" style="font-size:15px"> days</span></b><span>${next ? 'to ' + next.name : 'No upcoming event'}</span></div>
      <div class="ev-stat"><b>${upcoming.length}</b><span>Upcoming events</span></div>
      <div class="ev-stat"><b style="color:var(--${sum(e => e.progress.overdue) ? 'neg' : 'ink'})">${sum(e => e.progress.overdue)}</b><span>Overdue tasks</span></div>
      <div class="ev-stat"><b>${moneyOr(sum(e => e.budget))}</b><span>Budget committed</span></div>
      <div class="ev-stat"><b>${moneyOr(qualified ? cost / qualified : null)}</b><span>Avg. cost per qualified lead</span></div>
      <div class="ev-stat"><b>${moneyOr(pipeline)}</b><span>Sourced pipeline</span></div>
    </div></div>
    <div class="card clipped" style="--cols:minmax(0,1.8fr) 130px 110px 90px minmax(150px,1fr) 80px 80px 100px">
      <div class="thead right"><span style="text-align:left">Event</span><span style="text-align:left">Dates</span><span style="text-align:left">Stage</span><span>Starts in</span>
        <span style="text-align:left">Readiness</span><span>Overdue</span><span>Leads</span><span>Budget</span></div>
      ${d.events.map(e => html`<a class="trow right" href="#/events?id=${e.id}" style="color:inherit;text-decoration:none">
        <span class="stack" style="gap:2px;text-align:left;min-width:0"><span class="medium clip">${e.name}</span><span class="tiny muted clip">${e.kind}${e.city ? ' · ' + e.city : ''}</span></span>
        <span class="small" style="text-align:left">${span(e)} ${e.starts.slice(0, 4)}</span>
        <span class="small" style="text-align:left">${(STAGES.find(x => x[0] === e.phase) || [, e.phase])[1]}</span>
        <span class="small">${e.days_to_go > 0 ? e.days_to_go + ' days' : e.phase === 'Live' ? 'Live' : '—'}</span>
        <span class="row" style="gap:8px"><span class="track" style="flex:1;height:8px;border-radius:4px"><span class="fill" style="display:block;height:100%;border-radius:4px;width:${e.progress.readiness}%;background:var(--${e.progress.overdue ? 'warn' : 'pos'})"></span></span><span class="small medium" style="width:38px">${e.progress.readiness}%</span></span>
        <span class="small" style="color:var(--${e.progress.overdue ? 'neg' : 'ink3'})">${e.progress.overdue}</span>
        <span class="small">${e.has_sources ? f.num(e.total.leads) : '—'}</span>
        <span class="small">${moneyOr(e.budget)}</span></a>`)}
    </div>`;
}

function performance(d) {
  const done = d.events.filter(e => e.result_age >= 0 && e.has_sources);
  if (!done.length) return html`<div class="card pad small muted">No completed events with a Lead Source.</div>`;
  const ranked = [...done].sort((a, b) => (a.money.per_qualified ?? 1e18) - (b.money.per_qualified ?? 1e18));
  const top = Math.max(...ranked.map(e => e.money.pipeline_x || 0), 1);
  const cols = 'minmax(0,1.6fr) 90px 80px 110px 110px minmax(160px,1fr)';
  return html`<div class="card clipped" style="--cols:${cols}">
    <div class="baseline" style="padding:16px 16px 12px"><span class="title">Event performance</span><span class="small muted">Ranked by cost per qualified lead · final after ${d.result_days} days</span></div>
    <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Event</span><span>Leads</span><span>Qualified</span><span>Cost per qualified lead</span><span>Pipeline</span><span style="text-align:left">Pipeline ROI</span></div>
    ${ranked.map(e => html`<a class="trow right" href="#/events?id=${e.id}" style="color:inherit;text-decoration:none">
      <span class="stack" style="gap:2px;text-align:left;min-width:0"><span class="medium clip">${e.name}</span>
        <span class="tiny muted">${span(e)} · ${e.result_age < d.result_days ? html`<span style="color:var(--warn)">Preliminary · day ${e.result_age} of ${d.result_days}</span>` : 'Final'}</span></span>
      <span>${f.num(e.total.leads)}</span><span>${f.num(e.total.qualified)}</span><span class="medium">${moneyOr(e.money.per_qualified)}</span><span>${moneyOr(e.total.pipeline)}</span>
      <span class="row" style="gap:8px"><span class="track" style="flex:1;height:8px;border-radius:4px"><span class="fill" style="display:block;width:${(e.money.pipeline_x || 0) / top * 100}%;background:var(--pos)"></span></span><span class="small medium" style="width:44px">${times(e.money.pipeline_x)}</span></span></a>`)}
  </div>`;
}

// The standard tasks for each event type, and the types themselves. A new event gets the tasks ticked for its type.
function playbook(d, ctx) {
  const kindName = Object.fromEntries(d.kinds), pick = ctx.ui().kind || '';
  const forKind = s => !pick || !s.kinds || s.kinds.split(',').includes(pick);
  return html`<section class="ev-sec" style="padding:18px 22px">
      <div class="ev-h" style="margin-bottom:12px"><h2 style="font-size:17px">Event types</h2><span class="btn xs" data-act="newKind">Add type</span></div>
      <div class="ev-chips">${d.kinds.map(([k, l]) => html`<span class="ev-chip ev-click" data-act="editKind" data-arg="${k}" title="Rename or delete">${l}
        <span class="muted"> · ${d.playbook.filter(s => !s.kinds || s.kinds.split(',').includes(k)).length} tasks · ${d.kind_use[k] || 0} event${d.kind_use[k] === 1 ? '' : 's'}</span></span>`)}</div>
    </section>
    <div class="between" style="flex-wrap:wrap;gap:10px"><span class="small muted row" style="gap:6px">Playbook tasks${info(TIPS.playbook)}</span>
      ${switcher([{ arg: '', label: 'All types', on: !pick }, ...d.kinds.map(([k, l]) => ({ arg: k, label: l, on: pick === k }))], 'pickKind')}</div>
    ${d.phases.map(([key, label]) => { const steps = d.playbook.filter(s => s.phase === key && forKind(s)); return html`<div class="card" style="padding:14px 20px 6px">
      <div class="title" style="margin-bottom:6px">${label} <span class="small muted" style="font-weight:400">${steps.length}</span></div>
      ${steps.map(s => html`<div class="row" style="gap:14px;padding:9px 0;border-top:1px solid var(--line2)">
        <span class="tiny muted right" style="width:72px;flex:none">${key === 'follow' ? `+${s.offset_days} after` : s.offset_days === 0 ? 'Event day' : s.offset_days < 0 ? `${-s.offset_days} d before` : `${s.offset_days} d after`}</span>
        <span style="width:10px;height:10px;flex:none;${s.critical ? 'background:var(--neg);transform:rotate(45deg);border-radius:2px' : 'background:var(--ink3);border-radius:50%'}" title="${s.critical ? 'Critical' : ''}"></span>
        <span class="stack" style="flex:1;min-width:0;gap:1px"><span class="medium editable" data-act="editPlaybookStep" data-arg="${s.id}">${s.title}</span>
          <span class="tiny muted">${[s.workstream, s.owner && 'Owner: ' + s.owner, s.done_when && 'Done when: ' + s.done_when, s.kinds ? s.kinds.split(',').map(k => kindName[k] || k).join(', ') : 'All event types'].filter(Boolean).join(' · ')}</span></span></div>`)}
      ${steps.length ? '' : html`<div class="ev-empty" style="padding-bottom:10px">No tasks in this phase${pick ? ' for this type' : ''}.</div>`}
    </div>`; })}`;
}

// ------------------------------------------------------------------------------- the event workspace
// One event fills the window: a header with who, when and where, then one tab per area of work. Overview shows every
// area at a glance; each other tab is the full tracker for that area.

// The tasks a tab lists: those in the workstreams the event's setup gives that tab (Booth & logistics, Leads & follow-up).
const tabSteps = (d, tab) => d.steps.filter(s => d.setup.tab_ws[tab].includes(s.workstream));
const isLate = (s, today) => s.status !== 'Done' && s.status !== SKIPPED && s.due && s.due < today;
const tabLabel = (d, tab) => d.setup.tabs.find(t => t.id === tab).label;
// the event's tabs, in order, with its own names; hidden tabs are left out
const tabs = d => {
  const late = list => list.filter(s => isLate(s, d.today)).length;
  const booth = tabSteps(d, 'booth').filter(s => s.status !== SKIPPED), leads = tabSteps(d, 'leads');
  const counts = { plan: d.progress.overdue ? html`<em>${d.progress.overdue}</em>` : `${d.progress.done}/${d.progress.total}`,
    promotion: d.promos.length || '', content: d.creatives.length || '',
    booth: booth.length ? (late(booth) ? html`<em>${late(booth)}</em>` : `${booth.filter(s => s.status === 'Done').length}/${booth.length}`) : '',
    accounts: d.accounts.targets.length || '', leads: late(leads) ? html`<em>${late(leads)}</em>` : (d.event.lead_sources.length ? f.num(d.results.total.leads) : ''),
    budget: d.cost ? f.moneyShort(d.cost) : '' };
  return d.setup.tabs.filter(t => t.show).map(t => [t.id, t.label, counts[t.id] ?? '']);
};

function header(d, current) {
  const e = d.event, now = STAGES.findIndex(s => s[0] === d.phase);
  const count = d.phase === 'Live' ? `Day ${toDays(d.today) - toDays(e.starts) + 1} of the event`
    : d.days_to_go > 0 ? `${d.days_to_go} day${d.days_to_go === 1 ? '' : 's'} to go` : `${toDays(d.today) - toDays(e.ends || e.starts)} days since the event`;
  return html`<header class="evw-head">
    <div class="evw-top"><a href="#/events" class="ev-back">← All events</a>
      <span class="row ev-noprint" style="gap:8px"><span class="btn xs" data-act="editEvent">Edit event</span><span class="btn xs" data-act="setup">Settings</span><span class="btn xs" data-act="print">Export report</span></span></div>
    <div class="evw-id">
      <div class="stack" style="gap:6px;min-width:0">
        <span class="ev-kind">${d.kinds.find(k => k[0] === e.kind)?.[1] || 'Event'}</span>
        <h1 class="ev-name">${e.name}</h1>
        <span class="ev-meta">${span(e)} ${new Date(e.starts).getFullYear()} · ${[e.venue, e.city].filter(Boolean).join(', ') || 'Venue not set'}${e.partner ? ' · with ' + e.partner : ''}${e.booth ? ' · booth ' + e.booth : ''}</span>
      </div>
      <div class="evw-when"><b>${count}</b>
        <div class="ev-stage">${STAGES.map(([, label], i) => html`<span class="${i < now ? 'done' : i === now ? 'now' : ''}" title="${label}"></span>`)}</div>
        <span class="tiny muted">${STAGES.map(([, label], i) => (i === now ? label : '')).join('')} · ${e.decision}</span></div>
    </div>
    <nav class="evw-tabs ev-noprint">${tabs(d).map(([id, label, n]) => html`<a href="#/events?id=${e.id}&sec=${id}" class="${id === current ? 'on' : ''}">${label}${n !== '' ? html` <small>${n}</small>` : ''}</a>`)}</nav>
  </header>`;
}

const block = (title, link, body, extra = '') => html`<section class="ev-sec ${extra}"><div class="ev-h"><h2>${title}</h2>${link || ''}</div>${body}</section>`;
// a link to another tab, named as the event names it; nothing when the event hides that tab
const openTab = (d, sec) => (d.setup.tabs.find(t => t.id === sec && t.show)
  ? html`<a class="link small ev-noprint" href="#/events?id=${d.event.id}&sec=${sec}" style="text-decoration:none">${tabLabel(d, sec)} →</a>` : '');

// A row per task, on one line, changed in place: tick to pick it for a group change, task, workstream,
// owner, due date, status. Clicking the task name opens every field, including "Done when" and notes.
const initials = n => n.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('');
const FLAG = raw('<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path d="M3 1.5v13M3 2.5h8.5l-1.8 3 1.8 3H3" fill="currentColor" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>');

function taskRow(d, s, picked) {
  const late = isLate(s, d.today), team = d.team.includes(s.owner) || !s.owner ? d.team : [s.owner, ...d.team];
  const hint = [s.done_when && 'Done when: ' + s.done_when, s.note].filter(Boolean).join('\n');
  return html`<div class="ev-trow ${s.status === 'Done' ? 'done' : ''} ${s.status === SKIPPED ? 'skipped' : ''} ${picked ? 'picked' : ''}">
    <input type="checkbox" class="ev-pick ev-noprint" data-change="pickStep" data-id="${s.id}" ${picked ? 'checked' : ''} aria-label="Select task">
    <span class="ev-task" data-act="editStep" data-arg="${s.id}" title="${hint}">
      ${s.critical ? html`<span class="ev-flag" title="Critical">${FLAG}</span>` : html`<span class="ev-flag"></span>`}<span class="ev-title">${s.title}</span></span>
    <span class="ev-ws">${s.workstream ? html`<span class="ev-tag" title="Workstream">${s.workstream}</span>` : ''}</span>
    <label class="ev-owner-cell">${s.owner ? html`<span class="ev-av" aria-hidden="true">${initials(s.owner)}</span>` : html`<span class="ev-av none" aria-hidden="true"></span>`}
      <select class="ev-plain" data-change="stepField" data-id="${s.id}" data-field="owner" aria-label="Owner"><option value="">Unassigned</option>${team.map(n => html`<option ${n === s.owner ? 'selected' : ''}>${n}</option>`)}</select></label>
    <label class="ev-due ${late ? 'late' : ''}"><span>${s.due ? day(s.due) : 'No date'}${late ? html`<small>${toDays(d.today) - toDays(s.due)} d late</small>` : ''}</span>
      <input type="date" value="${s.due || ''}" data-change="stepField" data-id="${s.id}" data-field="due" aria-label="Due date"></label>
    <select class="ev-status" data-change="stepField" data-id="${s.id}" data-field="status" style="--t:var(--${STATUS_TONE[s.status]})" aria-label="Status">${d.statuses.map(x => html`<option ${x === s.status ? 'selected' : ''}>${x}</option>`)}</select></div>`;
}

function taskRows(d, steps, empty = 'No tasks here.', ctx = null) {
  const picked = new Set(ctx ? ctx.ui().picked || [] : []);
  return steps.length ? steps.map(s => taskRow(d, s, picked.has(s.id))) : html`<div class="ev-empty">${empty}</div>`;
}

// Common charts only: a pie with a legend, horizontal stacked bars, and columns. Easy to read at a glance.
const STATUS_COLORS = [['Done', 'var(--pos)'], ['In progress', 'var(--warn)'], ['Overdue', 'var(--neg)'], ['Not started', 'color-mix(in oklch, var(--ink3) 55%, var(--surface))']];
const statusOf = (s, today) => (s.status === SKIPPED ? null : s.status === 'Done' ? 'Done' : s.due && s.due < today ? 'Overdue' : s.status === 'Not started' ? 'Not started' : 'In progress');

function pie(parts, centre) {
  const total = parts.reduce((t, [, n]) => t + n, 0) || 1;
  let at = 0;
  const stops = parts.filter(([, n]) => n).map(([, n, c]) => { const from = at; at += n / total * 100; return `${c} ${from}% ${at}%`; }).join(', ');
  return html`<div class="ev-pie-wrap"><div class="ev-pie" style="background:conic-gradient(${stops || 'var(--track) 0 100%'})"><span>${centre || ''}</span></div>
    <div class="stack" style="gap:7px">${parts.map(([label, n, c]) => html`<div class="row small" style="gap:8px"><span style="width:10px;height:10px;border-radius:3px;background:${c};flex:none"></span>
      <span style="flex:1">${label}</span><span class="medium">${f.num(n)}</span><span class="muted" style="width:38px;text-align:right">${pct(n, total)}%</span></div>`)}</div></div>`;
}

function stacked(rows, colors) {
  const top = Math.max(...rows.map(r => r.parts.reduce((t, n) => t + n, 0)), 1);
  return html`<div class="stack" style="gap:12px">${rows.map(r => { const sum = r.parts.reduce((t, n) => t + n, 0); return html`<div style="display:grid;grid-template-columns:130px minmax(0,1fr) 46px;gap:12px;align-items:center">
      <span class="small">${r.label}</span>
      <div class="ev-split" style="height:16px;border-radius:5px;background:transparent">${r.parts.map((n, i) => (n ? html`<i style="width:${n / top * 100}%;background:${colors[i][1]}" title="${colors[i][0]}: ${n}"></i>` : ''))}</div>
      <span class="small muted right">${sum}</span></div>`; })}
    <div class="ev-legend">${colors.map(([l, c]) => html`<span style="--c:${c}">${l}</span>`)}</div></div>`;
}

// tasks by status: a pie for the whole plan, and a bar per phase
function taskCharts(d) {
  const count = list => STATUS_COLORS.map(([k]) => list.filter(s => statusOf(s, d.today) === k).length);
  const all = count(d.steps);
  return html`<div class="ev-grid-chart">
    ${pie(STATUS_COLORS.map(([l, c], i) => [l, all[i], c]), html`<b>${d.progress.readiness}%</b><small>ready</small>`)}
    ${stacked(d.phases.map(([k, label]) => ({ label, parts: count(d.steps.filter(s => s.phase === k)) })), STATUS_COLORS)}
  </div>`;
}

// tasks due each week, stacked by status, with the event week marked
function weekColumns(d) {
  const weekOf = iso => addDays(iso, -((new Date(iso + 'T00:00:00').getDay() + 6) % 7));
  const weeks = [...new Set(d.steps.filter(s => s.due && s.status !== SKIPPED).map(s => weekOf(s.due)))].sort();
  if (!weeks.length) return html`<div class="ev-empty">No dated tasks.</div>`;
  const rows = weeks.map(w => ({ w, parts: STATUS_COLORS.map(([k]) => d.steps.filter(s => s.due && weekOf(s.due) === w && statusOf(s, d.today) === k).length) }));
  const top = Math.max(...rows.map(r => r.parts.reduce((t, n) => t + n, 0)), 1);
  const eventWeek = weekOf(d.event.starts), thisWeek = weekOf(d.today);
  return html`<div style="display:flex;gap:8px;align-items:flex-end;height:180px">${rows.map(r => html`<div class="stack" style="flex:1;height:100%;justify-content:flex-end;align-items:center;gap:4px">
      <span class="micro muted">${r.parts.reduce((t, n) => t + n, 0)}</span>
      <div style="width:100%;max-width:44px;height:${r.parts.reduce((t, n) => t + n, 0) / top * 100}%;display:flex;flex-direction:column-reverse;border-radius:5px 5px 1px 1px;overflow:hidden">
        ${r.parts.map((n, i) => (n ? html`<div style="height:${n / r.parts.reduce((t, x) => t + x, 0) * 100}%;background:${STATUS_COLORS[i][1]}" title="${STATUS_COLORS[i][0]}: ${n}"></div>` : ''))}</div></div>`)}</div>
    <div style="display:flex;gap:8px;margin-top:6px">${rows.map(r => html`<span class="micro ${r.w === eventWeek || r.w === thisWeek ? 'medium' : 'faint'}" style="flex:1;text-align:center;${r.w === eventWeek ? 'color:var(--k)' : ''}">${r.w === eventWeek ? 'Event' : r.w === thisWeek ? 'This wk' : day(r.w)}</span>`)}</div>
    <div class="ev-legend" style="margin-top:10px">${STATUS_COLORS.map(([l, c]) => html`<span style="--c:${c}">${l}</span>`)}</div>`;
}

function funnelBars(d) {
  const t = d.results.total, steps = [['Leads', t.leads], ['Qualified leads', t.qualified], ['Opportunities', t.deals], ['Closed won', t.won]], top = Math.max(t.leads, t.deals, 1);
  return html`<div class="ev-funnel">${steps.map(([label, n], i) => html`<div class="ev-fstep"><span class="small muted">${label}</span>
    <div><div class="ev-fbar" style="width:${Math.max(n / top * 100, 6)}%">${f.num(n)}</div></div>
    <span class="small muted">${i && steps[i - 1][1] && n <= steps[i - 1][1] ? pct(n, steps[i - 1][1]) + '%' : ''}</span></div>`)}</div>`;
}

function slaBlock(d) {
  const sp = d.results.speed;
  if (!sp.leads) return html`<div class="ev-empty">No leads yet.</div>`;
  return pie([['Within 24 h', sp.h24, 'var(--pos)'], ['24–72 h', sp.h72 - sp.h24, 'color-mix(in oklch, var(--pos) 50%, var(--surface))'],
    ['3–7 days', sp.d7 - sp.h72, 'var(--warn)'], ['After 7 days', sp.timed - sp.d7, 'var(--neg)'], ['No contact yet', sp.untouched, 'color-mix(in oklch, var(--ink3) 55%, var(--surface))']],
  html`<b>${pct(sp.h24, sp.leads)}%</b><small>in 24 h</small>`);
}

function budgetBars(d) {
  const kinds = {};
  d.costs.forEach(c => { const k = kinds[c.category] = kinds[c.category] || { planned: 0, actual: 0 }; k.planned += c.planned || 0; k.actual += c.amount || 0; });
  const kmax = Math.max(...Object.values(kinds).map(k => Math.max(k.planned, k.actual)), 1);
  if (!Object.keys(kinds).length) return html`<div class="ev-empty">No costs recorded.</div>`;
  const bar = (v, color) => html`<div style="height:9px;border-radius:3px;width:${Math.max(v / kmax * 100, v ? 1 : 0)}%;background:${color}"></div>`;
  return html`<div class="stack" style="gap:12px">${Object.entries(kinds).map(([k, v]) => html`<div style="display:grid;grid-template-columns:minmax(110px,170px) minmax(0,1fr) 110px;gap:12px;align-items:center">
      <span class="small clip" title="${k}">${k}</span>
      <div class="stack" style="gap:3px">${bar(v.planned, 'color-mix(in oklch, var(--ink3) 45%, var(--surface))')}${bar(v.actual, v.planned && v.actual > v.planned ? 'var(--neg)' : 'var(--k)')}</div>
      <span class="small right">${f.moneyShort(v.actual)}<span class="muted">${v.planned ? ' / ' + f.moneyShort(v.planned) : ''}</span></span></div>`)}</div>
    <div class="ev-legend" style="margin-top:12px"><span style="--c:color-mix(in oklch, var(--ink3) 45%, var(--surface))">Budgeted</span><span style="--c:var(--k)">Actual</span><span style="--c:var(--neg)">Over budget</span></div>`;
}

function leadsChart(d) {
  const days = d.results.by_day;
  if (!days.length) return html`<div class="ev-empty">No leads yet.</div>`;
  const top = Math.max(...days.map(x => x.leads), 1);
  return html`<div style="display:flex;gap:4px;align-items:flex-end;height:150px">${days.map(x => html`<div class="stack" title="${day(x.day)}: ${x.leads} leads, ${x.qualified} qualified" style="flex:1;max-width:46px;height:100%;justify-content:flex-end;gap:3px;align-items:center">
      <span class="micro muted">${x.leads}</span>
      <div style="width:100%;height:${x.leads / top * 100}%;min-height:3px;border-radius:4px 4px 1px 1px;background:color-mix(in oklch, var(--k) 35%, var(--surface));display:flex;flex-direction:column-reverse;overflow:hidden">
        <div style="height:${x.leads ? x.qualified / x.leads * 100 : 0}%;background:var(--k)"></div></div></div>`)}</div>
    <div style="display:flex;gap:4px;margin-top:4px">${days.map(x => html`<span class="micro faint" style="flex:1;max-width:46px;text-align:center">${day(x.day)}</span>`)}</div>
    <div class="ev-legend" style="margin-top:8px"><span style="--c:var(--k)">Qualified</span><span style="--c:color-mix(in oklch, var(--k) 35%, var(--surface))">Other leads</span></div>`;
}

// ---- Overview: every area at a glance, each block opens its tab.
function overview(d) {
  const p = d.progress, t = d.results.total, e = d.event, a = d.accounts, has = e.lead_sources.length;
  const soon = addDays(d.today, 7);
  const attention = d.steps.filter(s => s.status !== 'Done' && s.status !== SKIPPED && s.due && (s.due < d.today || (s.critical && s.due <= soon))).slice(0, 6);
  const tile = (value, label, sub, goal, actual) => html`<div class="ev-tile"><b>${value}</b><span>${label}</span>
    ${goal ? html`<div class="ev-split" style="height:6px;margin-top:8px"><i style="width:${Math.min(pct(actual, goal), 100)}%;background:var(--k)"></i></div><span class="tiny muted">${sub}</span>` : html`<span class="tiny muted">${sub || ''}</span>`}</div>`;
  const posts = d.creatives.slice(0, 4);
  const thisWeek = d.promos.filter(x => x.day && x.day >= addDays(d.today, -3) && x.day <= addDays(d.today, 7));
  return html`
    ${e.goal ? html`<p class="ev-goal">${e.goal}</p>` : ''}
    <div class="ev-tiles">
      ${tile(p.readiness + '%', 'Readiness', `${p.due_done} of ${p.due} tasks due are done`, p.due, p.due_done)}
      ${tile(String(p.overdue), 'Overdue tasks', `${p.at_risk} critical at risk this week`)}
      ${tile(has ? f.num(t.leads) : '—', 'Leads', e.target_leads ? `${pct(t.leads, e.target_leads)}% of ${f.num(e.target_leads)} target` : '', e.target_leads, t.leads)}
      ${tile(moneyOr(t.pipeline), 'Sourced pipeline', e.target_pipeline ? `${pct(t.pipeline, e.target_pipeline)}% of ${f.moneyShort(e.target_pipeline)} target` : '', e.target_pipeline, t.pipeline)}
      ${tile(times(d.money.pipeline_x), 'Pipeline ROI', `Cost ${moneyOr(d.cost)} · ${times(d.money.won_x)} revenue ROI`)}
    </div>
    <div class="ev-grid2">
      ${block('Tasks by status', openTab(d, 'plan'), taskCharts(d), 'span2')}
      ${block('Needs attention', '', attention.length ? attention.map(s => html`<div class="ev-row slim" data-act="editStep" data-arg="${s.id}">
          <span class="ev-when" style="color:var(--${s.due < d.today ? 'neg' : 'warn'})">${s.due < d.today ? 'Overdue' : day(s.due)}</span>
          <span class="ev-task">${s.title}</span><span class="ev-owner">${s.owner || 'Unassigned'}</span></div>`) : html`<div class="ev-empty">No overdue or at-risk tasks.</div>`)}
    </div>
    <div class="ev-grid3">
      ${block('Lead funnel', openTab(d, 'results'), has ? funnelBars(d) : html`<div class="ev-empty">Lead Source not set.</div>`)}
      ${block('Target accounts', openTab(d, 'accounts'), a.targets.length ? html`${stageBars(a)}<div class="small muted" style="margin-top:12px">Influenced pipeline ${moneyOr(a.influenced)}</div>`
        : html`<div class="ev-empty">No target accounts yet.</div>`)}
      ${block('Budget vs actual', openTab(d, 'budget'), html`<div class="ev-big" style="margin-bottom:12px">${moneyOr(d.cost)}<span class="small muted" style="font-weight:400"> of ${moneyOr(d.planned)}</span></div>${budgetBars(d)}`)}
    </div>
    <div class="ev-grid3">
      ${block('Content', openTab(d, 'content'), posts.length ? html`<div class="ev-thumbs">${posts.map(c => html`<a href="${c.url}" target="_blank" rel="noopener" class="ev-thumb" style="${c.image ? `background-image:url('${c.image}')` : `background:color-mix(in oklch, ${PLATFORM_COLOR[c.platform] || '#6e6e73'} 16%, var(--surface));color:${PLATFORM_COLOR[c.platform] || '#6e6e73'}`}">${c.image ? '' : c.platform}</a>`)}</div>
        <div class="small muted" style="margin-top:10px">${d.creatives.length} post${d.creatives.length === 1 ? '' : 's'} on ${[...new Set(d.creatives.map(c => c.platform))].join(', ')}</div>` : html`<div class="ev-empty">No posts yet.</div>`)}
      ${block('Promotion this week', openTab(d, 'promotion'), thisWeek.length ? thisWeek.map(x => html`<div class="ev-row slim"><span class="ev-when">${day(x.day)}</span><span class="ev-task">${x.what}<span class="tiny muted" style="display:block">${x.channel}</span></span><span class="ev-owner" style="color:var(--${STATUS_TONE[x.status]})">${x.status}</span></div>`)
        : html`<div class="ev-empty">${d.promos.filter(x => x.status === 'Done').length} of ${d.promos.length} activities live. Nothing scheduled this week.</div>`)}
      ${block('Follow-up SLA', openTab(d, 'leads'), slaBlock(d))}
    </div>
    <div class="ev-grid2">
      ${block('Goals', html`<span class="btn xs ev-noprint" data-act="newGoal">Add goal</span>`, goalBars(d))}
      ${block('Key details', html`<span class="btn xs ev-noprint" data-act="newInfo">Add detail</span>`, keyDetails(d))}
    </div>`;
}

// Every goal of the event as a bar of reached against target: the standard ones from Edit event, then the event's own.
function goalList(d) {
  const e = d.event, t = d.results.total, has = e.lead_sources.length;
  const standard = [['Leads', has ? t.leads : null, e.target_leads], ['Qualified leads', has ? t.qualified : null, e.target_qualified],
    ['Meetings held', e.meetings_held, e.target_meetings], ['Sourced pipeline', has ? t.pipeline : null, e.target_pipeline, true]]
    .filter(g => g[2]).map(([name, actual, target, money]) => ({ name, actual, target, money }));
  return [...standard, ...d.goals.map(g => ({ ...g, own: true }))];
}

function goalBars(d) {
  const goals = goalList(d), fmt = (g, v) => (v == null ? '—' : g.money ? f.moneyShort(v) : f.num(v));
  if (!goals.length) return html`<div class="ev-empty">No goals set.</div>`;
  return html`<div class="stack" style="gap:14px">${goals.map(g => { const p = g.target ? pct(g.actual || 0, g.target) : 0; return html`<div class="stack ${g.own ? 'ev-click' : ''}" style="gap:6px" ${g.own ? html`data-act="editGoal" data-arg="${g.id}"` : ''}>
      <div class="between small"><span class="medium">${g.name}</span><span class="muted">${fmt(g, g.actual)}${g.target ? ' of ' + fmt(g, g.target) : ''}${g.target && g.actual != null ? html` · <b style="color:var(--${p >= 100 ? 'pos' : 'ink'})">${p}%</b>` : ''}</span></div>
      <div class="ev-split" style="height:9px"><i style="width:${Math.min(p, 100)}%;background:var(--${p >= 100 ? 'pos' : 'k'})"></i></div></div>`; })}
    <span class="tiny muted">Leads, qualified leads and pipeline sync from Zoho. Custom goals are updated manually.</span></div>`;
}

// What the team needs to hand on the day, different for every event: organiser contact, stand, platform, folder links.
function keyDetails(d) {
  if (!d.info.length) return html`<div class="ev-empty">No details added.</div>`;
  const shown = v => (/^https?:\/\//i.test(v) ? html`<a class="link" href="${v}" target="_blank" rel="noopener">${v.replace(/^https?:\/\/(www\.)?/i, '').slice(0, 48)}</a>`
    : /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i.test(v) ? html`<a class="link" href="mailto:${v}">${v}</a>` : v);
  return html`<div class="stack">${d.info.map(i => html`<div class="ev-info" data-act="editInfo" data-arg="${i.id}">
    <span class="small muted">${i.label}</span><span class="small ${i.value ? '' : 'faint'}">${i.value ? shown(i.value) : 'Not set'}</span></div>`)}</div>`;
}

// ---- Plan: progress by phase, tasks per week and workload, then the task list: search, show, group by, and change many at once.
const SHOW = [['all', 'All'], ['open', 'Open'], ['late', 'Overdue'], ['week', 'Next 7 days'], ['done', 'Done'], ['skipped', 'Skipped']];
const GROUPS = [['phase', 'Phase'], ['workstream', 'Workstream'], ['owner', 'Owner'], ['week', 'Week due'], ['status', 'Status'], ['none', 'No grouping']];
const weekOf = iso => addDays(iso, -((new Date(iso + 'T00:00:00').getDay() + 6) % 7));

function shownTasks(d, ui) {
  const q = (ui.q || '').toLowerCase(), show = ui.show || 'all', soon = addDays(d.today, 7);
  const keep = {
    all: () => true, open: s => s.status !== 'Done' && s.status !== SKIPPED, late: s => isLate(s, d.today),
    week: s => s.status !== 'Done' && s.status !== SKIPPED && s.due && s.due <= soon, done: s => s.status === 'Done', skipped: s => s.status === SKIPPED,
  }[show] || (() => true);
  return d.steps.filter(s => keep(s) && (!ui.phase || s.phase === ui.phase) && (!ui.ws || s.workstream === ui.ws)
    && (!ui.owner || (s.owner || 'Unassigned') === ui.owner)
    && (!q || [s.title, s.workstream, s.owner, s.note, s.done_when].some(x => (x || '').toLowerCase().includes(q))));
}

// tasks split into groups, in a sensible order for each kind of grouping; each group knows what a task added to it gets
function groupTasks(d, steps, by) {
  const phases = Object.fromEntries(d.phases);
  const key = { phase: s => s.phase, workstream: s => s.workstream || '', owner: s => s.owner || '', week: s => (s.due ? weekOf(s.due) : ''), status: s => s.status }[by];
  if (!key) return [{ title: '', steps }];
  const order = by === 'phase' ? d.phases.map(p => p[0]) : by === 'status' ? d.statuses : [...new Set(steps.map(key))].sort((a, b) => (a === '') - (b === '') || a.localeCompare(b));
  const name = k => (by === 'phase' ? phases[k] : by === 'week' ? (k ? `Week of ${day(k)}${k === weekOf(d.event.starts) ? ' · event week' : k === weekOf(d.today) ? ' · this week' : ''}` : 'No due date')
    : k || (by === 'owner' ? 'Unassigned' : by === 'workstream' ? 'No workstream' : k));
  return order.map(k => ({ title: name(k), steps: steps.filter(s => key(s) === k) })).filter(g => g.steps.length);
}

function plan(d, ctx) {
  const ui = ctx.ui(), phase = ui.phase || '', ws = ui.ws || '', owner = ui.owner || '', by = ui.by || 'phase', show = ui.show || 'all';
  const steps = shownTasks(d, ui), groups = groupTasks(d, steps, by);
  const picked = new Set((ui.picked || []).filter(id => d.steps.some(s => s.id === id)));
  const workstreams = d.setup.workstreams, owners = [...new Set([...d.team, ...d.steps.map(s => s.owner).filter(Boolean)])];
  const maxLoad = Math.max(...d.load.map(r => r.open), 1);
  const filtered = phase || ws || owner || ui.q || show !== 'all';
  const opt = (value, current, text = value) => html`<option value="${value}" ${value === current ? 'selected' : ''}>${text}</option>`;
  return html`
    <div class="ev-phases">${d.by_phase.map(x => html`<button class="ev-phase ${x.key === phase ? 'on' : ''}" data-act="phase" data-arg="${x.key === phase ? '' : x.key}">
      <span class="ev-phase-name">${x.label}</span><span class="ev-split" style="height:6px"><i style="width:${pct(x.done, x.total)}%;background:var(--${x.overdue ? 'neg' : 'k'})"></i></span>
      <span class="tiny muted">${x.done} of ${x.total} done${x.overdue ? html` · <span style="color:var(--neg)">${x.overdue} overdue</span>` : ''}</span></button>`)}</div>
    <div class="ev-grid2">
      ${block('Tasks due per week', '', weekColumns(d), 'span2')}
      ${block('Workload · next 14 days', '', d.load.length ? html`<div class="stack" style="gap:12px">${d.load.map(r => html`<div class="stack" style="gap:4px;cursor:pointer" data-act="owner" data-arg="${r.owner === owner ? '' : r.owner}">
          <div class="between small"><span class="${r.owner === owner ? 'medium' : ''}">${r.owner}</span><span class="muted">${r.open} open${r.overdue ? html` · <span style="color:var(--neg)">${r.overdue} overdue</span>` : ''}</span></div>
          <div class="ev-split" style="height:8px"><i style="width:${r.overdue / maxLoad * 100}%;background:var(--neg)"></i><i style="width:${(r.open - r.overdue) / maxLoad * 100}%;background:${r.open > 6 ? 'var(--warn)' : 'var(--k)'}"></i></div></div>`)}</div>`
        : html`<div class="ev-empty">No open tasks due in the next 14 days.</div>`)}
    </div>
    <section class="ev-sec">
      <div class="ev-h"><h2>Tasks <span class="ev-sub" style="font-weight:400">${steps.length} of ${d.steps.length}</span></h2>
        <span class="row ev-noprint" style="gap:8px"><span class="btn xs primary" data-act="newStep" data-preset="${JSON.stringify({ ...(phase && { phase }), ...(ws && { workstream: ws }), ...(owner && owner !== 'Unassigned' && { owner }) })}">Add task</span></span></div>
      <div class="ev-toolbar ev-noprint">
        <input class="input" id="taskQ" type="search" placeholder="Search tasks" value="${ui.q || ''}" data-input="taskQ" autocomplete="off" style="width:200px">
        ${segmented(SHOW.map(([arg, text]) => ({ arg, label: text, on: show === arg })), 'show', 10)}
        <label class="row small muted" style="gap:6px">Group by<select class="input ev-sel" data-change="groupBy">${GROUPS.map(([k, t]) => opt(k, by, t))}</select></label>
        <select class="input ev-sel" data-change="planOwner" aria-label="Owner"><option value="">All owners</option>${[...owners, 'Unassigned'].map(n => opt(n, owner))}</select>
        <select class="input ev-sel" data-change="planWs" aria-label="Workstream"><option value="">All workstreams</option>${workstreams.map(w => opt(w, ws))}</select>
        ${filtered ? html`<span class="btn xs" data-act="clearFilters">Clear filters</span>` : ''}
      </div>
      ${picked.size ? html`<div class="ev-bulk ev-noprint"><b>${picked.size} selected</b>
        <select class="input ev-sel" data-change="bulkField" data-field="status"><option value="">Set status…</option>${d.statuses.map(x => opt(x, ''))}</select>
        <select class="input ev-sel" data-change="bulkField" data-field="owner"><option value="">Set owner…</option>${owners.map(n => opt(n, ''))}<option value="-">Unassigned</option></select>
        <select class="input ev-sel" data-change="bulkField" data-field="phase"><option value="">Set phase…</option>${d.phases.map(([k, t]) => opt(k, '', t))}</select>
        <select class="input ev-sel" data-change="bulkField" data-field="workstream"><option value="">Set workstream…</option>${workstreams.map(w => opt(w, ''))}</select>
        <span class="row" style="gap:4px"><input class="input" id="bulkShift" type="number" step="1" placeholder="Days (±)" style="width:80px"><span class="btn xs" data-act="bulkShift">Shift dates</span></span>
        ${ui.confirmDelete ? html`<span class="btn xs danger" data-act="bulkDelete">Confirm delete (${picked.size})</span>` : html`<span class="btn xs" data-act="askDelete">Delete</span>`}
        <span class="btn xs" data-act="unpick">Clear</span></div>` : ''}
      ${groups.map(g => { const ids = g.steps.map(s => s.id), all = ids.every(id => picked.has(id)); return html`
        ${g.title ? html`<div class="ev-ghead"><input type="checkbox" class="ev-pick ev-noprint" data-change="pickGroup" data-ids="${ids.join(',')}" ${all ? 'checked' : ''} aria-label="Select all in ${g.title}">
          <span class="medium">${g.title}</span><span class="tiny muted">${g.steps.length} task${g.steps.length === 1 ? '' : 's'}${g.steps.some(s => isLate(s, d.today)) ? html` · <span style="color:var(--neg)">${g.steps.filter(s => isLate(s, d.today)).length} overdue</span>` : ''}</span>
</div>` : ''}
        ${g.steps.map(s => taskRow(d, s, picked.has(s.id)))}`; })}
      ${steps.length ? '' : html`<div class="ev-empty">${d.steps.length ? 'No tasks match these filters.' : 'No tasks yet.'}</div>`}
    </section>`;
}

// ---- Booth & logistics: the booth checklist from the plan, plus the booth's facts.
function booth(d, ctx) {
  const e = d.event, steps = tabSteps(d, 'booth'), counted = steps.filter(s => s.status !== SKIPPED);
  const done = counted.filter(s => s.status === 'Done').length;
  return html`<div class="ev-tiles">
      <div class="ev-tile"><b>${e.booth || '—'}</b><span>Booth / stand</span></div>
      <div class="ev-tile"><b>${[e.venue, e.city].filter(Boolean).join(', ') || '—'}</b><span>Venue</span></div>
      <div class="ev-tile"><b>${done}<span class="muted" style="font-size:16px"> / ${counted.length}</span></b><span>Checklist done</span><div class="ev-split" style="height:6px;margin-top:8px"><i style="width:${pct(done, counted.length)}%;background:var(--k)"></i></div></div>
      <div class="ev-tile"><b>${e.meetings_held == null ? '—' : f.num(e.meetings_held)}<span class="muted" style="font-size:16px">${e.target_meetings ? ' / ' + f.num(e.target_meetings) : ''}</span></b><span>Meetings held</span></div>
    </div>
    ${block(tabLabel(d, 'booth') + ' checklist', html`<span class="btn xs primary ev-noprint" data-act="newStep" data-preset="${JSON.stringify({ workstream: d.setup.tab_ws.booth[0] || '' })}">Add item</span>`,
      taskRows(d, steps, 'No tasks. Set this tab’s workstreams in Settings.', ctx))}`;
}

// ---- Leads & follow-up: leads arriving, how fast they were contacted, and the tasks that make it happen.
function leadsTab(d, ctx) {
  const t = d.results.total, e = d.event, steps = tabSteps(d, 'leads');
  return html`<div class="ev-tiles">
      <div class="ev-tile"><b>${e.lead_sources.length ? f.num(t.leads) : '—'}</b><span>Leads${e.target_leads ? ' · target ' + f.num(e.target_leads) : ''}</span></div>
      <div class="ev-tile"><b>${f.num(t.qualified)}</b><span>Qualified leads${t.leads ? ' · ' + pct(t.qualified, t.leads) + '%' : ''}</span></div>
      <div class="ev-tile"><b>${f.num(d.results.speed.untouched)}</b><span>Not yet contacted</span></div>
      <div class="ev-tile"><b>${e.visitors == null ? '—' : f.num(e.visitors)}</b><span>Booth visitors</span></div>
    </div>
    <div class="ev-grid2">
      ${block('Leads by day', html`<span class="btn xs ev-noprint" data-act="pickSources">Lead Source${e.lead_sources.length ? ': ' + e.lead_sources.join(', ') : ''}</span>`, leadsChart(d), 'span2')}
      ${block('Follow-up SLA', info(TIPS.sla, { end: true }), slaBlock(d))}
    </div>
    ${block('Tasks', html`<span class="btn xs primary ev-noprint" data-act="newStep" data-preset="${JSON.stringify({ workstream: d.setup.tab_ws.leads[0] || '' })}">Add task</span>`,
      taskRows(d, steps, 'No tasks. Set this tab’s workstreams in Settings.', ctx))}`;
}

// ---- Budget: planned against actual by category, and every cost line.
function budget(d) {
  const e = d.event;
  return html`<div class="ev-tiles">
      <div class="ev-tile"><b>${moneyOr(d.planned)}</b><span>Budget</span></div>
      <div class="ev-tile"><b>${moneyOr(d.cost)}</b><span>Actual spend</span>${d.planned ? html`<div class="ev-split" style="height:6px;margin-top:8px"><i style="width:${Math.min(pct(d.cost, d.planned), 100)}%;background:var(--${d.cost > d.planned ? 'neg' : 'k'})"></i></div>` : ''}</div>
      <div class="ev-tile"><b style="color:var(--${d.planned && d.cost > d.planned ? 'neg' : 'ink'})">${d.planned ? moneyOr(d.planned - d.cost) : '—'}</b><span>${d.planned && d.cost > d.planned ? 'Over budget' : 'Remaining'}</span></div>
      <div class="ev-tile"><b>${moneyOr(d.costs.filter(c => !c.paid).reduce((x, c) => x + (c.amount || 0), 0))}</b><span>Unpaid</span></div>
    </div>
    ${block('Budget vs actual by category', '', budgetBars(d))}
    ${block('Cost lines', html`<span class="btn xs primary ev-noprint" data-act="newCost">Add cost</span>`, d.costs.length ? html`
      <div class="ev-row head"><span>Category</span><span>Item</span><span class="right">Budgeted</span><span class="right">Actual</span><span>Paid</span></div>
      ${d.costs.map(c => html`<div class="ev-row cost" data-act="editCost" data-arg="${c.id}"><span class="small muted">${c.category}</span><span class="ev-task">${c.item}</span>
        <span class="small right">${c.planned ? f.money(c.planned) : '—'}</span><span class="small right medium" style="color:var(--${c.planned && c.amount > c.planned ? 'neg' : 'ink'})">${f.money(c.amount)}</span>
        <span class="small" style="color:var(--${c.paid ? 'pos' : 'warn'})">${c.paid ? 'Paid' : 'Unpaid'}</span></div>`)}` : html`<div class="ev-empty">No costs recorded.</div>`)}
    ${e.budget && !d.costs.some(c => c.planned) ? html`<div class="small muted">Budget ${f.money(e.budget)} is the event total; add a budgeted amount to each cost line to compare by category.</div>` : ''}`;
}

function promotion(d) {
  // activities by week, starting the week of the first one
  const weekOf = iso => addDays(iso, -((new Date(iso + 'T00:00:00').getDay() + 6) % 7));
  const dated = d.promos.filter(p => p.day), undated = d.promos.filter(p => !p.day);
  const weeks = [...new Set(dated.map(p => weekOf(p.day)))].sort();
  const card = p => html`<div class="ev-act ${p.status === 'Done' ? 'done' : ''}" data-act="editPromo" data-arg="${p.id}">
    <span class="tiny semi" style="color:var(--${STATUS_TONE[p.status]})">${p.channel}</span><span>${p.what}</span><span class="tiny muted">${p.day ? day(p.day) : 'No date'} · ${p.owner || 'Unassigned'}</span></div>`;
  return html`<section class="ev-sec">
    <div class="ev-h"><h2>Promotion</h2><span class="row ev-noprint" style="gap:10px"><span class="ev-sub">${d.promos.filter(p => p.status === 'Done').length} of ${d.promos.length} live</span><span class="btn xs primary" data-act="newPromo">Add activity</span></span></div>
    ${d.promos.length ? html`<div class="ev-week">${weeks.map(w => html`<div><span class="tiny muted medium">Week of ${day(w)}${w <= d.event.starts && addDays(w, 6) >= d.event.starts ? ' · event week' : ''}</span>${dated.filter(p => weekOf(p.day) === w).map(card)}</div>`)}
      ${undated.length ? html`<div><span class="tiny muted medium">Not scheduled</span>${undated.map(card)}</div>` : ''}</div>`
      : html`<div class="small muted">No activities scheduled.</div>`}
  </section>`;
}

function content(d, ctx) {
  const pick = ctx.ui().platform || '';
  const platforms = [...new Set(d.creatives.map(c => c.platform))];
  const shown = d.creatives.filter(c => !pick || c.platform === pick);
  const color = c => PLATFORM_COLOR[c.platform] || '#6e6e73';
  return html`<section class="ev-sec">
    <div class="ev-h"><h2>Content</h2><span class="row ev-noprint" style="gap:10px">
      ${platforms.length > 1 ? switcher([{ arg: '', label: 'All', on: !pick }, ...platforms.map(p => ({ arg: p, label: p, color: PLATFORM_COLOR[p], on: pick === p }))], 'platform') : ''}
      <span class="btn xs primary" data-act="newCreative">Add post</span></span></div>
    ${shown.length ? html`<div class="ev-wall">${shown.map(c => html`<div class="ev-post">
      ${c.embed ? html`<iframe src="${c.embed}" loading="lazy" height="${c.platform === 'YouTube' ? 220 : c.platform === 'Instagram' ? 560 : 480}" sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerpolicy="strict-origin-when-cross-origin" title="${c.platform} post"></iframe>`
        : html`<a class="ev-post-card" href="${c.url}" target="_blank" rel="noopener" style="${c.image ? `background-image:url('${c.image}')` : `background-color:color-mix(in oklch, ${color(c)} 14%, var(--surface));color:${color(c)}`}">${c.image ? '' : c.platform}</a>`}
      <div class="ev-post-foot"><span class="stack" style="gap:1px;min-width:0"><span class="tiny semi" style="color:${color(c)}">${c.platform}${c.posted_on ? ' · ' + day(c.posted_on) : ''}</span><span class="clip">${c.caption || c.title || ''}</span></span>
        <span class="row ev-noprint" style="gap:10px"><a class="link tiny" href="${c.url}" target="_blank" rel="noopener" style="text-decoration:none">Open</a><span class="tiny faint" data-act="editCreative" data-arg="${c.id}" style="cursor:pointer">Edit</span></span></div></div>`)}</div>`
      : html`<div class="small muted">No posts added. LinkedIn, Instagram and YouTube links display as embedded posts.</div>`}
  </section>`;
}

// Where each target account stands, furthest step only: not reached, in Zoho, engaged at this event, or with an opportunity.
const STAGE = [['none', 'Not reached', 'color-mix(in oklch, var(--ink3) 30%, var(--surface))', 'No record in Zoho.'],
  ['known', 'In CRM', 'color-mix(in oklch, var(--k) 30%, var(--surface))', 'In Zoho; no lead from this event.'],
  ['engaged', 'Engaged', 'var(--k)', 'Lead captured with this event\u2019s Lead Source.'],
  ['deal', 'Opportunity', 'var(--pos)', 'Open or won opportunity in Zoho.']];
const stageOf = x => (x.deal ? 'deal' : x.engaged ? 'engaged' : x.known ? 'known' : 'none');

function stageBars(a) {
  return stacked(a.tiers.map(t => ({ label: `Tier ${t.tier}`, parts: STAGE.map(([k]) => a.targets.filter(x => x.tier === t.tier && stageOf(x) === k).length) })),
    STAGE.map(([, label, color]) => [label, color]));
}

function accounts(d, ctx) {
  const a = d.accounts, tier = Number(ctx.ui().tier) || 0;
  const list = a.targets.filter(x => !tier || x.tier === tier);
  const count = k => list.filter(x => stageOf(x) === k).length;
  const chase = a.targets.filter(x => x.tier === 1 && (stageOf(x) === 'none' || stageOf(x) === 'known'));
  return html`<section class="ev-sec">
    <div class="ev-h"><h2>Target accounts</h2><span class="row ev-noprint" style="gap:10px">${info(TIPS.accounts)}<span class="btn xs ${a.targets.length ? '' : 'primary'}" data-act="editTargets">${a.targets.length ? 'Edit list' : 'Add target accounts'}</span></span></div>
    ${a.targets.length ? html`
      <div class="ev-stats">
        <div class="ev-stat"><b>${a.targets.length}</b><span>Target accounts</span></div>
        <div class="ev-stat"><b>${a.targets.filter(x => ['engaged', 'deal'].includes(stageOf(x))).length}<span class="muted" style="font-size:16px"> · ${pct(a.targets.filter(x => ['engaged', 'deal'].includes(stageOf(x))).length, a.targets.length)}%</span></b><span>Engaged</span></div>
        <div class="ev-stat"><b style="color:var(--pos)">${a.targets.filter(x => x.deal).length}</b><span>Opportunities</span></div>
        <div class="ev-stat"><b>${moneyOr(a.influenced)}</b><span>Influenced pipeline ${info(TIPS.influenced)}</span></div>
      </div>
      ${chase.length ? html`<div class="ev-chase"><b>Tier 1 not engaged (${chase.length}):</b> ${chase.map(x => x.company).join(', ')}</div>` : ''}
    ` : html`<div class="small muted">No target accounts. Import a list to track coverage and influenced pipeline.</div>`}
  </section>
  ${a.targets.length ? html`<div class="ev-grid2">
    ${block('Accounts by tier', '', stageBars(a), 'span2')}
    ${block('Definitions', '', html`<div class="stack" style="gap:10px">${STAGE.map(([, label, color, means]) => html`<div class="row small" style="gap:10px;align-items:flex-start">
      <span style="width:10px;height:10px;border-radius:3px;background:${color};flex:none;margin-top:4px"></span><span><span class="medium">${label}.</span> <span class="muted">${means}</span></span></div>`)}</div>`)}
  </div>
  <section class="ev-sec">
    <div class="ev-h"><h2>Accounts by stage</h2>${switcher([{ arg: '', label: 'All tiers', on: !tier }, ...a.tiers.map(t => ({ arg: String(t.tier), label: `Tier ${t.tier}`, on: tier === t.tier }))], 'tier')}</div>
    <div class="ev-board">${STAGE.map(([k, label, color]) => html`<div class="ev-col">
      <div class="ev-col-h"><span style="width:10px;height:10px;border-radius:3px;background:${color};flex:none"></span><span class="medium">${label}</span><span class="muted">${count(k)}</span></div>
      ${list.filter(x => stageOf(x) === k).map(x => html`<div class="ev-acct"><span class="ev-tier t${x.tier}">T${x.tier}</span><span class="clip" title="${x.company}">${x.company}</span>
        ${x.deal ? html`<span class="tiny muted" style="margin-left:auto">${x.deal === 'won' ? 'Won' : x.deal}${x.pipeline ? ' · ' + f.moneyShort(x.pipeline) : ''}</span>` : ''}</div>`)}
      ${count(k) ? '' : html`<div class="tiny faint" style="padding:6px 2px">None</div>`}</div>`)}</div>
  </section>` : ''}`;
}

function results(d) {
  const r = d.results, t = r.total, e = d.event, m = d.money;
  return html`<div class="ev-tiles">
      <div class="ev-tile"><b>${moneyOr(m.per_lead)}</b><span>Cost per lead</span></div>
      <div class="ev-tile"><b>${moneyOr(m.per_qualified)}</b><span>Cost per qualified lead</span></div>
      <div class="ev-tile"><b>${times(m.pipeline_x)}</b><span>Pipeline ROI · ${moneyOr(t.pipeline)} sourced</span></div>
      <div class="ev-tile"><b>${times(m.won_x)}</b><span>Revenue ROI · ${moneyOr(t.won_value)} won</span></div>
      <div class="ev-tile"><b>${moneyOr(d.accounts.influenced)}</b><span>Influenced pipeline ${info(TIPS.influenced, { end: true })}</span></div>
    </div>
    ${e.lead_sources.length ? '' : html`<div class="small" style="color:var(--warn)">Set this event's Lead Source to count its leads and opportunities from Zoho.</div>`}
    <div class="ev-grid2">
      ${block('Lead funnel', e.target_leads ? html`<span class="ev-sub">Target ${f.num(e.target_leads)} leads${e.target_qualified ? ' · ' + f.num(e.target_qualified) + ' qualified' : ''}</span>` : '', funnelBars(d), 'span2')}
      ${block('By Lead Source', html`<span class="btn xs ev-noprint" data-act="pickSources">Change</span>`, r.sources.length ? r.sources.map(x => html`<div class="stack" style="gap:4px;padding:10px 0;border-top:1px solid var(--line2)">
          <span class="medium small">${x.source}</span><span class="tiny muted">${f.num(x.leads)} leads · ${f.num(x.qualified)} qualified · ${f.num(x.deals)} opportunities · ${moneyOr(x.pipeline)} · ${f.num(x.won)} won</span></div>`)
        : html`<div class="ev-empty">No Lead Source set.</div>`)}
    </div>
    ${block('Goals', html`<span class="btn xs ev-noprint" data-act="newGoal">Add goal</span>`, goalBars(d))}
    ${e.lessons ? block('Lessons learned', '', html`<p style="margin:0;max-width:75ch">${e.lessons}</p>`) : ''}`;
}

function room(d, ctx) {
  const ids = tabs(d).map(x => x[0]);
  const current = ids.includes(ctx.app.params.sec) ? ctx.app.params.sec : 'overview';
  const page = { overview: () => overview(d), plan: () => plan(d, ctx), promotion: () => promotion(d), content: () => content(d, ctx), booth: () => booth(d, ctx),
    accounts: () => accounts(d, ctx), leads: () => leadsTab(d, ctx), budget: () => budget(d), results: () => results(d) };
  return html`<div class="ev evw" data-kind="${d.event.kind}">${header(d, current)}
    <main class="ev-main">${ctx.ui().printing ? ['overview', 'results', 'budget', 'accounts'].filter(id => ids.includes(id)).map(id => page[id]()) : page[current]()}</main></div>`;
}

// ------------------------------------------------------------------------------- forms

const field = (label, name, value, extra = '') => html`<label class="field">${label}<input class="input" name="${name}" value="${value == null ? '' : value}" ${extra}></label>`;
const select = (label, name, options, value) => html`<label class="field">${label}<select class="input" name="${name}">${options.map(o => (Array.isArray(o) ? html`<option value="${o[0]}" ${o[0] === value ? 'selected' : ''}>${o[1]}</option>` : html`<option ${o === value ? 'selected' : ''}>${o}</option>`))}</select></label>`;
const buttons = (removeAct, id) => html`<div class="between" style="margin-top:4px">${id && removeAct ? html`<button type="button" class="btn danger" data-act="${removeAct}" data-arg="${id}">Delete</button>` : html`<span></span>`}
  <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div></div>`;
const owners = d => html`<datalist id="owners">${(d.team || []).map(n => html`<option value="${n}">`)}</datalist>`;
const suggest = (id, list) => html`<datalist id="${id}">${(list || []).map(x => html`<option value="${x}">`)}</datalist>`;
const check = (name, label, on) => html`<label class="row small" style="gap:8px"><input type="checkbox" name="${name}" ${on ? 'checked' : ''}> ${label}</label>`;

export default {
  uses: {},
  noTopbar: true,
  solo: app => !!app.params.id,  // an event opens as its own workspace, without Meridian's sidebar
  load: ctx => (ctx.app.params.id ? ctx.api.get('events/' + ctx.app.params.id) : ctx.api.get('events')),
  render(d, ctx) {
    if (!d.event) return home(d, ctx);
    return room(d, ctx);
  },

  modal(m, ctx) {
    const d = ctx.app.data;
    if (m.kind === 'event') {
      const e = m.event || { kind: 'booth', decision: 'Go' };
      return html`<form class="modal" data-submit="saveEvent" style="width:660px">
        <span class="section">${m.event ? 'Edit event' : 'New event'}</span>
        ${m.event ? '' : html`<label class="field">Task plan<select class="input" name="start_from">
          <option value="playbook">Playbook for this event type</option>
          ${(d.events || []).length ? html`<optgroup label="Copy from a past event">${[...d.events].sort((a, b) => (a.starts < b.starts ? 1 : -1)).map(x => html`<option value="event:${x.id}">${x.name} (${span(x)} ${x.starts.slice(0, 4)})</option>`)}</optgroup>` : ''}
          <option value="empty">Blank</option></select></label>
          <span class="small muted">Dates are adjusted to the new event. Copied tasks are reset to Not started and actual costs are cleared.</span>`}
        <div class="grid" style="grid-template-columns:2fr 1fr">${field('Event name', 'name', e.name, 'required data-autofocus placeholder="e.g. SFF 2026"')}${select('Type', 'kind', d.kinds, e.kind)}</div>
        <div class="grid" style="grid-template-columns:1fr 1fr 1fr">${field('Start date', 'starts', e.starts, 'type="date" required')}${field('End date', 'ends', e.ends, 'type="date"')}${select('Decision', 'decision', d.decisions || ['Considering', 'Go', 'No-go'], e.decision || 'Go')}</div>
        <div class="grid" style="grid-template-columns:1fr 1fr">${field('City', 'city', e.city)}${field('Venue', 'venue', e.venue)}${field('Partner', 'partner', e.partner, 'placeholder="If co-hosted, e.g. Vonage"')}${field('Booth / stand', 'booth', e.booth)}</div>
        ${field('Objective', 'goal', e.goal, 'placeholder="e.g. Book 25 meetings with Tier 1 banks"')}
        <div class="grid" style="grid-template-columns:repeat(3,1fr)">${field('Budget (₹)', 'budget', e.budget, 'type="number" min="0" step="any"')}${field('Lead target', 'target_leads', e.target_leads, 'type="number" min="0"')}${field('Qualified lead target', 'target_qualified', e.target_qualified, 'type="number" min="0"')}
          ${field('Meeting target', 'target_meetings', e.target_meetings, 'type="number" min="0"')}${field('Pipeline target (₹)', 'target_pipeline', e.target_pipeline, 'type="number" min="0" step="any"')}${field('Meetings held', 'meetings_held', e.meetings_held, 'type="number" min="0"')}</div>
        ${field('Lessons learned', 'lessons', e.lessons, 'placeholder="After the event: attend again? what to change?"')}
        ${buttons('removeEvent', m.event && e.id)}</form>`;
    }
    if (m.kind === 'step') {
      const s = m.step || { phase: 'promote', status: 'Not started', ...(m.preset || {}) };
      return html`<form class="modal" data-submit="saveStep">${owners(d)}${suggest('workstreams', d.setup.workstreams)}
        <span class="section">${m.step ? 'Edit task' : 'Add task'}</span>
        ${field('Task', 'title', s.title, 'required data-autofocus')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${select('Phase', 'phase', d.phases, s.phase)}${field('Due date', 'due', s.due, 'type="date"')}${field('Owner', 'owner', s.owner, 'list="owners"')}${select('Status', 'status', d.statuses, s.status)}</div>
        <div class="grid" style="grid-template-columns:1fr 1fr">${field('Workstream', 'workstream', s.workstream, 'list="workstreams"')}${field('Done when', 'done_when', s.done_when)}</div>
        ${field('Note', 'note', s.note)}${check('critical', 'Critical task', s.critical)}
        ${buttons('removeStep', m.step && s.id)}</form>`;
    }
    if (m.kind === 'playbook') {
      const s = m.step || { phase: 'plan', offset_days: -14 }, kinds = (s.kinds || '').split(',');
      return html`<form class="modal" data-submit="savePlaybookStep">
        <span class="section">${m.step ? 'Edit playbook task' : 'Add playbook task'}</span>
        ${field('Task', 'title', s.title, 'required data-autofocus')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${select('Phase', 'phase', d.phases, s.phase)}${field('Offset in days from start (e.g. −21)', 'offset_days', s.offset_days, 'type="number" step="1" required')}${field('Workstream', 'workstream', s.workstream)}${field('Default owner', 'owner', s.owner)}</div>
        ${field('Done when', 'done_when', s.done_when)}
        <div class="stack" style="gap:6px"><span class="small muted">Event types (none = all)</span><div class="row" style="gap:14px;flex-wrap:wrap">${d.kinds.map(([k, l]) => check('kind_' + k, l, kinds.includes(k)))}</div></div>
        ${check('critical', 'Critical task', s.critical)}
        ${buttons('removePlaybookStep', m.step && s.id)}</form>`;
    }
    if (m.kind === 'promo') {
      const p = m.promo || { channel: 'LinkedIn post', status: 'Not started' };
      return html`<form class="modal" data-submit="savePromo">${owners(d)}${suggest('channels', d.channels)}
        <span class="section">${m.promo ? 'Edit activity' : 'Add activity'}</span>
        ${field('Activity', 'what', p.what, 'required data-autofocus placeholder="e.g. Teaser post: meet us at booth 6H02"')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${field('Channel', 'channel', p.channel, 'list="channels" required')}${field('Date', 'day', p.day, 'type="date"')}${field('Owner', 'owner', p.owner, 'list="owners"')}${select('Status', 'status', d.statuses, p.status)}</div>
        ${buttons('removePromo', m.promo && p.id)}</form>`;
    }
    if (m.kind === 'creative') {
      const c = m.creative || {};
      return html`<form class="modal" data-submit="saveCreative">
        <span class="section">${m.creative ? 'Edit post' : 'Add post'}</span>
        ${field('Post URL', 'url', c.url, 'required data-autofocus placeholder="https://www.linkedin.com/posts/…"')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${field('Published on', 'posted_on', c.posted_on, 'type="date"')}${field('Image URL (optional)', 'image', c.image, 'placeholder="For platforms that cannot be embedded"')}</div>
        ${field('Caption', 'caption', c.caption)}
        ${buttons('removeCreative', m.creative && c.id)}</form>`;
    }
    if (m.kind === 'cost') {
      const c = m.cost || { category: d.cost_kinds[0] };
      return html`<form class="modal" data-submit="saveCost">${suggest('costKinds', d.cost_kinds)}
        <span class="section">${m.cost ? 'Edit cost' : 'Add cost'}</span>
        ${field('Item', 'item', c.item, 'required data-autofocus placeholder="e.g. Booth space 6H02"')}
        <div class="grid" style="grid-template-columns:1fr 1fr 1fr">${field('Category', 'category', c.category, 'list="costKinds" required')}${field('Budgeted (₹)', 'planned', c.planned, 'type="number" min="0" step="any"')}${field('Actual (₹)', 'amount', c.amount, 'type="number" min="0" step="any"')}</div>
        ${check('paid', 'Paid', c.paid)}
        ${buttons('removeCost', m.cost && c.id)}</form>`;
    }
    if (m.kind === 'setup') {
      const st = d.setup, ws = (tab, w) => check(`ws_${tab}::${w}`, w, st.tab_ws[tab].includes(w));
      return html`<form class="modal" data-submit="saveSetup" style="width:640px">
        <span class="section">Settings · ${d.event.name}</span>
        <span class="small muted">Show, hide and rename tabs for this event.</span>
        <div class="stack" style="gap:8px">${st.tabs.map(t => html`<div class="row" style="gap:12px">
          <label class="row small" style="gap:8px;width:190px"><input type="checkbox" name="show_${t.id}" ${t.show ? 'checked' : ''} ${t.id === 'overview' ? 'disabled' : ''}> ${t.standard}</label>
          <input class="input" name="name_${t.id}" value="${t.label === t.standard ? '' : t.label}" placeholder="${t.standard}" style="flex:1"></div>`)}</div>
        <span class="section" style="font-size:14px;margin-top:6px">Tab task filters</span>
        ${['booth', 'leads'].map(tab => html`<div class="stack" style="gap:6px"><span class="small medium">${tabLabel(d, tab)} · workstreams</span>
          <div class="row" style="gap:6px 14px;flex-wrap:wrap">${st.workstreams.map(w => ws(tab, w))}</div></div>`)}
        ${field('Add workstreams (comma-separated)', 'new_workstreams', '', 'placeholder="e.g. Speaker prep, Hospitality"')}
        ${buttons(null, null)}</form>`;
    }
    if (m.kind === 'goal') {
      const g = m.goal || {};
      return html`<form class="modal" data-submit="saveGoal">
        <span class="section">${m.goal ? 'Edit goal' : 'Add goal'}</span>
        <span class="small muted">Track a metric not synced from Zoho, e.g. demos, registrations or attendees.</span>
        ${field('Goal', 'name', g.name, 'required data-autofocus placeholder="e.g. Demos given at the booth"')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${field('Target', 'target', g.target, 'type="number" step="any" min="0"')}${field('Actual', 'actual', g.actual, 'type="number" step="any" min="0"')}</div>
        ${buttons('removeGoal', m.goal && g.id)}</form>`;
    }
    if (m.kind === 'info') {
      const i = m.info || {};
      return html`<form class="modal" data-submit="saveInfo">
        <span class="section">${m.info ? 'Edit detail' : 'Add detail'}</span>
        ${field('Detail', 'label', i.label, `required ${m.info ? '' : 'data-autofocus'} placeholder="e.g. Organiser contact"`)}
        ${field('Value', 'value', i.value, `${m.info ? 'data-autofocus' : ''} placeholder="Text, an email, or a link starting with https://"`)}
        ${buttons('removeInfo', m.info && i.id)}</form>`;
    }
    if (m.kind === 'eventKind') {
      const k = m.key ? d.kinds.find(x => x[0] === m.key) : null;
      return html`<form class="modal" data-submit="saveKind">
        <span class="section">${k ? 'Rename event type' : 'Add event type'}</span>
        <span class="small muted">${k ? `Used by ${d.kind_use[m.key] || 0} event(s). Types in use cannot be deleted.` : 'After creating the type, assign playbook tasks to it.'}</span>
        ${field('Name', 'label', k ? k[1] : '', 'required data-autofocus placeholder="e.g. Customer summit"')}
        ${buttons(k ? 'removeKind' : null, m.key)}</form>`;
    }
    if (m.kind === 'targets') {
      const text = d.accounts.targets.map(t => [t.company, t.tier, t.domain].filter(x => x != null && x !== '').join(', ')).join('\n');
      return html`<form class="modal" data-submit="saveTargets" style="width:600px">
        <span class="section">Target accounts</span>
        <span class="small muted">One account per line: company, tier (1–3), domain (optional). Paste from a spreadsheet. Do not include contact names's names.</span>
        <textarea class="input" name="text" rows="14" data-autofocus placeholder="DBS Bank, 1, dbs.com&#10;HSBC, 1&#10;Maybank, 2">${text}</textarea>
        ${buttons(null, null)}</form>`;
    }
    if (m.kind === 'sources') {
      const mine = new Set(d.event.lead_sources), q = (ctx.ui().sourceQ || '').toLowerCase();
      const options = d.source_options.filter(o => mine.has(o.source) || !q || o.source.toLowerCase().includes(q));
      return html`<form class="modal" data-submit="saveSources" style="width:560px">
        <span class="section">Lead Source for ${d.event.name}</span>
        <span class="small muted">Select the Zoho Lead Source values for this event. Each value can be assigned to one event only.</span>
        <input class="input" placeholder="Search Lead Source" value="${ctx.ui().sourceQ || ''}" data-input="sourceQ" autocomplete="off">
        <div class="stack" style="gap:2px;max-height:320px;overflow:auto">${options.slice(0, 150).map(o => { const other = d.taken[o.source]; return html`<label class="row small" style="gap:8px;padding:4px 2px;${other ? 'opacity:.45' : ''}">
          <input type="checkbox" name="s::${o.source}" ${mine.has(o.source) ? 'checked' : ''} ${other ? 'disabled' : ''}><span style="flex:1" class="clip">${o.source}</span>
          <span class="tiny muted">${other ? 'used by ' + other : f.num(o.leads) + ' leads'}</span></label>`; })}</div>
        ${buttons(null, null)}</form>`;
    }
    return '';
  },

  actions: {
    home(ctx, d) { ctx.ui().home = d.arg; ctx.render(); },
    phase(ctx, d) { ctx.ui().phase = d.arg; ctx.render(); },
    owner(ctx, d) { ctx.ui().owner = d.arg; ctx.render(); },
    platform(ctx, d) { ctx.ui().platform = d.arg; ctx.render(); },
    tier(ctx, d) { ctx.ui().tier = d.arg; ctx.render(); },
    // the report prints the overview, results, accounts and promotion together, then the page returns to normal
    print(ctx) { ctx.ui().printing = true; ctx.render(); setTimeout(() => { window.print(); ctx.ui().printing = false; ctx.render(); }, 60); },
    newEvent: ctx => ctx.openModal({ kind: 'event' }),
    editEvent: ctx => ctx.openModal({ kind: 'event', event: ctx.app.data.event }),
    newStep: (ctx, d) => ctx.openModal({ kind: 'step', preset: d && d.preset ? JSON.parse(d.preset) : {} }),
    show(ctx, d) { ctx.ui().show = d.arg; ctx.render(); },
    clearFilters(ctx) { Object.assign(ctx.ui(), { q: '', show: 'all', phase: '', ws: '', owner: '' }); ctx.render(); },
    unpick(ctx) { ctx.ui().picked = []; ctx.ui().confirmDelete = false; ctx.render(); },
    askDelete(ctx) { ctx.ui().confirmDelete = true; ctx.render(); },
    bulkDelete: ctx => bulk(ctx, { delete: true }, 'Tasks deleted.'),
    bulkShift(ctx) {
      const days = document.getElementById('bulkShift').value;
      if (!days) return ctx.toast('Enter a number of days, e.g. 7 or -3.');
      return bulk(ctx, { shift: days }, 'Dates shifted.');
    },
    setup: ctx => ctx.openModal({ kind: 'setup' }),
    newGoal: ctx => ctx.openModal({ kind: 'goal' }),
    editGoal: (ctx, d) => ctx.openModal({ kind: 'goal', goal: ctx.app.data.goals.find(g => String(g.id) === d.arg) }),
    newInfo: ctx => ctx.openModal({ kind: 'info' }),
    editInfo: (ctx, d) => ctx.openModal({ kind: 'info', info: ctx.app.data.info.find(i => String(i.id) === d.arg) }),
    removeGoal: (ctx, d) => remove(ctx, 'remove_goal', d.arg),
    removeInfo: (ctx, d) => remove(ctx, 'remove_info', d.arg),
    pickKind(ctx, d) { ctx.ui().kind = d.arg; ctx.render(); },
    newKind: ctx => ctx.openModal({ kind: 'eventKind' }),
    editKind: (ctx, d) => ctx.openModal({ kind: 'eventKind', key: d.arg }),
    removeKind(ctx, d) {
      ctx.app.modal = null;
      return ctx.save(() => ctx.api.post('events', { what: 'remove_kind', data: { key: d.arg } }), 'Event type deleted.');
    },
    editStep: (ctx, d) => ctx.openModal({ kind: 'step', step: ctx.app.data.steps.find(s => String(s.id) === d.arg) }),
    newPlaybookStep: ctx => ctx.openModal({ kind: 'playbook' }),
    editPlaybookStep: (ctx, d) => ctx.openModal({ kind: 'playbook', step: ctx.app.data.playbook.find(s => String(s.id) === d.arg) }),
    newPromo: ctx => ctx.openModal({ kind: 'promo' }),
    editPromo: (ctx, d) => ctx.openModal({ kind: 'promo', promo: ctx.app.data.promos.find(p => String(p.id) === d.arg) }),
    newCreative: ctx => ctx.openModal({ kind: 'creative' }),
    editCreative: (ctx, d) => ctx.openModal({ kind: 'creative', creative: ctx.app.data.creatives.find(c => String(c.id) === d.arg) }),
    newCost: ctx => ctx.openModal({ kind: 'cost' }),
    editCost: (ctx, d) => ctx.openModal({ kind: 'cost', cost: ctx.app.data.costs.find(c => String(c.id) === d.arg) }),
    editTargets: ctx => ctx.openModal({ kind: 'targets' }),
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
    planWs(ctx, value) { ctx.ui().ws = value; ctx.render(); },
    planOwner(ctx, value) { ctx.ui().owner = value; ctx.render(); },
    groupBy(ctx, value) { ctx.ui().by = value; ctx.render(); },
    stepField: (ctx, value, el) => ctx.save(() => ctx.api.post('events', { what: 'step_field', id: Number(el.dataset.id), data: { field: el.dataset.field, value } })),
    pickStep(ctx, value, el) { pick(ctx, [Number(el.dataset.id)], el.checked); },
    pickGroup(ctx, value, el) { pick(ctx, el.dataset.ids.split(',').map(Number), el.checked); },
    bulkField(ctx, value, el) {
      if (!value) return;
      return bulk(ctx, { field: el.dataset.field, value: value === '-' ? '' : value }, 'Tasks updated.');
    },
  },

  inputs: {
    sourceQ(ctx, value) { ctx.ui().sourceQ = value; ctx.render(); },
    taskQ(ctx, value) { ctx.ui().q = value; ctx.render(); },
  },

  submits: {
    async saveEvent(ctx, v) {
      const old = ctx.app.modal.event;
      ctx.app.modal = null;
      const r = await ctx.save(() => ctx.api.post('events', { what: 'event', id: old ? old.id : null, data: v }), old ? 'Saved.' : 'Event created.');
      if (r && !old) ctx.go('events', { id: r.event_id });
    },
    saveStep: (ctx, v) => saveItem(ctx, 'step', 'step', { ...v, critical: !!v.critical }),
    savePlaybookStep: (ctx, v) => saveItem(ctx, 'playbook_step', 'step', { ...v, critical: !!v.critical }),
    savePromo: (ctx, v) => saveItem(ctx, 'promo', 'promo', v),
    saveCreative: (ctx, v) => saveItem(ctx, 'creative', 'creative', v, 'Post added.'),
    saveCost: (ctx, v) => saveItem(ctx, 'cost', 'cost', { ...v, paid: !!v.paid }),
    saveGoal: (ctx, v) => saveItem(ctx, 'goal', 'goal', v),
    saveInfo: (ctx, v) => saveItem(ctx, 'info', 'info', v),
    saveKind(ctx, v) {
      const key = ctx.app.modal.key;
      ctx.app.modal = null;
      return ctx.save(() => ctx.api.post('events', { what: 'kind', data: { key, label: v.label } }), key ? 'Event type renamed.' : 'Event type added.');
    },
    saveSetup(ctx, v) {
      ctx.app.modal = null;
      const ws = tab => Object.keys(v).filter(k => k.startsWith(`ws_${tab}::`)).map(k => k.slice(tab.length + 5));
      return ctx.save(() => ctx.api.post('events', { what: 'setup', event_id: ctx.app.data.event.id, data: { ...v, ws_booth: ws('booth'), ws_leads: ws('leads') } }), 'Settings saved.');
    },
    saveTargets(ctx, v) {
      ctx.app.modal = null;
      return ctx.save(() => ctx.api.post('events', { what: 'targets', event_id: ctx.app.data.event.id, data: { text: v.text } }), 'Target accounts saved.');
    },
    saveSources(ctx, v) {
      ctx.app.modal = null;
      const sources = Object.keys(v).filter(k => k.startsWith('s::')).map(k => k.slice(3));
      return ctx.save(() => ctx.api.post('events', { what: 'sources', event_id: ctx.app.data.event.id, data: { sources } }), 'Lead Source saved.');
    },
  },
};

function saveItem(ctx, what, key, v, done = 'Saved.') {
  const item = ctx.app.modal[key];
  ctx.app.modal = null;
  const eventId = ctx.app.data.event ? ctx.app.data.event.id : null;
  return ctx.save(() => ctx.api.post('events', { what, id: item ? item.id : null, event_id: eventId, data: v }), done);
}

// tasks picked in the task list for a change to many at once
function pick(ctx, ids, on) {
  const ui = ctx.ui(), set = new Set(ui.picked || []);
  ids.forEach(id => (on ? set.add(id) : set.delete(id)));
  ui.picked = [...set];
  ui.confirmDelete = false;
  ctx.render();
}

async function bulk(ctx, change, done) {
  const ui = ctx.ui();
  const r = await ctx.save(() => ctx.api.post('events', { what: 'steps', event_id: ctx.app.data.event.id, data: { ids: ui.picked || [], ...change } }), done);
  if (r) { ui.picked = []; ui.confirmDelete = false; ctx.render(); }
}

function remove(ctx, what, id) {
  ctx.app.modal = null;
  return ctx.save(() => ctx.api.post('events', { what, id: Number(id) }), 'Deleted.');
}

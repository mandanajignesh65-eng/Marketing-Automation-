import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, segmented, info, switcher } from '../ui.js';

// Event Hub. The home screen shows every event on one calendar and ranks finished events by return. Each event opens as a
// room: a pinned event pass (who, when, countdown, stage, headline KPIs) beside sections for readiness, promotion,
// content, target accounts, and results and ROI. Figures come from Zoho and are worked out here; typed status is the minority.

const HOME_TABS = [['calendar', 'Calendar'], ['performance', 'Performance'], ['playbook', 'Playbook']];
const STAGES = [['Planning', 'Planning'], ['Promoting', 'Promotion'], ['Live', 'Event days'], ['Follow-up', 'Follow-up'], ['Done', 'Results']];
const STATUS_TONE = { 'Not started': 'ink3', 'In progress': 'warn', 'Waiting on others': 'neg', Done: 'pos' };
const PLATFORM_COLOR = { Instagram: '#d6249f', LinkedIn: '#0a66c2', Facebook: '#1877f2', X: '#111111', YouTube: '#ff0000', Web: '#6e6e73' };
const KIND_COLOR = { booth: 'var(--accent)', sponsor: 'var(--violet)', partner: 'oklch(0.62 0.13 175)', roundtable: 'oklch(0.66 0.14 60)', webinar: 'oklch(0.6 0.15 25)' };
const TIPS = {
  sourced: 'Leads and opportunities whose Lead Source in Zoho is this event.',
  influenced: 'Open or won opportunities of target accounts that were already open while the event ran.',
  sla: 'Time from a lead reaching Zoho (or the event\'s last day, whichever is later) to the owner\'s first update. Leads Meridian has not seen touched yet are counted as untouched.',
  accounts: 'Engaged: a lead from this company came in with this event\'s Lead Source. In CRM: the company exists in Zoho. Matched by company name without legal suffixes, or by domain.',
  roi: 'Pipeline ROI: sourced pipeline divided by event cost. Revenue ROI: closed-won value divided by event cost.',
  playbook: 'Every new event gets these tasks for its type. Due dates count from the first day; follow-up tasks count from the last day. Diamonds mark critical tasks.',
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
  if (view === 'playbook') return html`${head}${playbook(d)}`;
  if (view === 'performance') return html`${head}${performance(d)}`;
  return html`${head}${calendar(d)}`;
}

function calendar(d) {
  if (!d.events.length) return html`<div class="ev-gantt stack" style="gap:8px;padding:28px"><span class="title">No events yet</span>
    <span class="small muted">Create an event and pick its type. It gets the standard playbook for that type, with every due date set from the event dates.</span>
    <span><span class="btn primary" data-act="newEvent">New event</span></span></div>`;
  // the window: from the earliest planning start to the latest follow-up end, clipped around today
  const starts = d.events.map(e => toDays(e.starts) - 42), ends = d.events.map(e => toDays(e.ends_on) + 30);
  const lo = Math.min(...starts, toDays(d.today) - 14), hi = Math.max(...ends, toDays(d.today) + 30);
  const x = iso => ((toDays(iso) - lo) / (hi - lo)) * 100;
  const months = [];
  for (let t = lo; t <= hi; t++) { const dt = new Date(t * 864e5); if (dt.getUTCDate() === 1 || t === lo) months.push([t, dt.toLocaleDateString('en-GB', { month: 'short' })]); }
  const seg = (a, b, color, op) => html`<span class="ev-gseg" style="left:${x(a)}%;width:${Math.max(x(b) - x(a), 0.6)}%;background:${color};opacity:${op}"></span>`;
  // across every event: what is coming, what is committed, what came back
  const upcoming = d.events.filter(e => e.days_to_go > 0), next = [...upcoming].sort((a, b) => a.days_to_go - b.days_to_go)[0];
  const sum = k => d.events.reduce((t, e) => t + (k(e) || 0), 0);
  const cost = sum(e => e.cost), qualified = sum(e => e.total.qualified), pipeline = sum(e => e.total.pipeline);
  return html`<div class="ev-sec" style="padding:20px 24px"><div class="ev-stats">
      <div class="ev-stat"><b>${next ? next.days_to_go : '—'}<span class="muted" style="font-size:15px"> days</span></b><span>${next ? 'to ' + next.name : 'No upcoming event'}</span></div>
      <div class="ev-stat"><b>${upcoming.length}</b><span>Upcoming events</span></div>
      <div class="ev-stat"><b style="color:var(--${sum(e => e.progress.overdue) ? 'neg' : 'ink'})">${sum(e => e.progress.overdue)}</b><span>Overdue tasks across events</span></div>
      <div class="ev-stat"><b>${moneyOr(sum(e => e.budget))}</b><span>Budget committed</span></div>
      <div class="ev-stat"><b>${moneyOr(qualified ? cost / qualified : null)}</b><span>Blended cost per qualified lead</span></div>
      <div class="ev-stat"><b>${moneyOr(pipeline)}</b><span>Sourced pipeline</span></div>
    </div></div>
    <div class="ev-gantt">
    <div style="display:grid;grid-template-columns:220px minmax(0,1fr) 250px;gap:18px;padding:0 8px 8px">
      <span class="small muted">${d.events.length} event${d.events.length === 1 ? '' : 's'}</span>
      <div style="position:relative;height:16px">${months.map(([t, m]) => html`<span class="micro faint" style="position:absolute;left:${(t - lo) / (hi - lo) * 100}%">${m}</span>`)}</div>
      <div class="ev-legend"><span style="--c:var(--ink3)">Planning</span><span style="--c:var(--accent)">Event</span><span style="--c:var(--pos)">Follow-up</span></div></div>
    ${d.events.map(e => { const k = KIND_COLOR[e.kindKey] || 'var(--accent)'; return html`<a class="ev-grow" href="#/events?id=${e.id}">
      <span class="stack" style="gap:3px;min-width:0"><span class="medium clip">${e.name}</span><span class="tiny muted clip">${e.kind} · ${span(e)}${e.city ? ' · ' + e.city : ''}</span></span>
      <span class="ev-gbar">
        ${seg(addDays(e.starts, -42), e.starts, 'var(--ink3)', 0.28)}${seg(e.starts, addDays(e.ends_on, 1), k, 1)}${seg(addDays(e.ends_on, 1), addDays(e.ends_on, 30), 'var(--pos)', 0.35)}
        <span style="position:absolute;top:0;bottom:0;left:${x(d.today)}%;border-left:1.5px dashed var(--ink2)"></span></span>
      <span class="row" style="gap:16px;justify-content:flex-end">
        <span class="ev-meter"><b>${e.progress.readiness}%</b><span>readiness</span></span>
        <span class="ev-meter"><b style="color:var(--${e.progress.overdue ? 'neg' : 'ink3'})">${e.progress.overdue}</b><span>overdue</span></span>
        <span class="ev-meter"><b>${e.has_sources ? f.num(e.total.leads) : '—'}</b><span>leads</span></span></span></a>`; })}
    <div class="row tiny muted" style="gap:6px;padding:10px 8px 4px">Dashed line: today</div></div>`;
}

function performance(d) {
  const done = d.events.filter(e => e.result_age >= 0 && e.has_sources);
  if (!done.length) return html`<div class="card pad small muted">Results appear here once an event has taken place and its Lead Source is set.</div>`;
  const ranked = [...done].sort((a, b) => (a.money.per_qualified ?? 1e18) - (b.money.per_qualified ?? 1e18));
  const top = Math.max(...ranked.map(e => e.money.pipeline_x || 0), 1);
  const cols = 'minmax(0,1.6fr) 90px 80px 110px 110px minmax(160px,1fr)';
  return html`<div class="card clipped" style="--cols:${cols}">
    <div class="baseline" style="padding:16px 16px 12px"><span class="title">Event performance</span><span class="small muted">Ranked by cost per qualified lead · results settle ${d.result_days} days after an event</span></div>
    <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Event</span><span>Leads</span><span>Qualified</span><span>Cost per qualified lead</span><span>Pipeline</span><span style="text-align:left">Pipeline ROI</span></div>
    ${ranked.map(e => html`<a class="trow right" href="#/events?id=${e.id}" style="color:inherit;text-decoration:none">
      <span class="stack" style="gap:2px;text-align:left;min-width:0"><span class="medium clip">${e.name}</span>
        <span class="tiny muted">${span(e)} · ${e.result_age < d.result_days ? html`<span style="color:var(--warn)">too early: ${e.result_age} of ${d.result_days} days</span>` : 'final'}</span></span>
      <span>${f.num(e.total.leads)}</span><span>${f.num(e.total.qualified)}</span><span class="medium">${moneyOr(e.money.per_qualified)}</span><span>${moneyOr(e.total.pipeline)}</span>
      <span class="row" style="gap:8px"><span class="track" style="flex:1;height:8px;border-radius:4px"><span class="fill" style="display:block;width:${(e.money.pipeline_x || 0) / top * 100}%;background:var(--pos)"></span></span><span class="small medium" style="width:44px">${times(e.money.pipeline_x)}</span></span></a>`)}
  </div>`;
}

function playbook(d) {
  const kindName = Object.fromEntries(d.kinds);
  return html`<div class="small muted row" style="gap:6px">Standard tasks by phase${info(TIPS.playbook)}</div>
    ${d.phases.map(([key, label]) => { const steps = d.playbook.filter(s => s.phase === key); return html`<div class="card" style="padding:14px 20px 6px">
      <div class="title" style="margin-bottom:6px">${label}</div>
      ${steps.map(s => html`<div class="row" style="gap:14px;padding:9px 0;border-top:1px solid var(--line2)">
        <span class="tiny muted right" style="width:72px;flex:none">${key === 'follow' ? `+${s.offset_days} after` : s.offset_days === 0 ? 'Event day' : s.offset_days < 0 ? `${-s.offset_days} d before` : `${s.offset_days} d after`}</span>
        <span style="width:10px;height:10px;flex:none;${s.critical ? 'background:var(--neg);transform:rotate(45deg);border-radius:2px' : 'background:var(--ink3);border-radius:50%'}" title="${s.critical ? 'Critical' : ''}"></span>
        <span class="stack" style="flex:1;min-width:0;gap:1px"><span class="medium editable" data-act="editPlaybookStep" data-arg="${s.id}">${s.title}</span>
          <span class="tiny muted">${[s.workstream, s.done_when && 'Done when: ' + s.done_when, s.kinds ? s.kinds.split(',').map(k => kindName[k]).join(', ') : 'All event types'].filter(Boolean).join(' · ')}</span></span></div>`)}
    </div>`; })}`;
}

// ------------------------------------------------------------------------------- the event workspace
// One event fills the window: a header with who, when and where, then one tab per area of work. Overview shows every
// area at a glance; each other tab is the full tracker for that area.

const BOOTH_WS = ['Booth & logistics', 'Booth team'], LEAD_WS = ['Lead capture', 'Follow-up'];
const tabs = d => {
  const ws = list => d.steps.filter(s => list.includes(s.workstream));
  const late = list => list.filter(s => s.status !== 'Done' && s.due && s.due < d.today).length;
  const booth = ws(BOOTH_WS), leads = ws(LEAD_WS);
  return [['overview', 'Overview', ''], ['plan', 'Plan', d.progress.overdue ? html`<em>${d.progress.overdue}</em>` : `${d.progress.done}/${d.progress.total}`],
    ['promotion', 'Promotion', d.promos.length || ''], ['content', 'Content', d.creatives.length || ''],
    ['booth', 'Booth & logistics', booth.length ? (late(booth) ? html`<em>${late(booth)}</em>` : `${booth.filter(s => s.status === 'Done').length}/${booth.length}`) : ''],
    ['accounts', 'Target accounts', d.accounts.targets.length || ''], ['leads', 'Leads & follow-up', late(leads) ? html`<em>${late(leads)}</em>` : (d.event.lead_sources.length ? f.num(d.results.total.leads) : '')],
    ['budget', 'Budget', d.cost ? f.moneyShort(d.cost) : ''], ['results', 'Results & ROI', '']];
};

function header(d, current) {
  const e = d.event, now = STAGES.findIndex(s => s[0] === d.phase);
  const count = d.phase === 'Live' ? `Day ${toDays(d.today) - toDays(e.starts) + 1} of the event`
    : d.days_to_go > 0 ? `${d.days_to_go} day${d.days_to_go === 1 ? '' : 's'} to go` : `${toDays(d.today) - toDays(e.ends || e.starts)} days since the event`;
  return html`<header class="evw-head">
    <div class="evw-top"><a href="#/events" class="ev-back">← All events</a>
      <span class="row ev-noprint" style="gap:8px"><span class="btn xs" data-act="editEvent">Edit event</span><span class="btn xs" data-act="print">Export report</span></span></div>
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
const openTab = (d, sec, label) => html`<a class="link small ev-noprint" href="#/events?id=${d.event.id}&sec=${sec}" style="text-decoration:none">${label} →</a>`;

// A row per task: due date, task, owner, status. Used by every tab that tracks tasks.
function taskRows(d, steps, empty = 'No tasks here.') {
  return steps.length ? steps.map(s => html`<div class="ev-row">
      <span class="ev-when" style="color:var(--${s.status !== 'Done' && s.due && s.due < d.today ? 'neg' : 'ink2'})">${day(s.due)}</span>
      <span class="ev-task editable ${s.status === 'Done' ? 'muted' : ''}" data-act="editStep" data-arg="${s.id}">${s.title}${s.critical ? html` <span class="ev-crit">Critical</span>` : ''}
        ${s.done_when || s.note ? html`<span class="tiny muted" style="display:block;margin-top:2px">${[s.done_when && 'Done when: ' + s.done_when, s.note].filter(Boolean).join(' · ')}</span>` : ''}</span>
      <span class="ev-owner">${s.owner || 'Unassigned'}</span>
      <select class="input ev-status" data-change="stepStatus" data-id="${s.id}" style="color:var(--${STATUS_TONE[s.status]})">${d.statuses.map(x => html`<option ${x === s.status ? 'selected' : ''}>${x}</option>`)}</select></div>`)
    : html`<div class="ev-empty">${empty}</div>`;
}

// The plan on a date line: one lane per phase, a mark per task, today and the event days shaded.
function timeline(d, compact) {
  const steps = d.steps.filter(s => s.due);
  if (!steps.length) return html`<div class="ev-empty">No dated tasks.</div>`;
  const lo = Math.min(...steps.map(s => toDays(s.due)), toDays(d.today)) - 1, hi = Math.max(...steps.map(s => toDays(s.due)), toDays(d.today)) + 2;
  const x = iso => ((toDays(iso) - lo) / (hi - lo)) * 100;
  const cls = s => (s.status === 'Done' ? 'done' : s.due < d.today ? 'late' : s.status === 'Not started' ? '' : 'prog');
  const ticks = []; for (let t = lo + 1; t < hi; t += Math.max(7, Math.round((hi - lo) / 7))) ticks.push(t);
  return html`<div class="ev-tl ${compact ? 'compact' : ''}">
    <div class="ev-tl-axis">${ticks.map(t => html`<span style="left:${(t - lo) / (hi - lo) * 100}%">${day(new Date(t * 864e5).toISOString())}</span>`)}</div>
    ${d.phases.map(([key, label]) => html`<div class="ev-lane"><span>${label}</span><div class="ev-lane-track">
      <span class="ev-band" style="left:${x(d.event.starts)}%;width:${x(addDays(d.event.ends || d.event.starts, 1)) - x(d.event.starts)}%"></span>
      <span class="ev-today" style="left:${x(d.today)}%"></span>
      ${steps.filter(s => s.phase === key).map(s => html`<span class="ev-dot ${cls(s)} ${s.critical ? 'crit' : ''}" style="left:${x(s.due)}%" data-act="editStep" data-arg="${s.id}"
        title="${day(s.due)} · ${s.title} · ${s.owner || 'Unassigned'} · ${s.status}"></span>`)}</div></div>`)}
    <div class="ev-legend" style="margin-top:10px"><span style="--c:var(--pos)">Done</span><span style="--c:var(--warn)">In progress</span><span style="--c:var(--neg)">Overdue</span><span style="--c:var(--ink3)">Not started</span><span style="--c:var(--k)">Today</span><span style="--c:color-mix(in oklch, var(--k) 30%, transparent)">Event days</span></div>
  </div>`;
}

function funnelBars(d) {
  const t = d.results.total, steps = [['Leads', t.leads], ['Qualified leads', t.qualified], ['Opportunities', t.deals], ['Closed won', t.won]], top = Math.max(t.leads, t.deals, 1);
  return html`<div class="ev-funnel">${steps.map(([label, n], i) => html`<div class="ev-fstep"><span class="small muted">${label}</span>
    <div><div class="ev-fbar" style="width:${Math.max(n / top * 100, 6)}%">${f.num(n)}</div></div>
    <span class="small muted">${i && steps[i - 1][1] && n <= steps[i - 1][1] ? pct(n, steps[i - 1][1]) + '%' : ''}</span></div>`)}</div>`;
}

function slaBlock(d) {
  const sp = d.results.speed;
  if (!sp.leads) return html`<div class="ev-empty">Measured once the event's leads are in Zoho.</div>`;
  return html`<div class="ev-stats" style="grid-template-columns:repeat(3,1fr)">
      <div class="ev-stat"><b>${pct(sp.h24, sp.leads)}%</b><span>within 24 h</span></div><div class="ev-stat"><b>${pct(sp.h72, sp.leads)}%</b><span>within 72 h</span></div><div class="ev-stat"><b>${pct(sp.d7, sp.leads)}%</b><span>within 7 days</span></div></div>
    <div class="ev-split" style="margin-top:14px"><i style="width:${pct(sp.h24, sp.leads)}%;background:var(--pos)"></i><i style="width:${pct(sp.h72 - sp.h24, sp.leads)}%;background:color-mix(in oklch, var(--pos) 55%, var(--surface))"></i><i style="width:${pct(sp.d7 - sp.h72, sp.leads)}%;background:var(--warn)"></i><i style="width:${pct(sp.timed - sp.d7, sp.leads)}%;background:var(--neg)"></i></div>
    <div class="tiny muted" style="margin-top:8px">${sp.untouched} of ${sp.leads} leads have no first contact recorded</div>`;
}

function budgetBars(d) {
  const kinds = {};
  d.costs.forEach(c => { const k = kinds[c.category] = kinds[c.category] || { planned: 0, actual: 0 }; k.planned += c.planned || 0; k.actual += c.amount || 0; });
  const kmax = Math.max(...Object.values(kinds).map(k => Math.max(k.planned, k.actual)), 1);
  if (!Object.keys(kinds).length) return html`<div class="ev-empty">No costs entered yet.</div>`;
  return html`<div class="stack" style="gap:12px">${Object.entries(kinds).map(([k, v]) => html`<div style="display:grid;grid-template-columns:minmax(120px,190px) minmax(0,1fr) 120px;gap:14px;align-items:center">
      <span class="small clip">${k}</span>
      <div style="position:relative;height:10px;border-radius:5px;background:var(--track)"><span style="position:absolute;left:0;top:0;bottom:0;border-radius:5px;width:${v.actual / kmax * 100}%;background:var(--${v.planned && v.actual > v.planned ? 'neg' : 'k'})"></span>
        ${v.planned ? html`<span style="position:absolute;top:-4px;bottom:-4px;left:${v.planned / kmax * 100}%;border-left:2px solid var(--ink)" title="Budgeted"></span>` : ''}</div>
      <span class="small right">${f.moneyShort(v.actual)}<span class="muted">${v.planned ? ' / ' + f.moneyShort(v.planned) : ''}</span></span></div>`)}</div>
    <div class="ev-legend" style="margin-top:12px"><span style="--c:var(--k)">Actual</span><span style="--c:var(--ink)">Budgeted (line)</span><span style="--c:var(--neg)">Over budget</span></div>`;
}

function leadsChart(d) {
  const days = d.results.by_day;
  if (!days.length) return html`<div class="ev-empty">No leads with this event's Lead Source yet.</div>`;
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
  const attention = d.steps.filter(s => s.status !== 'Done' && s.due && (s.due < d.today || (s.critical && s.due <= soon))).slice(0, 6);
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
      ${block('Plan timeline', openTab(d, 'plan', 'Plan'), timeline(d, true), 'span2')}
      ${block('Needs attention', '', attention.length ? attention.map(s => html`<div class="ev-row slim" data-act="editStep" data-arg="${s.id}">
          <span class="ev-when" style="color:var(--${s.due < d.today ? 'neg' : 'warn'})">${s.due < d.today ? 'Overdue' : day(s.due)}</span>
          <span class="ev-task">${s.title}</span><span class="ev-owner">${s.owner || 'Unassigned'}</span></div>`) : html`<div class="ev-empty">Nothing overdue and no critical task due this week.</div>`)}
    </div>
    <div class="ev-grid3">
      ${block('Lead funnel', openTab(d, 'results', 'Results & ROI'), has ? funnelBars(d) : html`<div class="ev-empty">Set the Lead Source on the Results tab.</div>`)}
      ${block('Target accounts', openTab(d, 'accounts', 'Accounts'), a.targets.length ? html`<div class="stack" style="gap:14px">${a.tiers.map(tr => html`<div class="stack" style="gap:6px">
          <div class="between small"><span class="medium">Tier ${tr.tier}</span><span class="muted">${tr.engaged} of ${tr.total} engaged</span></div>
          <div class="ev-split"><i style="width:${pct(tr.engaged, tr.total)}%;background:var(--k)"></i><i style="width:${pct(tr.known - tr.engaged, tr.total)}%;background:color-mix(in oklch, var(--k) 25%, var(--surface))"></i></div></div>`)}
          <span class="small muted">Influenced pipeline ${moneyOr(a.influenced)}</span></div>` : html`<div class="ev-empty">No target accounts yet.</div>`)}
      ${block('Budget vs actual', openTab(d, 'budget', 'Budget'), html`<div class="ev-big" style="margin-bottom:12px">${moneyOr(d.cost)}<span class="small muted" style="font-weight:400"> of ${moneyOr(d.planned)}</span></div>${budgetBars(d)}`)}
    </div>
    <div class="ev-grid3">
      ${block('Content', openTab(d, 'content', 'Content'), posts.length ? html`<div class="ev-thumbs">${posts.map(c => html`<a href="${c.url}" target="_blank" rel="noopener" class="ev-thumb" style="${c.image ? `background-image:url('${c.image}')` : `background:color-mix(in oklch, ${PLATFORM_COLOR[c.platform] || '#6e6e73'} 16%, var(--surface));color:${PLATFORM_COLOR[c.platform] || '#6e6e73'}`}">${c.image ? '' : c.platform}</a>`)}</div>
        <div class="small muted" style="margin-top:10px">${d.creatives.length} post${d.creatives.length === 1 ? '' : 's'} on ${[...new Set(d.creatives.map(c => c.platform))].join(', ')}</div>` : html`<div class="ev-empty">No posts yet.</div>`)}
      ${block('Promotion this week', openTab(d, 'promotion', 'Promotion'), thisWeek.length ? thisWeek.map(x => html`<div class="ev-row slim"><span class="ev-when">${day(x.day)}</span><span class="ev-task">${x.what}<span class="tiny muted" style="display:block">${x.channel}</span></span><span class="ev-owner" style="color:var(--${STATUS_TONE[x.status]})">${x.status}</span></div>`)
        : html`<div class="ev-empty">${d.promos.filter(x => x.status === 'Done').length} of ${d.promos.length} activities live. Nothing scheduled this week.</div>`)}
      ${block('Follow-up SLA', openTab(d, 'leads', 'Leads & follow-up'), slaBlock(d))}
    </div>`;
}

// ---- Plan: timeline, workload, then every task, filtered by phase, workstream or owner.
function plan(d, ctx) {
  const ui = ctx.ui(), phase = ui.phase || '', ws = ui.ws || '', owner = ui.owner || '';
  const steps = d.steps.filter(s => (!phase || s.phase === phase) && (!ws || s.workstream === ws) && (!owner || (s.owner || 'Unassigned') === owner));
  const workstreams = [...new Set(d.steps.map(s => s.workstream).filter(Boolean))];
  const maxLoad = Math.max(...d.load.map(r => r.open), 1);
  return html`
    <div class="ev-phases">${d.by_phase.map(x => html`<button class="ev-phase ${x.key === phase ? 'on' : ''}" data-act="phase" data-arg="${x.key === phase ? '' : x.key}">
      <span class="ev-phase-name">${x.label}</span><span class="ev-split" style="height:6px"><i style="width:${pct(x.done, x.total)}%;background:var(--${x.overdue ? 'neg' : 'k'})"></i></span>
      <span class="tiny muted">${x.done} of ${x.total} done${x.overdue ? html` · <span style="color:var(--neg)">${x.overdue} overdue</span>` : ''}</span></button>`)}</div>
    <div class="ev-grid2">
      ${block('Timeline', '', timeline(d), 'span2')}
      ${block('Owner workload · next 14 days', '', d.load.length ? html`<div class="stack" style="gap:12px">${d.load.map(r => html`<div class="stack" style="gap:4px;cursor:pointer" data-act="owner" data-arg="${r.owner === owner ? '' : r.owner}">
          <div class="between small"><span class="${r.owner === owner ? 'medium' : ''}">${r.owner}</span><span class="muted">${r.open} open${r.overdue ? html` · <span style="color:var(--neg)">${r.overdue} overdue</span>` : ''}</span></div>
          <div class="ev-split" style="height:8px"><i style="width:${r.overdue / maxLoad * 100}%;background:var(--neg)"></i><i style="width:${(r.open - r.overdue) / maxLoad * 100}%;background:${r.open > 6 ? 'var(--warn)' : 'var(--k)'}"></i></div></div>`)}</div>`
        : html`<div class="ev-empty">No open tasks in the next 14 days.</div>`)}
    </div>
    <section class="ev-sec">
      <div class="ev-h"><h2>Tasks <span class="ev-sub" style="font-weight:400">${steps.length} shown</span></h2>
        <span class="row ev-noprint" style="gap:10px;flex-wrap:wrap">
          <select class="input" data-change="planWs" style="font-size:12px;padding:5px 8px;width:auto"><option value="">All workstreams</option>${workstreams.map(w => html`<option ${w === ws ? 'selected' : ''}>${w}</option>`)}</select>
          ${owner ? html`<span class="btn xs" data-act="owner" data-arg="">${owner} ×</span>` : ''}
          <span class="btn xs primary" data-act="newStep">Add task</span></span></div>
      ${d.phases.filter(([k]) => !phase || k === phase).map(([k, label]) => { const list = steps.filter(s => s.phase === k); return list.length ? html`<div class="ev-group">${label}</div>${taskRows(d, list)}` : ''; })}
      ${steps.length ? '' : html`<div class="ev-empty">No tasks match.</div>`}
    </section>`;
}

// ---- Booth & logistics: the booth checklist from the plan, plus the booth's facts.
function booth(d) {
  const e = d.event, steps = d.steps.filter(s => BOOTH_WS.includes(s.workstream));
  const done = steps.filter(s => s.status === 'Done').length;
  return html`<div class="ev-tiles">
      <div class="ev-tile"><b>${e.booth || '—'}</b><span>Booth / stand</span></div>
      <div class="ev-tile"><b>${[e.venue, e.city].filter(Boolean).join(', ') || '—'}</b><span>Venue</span></div>
      <div class="ev-tile"><b>${done}<span class="muted" style="font-size:16px"> / ${steps.length}</span></b><span>Checklist done</span><div class="ev-split" style="height:6px;margin-top:8px"><i style="width:${pct(done, steps.length)}%;background:var(--k)"></i></div></div>
      <div class="ev-tile"><b>${e.meetings_held == null ? '—' : f.num(e.meetings_held)}<span class="muted" style="font-size:16px">${e.target_meetings ? ' / ' + f.num(e.target_meetings) : ''}</span></b><span>Meetings held</span></div>
    </div>
    ${block('Booth & logistics checklist', html`<span class="btn xs primary ev-noprint" data-act="newStep" data-ws="Booth & logistics">Add item</span>`, taskRows(d, steps, 'No booth or logistics tasks for this event type.'))}`;
}

// ---- Leads & follow-up: leads arriving, how fast they were contacted, and the tasks that make it happen.
function leadsTab(d) {
  const t = d.results.total, e = d.event, steps = d.steps.filter(s => LEAD_WS.includes(s.workstream));
  return html`<div class="ev-tiles">
      <div class="ev-tile"><b>${e.lead_sources.length ? f.num(t.leads) : '—'}</b><span>Leads${e.target_leads ? ' · target ' + f.num(e.target_leads) : ''}</span></div>
      <div class="ev-tile"><b>${f.num(t.qualified)}</b><span>Qualified leads${t.leads ? ' · ' + pct(t.qualified, t.leads) + '%' : ''}</span></div>
      <div class="ev-tile"><b>${f.num(d.results.speed.untouched)}</b><span>Leads with no first contact</span></div>
      <div class="ev-tile"><b>${e.visitors == null ? '—' : f.num(e.visitors)}</b><span>People captured at the booth</span></div>
    </div>
    <div class="ev-grid2">
      ${block('Leads by day', html`<span class="btn xs ev-noprint" data-act="pickSources">Lead Source${e.lead_sources.length ? ': ' + e.lead_sources.join(', ') : ''}</span>`, leadsChart(d), 'span2')}
      ${block('Follow-up SLA', info(TIPS.sla, { end: true }), slaBlock(d))}
    </div>
    ${block('Lead capture & follow-up tasks', '', taskRows(d, steps))}`;
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
        <span class="small" style="color:var(--${c.paid ? 'pos' : 'warn'})">${c.paid ? 'Paid' : 'Unpaid'}</span></div>`)}` : html`<div class="ev-empty">No costs yet: space, booth build, screen, travel, print, ads.</div>`)}
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
      : html`<div class="small muted">No activities yet: teaser post, invites, paid campaign, landing page, recap.</div>`}
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
      : html`<div class="small muted">Paste the link of each post made for this event. LinkedIn, Instagram and YouTube posts show here as the post itself.</div>`}
  </section>`;
}

function accounts(d) {
  const a = d.accounts;
  const tierColors = ['', 'var(--k)', 'color-mix(in oklch, var(--k) 70%, var(--surface))', 'color-mix(in oklch, var(--k) 45%, var(--surface))'];
  return html`<section class="ev-sec">
    <div class="ev-h"><h2>Target accounts</h2><span class="row ev-noprint" style="gap:10px">${info(TIPS.accounts)}<span class="btn xs ${a.targets.length ? '' : 'primary'}" data-act="editTargets">${a.targets.length ? 'Edit list' : 'Add target accounts'}</span></span></div>
    ${a.targets.length ? html`
      <div class="ev-stats">
        ${a.tiers.map(t => html`<div class="ev-stat"><b>${t.engaged}<span class="muted" style="font-size:16px"> / ${t.total}</span></b><span>Tier ${t.tier} accounts engaged</span></div>`)}
        <div class="ev-stat"><b>${moneyOr(a.influenced)}</b><span>Influenced pipeline · ${a.influenced_deals} opportunit${a.influenced_deals === 1 ? 'y' : 'ies'} ${info(TIPS.influenced)}</span></div>
      </div>
      ${a.tiers.map(t => { const list = a.targets.filter(x => x.tier === t.tier); return html`<div class="stack" style="gap:10px;margin-top:22px">
        <div class="between"><span class="medium">Tier ${t.tier}</span><span class="small muted">${t.engaged} engaged · ${t.known} in CRM · ${t.deals} with an opportunity</span></div>
        <div class="ev-split"><i style="width:${pct(t.engaged, t.total)}%;background:${tierColors[t.tier] || 'var(--k)'}"></i><i style="width:${pct(t.known - t.engaged, t.total)}%;background:color-mix(in oklch, var(--k) 22%, var(--surface))"></i></div>
        <div class="ev-chips">${list.map(x => html`<span class="ev-chip ${x.deal ? 'deal' : x.engaged ? 'engaged' : ''}" title="${x.deal ? 'Opportunity: ' + x.deal : x.engaged ? 'Engaged at this event' : x.known ? 'In CRM' : 'Not reached'}">${x.company}</span>`)}</div></div>`; })}
      <div class="ev-legend" style="margin-top:14px"><span style="--c:color-mix(in oklch, var(--pos) 40%, var(--surface))">Has an opportunity</span><span style="--c:color-mix(in oklch, var(--k) 40%, var(--surface))">Engaged at this event</span><span style="--c:var(--track)">Not reached</span></div>`
      : html`<div class="small muted">Paste the target account list (company, tier, domain) to see which accounts this event reached and the pipeline it influenced. Company names only.</div>`}
  </section>`;
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
    ${e.lessons ? block('Lessons learned', '', html`<p style="margin:0;max-width:75ch">${e.lessons}</p>`) : ''}`;
}

function room(d, ctx) {
  const ids = tabs(d).map(x => x[0]);
  const current = ids.includes(ctx.app.params.sec) ? ctx.app.params.sec : 'overview';
  const page = { overview: () => overview(d), plan: () => plan(d, ctx), promotion: () => promotion(d), content: () => content(d, ctx), booth: () => booth(d),
    accounts: () => accounts(d), leads: () => leadsTab(d), budget: () => budget(d), results: () => results(d) };
  return html`<div class="ev evw" data-kind="${d.event.kind}">${header(d, current)}
    <main class="ev-main">${ctx.ui().printing ? ['overview', 'results', 'budget', 'accounts'].map(id => page[id]()) : page[current]()}</main></div>`;
}

// ------------------------------------------------------------------------------- forms

const field = (label, name, value, extra = '') => html`<label class="field">${label}<input class="input" name="${name}" value="${value == null ? '' : value}" ${extra}></label>`;
const select = (label, name, options, value) => html`<label class="field">${label}<select class="input" name="${name}">${options.map(o => (Array.isArray(o) ? html`<option value="${o[0]}" ${o[0] === value ? 'selected' : ''}>${o[1]}</option>` : html`<option ${o === value ? 'selected' : ''}>${o}</option>`))}</select></label>`;
const buttons = (removeAct, id) => html`<div class="between" style="margin-top:4px">${id && removeAct ? html`<button type="button" class="btn danger" data-act="${removeAct}" data-arg="${id}">Delete</button>` : html`<span></span>`}
  <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div></div>`;
const owners = d => html`<datalist id="owners">${(d.team || []).map(n => html`<option value="${n}">`)}</datalist>`;
const check = (name, label, on) => html`<label class="row small" style="gap:8px"><input type="checkbox" name="${name}" ${on ? 'checked' : ''}> ${label}</label>`;

export default {
  uses: {},
  noTopbar: true,
  solo: app => !!app.params.id,  // an event opens as its own workspace, without Meridian's sidebar
  load: ctx => (ctx.app.params.id ? ctx.api.get('events/' + ctx.app.params.id) : ctx.api.get('events')),
  render(d, ctx) {
    if (!d.event) {
      d.events.forEach(e => { e.kindKey = (d.kinds.find(k => k[1] === e.kind) || ['booth'])[0]; });
      return home(d, ctx);
    }
    return room(d, ctx);
  },

  modal(m, ctx) {
    const d = ctx.app.data;
    if (m.kind === 'event') {
      const e = m.event || { kind: 'booth', decision: 'Go' };
      return html`<form class="modal" data-submit="saveEvent" style="width:660px">
        <span class="section">${m.event ? 'Edit event' : 'New event'}</span>
        ${m.event ? '' : html`<span class="small muted">The event gets the standard playbook for its type, with every due date set from its dates.</span>`}
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
      const s = m.step || { phase: 'promote', status: 'Not started', workstream: m.ws || '' };
      return html`<form class="modal" data-submit="saveStep">${owners(d)}
        <span class="section">${m.step ? 'Edit task' : 'Add task'}</span>
        ${field('Task', 'title', s.title, 'required data-autofocus')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${select('Phase', 'phase', d.phases, s.phase)}${field('Due date', 'due', s.due, 'type="date"')}${field('Owner', 'owner', s.owner, 'list="owners"')}${select('Status', 'status', d.statuses, s.status)}</div>
        <div class="grid" style="grid-template-columns:1fr 1fr">${field('Workstream', 'workstream', s.workstream)}${field('Done when', 'done_when', s.done_when)}</div>
        ${field('Note', 'note', s.note)}${check('critical', 'Critical task', s.critical)}
        ${buttons('removeStep', m.step && s.id)}</form>`;
    }
    if (m.kind === 'playbook') {
      const s = m.step || { phase: 'plan', offset_days: -14 }, kinds = (s.kinds || '').split(',');
      return html`<form class="modal" data-submit="savePlaybookStep">
        <span class="section">${m.step ? 'Edit playbook task' : 'Add playbook task'}</span>
        ${field('Task', 'title', s.title, 'required data-autofocus')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${select('Phase', 'phase', d.phases, s.phase)}${field('Days from the event (−21 = 3 weeks before)', 'offset_days', s.offset_days, 'type="number" step="1" required')}${field('Workstream', 'workstream', s.workstream)}${field('Default owner', 'owner', s.owner)}</div>
        ${field('Done when', 'done_when', s.done_when)}
        <div class="stack" style="gap:6px"><span class="small muted">Event types (none ticked = all types)</span><div class="row" style="gap:14px;flex-wrap:wrap">${d.kinds.map(([k, l]) => check('kind_' + k, l, kinds.includes(k)))}</div></div>
        ${check('critical', 'Critical task', s.critical)}
        ${buttons('removePlaybookStep', m.step && s.id)}</form>`;
    }
    if (m.kind === 'promo') {
      const p = m.promo || { channel: 'LinkedIn post', status: 'Not started' };
      return html`<form class="modal" data-submit="savePromo">${owners(d)}
        <span class="section">${m.promo ? 'Edit activity' : 'Add activity'}</span>
        ${field('Activity', 'what', p.what, 'required data-autofocus placeholder="e.g. Teaser post: meet us at booth 6H02"')}
        <div class="grid" style="grid-template-columns:1fr 1fr">${select('Channel', 'channel', d.channels, p.channel)}${field('Date', 'day', p.day, 'type="date"')}${field('Owner', 'owner', p.owner, 'list="owners"')}${select('Status', 'status', d.statuses, p.status)}</div>
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
      return html`<form class="modal" data-submit="saveCost">
        <span class="section">${m.cost ? 'Edit cost' : 'Add cost'}</span>
        ${field('Item', 'item', c.item, 'required data-autofocus placeholder="e.g. Booth space 6H02"')}
        <div class="grid" style="grid-template-columns:1fr 1fr 1fr">${select('Category', 'category', d.cost_kinds, c.category)}${field('Budgeted (₹)', 'planned', c.planned, 'type="number" min="0" step="any"')}${field('Actual (₹)', 'amount', c.amount, 'type="number" min="0" step="any"')}</div>
        ${check('paid', 'Paid', c.paid)}
        ${buttons('removeCost', m.cost && c.id)}</form>`;
    }
    if (m.kind === 'targets') {
      const text = d.accounts.targets.map(t => [t.company, t.tier, t.domain].filter(x => x != null && x !== '').join(', ')).join('\n');
      return html`<form class="modal" data-submit="saveTargets" style="width:600px">
        <span class="section">Target accounts</span>
        <span class="small muted">One company per line: company, tier (1–3), domain. Paste straight from a sheet. Only company names are kept; leave out people's names.</span>
        <textarea class="input" name="text" rows="14" data-autofocus placeholder="DBS Bank, 1, dbs.com&#10;HSBC, 1&#10;Maybank, 2">${text}</textarea>
        ${buttons(null, null)}</form>`;
    }
    if (m.kind === 'sources') {
      const mine = new Set(d.event.lead_sources), q = (ctx.ui().sourceQ || '').toLowerCase();
      const options = d.source_options.filter(o => mine.has(o.source) || !q || o.source.toLowerCase().includes(q));
      return html`<form class="modal" data-submit="saveSources" style="width:560px">
        <span class="section">Lead Source for ${d.event.name}</span>
        <span class="small muted">Tick the Zoho Lead Source values used for this event. A value can belong to one event only.</span>
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
    // the report prints the overview, results, accounts and promotion together, then the page returns to normal
    print(ctx) { ctx.ui().printing = true; ctx.render(); setTimeout(() => { window.print(); ctx.ui().printing = false; ctx.render(); }, 60); },
    newEvent: ctx => ctx.openModal({ kind: 'event' }),
    editEvent: ctx => ctx.openModal({ kind: 'event', event: ctx.app.data.event }),
    newStep: (ctx, d) => ctx.openModal({ kind: 'step', ws: d && d.ws }),
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
    stepStatus: (ctx, value, el) => ctx.save(() => ctx.api.post('events', { what: 'status', id: Number(el.dataset.id), data: { status: value } })),
  },

  inputs: {
    sourceQ(ctx, value) { ctx.ui().sourceQ = value; ctx.render(); },
  },

  submits: {
    async saveEvent(ctx, v) {
      const old = ctx.app.modal.event;
      ctx.app.modal = null;
      const r = await ctx.save(() => ctx.api.post('events', { what: 'event', id: old ? old.id : null, data: v }), old ? 'Saved.' : 'Event created with its playbook.');
      if (r && !old) ctx.go('events', { id: r.event_id });
    },
    saveStep: (ctx, v) => saveItem(ctx, 'step', 'step', { ...v, critical: !!v.critical }),
    savePlaybookStep: (ctx, v) => saveItem(ctx, 'playbook_step', 'step', { ...v, critical: !!v.critical }),
    savePromo: (ctx, v) => saveItem(ctx, 'promo', 'promo', v),
    saveCreative: (ctx, v) => saveItem(ctx, 'creative', 'creative', v, 'Post added.'),
    saveCost: (ctx, v) => saveItem(ctx, 'cost', 'cost', { ...v, paid: !!v.paid }),
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

function remove(ctx, what, id) {
  ctx.app.modal = null;
  return ctx.save(() => ctx.api.post('events', { what, id: Number(id) }), 'Deleted.');
}

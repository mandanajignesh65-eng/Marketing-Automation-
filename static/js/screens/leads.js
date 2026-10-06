import { html } from '../html.js';
import * as f from '../format.js';
import { sq, avatar, statusPill, menu, switcher, info } from '../ui.js';

const WIDE = 'minmax(0,1.5fr) minmax(0,1.5fr) minmax(0,1.3fr) minmax(0,1.05fr) minmax(0,1.05fr) 84px 56px minmax(0,1.2fr)';
const NARROW = 'minmax(0,1.4fr) minmax(0,1.4fr) minmax(0,1.2fr) minmax(0,1.1fr) 84px 56px';
const OWNER_BUTTONS = 6;  // owners with the most leads get a button each; the rest sit behind "More"
const TIPS = {
  leads: 'New people who gave us their details in this period. They came from marketing.',
  qualified: 'Leads that look like the customers we want: the right industry and a big enough company.',
  target: 'Leads whose company is in one of the industries we want most.',
  unknown: 'Leads where we do not know the company. We cannot tell if these are good or not. A company field on our forms would fix this.',
  filters: 'Click the name at the top of a column, like Channel or Status, to choose which leads to see. You can filter several columns at once. Each filter you turn on shows here as a blue tag. Click the × on a tag to remove it.',
  score: 'A number from 0 to 100 that says how well this lead matches the customers we want. A green bar means it qualifies.',
  age: 'How long ago this lead came in.',
};
const SCORES = [['', 'Any'], ['qualified', 'Qualified'], ['unqualified', 'Not qualified']];
let searchTimer;

const SCORE_NAMES = { qualified: 'Qualified', unqualified: 'Not qualified', high: '80 and above', zero: 'Score 0' };
const AGE_NAMES = { today: 'Today', week: 'Last 7 days', month: 'Last 30 days', older: 'Older than 30 days' };
const ACTIVITY_NAMES = { waiting: 'Waiting for owner', recent: 'Active in last 7 days', none: 'No activity yet' };

// Every column can be filtered from its own heading. Returns, per column: its label, what is picked, and the choices.
function columnFilters(d, ctx) {
  const { app } = ctx, ui = ctx.ui(), ch = app.params.channel || '', fc = d.list.facets, L = d.list;
  const n = v => html`<span class="faint" style="margin-left:auto;padding-left:14px">${f.num(v)}</span>`;
  const item = (arg, label, on, count, color) => ({ arg, on, color, label: count == null ? label : html`${label}${n(count)}` });
  const group = app.shell.groups.find(g => g.id === ch);
  const chName = ch ? (fc.channels.some(c => c.id === ch) || !group ? ctx.channel(ch).name : group.label) : '';
  const countOf = (list, id) => (list.find(x => x.id === id) || { n: 0 }).n;
  const activity = ui.needs ? 'waiting' : ui.activity || '';
  const named = (names, picked) => Object.entries(names).map(([arg, label]) => item(arg, label, picked === arg));
  return {
    segment: ['Company', ui.segment, [item('', 'All company types', !ui.segment), ...fc.kinds.filter(k => k.n).map(k => item(k.id, k.id, ui.segment === k.id, k.n))]],
    channel: ['Channel', chName, [item('', 'All channels', !ch), ...fc.channels.map(c => item(c.id, ctx.channel(c.id).name, ch === c.id, c.n, ctx.channel(c.id).color))]],
    owner: ['Owner', ui.owner, [item('', 'All owners', !ui.owner), ...fc.owners.map(o => item(o.id, o.id, ui.owner === o.id, o.n)),
      ...app.shell.owners.filter(o => !fc.owners.some(x => x.id === o)).map(o => item(o, o, ui.owner === o, 0))]],
    status: ['Status', ui.status, [item('', 'All statuses', !ui.status), ...app.shell.statuses.map(st => item(st, st, ui.status === st, countOf(fc.statuses, st)))]],
    score: ['Score', SCORE_NAMES[ui.score] || '', [item('', 'Any score', !ui.score), item('qualified', `Qualified (${L.threshold} or more)`, ui.score === 'qualified', L.period_qualified),
      item('unqualified', `Not qualified (under ${L.threshold})`, ui.score === 'unqualified', L.period_total - L.period_qualified), item('high', '80 and above', ui.score === 'high'), item('zero', 'Score 0 (company not known)', ui.score === 'zero')]],
    age: ['Age', AGE_NAMES[ui.age] || '', [item('', 'Any age', !ui.age), ...named(AGE_NAMES, ui.age)]],
    activity: ['Last activity', ACTIVITY_NAMES[activity] || '', [item('', 'Any activity', !activity), item('waiting', 'Waiting for an owner update', activity === 'waiting', L.waiting),
      item('recent', 'Active in the last 7 days', activity === 'recent'), item('none', 'No activity yet', activity === 'none')]],
  };
}

// The slim strip above the rows: how many leads are showing, and a removable tag for every filter that is on.
function filterStrip(d, ctx, cols) {
  const ui = ctx.ui(), L = d.list;
  const active = Object.entries(cols).filter(([, c]) => c[1]);
  return html`<div class="row" style="gap:10px;flex-wrap:wrap;padding:11px 16px;border-bottom:1px solid var(--line)">
    <span><span class="semi">${f.num(L.total)}</span><span class="muted">${active.length || ui.q ? ` of ${f.num(L.period_total)}` : ''} lead${L.total === 1 ? '' : 's'} · newest first</span></span>
    ${active.map(([id, [label, value]]) => html`<span class="chip on" data-act="filter-${id}" data-arg="" title="Remove this filter" style="display:inline-flex;gap:6px;align-items:center">${label}: ${value}<span>×</span></span>`)}
    ${ui.q ? html`<span class="chip on" data-act="clearSearch" title="Remove the search" style="display:inline-flex;gap:6px;align-items:center">Search: ${ui.q}<span>×</span></span>` : ''}
    ${active.length || ui.q ? html`<span class="link" data-act="clear">Clear all</span>` : ''}
    <span style="flex:1"></span>
    <span class="row small muted" style="gap:7px">Click a column name to filter${info(TIPS.filters, { end: true })}</span>
  </div>`;
}

// Four numbers for the period, before any filter is applied.
function summary(d) {
  const L = d.list, kinds = L.facets.kinds, total = L.period_total;
  const target = kinds.slice(0, L.targets).reduce((a, k) => a + k.n, 0), unknown = (kinds[kinds.length - 1] || { n: 0 }).n;
  const share = n => (total ? `${f.pct(n / total * 100)} of leads` : '');
  const box = (value, label, tip, sub, end) => html`<div class="card kpi" style="padding:14px 16px">
    <span class="kpi-v md" style="font-size:26px">${f.num(value)}</span><span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span>
    <span class="kpi-d faint" style="margin-top:2px">${sub}</span></div>`;
  return html`<div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
    ${box(total, 'Leads', TIPS.leads, L.period.short)}
    ${box(L.period_qualified, 'Qualified', TIPS.qualified, share(L.period_qualified))}
    ${box(target, 'From the industries we want', TIPS.target, share(target))}
    ${box(unknown, 'Company not known', TIPS.unknown, share(unknown), true)}
  </div>`;
}

function table(d, ctx) {
  const { list, lead } = d, ui = ctx.ui(), wide = !lead, { app } = ctx;
  const filtered = app.params.channel || ui.owner || ui.status || ui.score || ui.segment || ui.needs || ui.age || ui.activity || ui.q;
  const cols = columnFilters(d, ctx);
  // a column heading that opens its filter; the last columns open leftwards so the list stays inside the page
  const head = (id, tip, right) => { const [label, value, items] = cols[id]; return html`<div class="menu-wrap" data-menu-trigger style="min-width:0">
    <span class="colf ${value ? 'on' : ''}" data-act="menu" data-arg="f-${id}" title="Filter by ${label.toLowerCase()}"><span class="clip">${label}</span><span style="font-size:8px">▼</span></span>
    ${tip ? info(tip, { end: right }) : ''}${app.menu === 'f-' + id ? menu(items, 'filter-' + id, { right }) : ''}</div>`; };
  const heads = html`<div class="thead" style="gap:12px"><span>Name</span>${head('segment')}${head('channel')}${wide ? head('owner') : ''}${head('status')}
    ${head('score', TIPS.score, true)}${head('age', null, true)}${wide ? head('activity', null, true) : ''}</div>`;
  if (!list.rows.length) {
    return html`<div class="card" style="--cols:${wide ? WIDE : NARROW};--gap:12px">${filterStrip(d, ctx, cols)}${heads}
      <div class="stack" style="align-items:center;gap:10px;padding:36px 20px;text-align:center">
      <span class="title">No leads match these filters</span>
      <span class="small muted" style="max-width:260px">Try a wider date range or remove a filter.</span>
      ${filtered ? html`<span class="btn" data-act="clear">Clear all filters</span>` : ''}</div></div>`;
  }
  return html`<div class="card" style="--cols:${wide ? WIDE : NARROW};--gap:12px">
    ${filterStrip(d, ctx, cols)}
    <div>
    ${heads}
    ${list.rows.map((r, i) => { const c = ctx.channel(r.channel_id); return html`<div class="trow ${i ? '' : 'first'} ${lead && lead.id === r.id ? 'sel' : ''}" style="gap:12px;padding:9px 16px" data-act="open" data-arg="${r.id}">
      <div class="row" style="gap:10px;min-width:0">${avatar(r.initials)}<span class="medium clip">${r.name}</span></div>
      <div class="stack" style="min-width:0"><span class="clip ${r.company ? 'medium' : 'faint'}" title="${r.company || ''}">${r.company || 'Not known'}</span>
        <span class="small clip ${r.industry ? 'muted' : 'faint'}" title="${r.industry || ''}">${r.industry || 'Industry not known'}</span></div>
      <div class="stack" style="min-width:0"><div class="row" style="gap:7px;min-width:0">${sq(c.color)}<span class="clip">${c.name}</span></div>
        ${r.source ? html`<span class="small muted clip" style="padding-left:15px" title="${r.source}">${r.source}</span>` : ''}</div>
      ${wide ? html`<span class="clip">${r.owner || '—'}</span>` : ''}
      <div>${statusPill(r.status)}</div>
      <div class="row" style="gap:8px"><span class="medium" style="width:18px">${r.score}</span>
        <div style="width:32px;height:4px;border-radius:2px;background:var(--track)"><div style="width:${r.score}%;height:100%;border-radius:2px;background:var(--${r.qualified ? 'pos' : 'ink3'})"></div></div></div>
      <span style="color:var(--${r.age_tone})">${r.age}</span>
      ${wide ? html`<span class="small muted clip">${r.last}</span>` : ''}
    </div>`; })}
    <div class="between small faint" style="padding:10px 16px;border-top:1px solid var(--line)">
      <span>Showing ${f.num(list.rows.length)} of ${f.num(list.total)}</span>
      ${list.rows.length < list.total ? html`<span class="link" data-act="more">Show 50 more</span>` : ''}</div>
    </div>
  </div>`;
}

function detail(L, ctx) {
  const { app } = ctx;
  const tone = L.qualified ? 'pos' : 'ink3';
  const fit = L.groups.find(g => g.label === 'Fit') || { points: 0, max: 0 }, intent = L.groups.find(g => g.label === 'Intent') || { points: 0, max: 0 };
  const section = (title, right, content, pad = '24px 24px 0') => html`<div class="stack" style="padding:${pad};gap:12px">
    <div class="between"><span class="semi">${title}</span>${right ? html`<span class="small faint">${right}</span>` : ''}</div>${content}</div>`;
  return html`<aside class="detail" data-scroll="lead">
    <div style="padding:20px 24px 18px;display:flex;gap:14px;align-items:flex-start">
      ${avatar(L.initials, 44)}
      <div class="stack" style="flex:1;min-width:0;gap:2px">
        <div style="font-size:18px;font-weight:600;letter-spacing:-0.015em">${L.name}</div>
        <div class="muted">${[L.title, L.company].filter(Boolean).join(' · ')}</div>
        <div class="row" style="gap:8px;margin-top:8px;flex-wrap:wrap">${statusPill(L.status)}<span class="small muted">Owner <span class="ink">${L.owner || 'Unassigned'}</span></span></div>
      </div>
      <button class="round-btn" data-act="close" aria-label="Close lead">✕</button>
    </div>
    <div class="row" style="gap:8px;padding:0 24px 20px">
      ${L.zoho_url ? html`<a class="btn primary" href="${L.zoho_url}" target="_blank" rel="noopener" style="text-decoration:none">Open in Zoho CRM</a>`
        : html`<div class="btn primary" data-act="noZoho">Open in Zoho CRM</div>`}
      <div class="menu-wrap" data-menu-trigger><div class="btn" data-act="menu" data-arg="reassign">Reassign</div>
        ${app.menu === 'reassign' ? menu(app.shell.owners.map(o => ({ label: o, arg: o, on: o === L.owner })), 'reassign') : ''}</div>
    </div>

    <div class="inset stack" style="margin:0 24px;padding:18px;gap:12px">
      <div class="between" style="align-items:flex-end">
        <div class="row" style="align-items:baseline;gap:4px"><span style="font-size:44px;font-weight:600;letter-spacing:-0.035em;line-height:1">${L.score}</span><span class="faint" style="font-size:14px">/100</span></div>
        <div class="stack" style="align-items:flex-end;gap:2px"><span class="semi" style="color:var(--${tone})">${L.qualified ? 'Qualified' : 'Not qualified'}</span>
          <span class="small muted">Fit ${fit.points}/${fit.max} · Intent ${intent.points}/${intent.max}</span></div>
      </div>
      <div class="track"><div class="fill" style="width:${Math.min(100, L.score)}%;background:var(--${tone})"></div>
        <div class="mark" style="left:${L.threshold}%;top:-4px;bottom:-4px;background:var(--ink)"></div></div>
      <div class="tiny faint">Qualifies at ${L.threshold}</div>
    </div>

    ${section('Company', '', html`<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px 12px">
        ${L.company_facts.map(kv => html`<div class="stack" style="gap:2px;min-width:0"><span class="medium clip" style="font-size:15px">${kv.v}</span><span class="tiny muted">${kv.k}</span></div>`)}</div>
      <div class="tiny faint">${L.enriched}</div>`)}

    ${section(L.qualified ? 'Why it qualified' : 'Why it didn’t qualify', '', html`<div class="stack" style="gap:14px">${L.groups.map(g => html`<div class="stack" style="gap:10px">
      <div class="between tiny medium faint"><span>${g.label}</span><span>${g.points} / ${g.max}</span></div>
      ${g.items.map(c => html`<div style="display:grid;grid-template-columns:minmax(0,1fr) 40px 44px;gap:10px;align-items:center">
        <div class="stack" style="min-width:0"><span>${c.label}</span><span class="small muted">${c.why}</span></div>
        <div style="height:4px;border-radius:2px;background:var(--track)"><div style="width:${c.max ? c.points / c.max * 100 : 0}%;height:100%;border-radius:2px;background:var(--ink2)"></div></div>
        <span class="small right"><span class="medium">${c.points}</span><span class="faint">/${c.max}</span></span></div>`)}</div>`)}</div>`)}

    ${L.touches.length ? section('Attribution', '', html`<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">${L.touches.map(t => { const c = ctx.channel(t.channel_id); return html`
      <div class="stack" style="padding:12px;border-radius:10px;border:1px solid var(--line);gap:4px">
        <span class="tiny faint medium">${t.label}</span><div class="row" style="gap:7px">${sq(c.color)}<span class="medium">${c.name}</span></div>
        <span class="small muted pretty">${t.detail}</span><span class="tiny faint">${t.when}</span></div>`; })}</div>`) : ''}

    ${section('Timeline', `${L.timeline.length} ${L.timeline.length === 1 ? 'touch' : 'touches'}`, html`<div class="stack">${L.timeline.map((e, i) => html`
      <div style="display:grid;grid-template-columns:14px minmax(0,1fr) auto;gap:12px">
        <div class="stack" style="align-items:center"><div style="width:9px;height:9px;border-radius:50%;margin-top:4px;flex:none;${e.kind === 'touch' && e.channel_id
          ? `background:${ctx.channel(e.channel_id).color}` : `background:var(--surface);border:1.5px solid var(--${e.kind === 'reminder' ? 'warn' : 'ink2'})`}"></div>
          <div style="flex:1;width:1px;background:${i === L.timeline.length - 1 ? 'transparent' : 'var(--line)'};margin:3px 0"></div></div>
        <div class="stack" style="gap:1px;padding-bottom:14px;min-width:0"><span class="medium">${e.title}</span><span class="small muted pretty">${e.detail}</span></div>
        <span class="tiny faint nowrap" style="padding-top:1px">${e.when}</span></div>`)}</div>`)}

    ${section('Reminders to owner', 'Rule: no update after 3 and 7 days', L.reminders.length
      ? html`<div style="border:1px solid var(--line);border-radius:10px;overflow:hidden">${L.reminders.map((m, i) => html`
        <div style="display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:10px 12px;border-top:${i ? '1px solid var(--line2)' : 'none'}">
          <div class="stack" style="gap:1px"><span class="medium">${m.title}</span><span class="small muted">${m.detail}</span></div>
          <span class="small nowrap" style="color:var(--${m.tone})">${m.outcome}</span></div>`)}</div>`
      : html`<div class="small muted" style="padding:14px;border-radius:10px;border:1px dashed var(--line);text-align:center">No reminders needed. The owner has kept this lead up to date.</div>`, '12px 24px 28px')}
  </aside>`;
}

export default {
  uses: { range: true },
  bare: true,

  async load(ctx) {
    const ui = ctx.ui(), p = ctx.app.params;
    const [list, lead] = await Promise.all([
      ctx.api.get('leads', { ...ctx.rangeParams(), q: ui.q, channel: p.channel, owner: ui.owner, status: ui.status, score: ui.score, segment: ui.segment, age: ui.age, activity: ui.activity, needs_update: ui.needs, limit: ui.limit || 50 }),
      p.lead ? ctx.api.get('leads/' + encodeURIComponent(p.lead)).catch(() => null) : null,
    ]);
    return { list, lead };
  },

  render(d, ctx) {
    const { list, lead } = d, ui = ctx.ui();
    const scope = ui.needs ? 'waiting on an owner update' : ctx.app.range === 'month' ? 'this month' : 'in ' + list.period.short;
    return html`<div style="display:flex;flex:1;min-height:0">
      <div class="page ${ctx.app.loading ? 'stale' : ''}" style="flex:1;min-width:0;width:auto;padding:28px 28px 40px 32px">
        <div class="page-head" style="margin-bottom:0">
          <div class="stack" style="gap:6px"><div class="eyebrow">${ui.needs ? `${f.num(list.total)} ${scope}` : `${f.num(list.period_total)} ${scope} · ${f.num(list.period_qualified)} qualified`}</div><h1 class="h1">Leads</h1></div>
          <label class="search"><i></i><input id="lead-search" type="search" placeholder="Search name, company or lead source" value="${ui.q || ''}" data-input="search" autocomplete="off"></label>
        </div>
        ${summary(d)}
        ${table(d, ctx)}
      </div>
      ${lead ? detail(lead, ctx) : ''}
    </div>`;
  },

  actions: {
    open: (ctx, d) => ctx.go('leads', { ...ctx.app.params, lead: d.arg }),
    close: ctx => ctx.go('leads', { channel: ctx.app.params.channel }),
    'filter-channel'(ctx, d) { ctx.app.menu = null; ctx.go('leads', { ...ctx.app.params, channel: d.arg }); },
    'filter-owner': (ctx, d) => setFilter(ctx, { owner: d.arg }),
    'filter-status': (ctx, d) => setFilter(ctx, { status: d.arg }),
    'filter-score': (ctx, d) => setFilter(ctx, { score: d.arg }),
    'filter-segment': (ctx, d) => setFilter(ctx, { segment: d.arg }),
    'filter-age': (ctx, d) => setFilter(ctx, { age: d.arg }),
    // "waiting for owner" is the older needs-update filter, which looks across all dates; the others stay inside the period
    'filter-activity': (ctx, d) => setFilter(ctx, { needs: d.arg === 'waiting', activity: d.arg === 'waiting' ? '' : d.arg }),
    more(ctx) { ctx.ui().limit = (ctx.ui().limit || 50) + 50; ctx.reload(); },
    clearSearch(ctx) { ctx.ui().q = ''; setFilter(ctx, {}); },
    clear(ctx) {
      ctx.app.ui.leads = {};
      ctx.go('leads', { lead: ctx.app.params.lead });
    },
    noZoho: ctx => ctx.toast('This lead has no Zoho CRM record linked yet. Sample leads are not in Zoho.'),
    async reassign(ctx, d) {
      ctx.app.menu = null;
      await ctx.save(() => ctx.api.patch('leads/' + ctx.app.params.lead, { owner: d.arg }), 'Reassigned to ' + d.arg + '. Zoho CRM is not updated from here.');
    },
  },

  inputs: {
    search(ctx, value) {
      ctx.ui().q = value;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => { ctx.ui().limit = 50; ctx.reload(); }, 250);
    },
  },
};

function setFilter(ctx, change) {
  Object.assign(ctx.ui(), change, { limit: 50 });
  ctx.app.menu = null;
  ctx.reload();
}

import { html } from '../html.js';
import * as f from '../format.js';
import { deltaLine, avatar, sq, switcher } from '../ui.js';

// Where each channel row opens. "No channel" has no list of its own; its note points to Settings instead.
const TO = { paid: '#/paid', outbound: '#/outbound', organic: '#/web', events: '#/leads?channel=events' };
const MAX_PEOPLE = 6;
const initials = name => name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
const money = (key, v) => (key === 'spend' || key === 'pipeline' ? f.moneyShort(v) : f.num(v));
// a channel group takes the colour of its first channel, so the graphs match the colours used elsewhere
const groupColor = (ctx, key) => (ctx.app.shell.channels.find(c => c.grp === key) || { color: 'var(--ink3)' }).color;

// Leads per day, every channel stacked, or only the channels of the group picked with the buttons above it.
function daily(d, ctx, only) {
  const order = [...ctx.app.shell.channels, ctx.channel('unmapped')].filter(c => !only || c.grp === only);
  const count = x => (only ? x.segs.filter(g => ctx.channel(g.id).grp === only).reduce((t, g) => t + g.n, 0) : x.total);
  const ax = f.axis(Math.max(...d.chart.map(count), 1));
  const every = d.chart.length <= 10;
  const label = (x, i) => (x.partial ? 'Today' : i === 0 ? `${x.day} ${x.month}` : every || x.day % 7 === 0 ? x.day : '');
  return html`<div class="stack" style="flex:1;min-width:0;gap:6px">
    <div style="position:relative;height:190px">
      ${ax.ticks.map(t => html`<div class="row" style="position:absolute;left:0;right:0;bottom:${t / ax.max * 100}%;gap:8px">
        <span class="micro faint right" style="width:18px;transform:translateY(50%)">${t}</span><div style="flex:1;height:1px;background:var(--grid)"></div></div>`)}
      <div style="position:absolute;left:26px;right:0;top:0;bottom:0;display:flex;align-items:flex-end;gap:4px">
        ${d.chart.map(x => html`<div title="${x.day} ${x.month} · ${count(x)} leads${x.partial ? ' (so far)' : ''}"
          style="flex:1;height:${count(x) / ax.max * 100}%;display:flex;flex-direction:column-reverse;gap:1px;opacity:${x.partial ? 0.45 : 1};border-radius:3px 3px 1px 1px;overflow:hidden">
          ${order.map(c => { const s = x.segs.find(g => g.id === c.id); return s ? html`<div style="height:${s.n / count(x) * 100}%;background:${c.color};flex:none"></div>` : ''; })}
        </div>`)}
      </div>
    </div>
    <div style="display:flex;gap:4px;margin-left:26px">${d.chart.map((x, i) => html`<div class="micro faint nowrap" style="flex:1;text-align:center">${label(x, i)}</div>`)}</div>
  </div>`;
}

function legend(d, ctx, only) {
  const by = {};
  d.chart.forEach(x => x.segs.filter(s => !only || ctx.channel(s.id).grp === only).forEach(s => { by[s.id] = (by[s.id] || 0) + s.n; }));
  const rows = Object.entries(by).map(([id, n]) => ({ c: ctx.channel(id), id, n })).sort((a, b) => b.n - a.n);
  const all = rows.reduce((t, r) => t + r.n, 0);
  return html`<div class="stack" style="width:190px;flex:none;gap:5px">
    <div class="between tiny faint medium" style="margin-bottom:2px"><span>By channel</span><span>${f.num(all)}</span></div>
    ${rows.map(r => html`<div class="row small" style="gap:8px;font-size:12px">${sq(r.c.color)}<span style="flex:1" class="nowrap clip">${r.c.name}</span>
      <span class="medium">${f.num(r.n)}</span><span class="faint" style="width:36px;text-align:right">${all ? Math.round(r.n / all * 100) + '%' : ''}</span></div>`)}
    ${rows.length ? '' : html`<span class="small muted">No leads in this period yet.</span>`}
  </div>`;
}

// Each channel's path from lead to won deal, as bars on one scale so channels can be compared.
function funnel(d, ctx) {
  const rows = d.channels.filter(r => r.leads || r.deals);
  const top = Math.max(...rows.map(r => r.leads), 1);
  const steps = [['leads', 'Leads'], ['qualified', 'Qualified'], ['deals', 'Deals started'], ['won', 'Deals won']];
  return html`<div class="card pad stack" style="gap:14px">
    <div class="baseline"><span class="title">From lead to won deal</span><span class="small muted">${d.range_name}</span></div>
    ${rows.length ? html`<div class="grid" style="grid-template-columns:repeat(${rows.length},minmax(0,1fr));gap:28px">${rows.map(r => html`<div class="stack" style="gap:5px">
      <span class="row small medium" style="gap:8px">${sq(groupColor(ctx, r.key))}${r.name}</span>
      ${steps.map(([key, label], i) => html`<div style="display:grid;grid-template-columns:92px minmax(0,1fr) 44px;gap:10px;align-items:center">
        <span class="tiny muted">${label}</span>
        <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${r[key] / top * 100}%;background:${groupColor(ctx, r.key)};opacity:${1 - i * 0.2}"></div></div>
        <span class="tiny medium right">${f.num(r[key])}</span></div>`)}
    </div>`)}</div>` : html`<div class="small muted">No leads or deals in this period.</div>`}
  </div>`;
}

export default {
  uses: { range: true, compare: true },
  load: ctx => ctx.api.get('overview', ctx.rangeParams()),

  render(d, ctx) {
    const show = ctx.app.compare;
    const k = d.kpis, t = d.team, mt = d.month_targets;
    const kpis = [
      ['Leads', f.num(d.leads.value), deltaLine(d.leads, { show, short: true }), 'leads'],
      ['Qualified leads', f.num(k.qualified.value), deltaLine(k.qualified, { show, short: true }), 'quality'],
      ['Deals started', f.num(d.deals.value), deltaLine(d.deals, { show, short: true }), null],
      ['Deals won', f.num(d.won.value), deltaLine(d.won, { show, short: true }), null],
      ['Value of new deals', k.pipeline.value ? f.moneyShort(k.pipeline.value) : '—', deltaLine(k.pipeline, { show, short: true, fmt: f.moneyShort }), null],
    ];
    const cols = 'minmax(0,1.6fr) 62px 70px 70px 64px 58px 84px 72px 96px';
    const dash = html`<span class="faint">—</span>`;
    const n = v => (v ? f.num(v) : dash);
    const change = (cur, prev) => (show && prev ? (ch => html`<span class="tiny" style="color:${f.tone(ch)}">${f.arrowShort(ch)}</span>`)((cur - prev) / prev * 100) : '');
    const mark = r => (r.rank === 'best' ? html`<span class="pill sm" style="color:var(--pos);align-self:flex-start"><span class="dot" style="background:var(--pos)"></span>Best</span>`
      : r.rank === 'weakest' ? html`<span class="pill sm" style="color:var(--neg);align-self:flex-start"><span class="dot" style="background:var(--neg)"></span>Weakest</span>` : '');
    const cost = r => (r.spend_flag === 'spent_none' ? html`<span class="small" style="color:var(--neg)">spent, none qualified</span>`
      : r.spend_flag === 'no_spend' ? html`<span class="tiny faint">no spend recorded</span>` : r.cpql ? f.moneyShort(r.cpql) : dash);
    const people = t.people.slice(0, MAX_PEOPLE);
    const present = d.channels.filter(r => r.key !== 'none' && r.leads);
    const only = present.some(r => r.key === ctx.ui().only) ? ctx.ui().only : null;
    const topLeads = Math.max(...d.channels.map(r => r.leads), 1);

    return html`
    <div class="page-head"><div class="stack" style="gap:6px"><div class="eyebrow">${d.date_line}</div><h1 class="h1">Overview</h1></div></div>

    <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">
      ${kpis.map(([label, value, delta, to]) => html`<a class="card kpi" ${to ? html`href="#/${to}"` : ''} style="color:inherit;text-decoration:none"><div class="kpi-v">${value}</div>
        <div class="eyebrow">${label}</div>${delta}</a>`)}
    </div>

    <div class="grid start" style="grid-template-columns:minmax(0,1fr) 336px">
      <div class="card stack" style="padding:18px 20px 16px;gap:16px">
        <div class="baseline" style="gap:16px;flex-wrap:wrap"><span class="title">${only ? `Leads per day · ${present.find(r => r.key === only).name}` : 'Leads per day'}</span>
          ${present.length > 1 ? switcher([{ arg: '', label: 'All channels', on: !only }, ...present.map(r => ({ arg: r.key, label: r.name, color: groupColor(ctx, r.key), on: only === r.key }))], 'only') : ''}</div>
        <div style="display:flex;gap:28px">${daily(d, ctx, only)}${legend(d, ctx, only)}</div>
      </div>

      <div class="card pad stack" style="gap:10px">
        <div class="baseline"><span class="title">On track</span><a class="link" href="#/targets" style="text-decoration:none">All targets</a></div>
        <div class="small faint" style="margin-top:-6px">${mt.month} so far</div>
        ${mt.rows.length ? mt.rows.map(r => html`<div class="stack" style="gap:4px">
          <div class="between small"><span class="medium">${r.label}</span>
            <span class="muted nowrap">${money(r.key, r.actual)} of ${money(r.key, r.target)}${r.status ? html` · <span style="color:var(--${r.tone})">${r.status}</span>` : ''}</span></div>
          <div class="track"><div class="fill" style="width:${r.pct}%;background:var(--${r.tone || 'ink2'})"></div><div class="mark" style="left:${Math.min(mt.pace_pct, 100)}%" title="Where it should be by today"></div></div>
        </div>`) : html`<div class="small muted">No monthly targets yet · <a class="link" href="#/settings" style="text-decoration:none">Set them in Settings</a></div>`}
        <div class="small faint" style="padding-top:10px;border-top:1px solid var(--line2)">This week</div>
        ${people.map(p => html`<div class="between" style="gap:8px">
          <span class="row" style="gap:9px;min-width:0">${avatar(initials(p.name), 22)}<span class="medium small clip">${p.name}</span></span>
          <span class="small muted nowrap">${p.targets ? html`<span class="ink medium">${p.on_track}</span> of ${p.targets} on track` : 'No weekly targets'}</span></div>`)}
        ${t.people.length > MAX_PEOPLE ? html`<a class="link small" href="#/targets" style="text-decoration:none">See all ${t.people.length} on Targets</a>` : ''}
        ${t.people.length ? '' : html`<div class="small muted">Nobody has targets yet.</div>`}
        ${t.blockers ? html`<a href="#/targets?view=blockers" class="small" style="color:var(--warn);text-decoration:none">${t.blockers} open blocker${t.blockers === 1 ? '' : 's'} →</a>` : ''}
      </div>
    </div>

    <div class="grid start" style="grid-template-columns:minmax(0,1fr) 336px">
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 12px"><span class="title">Channels</span><span class="small muted">${d.range_name}</span></div>
        <div class="thead right" style="border-top:1px solid var(--line)"><span></span><span>Leads</span><span>Qualified</span><span>Qualified %</span><span>Deals started</span><span>Deals won</span><span>Value of new deals</span><span>Spend</span><span>Cost per qualified lead</span></div>
        ${d.channels.map(r => html`<a class="trow right" ${TO[r.key] ? html`href="${TO[r.key]}"` : ''} style="color:inherit;text-decoration:none">
          <span class="stack" style="gap:4px;text-align:left;min-width:0;align-items:stretch">
            <span class="row" style="gap:8px;min-width:0">${sq(groupColor(ctx, r.key))}<span class="medium nowrap">${r.name}</span></span>
            <span class="track" style="height:6px;border-radius:3px;display:block" title="Leads, with the qualified part darker"><span class="fill" style="display:block;width:${r.leads / topLeads * 100}%;background:color-mix(in oklch, ${groupColor(ctx, r.key)} 35%, var(--surface));position:relative">
              <span style="position:absolute;left:0;top:0;bottom:0;width:${r.leads ? r.qualified / r.leads * 100 : 0}%;background:${groupColor(ctx, r.key)};border-radius:3px"></span></span></span>${mark(r)}</span>
          <span class="stack" style="gap:0"><span class="medium">${n(r.leads)}</span>${change(r.leads, r.prev.leads)}</span>
          <span class="stack" style="gap:0"><span>${n(r.qualified)}</span>${change(r.qualified, r.prev.qualified)}</span>
          <span>${r.qualified_pct == null ? dash : f.pct(r.qualified_pct)}</span>
          <span>${n(r.deals)}</span><span>${n(r.won)}</span>
          <span>${r.pipeline ? f.moneyShort(r.pipeline) : dash}</span>
          <span>${r.spend ? f.moneyShort(r.spend) : dash}</span><span>${cost(r)}</span></a>
          ${r.note ? html`<div class="small" style="padding:0 16px 12px;color:var(--warn)">${r.note} <a class="link" href="#/settings" style="text-decoration:none">Give them a channel in Settings</a></div>` : ''}`)}
      </div>

      <div class="card stack" style="padding:16px 20px 8px">
        <div class="baseline" style="margin-bottom:4px"><span class="title">Needs attention</span><a class="link" href="#/alerts" style="text-decoration:none">All alerts</a></div>
        ${d.alerts.length ? d.alerts.map((a, i) => html`<div style="display:flex;gap:12px;padding:9px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
          <span class="dot" style="width:7px;height:7px;background:var(--${a.tone});margin-top:6px"></span>
          <div class="between" style="flex:1;min-width:0;gap:12px"><span class="medium small clip" title="${a.detail}">${a.title}</span><span class="tiny faint nowrap">${a.when}</span></div></div>`)
          : html`<div class="small muted" style="padding:8px 0 12px">Nothing needs attention.</div>`}
      </div>
    </div>

    ${funnel(d, ctx)}`;
  },

  actions: {
    only(ctx, d) { ctx.ui().only = d.arg || null; ctx.render(); },
  },
};

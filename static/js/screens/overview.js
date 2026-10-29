import { html } from '../html.js';
import * as f from '../format.js';
import { deltaLine, avatar } from '../ui.js';

// Where each channel row opens. "No channel" has no list of its own; its note points to Settings instead.
const TO = { paid: '#/paid', outbound: '#/outbound', organic: '#/web', events: '#/leads?channel=events' };
const MAX_PEOPLE = 6;   // the right column has to fit a 1366x768 screen
const initials = name => name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
const money = (key, v) => (key === 'spend' || key === 'pipeline' ? f.moneyShort(v) : f.num(v));

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
    const mark = r => (r.rank === 'best' ? html`<span class="pill sm" style="color:var(--pos)"><span class="dot" style="background:var(--pos)"></span>Best</span>`
      : r.rank === 'weakest' ? html`<span class="pill sm" style="color:var(--neg)"><span class="dot" style="background:var(--neg)"></span>Weakest</span>` : '');
    const cost = r => (r.spend_flag === 'spent_none' ? html`<span class="small" style="color:var(--neg)">spent, none qualified</span>`
      : r.spend_flag === 'no_spend' ? html`<span class="tiny faint">no spend recorded</span>` : r.cpql ? f.moneyShort(r.cpql) : dash);
    const people = t.people.slice(0, MAX_PEOPLE);

    return html`
    <div class="page-head"><div class="stack" style="gap:6px"><div class="eyebrow">${d.date_line}</div><h1 class="h1">Overview</h1></div></div>

    <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">
      ${kpis.map(([label, value, delta, to]) => html`<a class="card kpi" ${to ? html`href="#/${to}"` : ''} style="color:inherit;text-decoration:none"><div class="kpi-v">${value}</div>
        <div class="eyebrow">${label}</div>${delta}</a>`)}
    </div>

    <div class="grid start" style="grid-template-columns:minmax(0,1fr) 336px">
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 12px"><span class="title">Channels</span><span class="small muted">${d.range_name}</span></div>
        <div class="thead right" style="border-top:1px solid var(--line)"><span></span><span>Leads</span><span>Qualified</span><span>Qualified %</span><span>Deals started</span><span>Deals won</span><span>Value of new deals</span><span>Spend</span><span>Cost per qualified lead</span></div>
        ${d.channels.map(r => html`<a class="trow right" ${TO[r.key] ? html`href="${TO[r.key]}"` : ''} style="color:inherit;text-decoration:none">
          <span class="stack" style="gap:3px;text-align:left;min-width:0;align-items:flex-start"><span class="medium clip">${r.name}</span>${mark(r)}</span>
          <span class="stack" style="gap:0"><span class="medium">${n(r.leads)}</span>${change(r.leads, r.prev.leads)}</span>
          <span class="stack" style="gap:0"><span>${n(r.qualified)}</span>${change(r.qualified, r.prev.qualified)}</span>
          <span>${r.qualified_pct == null ? dash : f.pct(r.qualified_pct)}</span>
          <span>${n(r.deals)}</span><span>${n(r.won)}</span>
          <span>${r.pipeline ? f.moneyShort(r.pipeline) : dash}</span>
          <span>${r.spend ? f.moneyShort(r.spend) : dash}</span><span>${cost(r)}</span></a>
          ${r.note ? html`<div class="small" style="padding:0 16px 12px;color:var(--warn)">${r.note} <a class="link" href="#/settings" style="text-decoration:none">Give them a channel in Settings</a></div>` : ''}`)}
      </div>

      <div class="stack" style="gap:16px">
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

        <div class="card stack" style="padding:16px 20px 8px">
          <div class="baseline" style="margin-bottom:4px"><span class="title">Needs attention</span><a class="link" href="#/alerts" style="text-decoration:none">All alerts</a></div>
          ${d.alerts.length ? d.alerts.map((a, i) => html`<div style="display:flex;gap:12px;padding:9px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
            <span class="dot" style="width:7px;height:7px;background:var(--${a.tone});margin-top:6px"></span>
            <div class="between" style="flex:1;min-width:0;gap:12px"><span class="medium small clip" title="${a.detail}">${a.title}</span><span class="tiny faint nowrap">${a.when}</span></div></div>`)
            : html`<div class="small muted" style="padding:8px 0 12px">Nothing needs attention.</div>`}
        </div>
      </div>
    </div>`;
  },
};

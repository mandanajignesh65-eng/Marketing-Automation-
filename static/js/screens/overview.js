import { html } from '../html.js';
import * as f from '../format.js';
import { sq, deltaLine, info, switcher, avatar } from '../ui.js';

const TIPS = {
  leads: 'A lead is a person who gave us their details. These three numbers count new leads today, this week and this month, from every channel.',
  visits: 'How many times people opened our website. Counted by Google Analytics.',
  qualified: 'Leads that look like the customers we want. Meridian gives each lead a score, and the ones above the pass mark count here.',
  replies: 'How many people wrote back to our LinkedIn messages and our emails.',
  deals: 'How many leads turned into a real sales talk. The money under it is what those deals could be worth.',
  chart: 'How many new leads we got each day. Use the buttons to choose what the chart shows. "All together" stacks every channel, one colour each. Click a channel name to see only that channel.',
  team: 'One row for each person. The bar shows how far along their targets are. The small line is where they should be by today. Past the line means on track.',
  journey: 'The steps from a stranger to a customer. Each box shows how many people reached that step in this period, and what share made it from the step before.',
  outreach: 'People we wrote to first. For LinkedIn: requests we sent, how many accepted, how many replied. For email: sent, opened, replied.',
  alerts: 'Things that dropped or fell below the benchmark. The newest ones are on top.',
};
const share = (a, b) => (!b ? '—' : a ? f.pct(a / b * 100) : '0%');

// only: a channel id to show by itself, or null for every channel stacked.
function chart(d, ctx, only) {
  const order = [...ctx.app.shell.channels, ctx.channel('unmapped')].filter(c => !only || c.id === only);
  const count = x => (only ? (x.segs.find(g => g.id === only) || { n: 0 }).n : x.total);
  const ax = f.axis(Math.max(...d.chart.map(count), 1));
  const every = d.chart.length <= 10;
  const label = (x, i) => (x.partial ? 'Today' : i === 0 ? `${x.day} ${x.month}` : every || x.day % 7 === 0 ? x.day : '');
  return html`<div class="stack" style="flex:1;min-width:0;gap:6px">
    <div style="position:relative;height:216px">
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

function legend(d, ctx) {
  const rows = Object.entries(d.by_channel).map(([id, n]) => ({ c: ctx.channel(id), id, n })).sort((x, y) => y.n - x.n);
  const all = rows.reduce((t, r) => t + r.n, 0);
  return html`<div class="stack" style="width:210px;flex:none;gap:5px">
    <div class="between tiny faint medium" style="margin-bottom:2px"><span>Where they came from</span><span>${f.num(all)}</span></div>
    ${rows.map(r => html`<div class="row small ${r.id === 'unmapped' ? '' : 'menu-item'}" style="gap:8px;padding:1px 4px;margin:0 -4px;font-size:12px" ${r.id === 'unmapped' ? '' : html`data-act="openChannel" data-arg="${r.id}"`}>
      ${sq(r.c.color)}<span style="flex:1" class="nowrap">${r.id === 'unmapped' ? 'Channel not known' : r.c.name}</span><span class="medium">${f.num(r.n)}</span><span class="faint" style="width:44px;text-align:right">${all ? Math.round(r.n / all * 100) + '%' : ''}</span></div>`)}
    ${rows.length ? '' : html`<span class="small muted">No leads in this period yet.</span>`}
  </div>`;
}

export default {
  uses: { range: true, compare: true },
  load: ctx => ctx.api.get('overview', ctx.rangeParams()),

  render(d, ctx) {
    const show = ctx.app.compare;
    const k = d.kpis, j = d.journey, o = d.outreach, t = d.team;
    const kpis = [
      ['Website visits', f.big(d.visits.value), deltaLine(d.visits, { show }), TIPS.visits, 'web'],
      ['Qualified leads', f.num(k.qualified.value), deltaLine(k.qualified, { show }), TIPS.qualified, 'quality'],
      ['Outreach replies', f.num(d.replies.value), deltaLine(d.replies, { show }), TIPS.replies, 'outbound'],
      ['Deals started', f.num(d.deals.value), html`<span class="kpi-d faint">${k.pipeline.value ? f.moneyShort(k.pipeline.value) + ' possible value' : 'No value entered yet'}</span>`, TIPS.deals, 'funnel'],
    ];
    // The daily chart shows every channel stacked, or just the one picked with the buttons above it.
    const present = Object.keys(d.by_channel).filter(id => id !== 'unmapped').map(id => ctx.channel(id)).sort((a, b) => d.by_channel[b.id] - d.by_channel[a.id]);
    const only = present.some(c => c.id === ctx.ui().only) ? ctx.ui().only : null;
    const steps = [
      ['Website visits', j.visits, ''],
      ['Leads', j.leads, j.visits ? `${share(j.web_leads, j.visits)} of visits became a lead` : ''],
      ['Qualified', j.qualified, j.leads ? `${share(j.qualified, j.leads)} of leads` : ''],
      ['Deals started', j.deals, j.leads ? `${share(j.deals, j.leads)} of leads` : ''],
      ['Deals won', j.won, j.deals ? `${share(j.won, j.deals)} of deals` : ''],
    ];
    const line = (label, parts, used) => html`<div class="row small" style="gap:10px;flex-wrap:wrap"><span class="medium" style="width:74px">${label}</span>
      ${used ? parts.map(([n, word], i) => html`${i ? html`<span class="faint">→</span>` : ''}<span class="nowrap"><span class="ink medium">${f.num(n)}</span> <span class="muted">${word}</span></span>`) : html`<span class="muted">Nothing sent in this period</span>`}</div>`;
    return html`
    <div class="page-head" style="gap:24px">
      <div class="stack" style="gap:6px;max-width:720px">
        <div class="eyebrow">${d.date_line}</div>
        <h1 class="h1">Overview</h1>
        <p class="muted pretty" style="margin-top:2px;font-size:15px;line-height:1.45">${d.summary.map(s => (s.tone ? html`<span style="color:var(--${s.tone})">${s.t}</span>` : s.t))}</p>
      </div>
      <div class="small faint nowrap">${d.day_of}</div>
    </div>

    <div class="grid" style="grid-template-columns:minmax(0,2.3fr) repeat(4,minmax(0,1fr))">
      <div class="card" style="padding:18px 20px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr))">
        ${d.lead_kpis.map((x, i) => html`<div class="stack" style="gap:3px;padding:0 10px;border-left:${i ? '1px solid var(--line)' : 'none'}">
          <div class="kpi-v" style="font-size:34px">${f.num(x.value)}</div><div class="row eyebrow nowrap" style="gap:7px">${x.label}${i ? '' : info(TIPS.leads)}</div>${deltaLine(x, { show, short: true })}</div>`)}
      </div>
      ${kpis.map(([label, value, delta, tip, to], i) => html`<div class="card kpi"><div class="kpi-v">${value}</div>
        <div class="row eyebrow" style="gap:7px"><a href="#/${to}" style="color:inherit;text-decoration:none" title="Open the full page">${label}</a>${info(tip, { end: i > 1 })}</div>${delta}</div>`)}
    </div>

    <div class="grid" style="grid-template-columns:minmax(0,1fr) 336px">
      <div class="card stack" style="padding:18px 20px 16px;gap:16px">
        <div class="baseline" style="gap:16px;flex-wrap:wrap"><div class="row" style="gap:8px"><span class="title">${only ? `Leads from ${ctx.channel(only).name}` : 'New leads each day'}</span>${info(TIPS.chart)}</div>
          ${present.length > 1 ? switcher([{ arg: '', label: 'All together', on: !only }, ...present.map(c => ({ arg: c.id, label: c.name, color: c.color, on: only === c.id }))], 'only')
            : html`<div class="small faint">${d.chart_label}</div>`}</div>
        ${present.length > 1 ? html`<div class="small faint" style="margin-top:-10px">${d.chart_label}</div>` : ''}
        <div style="display:flex;gap:28px">${chart(d, ctx, only)}${legend(d, ctx)}</div>
      </div>
      <div class="card pad stack" style="gap:14px">
        <div class="baseline"><div class="row" style="gap:8px"><span class="title">Team targets</span>${info(TIPS.team, { end: true })}</div><a class="link" href="#/targets" style="text-decoration:none">All targets</a></div>
        <div class="small faint" style="margin-top:-8px">This week · ${t.week}${t.demo ? ' · example data' : ''}</div>
        ${t.people.map(p => html`<div class="stack" style="gap:6px">
          <div class="between" style="gap:8px"><span class="row" style="gap:9px;min-width:0">${avatar(p.name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase(), 24)}<span class="medium clip">${p.name}</span></span>
            <span class="small muted nowrap">${p.targets ? html`<span class="ink medium">${p.on_track}</span> of ${p.targets} on track` : 'No targets yet'}</span></div>
          ${p.targets ? html`<div class="track"><div class="fill" style="width:${p.pct}%;background:var(--${p.on_track === p.targets ? 'pos' : p.on_track ? 'warn' : 'neg'})"></div><div class="mark" style="left:${p.pace}%" title="Where it should be by today"></div></div>
          <div class="tiny muted">${p.today_all ? `Today: ${p.today_done} of ${p.today_all} done` : 'Nothing due today'}</div>` : ''}</div>`)}
        ${t.people.length ? '' : html`<div class="small muted">Nobody has targets yet. Add them on the Targets page.</div>`}
        ${t.blockers ? html`<a href="#/targets?view=blockers" class="small" style="color:var(--warn);text-decoration:none;padding-top:10px;border-top:1px solid var(--line2)">${t.blockers} open blocker${t.blockers === 1 ? '' : 's'} →</a>` : ''}
      </div>
    </div>

    <div class="grid start" style="grid-template-columns:minmax(0,1.25fr) minmax(0,1fr)">
      <div class="card pad stack" style="gap:18px">
        <div class="baseline"><div class="row" style="gap:8px"><span class="title">From visit to deal</span>${info(TIPS.journey)}</div><a class="link" href="#/funnel" style="text-decoration:none">Full funnel</a></div>
        <div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr))">
          ${steps.map(([label, n, note], i) => html`<div class="stack" style="gap:3px;padding:0 10px;border-left:${i ? '1px solid var(--line2)' : 'none'};min-width:0">
            <div class="nowrap" style="font-size:20px;font-weight:600;letter-spacing:-0.02em">${f.big(n)}</div>
            <div class="small medium clip">${label}</div><div class="tiny muted pretty" style="min-height:28px">${note}</div></div>`)}
        </div>
        <div class="stack" style="gap:8px;padding-top:14px;border-top:1px solid var(--line2)">
          <div class="between"><div class="row small muted" style="gap:7px">Outreach in this period${info(TIPS.outreach)}</div><a class="link" href="#/outbound" style="text-decoration:none">Outbound</a></div>
          ${line('LinkedIn', [[o.linkedin.sent, 'requests'], [o.linkedin.accepted, 'accepted'], [o.linkedin.replied, 'replied']], o.linkedin.sent)}
          ${line('Email', [[o.email.sent, 'sent'], [o.email.opened, 'opened'], [o.email.replied, 'replied']], o.email.sent)}
        </div>
      </div>
      <div class="card stack" style="padding:18px 20px 8px">
        <div class="baseline" style="margin-bottom:6px"><div class="row" style="gap:8px"><span class="title">Needs attention</span>${info(TIPS.alerts, { end: true })}</div><a class="link" href="#/alerts" style="text-decoration:none">All alerts</a></div>
        ${d.alerts.length ? d.alerts.map((a, i) => html`<div style="display:flex;gap:12px;padding:11px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
          <span class="dot" style="width:7px;height:7px;background:var(--${a.tone});margin-top:6px"></span>
          <div class="stack" style="flex:1;min-width:0;gap:2px">
            <div class="between" style="gap:12px"><span class="medium">${a.title}</span><span class="tiny faint nowrap">${a.when}</span></div>
            <div class="small muted pretty">${a.detail}</div></div></div>`)
          : html`<div class="small muted" style="padding:10px 0 14px">Nothing needs attention right now.</div>`}
      </div>
    </div>`;
  },

  actions: {
    openChannel: (ctx, d) => ctx.go('channels', { channel: d.arg }),
    only(ctx, d) { ctx.ui().only = d.arg || null; ctx.render(); },
  },
};

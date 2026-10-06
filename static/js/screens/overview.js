import { html } from '../html.js';
import * as f from '../format.js';
import { sq, deltaLine, info, switcher } from '../ui.js';

const FUNNEL = [['impressions', 'Impr.'], ['clicks', 'Clicks'], ['leads', 'Leads'], ['qualified', 'Qualified'], ['deals', 'Deals'], ['won', 'Won']];
const TARGET_FMT = {
  leads: [f.num, f.num, f.num], qualified: [f.num, f.num, f.num],
  pipeline: [f.moneyShort, f.moneyShort, f.moneyShort], spend: [f.moneyShort, f.moneyShort, f.moneyShort],
  won: [f.num, f.num, v => v.toFixed(1).replace(/\.0$/, '')],
};

// only: a channel id to show by itself, or null for every channel stacked.
function chart(d, ctx, only) {
  const order = ctx.app.shell.channels.filter(c => !only || c.id === only);
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
  const { shell } = ctx.app;
  return html`<div class="stack" style="width:184px;flex:none;gap:12px">${shell.groups.map(g => {
    const items = shell.channels.filter(c => c.grp === g.id && d.by_channel[c.id] != null);
    if (!items.length) return '';
    return html`<div class="stack" style="gap:4px">
      <div class="between tiny faint medium"><span>${g.label}</span><span>${f.num(items.reduce((a, c) => a + d.by_channel[c.id], 0))}</span></div>
      ${items.map(c => html`<div class="row small menu-item" style="padding:1px 4px;margin:0 -4px;font-size:12px" data-act="openChannel" data-arg="${c.id}">
        ${sq(c.color)}<span style="flex:1" class="nowrap">${c.name}</span><span class="medium">${f.num(d.by_channel[c.id])}</span></div>`)}
    </div>`;
  })}</div>`;
}

export default {
  uses: { range: true, compare: true, channel: true },
  load: ctx => ctx.api.get('overview', { ...ctx.rangeParams(), channel: ctx.app.channel }),

  render(d, ctx) {
    const show = ctx.app.compare;
    const k = d.kpis, fn = d.funnel;
    const kpis = [
      ['Qualified leads', f.num(k.qualified.value), deltaLine(k.qualified, { show })],
      ['Total spend', f.moneyShort(k.spend.value), deltaLine(k.spend, { show, mode: 'neutral', fmt: f.moneyShort })],
      ['Cost per qualified lead', f.orDash(k.cpql.value, f.money), deltaLine(k.cpql, { show, mode: 'down', fmt: f.money })],
      ['Pipeline value', f.moneyShort(k.pipeline.value), deltaLine(k.pipeline, { show, fmt: f.moneyShort })],
    ];
    // The daily chart shows every channel stacked, or just the one picked with the buttons above it.
    const present = ctx.app.shell.channels.filter(c => d.by_channel[c.id] != null).sort((a, b) => d.by_channel[b.id] - d.by_channel[a.id]);
    const only = present.some(c => c.id === ctx.ui().only) ? ctx.ui().only : null;
    const rate = i => (i && fn[FUNNEL[i - 1][0]] ? f.pct(fn[FUNNEL[i][0]] / fn[FUNNEL[i - 1][0]] * 100) + ' →' : '');
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
          <div class="kpi-v" style="font-size:34px">${f.num(x.value)}</div><div class="eyebrow nowrap">${x.label}</div>${deltaLine(x, { show, short: true })}</div>`)}
      </div>
      ${kpis.map(([label, value, delta]) => html`<div class="card kpi"><div class="kpi-v">${value}</div><div class="eyebrow">${label}</div>${delta}</div>`)}
    </div>

    <div class="grid" style="grid-template-columns:minmax(0,1fr) 336px">
      <div class="card stack" style="padding:18px 20px 16px;gap:16px">
        <div class="baseline" style="gap:16px;flex-wrap:wrap"><div class="row" style="gap:8px"><span class="title">${only ? `Leads from ${ctx.channel(only).name}` : 'Leads by channel'}</span>
            ${info('How many new leads we got each day. Use the buttons to choose what the chart shows. "All together" stacks every channel, one colour each. Click a channel name to see only that channel.')}</div>
          ${present.length > 1 ? switcher([{ arg: '', label: 'All together', on: !only }, ...present.map(c => ({ arg: c.id, label: c.name, color: c.color, on: only === c.id }))], 'only')
            : html`<div class="small faint">${d.chart_label}</div>`}</div>
        ${present.length > 1 ? html`<div class="small faint" style="margin-top:-10px">${d.chart_label}</div>` : ''}
        <div style="display:flex;gap:28px">${chart(d, ctx, only)}${legend(d, ctx)}</div>
      </div>
      <div class="card pad stack" style="gap:16px">
        <div class="baseline"><div class="title">${d.targets.month} targets</div><div class="small faint">Line = today</div></div>
        ${d.targets.rows.length ? d.targets.rows.map(t => { const [a, b, c] = TARGET_FMT[t.key]; return html`<div class="stack" style="gap:6px">
          <div class="baseline" style="gap:8px"><span>${t.label}</span><span class="small muted"><span class="ink medium">${a(t.actual)}</span> / ${b(t.target)}</span></div>
          <div class="track"><div class="fill" style="width:${t.pct}%;background:var(--ink)"></div><div class="mark" style="left:${d.targets.pace_pct}%"></div></div>
          <div class="tiny" style="color:var(--${t.tone})">${t.status} · ${c(t.projected)} projected</div></div>`; })
          : html`<div class="small muted">No targets set for this month. Add them in Settings.</div>`}
      </div>
    </div>

    <div class="grid start" style="grid-template-columns:minmax(0,1.25fr) minmax(0,1fr)">
      <div class="card pad stack" style="gap:18px">
        <div class="baseline"><div class="title">Funnel</div><a class="link" href="#/funnel" style="text-decoration:none">Full funnel</a></div>
        <div style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr))">
          ${FUNNEL.map(([key, label], i) => html`<div class="stack" style="gap:3px;padding:0 8px;border-left:${i ? '1px solid var(--line2)' : 'none'};min-width:0">
            <div class="tiny faint" style="height:16px">${rate(i)}</div>
            <div class="nowrap" style="font-size:18px;font-weight:600;letter-spacing:-0.02em">${f.big(fn[key])}</div>
            <div class="tiny muted clip">${label}</div></div>`)}
        </div>
        <div class="small muted" style="display:flex;gap:20px;padding-top:14px;border-top:1px solid var(--line2);flex-wrap:wrap">
          <span class="nowrap"><span class="ink medium">${f.money(fn.spend)}</span> spent</span>
          <span class="nowrap"><span class="ink medium">${fn.leads && fn.spend ? f.money2(fn.spend / fn.leads) : '—'}</span> per lead</span>
          <span class="nowrap"><span class="ink medium">${fn.won && fn.spend ? f.money(fn.spend / fn.won) : '—'}</span> per won deal</span>
        </div>
      </div>
      <div class="card stack" style="padding:18px 20px 8px">
        <div class="baseline" style="margin-bottom:6px"><div class="title">Alerts</div><a class="link" href="#/alerts" style="text-decoration:none">All alerts</a></div>
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

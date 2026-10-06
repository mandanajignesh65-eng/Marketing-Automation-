import { html } from '../html.js';
import * as f from '../format.js';
import { sq, pageHead, info, segmented, switcher } from '../ui.js';

const rate = (a, b) => (b ? a / b * 100 : null);
const change = (a, b) => (b ? (a - b) / b * 100 : null);
const sum = (rows, key) => rows.reduce((a, r) => a + r[key], 0);
const light = color => `color-mix(in oklch, ${color} 32%, var(--surface))`;

// The page is split into sides, and each side into parts, so every block answers one question.
const SIDES = {
  inbound: { label: 'Inbound', blurb: 'People who came to us', groups: ['organic', 'events', 'paid'] },
  outbound: { label: 'Outbound', blurb: 'People we reached out to', groups: ['outbound'] },
};
const PARTS = {
  organic: ['Website and organic', 'Found us themselves: website forms, chatbot, search and referrals'],
  events: ['Events', 'Met at events, webinars and trade shows'],
  paid: ['Paid ads', 'Came through an advert'],
  outbound: ['Outreach', 'Replied to marketing’s own email or LinkedIn outreach. Sales cold calling is not counted'],
};

// The outreach tools and how each one names its steps.
const OUTREACH = {
  apollo: { tool: 'Apollo', blurb: 'Emails sent to people we chose', steps: ['Emails sent', 'Opened', 'Replied'],
    tips: ['How many emails we sent from Apollo in this period.', 'How many of those emails were opened.', 'How many people wrote back to us.'] },
  heyreach: { tool: 'HeyReach', blurb: 'LinkedIn requests and messages sent to people we chose', steps: ['Requests sent', 'Accepted', 'Replied'],
    tips: ['How many people we asked to connect with on LinkedIn in this period.', 'How many of them said yes to connecting.', 'How many people wrote back to us on LinkedIn.'] },
};

const TIPS = {
  outBox: 'Read it from top to bottom. The light bars are what the outreach tool did: how many people we contacted and how many answered. The dark bars are what reached Zoho: new leads, the good ones, and deals.',
  outLeads: 'How many new leads from this kind of outreach were added to Zoho in this period.',
  outQualified: 'How many of those leads look like the customers we want.',
  outCamps: 'The campaigns that were running in the tool in this period, biggest first. Sent is how many people were contacted. Replied is how many wrote back.',
  outSources: 'The names used in Zoho for leads from this outreach. It shows which list or sender the leads came from.',
  leads: 'New people who gave us their details in this period. They came from marketing. Cold calls by sales are not counted.',
  qualified: d => `Leads that look like the customers we want: the right industry and a big enough company. Each lead gets a score out of 100. A score of ${d.threshold} or more counts as qualified.`,
  deals: 'Leads that became a real sales chance. Sales opened a deal for them in Zoho in this period.',
  pipeline: 'The money value of all the deals opened in this period, added up. If a deal has no amount in Zoho, it counts as zero.',
  trendPick: 'Use the buttons to choose what the two charts show. "All together" stacks every channel, one colour each. Click a channel name to see only that channel.',
  months: 'How many leads we got in each of the last 6 months. Each colour is one channel. Taller bars mean more leads. This month is not finished yet, so its bar is small.',
  monthsQ: 'The same 6 months, but only the leads that look like the customers we want. If the left chart grows and this one does not, we are getting more people but not the right ones.',
  ranked: 'One row for each channel, biggest first. The bar shows its leads. The dark part of the bar is the leads that look like the customers we want.',
  part: 'One row for each channel. The bar shows its leads. The dark part of the bar is the leads that look like the customers we want. Click a row to see the events, forms or campaigns inside it.',
  inside: 'What is inside this channel: each event, form or campaign, with the same name as in Zoho. The bar shows its leads. The dark part is the good ones. Use it to see which one to do again.',
};

// Three simple rankings side by side: who brings the most leads, the best-fitting leads, and the most deals.
function leaders(rows, d) {
  const boards = [
    { title: 'Most leads', tip: 'Which channel brought the most leads. The longest bar wins.',
      list: rows.filter(r => r.leads), value: r => r.leads, text: r => f.num(r.leads), note: () => '' },
    { title: 'Best fit', tip: `Which channel brought the best kind of leads. The % is how many of its leads look like the customers we want. The small grey number shows how many leads that is. A high % from very few leads is not proof yet.`,
      list: rows.filter(r => r.leads), value: r => r.qualified / r.leads * 100, text: r => f.pct(r.qualified / r.leads * 100), note: r => `${f.num(r.qualified)} of ${f.num(r.leads)}`, scale: 100 },
    { title: 'Most deals', tip: 'Which channel brought the most deals. The small grey number is how many of them we won.',
      list: rows.filter(r => r.deals || r.won), value: r => r.deals, text: r => f.num(r.deals), note: r => (r.won ? `${f.num(r.won)} won` : '') },
  ];
  return html`<div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
    ${boards.map((b, bi) => { const list = [...b.list].sort((x, y) => b.value(y) - b.value(x)), top = b.scale || Math.max(...list.map(b.value), 1); return html`
    <div class="card" style="padding:16px 20px 12px">
      <div class="row" style="gap:8px;margin-bottom:10px"><span class="title">${b.title}</span>${info(b.tip, { end: bi === 2 })}</div>
      ${list.length ? list.map((r, i) => html`<div class="stack" style="gap:5px;padding:8px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
        <div class="baseline" style="gap:10px"><span class="row" style="gap:8px;min-width:0">${sq(r.color, 10, 3)}<span class="clip ${i ? '' : 'semi'}">${r.name}</span></span>
          <span class="nowrap"><span class="tiny faint">${b.note(r)}</span> <span class="${i ? 'medium' : 'semi'}" style="font-size:${i ? 13 : 15}px">${b.text(r)}</span></span></div>
        <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${b.value(r) ? Math.max(b.value(r) / top * 100, 1.5) : 0}%;background:${r.color}"></div></div></div>`)
        : html`<div class="small muted" style="padding:6px 0 8px">None in this period.</div>`}
    </div>`; })}
  </div>`;
}

// Stacked columns, one per month. order: channels, largest first, so colours stack the same way in every column.
function monthly(months, key, order, channel) {
  const totals = months.map(m => order.reduce((a, id) => a + ((m.by[id] || {})[key] || 0), 0));
  const top = Math.max(...totals, 1);
  return html`<div style="display:flex;gap:10px;align-items:flex-end;height:190px;padding-top:18px">
    ${months.map((m, i) => html`<div class="stack" style="flex:1;min-width:0;height:100%;justify-content:flex-end;align-items:stretch;gap:5px">
      <span class="small medium" style="text-align:center">${f.num(totals[i])}</span>
      <div class="stack" style="height:${totals[i] / top * 100}%;min-height:${totals[i] ? 3 : 0}px;border-radius:6px 6px 2px 2px;overflow:hidden;flex-direction:column-reverse">
        ${order.map(id => { const n = (m.by[id] || {})[key] || 0; return n ? html`<div title="${channel(id).name}, ${m.label}: ${f.num(n)}" style="flex:${n} 0 0;min-height:1px;background:${channel(id).color}"></div>` : ''; })}
      </div>
      <span class="tiny muted" style="text-align:center">${m.label}</span></div>`)}
  </div>`;
}

export default {
  uses: { range: true, compare: true },
  load: ctx => ctx.api.get('channels', ctx.rangeParams()),

  render(d, ctx) {
    const { params, compare: show } = ctx.app;
    const view = SIDES[params.view] || params.view === 'compare' ? params.view : 'inbound';
    const all = d.rows.map(r => ({ ...r, ...ctx.channel(r.id) }));
    const live = r => r.leads || r.deals || r.won;
    const tabs = [['inbound', 'Inbound'], ['outbound', 'Outbound'], ['compare', 'Compare all']].map(([arg, label]) => ({ arg, label, on: view === arg }));
    const side = SIDES[view];
    const rows = side ? all.filter(r => side.groups.includes(r.grp)) : all;
    const cur = k => sum(rows, k), prev = k => rows.reduce((a, r) => a + r.prev[k], 0);
    const kpi = (value, label, tip, delta, sub, end) => html`<div class="card kpi" style="padding:16px 18px">
      <span class="kpi-v md">${value}</span><span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span>
      <span class="kpi-d">${show && delta != null ? html`<span style="color:${f.tone(delta)}">${f.arrowShort(delta)}</span> <span class="faint">vs ${d.period.prev_short}</span>` : ''}${sub ? html`<span class="faint">${show && delta != null ? ' · ' : ''}${sub}</span>` : ''}</span></div>`;
    const qRate = rate(cur('qualified'), cur('leads'));
    const split = (n, q, top, color, height = 10) => html`<div class="track" style="height:${height}px;border-radius:${height / 2}px;background:transparent">
      <div style="display:flex;width:${n ? Math.max(n / top * 100, 1.5) : 0}%;height:100%;border-radius:${height / 2}px;overflow:hidden;background:${light(color)}"><div style="width:${n ? q / n * 100 : 0}%;background:${color}"></div></div></div>`;
    const maxLeads = Math.max(...rows.map(r => r.leads), 1);
    const cols = `minmax(130px,200px) minmax(80px,1fr) 56px 70px 52px 48px ${show ? '70px' : ''}`;
    const headRow = html`<div class="thead right" style="border-top:1px solid var(--line);--cols:${cols}"><span style="text-align:left">Channel</span><span style="text-align:left">Leads (dark part = qualified)</span><span>Leads</span><span>Qualified</span><span>Deals</span><span>Won</span>${show ? html`<span>Change</span>` : ''}</div>`;
    const channelRow = (r, open) => { const ch = change(r.leads, r.prev.leads); return html`<div class="trow right ${open ? 'sel' : ''}" data-act="select" data-arg="${open ? '' : r.id}" style="cursor:pointer;--cols:${cols}">
      <span class="row" style="gap:8px;text-align:left;min-width:0"><span class="faint" style="width:10px;font-size:10px">${open ? '▾' : '▸'}</span>${sq(r.color, 10, 3)}<span class="clip medium">${r.name}</span></span>
      ${split(r.leads, r.qualified, maxLeads, r.color)}
      <span class="medium">${f.num(r.leads)}</span><span class="muted">${r.leads ? f.pct(r.qualified / r.leads * 100) : '—'}</span><span>${f.num(r.deals)}</span><span>${f.num(r.won)}</span>
      ${show ? html`<span class="small" style="color:${ch == null ? 'var(--ink3)' : f.tone(ch)}">${ch == null ? (r.leads ? 'new' : '—') : f.arrowShort(ch)}</span>` : ''}</div>`; };
    const sources = r => { const list = d.inside[r.id] || [], top = Math.max(...list.map(s => s.leads), 1); return html`<div style="padding:6px 16px 12px 44px;background:var(--surface2);border-top:1px solid var(--line2)">
      <div class="tiny muted medium" style="padding:6px 0 2px">Sources inside ${r.name}</div>
      ${list.slice(0, 10).map(s => html`<div style="display:grid;grid-template-columns:minmax(120px,260px) minmax(60px,1fr) minmax(180px,auto);gap:14px;align-items:center;padding:6px 0">
        <span class="clip" title="${s.source}">${s.source}</span>${split(s.leads, s.qualified, top, r.color, 8)}
        <span class="small muted nowrap right">${s.leads ? html`<span class="ink medium">${f.num(s.leads)}</span> leads · <span class="ink medium">${f.pct(s.qualified / s.leads * 100)}</span> qualified` : 'no new leads'}${s.deals ? html` · <span class="ink medium">${f.num(s.deals)}</span> deal${s.deals === 1 ? '' : 's'}` : ''}</span></div>`)}
      ${list.length > 10 ? html`<div class="small faint" style="padding-top:4px">and ${f.num(list.length - 10)} smaller sources</div>` : ''}
      ${list.length ? '' : html`<div class="small muted" style="padding:4px 0">No sources recorded.</div>`}</div>`; };
    const part = g => { const list = rows.filter(r => r.grp === g && live(r)).sort((a, b) => b.leads - a.leads || b.deals - a.deals), [title, blurb] = PARTS[g];
      const leads = sum(list, 'leads'), q = rate(sum(list, 'qualified'), leads);
      return html`<div class="card clipped">
        <div class="baseline" style="padding:16px 16px 12px;gap:16px;flex-wrap:wrap">
          <div class="stack" style="gap:2px"><span class="row" style="gap:8px"><span class="title">${title}</span>${info(TIPS.part)}</span><span class="small muted">${blurb}</span></div>
          <div class="small muted" style="display:flex;gap:18px">${[[f.num(leads), 'leads'], [f.orDash(q, f.pct), 'qualified'], [f.num(sum(list, 'deals')), 'deals'], [f.num(sum(list, 'won')), 'won']]
            .map(([v, l]) => html`<span><span class="ink semi" style="font-size:15px">${v}</span> ${l}</span>`)}</div></div>
        ${list.length ? html`${headRow}${list.map(r => html`${channelRow(r, params.channel === r.id)}${params.channel === r.id ? sources(r) : ''}`)}`
          : html`<div class="small muted" style="padding:12px 16px 16px;border-top:1px solid var(--line)">Nothing from this part in the period.</div>`}
      </div>`; };
    // Outbound: one box per outreach channel, what the tool sent and what came back, down to the leads that reached Zoho.
    const outreachBox = r => {
      const kind = OUTREACH[r.id], tool = d.outreach[r.id], linked = kind && d.connected.includes(r.id);
      const steps = [...(tool ? [[kind.steps[0], tool.sent, kind.tips[0]], [kind.steps[1], tool.opened, kind.tips[1]], [kind.steps[2], tool.replied, kind.tips[2]]] : []),
        ['Leads in Zoho', r.leads, TIPS.outLeads], ['Qualified', r.qualified, TIPS.outQualified], ['Deals', r.deals, TIPS.deals]];
      const top = Math.max(...steps.map(x => x[1]), 1), list = d.inside[r.id] || [], camps = tool ? tool.campaigns : [];
      const gap = tool && tool.replied > 0 && r.leads === 0;
      return html`<div class="card" style="padding:16px 20px 16px">
        <div class="baseline" style="gap:16px;flex-wrap:wrap;margin-bottom:12px">
          <div class="stack" style="gap:2px"><span class="row" style="gap:8px">${sq(r.color, 10, 3)}<span class="title">${r.name}</span>${info(TIPS.outBox)}</span>
            <span class="small muted">${kind ? `${kind.blurb} · ${linked ? `figures from ${kind.tool} and Zoho` : `${kind.tool} is not connected, so only Zoho leads show`}` : 'Other outreach recorded in Zoho'}</span></div>
          ${tool && tool.sent ? html`<span class="small muted"><span class="ink semi" style="font-size:15px">${f.pct(tool.replied / tool.sent * 100)}</span> replied</span>` : ''}</div>
        ${steps.map(([label, n, tip], i) => html`<div style="display:grid;grid-template-columns:150px minmax(0,1fr) 70px;gap:14px;align-items:center;padding:5px 0">
          <span class="row" style="gap:7px"><span class="${i < steps.length - 3 ? 'muted' : ''}">${label}</span>${info(tip)}</span>
          <div class="track" style="height:12px;border-radius:6px"><div class="fill" style="width:${n ? Math.max(n / top * 100, 1) : 0}%;background:${i < steps.length - 3 ? light(r.color) : r.color};${i < steps.length - 3 ? `border:1px solid ${r.color}` : ''}"></div></div>
          <span class="right semi">${f.num(n)}</span></div>`)}
        ${!tool && linked ? html`<div class="small muted" style="padding-top:6px">Nothing was sent from ${kind.tool} in this period.</div>` : ''}
        ${gap ? html`<div class="small" style="margin-top:10px;padding:10px 12px;border-radius:9px;background:color-mix(in oklch, var(--warn) 12%, var(--surface));color:var(--ink)">
          <span class="semi">${f.num(tool.replied)} people replied, but no lead from ${r.name.toLowerCase()} was added to Zoho in this period.</span>
          The replies may not have been entered in Zoho yet, or they were entered under another lead source (for example “Outbound”, which is left out as sales cold calling).</div>` : ''}
        ${camps.length || list.length ? html`<div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line2)">
          <div><div class="row tiny muted medium" style="gap:7px;margin-bottom:4px">Campaigns in ${kind ? kind.tool : 'the tool'}${info(TIPS.outCamps)}</div>
            ${camps.length ? camps.slice(0, 6).map(c => html`<div class="baseline" style="gap:12px;padding:5px 0"><span class="clip" title="${c.name}">${c.name}</span>
              <span class="small muted nowrap"><span class="ink medium">${f.num(c.sent)}</span> sent · <span class="ink medium">${f.num(c.replied)}</span> replied</span></div>`) : html`<div class="small muted" style="padding:5px 0">None in this period.</div>`}
            ${camps.length > 6 ? html`<div class="small faint" style="padding-top:2px">and ${f.num(camps.length - 6)} more</div>` : ''}</div>
          <div><div class="row tiny muted medium" style="gap:7px;margin-bottom:4px">Lead sources in Zoho${info(TIPS.outSources, { end: true })}</div>
            ${list.length ? list.slice(0, 6).map(x => html`<div class="baseline" style="gap:12px;padding:5px 0"><span class="clip" title="${x.source}">${x.source}</span>
              <span class="small muted nowrap">${x.leads ? html`<span class="ink medium">${f.num(x.leads)}</span> leads · <span class="ink medium">${f.num(x.qualified)}</span> qualified` : 'no new leads'}${x.deals ? html` · <span class="ink medium">${f.num(x.deals)}</span> deal${x.deals === 1 ? '' : 's'}` : ''}</span></div>`) : html`<div class="small muted" style="padding:5px 0">No leads from this channel in this period.</div>`}</div>
        </div>` : ''}
      </div>`;
    };
    const order = [...rows].sort((a, b) => d.months.reduce((t, m) => t + ((m.by[b.id] || {}).leads || 0), 0) - d.months.reduce((t, m) => t + ((m.by[a.id] || {}).leads || 0), 0))
      .filter(r => d.months.some(m => m.by[r.id])).map(r => r.id);
    const key = list => html`<div class="small" style="display:flex;gap:16px;flex-wrap:wrap">${list.map(id => html`<span class="row" style="gap:6px">${sq(ctx.channel(id).color, 10, 3)}${ctx.channel(id).name}</span>`)}</div>`;
    // The six-month charts show every channel stacked, or just the one picked with the buttons above them.
    const ui = ctx.ui(), one = order.includes((ui.trend || {})[view]) ? ui.trend[view] : null, shown = one ? [one] : order;
    const active = rows.filter(live).sort((a, b) => b.leads - a.leads || b.deals - a.deals);

    return html`
    ${pageHead(`${d.range_name} · ${d.period.short}`, 'Channels', segmented(tabs, 'view', 16))}
    <div class="row" style="gap:10px;margin:2px 0 -2px"><span class="section">${side ? side.label : 'All channels side by side'}</span><span class="muted">${side ? side.blurb : 'Inbound and outbound together'}</span></div>
    <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      ${kpi(f.num(cur('leads')), 'Leads', TIPS.leads, change(cur('leads'), prev('leads')))}
      ${kpi(f.num(cur('qualified')), 'Qualified leads', TIPS.qualified(d), change(cur('qualified'), prev('qualified')), qRate != null ? `${f.pct(qRate)} of leads` : '')}
      ${kpi(f.num(cur('deals')), 'Deals opened', TIPS.deals, change(cur('deals'), prev('deals')), `${f.num(cur('won'))} won`)}
      ${kpi(f.moneyShort(cur('pipeline')), 'Pipeline opened', TIPS.pipeline, change(cur('pipeline'), prev('pipeline')), '', true)}
    </div>
    ${side ? html`
      ${view === 'outbound' ? rows.filter(r => OUTREACH[r.id] || live(r)).map(outreachBox) : side.groups.map(part)}
      ${order.length ? html`<div class="card" style="padding:18px 24px 18px">
        <div class="baseline" style="gap:16px;flex-wrap:wrap;margin-bottom:10px"><span class="row" style="gap:8px"><span class="title">${one ? ctx.channel(one).name : side.label} over the last six months</span>${info(TIPS.trendPick)}</span>
          ${switcher([{ arg: '', label: 'All together', on: !one }, ...order.map(id => ({ arg: id, label: ctx.channel(id).name, color: ctx.channel(id).color, on: one === id }))], 'trend')}</div>
        <div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:36px">
          <div><div class="row small muted" style="gap:7px">Leads per month${info(TIPS.months)}</div>${monthly(d.months, 'leads', shown, ctx.channel)}</div>
          <div><div class="row small muted" style="gap:7px">Qualified leads per month${info(TIPS.monthsQ)}</div>${monthly(d.months, 'qualified', shown, ctx.channel)}</div>
        </div>
      </div>` : ''}`
    : active.length ? html`
      ${leaders(active, d)}
      <div class="card clipped">
        <div class="row" style="gap:8px;padding:16px 16px 10px"><span class="title">Channels ranked</span>${info(TIPS.ranked)}</div>
        ${headRow}
        ${active.map(r => html`<div class="trow right" style="--cols:${cols}">
          <span class="row" style="gap:8px;text-align:left;min-width:0"><span style="width:10px"></span>${sq(r.color, 10, 3)}<span class="clip medium">${r.name}</span></span>
          ${split(r.leads, r.qualified, maxLeads, r.color)}
          <span class="medium">${f.num(r.leads)}</span><span class="muted">${r.leads ? f.pct(r.qualified / r.leads * 100) : '—'}</span><span>${f.num(r.deals)}</span><span>${f.num(r.won)}</span>
          ${show ? (ch => html`<span class="small" style="color:${ch == null ? 'var(--ink3)' : f.tone(ch)}">${ch == null ? (r.leads ? 'new' : '—') : f.arrowShort(ch)}</span>`)(change(r.leads, r.prev.leads)) : ''}</div>`)}
      </div>` : html`<div class="card pad small muted">No leads or deals in this period. Pick a longer range at the top.</div>`}
    ${d.unmapped ? html`<div class="small" style="color:var(--warn)">${f.num(d.unmapped)} more leads have a source that is not placed under a channel yet. <a class="link" href="#/settings" style="text-decoration:none">Place them in Settings</a></div>` : ''}`;
  },

  actions: {
    view: (ctx, d) => ctx.setParams({ view: d.arg }),
    trend(ctx, d) { const ui = ctx.ui(); ui.trend = { ...(ui.trend || {}), [ctx.app.params.view || 'inbound']: d.arg || null }; ctx.render(); },
    select: (ctx, d) => ctx.setParams({ ...ctx.app.params, channel: d.arg || undefined }),
  },
};

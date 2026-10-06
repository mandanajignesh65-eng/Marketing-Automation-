import { html } from '../html.js';
import * as f from '../format.js';
import { sq, pageHead, info, segmented } from '../ui.js';

const rate = (a, b) => (b ? a / b * 100 : null);
const change = (a, b) => (b ? (a - b) / b * 100 : null);
const light = color => `color-mix(in oklch, ${color} 30%, var(--surface))`;
const MIN_SENT = 30;  // a campaign needs this many sends before its reply rate is ranked

// How each outreach tool names its steps, and what the "i" beside each one says.
const KINDS = {
  heyreach: { tab: 'LinkedIn outreach', tool: 'HeyReach', blurb: 'LinkedIn requests and messages we sent to people we chose',
    steps: ['Requests sent', 'Accepted', 'Replied'], unit: 'requests', second: 'accepted',
    tips: ['How many people we asked to connect with on LinkedIn in this period.',
      'How many of them said yes to connecting. Out of every 100 requests, this many were accepted.',
      'How many people wrote back to us on LinkedIn. Out of every 100 requests, this many replied.'] },
  apollo: { tab: 'Email outreach', tool: 'Apollo', blurb: 'Emails we sent to people we chose',
    steps: ['Emails sent', 'Opened', 'Replied'], unit: 'emails', second: 'opened',
    tips: ['How many emails we sent from Apollo in this period.',
      'How many of those emails were opened. Out of every 100 emails, this many were opened.',
      'How many people wrote back to us. Out of every 100 emails, this many got a reply.'] },
};
const OTHER = { tab: 'Other outreach', tool: 'Zoho', blurb: 'Other outreach recorded in Zoho', steps: ['Sent', 'Opened', 'Replied'], unit: 'messages', second: 'opened',
  tips: ['How many messages were sent in this period.', 'How many were opened.', 'How many people wrote back.'] };
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const day = iso => (iso ? `${Number(iso.slice(8, 10))} ${MONTHS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}` : 'not started');
const SORTS = { new: ['Newest first', (a, b) => (b.first || '').localeCompare(a.first || '')], sent: ['Most sent', (a, b) => b.steps[0] - a.steps[0]], replies: ['Most replies', (a, b) => b.steps[2] - a.steps[2]] };

const TIPS = {
  pick: 'Choose one or more campaigns to look at. Every number and chart on this page then counts only the campaigns you ticked. Tick nothing to see all of them.',
  leadsPicked: 'This is for all campaigns together. Zoho does not tell us which campaign a lead came from, so this number cannot be split by campaign.',
  leads: 'How many new leads from this outreach were added to Zoho in this period. If people replied but this is 0, the replies were not entered in Zoho, or were entered under another lead source.',
  path: 'Read it from top to bottom. Each bar is one step. The % on the right is how many moved on from the step above. The last bar is how many became leads in Zoho.',
  chart: ['How many people we contacted in each of the last 6 months. Taller bars mean more outreach. This month is not finished yet.',
    'How many people said yes, or opened our email, in each of the last 6 months.',
    'How many people wrote back in each of the last 6 months. If we send more but this does not grow, the messages are not working.'],
  most: 'Which campaigns got the most replies in this period. The longest bar wins.',
  best: `Which campaigns got the best share of replies. Out of every 100 people contacted, this many wrote back. Only campaigns that contacted ${MIN_SENT} or more people are ranked, so a lucky small one does not win.`,
  all: 'Every campaign that was active in this period, newest first. The bar shows how many people it contacted. The dark part is the people who replied.',
  life: 'Apollo only tells us totals since each sequence began, not day by day. These are those all-time totals. Day by day counting started on the day Apollo was connected.',
};

function columns(months, key, color, height = 170) {
  const top = Math.max(...months.map(m => m[key]), 1);
  return html`<div style="display:flex;gap:10px;align-items:flex-end;height:${height}px;padding-top:18px">
    ${months.map(m => html`<div class="stack" style="flex:1;min-width:0;height:100%;justify-content:flex-end;gap:5px">
      <span class="small medium" style="text-align:center">${f.num(m[key])}</span>
      <div title="${m.label}: ${f.num(m[key])}" style="height:${m[key] / top * 100}%;min-height:${m[key] ? 3 : 0}px;border-radius:6px 6px 2px 2px;background:${color}"></div>
      <span class="tiny muted" style="text-align:center">${m.label}</span></div>`)}
  </div>`;
}

// The tool whose tab is showing: the one in the address, or the busiest one, as render() picks it.
function shownTool(ctx) {
  const groups = ctx.app.data.groups.filter(g => KINDS[g.id] || g.campaigns.length || g.leads).sort((a, b) => (b.totals[0] + b.leads) - (a.totals[0] + a.leads));
  return (groups.find(x => x.id === ctx.app.params.tool) || groups[0]).id;
}

export default {
  uses: { range: true, compare: true },
  load: ctx => ctx.api.get('outbound', ctx.rangeParams()),

  render(d, ctx) {
    const { params, compare: show } = ctx.app;
    // A tool is shown when it is connected or has anything to show; LinkedIn first, since it carries the most.
    const groups = d.groups.filter(g => KINDS[g.id] || g.campaigns.length || g.leads).sort((a, b) => (b.totals[0] + b.leads) - (a.totals[0] + a.leads));
    if (!groups.length) return html`${pageHead(d.period.short, 'Outbound')}<div class="card pad small muted">No outreach tools are connected yet.</div>`;
    const g = groups.find(x => x.id === params.tool) || groups[0];
    const kind = KINDS[g.id] || { ...OTHER, tab: ctx.channel(g.id).name };
    const tabs = groups.map(x => ({ arg: x.id, label: (KINDS[x.id] || { tab: ctx.channel(x.id).name }).tab, on: x.id === g.id }));
    // Picking campaigns narrows every figure on the page to those campaigns; with nothing picked, all of them count.
    const ui = ctx.ui();
    ui.picked = ui.picked || {};
    const picked = (ui.picked[g.id] || []).filter(id => g.campaigns.some(c => c.id === id));
    const filtered = picked.length > 0;
    const chosen = filtered ? g.campaigns.filter(c => picked.includes(c.id)) : g.campaigns;
    const add = get => [0, 1, 2].map(i => chosen.reduce((a, c) => a + get(c)[i], 0));
    const [sent, second, replied] = filtered ? add(c => c.steps) : g.totals, [pSent, pSecond, pReplied] = filtered ? add(c => c.prev) : g.prev;
    const months = filtered ? g.months.map((m, i) => ({ label: m.label, sent: chosen.reduce((a, c) => a + c.months[i][0], 0), opened: chosen.reduce((a, c) => a + c.months[i][1], 0), replied: chosen.reduce((a, c) => a + c.months[i][2], 0) })) : g.months;
    const metric = [0, 1, 2].includes(ui.metric) ? ui.metric : 0;  // which step the six-month chart shows
    const known = g.campaigns.filter(c => c.first || (c.lifetime && c.lifetime[0]));
    const sort = SORTS[ui.sort] ? ui.sort : 'new', q = (ui.q || '').trim().toLowerCase();
    const listed = known.filter(c => !q || c.name.toLowerCase().includes(q)).sort(SORTS[sort][1]);
    const tick = on => html`<span style="width:16px;height:16px;border-radius:5px;flex:none;display:grid;place-items:center;font-size:11px;font-weight:700;color:#fff;border:1.5px solid ${on ? 'var(--accent)' : 'var(--ink3)'};background:${on ? 'var(--accent)' : 'transparent'}">${on ? '✓' : ''}</span>`;
    const picker = html`<div class="card" style="padding:12px 16px">
      <div class="row" style="gap:12px;flex-wrap:wrap">
        <span class="row" style="gap:7px"><span class="semi">Campaigns</span>${info(TIPS.pick)}</span>
        <span class="muted">${filtered ? html`Showing <span class="ink semi">${f.num(picked.length)}</span> of ${f.num(known.length)}` : `Showing all ${f.num(known.length)}`}</span>
        ${chosen.length && filtered ? html`<div class="row" style="gap:6px;flex-wrap:wrap;flex:1;min-width:0">${chosen.slice(0, 6).map(c => html`<span class="chip on" data-act="pick" data-arg="${c.id}" title="Remove ${c.name}" style="max-width:240px;display:inline-flex;gap:6px;align-items:center"><span class="clip">${c.name}</span><span>×</span></span>`)}
          ${chosen.length > 6 ? html`<span class="small muted">+${f.num(chosen.length - 6)} more</span>` : ''}</div>` : html`<span style="flex:1"></span>`}
        ${filtered ? html`<span class="btn xs" data-act="clearPicked">Show all</span>` : ''}
        <span class="btn xs ${ui.open ? '' : 'primary'}" data-act="togglePicker">${ui.open ? 'Done' : 'Choose campaigns'}</span>
      </div>
      ${ui.open ? html`<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--line2)">
        <div class="row" style="gap:12px;flex-wrap:wrap;margin-bottom:8px">
          <label class="search" style="width:260px"><i></i><input id="camp-search" type="search" placeholder="Search campaign name" value="${ui.q || ''}" data-input="campSearch" autocomplete="off"></label>
          ${segmented(Object.entries(SORTS).map(([arg, [label]]) => ({ arg, label, on: sort === arg })), 'sortCamps')}
          <span style="flex:1"></span>
          <span class="link" data-act="pickShown">Tick all ${f.num(listed.length)} shown</span>
        </div>
        <div class="thead right" style="--cols:24px minmax(0,1fr) 110px 70px 70px;padding:6px 8px;border-bottom:1px solid var(--line2)"><span></span><span style="text-align:left">Campaign</span><span>Started</span><span>Sent</span><span>Replies</span></div>
        <div data-scroll="camps" style="max-height:300px;overflow-y:auto">
          ${listed.map(c => html`<div class="trow right" data-act="pick" data-arg="${c.id}" style="--cols:24px minmax(0,1fr) 110px 70px 70px;padding:8px;cursor:pointer">
            ${tick(picked.includes(c.id))}<span class="clip ${picked.includes(c.id) ? 'semi' : ''}" style="text-align:left" title="${c.name}">${c.name}</span>
            <span class="small muted">${day(c.first)}</span><span>${f.num(c.steps[0])}</span><span>${f.num(c.steps[2])}</span></div>`)}
          ${listed.length ? '' : html`<div class="small muted" style="padding:12px 8px">No campaign matches that name.</div>`}
        </div>
        <div class="tiny faint" style="padding-top:8px">Sent and replies are for ${d.period.short}. Started is the first day the campaign did anything.</div>
      </div>` : ''}
    </div>`;
    const kpi = (value, label, tip, delta, sub, end) => html`<div class="card kpi" style="padding:16px 18px">
      <span class="kpi-v md">${value}</span><span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span>
      <span class="kpi-d">${show && delta != null ? html`<span style="color:${f.tone(delta)}">${f.arrowShort(delta)}</span> <span class="faint">vs ${d.period.prev_short}</span>` : ''}${sub ? html`<span class="faint">${show && delta != null ? ' · ' : ''}${sub}</span>` : ''}</span></div>`;
    // Opens and replies can arrive for messages sent before the period, so a share above 100% is not shown.
    const share = (a, b, word) => (b && a <= b ? `${f.pct(a / b * 100)} ${word}` : '');
    const path = [[kind.steps[0], sent, kind.tips[0]], [kind.steps[1], second, kind.tips[1]], [kind.steps[2], replied, kind.tips[2]], ...(filtered ? [] : [['Leads in Zoho', g.leads, TIPS.leads]])];
    const top = Math.max(...path.map(x => x[1]), 1);
    const active = chosen.filter(c => c.steps[0] || c.steps[1] || c.steps[2]);
    const newest = [...active].sort(SORTS.new[1]);
    const mostReplies = [...active].filter(c => c.steps[2]).sort((a, b) => b.steps[2] - a.steps[2]).slice(0, 5);
    const bestRate = [...active].filter(c => c.steps[0] >= MIN_SENT).sort((a, b) => b.steps[2] / b.steps[0] - a.steps[2] / a.steps[0]).slice(0, 5);
    const board = (title, tip, list, value, text, note, scale, end) => html`<div class="card" style="padding:16px 20px 12px">
      <div class="row" style="gap:8px;margin-bottom:10px"><span class="title">${title}</span>${info(tip, { end })}</div>
      ${list.length ? list.map((c, i) => html`<div class="stack" style="gap:5px;padding:8px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
        <div class="baseline" style="gap:10px"><span class="clip ${i ? '' : 'semi'}" title="${c.name}">${c.name}</span>
          <span class="nowrap"><span class="tiny faint">${note(c)}</span> <span class="${i ? 'medium' : 'semi'}" style="font-size:${i ? 13 : 15}px">${text(c)}</span></span></div>
        <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${Math.max(value(c) / (scale || value(list[0]) || 1) * 100, 1.5)}%;background:${g.color}"></div></div></div>`)
        : html`<div class="small muted" style="padding:6px 0 8px">None in this period.</div>`}
    </div>`;
    const maxSent = Math.max(...active.map(c => c.steps[0]), 1);
    const cols = 'minmax(160px,1.3fr) 100px minmax(90px,1fr) 64px 72px 72px 60px';
    const life = g.campaigns.filter(c => c.lifetime && c.lifetime[0]).sort((a, b) => b.lifetime[0] - a.lifetime[0]);
    const gap = !filtered && replied > 0 && g.leads === 0;

    return html`
    ${pageHead(show ? `${d.period.short} compared with ${d.period.prev_short}` : d.period.short, 'Outbound', groups.length > 1 ? segmented(tabs, 'tool', 16) : '')}
    <div class="row" style="gap:10px;margin:2px 0 -2px;flex-wrap:wrap">${sq(g.color, 11, 3)}<span class="section">${kind.tab}</span>
      <span class="muted">${kind.blurb} · ${g.connected ? `figures from ${kind.tool}` : `${kind.tool} is not connected`}</span></div>
    ${known.length ? picker : ''}
    <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      ${kpi(f.num(sent), kind.steps[0], kind.tips[0], change(sent, pSent))}
      ${kpi(f.num(second), kind.steps[1], kind.tips[1], change(second, pSecond), share(second, sent, `of ${kind.unit}`))}
      ${kpi(f.num(replied), kind.steps[2], kind.tips[2], change(replied, pReplied), share(replied, sent, `of ${kind.unit}`))}
      ${filtered ? kpi(f.num(g.leads), 'Leads in Zoho', TIPS.leadsPicked, null, 'all campaigns together', true)
        : kpi(f.num(g.leads), 'Leads in Zoho', TIPS.leads, change(g.leads, g.prev_leads), g.leads ? `${f.num(g.qualified)} qualified` : '', true)}
    </div>
    ${sent || second || replied || g.leads ? html`
    <div class="card" style="padding:18px 24px 18px">
      <div class="row" style="gap:8px;margin-bottom:12px"><span class="title">From first message to lead</span>${info(TIPS.path)}</div>
      ${path.map(([label, n], i) => { const raw = i ? rate(n, path[i - 1][1]) : null, r = raw != null && raw > 100 ? null : raw, last = !filtered && i === path.length - 1; return html`
        <div style="display:grid;grid-template-columns:150px minmax(0,1fr) 70px 130px;gap:14px;align-items:center;padding:6px 0">
          <span class="medium">${label}</span>
          <div class="track" style="height:22px;border-radius:6px"><div class="fill" style="width:${n ? Math.max(n / top * 100, 0.8) : 0}%;border-radius:6px;background:${last ? 'var(--ink)' : `color-mix(in oklch, ${g.color} ${100 - i * 22}%, var(--surface))`}"></div></div>
          <span class="right semi" style="font-size:15px">${f.num(n)}</span>
          <span class="small muted">${i ? html`<span class="ink medium">${f.orDash(r, f.pct)}</span> of ${path[i - 1][0].toLowerCase()}` : ''}</span></div>`; })}
      ${gap ? html`<div class="small" style="margin-top:10px;padding:10px 12px;border-radius:9px;background:color-mix(in oklch, var(--warn) 12%, var(--surface))">
        <span class="semi">${f.num(replied)} people replied, but no lead from ${kind.tab.toLowerCase()} was added to Zoho in this period.</span>
        The replies may not be in Zoho yet, or they were added under another lead source (for example “Outbound”, which is left out as sales cold calling).</div>` : ''}
    </div>` : html`<div class="card pad small muted">${g.connected ? `Nothing was sent from ${kind.tool} in this period. Pick a longer range at the top.` : `Connect ${kind.tool} to see what was sent and who replied.`}</div>`}
    ${months.some(m => m.sent || m.opened || m.replied) ? html`<div class="card" style="padding:18px 24px 18px">
      <div class="baseline" style="gap:16px;flex-wrap:wrap;margin-bottom:6px">
        <span class="row" style="gap:8px"><span class="title">${kind.steps[metric]} per month</span>${info(TIPS.chart[metric])}<span class="small muted">last six months</span></span>
        ${segmented(kind.steps.map((label, i) => ({ arg: i, label, on: metric === i })), 'metric')}</div>
      ${columns(months, ['sent', 'opened', 'replied'][metric], `color-mix(in oklch, ${g.color} ${[45, 72, 100][metric]}%, var(--surface))`, 210)}
    </div>` : ''}
    ${active.length ? html`
    <div class="row" style="gap:10px;margin:6px 0 -2px"><span class="section">Campaigns</span><span class="muted">${filtered ? 'Only the campaigns you chose' : 'Which message and audience worked'}</span></div>
    <div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
      ${board('Most replies', TIPS.most, mostReplies, c => c.steps[2], c => f.num(c.steps[2]), c => `${f.num(c.steps[0])} sent`)}
      ${board('Best reply rate', TIPS.best, bestRate, c => c.steps[2] / c.steps[0] * 100, c => f.pct(c.steps[2] / c.steps[0] * 100), c => `${f.num(c.steps[2])} of ${f.num(c.steps[0])}`,
        bestRate.length ? Math.max(bestRate[0].steps[2] / bestRate[0].steps[0] * 100, 1) : 1, true)}
    </div>
    <div class="card clipped" style="--cols:${cols}">
      <div class="baseline" style="padding:16px 16px 10px"><span class="row" style="gap:8px"><span class="title">${filtered ? 'The campaigns you chose' : 'All campaigns in this period'}</span>${info(TIPS.all)}</span>
        <span class="small muted">${f.num(active.length)} active · newest first</span></div>
      <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Campaign</span><span>Started</span><span style="text-align:left">Sent (dark part = replied)</span>
        <span>Sent</span><span style="text-transform:capitalize">${kind.second}</span><span>Replied</span><span>Replies</span></div>
      ${newest.slice(0, 25).map(c => html`<div class="trow right">
        <div class="stack" style="text-align:left;min-width:0"><span class="medium clip" title="${c.name}">${c.name}</span>${c.detail ? html`<span class="tiny faint clip">${c.detail}</span>` : ''}</div>
        <span class="small muted">${day(c.first)}</span>
        <div class="track" style="height:10px;border-radius:5px;background:transparent"><div style="display:flex;width:${c.steps[0] ? Math.max(c.steps[0] / maxSent * 100, 1.5) : 0}%;height:100%;border-radius:5px;overflow:hidden;background:${light(g.color)}">
          <div style="width:${c.steps[0] ? Math.min(c.steps[2] / c.steps[0] * 100, 100) : 0}%;background:${g.color}"></div></div></div>
        <span class="medium">${f.num(c.steps[0])}</span><span class="muted">${f.orDash(rate(c.steps[1], c.steps[0]), f.pct)}</span>
        <span class="muted">${f.orDash(rate(c.steps[2], c.steps[0]), f.pct)}</span><span class="medium">${f.num(c.steps[2])}</span></div>`)}
      ${active.length > 25 ? html`<div class="small faint" style="padding:10px 16px;border-top:1px solid var(--line2)">and ${f.num(active.length - 25)} smaller campaigns</div>` : ''}
    </div>` : ''}
    ${life.length ? html`<div class="card clipped" style="--cols:minmax(160px,1.6fr) 90px 90px 90px">
      <div class="baseline" style="padding:16px 16px 10px"><span class="row" style="gap:8px"><span class="title">All-time by sequence</span>${info(TIPS.life)}</span>
        <span class="small muted">${f.num(life.length)} sequences with emails sent</span></div>
      <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Sequence</span><span>Sent</span><span>Opened</span><span>Replied</span></div>
      ${life.slice(0, 12).map(c => html`<div class="trow right"><div class="stack" style="text-align:left;min-width:0"><span class="medium clip" title="${c.name}">${c.name}</span>${c.detail ? html`<span class="tiny faint clip">${c.detail}</span>` : ''}</div>
        <span class="medium">${f.num(c.lifetime[0])}</span><span class="muted">${f.num(c.lifetime[1])}</span><span class="muted">${f.num(c.lifetime[2])}</span></div>`)}
    </div>` : ''}`;
  },

  actions: {
    tool: (ctx, d) => ctx.setParams({ tool: d.arg }),
    metric(ctx, d) { ctx.ui().metric = Number(d.arg); ctx.render(); },
    togglePicker(ctx) { const ui = ctx.ui(); ui.open = !ui.open; ctx.render(); },
    sortCamps(ctx, d) { ctx.ui().sort = d.arg; ctx.render(); },
    pick(ctx, d) {
      const ui = ctx.ui(), tool = shownTool(ctx), id = Number(d.arg), now = ui.picked[tool] || [];
      ui.picked[tool] = now.includes(id) ? now.filter(x => x !== id) : [...now, id];
      ctx.render();
    },
    pickShown(ctx) {
      const ui = ctx.ui(), tool = shownTool(ctx), q = (ui.q || '').trim().toLowerCase();
      const group = ctx.app.data.groups.find(x => x.id === tool);
      const shown = group.campaigns.filter(c => (c.first || (c.lifetime && c.lifetime[0])) && (!q || c.name.toLowerCase().includes(q))).map(c => c.id);
      ui.picked[tool] = [...new Set([...(ui.picked[tool] || []), ...shown])];
      ctx.render();
    },
    clearPicked(ctx) { ctx.ui().picked[shownTool(ctx)] = []; ctx.render(); },
  },

  inputs: {
    campSearch(ctx, value) { ctx.ui().q = value; ctx.render(); },
  },
};

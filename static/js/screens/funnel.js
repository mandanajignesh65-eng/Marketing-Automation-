import { html } from '../html.js';
import * as f from '../format.js';
import { segmented, pageHead, info, sq, switcher } from '../ui.js';

// key, name, one line under the name, and what the "i" says. `part` groups the steps by where the figure comes from.
// `rate` gives the two numbers behind the % on the right, `of` names what it is a share of, and `why` explains it.
const STEPS = {
  reached: { k: 'reached', label: 'People reached', part: 'reach', sub: 'Website visits plus outreach messages',
    parts: x => [[x.visits, 'website visits'], [x.sent, 'outreach messages sent'], [x.replied, 'replies to those messages']],
    tip: 'Everyone marketing touched in this period. It adds two things: how many times people opened our website, and how many LinkedIn requests and emails we sent. When ads are connected, ad clicks will be added too.' },
  visits: { k: 'visits', label: 'Website visits', part: 'web', sub: 'Times people opened our website',
    tip: 'How many times people opened our website in this period. Counted by Google Analytics.' },
  sent: { k: 'sent', label: 'Messages sent', part: 'outreach', sub: 'LinkedIn requests and emails we sent',
    tip: 'How many people we wrote to first: LinkedIn connection requests and emails added together.' },
  replied: { k: 'replied', label: 'Replies', part: 'outreach', sub: 'People who wrote back', rate: x => [x.replied, x.sent], of: 'of messages',
    tip: 'How many of those people wrote back to us.', why: 'Out of every 100 messages we sent, how many got a reply.' },
  leads: { k: 'leads', label: 'Leads', part: 'crm', sub: 'New marketing leads in Zoho',
    tip: 'New people who gave us their details in this period. They came from marketing. Cold calls by sales are not counted.' },
  qualified: { k: 'qualified', label: 'Qualified', part: 'crm', sub: 'Leads that fit your ideal customer', rate: x => [x.qualified, x.leads], of: 'of leads',
    tip: d => `Leads that look like the customers we want: the right industry and a big enough company. Each lead gets a score out of 100. A score of ${d.threshold} or more counts as qualified. If we do not know the company, the lead cannot qualify.`,
    why: 'Out of every 100 leads, how many look like the customers we want. Higher is better.' },
  deals: { k: 'deals', label: 'Deals', part: 'crm', sub: 'Deals opened in Zoho', rate: x => [x.deals, x.leads], of: 'of leads',
    tip: 'Leads that became a real sales chance. Sales opened a deal for them in Zoho in this period.',
    why: 'Out of every 100 leads, how many became a deal. Some deals come from leads of earlier months, so on a single day this number can look odd.' },
  won: { k: 'won', label: 'Won', part: 'crm', sub: 'Deals closed as won', rate: x => [x.won, x.deals], of: 'of deals',
    tip: 'Deals that said yes and became customers in this period. Some of them were opened in earlier months.',
    why: 'Out of every 100 deals opened, how many we won. Higher is better.' },
};
// How leads relate to the step above them, which depends on what that step is.
const LEAD_RATE = {
  all: { rate: x => [x.leads, x.reached], of: 'of people reached', why: 'Out of every 100 people we reached, by the website or by a message, how many became a lead.' },
  web: { rate: x => [x.web_leads, x.visits], of: 'of visits', why: 'Out of every 100 website visits, how many became a lead on the website (a form or the chatbot). Leads from outreach and events are left out of this %, because those people did not come through the website.' },
  outreach: { rate: x => [x.leads, x.replied], of: 'of replies', why: 'Out of every 100 replies, how many became a lead in Zoho. If this is very low, replies are probably not being added to Zoho with the right lead source.' },
};
const ORDER = { all: ['reached'], web: ['visits'], outreach: ['sent', 'replied'] };
const PART = { reach: 'Reach · website and outreach', web: 'Website · Google Analytics', outreach: 'Outreach · HeyReach and Apollo', crm: 'Pipeline · Zoho CRM' };
const TOP = [100, 84, 68, 54, 42, 32], LAST = 24;  // slice widths, top edge of each and the bottom of the last
// One colour per target segment, then grey for other industries and a pale tone where the company is not known.
const SEGMENT_COLORS = ['oklch(0.62 0.13 165)', 'oklch(0.70 0.14 65)', 'oklch(0.58 0.14 262)', 'oklch(0.60 0.15 320)', 'oklch(0.66 0.12 25)', 'oklch(0.64 0.10 210)'];
const MIX = [['leads', 'Leads'], ['qualified', 'Qualified'], ['deals', 'Deals'], ['won', 'Won']];

export default {
  uses: { range: true, compare: true, channel: true },
  load: ctx => ctx.api.get('funnel', { ...ctx.rangeParams(), segment: ctx.app.channel }),

  render(d, ctx) {
    const { app } = ctx;
    const show = app.compare, c = d.cur, p = d.prev;
    const segs = [{ arg: 'all', label: 'All channels' }, ...app.shell.groups.map(g => ({ arg: g.id, label: g.label }))]
      .map(s => ({ ...s, on: app.channel === s.arg }));
    const change = (a, b) => (b ? (a - b) / b * 100 : null);
    const rate = (a, b) => (b ? a / b * 100 : null);
    // The steps above "Leads" change with what is being looked at; some channels (events, ads not connected) start at leads.
    const steps = [...(ORDER[d.top] || []), 'leads', 'qualified', 'deals', 'won'].map(k => (k === 'leads' && LEAD_RATE[d.top] ? { ...STEPS.leads, ...LEAD_RATE[d.top] } : STEPS[k]));
    const widths = TOP.slice(TOP.length - steps.length).concat(LAST);
    const shade = i => 26 + Math.round(74 * i / Math.max(steps.length - 1, 1));  // light at the top, full colour at the bottom

    const rows = steps.map((s, i) => {
      const from = steps[i - 1], n = c[s.k];
      const share = x => { const [a, b] = s.rate(x); return rate(a, b); };
      const r = s.rate ? share(c) : null, pr = s.rate ? share(p) : null;
      const late = !i && !n && c.leads > 0;  // the first step has nothing yet although leads exist: its source has not reported
      const wt = widths[i], wb = widths[i + 1], mix = shade(i);
      const clip = `polygon(${(100 - wt) / 2}% 0, ${(100 + wt) / 2}% 0, ${(100 + wb) / 2}% 100%, ${(100 - wb) / 2}% 100%)`;
      const delta = change(n, p[s.k]);
      const newPart = !from || from.part !== s.part;
      return html`
      ${newPart ? html`<div class="funnel-row" style="margin-top:${i ? 14 : 0}px"><span class="funnel-part">${PART[s.part]}</span><span></span><span></span></div>` : ''}
      <div class="funnel-row" style="margin-top:4px">
        <div class="stack" style="gap:2px;min-width:0">
          <span class="row" style="gap:7px"><span class="title">${s.label}</span>${info(typeof s.tip === 'function' ? s.tip(d) : s.tip)}</span>
          <span class="small muted">${late ? 'Not counted yet for this period' : s.sub}</span>
        </div>
        <div class="funnel-slice" title="${s.label}: ${f.num(n)}"
          style="clip-path:${clip};background:color-mix(in oklch, var(--accent) ${mix}%, var(--surface));color:${mix >= 55 ? '#fff' : 'var(--ink)'}">${late ? '—' : f.big(n)}</div>
        <div class="stack" style="gap:2px;min-width:0">
          ${s.rate ? html`<span class="row" style="gap:7px"><span style="font-size:17px;font-weight:600;letter-spacing:-0.01em">${f.orDash(r, f.pct)}</span>
              <span class="small muted">${s.of}</span>${info(s.why, { end: true })}</span>` : s.parts ? html`<div class="stack small" style="gap:1px">${s.parts(c).map(([n, word]) => html`<span class="nowrap"><span class="ink medium">${f.num(n)}</span> <span class="muted">${word}</span></span>`)}</div>`
            : html`<span class="small muted">${from ? '' : 'Where it starts'}</span>`}
          ${show ? html`<span class="tiny nowrap">
            ${delta != null ? html`<span style="color:${f.tone(delta)}">${f.arrowShort(delta)}</span> <span class="faint">vs ${f.big(p[s.k])}</span>` : html`<span class="faint">No earlier figure</span>`}
            ${r != null && pr != null && Math.abs(r - pr) >= 0.005 ? html`<span class="faint"> · rate </span><span style="color:var(--${r >= pr ? 'pos' : 'neg'})">${r >= pr ? '+' : '−'}${Math.abs(r - pr).toFixed(2)} pts</span>` : ''}</span>` : ''}
        </div>
      </div>`;
    });

    const heads = [
      ['Qualified rate', rate(c.qualified, c.leads), rate(p.qualified, p.leads), STEPS.qualified.why],
      ['Lead to deal', rate(c.deals, c.leads), rate(p.deals, p.leads), 'Out of every 100 leads, how many became a deal. It shows how much of what marketing brings turns into real sales chances.'],
      ['Win rate', rate(c.won, c.deals), rate(p.won, p.deals), STEPS.won.why],
    ];
    const mixRows = MIX.map(([k, label]) => ({ k, label, total: d.mix.reduce((a, m) => a + m[k], 0), parts: d.mix.filter(m => m[k]).sort((a, b) => b[k] - a[k]) }));
    const legend = d.mix.map(m => ctx.channel(m.id));
    const aud = d.audience, audTotal = aud.total.reduce((a, s) => a + s.leads, 0);
    const segColor = i => (i < aud.targets ? SEGMENT_COLORS[i % SEGMENT_COLORS.length] : i === aud.targets ? 'var(--ink3)' : 'var(--track)');
    const segInk = i => (i > aud.targets ? 'var(--ink2)' : '#fff');
    const inTarget = aud.total.slice(0, aud.targets).reduce((a, s) => a + s.leads, 0), unknown = aud.total[aud.total.length - 1].leads;
    // Both colour charts show everything together, or just the one channel or company type picked with the buttons above them.
    const ui = ctx.ui();
    const oneCh = d.mix.some(m => m.id === ui.mixOnly) ? ui.mixOnly : null;
    const oneSeg = Number.isInteger(ui.segOnly) && aud.total[ui.segOnly] && aud.total[ui.segOnly].leads ? ui.segOnly : null;
    const lone = (n, total, color, name, ink = '#fff') => { const share = total ? n / total * 100 : 0; return html`<div class="row" style="gap:10px">
      <div class="mixbar" style="flex:1">${n ? html`<div style="width:${Math.max(share, 0.8)}%;background:${color};color:${ink}" title="${name}: ${f.num(n)} (${f.pct(share)})">${share >= 9 ? f.num(n) : ''}</div>` : ''}</div>
      <span class="small muted nowrap" style="width:96px"><span class="ink medium">${f.num(n)}</span> · ${f.pct(share)}</span></div>`; };
    const segBar = (counts, total) => (oneSeg != null ? lone(counts[oneSeg], total, segColor(oneSeg), aud.names[oneSeg], segInk(oneSeg))
      : html`<div class="mixbar">${aud.names.map((name, i) => { const n = counts[i], share = total ? n / total * 100 : 0; return n ? html`
      <div style="width:${share}%;background:${segColor(i)};color:${segInk(i)}" title="${name}: ${f.num(n)} (${f.pct(share)})">${share >= 9 ? f.num(n) : ''}</div>` : ''; })}</div>`);
    const per = (n, k) => (c[k] && c.spend ? f.moneyAuto(c.spend / c[k] * n) : '—');
    const costs = [['Per 1,000 impressions', per(1000, 'impressions')], ['Per click', per(1, 'clicks')], ['Per lead', per(1, 'leads')],
      ['Per qualified lead', per(1, 'qualified')], ['Per deal', per(1, 'deals')], ['Per won deal', per(1, 'won')]];

    return html`
    ${pageHead(show ? `${d.period.short} compared with ${d.period.prev_short}` : d.period.short, 'Funnel', segmented(segs, 'setChannel'))}
    <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      ${heads.map(([label, v, pv, tip], i) => html`<div class="card kpi" style="padding:16px 18px">
        <span class="kpi-v md">${f.orDash(v, f.pct)}</span>
        <span class="row eyebrow" style="gap:7px">${label}${info(tip, { end: i === 2 })}</span>
        ${show && v != null && pv != null ? html`<span class="kpi-d" style="color:var(--${v >= pv ? 'pos' : 'neg'})">${v >= pv ? '▲' : '▼'} ${Math.abs(v - pv).toFixed(2)} pts <span class="faint">vs ${f.pct(pv)}</span></span>` : ''}
      </div>`)}
    </div>
    <div class="card" style="padding:20px 24px 24px">
      <div class="baseline" style="margin-bottom:16px"><span class="row" style="gap:8px"><span class="title">${d.top === 'all' ? 'From first touch to won deal' : d.top === 'web' ? 'From website visit to won deal' : d.top === 'outreach' ? 'From first message to won deal' : 'From lead to won deal'}</span>
          ${info('Read it from top to bottom. Each coloured band is one step. The number inside is how many reached that step. The % on the right is how many moved on from the step above. The shape is just a picture, the widths are not exact.')}</span>
        <span class="small muted">${show ? `Changes are against ${d.period.prev_short}` : d.period.label}</span></div>
      ${rows}
    </div>
    <div class="card" style="padding:18px 24px 20px">
      <div class="baseline" style="gap:16px;flex-wrap:wrap;margin-bottom:14px"><span class="row" style="gap:8px"><span class="title">Which channels fill each step</span>
        ${info('Each bar shows where the leads or deals came from. Each colour is one channel. A big colour under Leads but a small one under Won means that channel brings many people, but few become customers.')}</span>
        ${d.mix.length ? switcher([{ arg: '', label: 'All together', on: !oneCh }, ...legend.map(ch => ({ arg: ch.id, label: ch.name, color: ch.color, on: oneCh === ch.id }))], 'mixOnly') : ''}</div>
      ${d.mix.length ? html`
        ${mixRows.map(r => html`<div style="display:grid;grid-template-columns:110px minmax(0,1fr);gap:16px;align-items:center;padding:6px 0">
          <div class="baseline"><span class="medium">${r.label}</span><span class="muted">${f.num(r.total)}</span></div>
          ${r.total && oneCh ? lone((d.mix.find(m => m.id === oneCh) || {})[r.k] || 0, r.total, ctx.channel(oneCh).color, ctx.channel(oneCh).name)
            : r.total ? html`<div class="mixbar">${r.parts.map(m => { const ch = ctx.channel(m.id), share = m[r.k] / r.total * 100; return html`
            <div style="width:${share}%;background:${ch.color}" title="${ch.name}: ${f.num(m[r.k])} (${f.pct(share)})">${share >= 9 ? f.num(m[r.k]) : ''}</div>`; })}</div>`
            : html`<div class="small faint">None in this period</div>`}
        </div>`)}`
        : html`<div class="small muted">No leads or deals in this period.</div>`}
    </div>
    ${d.mix.length ? html`<div class="card" style="padding:18px 24px 20px">
      <div class="row" style="gap:8px;margin-bottom:14px"><span class="title">How each channel converts</span>
        ${info('One small box for each channel. It shows how many leads it brought, how many were the right kind, and how many became deals and wins. Pipeline is the money value of the deals it opened.')}</div>
      <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px">
        ${d.mix.map(m => { const ch = ctx.channel(m.id), top = Math.max(m.leads, m.qualified, m.deals, m.won, 1), q = rate(m.qualified, m.leads); return html`
        <div class="inset stack" style="gap:10px;padding:14px 16px">
          <div class="baseline"><span class="row medium" style="gap:7px">${sq(ch.color, 10, 3)}${ch.name}</span>
            <span class="small muted">${q != null ? html`<span class="ink semi">${f.pct(q)}</span> qualified` : 'no new leads'}</span></div>
          ${MIX.map(([k, label]) => html`<div style="display:grid;grid-template-columns:64px minmax(0,1fr) 40px;gap:10px;align-items:center">
            <span class="small muted">${label}</span>
            <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${m[k] ? Math.max(m[k] / top * 100, 1.5) : 0}%;background:${ch.color}"></div></div>
            <span class="small right medium">${f.num(m[k])}</span></div>`)}
          <div class="small muted">${m.pipeline ? html`Pipeline opened <span class="ink medium">${f.moneyShort(m.pipeline)}</span>` : 'No pipeline value in this period'}</div>
        </div>`; })}
      </div>
    </div>` : ''}
    ${audTotal ? html`<div class="card" style="padding:18px 24px 20px">
      <div class="baseline" style="margin-bottom:12px"><span class="row" style="gap:8px"><span class="title">Who we are attracting</span>
          ${info('This shows what kind of companies our leads are from. Each colour is one type of company we want. Grey means another type. Light grey means we do not know the company. More colour is better.')}</span>
        <span class="small muted"><span class="ink semi">${f.pct(inTarget / audTotal * 100)}</span> in target segments · <span class="ink semi">${f.pct(unknown / audTotal * 100)}</span> company not known</span></div>
      <div class="row" style="justify-content:flex-end;margin-bottom:10px">${switcher([{ arg: '', label: 'All together', on: oneSeg == null },
        ...aud.names.map((name, i) => ({ arg: i, label: name, color: segColor(i), on: oneSeg === i })).filter((o, i) => aud.total[i].leads)], 'segOnly')}</div>
      <div style="display:grid;grid-template-columns:160px minmax(0,1fr);gap:16px;align-items:center;padding:6px 0">
        <div class="baseline"><span class="semi">All leads</span><span class="muted">${f.num(audTotal)}</span></div>${segBar(aud.total.map(s => s.leads), audTotal)}</div>
      ${aud.by_channel.map(r => html`<div style="display:grid;grid-template-columns:160px minmax(0,1fr);gap:16px;align-items:center;padding:6px 0">
        <div class="baseline" style="gap:8px"><span class="clip">${ctx.channel(r.id).name}</span><span class="muted">${f.num(r.leads)}</span></div>${segBar(aud.names.map(n => r.parts[n]), r.leads)}</div>`)}
    </div>` : ''}
    <div class="card" style="padding:18px 24px 20px">
      <div class="row" style="gap:8px;margin-bottom:${c.spend ? 12 : 6}px"><span class="title">Cost per step</span>
        ${info('How much money we spent to get one of each. Example: money spent divided by number of leads gives the cost of one lead.')}</div>
      ${c.spend ? html`<div class="grid" style="grid-template-columns:repeat(6,minmax(0,1fr));gap:20px">
          ${costs.map(([label, value]) => html`<div class="stack" style="gap:3px"><span style="font-size:19px;font-weight:600;letter-spacing:-0.015em">${value}</span><span class="small muted">${label}</span></div>`)}</div>
        <div class="small faint" style="margin-top:10px">Total spend ${f.money(c.spend)}</div>`
        : html`<div class="small muted">No spend is recorded for this period, so cost per lead and per deal cannot be worked out yet. They appear once an ad platform is connected.</div>`}
    </div>`;
  },
  actions: {
    mixOnly(ctx, d) { ctx.ui().mixOnly = d.arg || null; ctx.render(); },
    segOnly(ctx, d) { ctx.ui().segOnly = d.arg === '' ? null : Number(d.arg); ctx.render(); },
  },
};

import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, info, segmented, switcher } from '../ui.js';

const TABS = [['answers', 'The eight answers'], ['numbers', 'The numbers behind them']];
const SPANS = [['all', 'All deals'], ['24', 'Last 2 years'], ['12', 'Last 12 months']];
const TIPS = {
  page: 'This page looks at every deal in Zoho and asks: what kind of company actually buys from us? The answer is our ideal customer.',
  winRate: 'Out of every 100 deals that finished, how many we won. Deals still open are not counted. Higher means this kind of company buys more often.',
  value: 'The value of the middle won deal in this group: half were bigger, half were smaller. The middle is used instead of the average so one giant deal cannot change the picture.',
  days: 'For deals we won: the usual number of days from opening the deal to winning it. Half were faster, half were slower.',
  sample: 'An answer built on few deals can be luck. Meridian only names a group when it has at least 10 finished deals (for win rate) or 3 won deals (for value and speed).',
  recorded: 'To know who buys, each won deal needs its company’s industry and size written down. This bar shows how many have it. The emptier the bar, the less we can trust the answers.',
  target: 'An industry we have said we want. The list is set in Meridian’s scoring rules.',
  table: 'One row for each group. The green bar is the win rate. Use the buttons to split the deals a different way.',
};
const pc = v => Math.round(v) + '%';
const tone = (rate, base) => (rate == null ? 'ink3' : rate >= base * 1.2 ? 'pos' : rate < base * 0.6 ? 'neg' : 'ink');
const days = n => (n == null ? '—' : `${f.num(n)} day${n === 1 ? '' : 's'}`);
const basis = (r, kind = 'closed') => html`<span class="tiny faint">based on ${f.num(kind === 'won' ? r.won : r.closed)} ${kind === 'won' ? 'won' : 'finished'} deals${(kind === 'won' ? r.won : r.closed) < 30 ? ' · small sample' : ''}</span>`;

export default {
  uses: {},
  load: ctx => ctx.api.get('icp', { span: ctx.ui().span || 'all' }),

  render(d, ctx) {
    const { params } = ctx.app, ui = ctx.ui();
    const view = TABS.some(t => t[0] === params.view) ? params.view : 'answers';
    const a = d.answers, t = d.total, base = t.win_rate || 0;
    const cannot = why => html`<span class="semi" style="font-size:17px;color:var(--warn)">We cannot tell yet</span><span class="small muted pretty">${why}</span>`;
    const share = (n, of) => (of ? pc(n / of * 100) : '—');
    const missing = dim => d.won - d.recorded[dim];

    // ------------------------------------------------------------ the eight answers
    const card = (n, question, body, go) => html`<div class="card stack" style="padding:18px 20px;gap:8px">
      <div class="row" style="gap:10px"><span class="tile" style="width:26px;height:26px;font-size:12px">${n}</span><span class="title">${question}</span></div>
      <div class="stack" style="gap:5px;padding-left:36px">${body}${go ? html`<span class="link" data-act="open" data-arg="${go}" style="margin-top:2px">See the numbers</span>` : ''}</div></div>`;
    const big = text => html`<span class="semi" style="font-size:17px;letter-spacing:-0.01em">${text}</span>`;
    const next = () => {
      const moves = [];
      if (d.recorded.industry < d.won * 0.6) moves.push(['Write down the industry and size of our own customers', `${f.num(missing('industry'))} of ${f.num(d.won)} won deals have no industry. Until they do, every answer on this page is a guess from a small part of our customers.`]);
      if (a.buys) moves.push([`Put more effort behind ${a.buys.name}`, `It wins ${pc(a.buys.win_rate)} of finished deals, against ${pc(base)} overall.`]);
      a.avoid.slice(0, 2).forEach(x => moves.push([`Look hard at ${x.name}`, `${f.num(x.deals)} deals and only ${pc(x.win_rate)} won. Either change how we sell there, or spend less on it.`]));
      if (a.channel) moves.push([`Get more from ${a.channel.name.toLowerCase()}`, `It wins ${pc(a.channel.win_rate)} of finished deals. Ask what makes these leads different and copy it.`]);
      if (d.recorded.role < d.won * 0.6) moves.push(['Record the buyer’s job title', `Only ${f.num(d.recorded.role)} of ${f.num(d.won)} won deals have one, so we cannot say who to aim the ads at.`]);
      return moves.slice(0, 5);
    };
    const answers = () => html`
      <div class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr))">
        ${card(1, 'Who buys from us?', a.buys ? html`${big(`${a.buys.name}${a.buys_size ? `, and companies with ${a.buys_size.name.toLowerCase()}` : ''}`)}
          <span class="small muted pretty">${a.buys.name} wins <span class="ink medium">${pc(a.buys.win_rate)}</span> of finished deals${a.buys_size ? html`, and ${a.buys_size.name.toLowerCase()} wins <span class="ink medium">${pc(a.buys_size.win_rate)}</span>` : ''}. Across all deals it is ${pc(base)}.</span>${basis(a.buys)}`
          : cannot('Too few deals have an industry written down.'), 'industry')}
        ${card(2, 'Who is worth the most?', a.worth ? html`${big(`${a.worth.name}: ${f.moneyShort(a.worth.avg_value)} for a typical deal`)}
          <span class="small muted pretty">${a.worth_size ? html`By size, ${a.worth_size.name.toLowerCase()} pays the most: <span class="ink medium">${f.moneyShort(a.worth_size.avg_value)}</span> for a typical deal. ` : ''}Across all won deals the typical one is ${f.moneyShort(t.avg_value || 0)}${t.largest > (t.avg_value || 0) * 20 ? html`, and the largest is <span class="ink medium">${f.moneyShort(t.largest)}</span>` : ''}.</span>${basis(a.worth, 'won')}`
          : cannot('Too few won deals have an industry written down.'), 'industry')}
        ${card(3, 'Who buys fastest?', a.fastest ? html`${big(`${a.fastest.name}: about ${days(a.fastest.median_days)}`)}
          <span class="small muted pretty">${a.fastest_channel ? html`By channel, ${a.fastest_channel.name.toLowerCase()} is quickest at about <span class="ink medium">${days(a.fastest_channel.median_days)}</span>. ` : ''}Across all won deals it takes about ${days(t.median_days)}.</span>${basis(a.fastest, 'won')}`
          : cannot('Too few won deals have an industry written down.'), 'industry')}
        ${card(4, 'Who takes effort and rarely buys?', a.avoid.length ? html`${big(a.avoid.slice(0, 3).map(x => x.name).join(', '))}
          ${a.avoid.map(x => html`<span class="small muted">${x.dim}: <span class="ink medium">${x.name}</span> · ${f.num(x.deals)} deals, only <span style="color:var(--neg)">${pc(x.win_rate)}</span> won</span>`)}`
          : html`${big('Nothing stands out')}<span class="small muted">No group with 15 or more finished deals wins far less than the rest.</span>`, 'industry')}
        ${card(5, 'Where do the good ones come from?', a.channel ? html`${big(`${a.channel.name}: ${pc(a.channel.win_rate)} won`)}
          <span class="small muted pretty">${a.channel_value ? html`${a.channel_value.name} also brought the most money: <span class="ink medium">${f.moneyShort(a.channel_value.won_value)}</span> of ${f.moneyShort(t.won_value)} won.` : ''}</span>${basis(a.channel)}`
          : cannot('Too few finished deals have a known channel.'), 'channel')}
        ${card(6, 'Who inside the company says yes?', d.recorded.role >= d.won * 0.5 && a.role ? html`${big(a.role.name)}<span class="small muted">${f.num(a.role.won)} of ${f.num(d.recorded.role)} won deals with a job title.</span>`
          : cannot(`Only ${f.num(d.recorded.role)} of ${f.num(d.won)} won deals have the buyer’s job title.${a.role ? ` Among those few, “${a.role.name}” is the most common.` : ''}`), 'role')}
        ${card(7, 'Is the market big enough?', html`${cannot('Our own deals cannot answer this. It needs a count of how many such companies exist, from an outside list.')}
          <span class="small muted pretty">What we can see: of ${f.num(a.market.leads)} leads in the last 12 months, <span class="ink medium">${f.num(a.market.in_industry)}</span> (${share(a.market.in_industry, a.market.leads)}) were in a target industry, and <span class="ink medium">${f.num(a.market.in_both)}</span> of those had 200 or more staff.</span>`)}
        ${card(8, 'What should we do next?', html`${next().map(([title, why]) => html`<div class="stack" style="gap:1px;padding:3px 0"><span class="medium">${title}</span><span class="small muted pretty">${why}</span></div>`)}`)}
      </div>`;

    // ------------------------------------------------------------ the numbers
    const numbers = () => {
      const dim = d.dimensions[ui.dim] ? ui.dim : 'industry';
      const rows = d.tables[dim], top = Math.max(...rows.map(r => r.win_rate || 0), 1);
      const cols = 'minmax(0,1.7fr) 64px 56px 56px 56px minmax(120px,1.1fr) 100px 100px 90px';
      return html`
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 10px;gap:16px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">Deals by ${d.dimensions[dim].toLowerCase()}</span>${info(TIPS.table)}</span>
          ${switcher(Object.entries(d.dimensions).map(([arg, label]) => ({ arg, label, on: dim === arg })), 'dim')}</div>
        <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">${d.dimensions[dim]}</span><span>Deals</span><span>Won</span><span>Lost</span><span>Open</span>
          <span class="row" style="gap:5px;text-align:left">Win rate${info(TIPS.winRate)}</span><span class="row" style="gap:5px;justify-content:flex-end">Typical won${info(TIPS.value, { end: true })}</span><span>Total won</span><span class="row" style="gap:5px;justify-content:flex-end">Days${info(TIPS.days, { end: true })}</span></div>
        ${rows.map(r => { const enough = r.closed >= d.min_closed, mute = r.name === 'Not recorded' || r.name.startsWith('Other ('); return html`<div class="trow right">
          <span class="row" style="gap:8px;text-align:left;min-width:0"><span class="clip ${mute ? 'muted' : 'medium'}" title="${r.name}">${r.name}</span>${r.target ? html`<span class="pill sm" title="${TIPS.target}" style="flex:none">target</span>` : ''}</span>
          <span class="medium">${f.num(r.deals)}</span><span style="color:var(--pos)">${f.num(r.won)}</span><span class="muted">${f.num(r.lost)}</span><span class="faint">${f.num(r.open)}</span>
          <div class="row" style="gap:8px"><div class="track" style="flex:1;height:8px;border-radius:4px"><div class="fill" style="width:${r.win_rate ? Math.max(r.win_rate / top * 100, 2) : 0}%;background:var(--${enough ? tone(r.win_rate, base) === 'ink' ? 'ink2' : tone(r.win_rate, base) : 'ink3'})"></div></div>
            <span class="${enough ? 'medium' : 'faint'}" style="width:44px;text-align:right" title="${enough ? '' : 'Fewer than 10 finished deals: too few to trust'}">${r.win_rate == null ? '—' : Math.round(r.win_rate) + '%'}</span></div>
          <span class="${r.won >= d.min_won ? '' : 'faint'}">${f.orDash(r.avg_value, f.moneyShort)}</span><span class="muted">${r.won_value ? f.moneyShort(r.won_value) : '—'}</span>
          <span class="${r.won >= d.min_won ? 'muted' : 'faint'}">${r.median_days == null ? '—' : f.num(r.median_days)}</span></div>`; })}
        <div class="trow right tfoot"><span style="text-align:left">All deals</span><span>${f.num(t.deals)}</span><span>${f.num(t.won)}</span><span>${f.num(t.lost)}</span><span>${f.num(t.open)}</span>
          <span style="text-align:right">${Math.round(base)}%</span><span>${f.orDash(t.avg_value, f.moneyShort)}</span><span>${f.moneyShort(t.won_value)}</span><span>${f.orDash(t.median_days, f.num)}</span></div>
      </div>
      <div class="row small muted" style="gap:7px">Grey numbers rest on too few deals to trust${info(TIPS.sample)}</div>`;
    };

    const known = [['industry', 'Industry'], ['size', 'Company size'], ['role', 'Buyer’s job title']];
    return html`
    ${pageHead(`${f.num(t.deals)} deals · ${f.num(t.won)} won · ${f.moneyShort(t.won_value)} won in total`, 'Ideal customer', segmented(TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'view', 16))}
    <div class="row" style="gap:10px;margin:2px 0 -2px;flex-wrap:wrap"><span class="section">${TABS.find(x => x[0] === view)[1]}</span>
      <span class="row muted" style="gap:7px">Worked out from who actually bought${info(TIPS.page)}</span><span style="flex:1"></span>${switcher(SPANS.map(([arg, label]) => ({ arg, label, on: d.span === arg })), 'span')}</div>
    <div class="card" style="padding:14px 20px;display:grid;grid-template-columns:minmax(0,1.2fr) repeat(3,minmax(0,1fr));gap:22px;align-items:center">
      <div class="stack" style="gap:2px"><span class="row medium" style="gap:7px">How much we know about our customers${info(TIPS.recorded)}</span>
        <span class="small muted">Out of ${f.num(d.won)} won deals, how many have each detail written down</span></div>
      ${known.map(([dim, label]) => { const pct = d.won ? d.recorded[dim] / d.won * 100 : 0; return html`<div class="stack" style="gap:5px">
        <div class="baseline small"><span>${label}</span><span><span class="medium">${f.num(d.recorded[dim])}</span> <span class="muted">of ${f.num(d.won)}</span></span></div>
        <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${pct}%;background:var(--${pct >= 70 ? 'pos' : pct >= 40 ? 'warn' : 'neg'})"></div></div></div>`; })}
    </div>
    ${t.deals ? { answers, numbers }[view]() : html`<div class="card pad small muted">No deals in this period.</div>`}`;
  },

  actions: {
    view: (ctx, d) => ctx.setParams({ view: d.arg }),
    open(ctx, d) { ctx.ui().dim = d.arg; ctx.setParams({ view: 'numbers' }); window.scrollTo(0, 0); },
    dim(ctx, d) { ctx.ui().dim = d.arg; ctx.render(); },
    span(ctx, d) { ctx.ui().span = d.arg; ctx.reload(); },
  },
};

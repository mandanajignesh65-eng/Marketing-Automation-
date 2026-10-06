import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, info, segmented, switcher, sq } from '../ui.js';

const rate = (a, b) => (b ? a / b * 100 : null);
const change = (a, b) => (b ? (a - b) / b * 100 : null);
const sum = (rows, key) => rows.reduce((a, r) => a + r[key], 0);
const TABS = [['summary', 'Summary'], ['search', 'Google search'], ['pages', 'Pages and content'], ['rankings', 'Rankings']];
const BLURB = {
  summary: 'How many people visit, where they come from, and how many become leads',
  search: 'What people type into Google when they find us · from Search Console, 2 to 3 days behind',
  pages: 'Which pages people read, grouped by what kind of page it is',
  rankings: 'Where we stand in Google for the words we want, and who else ranks for them · from Semrush',
};
const GREEN = 'oklch(0.60 0.11 165)', BLUE = 'var(--accent)', GREY = 'var(--ink3)', VIOLET = 'oklch(0.62 0.15 300)';
const SOURCE_COLOR = { 'Came directly': 'oklch(0.56 0.07 215)', 'Google search': GREEN, 'Other search engines': 'oklch(0.74 0.09 178)', 'Social media': 'oklch(0.55 0.13 262)',
  'AI assistants': VIOLET, 'Paid ads': 'oklch(0.66 0.13 48)', Email: 'oklch(0.70 0.14 65)', 'Other websites': 'oklch(0.48 0.08 196)', 'Not known': GREY };

const TIPS = {
  visits: 'How many times people came to our website in this period. One person who comes twice counts as two visits.',
  clicks: 'How many times someone saw us in Google results and clicked to visit our website.',
  leads: 'New leads that came through the website itself: people who filled a form or talked to the chatbot. Counted from Zoho.',
  toLead: 'Out of every 100 visits, how many became a lead. Example: 2% means 2 leads for every 100 visits.',
  daily: 'One bar for each day. Use the buttons to switch between visits, Google clicks and leads.',
  sources: 'How people got to our website. "Came directly" means they typed our address or used a bookmark, which is often existing customers going to log in. "AI assistants" means a tool like ChatGPT sent them.',
  months: 'One bar for each of the last 6 months. Use the buttons to switch what is counted. This month is not finished yet.',
  shown: 'How many times we appeared in Google results. Appearing is not clicking.',
  ctr: 'Out of every 100 times Google showed us, how many times people clicked.',
  position: 'Our average place in Google results. 1 is the top. A smaller number is better. Places 1 to 10 are on the first page.',
  split: 'Some people search using our name, like "chat360 login". They already know us. Other people search for a need, like "whatsapp chatbot", and find us. Only the second kind are new people. A healthy website gets about half or more of its clicks from them.',
  splitMonths: 'Google clicks in each of the last 6 months. Use the buttons to see all clicks, only searches with our name, or only searches without our name. The last one shows if content is bringing new people.',
  buckets: 'For searches that do not use our name: how many of them show us at each place in Google. Top 3 gets most of the clicks. Beyond place 10 almost nobody sees us.',
  queries: 'The exact words people typed into Google before clicking to our site. Use the buttons to see all of them, only those with our name, or only those without.',
  near: 'Searches without our name where Google already shows us between place 4 and 20, and many people search. A small improvement to that page could bring real visits. These are the easiest wins.',
  stray: 'These are pages on a test copy of the website. Google is showing them to people. They compete with the real pages and confuse Google. The web team should hide the test site from Google.',
  types: 'All pages grouped by what they are. Views is how many times pages of that kind were opened. Google clicks is how many of those visits came from a Google search.',
  pagesList: 'Each page, with how many times it was opened. Google clicks is how many came from Google search. Place is where the page usually shows in Google, 1 is the top. Use the buttons to see one kind of page.',
  sides: 'The same numbers for each website, next to each other. Click a row to see the whole page for that website only.',
  forms: 'Every form and chatbot that brought a lead in this period. Zoho tells us the name of the form, but not which website it is on. Pick the website for each form once and Meridian remembers it. After that, leads can be counted for each website.',
  noRank: 'Rankings come from Semrush. To add them: in Semrush open Organic Research, and on the Positions and Competitors tabs click Export, then CSV. Put the files in the "semrush" folder next to the app.',
};

function bars(list, value, color, { height = 200, label, title } = {}) {
  const ax = f.axis(Math.max(...list.map(value), 1));
  const dense = list.length > 16;
  return html`<div style="display:grid;grid-template-columns:40px minmax(0,1fr);gap:0 8px">
    <div style="position:relative;height:${height}px">${ax.ticks.map(t => html`<span class="micro faint" style="position:absolute;right:0;bottom:${t / ax.max * 100}%;transform:translateY(50%)">${f.num(t)}</span>`)}</div>
    <div style="position:relative;height:${height}px">
      ${ax.ticks.map(t => html`<div style="position:absolute;left:0;right:0;bottom:${t / ax.max * 100}%;height:1px;background:var(--grid)"></div>`)}
      <div style="position:absolute;inset:0;display:flex;align-items:flex-end;gap:${dense ? 3 : 10}px">
        ${list.map(x => html`<div class="stack" style="flex:1;min-width:0;height:100%;justify-content:flex-end;gap:4px">
          ${dense ? '' : html`<span class="small medium" style="text-align:center">${f.num(value(x))}</span>`}
          <div title="${title(x)}: ${f.num(value(x))}" style="height:${value(x) / ax.max * 100}%;min-height:${value(x) ? 2 : 0}px;border-radius:${dense ? 3 : 6}px ${dense ? 3 : 6}px 1px 1px;background:${color}"></div></div>`)}
      </div>
    </div>
    <span></span>
    <div style="display:flex;gap:${dense ? 3 : 10}px;margin-top:6px">${list.map((x, i) => html`<span class="micro muted nowrap" style="flex:1;text-align:center;min-width:0;overflow:visible">${label(x, i)}</span>`)}</div>
  </div>`;
}

// One ranked list of bars: [{ name, value, color, note, title }]
function ranked(rows, { fmt = f.num, empty = 'Nothing in this period.' } = {}) {
  const top = Math.max(...rows.map(r => r.value), 1);
  return rows.length ? rows.map((r, i) => html`<div class="stack" style="gap:5px;padding:8px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
    <div class="baseline" style="gap:10px"><span class="row" style="gap:8px;min-width:0">${r.color ? sq(r.color, 10, 3) : ''}<span class="clip ${i ? '' : 'semi'}" title="${r.title || r.name}">${r.name}</span></span>
      <span class="nowrap"><span class="tiny faint">${r.note || ''}</span> <span class="${i ? 'medium' : 'semi'}" style="font-size:${i ? 13 : 15}px">${fmt(r.value)}</span></span></div>
    <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${r.value ? Math.max(r.value / top * 100, 1.2) : 0}%;background:${r.color || 'var(--ink)'}"></div></div></div>`)
    : html`<div class="small muted" style="padding:6px 0 8px">${empty}</div>`;
}

function semrushCards(s) {
  const move = k => {
    if (!k.previous || k.previous === k.position) return html`<span class="tiny faint">—</span>`;
    const up = k.position < k.previous;
    return html`<span class="tiny" style="color:var(--${up ? 'pos' : 'neg'})">${up ? '▲' : '▼'} ${Math.abs(k.position - k.previous)}</span>`;
  };
  const rows = (list, empty) => (list.length ? list.map(k => html`<div class="trow right" style="padding:9px 0">
      <div class="stack" style="text-align:left;min-width:0"><span class="medium clip" title="${k.keyword}">${k.keyword}</span><span class="tiny faint clip">${k.path}</span></div>
      <span class="nowrap">${k.position} ${move(k)}</span><span class="muted">${f.num(k.volume)}</span><span>${f.num(k.traffic)}</span></div>`)
    : html`<div class="small muted" style="padding:12px 0">${empty}</div>`);
  const head = (title, tip, end) => html`<div class="thead right" style="padding:0 0 8px;border:0"><span class="row title ink" style="gap:8px;text-align:left">${title}${info(tip, { end })}</span><span>Place</span><span>Searches</span><span>Visits</span></div>`;
  const share = s.traffic ? s.brand_traffic / s.traffic * 100 : 0;
  const facts = [[f.num(s.keywords), 'Words we rank for', 'How many different searches show our website somewhere in the first 100 Google results.'],
    [f.num(s.top3), 'In the top 3', 'How many of those searches show us in place 1, 2 or 3. These get most of the clicks.'],
    [f.num(s.top10), 'On the first page', 'How many of those searches show us in the first 10 results.'],
    [f.num(s.traffic), 'Visits a month, estimated', 'Semrush’s guess of how many visits a month these rankings bring. It is an estimate, not a count.'],
    [f.pct(share), 'From our own name', 'How much of that estimate comes from people searching our name. The rest comes from people who did not know us.']];
  return html`
    <div class="row" style="gap:10px;margin:6px 0 -2px"><span class="section">${s.domain}</span><span class="muted">Semrush, ${s.country}, export of ${s.day}</span></div>
    <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">${facts.map(([v, l, tip], i) => html`<div class="card kpi" style="padding:14px 16px">
      <span class="kpi-v md" style="font-size:26px">${v}</span><span class="row eyebrow" style="gap:7px">${l}${info(tip, { end: i > 2 })}</span></div>`)}</div>
    <div class="grid start" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
      <div class="card" style="padding:18px 20px 8px;--cols:minmax(0,1fr) 70px 64px 52px">${head('Searches bringing visits, our name aside', 'Searches that do not use our name and already bring visits. Place is where we show in Google. Searches is how many people search it each month.')}${rows(s.earning, 'No rankings outside our own name.')}</div>
      <div class="card" style="padding:18px 20px 8px;--cols:minmax(0,1fr) 70px 64px 52px">${head('Within reach: places 11 to 30', 'Searches where we are on page 2 or 3 of Google and many people search. Moving these onto page 1 would bring visits.', true)}${rows(s.within_reach, 'Nothing between places 11 and 30.')}</div>
    </div>
    ${s.competitors.length ? html`<div class="card" style="padding:18px 20px 8px;--cols:minmax(0,1fr) 120px 120px 150px">
      <div class="thead right" style="padding:0 0 8px;border:0"><span class="row title ink" style="gap:8px;text-align:left">Sites ranking for the same searches${info('Other websites that show up in Google for the same searches as us. Shared words is how many searches we both appear in. The other two numbers show how big they are in Google.')}</span><span>Shared words</span><span>Their words</span><span>Their visits a month</span></div>
      <div class="trow right" style="padding:9px 0"><span class="semi" style="text-align:left">${s.domain} <span class="tiny faint">us</span></span><span class="muted">—</span><span>${f.num(s.own.keywords)}</span><span>${f.num(s.own.traffic)}</span></div>
      ${s.competitors.map(c => html`<div class="trow right" style="padding:9px 0"><span class="clip" style="text-align:left">${c.competitor}</span><span>${f.num(c.common)}</span><span>${f.num(c.keywords)}</span><span>${f.num(c.traffic)}</span></div>`)}
    </div>` : ''}`;
}

export default {
  uses: { range: true, compare: true },
  load: ctx => ctx.api.get('web', { ...ctx.rangeParams(), site: ctx.app.params.site }),

  render(d, ctx) {
    const { params, compare: show } = ctx.app, ui = ctx.ui();
    const view = TABS.some(t => t[0] === params.view) ? params.view : 'summary';
    const kpi = (value, label, tip, delta, sub, { end = false, mode = 'up' } = {}) => html`<div class="card kpi" style="padding:16px 18px">
      <span class="kpi-v md">${value}</span><span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span>
      <span class="kpi-d">${show && delta != null ? html`<span style="color:${f.tone(delta, mode)}">${f.arrowShort(delta)}</span> <span class="faint">vs ${d.period.prev_short}</span>` : ''}${sub ? html`<span class="faint">${show && delta != null ? ' · ' : ''}${sub}</span>` : ''}</span></div>`;
    const cardHead = (title, tip, right = '') => html`<div class="baseline" style="gap:16px;flex-wrap:wrap;margin-bottom:12px"><span class="row" style="gap:8px"><span class="title">${title}</span>${info(tip)}</span>${right}</div>`;
    const pick = (key, options, fallback) => (options.includes(ui[key]) ? ui[key] : fallback);
    const sw = (key, options, on) => switcher(options.map(([arg, label, color]) => ({ arg: `${key}=${arg}`, label, color, on: on === arg })), 'set');
    const dayLabel = (x, i) => (i === 0 || x.day === 1 ? `${x.day} ${x.month}` : d.days.length <= 16 || x.day % 5 === 0 ? x.day : '');
    const METRIC = { visits: ['Visits', 'var(--ink)'], clicks: ['Google clicks', GREEN], leads: ['Leads', BLUE] };

    // ------------------------------------------------------------ summary
    const summary = () => {
      const m = pick('day', Object.keys(METRIC), 'visits'), mm = pick('month', Object.keys(METRIC), 'visits');
      const toLead = rate(d.leads.value, d.visits.value), toLeadPrev = rate(d.leads.prev, d.visits.prev);
      const total = sum(d.sources, 'visits');
      const lead = !ctx.app.shell.user || ctx.app.shell.user.admin !== false;
      const forms = d.forms.filter(x => !d.site || x.site === d.site);
      const scols = 'minmax(0,1.3fr) repeat(4,minmax(0,1fr))', fcols = 'minmax(0,1.6fr) 90px minmax(150px,1fr) 70px 80px 80px';
      return html`
      ${d.site && d.unplaced ? html`<div class="row small" style="gap:10px;padding:9px 14px;border-radius:10px;background:color-mix(in oklch, var(--warn) 12%, var(--surface))">
        <span><span class="semi">${f.num(d.unplaced)} website lead${d.unplaced === 1 ? ' is' : 's are'} not counted for any website yet.</span> Their forms have no website picked.</span>
        <span style="flex:1"></span><span class="btn xs" data-act="site" data-arg="">Pick websites for the forms</span></div>` : ''}
      <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        ${kpi(f.num(d.visits.value), 'Visits', TIPS.visits, change(d.visits.value, d.visits.prev))}
        ${kpi(f.num(d.clicks.value), 'Clicks from Google', TIPS.clicks, change(d.clicks.value, d.clicks.prev), d.visits.value ? `${f.pct(d.clicks.value / d.visits.value * 100)} of visits` : '')}
        ${kpi(f.num(d.leads.value), 'Website leads', TIPS.leads, change(d.leads.value, d.leads.prev), `${f.num(d.leads.qualified)} qualified`)}
        ${kpi(f.orDash(toLead, f.pct), 'Visits that became leads', TIPS.toLead, null, show && toLeadPrev != null ? `was ${f.pct(toLeadPrev)}` : '', { end: true })}
      </div>
      ${!d.site && d.by_site.length ? html`<div class="card clipped" style="--cols:${scols}">
        <div class="row" style="gap:8px;padding:16px 16px 10px"><span class="title">The websites side by side</span>${info(TIPS.sides)}</div>
        <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Website</span><span>Visits</span><span>Clicks from Google</span><span>Leads</span><span>Visits that became leads</span></div>
        ${d.by_site.map(x => html`<div class="trow right" data-act="site" data-arg="${x.site}" title="See only ${x.site}" style="cursor:pointer">
          <span class="medium" style="text-align:left">${x.site}</span>
          <span><span class="medium">${f.num(x.visits)}</span>${show && x.prev ? html` <span class="tiny" style="color:${f.tone(change(x.visits, x.prev))}">${f.arrowShort(change(x.visits, x.prev))}</span>` : ''}</span>
          <span>${f.num(x.clicks)}</span><span class="medium">${x.leads || !d.unplaced ? f.num(x.leads) : '—'}</span><span class="muted">${x.leads || !d.unplaced ? f.orDash(rate(x.leads, x.visits), f.pct) : '—'}</span></div>`)}
        ${d.site_ready ? '' : html`<div class="small muted" style="padding:10px 16px">Numbers for each website will fill in after the next sync.</div>`}
        ${d.unplaced ? html`<div class="small muted" style="padding:10px 16px;border-top:1px solid var(--line2)">${f.num(d.unplaced)} website lead${d.unplaced === 1 ? '' : 's'} came through forms that have no website picked yet. Pick one in “Leads by form” below.</div>` : ''}
      </div>` : ''}
      <div class="card" style="padding:18px 24px 16px">
        ${cardHead(`${METRIC[m][0]} per day`, TIPS.daily, sw('day', Object.entries(METRIC).map(([k, v]) => [k, v[0]]), m))}
        ${bars(d.days, x => x[m], METRIC[m][1], { label: dayLabel, title: x => `${x.day} ${x.month}` })}
      </div>
      <div class="grid start" style="grid-template-columns:minmax(0,1fr) minmax(0,1.15fr)">
        <div class="card" style="padding:18px 24px 12px">
          ${cardHead('Where visitors came from', TIPS.sources)}
          ${ranked(d.sources.map(s => ({ name: s.name, value: s.visits, color: SOURCE_COLOR[s.name] || GREY, title: s.top.join(', '),
            note: `${total ? f.pct(s.visits / total * 100) : ''}${show && s.prev ? ` · ${f.arrowShort(change(s.visits, s.prev))}` : ''}` })))}
        </div>
        <div class="card" style="padding:18px 24px 16px">
          ${cardHead(`${METRIC[mm][0]} per month`, TIPS.months, sw('month', Object.entries(METRIC).map(([k, v]) => [k, v[0]]), mm))}
          ${bars(d.months, x => x[mm], METRIC[mm][1], { label: x => x.label, title: x => x.label, height: 230 })}
        </div>
      </div>
      <div class="card clipped" style="--cols:${fcols}">
        <div class="baseline" style="padding:16px 16px 10px;gap:16px"><span class="row" style="gap:8px"><span class="title">Leads by form</span>${info(TIPS.forms)}</span>
          <span class="small muted">${d.site ? `Forms on ${d.site}` : 'Every form and chatbot'}</span></div>
        <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Form or chatbot</span><span style="text-align:left">Type</span><span style="text-align:left">Website it is on</span><span>Leads</span><span>Qualified</span><span>${show ? 'Change' : ''}</span></div>
        ${forms.length ? forms.map(x => { const ch = change(x.leads, x.prev); return html`<div class="trow right">
          <span class="medium clip" style="text-align:left" title="${x.name}">${x.name || 'No lead source written'}</span>
          <span class="muted" style="text-align:left">${x.kind}</span>
          <span style="text-align:left">${lead && d.sites.length ? html`<select class="input" data-change="formSite" data-source="${x.name}" style="padding:3px 8px;font-size:12px;${x.site ? '' : 'color:var(--warn)'}">
            <option value="">Not picked yet</option>${d.sites.map(site => html`<option value="${site}" ${x.site === site ? 'selected' : ''}>${site}</option>`)}</select>` : (x.site || html`<span class="faint">Not picked yet</span>`)}</span>
          <span class="medium">${f.num(x.leads)}</span><span class="muted">${f.num(x.qualified)}</span>
          <span class="small" style="color:${ch == null ? 'var(--ink3)' : f.tone(ch)}">${show ? (ch == null ? 'new' : f.arrowShort(ch)) : ''}</span></div>`; })
          : html`<div class="small muted" style="padding:14px 16px">${d.site ? `No leads came through forms on ${d.site} in this period.` : 'No website leads in this period.'}</div>`}
      </div>`;
    };

    // ------------------------------------------------------------ Google search
    const search = () => {
      const b = d.split.brand, o = d.split.other, known = b.clicks + o.clicks;
      const share = rate(o.clicks, known), ctr = rate(d.clicks.value, d.impressions.value), pos = d.position;
      const which = pick('which', ['all', 'brand', 'other'], 'all'), kind = pick('kind', ['all', 'brand', 'other'], 'other');
      const series = { all: ['All clicks', 'var(--ink)', x => x.clicks], brand: ['With our name', GREY, x => x.brand], other: ['Without our name', GREEN, x => x.other] };
      const list = d.queries.filter(q => kind === 'all' || (kind === 'brand') === q.brand).slice(0, 15);
      const moved = q => {
        if (q.position == null || q.prev_position == null || Math.abs(q.position - q.prev_position) < 0.05) return html`<span class="tiny faint">—</span>`;
        const up = q.position < q.prev_position;
        return html`<span class="tiny" style="color:var(--${up ? 'pos' : 'neg'})">${up ? '▲' : '▼'} ${Math.abs(q.position - q.prev_position).toFixed(1)}</span>`;
      };
      const qcols = 'minmax(0,1fr) 60px 76px 64px 86px';
      const qrow = q => html`<div class="trow right" style="--cols:${qcols}"><span class="row" style="gap:8px;text-align:left;min-width:0"><span class="clip medium" title="${q.query}">${q.query}</span>${q.brand ? html`<span class="pill sm" style="flex:none">our name</span>` : ''}</span>
        <span class="medium">${f.num(q.clicks)}</span><span class="muted">${f.num(q.impressions)}</span><span class="muted">${q.impressions ? f.pct(q.clicks / q.impressions * 100) : '—'}</span>
        <span class="nowrap">${f.orDash(q.position, v => v.toFixed(1))} ${show ? moved(q) : ''}</span></div>`;
      const qhead = html`<div class="thead right" style="border-top:1px solid var(--line);--cols:${qcols}"><span style="text-align:left">Search</span><span>Clicks</span><span>Times shown</span><span>Click rate</span><span>Place</span></div>`;
      return html`
      <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        ${kpi(f.num(d.clicks.value), 'Clicks from Google', TIPS.clicks, change(d.clicks.value, d.clicks.prev))}
        ${kpi(f.big(d.impressions.value), 'Times shown in Google', TIPS.shown, change(d.impressions.value, d.impressions.prev))}
        ${kpi(f.orDash(ctr, f.pct), 'Click rate', TIPS.ctr, null, show && d.impressions.prev ? `was ${f.pct(d.clicks.prev / d.impressions.prev * 100)}` : '')}
        ${kpi(f.orDash(pos.value, v => v.toFixed(1)), 'Average place in Google', TIPS.position, null,
          show && pos.value != null && pos.prev != null ? html`<span style="color:var(--${pos.value <= pos.prev ? 'pos' : 'neg'})">${pos.value <= pos.prev ? '▲ better' : '▼ worse'}</span>, was ${pos.prev.toFixed(1)}` : '', { end: true })}
      </div>
      <div class="card" style="padding:18px 24px 18px">
        ${cardHead('New people, or people who already know us?', TIPS.split, html`<span class="small muted"><span class="ink semi" style="font-size:15px">${f.orDash(share, f.pct)}</span> of clicks came from people who did not search our name</span>`)}
        <div class="mixbar" style="height:34px;border-radius:9px">
          ${b.clicks ? html`<div style="width:${b.clicks / known * 100}%;background:${GREY};font-size:12px" title="Searches with our name: ${f.num(b.clicks)} clicks">${f.num(b.clicks)}</div>` : ''}
          ${o.clicks ? html`<div style="width:${Math.max(o.clicks / known * 100, 1)}%;background:${GREEN};font-size:12px" title="Searches without our name: ${f.num(o.clicks)} clicks">${o.clicks / known > 0.06 ? f.num(o.clicks) : ''}</div>` : ''}
        </div>
        <div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;margin-top:12px">
          ${[[GREY, 'Searched our name', 'They already knew us', b, d.prev_split.brand], [GREEN, 'Did not search our name', 'New people finding us', o, d.prev_split.other]].map(([color, title, sub, x, before]) => html`
          <div class="row" style="gap:10px;align-items:flex-start">${sq(color, 12, 3)}<div class="stack" style="gap:2px;margin-top:-3px">
            <span><span class="semi">${title}</span> <span class="muted">· ${sub}</span></span>
            <span class="small muted"><span class="ink semi" style="font-size:15px">${f.num(x.clicks)}</span> clicks from ${f.num(x.queries)} different searches, shown ${f.num(x.impressions)} times
              ${show && before ? html` · <span style="color:${f.tone(change(x.clicks, before))}">${f.arrowShort(change(x.clicks, before))}</span>` : ''}</span></div></div>`)}
        </div>
        ${d.hidden_clicks ? html`<div class="tiny faint" style="margin-top:10px">Google keeps the words private for another ${f.num(d.hidden_clicks)} clicks, so they are not in either group.</div>` : ''}
      </div>
      <div class="grid start" style="grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)">
        <div class="card" style="padding:18px 24px 16px">
          ${cardHead(`${series[which][0]} per month`, TIPS.splitMonths, sw('which', Object.entries(series).map(([k, v]) => [k, v[0], k === 'all' ? null : v[1]]), which))}
          ${bars(d.months, series[which][2], series[which][1], { label: x => x.label, title: x => x.label, height: 210 })}
        </div>
        <div class="card" style="padding:18px 24px 12px">
          ${cardHead('Where Google places us', TIPS.buckets, html`<span class="small muted">searches without our name</span>`)}
          ${ranked(d.buckets.map((x, i) => ({ name: `Place ${x.label.toLowerCase()}`.replace('Place top 3', 'Top 3').replace('Place beyond 20', 'Beyond place 20'), value: x.n,
            color: `color-mix(in oklch, ${GREEN} ${[100, 72, 45, 22][i]}%, var(--surface))`, note: 'searches' })))}
        </div>
      </div>
      <div class="card clipped">
        <div class="baseline" style="padding:16px 16px 10px;gap:16px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">What people searched</span>${info(TIPS.queries)}<span class="small muted">top 15 of ${f.num(d.query_count)}</span></span>
          ${sw('kind', [['other', 'Without our name', GREEN], ['brand', 'With our name', GREY], ['all', 'All']], kind)}</div>
        ${qhead}${list.length ? list.map(qrow) : html`<div class="small muted" style="padding:14px 16px">No searches of this kind in the period.</div>`}
      </div>
      ${d.near.length ? html`<div class="card clipped">
        <div class="baseline" style="padding:16px 16px 10px;gap:16px"><span class="row" style="gap:8px"><span class="title">Easiest wins</span>${info(TIPS.near)}</span>
          <span class="small muted">Shown often, not yet near the top</span></div>
        ${qhead}${d.near.map(qrow)}
      </div>` : ''}
      ${d.stray.length ? html`<div class="card" style="padding:16px 20px 12px;border-color:color-mix(in oklch, var(--warn) 45%, var(--line))">
        <div class="row" style="gap:8px;margin-bottom:8px"><span class="dot" style="width:8px;height:8px;background:var(--warn)"></span><span class="title">Google is showing pages from a test copy of the site</span>${info(TIPS.stray)}</div>
        ${d.stray.map((x, i) => html`<div class="baseline" style="gap:12px;padding:7px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}"><span class="clip mono" title="${x.page}">${x.page}</span>
          <span class="small muted nowrap">shown <span class="ink medium">${f.num(x.impressions)}</span> times · <span class="ink medium">${f.num(x.clicks)}</span> clicks</span></div>`)}
      </div>` : ''}`;
    };

    // ------------------------------------------------------------ pages
    const pages = () => {
      const inSite = () => true;  // the page is already cut down to the chosen website
      const kinds = {};
      d.types.filter(inSite).forEach(t => { const k = kinds[t.type] = kinds[t.type] || { type: t.type, pages: 0, views: 0, prev: 0, clicks: 0 }; ['pages', 'views', 'prev', 'clicks'].forEach(x => { k[x] += t[x]; }); });
      const types = Object.values(kinds).sort((a, b) => b.views - a.views);
      const type = pick('type', types.map(t => t.type), null);
      const list = d.pages.filter(r => inSite(r) && (!type || r.type === type));
      const shownList = list.slice(0, 20), top = Math.max(...shownList.map(r => r.views), 1);
      const views = sum(types, 'views');
      const cols = 'minmax(0,1.5fr) minmax(70px,0.8fr) 70px 70px 80px 60px';
      return html`
      <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        ${kpi(f.num(views), 'Page views', 'How many times any page on the website was opened in this period.', change(views, sum(types, 'prev')))}
        ${kpi(f.num(sum(types, 'pages')), 'Pages that were read', 'How many different pages were opened at least once in this period.', null)}
        ${kpi(f.num((kinds.Blog || { views: 0 }).views), 'Blog views', 'How many times blog articles were opened.', change((kinds.Blog || { views: 0 }).views, (kinds.Blog || { prev: 0 }).prev), views ? `${f.pct((kinds.Blog || { views: 0 }).views / views * 100)} of all views` : '')}
        ${kpi(f.num((kinds['Case studies'] || { views: 0 }).views), 'Case study views', 'How many times case study pages were opened.', change((kinds['Case studies'] || { views: 0 }).views, (kinds['Case studies'] || { prev: 0 }).prev), '', { end: true })}
      </div>
      <div class="card" style="padding:18px 24px 12px">
        ${cardHead('What kind of pages people read', TIPS.types)}
        ${ranked(types.map((t, i) => ({ name: t.type, value: t.views, color: `color-mix(in oklch, var(--accent) ${Math.max(100 - i * 12, 28)}%, var(--surface))`,
          note: `${f.num(t.pages)} page${t.pages === 1 ? '' : 's'} · ${f.num(t.clicks)} Google clicks${show && t.prev ? ` · ${f.arrowShort(change(t.views, t.prev))}` : ''}` })))}
      </div>
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 10px;gap:16px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">${type || 'All pages'}</span>${info(TIPS.pagesList)}<span class="small muted">top ${f.num(shownList.length)} of ${f.num(list.length)}</span></span>
          ${sw('type', [['', 'All'], ...types.map(t => [t.type, t.type])], type || '')}</div>
        <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Page</span><span style="text-align:left">Views</span><span>Views</span><span>${show ? 'Change' : ''}</span><span>Google clicks</span><span>Place</span></div>
        ${shownList.length ? shownList.map(r => { const ch = change(r.views, r.prev); return html`<div class="trow right">
          <div class="stack" style="text-align:left;min-width:0"><span class="medium clip" title="${r.title || r.path}">${r.title || r.path}</span><span class="tiny faint clip">${r.site}${r.path}</span></div>
          <div class="track" style="height:8px;border-radius:4px;background:transparent"><div class="fill" style="width:${r.views ? Math.max(r.views / top * 100, 1.5) : 0}%;background:var(--accent)"></div></div>
          <span class="medium">${f.num(r.views)}</span>
          <span class="small" style="color:${ch == null ? 'var(--ink3)' : f.tone(ch)}">${show ? (ch == null ? (r.views ? 'new' : '—') : f.arrowShort(ch)) : ''}</span>
          <span class="muted">${f.num(r.clicks)}</span><span class="muted">${f.orDash(r.position, v => v.toFixed(1))}</span></div>`; })
          : html`<div class="small muted" style="padding:14px 16px">No pages of this kind were read in the period.</div>`}
      </div>
      ${d.elsewhere ? html`<div class="tiny faint">${f.num(d.elsewhere)} more page views were on test or copy addresses and are not counted here.</div>` : ''}`;
    };

    const ranked_sites = d.semrush ? d.semrush.sites.filter(x => !d.site || x.domain.replace(/^www\./, '') === d.site) : [];
    const rankings = () => (ranked_sites.length ? ranked_sites.map(semrushCards)
      : html`<div class="card pad row" style="gap:8px"><span class="muted">${d.site && d.semrush ? `No Semrush export has been added for ${d.site} yet.` : 'No rankings have been added yet.'}</span>${info(TIPS.noRank)}</div>`);

    return html`
    ${pageHead(show ? `${d.period.short} compared with ${d.period.prev_short}` : d.period.short, 'Website and organic', segmented(TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'view', 16))}
    <div class="row" style="gap:10px;margin:2px 0 -2px;flex-wrap:wrap"><span class="section">${TABS.find(t => t[0] === view)[1]}</span><span class="muted">${BLURB[view]}</span>
      <span style="flex:1"></span>${d.sites.length > 1 ? switcher([{ arg: '', label: 'All websites', on: !d.site }, ...d.sites.map(x => ({ arg: x, label: x, on: d.site === x }))], 'site') : ''}</div>
    ${{ summary, search, pages, rankings }[view]()}`;
  },

  actions: {
    view: (ctx, d) => ctx.setParams({ ...ctx.app.params, view: d.arg }),
    site(ctx, d) { ctx.setParams({ ...ctx.app.params, site: d.arg || null }); ctx.reload(); },
    // a chart's buttons: "which=brand" remembers the choice for that chart
    set(ctx, d) { const at = d.arg.indexOf('='); ctx.ui()[d.arg.slice(0, at)] = d.arg.slice(at + 1) || null; ctx.render(); },
  },
  changes: {
    formSite: (ctx, value, el) => ctx.save(() => ctx.api.put('web/forms', { source: el.dataset.source, site: value }), value ? `Saved. Leads from this form now count for ${value}.` : 'Saved.'),
  },
};

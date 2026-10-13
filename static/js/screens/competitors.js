import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, info, segmented, switcher, dot } from '../ui.js';

const TABS = [['signals', 'Signals'], ['social', 'Social'], ['compare', 'Compare'], ['sources', 'Sources']];
const SPANS = [[7, '7 days'], [30, '30 days'], [90, '90 days']];
const COLOR = { product: 'var(--accent)', pricing: 'oklch(0.66 0.13 48)', customers: 'oklch(0.60 0.11 165)', partnership: 'oklch(0.62 0.15 300)', funding: 'oklch(0.70 0.14 65)',
  hiring: 'oklch(0.56 0.07 215)', events: 'oklch(0.60 0.15 320)', recognition: 'oklch(0.74 0.09 178)', content: 'var(--ink3)', news: 'var(--ink2)' };
const EVIDENCE = {
  dated: ['Press, dated', 'ink2', 'Published by a news outlet, with its publication date.'],
  first_seen: ['On their site', 'warn', 'Found on the competitor’s own site. Their page shows no date, so the date is the day Meridian first saw it.'],
  verified: ['Verified', 'pos', 'Checked in the weekly competitor watch against the original source.'],
  lead: ['Unverified lead', 'neg', 'Found by search but could not be opened and read. Treat as a hint only.'],
};
const TIPS = {
  matrix: 'How many signals each competitor had in this period, by type. A darker box means more. Click a box to see just those signals.',
  weekly: 'Signals per week for the last 12 weeks. Use the buttons to look at one competitor.',
  feed: 'Every signal, newest first. Each one links to where it was found. “Outlets” is how many news sites ran the same story.',
  evidence: 'How sure we can be. Press items carry the publication date. Items from a competitor’s own site carry the day we first saw them. Verified items were checked by hand in the weekly watch.',
  seo: 'From the Semrush competitors export, India database. Shared keywords are searches where both we and they appear in Google.',
  sources: 'The pages Meridian reads for each competitor, twice a day. A link that was not there before becomes a signal. A pricing page is compared as a whole.',
  notRead: 'These cannot be read by a program without breaking the site’s rules or paying for data. Google reviews need a paid Google key. The weekly watch covers what it can of these by search.',
};
const day = iso => { const d = new Date(String(iso).slice(0, 10) + 'T00:00:00'); return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }); };
const ago = iso => { if (!iso) return 'never'; const h = (Date.now() - new Date(iso).getTime()) / 36e5; return h < 1 ? 'just now' : h < 48 ? `${Math.round(h)} h ago` : `${Math.round(h / 24)} days ago`; };
const host = url => { try { return new URL(url).hostname.replace('www.', ''); } catch (e) { return url; } };

export default {
  uses: {},
  load: ctx => ctx.api.get('competitors', { days: ctx.ui().days || 30 }),

  render(d, ctx) {
    const { params } = ctx.app, ui = ctx.ui();
    const view = TABS.some(t => t[0] === params.view) ? params.view : 'signals';
    const lead = !ctx.app.shell.user || ctx.app.shell.user.admin !== false;
    const cats = Object.entries(d.categories);
    const comp = d.competitors.find(c => String(c.id) === String(ui.comp)) || null;
    const cat = d.categories[ui.cat] ? ui.cat : null;
    const real = d.signals.filter(s => s.verification !== 'lead');
    const name = id => (d.competitors.find(c => c.id === id) || { name: '—' }).name;
    const pill = key => html`<span class="pill sm" style="flex:none"><span class="sq" style="width:8px;height:8px;border-radius:2px;background:${COLOR[key] || 'var(--ink3)'}"></span>${d.categories[key] || key}</span>`;
    const count = key => real.filter(s => s.category === key).length;
    const kpi = (value, label, sub) => html`<div class="card kpi" style="padding:16px 18px"><span class="kpi-v md">${value}</span><span class="eyebrow">${label}</span><span class="kpi-d faint">${sub}</span></div>`;
    const busiest = d.competitors.slice().sort((a, b) => b.total - a.total)[0];

    // ------------------------------------------------------------ signals
    const signals = () => {
      const top = Math.max(...d.competitors.flatMap(c => Object.values(c.counts)), 1);
      const who = d.competitors.find(c => String(c.id) === String(ui.week)) || null;
      const series = d.weeks.map((w, i) => ({ w, n: who ? who.weekly[i] : d.competitors.reduce((a, c) => a + c.weekly[i], 0) }));
      const wTop = Math.max(...series.map(x => x.n), 1);
      const leads = d.signals.filter(s => s.verification === 'lead' && (!comp || s.competitor_id === comp.id));
      const list = ui.leads ? leads : d.signals.filter(s => s.verification !== 'lead' && (!comp || s.competitor_id === comp.id) && (!cat || s.category === cat));
      const cols = '74px 110px 150px minmax(0,1fr) 130px 120px 34px';
      return html`
      <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">
        ${kpi(f.num(real.length), 'Signals', `last ${d.days} days`)}
        ${kpi(f.num(count('product')), 'Product launches', 'new products and features')}
        ${kpi(f.num(count('customers') + count('partnership')), 'Customers and partners', 'wins and tie-ups announced')}
        ${kpi(f.num(count('funding') + count('hiring')), 'Funding and people', 'money raised, senior hires')}
        ${kpi(busiest && busiest.total ? busiest.name : '—', 'Most active', busiest && busiest.total ? `${f.num(busiest.total)} signals` : 'nothing yet')}
      </div>
      <div class="grid start" style="grid-template-columns:minmax(0,1.6fr) minmax(0,1fr)">
        <div class="card" style="padding:18px 22px 18px">
          <div class="row" style="gap:8px;margin-bottom:12px"><span class="title">Activity by competitor and type</span>${info(TIPS.matrix)}</div>
          <div style="display:grid;grid-template-columns:minmax(90px,1fr) repeat(${cats.length},minmax(0,1fr));gap:5px;align-items:stretch">
            <span></span>${cats.map(([k, label]) => html`<span class="micro muted" style="text-align:center;line-height:1.2;padding-bottom:3px">${label}</span>`)}
            ${d.competitors.map(c => html`<span class="small medium clip" style="align-self:center">${c.name}</span>
              ${cats.map(([k]) => { const n = c.counts[k], on = comp && comp.id === c.id && cat === k; return html`<div data-act="cell" data-arg="${c.id}:${k}" title="${c.name} · ${d.categories[k]}: ${n}"
                style="height:38px;border-radius:7px;display:grid;place-items:center;cursor:${n ? 'pointer' : 'default'};font-weight:600;font-size:13px;
                  outline:${on ? '2px solid var(--ink)' : 'none'};background:${n ? `color-mix(in oklch, var(--accent) ${Math.round(18 + n / top * 62)}%, var(--surface2))` : 'var(--surface2)'};color:${n / top > 0.55 ? '#fff' : n ? 'var(--ink)' : 'var(--ink3)'}">${n || '·'}</div>`; })}`)}
          </div>
        </div>
        <div class="card" style="padding:18px 22px 16px">
          <div class="baseline" style="gap:10px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">Signals per week</span>${info(TIPS.weekly)}</span></div>
          <div style="margin:10px 0 0">${switcher([{ arg: `week=`, label: 'All', on: !who }, ...d.competitors.map(c => ({ arg: `week=${c.id}`, label: c.name, on: who && who.id === c.id }))], 'set')}</div>
          <div style="height:150px;display:flex;align-items:flex-end;gap:6px;margin-top:14px">
            ${series.map(x => html`<div class="stack" style="flex:1;height:100%;justify-content:flex-end;align-items:center;gap:3px" title="Week of ${day(x.w)}: ${x.n}">
              <span class="micro ${x.n ? 'medium' : 'faint'}">${x.n || ''}</span><div style="width:100%;height:${x.n / wTop * 100}%;min-height:2px;border-radius:4px 4px 1px 1px;background:var(--${x.n ? 'ink' : 'track'})"></div></div>`)}
          </div>
          <div style="display:flex;gap:6px;margin-top:5px">${series.map((x, i) => html`<span class="micro faint nowrap" style="flex:1;text-align:center;overflow:visible">${i % 3 === 0 ? day(x.w) : ''}</span>`)}</div>
        </div>
      </div>
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 10px;gap:14px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">Signal feed</span>${info(TIPS.feed)}<span class="small muted">${f.num(list.length)} shown</span></span>
          <div class="row" style="gap:10px;flex-wrap:wrap">
            ${switcher([{ arg: 'comp=', label: 'All competitors', on: !comp }, ...d.competitors.map(c => ({ arg: `comp=${c.id}`, label: c.name, on: comp && comp.id === c.id }))], 'set')}</div></div>
        <div class="row" style="padding:0 16px 12px;gap:10px;flex-wrap:wrap">${switcher([{ arg: 'cat=', label: 'All types', on: !cat && !ui.leads }, ...cats.filter(([k]) => real.some(s => s.category === k)).map(([k, label]) => ({ arg: `cat=${k}`, label, color: COLOR[k], on: cat === k && !ui.leads }))], 'cat')}
          ${leads.length ? switcher([{ arg: '1', label: `Unverified leads · ${leads.length}`, on: !!ui.leads }], 'leads') : ''}</div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Date</span><span>Competitor</span><span>Type</span><span>Signal</span><span>Source</span><span class="row" style="gap:5px">Evidence${info(TIPS.evidence, { end: true })}</span><span></span></div>
        ${list.slice(0, 80).map(s => { const e = EVIDENCE[s.verification] || EVIDENCE.dated; return html`<div class="trow" style="align-items:flex-start">
          <span class="muted nowrap">${day(s.at)}</span><span class="medium">${name(s.competitor_id)}</span><span>${pill(s.category)}</span>
          <div class="stack" style="gap:2px;min-width:0"><a href="${s.url}" target="_blank" rel="noopener" class="medium pretty" style="color:var(--ink);text-decoration:none" title="Open the source">${s.title}</a>
            ${s.summary && s.summary !== s.title ? html`<span class="small muted pretty">${s.summary.length > 260 ? s.summary.slice(0, 260) + '…' : s.summary}</span>` : ''}</div>
          <div class="stack" style="gap:1px;min-width:0"><span class="small clip" title="${s.source || ''}">${s.source || host(s.url)}</span>${s.mentions > 1 ? html`<span class="tiny muted">${f.num(s.mentions)} outlets</span>` : ''}</div>
          <span class="row small" style="gap:6px;color:var(--${e[1]})" title="${e[2]}">${dot(`var(--${e[1]})`)}${e[0]}</span>
          <span>${lead ? html`<span class="tiny faint" data-act="hide" data-arg="${s.id}" style="cursor:pointer" title="Not relevant: take it off the list">✕</span>` : ''}</span></div>`; })}
        ${list.length ? '' : html`<div class="small muted" style="padding:16px">${d.synced_at ? 'No signals of this kind in the period.' : 'Nothing has been read yet. The first read happens with the next sync.'}</div>`}
        ${list.length > 80 ? html`<div class="small muted" style="padding:12px 16px">Showing the newest 80. Narrow by competitor or type to see the rest.</div>` : ''}
      </div>`;
    };

    // ------------------------------------------------------------ social
    const social = () => {
      const so = d.social, nets = Object.keys(so.networks).filter(n => so.rows.some(r => r.network === n));
      if (!nets.length) return html`<div class="card pad small muted">No social pages are being read yet. Add a LinkedIn page or a YouTube channel from the Sources tab.</div>`;
      const net = nets.includes(ui.net) ? ui.net : nets[0], li = net === 'linkedin', word = li ? 'post' : 'video';
      const rows = so.rows.filter(r => r.network === net), second = li ? 'comments' : 'views';
      const all = so.posts.filter(p => p.network === net && (!comp || p.competitor_id === comp.id));
      const posts = ui.top ? all.slice().sort((a, b) => (b.likes || 0) - (a.likes || 0)) : all;
      const top = Math.max(...rows.map(r => r.posts), 1), best = k => Math.max(...rows.map(r => r[k] || 0), 0);
      const num = (r, k) => { const v = r[k] || 0, on = v && v === best(k) && rows.length > 1; return html`<span class="right ${on ? 'semi' : ''}" style="${on ? 'color:var(--pos)' : ''}">${k !== 'followers' && !r.posts ? html`<span class="faint">—</span>` : v || k !== 'followers' ? f.num(v) : html`<span class="faint">—</span>`}</span>`; };
      const cols = `minmax(0,1fr) ${li ? '110px ' : ''}minmax(0,1.4fr) 100px 100px 120px`, pcols = '74px 130px minmax(0,1fr) 80px 90px';
      return html`
      ${nets.length > 1 ? html`<div class="row">${switcher(nets.map(n => ({ arg: `net=${n}`, label: so.networks[n], on: n === net })), 'set')}</div>` : ''}
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 12px"><span class="title">${so.networks[net]}</span><span class="small muted">last ${d.days} days</span></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Competitor</span>${li ? html`<span class="right">Followers</span>` : ''}<span>${li ? 'Posts' : 'Videos posted'}</span>
          <span class="right">${li ? 'Likes' : 'Views'}</span><span class="right">${li ? 'Comments' : 'Likes'}</span><span class="right">Last ${word}</span></div>
        ${rows.map(r => html`<div class="trow"><a class="medium" href="${r.url}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none">${r.name}</a>
          ${li ? num(r, 'followers') : ''}
          <span class="row" style="gap:10px"><span style="flex:1;height:8px;border-radius:4px;background:var(--track);overflow:hidden"><span style="display:block;height:100%;width:${r.posts / top * 100}%;background:var(--ink);border-radius:4px"></span></span><span class="medium" style="width:24px;text-align:right">${f.num(r.posts)}</span></span>
          ${num(r, li ? 'likes' : 'views')}${num(r, li ? 'comments' : 'likes')}
          <span class="right muted">${r.note ? html`<span style="color:var(--warn)" title="${r.note}">Not read</span>` : r.last ? day(r.last) : '—'}</span></div>`)}
      </div>
      <div class="card clipped" style="--cols:${pcols}">
        <div class="baseline" style="padding:16px 16px 12px;gap:14px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">${li ? 'Posts' : 'Videos'}</span><span class="small muted">${f.num(posts.length)} in the last ${d.days} days</span></span>
          <div class="row" style="gap:10px;flex-wrap:wrap">${switcher([{ arg: 'top=', label: 'Newest', on: !ui.top }, { arg: 'top=1', label: 'Most liked', on: !!ui.top }], 'set')}
          ${switcher([{ arg: 'comp=', label: 'All competitors', on: !comp }, ...d.competitors.filter(c => rows.some(r => r.competitor_id === c.id)).map(c => ({ arg: `comp=${c.id}`, label: c.name, on: comp && comp.id === c.id }))], 'set')}</div></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Date</span><span>Competitor</span><span>${li ? 'Post' : 'Video'}</span><span class="right">${li ? 'Likes' : 'Views'}</span><span class="right">${li ? 'Comments' : 'Likes'}</span></div>
        ${posts.slice(0, 60).map(p => html`<div class="trow"><span class="muted nowrap">${day(p.posted_at)}</span><span class="medium">${name(p.competitor_id)}</span>
          <span class="row" style="gap:8px;min-width:0"><a href="${p.url}" target="_blank" rel="noopener" class="medium clip" style="color:var(--ink);text-decoration:none" title="${p.title}">${p.title}</a>${p.kind && !['Video', 'Text'].includes(p.kind) || (li && p.kind === 'Video') ? html`<span class="pill sm" style="flex:none">${p.kind}</span>` : ''}</span>
          <span class="right">${f.num((li ? p.likes : p.views) || 0)}</span><span class="right">${f.num((li ? p.comments : p.likes) || 0)}</span></div>`)}
        ${posts.length ? '' : html`<div class="small muted" style="padding:16px">Nothing posted in this period.</div>`}
      </div>`;
    };

    // ------------------------------------------------------------ compare
    const compare = () => {
      const cols = `minmax(120px,1.1fr) repeat(${d.competitors.length},minmax(0,1fr))`;
      const row = (label, cell, tip) => html`<div class="trow right" style="--cols:${cols}"><span class="row muted" style="gap:6px;text-align:left">${label}${tip ? info(tip) : ''}</span>${d.competitors.map(c => html`<span>${cell(c)}</span>`)}</div>`;
      const last = (c, k) => (c.last[k] ? day(c.last[k]) : html`<span class="faint">—</span>`);
      return html`
      <div class="card clipped" style="--cols:${cols}">
        <div class="thead right"><span style="text-align:left">Last ${d.days} days</span>${d.competitors.map(c => html`<span class="ink semi">${c.name}</span>`)}</div>
        ${row('All signals', c => html`<span class="semi">${f.num(c.total)}</span>`)}
        ${cats.map(([k, label]) => row(label, c => (c.counts[k] ? html`<span class="medium">${f.num(c.counts[k])}</span>` : html`<span class="faint">·</span>`)))}
      </div>
      <div class="card clipped" style="--cols:${cols}">
        <div class="thead right"><span style="text-align:left">Most recent, any period</span>${d.competitors.map(c => html`<span class="ink semi">${c.name}</span>`)}</div>
        ${row('Product launch', c => last(c, 'product'))}${row('Customer or partner', c => (c.last.customers || c.last.partnership ? day([c.last.customers, c.last.partnership].filter(Boolean).sort().pop()) : html`<span class="faint">—</span>`))}
        ${row('Funding or deal', c => last(c, 'funding'))}${row('Senior hire', c => last(c, 'hiring'))}${row('Pricing change', c => last(c, 'pricing'))}
      </div>
      <div class="card clipped" style="--cols:${cols}">
        <div class="thead right"><span class="row" style="gap:6px;text-align:left">Search presence${info(TIPS.seo)}</span>${d.competitors.map(c => html`<span class="ink semi">${c.name}</span>`)}</div>
        ${row('Keywords they rank for', c => (c.seo ? f.num(c.seo.keywords) : html`<span class="faint">—</span>`))}
        ${row('Estimated visits a month', c => (c.seo ? f.num(c.seo.traffic) : html`<span class="faint">—</span>`))}
        ${row('Keywords shared with us', c => (c.seo ? f.num(c.seo.common) : html`<span class="faint">—</span>`))}
        ${d.competitors.some(c => c.seo) ? '' : html`<div class="small muted" style="padding:12px 16px">None of these competitors is in the Semrush competitors export yet.</div>`}
      </div>
      <div class="card clipped" style="--cols:${cols}">
        <div class="thead right"><span style="text-align:left">Where to look by hand</span>${d.competitors.map(c => html`<span class="ink semi">${c.name}</span>`)}</div>
        ${row('Website', c => html`<a class="link" href="https://${c.domain}" target="_blank" rel="noopener" style="text-decoration:none">${c.domain}</a>`)}
        ${row('LinkedIn page', c => (c.linkedin ? html`<a class="link" href="${c.linkedin}" target="_blank" rel="noopener" style="text-decoration:none">Open</a>` : html`<span class="faint">—</span>`))}
        ${row('Ads running on Meta', c => html`<a class="link" href="https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IN&q=${encodeURIComponent(c.name)}" target="_blank" rel="noopener" style="text-decoration:none">Ad Library</a>`)}
      </div>`;
    };

    // ------------------------------------------------------------ sources
    const sources = () => {
      const cols = '150px minmax(0,1fr) 110px minmax(0,0.9fr) 60px';
      return html`
      <div class="row" style="gap:12px;flex-wrap:wrap"><span class="muted">Read every ${d.every_hours} hours · last read ${ago(d.synced_at)}</span><span style="flex:1"></span>
        ${lead ? html`<span class="btn" data-act="sync">Read all now</span>
          <label class="btn" style="cursor:pointer">Add weekly watch findings<input type="file" accept=".json" data-change="findings" style="display:none"></label>
          <span class="btn" data-act="addSource">Add a page</span><span class="btn primary" data-act="addCompetitor">Add competitor</span>` : ''}</div>
      ${d.competitors.map(c => html`<div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:14px 16px 10px"><span class="row" style="gap:10px"><span class="title">${c.name}</span><span class="small muted">${c.domain}</span></span>
          <span class="small" style="color:var(--${c.failing ? 'warn' : 'pos'})">${c.failing ? `${c.failing} could not be read` : 'All readable'}</span></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Feed</span><span>Address</span><span>Last read</span><span>Status</span><span></span></div>
        <div class="trow"><span class="medium">Press</span><span class="muted clip">Google News, headlines naming ${c.name}</span><span class="muted">${ago(c.press_at)}</span>
          <span class="small" style="color:var(--${c.press_note ? 'warn' : 'ink2'})">${c.press_note || (c.press_at ? 'Reading' : 'Waiting for the first read')}</span><span></span></div>
        ${c.sources.map(s => html`<div class="trow"><span class="medium">${d.kinds[s.kind] || s.kind}</span><a class="link clip" href="${s.url}" target="_blank" rel="noopener" style="text-decoration:none" title="${s.url}">${s.url.replace(/^https?:\/\/(www\.)?/, '')}</a>
          <span class="muted">${ago(s.checked_at)}</span><span class="small" style="color:var(--${s.note ? 'warn' : 'ink2'})">${s.note ? 'Not read: ' + s.note : s.kind === 'pricing' ? 'Watching for changes' : s.baseline_at ? 'Watching for new links' : 'Waiting for the first read'}</span>
          <span class="right">${lead ? html`<span class="tiny faint" data-act="removeSource" data-arg="${s.id}" style="cursor:pointer" title="Stop reading this page">Remove</span>` : ''}</span></div>`)}
        ${d.social.accounts.filter(a => a.competitor_id === c.id).map(a => html`<div class="trow"><span class="medium">${d.social.networks[a.network] || a.network}</span><a class="link clip" href="${a.url}" target="_blank" rel="noopener" style="text-decoration:none" title="${a.url}">${a.url.replace(/^https?:\/\/(www\.)?/, '')}</a>
          <span class="muted">${ago(a.checked_at)}</span><span class="small" style="color:var(--${a.note ? 'warn' : 'ink2'})">${a.note ? 'Not read: ' + a.note : a.checked_at ? (a.network === 'linkedin' ? 'Reading new posts, once a day' : 'Reading new videos') : 'Waiting for the first read'}</span>
          <span class="right">${lead ? html`<span class="tiny faint" data-act="removeAccount" data-arg="${a.id}" style="cursor:pointer" title="Stop reading this page">Remove</span>` : ''}</span></div>`)}
      </div>`)}
      <div class="card pad stack" style="gap:8px">
        <div class="row" style="gap:8px"><span class="title">Not read automatically</span>${info(TIPS.notRead)}</div>
        <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr));gap:18px">
          ${[['Instagram, Facebook and X', 'These show nothing without signing in. Instagram can be added once the Meta account is connected.'],
            ['Google reviews', 'Needs a Google Places key, which is billed by Google. Can be added if you want it.'],
            ['Website traffic', 'Only what the Semrush export gives. Add a fresh competitors export on the Website page to update it.']]
            .map(([t, x]) => html`<div class="stack" style="gap:3px"><span class="medium">${t}</span><span class="small muted pretty">${x}</span></div>`)}
        </div>
      </div>`;
    };

    return html`
    ${pageHead(`${f.num(d.competitors.length)} competitors · ${f.num(d.competitors.reduce((a, c) => a + c.sources.length + 1, 0))} feeds read · last read ${ago(d.synced_at)}`, 'Competitors',
      html`<div class="row" style="gap:10px">${view === 'sources' ? '' : switcher(SPANS.map(([arg, label]) => ({ arg, label, on: d.days === arg })), 'days')}${segmented(TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'view', 16)}</div>`)}
    ${d.competitors.length ? { signals, social, compare, sources }[view]() : html`<div class="card pad small muted">No competitors are being watched yet.</div>`}`;
  },

  modal(m, ctx) {
    const d = ctx.app.data;
    if (m.kind === 'competitor') {
      return html`<form class="modal" data-submit="saveCompetitor"><span class="section">Add a competitor</span>
        <label class="field">Name, exactly as the press writes it<input class="input" name="name" required data-autofocus placeholder="e.g. Wati"></label>
        <label class="field">Website<input class="input" name="domain" required placeholder="wati.io"></label>
        <label class="field">LinkedIn company page (optional)<input class="input" name="linkedin" placeholder="https://www.linkedin.com/company/…"></label>
        <span class="small muted">Press coverage starts with the next read. Add their newsroom, blog and pricing pages afterwards with “Add a page”.</span>
        <div class="row" style="gap:8px;justify-content:flex-end"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Add</button></div></form>`;
    }
    return html`<form class="modal" data-submit="saveSource"><span class="section">Add a page to read</span>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <label class="field">Competitor<select class="input" name="id">${d.competitors.map(c => html`<option value="${c.id}">${c.name}</option>`)}</select></label>
        <label class="field">What the page is<select class="input" name="kind">${Object.entries(d.kinds).map(([k, label]) => html`<option value="${k}">${label}</option>`)}</select></label>
      </div>
      <label class="field">Full address of the page<input class="input" name="url" type="url" required data-autofocus placeholder="https://…"></label>
      <span class="small muted">The first read records what is already on the page. After that, anything new becomes a signal. For a LinkedIn page or a YouTube channel, paste its address.</span>
      <div class="row" style="gap:8px;justify-content:flex-end"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Add</button></div></form>`;
  },

  actions: {
    view: (ctx, d) => ctx.setParams({ view: d.arg }),
    days(ctx, d) { ctx.ui().days = Number(d.arg); ctx.reload(); },
    set(ctx, d) { const at = d.arg.indexOf('='); ctx.ui()[d.arg.slice(0, at)] = d.arg.slice(at + 1) || null; ctx.render(); },
    cat(ctx, d) { Object.assign(ctx.ui(), { cat: d.arg.slice(4) || null, leads: false }); ctx.render(); },
    leads(ctx) { const ui = ctx.ui(); ui.leads = !ui.leads; ctx.render(); },
    cell(ctx, d) { const [comp, cat] = d.arg.split(':'), ui = ctx.ui(); const same = String(ui.comp) === comp && ui.cat === cat; Object.assign(ui, { comp: same ? null : comp, cat: same ? null : cat, leads: false }); ctx.render(); },
    hide: (ctx, d) => ctx.save(() => ctx.api.post('competitors', { what: 'hide', id: Number(d.arg) }), 'Taken off the list.'),
    addCompetitor: ctx => ctx.openModal({ kind: 'competitor' }),
    addSource: ctx => ctx.openModal({ kind: 'source' }),
    removeAccount: (ctx, d) => ctx.save(() => ctx.api.post('competitors', { what: 'remove_account', id: Number(d.arg) }), 'No longer read.'),
    removeSource: (ctx, d) => ctx.save(() => ctx.api.post('competitors', { what: 'remove_source', id: Number(d.arg) }), 'No longer read.'),
    async sync(ctx) { ctx.toast('Reading every feed. This takes a minute or two…'); try { const r = await ctx.api.post('competitors', { what: 'sync' }); await ctx.reload(); ctx.toast(r.message); } catch (err) { ctx.toast(err.message); } },
  },

  changes: {
    async findings(ctx, value, el) {
      const file = el.files[0];
      if (!file) return;
      try { const r = await ctx.api.post('competitors', { what: 'findings', text: await file.text() }); await ctx.reload(); ctx.toast(r.message); } catch (err) { ctx.toast(err.message); }
    },
  },

  submits: {
    async saveCompetitor(ctx, v) { const ok = await ctx.save(() => ctx.api.post('competitors', { what: 'competitor', name: v.name, domain: v.domain, linkedin: v.linkedin }), `${v.name} added.`); if (ok) ctx.closeModal(); },
    async saveSource(ctx, v) { const ok = await ctx.save(() => ctx.api.post('competitors', { what: 'source', id: Number(v.id), kind: v.kind, url: v.url }), 'Page added. It is read with the next sync.'); if (ok) ctx.closeModal(); },
  },
};

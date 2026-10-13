import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, segmented, switcher } from '../ui.js';

const TABS = [['updates', 'Updates'], ['social', 'Social'], ['compare', 'Compare'], ['sources', 'Sources']];
const SPANS = [[7, '7 days'], [30, '30 days'], [90, '90 days']];
const COLOR = { product: 'var(--accent)', pricing: 'oklch(0.66 0.13 48)', customers: 'oklch(0.60 0.11 165)', partnership: 'oklch(0.62 0.15 300)', funding: 'oklch(0.70 0.14 65)',
  hiring: 'oklch(0.56 0.07 215)', events: 'oklch(0.60 0.15 320)', recognition: 'oklch(0.74 0.09 178)', content: 'var(--ink3)', news: 'var(--ink2)' };
const day = iso => { const d = new Date(String(iso).slice(0, 10) + 'T00:00:00'); return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }); };
const ago = iso => { if (!iso) return 'never'; const h = (Date.now() - new Date(iso).getTime()) / 36e5; return h < 1 ? 'just now' : h < 48 ? `${Math.round(h)} h ago` : `${Math.round(h / 24)} days ago`; };
const host = url => { try { return new URL(url).hostname.replace('www.', ''); } catch (e) { return url; } };
const none = html`<span class="faint">—</span>`;
const bar = (n, top) => html`<span class="row" style="gap:10px"><span style="flex:1;height:8px;border-radius:4px;background:var(--track);overflow:hidden"><span style="display:block;height:100%;width:${n / top * 100}%;background:var(--ink);border-radius:4px"></span></span><span class="medium" style="width:26px;text-align:right">${f.num(n)}</span></span>`;

export default {
  uses: {},
  load: ctx => ctx.api.get('competitors', { days: ctx.ui().days || 30 }),

  render(d, ctx) {
    const { params } = ctx.app, ui = ctx.ui();
    const view = TABS.some(t => t[0] === params.view) ? params.view : 'updates';
    const lead = !ctx.app.shell.user || ctx.app.shell.user.admin !== false;
    const comp = d.competitors.find(c => String(c.id) === String(ui.comp)) || null;
    const cat = d.categories[ui.cat] ? ui.cat : null;
    const real = d.signals.filter(s => s.verification !== 'lead');
    const so = d.social, names = Object.fromEntries([...d.competitors, ...so.rows.map(r => ({ id: r.competitor_id, name: r.name }))].map(c => [c.id, c.name]));
    const pill = key => html`<span class="pill sm" style="flex:none"><span class="sq" style="width:8px;height:8px;border-radius:2px;background:${COLOR[key] || 'var(--ink3)'}"></span>${d.categories[key] || key}</span>`;
    const who = (label = 'All competitors', list = d.competitors) => switcher([{ arg: 'comp=', label, on: !ui.comp }, ...list.map(c => ({ arg: `comp=${c.id}`, label: c.name, on: String(ui.comp) === String(c.id) }))], 'set');

    // ------------------------------------------------------------ updates
    const updates = () => {
      const top = Math.max(...d.competitors.map(c => c.total), 1);
      const latest = c => real.find(s => s.competitor_id === c.id);
      const leads = d.signals.filter(s => s.verification === 'lead' && (!comp || s.competitor_id === comp.id));
      const list = ui.leads ? leads : real.filter(s => (!comp || s.competitor_id === comp.id) && (!cat || s.category === cat));
      const n = (c, ...keys) => { const v = keys.reduce((a, k) => a + (c.counts[k] || 0), 0); return html`<span class="right">${v ? f.num(v) : none}</span>`; };
      const cols = 'minmax(0,0.9fr) minmax(0,1.3fr) 80px 110px 90px 80px minmax(0,2fr)', lcols = '74px 120px 150px minmax(0,1fr) 150px 28px';
      return html`
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 12px"><span class="title">What each competitor did</span><span class="small muted">last ${d.days} days</span></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Competitor</span><span>Updates</span><span class="right">Product</span><span class="right">Customers</span><span class="right">Funding</span><span class="right">People</span><span>Latest</span></div>
        ${d.competitors.map(c => { const l = latest(c), on = comp && comp.id === c.id; return html`<div class="trow" data-act="set" data-arg="comp=${on ? '' : c.id}" style="cursor:pointer;${on ? 'background:var(--surface2)' : ''}">
          <span class="medium">${c.name}</span>${bar(c.total, top)}${n(c, 'product')}${n(c, 'customers', 'partnership')}${n(c, 'funding')}${n(c, 'hiring')}
          <span class="row" style="gap:8px;min-width:0">${l ? html`<span class="muted nowrap">${day(l.at)}</span><span class="clip" title="${l.title}">${l.title}</span>` : html`<span class="faint">Nothing in this period</span>`}</span></div>`; })}
      </div>
      <div class="card clipped" style="--cols:${lcols}">
        <div class="baseline" style="padding:16px 16px 10px;gap:14px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">${comp ? comp.name : 'All updates'}</span><span class="small muted">${f.num(list.length)}</span></span>${who()}</div>
        <div class="row" style="padding:0 16px 12px;gap:10px;flex-wrap:wrap">${switcher([{ arg: 'cat=', label: 'All types', on: !cat && !ui.leads }, ...Object.entries(d.categories).filter(([k]) => real.some(s => s.category === k)).map(([k, label]) => ({ arg: `cat=${k}`, label, color: COLOR[k], on: cat === k && !ui.leads }))], 'cat')}
          ${leads.length ? switcher([{ arg: '1', label: `Not confirmed · ${leads.length}`, on: !!ui.leads }], 'leads') : ''}</div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Date</span><span>Competitor</span><span>Type</span><span>What happened</span><span>Source</span><span></span></div>
        ${list.slice(0, 80).map(s => html`<div class="trow" style="align-items:flex-start">
          <span class="muted nowrap">${day(s.at)}</span><span class="medium">${names[s.competitor_id] || '—'}</span><span>${pill(s.category)}</span>
          <div class="stack" style="gap:2px;min-width:0"><a href="${s.url}" target="_blank" rel="noopener" class="medium pretty" style="color:var(--ink);text-decoration:none">${s.title}</a>
            ${s.summary && s.summary !== s.title ? html`<span class="small muted pretty">${s.summary.length > 260 ? s.summary.slice(0, 260) + '…' : s.summary}</span>` : ''}</div>
          <div class="stack" style="gap:1px;min-width:0"><span class="small clip muted" title="${s.source || ''}">${s.origin === 'site' ? 'Their website' : s.source || host(s.url)}</span>${s.mentions > 1 ? html`<span class="tiny muted">and ${f.num(s.mentions - 1)} more</span>` : ''}</div>
          <span>${lead ? html`<span class="tiny faint" data-act="hide" data-arg="${s.id}" style="cursor:pointer" title="Remove from the list">✕</span>` : ''}</span></div>`)}
        ${list.length ? '' : html`<div class="small muted" style="padding:16px">${d.synced_at ? 'Nothing in this period.' : 'Nothing has been read yet. The first read happens with the next sync.'}</div>`}
        ${list.length > 80 ? html`<div class="small muted" style="padding:12px 16px">Showing the newest 80. Choose a competitor or a type to see the rest.</div>` : ''}
      </div>`;
    };

    // ------------------------------------------------------------ social
    const social = () => {
      const nets = Object.keys(so.networks).filter(n => so.rows.some(r => r.network === n));
      if (!nets.length) return html`<div class="card pad small muted">No social pages are being read yet. Add a LinkedIn page or a YouTube channel from the Sources tab.</div>`;
      const net = nets.includes(ui.net) ? ui.net : nets[0], li = net === 'linkedin', word = li ? 'post' : 'video';
      const rows = so.rows.filter(r => r.network === net), mine = rows.filter(r => r.own).map(r => r.competitor_id);
      const picked = rows.find(r => String(r.competitor_id) === String(ui.comp));
      const all = so.posts.filter(p => p.network === net && (picked ? p.competitor_id === picked.competitor_id : !mine.includes(p.competitor_id)));
      const posts = ui.top ? all.slice().sort((a, b) => (b.likes || 0) - (a.likes || 0)) : all;
      const top = Math.max(...rows.map(r => r.posts), 1), best = k => Math.max(...rows.map(r => r[k] || 0), 0);
      const num = (r, k) => { const v = r[k] || 0, on = v && v === best(k) && rows.length > 1; return html`<span class="right ${on ? 'semi' : ''}" style="${on ? 'color:var(--pos)' : ''}">${v && (r.posts || k === 'followers') ? f.num(v) : none}</span>`; };
      const cols = `minmax(0,1fr) ${li ? '110px ' : ''}minmax(0,1.4fr) 100px 100px 120px`, pcols = '74px 130px minmax(0,1fr) 80px 90px';
      return html`
      ${nets.length > 1 ? html`<div class="row">${switcher(nets.map(n => ({ arg: `net=${n}`, label: so.networks[n], on: n === net })), 'set')}</div>` : ''}
      <div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:16px 16px 12px"><span class="title">${so.networks[net]}</span><span class="small muted">last ${d.days} days</span></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Page</span>${li ? html`<span class="right">Followers</span>` : ''}<span>${li ? 'Posts' : 'Videos'}</span>
          <span class="right">${li ? 'Likes' : 'Views'}</span><span class="right">${li ? 'Comments' : 'Likes'}</span><span class="right">Last ${word}</span></div>
        ${rows.map(r => html`<div class="trow" style="${r.own ? 'background:var(--surface2)' : ''}"><span class="row" style="gap:8px;min-width:0"><a class="medium clip" href="${r.url}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none">${r.name}</a>${r.own ? html`<span class="pill sm" style="flex:none">Us</span>` : ''}</span>
          ${li ? num(r, 'followers') : ''}${bar(r.posts, top)}${num(r, li ? 'likes' : 'views')}${num(r, li ? 'comments' : 'likes')}
          <span class="right muted">${r.note ? html`<span style="color:var(--warn)" title="${r.note}">Not read</span>` : r.last ? day(r.last) : '—'}</span></div>`)}
      </div>
      <div class="card clipped" style="--cols:${pcols}">
        <div class="baseline" style="padding:16px 16px 12px;gap:14px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">${picked ? picked.name : li ? 'Competitor posts' : 'Competitor videos'}</span><span class="small muted">${f.num(posts.length)}</span></span>
          <div class="row" style="gap:10px;flex-wrap:wrap">${switcher([{ arg: 'top=', label: 'Newest', on: !ui.top }, { arg: 'top=1', label: 'Most liked', on: !!ui.top }], 'set')}
          ${switcher([{ arg: 'comp=', label: 'All competitors', on: !picked }, ...rows.map(r => ({ arg: `comp=${r.competitor_id}`, label: r.name, on: picked === r }))], 'set')}</div></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Date</span><span>Page</span><span>${li ? 'Post' : 'Video'}</span><span class="right">${li ? 'Likes' : 'Views'}</span><span class="right">${li ? 'Comments' : 'Likes'}</span></div>
        ${posts.slice(0, 60).map(p => html`<div class="trow"><span class="muted nowrap">${day(p.posted_at)}</span><span class="medium">${names[p.competitor_id] || '—'}</span>
          <span class="row" style="gap:8px;min-width:0"><a href="${p.url}" target="_blank" rel="noopener" class="medium clip" style="color:var(--ink);text-decoration:none" title="${p.title}">${p.title}</a>${p.kind && p.kind !== 'Text' && (li || p.kind !== 'Video') ? html`<span class="pill sm" style="flex:none">${p.kind}</span>` : ''}</span>
          <span class="right">${f.num((li ? p.likes : p.views) || 0)}</span><span class="right">${f.num((li ? p.comments : p.likes) || 0)}</span></div>`)}
        ${posts.length ? '' : html`<div class="small muted" style="padding:16px">Nothing posted in this period.</div>`}
      </div>`;
    };

    // ------------------------------------------------------------ compare
    const compare = () => {
      const cols = `minmax(150px,1.2fr) repeat(${d.competitors.length},minmax(0,1fr))`;
      const soc = (c, net) => so.rows.find(r => r.competitor_id === c.id && r.network === net);
      const val = v => (v ? f.num(v) : none), when = v => (v ? day(v) : none);
      const row = (label, cell) => html`<div class="trow right"><span class="muted" style="text-align:left">${label}</span>${d.competitors.map(c => html`<span>${cell(c)}</span>`)}</div>`;
      const part = label => html`<div class="trow" style="background:var(--surface2)"><span class="eyebrow">${label}</span>${d.competitors.map(() => html`<span></span>`)}</div>`;
      const link = (href, text) => html`<a class="link" href="${href}" target="_blank" rel="noopener" style="text-decoration:none">${text}</a>`;
      return html`
      <div class="card clipped" style="--cols:${cols}">
        <div class="thead right"><span style="text-align:left">Last ${d.days} days</span>${d.competitors.map(c => html`<span class="ink semi">${c.name}</span>`)}</div>
        ${part('LinkedIn')}
        ${row('Followers', c => val((soc(c, 'linkedin') || {}).followers))}
        ${row('Posts', c => val((soc(c, 'linkedin') || {}).posts))}
        ${row('Likes per post', c => { const r = soc(c, 'linkedin'); return r && r.posts ? f.num(Math.round(r.likes / r.posts)) : none; })}
        ${part('YouTube')}
        ${row('Videos', c => val((soc(c, 'youtube') || {}).posts))}
        ${row('Views', c => val((soc(c, 'youtube') || {}).views))}
        ${part('Updates')}
        ${row('All updates', c => html`<span class="semi">${val(c.total)}</span>`)}
        ${row('Product', c => val(c.counts.product))}
        ${row('Customers and partners', c => val(c.counts.customers + c.counts.partnership))}
        ${row('Funding and deals', c => val(c.counts.funding))}
        ${row('People and hiring', c => val(c.counts.hiring))}
        ${row('Events', c => val(c.counts.events))}
        ${part('Last time they had')}
        ${row('A product launch', c => when(c.last.product))}
        ${row('A new customer or partner', c => when([c.last.customers, c.last.partnership].filter(Boolean).sort().pop()))}
        ${row('Funding or a deal', c => when(c.last.funding))}
        ${row('A pricing change', c => when(c.last.pricing))}
        ${d.competitors.some(c => c.seo) ? html`${part('Google search, India')}
        ${row('Keywords they rank for', c => val(c.seo && c.seo.keywords))}
        ${row('Visits a month, estimated', c => val(c.seo && c.seo.traffic))}
        ${row('Keywords shared with us', c => val(c.seo && c.seo.common))}` : ''}
        ${part('Open')}
        ${row('Website', c => link(`https://${c.domain}`, c.domain))}
        ${row('LinkedIn page', c => (c.linkedin ? link(c.linkedin, 'Open') : none))}
        ${row('Ads on Meta', c => link(`https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=IN&q=${encodeURIComponent(c.name)}`, 'Open'))}
      </div>`;
    };

    // ------------------------------------------------------------ sources
    const sources = () => {
      const cols = '150px minmax(0,1fr) 110px minmax(0,0.9fr) 60px';
      const acc = id => so.accounts.filter(a => a.competitor_id === id).map(a => html`<div class="trow"><span class="medium">${so.networks[a.network] || a.network}</span><a class="link clip" href="${a.url}" target="_blank" rel="noopener" style="text-decoration:none" title="${a.url}">${a.url.replace(/^https?:\/\/(www\.)?/, '')}</a>
          <span class="muted">${ago(a.checked_at)}</span><span class="small" style="color:var(--${a.note ? 'warn' : 'ink2'})">${a.note ? 'Not read: ' + a.note : a.checked_at ? (a.network === 'linkedin' ? 'Read once a day' : 'Reading') : 'Waiting for the first read'}</span>
          <span class="right">${lead ? html`<span class="tiny faint" data-act="removeAccount" data-arg="${a.id}" style="cursor:pointer">Remove</span>` : ''}</span></div>`);
      const ours = [...new Set(so.rows.filter(r => r.own).map(r => r.competitor_id))];
      return html`
      <div class="row" style="gap:12px;flex-wrap:wrap"><span class="muted">Read every ${d.every_hours} hours · last read ${ago(d.synced_at)}</span><span style="flex:1"></span>
        ${lead ? html`<span class="btn" data-act="sync">Read all now</span>
          <label class="btn" style="cursor:pointer">Add weekly watch findings<input type="file" accept=".json" data-change="findings" style="display:none"></label>
          <span class="btn" data-act="addSource">Add a page</span><span class="btn primary" data-act="addCompetitor">Add competitor</span>` : ''}</div>
      ${d.competitors.map(c => html`<div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:14px 16px 10px"><span class="row" style="gap:10px"><span class="title">${c.name}</span><span class="small muted">${c.domain}</span></span>
          <span class="small" style="color:var(--${c.failing ? 'warn' : 'pos'})">${c.failing ? `${c.failing} could not be read` : 'All readable'}</span></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Page</span><span>Address</span><span>Last read</span><span>Status</span><span></span></div>
        <div class="trow"><span class="medium">News</span><span class="muted clip">Google News, headlines naming ${c.name}</span><span class="muted">${ago(c.press_at)}</span>
          <span class="small" style="color:var(--${c.press_note ? 'warn' : 'ink2'})">${c.press_note || (c.press_at ? 'Reading' : 'Waiting for the first read')}</span><span></span></div>
        ${c.sources.map(s => html`<div class="trow"><span class="medium">${d.kinds[s.kind] || s.kind}</span><a class="link clip" href="${s.url}" target="_blank" rel="noopener" style="text-decoration:none" title="${s.url}">${s.url.replace(/^https?:\/\/(www\.)?/, '')}</a>
          <span class="muted">${ago(s.checked_at)}</span><span class="small" style="color:var(--${s.note ? 'warn' : 'ink2'})">${s.note ? 'Not read: ' + s.note : s.baseline_at || s.kind === 'pricing' ? 'Reading' : 'Waiting for the first read'}</span>
          <span class="right">${lead ? html`<span class="tiny faint" data-act="removeSource" data-arg="${s.id}" style="cursor:pointer">Remove</span>` : ''}</span></div>`)}
        ${acc(c.id)}
      </div>`)}
      ${ours.length ? html`<div class="card clipped" style="--cols:${cols}">
        <div class="baseline" style="padding:14px 16px 10px"><span class="row" style="gap:10px"><span class="title">Chat360</span><span class="small muted">our own pages, for comparison</span></span></div>
        <div class="thead" style="border-top:1px solid var(--line)"><span>Page</span><span>Address</span><span>Last read</span><span>Status</span><span></span></div>${ours.map(acc)}</div>` : ''}
      <div class="card pad stack" style="gap:8px">
        <span class="title">Not read</span>
        <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr));gap:18px">
          ${[['Instagram, Facebook and X', 'These show nothing without signing in. Instagram can be added once the Meta account is connected.'],
            ['Google reviews', 'Needs a Google Places key, which is billed by Google.'],
            ['Website traffic', 'Only what the Semrush export gives. Add a fresh competitors export on the Website page to update it.']]
            .map(([t, x]) => html`<div class="stack" style="gap:3px"><span class="medium">${t}</span><span class="small muted pretty">${x}</span></div>`)}
        </div>
      </div>`;
    };

    return html`
    ${pageHead(`${f.num(d.competitors.length)} competitors · last read ${ago(d.synced_at)}`, 'Competitors',
      html`<div class="row" style="gap:10px">${view === 'sources' ? '' : switcher(SPANS.map(([arg, label]) => ({ arg, label, on: d.days === arg })), 'days')}${segmented(TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'view', 16)}</div>`)}
    ${d.competitors.length ? { updates, social, compare, sources }[view]() : html`<div class="card pad small muted">No competitors are being watched yet.</div>`}`;
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
    hide: (ctx, d) => ctx.save(() => ctx.api.post('competitors', { what: 'hide', id: Number(d.arg) }), 'Removed.'),
    addCompetitor: ctx => ctx.openModal({ kind: 'competitor' }),
    addSource: ctx => ctx.openModal({ kind: 'source' }),
    removeAccount: (ctx, d) => ctx.save(() => ctx.api.post('competitors', { what: 'remove_account', id: Number(d.arg) }), 'No longer read.'),
    removeSource: (ctx, d) => ctx.save(() => ctx.api.post('competitors', { what: 'remove_source', id: Number(d.arg) }), 'No longer read.'),
    async sync(ctx) { ctx.toast('Reading every page. This takes a minute or two…'); try { const r = await ctx.api.post('competitors', { what: 'sync' }); await ctx.reload(); ctx.toast(r.message); } catch (err) { ctx.toast(err.message); } },
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

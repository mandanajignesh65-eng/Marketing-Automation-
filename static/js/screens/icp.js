import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, segmented, switcher } from '../ui.js';

const GREEN = 'var(--pos)', RED = 'var(--neg)';
const or = list => (list.length > 1 ? list.slice(0, -1).join(', ') + ' or ' + list[list.length - 1] : list[0] || '');

// One list: a name, a bar, and the win rate. The best row is green, the worst is red.
// The three lists sit side by side at one height: rows spread to fill the card, and a long list shows its best and worst until opened.
const SHORT = 5;
function winList(title, rows, foot, key, ctx) {
  const open = ctx.ui()['all_' + key];
  const shown = rows.length > SHORT && !open ? [...rows.slice(0, SHORT - 2), ...rows.slice(-2)] : rows;
  const cut = rows.length > SHORT && !open ? SHORT - 2 : -1;  // where the hidden middle rows are
  return html`<div class="card" style="padding:18px 20px 12px;display:flex;flex-direction:column">
    <div class="title" style="margin-bottom:6px">${title}</div>
    <div style="flex:1;display:flex;flex-direction:column">
    ${shown.map((r, i) => { const color = rows.length > 1 && r === rows[0] ? GREEN : rows.length > 1 && r === rows[rows.length - 1] ? RED : 'var(--ink)'; return html`
      <div style="flex:1;display:grid;grid-template-columns:minmax(0,1fr) 44px;gap:5px 10px;align-content:center;align-items:center;padding:10px 0;border-top:${i ? `1px ${i === cut ? 'dashed var(--line)' : 'solid var(--line2)'}` : 'none'}">
        <span class="baseline" style="gap:10px"><span class="medium clip">${r.name}</span><span class="tiny faint nowrap">from ${f.num(r.deals)} deals</span></span>
        <span class="semi right" style="font-size:16px;color:${color};grid-row:span 2">${r.per_100}%</span>
        <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${r.per_100 ? Math.max(r.per_100, 2) : 0}%;background:${color}"></div></div>
      </div>`; })}
    ${rows.length ? '' : html`<div class="small muted" style="padding:6px 0 12px">Not enough finished deals yet.</div>`}
    </div>
    <div class="tiny muted pretty" style="padding-top:10px;border-top:1px solid var(--line2);min-height:38px">
      ${rows.length > SHORT ? html`<span class="link" data-act="showAll" data-arg="${key}" style="font-size:11px">${open ? 'Show fewer' : `Show all ${rows.length}`}</span>${foot ? ' · ' : ''}` : ''}${foot}</div>
  </div>`;
}

const TABS = [['summary', 'Summary'], ['industries', 'Industries'], ['personas', 'Personas']];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const COLS = [['leads', 'Leads'], ['deals', 'Deals'], ['per_100', 'Win rate'], ['typical', 'Typical deal'], ['total_won', 'Total won'], ['days', 'Days to win'], ['open', 'Open now']];
const dash = html`<span class="faint">—</span>`;
const show = { leads: f.num, deals: f.num, per_100: v => v + '%', typical: f.moneyShort, total_won: f.moneyShort, days: f.num, open: f.num };
const cell = (r, k) => (r[k] == null || (k !== 'leads' && k !== 'deals' && k !== 'open' && !r[k] && k !== 'per_100') ? dash : show[k](r[k]));

// Every group side by side. Click a column to sort by it, click a row to open that group.
function compareTable(title, rows, kind, ctx) {
  const ui = ctx.ui(), sort = ui['sort_' + kind] || 'leads';
  const known = rows.filter(r => r.name !== 'Not known').sort((a, b) => (a.name === 'Other') - (b.name === 'Other') || (b[sort] ?? -1) - (a[sort] ?? -1));
  const unknown = rows.find(r => r.name === 'Not known');
  const best = Object.fromEntries(COLS.map(([k]) => [k, Math.max(...known.map(r => r[k] || 0))]));
  const cols = 'minmax(0,1.8fr) repeat(7,minmax(0,0.8fr))';
  const line = (r, quiet) => html`<div class="trow right" ${quiet ? '' : html`data-act="openSegment" data-arg="${kind}|${r.name}" style="cursor:pointer" title="Open ${r.name}"`}>
    <span class="row" style="gap:8px;text-align:left;min-width:0"><span class="clip ${quiet ? 'muted' : 'medium'}">${r.name}</span>${r.target ? html`<span class="pill sm" style="flex:none">target</span>` : ''}</span>
    ${COLS.map(([k]) => html`<span class="${quiet ? 'muted' : ''}" style="${!quiet && r[k] && r[k] === best[k] ? 'font-weight:600;color:var(--pos)' : ''}">${cell(r, k)}</span>`)}</div>`;
  return html`<div class="card clipped" style="--cols:${cols}">
    <div class="baseline" style="padding:16px 16px 10px"><span class="title">${title}</span><span class="small muted">Click a row to see everything about it</span></div>
    <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left"></span>
      ${COLS.map(([k, label]) => html`<span data-act="sort" data-arg="${kind}|${k}" style="cursor:pointer;${sort === k ? 'color:var(--ink);font-weight:600' : ''}" title="Sort by this">${label}${sort === k ? ' ↓' : ''}</span>`)}</div>
    ${(ui['all_' + kind] ? known : known.slice(0, 12)).map(r => line(r))}${unknown ? line(unknown, true) : ''}
    ${known.length > 12 ? html`<div class="small" style="padding:10px 16px;border-top:1px solid var(--line2)"><span class="link" data-act="showAll" data-arg="${kind}">${ui['all_' + kind] ? 'Show fewer' : `Show all ${known.length}`}</span></div>` : ''}
  </div>`;
}

// One group split another way, across the full width: each row with its leads, deals, win rate and money.
function breakdown(p, ctx) {
  const kinds = Object.entries(p.splits).filter(([, rows]) => rows.some(r => r.name !== 'Not known'));
  if (!kinds.length) return '';
  const pick = ctx.ui().split, kind = kinds.some(([k]) => k === pick) ? pick : kinds[0][0];
  const rows = p.splits[kind], top = Math.max(...rows.map(r => r.leads), 1);
  const best = Math.max(...rows.filter(r => r.name !== 'Not known').map(r => r.per_100 ?? -1));
  const cols = 'minmax(0,1.2fr) minmax(0,1.6fr) 70px 80px 100px 100px';
  return html`<div class="card clipped" style="--cols:${cols}">
    <div class="baseline" style="padding:16px 16px 12px;gap:14px;flex-wrap:wrap"><span class="title">${p.value} by ${p.kinds[kind].toLowerCase()}</span>
      ${switcher(kinds.map(([k]) => ({ arg: `split=${k}`, label: p.kinds[k], on: kind === k })), 'set')}</div>
    <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">${p.kinds[kind]}</span><span style="text-align:left">Leads</span><span>Deals</span><span>Win rate</span><span>Typical deal</span><span>Total won</span></div>
    ${rows.map(r => { const quiet = r.name === 'Not known'; return html`<div class="trow right">
      <span class="clip ${quiet ? 'muted' : 'medium'}" style="text-align:left" title="${r.name}">${r.name}</span>
      <div class="row" style="gap:10px"><div class="track" style="flex:1;height:8px;border-radius:4px"><div class="fill" style="width:${r.leads ? Math.max(r.leads / top * 100, 1.5) : 0}%;background:var(--${quiet ? 'ink3' : 'ink'})"></div></div>
        <span class="${quiet ? 'muted' : 'medium'}" style="width:44px;text-align:right">${f.num(r.leads)}</span></div>
      <span class="${quiet ? 'muted' : ''}">${f.num(r.deals)}</span>
      <span class="semi" style="${!quiet && r.per_100 != null && r.per_100 === best && best > 0 ? 'color:var(--pos)' : quiet ? 'color:var(--ink2)' : ''}">${r.per_100 == null ? dash : r.per_100 + '%'}</span>
      <span class="muted">${r.typical ? f.moneyShort(r.typical) : dash}</span><span class="muted">${r.total_won ? f.moneyShort(r.total_won) : dash}</span></div>`; })}
  </div>`;
}

function profile(p, ctx) {
  const g = p.figures, all = p.all, ui = ctx.ui();
  const series = ['leads', 'deals', 'won'].includes(ui.flow) ? ui.flow : 'leads';
  const top = Math.max(...p.flow.map(x => x[series]), 1);
  const tile = (value, label, sub = '') => html`<div class="card kpi" style="padding:14px 16px"><span class="kpi-v md" style="font-size:24px">${value}</span><span class="eyebrow">${label}</span><span class="kpi-d faint">${sub}</span></div>`;
  const back = p.kind === 'industry' ? ['industries', 'All industries'] : ['personas', 'All personas'];
  const SHOW = 8;  // the lists at the bottom show the same number of rows, so they line up
  const when = m => (m ? `${MONTHS[Number(m.slice(5)) - 1]} ${m.slice(0, 4)}` : '');
  const lists = [
    p.titles.length ? ['Job titles', `from ${f.num(p.titled)} leads with a title`, p.titles.slice(0, SHOW).map(x => [x.name, html`<span class="medium">${f.num(x.n)}</span>`])] : null,
    p.customers.length ? ['Deals we won', p.customer_count > SHOW ? `newest ${SHOW} of ${f.num(p.customer_count)}` : `${f.num(p.customer_count)} in all`,
      p.customers.slice(0, SHOW).map(x => [x.name, html`<span class="small muted">${when(x.month)}${x.amount ? html` · <span class="ink medium">${f.moneyShort(x.amount)}</span>` : ''}</span>`])] : null,
    p.named >= 5 ? ['What the deals were for', `from ${f.num(p.named)} deals that say it in their name`, p.bought.slice(0, SHOW).map(x => [x.name, html`<span class="small muted"><span class="ink medium">${f.num(x.deals)}</span> deals · ${f.num(x.won)} won</span>`])] : null,
  ].filter(Boolean);
  return html`
    <div class="row" style="gap:12px;margin:2px 0 -2px;flex-wrap:wrap"><span class="link" data-act="closeSegment" data-arg="${back[0]}">← ${back[1]}</span>
      <span class="section">${p.value}</span>${p.target ? html`<span class="pill sm">target</span>` : ''}<span class="muted">${p.kind_label}</span></div>
    <div class="grid" style="grid-template-columns:repeat(7,minmax(0,1fr))">
      ${tile(f.num(g.leads), 'Leads', 'last 12 months')}
      ${tile(f.num(g.deals), 'Deals', `${f.num(g.won)} won · ${f.num(g.lost)} lost`)}
      ${tile(g.per_100 == null ? '—' : g.per_100 + '%', 'Win rate', `all deals: ${all.per_100}%`)}
      ${tile(g.typical ? f.moneyShort(g.typical) : '—', 'Typical deal', `all deals: ${f.moneyShort(all.typical || 0)}`)}
      ${tile(g.total_won ? f.moneyShort(g.total_won) : '—', 'Total won', all.total_won ? `${Math.round(g.total_won / all.total_won * 100)}% of everything won` : '')}
      ${tile(g.days == null ? '—' : f.num(g.days), 'Days to win', `all deals: ${f.num(all.days || 0)}`)}
      ${tile(f.num(g.open), 'Open now', g.open_value ? `worth ${f.moneyShort(g.open_value)}` : '')}
    </div>
    <div class="grid" style="grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);align-items:stretch">
      <div class="card" style="padding:18px 22px 16px">
        <div class="baseline" style="gap:14px;flex-wrap:wrap"><span class="title">Monthly trend</span>
          ${switcher([['leads', 'Leads'], ['deals', 'Deals opened'], ['won', 'Deals won']].map(([arg, label]) => ({ arg: `flow=${arg}`, label, on: series === arg })), 'set')}</div>
        <div style="height:170px;display:flex;align-items:flex-end;gap:10px;margin-top:14px">
          ${p.flow.map(x => html`<div class="stack" style="flex:1;height:100%;justify-content:flex-end;align-items:center;gap:4px">
            <span class="small ${x[series] ? 'medium' : 'faint'}">${x[series] || ''}</span><div style="width:100%;height:${x[series] / top * 100}%;min-height:2px;border-radius:5px 5px 1px 1px;background:var(--${x[series] ? 'ink' : 'track'})"></div></div>`)}
        </div>
        <div style="display:flex;gap:10px;margin-top:6px">${p.flow.map(x => html`<span class="micro muted" style="flex:1;text-align:center">${MONTHS[Number(x.month.slice(5)) - 1]}</span>`)}</div>
      </div>
      <div class="card stack" style="padding:18px 22px;gap:14px">
        <span class="title">Lead to customer</span>
        ${[['Leads, ever', g.leads_ever, 100], ['Became a deal', g.deals, g.leads_ever ? g.deals / g.leads_ever * 100 : 0], ['Won', g.won, g.leads_ever ? g.won / g.leads_ever * 100 : 0]].map(([label, n, w], i) => html`
          <div class="stack" style="gap:5px"><div class="baseline"><span>${label}</span><span class="semi" style="font-size:16px">${f.num(n)}</span></div>
            <div class="track" style="height:10px;border-radius:5px"><div class="fill" style="width:${n ? Math.max(Math.min(w, 100), 1.5) : 0}%;background:var(--${i === 2 ? 'pos' : 'ink'})"></div></div></div>`)}
        <span class="small muted">${g.open ? `${f.num(g.open)} deals are still open.` : 'No deals are open right now.'}</span>
      </div>
    </div>
    ${breakdown(p, ctx)}
    ${lists.length ? html`<div class="grid" style="grid-template-columns:repeat(${lists.length},minmax(0,1fr));align-items:stretch">
      ${lists.map(([title, note, rows]) => html`<div class="card" style="padding:16px 20px 8px">
        <div class="baseline" style="margin-bottom:6px;gap:10px"><span class="title">${title}</span><span class="tiny muted">${note}</span></div>
        ${rows.map(([name, right], i) => html`<div class="baseline" style="padding:8px 0;border-top:${i ? '1px solid var(--line2)' : 'none'};gap:10px"><span class="clip" title="${name}">${name}</span><span class="nowrap">${right}</span></div>`)}
      </div>`)}
    </div>` : ''}`;
}

export default {
  uses: { range: true },
  async load(ctx) {
    const { view, kind, value } = ctx.app.params;
    // each view asks only for what it shows
    if (kind && value) return { seg: await ctx.api.get('icp/profile', { kind, value }) };
    if (view === 'industries' || view === 'personas') return { compare: await ctx.api.get('icp/compare') };
    return ctx.api.get('icp', ctx.rangeParams());
  },

  render(d, ctx) {
    const view = TABS.some(x => x[0] === ctx.app.params.view) ? ctx.app.params.view : 'summary';
    const head = pageHead(view === 'summary' ? 'Based on all deals in Zoho' : 'Leads are the last 12 months · deals are every deal in Zoho', 'Ideal customer',
      segmented(TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'view', 16));
    if (d.seg) return html`${head}${profile(d.seg, ctx)}`;
    if (view === 'industries' && d.compare) return html`${head}${compareTable('Industries', d.compare.industry, 'industry', ctx)}`;
    if (view === 'personas' && d.compare) return html`${head}
      ${compareTable('By department', d.compare.department, 'department', ctx)}${compareTable('By seniority', d.compare.seniority, 'seniority', ctx)}`;
    if (!d.card) return html`${head}`;
    const lead = !ctx.app.shell.user || ctx.app.shell.user.admin !== false;
    const c = d.card, t = d.lead_totals, left = d.customers - d.labelled;
    const known = d.customers ? d.labelled / d.customers * 100 : 0;
    const fact = (label, value) => html`<div class="stack" style="gap:4px;padding:0 18px;border-left:1px solid var(--line);min-width:0">
      <span class="small muted">${label}</span><span class="semi pretty" style="font-size:19px;letter-spacing:-0.015em;line-height:1.2">${value || '—'}</span></div>`;
    const widest = Math.max(...d.leads.map(r => r.total), 1);
    const part = (n, total, bg, ink) => (n ? html`<div title="${f.num(n)}" style="width:${n / total * 100}%;background:${bg};color:${ink};display:grid;place-items:center;font-size:11px;font-weight:600;overflow:hidden">${n / total > 0.09 ? f.num(n) : ''}</div>` : '');
    const stripes = 'repeating-linear-gradient(135deg, var(--track) 0 5px, var(--surface2) 5px 10px)';
    const key = (bg, text) => html`<span class="row small muted" style="gap:6px"><span style="width:11px;height:11px;border-radius:3px;background:${bg}"></span>${text}</span>`;

    return html`
    ${head}

    <div class="card" style="padding:20px 6px 16px 24px">
      <div class="title" style="margin-bottom:14px">Ideal customer profile</div>
      <div style="display:grid;grid-template-columns:1.3fr 1.1fr 1fr 0.8fr 0.8fr;margin-left:-18px">
        ${fact('Industry', or(c.industry))}${fact('Company size', c.size)}${fact('Source', c.channel)}
        ${fact('Typical deal', c.deal ? f.moneyShort(c.deal) : '')}${fact('Time to win', c.days != null ? `${f.num(c.days)} days` : '')}
      </div>
      <div class="row" style="gap:14px;margin-top:18px;padding:14px 18px 0 0;border-top:1px solid var(--line2);flex-wrap:wrap">
        <div class="track" style="width:160px;height:8px;border-radius:4px;flex:none"><div class="fill" style="width:${known}%;background:var(--${known >= 70 ? 'pos' : 'warn'})"></div></div>
        <span class="small">Built from <span class="semi">${f.num(d.labelled)}</span> of our ${f.num(d.customers)} won deals.${left ? html` <span class="muted">The other ${f.num(left)} have no industry written down.</span>` : ''}</span>
        <span style="flex:1"></span>${lead && left ? html`<span class="btn primary" data-act="label">Add the industry</span>` : ''}
      </div>
    </div>

    <div class="row" style="gap:10px;margin:6px 0 -4px;flex-wrap:wrap"><span class="section">Win rate</span><span class="muted">Win rate: deals won out of deals finished. The coloured part of each bar is won, the grey part is lost.</span></div>
    <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr));align-items:stretch">
      ${winList('By industry', d.industry, `${d.small_industries ? `${f.num(d.small_industries)} other industries have too few deals to judge. ` : ''}${d.no_industry ? `${f.num(d.no_industry)} deals have no industry written down.` : ''}`, 'w_industry', ctx)}
      ${winList('By company size', d.size, d.no_size ? `${f.num(d.no_size)} deals have no company size written down.` : '', 'w_size', ctx)}
      ${winList('By source', d.channel, 'Sources with fewer than 10 finished deals are left out.', 'w_source', ctx)}
    </div>

    <div class="card" style="padding:20px 24px 18px">
      <div class="baseline" style="gap:16px;flex-wrap:wrap"><span class="title">Leads matching the profile · ${d.period.short}</span>
        <div class="row" style="gap:16px">${key(GREEN, 'Match')}${key('var(--ink3)', 'Do not match')}${key(stripes, 'Cannot tell')}</div></div>
      <div style="font-size:22px;font-weight:600;letter-spacing:-0.02em;margin:10px 0 14px"><span style="color:${GREEN}">${f.num(t.match)}</span> of ${f.num(t.total)} leads match${t.unknown ? html`<span class="muted" style="font-weight:500">. We cannot tell for ${f.num(t.unknown)}.</span>` : '.'}</div>
      ${d.leads.map(r => html`<div style="display:grid;grid-template-columns:150px minmax(0,1fr) 50px;gap:14px;align-items:center;padding:6px 0">
        <span class="medium clip">${r.name}</span>
        <div style="display:flex;height:22px;border-radius:6px;overflow:hidden;width:${Math.max(r.total / widest * 100, 3)}%">
          ${part(r.match, r.total, GREEN, '#fff')}${part(r.other, r.total, 'var(--ink3)', '#fff')}${part(r.unknown, r.total, stripes, 'var(--ink2)')}</div>
        <span class="right muted">${f.num(r.total)}</span></div>`)}
      ${d.leads.length ? '' : html`<div class="small muted">No leads in this period.</div>`}
      <div class="row" style="gap:14px;margin-top:14px;padding-top:14px;border-top:1px solid var(--line2);flex-wrap:wrap">
        <span class="small muted pretty">A lead matches when its company is in ${or(d.targets)} and has 200 or more staff.${t.unknown ? ' We cannot tell when the company is not known.' : ''}</span>
        <span style="flex:1"></span>${t.unknown ? html`<span class="btn" data-act="unknownLeads">See these leads</span>` : ''}
      </div>
    </div>`;
  },

  modal(m, ctx) {
    const d = ctx.app.data;
    return html`<div class="modal wide" style="gap:12px">
      <div class="baseline"><span class="section">Won deals without an industry</span><span class="small muted">${f.num(d.to_label.length)} left</span></div>
      <span class="small muted">Pick the industry for each deal. It saves as you pick.</span>
      <div data-scroll="label" style="overflow-y:auto;max-height:58vh;margin:0 -8px;padding:0 8px">
        ${d.to_label.map(x => html`<div style="display:grid;grid-template-columns:minmax(0,1fr) 170px 180px;gap:10px;align-items:center;padding:7px 0;border-top:1px solid var(--line2)">
          <span class="medium clip" title="${x.name}">${x.name}</span>
          <select class="input" id="ind-${x.id}" data-change="industry" data-deal="${x.id}"><option value="">Industry</option>${d.industries.map(i => html`<option>${i}</option>`)}</select>
          <select class="input" id="size-${x.id}"><option value="">Company size</option>${d.sizes.map(s => html`<option ${x.size === s ? 'selected' : ''}>${s}</option>`)}</select>
        </div>`)}
        ${d.to_label.length ? '' : html`<div class="small muted" style="padding:14px 0">Every won deal has an industry now.</div>`}
      </div>
      <div class="row" style="justify-content:flex-end"><button type="button" class="btn primary" data-act="cancelModal">Done</button></div>
    </div>`;
  },

  actions: {
    view(ctx, d) { ctx.setParams({ view: d.arg }); ctx.reload(false); },
    set(ctx, d) { const at = d.arg.indexOf('='); ctx.ui()[d.arg.slice(0, at)] = d.arg.slice(at + 1) || null; ctx.render(); },
    showAll(ctx, d) { const ui = ctx.ui(); ui['all_' + d.arg] = !ui['all_' + d.arg]; ctx.render(); },
    sort(ctx, d) { const [kind, key] = d.arg.split('|'); ctx.ui()['sort_' + kind] = key; ctx.render(); },
    openSegment(ctx, d) { const at = d.arg.indexOf('|'); ctx.setParams({ view: ctx.app.params.view, kind: d.arg.slice(0, at), value: d.arg.slice(at + 1) }); window.scrollTo(0, 0); ctx.reload(false); },
    closeSegment(ctx, d) { ctx.setParams({ view: d.arg }); ctx.reload(false); },
    label: ctx => ctx.openModal({ label: true }),
    unknownLeads(ctx) { ctx.app.ui.leads = { ...(ctx.app.ui.leads || {}), segment: 'Company not known' }; ctx.go('leads'); },
  },

  changes: {
    industry(ctx, value, el) {
      if (!value) return null;
      const size = document.getElementById('size-' + el.dataset.deal);
      return ctx.save(() => ctx.api.post('icp/label', { id: Number(el.dataset.deal), industry: value, size: size ? size.value : '' }));
    },
  },
};

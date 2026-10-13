import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead } from '../ui.js';

const GREEN = 'var(--pos)', RED = 'var(--neg)';
const or = list => (list.length > 1 ? list.slice(0, -1).join(', ') + ' or ' + list[list.length - 1] : list[0] || '');

// One list: a name, a bar, and how many of every 100 deals were won. The best row is green, the worst is red.
function winList(title, rows) {
  const top = Math.max(...rows.map(r => r.per_100), 1);
  return html`<div class="card" style="padding:18px 20px 10px">
    <div class="title" style="margin-bottom:10px">${title}</div>
    ${rows.map((r, i) => { const color = rows.length > 1 && i === 0 ? GREEN : rows.length > 1 && i === rows.length - 1 ? RED : 'var(--ink)'; return html`
      <div style="display:grid;grid-template-columns:minmax(0,1fr) 34px;gap:4px 10px;align-items:center;padding:9px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
        <span class="baseline" style="gap:10px"><span class="medium clip">${r.name}</span><span class="tiny faint nowrap">from ${f.num(r.deals)} deals</span></span>
        <span class="semi right" style="font-size:16px;color:${color};grid-row:span 2">${r.per_100}</span>
        <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${r.per_100 ? Math.max(r.per_100 / top * 100, 2) : 0}%;background:${color}"></div></div>
      </div>`; })}
    ${rows.length ? '' : html`<div class="small muted" style="padding:6px 0 12px">Not enough finished deals yet.</div>`}
  </div>`;
}

export default {
  uses: { range: true },
  load: ctx => ctx.api.get('icp', ctx.rangeParams()),

  render(d, ctx) {
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
    ${pageHead('Worked out from every deal in Zoho', 'Ideal customer')}

    <div class="card" style="padding:20px 6px 16px 24px">
      <div class="title" style="margin-bottom:14px">Our best customer</div>
      <div style="display:grid;grid-template-columns:1.3fr 1.1fr 1fr 0.8fr 0.8fr;margin-left:-18px">
        ${fact('Industry', or(c.industry))}${fact('Company size', c.size)}${fact('Found us through', c.channel)}
        ${fact('Typical deal', c.deal ? f.moneyShort(c.deal) : '')}${fact('Time to win', c.days != null ? `${f.num(c.days)} days` : '')}
      </div>
      <div class="row" style="gap:14px;margin-top:18px;padding:14px 18px 0 0;border-top:1px solid var(--line2);flex-wrap:wrap">
        <div class="track" style="width:160px;height:8px;border-radius:4px;flex:none"><div class="fill" style="width:${known}%;background:var(--${known >= 70 ? 'pos' : 'warn'})"></div></div>
        <span class="small">Built from <span class="semi">${f.num(d.labelled)}</span> of our ${f.num(d.customers)} customers.${left ? html` <span class="muted">The other ${f.num(left)} have no industry written down.</span>` : ''}</span>
        <span style="flex:1"></span>${lead && left ? html`<span class="btn primary" data-act="label">Label customers</span>` : ''}
      </div>
    </div>

    <div class="row" style="gap:10px;margin:6px 0 -4px;flex-wrap:wrap"><span class="section">Where we win and lose</span><span class="muted">Out of every 100 finished deals, how many we win</span></div>
    <div class="grid start" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      <div class="stack" style="gap:8px">${winList('By industry', d.industry)}
        <div class="tiny muted pretty" style="padding:0 4px">${d.small_industries ? `${f.num(d.small_industries)} other industries have too few deals to judge. ` : ''}${d.no_industry ? `${f.num(d.no_industry)} deals have no industry written down, so they are not in this list.` : ''}</div></div>
      ${winList('By company size', d.size)}
      ${winList('By how they found us', d.channel)}
    </div>

    <div class="card" style="padding:20px 24px 18px">
      <div class="baseline" style="gap:16px;flex-wrap:wrap"><span class="title">Leads that match · ${d.period.short}</span>
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
      <div class="baseline"><span class="section">Label customers</span><span class="small muted">${f.num(d.to_label.length)} left</span></div>
      <span class="small muted">Pick the industry for each customer. It saves as you pick.</span>
      <div data-scroll="label" style="overflow-y:auto;max-height:58vh;margin:0 -8px;padding:0 8px">
        ${d.to_label.map(x => html`<div style="display:grid;grid-template-columns:minmax(0,1fr) 170px 180px;gap:10px;align-items:center;padding:7px 0;border-top:1px solid var(--line2)">
          <span class="medium clip" title="${x.name}">${x.name}</span>
          <select class="input" id="ind-${x.id}" data-change="industry" data-deal="${x.id}"><option value="">Industry</option>${d.industries.map(i => html`<option>${i}</option>`)}</select>
          <select class="input" id="size-${x.id}"><option value="">Company size</option>${d.sizes.map(s => html`<option ${x.size === s ? 'selected' : ''}>${s}</option>`)}</select>
        </div>`)}
        ${d.to_label.length ? '' : html`<div class="small muted" style="padding:14px 0">Every customer has an industry now.</div>`}
      </div>
      <div class="row" style="justify-content:flex-end"><button type="button" class="btn primary" data-act="cancelModal">Done</button></div>
    </div>`;
  },

  actions: {
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

import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, deltaLine } from '../ui.js';

const COLS = 'minmax(0,1.5fr) minmax(0,1.1fr) 76px 48px minmax(0,1fr) minmax(0,1.1fr)';
const renewalCost = t => (t.billing === 'Annual' && t.annual_cost ? t.annual_cost : t.monthly_cost);

export default {
  uses: { compare: true },
  load: ctx => ctx.api.get('subscriptions'),

  render(d, ctx) {
    const tools = d.tools;
    const monthly = tools.reduce((a, t) => a + t.monthly_cost, 0);
    const seats = tools.reduce((a, t) => a + (t.seats || 0), 0);
    const last = d.history.length ? d.history[d.history.length - 1].total : null;
    const next = tools.find(t => t.days != null && t.days >= 0);
    const soon = tools.filter(t => t.days != null && t.days >= 0 && t.days <= 30);
    const trend = [...d.history, { month: d.month, total: monthly }];
    const top = Math.max(...trend.map(m => m.total), 1) * 1.07;
    const first = trend[0];
    const since = first && first.total ? (monthly - first.total) / first.total * 100 : null;
    const kpi = (value, label, extra = '', color = '') => html`<div class="card kpi" style="padding:18px"><span class="kpi-v md" style="${color ? 'color:' + color : ''}">${value}</span><span class="eyebrow">${label}</span>${extra}</div>`;

    return html`
    ${pageHead('Every marketing tool we pay for', 'Subscriptions', html`<div class="btn primary" data-act="add">Add tool</div>`)}
    <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      ${kpi(f.money(monthly), 'Per month', last ? deltaLine({ value: monthly, prev: last, pct: (monthly - last) / last * 100 }, { mode: 'neutral', fmt: f.money, show: ctx.app.compare }) : '')}
      ${kpi(f.money(monthly * 12), 'Per year at current run rate')}
      ${kpi(tools.length, `Tool${tools.length === 1 ? '' : 's'} · ${f.num(seats)} seats`)}
      ${next ? kpi(`${next.days} day${next.days === 1 ? '' : 's'}`, `Until ${next.name} renews · ${f.money(renewalCost(next))}`, '', next.days <= 14 ? 'var(--warn)' : '')
        : kpi('—', 'No renewal dates set')}
    </div>
    <div class="grid start" style="grid-template-columns:minmax(0,1fr) 320px">
      <div class="card clipped" style="--cols:${COLS}">
        <div class="thead"><span>Tool</span><span>Category</span><span class="right">Monthly</span><span class="right">Seats</span><span>Owner</span><span>Renews</span></div>
        ${tools.map((t, i) => html`<div class="trow ${i ? '' : 'first'}" data-act="edit" data-arg="${t.id}" title="Edit ${t.name}">
          <span class="row" style="gap:10px;min-width:0"><span class="tile">${t.name.slice(0, 2)}</span><span class="medium clip">${t.name}</span></span>
          <span class="muted clip">${t.category || '—'}</span><span class="right medium">${f.money(t.monthly_cost)}</span><span class="right muted">${t.seats == null ? '—' : t.seats}</span>
          <span class="clip">${t.owner || '—'}</span>
          <span class="stack"><span>${t.renews_label} ${t.days != null && t.days >= 0 && t.days <= 30 ? html`<span class="small" style="color:var(--${t.days <= 14 ? 'warn' : 'ink2'})">in ${t.days} days</span>` : ''}</span>
            <span class="tiny faint">${t.billing === 'Annual' && t.annual_cost ? `Annual · ${f.money(t.annual_cost)}` : t.billing}</span></span>
        </div>`)}
        ${tools.length ? '' : html`<div class="small muted" style="padding:18px 16px">No tools yet. Add the first one to start tracking cost and renewals.</div>`}
      </div>
      <div class="stack" style="gap:12px">
        <div class="card" style="padding:18px 20px 8px">
          <div class="title" style="margin-bottom:6px">Renewing in the next 30 days</div>
          ${soon.map((t, i) => html`<div class="between" style="gap:10px;padding:10px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
            <div class="stack"><span class="medium">${t.name}</span><span class="small muted">${t.renews_label} · ${t.owner || 'no owner'}</span></div>
            <div class="stack" style="align-items:flex-end"><span class="medium">${f.money(renewalCost(t))}</span><span class="small" style="color:var(--${t.days <= 14 ? 'warn' : 'ink2'})">in ${t.days} days</span></div></div>`)}
          ${soon.length ? '' : html`<div class="small muted" style="padding:8px 0 12px">Nothing renews in the next 30 days.</div>`}
        </div>
        <div class="card stack" style="padding:18px 20px 16px;gap:12px">
          <div class="baseline"><span class="title">Monthly cost</span>${since != null && trend.length > 1 ? html`<span class="small faint">${since >= 0 ? '+' : '−'}${Math.abs(since).toFixed(1)}% since ${first.month}</span>` : ''}</div>
          <div style="height:120px;display:flex;align-items:flex-end;gap:10px">
            ${trend.map((m, i) => html`<div class="stack" style="flex:1;height:100%;justify-content:flex-end;align-items:center;gap:4px">
              <span class="micro muted">${f.money(m.total)}</span><div style="width:100%;height:${m.total / top * 100}%;border-radius:4px 4px 1px 1px;background:var(--${i === trend.length - 1 ? 'ink' : 'ink3'})"></div></div>`)}
          </div>
          <div style="display:flex;gap:10px">${trend.map(m => html`<span class="micro faint" style="flex:1;text-align:center">${m.month}</span>`)}</div>
        </div>
      </div>
    </div>`;
  },

  modal(m, ctx) {
    const t = m.tool || { billing: 'Monthly' };
    return html`<form class="modal" data-submit="saveTool">
      <span class="section">${m.tool ? 'Edit ' + t.name : 'Add a tool'}</span>
      <label class="field">Name<input class="input" name="name" value="${t.name || ''}" required data-autofocus></label>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <label class="field">Category<input class="input" name="category" value="${t.category || ''}" placeholder="e.g. Website"></label>
        <label class="field">Owner<input class="input" name="owner" value="${t.owner || ''}"></label>
        <label class="field">Monthly cost (${f.symbol()})<input class="input" name="monthly_cost" type="number" min="0" step="1" value="${t.monthly_cost == null ? '' : t.monthly_cost}" required></label>
        <label class="field">Seats<input class="input" name="seats" type="number" min="0" step="1" value="${t.seats == null ? '' : t.seats}"></label>
        <label class="field">Next renewal<input class="input" name="renews_on" type="date" value="${t.renews_on || ''}"></label>
        <label class="field">Billing<select class="input" name="billing"><option ${t.billing === 'Monthly' ? 'selected' : ''}>Monthly</option><option ${t.billing === 'Annual' ? 'selected' : ''}>Annual</option></select></label>
      </div>
      <label class="field">Email for renewal reminders<input class="input" name="email" type="email" value="${t.email || ''}" placeholder="Who should be reminded before it renews"></label>
      <label class="field">Annual cost (${f.symbol()}), if billed annually<input class="input" name="annual_cost" type="number" min="0" step="1" value="${t.annual_cost == null ? '' : t.annual_cost}"></label>
      <div class="between" style="margin-top:4px">
        ${m.tool ? html`<button type="button" class="btn danger" data-act="remove" data-arg="${t.id}">Delete</button>` : html`<span></span>`}
        <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div>
      </div>
    </form>`;
  },

  actions: {
    add: ctx => ctx.openModal({ tool: null }),
    edit: (ctx, d) => ctx.openModal({ tool: ctx.app.data.tools.find(t => String(t.id) === d.arg) }),
    async remove(ctx, d) {
      ctx.app.modal = null;
      await ctx.save(() => ctx.api.del('subscriptions/' + d.arg), 'Tool removed.');
    },
  },

  submits: {
    async saveTool(ctx, v) {
      const tool = ctx.app.modal.tool;
      const int = x => (x === '' || x == null ? null : Math.round(Number(x)));
      const body = { name: v.name, category: v.category || null, owner: v.owner || null, monthly_cost: int(v.monthly_cost) || 0,
        seats: int(v.seats), renews_on: v.renews_on || null, billing: v.billing, annual_cost: int(v.annual_cost), email: v.email || null };
      ctx.app.modal = null;
      await ctx.save(() => (tool ? ctx.api.put('subscriptions/' + tool.id, body) : ctx.api.post('subscriptions', body)), tool ? 'Saved.' : 'Tool added.');
    },
  },
};

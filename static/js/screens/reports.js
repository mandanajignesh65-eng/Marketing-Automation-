import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead } from '../ui.js';

// Short channel names for the compact table inside the report.
const SHORT = { apollo: 'Apollo', heyreach: 'HeyReach', social: 'Social' };
const paragraphs = text => text.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
const lines = text => text.split('\n').map(p => p.trim()).filter(Boolean);

export default {
  uses: {},
  load: ctx => ctx.api.get('reports'),

  render(d, ctx) {
    const k = d.kpis, r = d.report;
    const wk = (x, mode) => (x.pct == null ? '' : html`<span class="tiny" style="color:${f.tone(x.pct, mode)}">${f.arrow(x.pct)} wk/wk</span>`);
    const tiles = [[f.num(k.leads.value), 'Leads', wk(k.leads, 'up')], [f.num(k.qualified.value), 'Qualified', wk(k.qualified, 'up')],
      [f.money(k.spend.value), 'Spend', wk(k.spend, 'neutral')], [f.orDash(k.cpql.value, f.money), 'Per qualified', wk(k.cpql, 'down')]];
    const diff = n => html`<span class="tiny" style="color:var(--${n > 0 ? 'pos' : n < 0 ? 'neg' : 'ink3'})">${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n)}</span>`;
    const steps = lines(r.next_steps);

    return html`
    ${pageHead('Weekly leadership report', 'Reports', html`<div class="row" style="gap:8px"><div class="btn" data-act="test">Send test to me</div><div class="btn primary" data-act="edit">Edit summary</div></div>`)}
    <div class="grid start" style="grid-template-columns:minmax(0,1fr) 320px">
      <div style="background:var(--surface2);border:1px solid var(--line);border-radius:14px;padding:28px;display:flex;justify-content:center">
        <div class="stack" style="width:100%;max-width:640px;background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:32px 36px;gap:22px">
          <div class="between" style="align-items:center"><span class="row semi" style="gap:8px"><span style="width:18px;height:18px;border-radius:5px;background:var(--ink)"></span>${d.company} · Marketing</span>
            <span class="pill sm muted medium" style="padding:3px 8px">${d.pill}</span></div>
          <div class="stack" style="gap:4px"><span class="eyebrow">${d.week_label}</span>
            <span class="pretty" style="font-size:24px;font-weight:600;letter-spacing:-0.02em;line-height:1.2">${r.headline}</span></div>
          <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;padding:16px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)">
            ${tiles.map(([v, l, delta]) => html`<div class="stack"><span style="font-size:22px;font-weight:600;letter-spacing:-0.02em">${v}</span><span class="tiny muted">${l}</span>${delta}</div>`)}
          </div>
          <div class="stack pretty" style="gap:10px;font-size:14px;line-height:1.6">
            <span class="small semi muted">What changed and why</span>
            ${paragraphs(r.body).map(p => html`<p>${p}</p>`)}
          </div>
          <div class="stack" style="gap:8px">
            <span class="small semi muted">${d.channel_label}</span>
            <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px 16px">
              ${d.channels.map(c => html`<span class="between"><span class="clip">${SHORT[c.id] || ctx.channel(c.id).name}</span><span class="nowrap"><span class="semi">${f.num(c.leads)}</span> ${diff(c.diff)}</span></span>`)}
            </div>
          </div>
          ${steps.length ? html`<div class="stack" style="gap:6px;font-size:14px;line-height:1.55"><span class="small semi muted">Next week</span>${steps.map(s => html`<span>${s}</span>`)}</div>` : ''}
        </div>
      </div>
      <div class="stack" style="gap:12px">
        <div class="card pad stack" style="gap:10px"><span class="title">Schedule</span>
          ${d.schedule.map(([label, value]) => html`<div class="between" style="gap:12px"><span class="muted">${label}</span><span class="right">${value}</span></div>`)}</div>
        <div class="card pad stack" style="gap:10px">
          <div class="baseline"><span class="title">Recipients</span><span class="link" data-act="addRecipient">Add</span></div>
          ${d.recipients.map(x => html`<div class="between" style="gap:10px"><span class="clip">${x.name}</span>
            <span class="row muted nowrap" style="gap:8px">${x.role || ''}<span class="faint" style="cursor:pointer" data-act="removeRecipient" data-arg="${x.id}" title="Remove ${x.name}" role="button" aria-label="Remove ${x.name}">✕</span></span></div>`)}
          ${d.recipients.length ? '' : html`<span class="small muted">No recipients yet.</span>`}
        </div>
        <div class="card" style="padding:18px 20px 8px">
          <div class="title" style="margin-bottom:6px">Past reports</div>
          ${d.past.map((p, i) => html`<div class="stack" style="gap:1px;padding:9px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
            <div class="between"><span class="medium">${p.label}</span><span class="small muted">${p.opened}</span></div><span class="small muted">${p.headline}</span></div>`)}
          ${d.past.length ? '' : html`<div class="small muted" style="padding:6px 0 12px">No reports sent yet.</div>`}
        </div>
      </div>
    </div>`;
  },

  modal(m, ctx) {
    if (m.kind === 'recipient') {
      return html`<form class="modal" data-submit="saveRecipient"><span class="section">Add a recipient</span>
        <label class="field">Name or email<input class="input" name="name" required data-autofocus></label>
        <label class="field">Role<input class="input" name="role" placeholder="e.g. CEO"></label>
        <div class="row" style="gap:8px;justify-content:flex-end"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Add</button></div>
      </form>`;
    }
    const r = ctx.app.data.report;
    return html`<form class="modal wide" data-submit="saveSummary"><span class="section">Edit this week’s summary</span>
      <label class="field">Headline<input class="input" name="headline" value="${r.headline}" required></label>
      <label class="field">What changed and why (leave a blank line between paragraphs)<textarea class="input" name="body" rows="11" required>${r.body}</textarea></label>
      <label class="field">Next week (one item per line)<textarea class="input" name="next_steps" rows="4">${r.next_steps}</textarea></label>
      <div class="between"><button type="button" class="btn" data-act="redraft">Rewrite from the data</button>
        <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div></div>
    </form>`;
  },

  actions: {
    edit: ctx => ctx.openModal({ kind: 'summary' }),
    addRecipient: ctx => ctx.openModal({ kind: 'recipient' }),
    removeRecipient: (ctx, d) => ctx.save(() => ctx.api.del('reports/recipients/' + d.arg)),
    async redraft(ctx) {
      ctx.app.modal = null;
      await ctx.save(() => ctx.api.post('reports/current/redraft'), 'Summary rewritten from the current figures.');
    },
    async test(ctx) {
      try { ctx.toast((await ctx.api.post('reports/current/test')).message); } catch (err) { ctx.toast(err.message); }
    },
  },

  submits: {
    async saveSummary(ctx, v) {
      ctx.app.modal = null;
      await ctx.save(() => ctx.api.put('reports/current', v), 'Summary saved.');
    },
    async saveRecipient(ctx, v) {
      ctx.app.modal = null;
      await ctx.save(() => ctx.api.post('reports/recipients', { name: v.name, role: v.role || null }));
    },
  },
};

import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, toggle, info, segmented, switcher } from '../ui.js';

const TABS = [['open', 'Needs attention'], ['health', 'Health check'], ['rules', 'Reminders and rules']];
const BLURB = {
  open: 'Everything that is off right now, most serious first',
  health: 'Each important number, set against its benchmark and against the 30 days before',
  rules: 'Renewal reminders, and which alerts are switched on',
};
const AGAINST = { above: ['Above benchmark', 'pos'], near: ['At benchmark', 'ink2'], below: ['Below benchmark', 'neg'], too_few: ['Too few to judge', 'ink3'] };
// which section of "Needs attention" a rule's alerts go under
const SECTION = { benchmark: 'flags', trend: 'flags', drop: 'flags', cost: 'flags', budget: 'flags', renew: 'renewals', sync: 'data', r7: 'data', r3: 'data' };
const SECTIONS = [['flags', 'Red flags', 'Numbers that are under their benchmark or have dropped.'], ['renewals', 'Renewals', 'Tools whose renewal date is close or has passed.'],
  ['data', 'Data and follow-up', 'A connected tool that stopped updating, or work waiting on someone.']];
const TIPS = {
  open: 'How many alerts are open right now. An alert closes by itself when the number recovers.',
  below: 'How many numbers are clearly under their benchmark. Under means more than a tenth below it.',
  dropped: d => `How many numbers fell ${d.drop_pct}% or more compared with the 30 days before.`,
  renewal: 'The next tool that needs renewing, and how many days are left.',
  tile: 'The big number is the last 30 days. The two bars compare the 30 days before (grey) with the last 30 days (colour). The dashed line is the benchmark: a bar above the line is good.',
  benchmark: 'The benchmark is the number we expect a healthy team to reach. It starts from published averages. Click it to set your own.',
  watch: 'When this is on, you get an alert if this number goes under its benchmark or drops sharply.',
  renewals: 'You are reminded 30, 14, 7 and 3 days before each renewal, on the day, and if the date passes. The reminder shows on the dashboard, and is emailed to the address on the tool if one is set.',
  rules: 'Switch an alert off if you do not want it. Switched-off alerts never show on the dashboard.',
};
const show = (c, v) => (v == null ? '—' : c.kind === 'rate' ? f.pct(v) : f.num(v));
const days = n => (n < 0 ? `${-n} day${n === -1 ? '' : 's'} ago` : n === 0 ? 'today' : `in ${n} day${n === 1 ? '' : 's'}`);

export default {
  uses: {},
  load: ctx => ctx.api.get('alerts'),

  render(d, ctx) {
    const { params } = ctx.app, ui = ctx.ui();
    const view = TABS.some(t => t[0] === params.view) ? params.view : 'open';
    const below = d.health.filter(c => c.watch && c.against === 'below'), dropped = d.health.filter(c => c.watch && c.dropped);
    const next = d.renewals.find(r => r.days >= 0);
    const kpi = (value, label, tip, sub, tone, end) => html`<div class="card kpi" style="padding:16px 18px">
      <span class="kpi-v md" style="${tone ? `color:var(--${tone})` : ''}">${value}</span><span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span><span class="kpi-d faint">${sub}</span></div>`;

    // ------------------------------------------------------------ what needs attention
    const open = () => html`
      <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        ${kpi(f.num(d.open.length), 'Open alerts', TIPS.open, d.open.length ? 'most serious first' : 'Nothing needs attention', d.open.some(a => a.tone === 'neg') ? 'neg' : '')}
        ${kpi(f.num(below.length), 'Below benchmark', TIPS.below, `of ${d.health.filter(c => c.kind === 'rate').length} numbers with a benchmark`, below.length ? 'warn' : '')}
        ${kpi(f.num(dropped.length), 'Dropped', TIPS.dropped(d), 'against the 30 days before', dropped.length ? 'warn' : '')}
        ${kpi(next ? `${next.days} day${next.days === 1 ? '' : 's'}` : '—', 'Next renewal', TIPS.renewal, next ? next.name : 'No renewal dates set', next && next.days <= 7 ? 'neg' : next && next.days <= 14 ? 'warn' : '', true)}
      </div>
      ${SECTIONS.map(([id, title, tip]) => { const list = d.open.filter(a => (SECTION[a.rule] || 'data') === id); return html`<div class="card" style="padding:16px 22px 8px">
        <div class="baseline" style="margin-bottom:6px"><span class="row" style="gap:8px"><span class="title">${title}</span>${info(tip)}</span><span class="small muted">${list.length ? `${list.length} open` : 'All clear'}</span></div>
        ${list.length ? list.map(a => html`<div style="display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line2)">
          <span class="dot" style="width:9px;height:9px;background:var(--${a.tone});margin-top:5px;flex:none"></span>
          <div class="stack" style="flex:1;min-width:0;gap:2px"><div class="between" style="gap:12px"><span class="medium">${a.title}</span><span class="tiny faint nowrap">${a.when}</span></div>
            <div class="small muted pretty">${a.detail}</div></div></div>`)
          : html`<div class="small muted" style="padding:10px 0 14px;border-top:1px solid var(--line2)">Nothing here right now.</div>`}
      </div>`; })}`;

    // ------------------------------------------------------------ every number against its benchmark
    const tile = c => { const [label, tone] = c.kind === 'rate' ? AGAINST[c.against] : c.dropped ? ['Dropped', 'neg'] : ['No benchmark', 'ink3'];
      const top = Math.max(c.value || 0, c.prev || 0, c.benchmark || 0, 0.0001) * 1.18, h = v => Math.max((v || 0) / top * 100, v ? 3 : 0);
      const color = c.kind === 'rate' ? (c.against === 'below' ? 'var(--neg)' : c.against === 'above' ? 'var(--pos)' : 'var(--ink)') : c.dropped ? 'var(--neg)' : 'var(--ink)';
      return html`<div class="card" style="padding:16px 18px 14px;display:grid;grid-template-columns:minmax(0,1fr) 76px;gap:14px;${c.watch ? '' : 'opacity:0.6'}">
        <div class="stack" style="gap:3px;min-width:0">
          <span style="font-size:26px;font-weight:600;letter-spacing:-0.025em;line-height:1.1">${show(c, c.value)}</span>
          <span class="row" style="gap:7px"><span class="medium">${c.name}</span>${info(c.says)}</span>
          <span class="pill sm" style="align-self:flex-start;margin-top:4px;color:var(--${tone})"><span class="dot" style="background:var(--${tone})"></span>${label}</span>
          <span class="small muted" style="margin-top:6px">${c.kind === 'rate'
            ? html`Benchmark <span class="editable ink medium" data-act="edit" data-arg="${c.key}" title="Click to change the benchmark">${show(c, c.benchmark)}</span>${c.custom ? html` <span class="tiny faint">yours</span>` : ''}`
            : html`<span class="editable" data-act="edit" data-arg="${c.key}" title="Click to change the alert for this number">Compared with the 30 days before</span>`}</span>
          <span class="small muted">${c.prev == null ? 'No earlier figure' : html`Before: <span class="ink">${show(c, c.prev)}</span>${c.change != null ? html` · <span style="color:${f.tone(c.change)}">${f.arrowShort(c.change)}</span>` : ''}`}</span>
        </div>
        <div style="position:relative;height:104px;align-self:end">
          <div style="position:absolute;inset:0 0 16px 0;display:flex;gap:8px;align-items:flex-end">
            <div title="The 30 days before: ${show(c, c.prev)}" style="flex:1;height:${h(c.prev)}%;border-radius:5px 5px 0 0;background:var(--ink3);opacity:0.55"></div>
            <div title="The last 30 days: ${show(c, c.value)}" style="flex:1;height:${h(c.value)}%;border-radius:5px 5px 0 0;background:${color}"></div></div>
          ${c.kind === 'rate' ? html`<div title="Benchmark: ${show(c, c.benchmark)}" style="position:absolute;left:-4px;right:-4px;bottom:calc(16px + ${(c.benchmark / top) * 88}px);border-top:1.5px dashed var(--ink2)"></div>` : ''}
          <div class="micro faint" style="position:absolute;left:0;right:0;bottom:0;display:flex;gap:8px"><span style="flex:1;text-align:center">Before</span><span style="flex:1;text-align:center">Now</span></div>
        </div>
      </div>`; };
    const health = () => { const group = d.groups.includes(ui.group) ? ui.group : null, groups = d.groups.filter(g => !group || g === group); return html`
      <div class="row" style="gap:12px;flex-wrap:wrap"><span class="row small muted" style="gap:7px">How to read a box${info(TIPS.tile)}</span>
        <span class="row small muted" style="gap:7px">What a benchmark is${info(TIPS.benchmark)}</span><span style="flex:1"></span>
        ${switcher([{ arg: '', label: 'All', on: !group }, ...d.groups.map(g => ({ arg: g, label: g, on: group === g }))], 'group')}</div>
      ${groups.map(g => html`<div class="row" style="gap:10px;margin:8px 0 -4px"><span class="title">${g}</span>
          <span class="small muted">${d.health.filter(c => c.group === g && c.against === 'below').length} below benchmark · ${d.health.filter(c => c.group === g && c.dropped).length} dropped</span></div>
        <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(300px,1fr))">${d.health.filter(c => c.group === g).map(tile)}</div>`)}`; };

    // ------------------------------------------------------------ reminders and rules
    const rules = () => html`
      <div class="card" style="padding:16px 22px 8px">
        <div class="baseline" style="margin-bottom:6px;gap:16px;flex-wrap:wrap"><span class="row" style="gap:8px"><span class="title">Renewal reminders</span>${info(TIPS.renewals)}</span>
          <a class="link" href="#/subs" style="text-decoration:none">Add or change tools in Subscriptions</a></div>
        ${d.renewals.length ? d.renewals.map(r => html`<div style="display:grid;grid-template-columns:minmax(0,1.2fr) 150px minmax(0,1.4fr);gap:16px;align-items:center;padding:11px 0;border-top:1px solid var(--line2)">
          <div class="stack" style="gap:1px;min-width:0"><span class="medium clip">${r.name}</span><span class="tiny muted">${r.owner || 'No owner set'}</span></div>
          <span class="${r.days <= 3 ? 'semi' : ''}" style="color:var(--${r.days < 0 || r.days <= 3 ? 'neg' : r.days <= 14 ? 'warn' : 'ink'})">Renews ${days(r.days)}</span>
          <span class="small ${r.email ? 'muted' : ''}" style="${r.email ? '' : 'color:var(--warn)'}">${r.email ? `Reminders also go to ${r.email}` : 'No email set, so reminders show on the dashboard only'}</span></div>`)
          : html`<div class="small muted" style="padding:10px 0 14px;border-top:1px solid var(--line2)">No tools with a renewal date yet. Add your tools in Subscriptions and you will be reminded before each one renews.</div>`}
        <div class="small" style="margin:6px 0 10px;padding:10px 12px;border-radius:9px;background:var(--surface2)">
          ${d.email_ready ? html`<span class="semi">Email is switched on.</span> Reminders are emailed as soon as they come up.`
            : html`<span class="semi">Emails are not being sent yet.</span> Reminders show on the dashboard${d.queued ? ` and ${f.num(d.queued)} email${d.queued === 1 ? ' is' : 's are'} waiting` : ''}. To send them, the app needs a mailbox to send from.`}</div>
      </div>
      <div class="card clipped" style="--cols:44px minmax(0,2.4fr) 130px">
        <div class="row" style="gap:8px;padding:16px 16px 10px"><span class="title">Alerts that are switched on</span>${info(TIPS.rules)}</div>
        <div class="thead" style="gap:14px;border-top:1px solid var(--line)"><span></span><span>Alert</span><span>Last came up</span></div>
        ${[...d.alert_rules, ...d.reminder_rules.map(r => ({ ...r, title: r.title + ' (for sales lead owners)', last: '' }))].map(r => html`<div class="trow" style="gap:14px;padding:13px 16px">
          ${toggle(r.enabled, 'rule', r.key)}
          <div class="stack" style="gap:1px"><span class="medium">${r.title}</span><span class="small muted">${r.detail}</span></div>
          <span class="muted">${r.last || '—'}</span></div>`)}
      </div>`;

    return html`
    ${pageHead(`${d.open.length} open · last 30 days against the 30 before`, 'Alerts and reminders', segmented(TABS.map(([arg, label]) => ({ arg, label: arg === 'open' && d.open.length ? `${label} · ${d.open.length}` : label, on: view === arg })), 'view', 16))}
    <div class="row" style="gap:10px;margin:2px 0 -2px;flex-wrap:wrap"><span class="section">${TABS.find(t => t[0] === view)[1]}</span><span class="muted">${BLURB[view]}</span></div>
    ${{ open, health, rules }[view]()}`;
  },

  modal(m, ctx) {
    const c = ctx.app.data.health.find(x => x.key === m.key);
    return html`<form class="modal" data-submit="saveBenchmark">
      <span class="section">${c.name}</span>
      <span class="muted pretty" style="margin-top:-8px">${c.says}</span>
      ${c.kind === 'rate' ? html`
        <label class="field">Benchmark, out of every 100<input class="input" name="value" type="number" min="0.1" max="100" step="0.1" value="${c.benchmark}" required data-autofocus></label>
        <div class="small muted pretty" style="margin-top:-6px"><span class="medium ink">Where the starting figure of ${show(c, c.default)} comes from:</span> ${c.source}</div>` : html`
        <div class="small muted pretty">This is a count, so it has no benchmark. It is compared with the 30 days before, and alerts if it falls ${ctx.app.data.drop_pct}% or more.</div>`}
      <label class="row" style="gap:10px"><input type="checkbox" name="watch" ${c.watch ? 'checked' : ''}> <span>Alert me about this number</span>${info(TIPS.watch)}</label>
      <div class="between" style="margin-top:4px">${c.custom ? html`<button type="button" class="btn" data-act="reset" data-arg="${c.key}">Use the starting figure</button>` : html`<span></span>`}
        <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div></div>
    </form>`;
  },

  actions: {
    view: (ctx, d) => ctx.setParams({ view: d.arg }),
    group(ctx, d) { ctx.ui().group = d.arg || null; ctx.render(); },
    edit: (ctx, d) => ctx.openModal({ key: d.arg }),
    async reset(ctx, d) { ctx.app.modal = null; await ctx.save(() => ctx.api.put('benchmarks/' + d.arg, { reset: true }), 'Back to the starting figure.'); },
    rule(ctx, d) {
      const all = [...ctx.app.data.reminder_rules, ...ctx.app.data.alert_rules];
      const rule = all.find(r => r.key === d.arg);
      return ctx.save(() => ctx.api.put('alert-rules/' + d.arg, { enabled: !rule.enabled }));
    },
  },

  submits: {
    async saveBenchmark(ctx, v) {
      const key = ctx.app.modal.key, c = ctx.app.data.health.find(x => x.key === key);
      ctx.app.modal = null;
      const body = { watch: v.watch === 'on' };
      if (c.kind === 'rate' && Number(v.value) !== c.benchmark) body.value = Number(v.value);
      await ctx.save(() => ctx.api.put('benchmarks/' + key, body), 'Saved.');
    },
  },
};

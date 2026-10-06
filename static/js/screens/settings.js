import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, segmented, sq, dot, avatar, menu } from '../ui.js';

const STATE = { connected: ['Connected', 'pos'], stale: ['Stale', 'warn'], disconnected: ['Disconnected', 'neg'], not_connected: ['Not connected', 'ink3'] };
const TARGET_COLS = 'minmax(0,1fr) 90px 90px';
const FMT = { int: f.num, money: f.money, money_m: f.moneyShort };

export default {
  uses: { range: true },
  load: ctx => ctx.api.get('settings', ctx.rangeParams()),

  render(d, ctx) {
    const { app } = ctx, ui = ctx.ui();
    const unmapped = d.utm.filter(u => !u.channel_id && !u.excluded).length;
    const leftOut = d.utm.reduce((a, u) => a + u.left_out, 0);
    const themes = ['auto', 'light', 'dark'].map(t => ({ arg: t, label: t[0].toUpperCase() + t.slice(1), on: ctx.theme() === t }));
    const channelItems = [...app.shell.channels.map(c => ({ label: c.name, arg: c.id, color: c.color })), { label: 'Leave unmapped', arg: '' }];
    const OUT = '!out';  // a lead source can also be left out altogether: sales activity, old lists, tests
    const itemsFor = u => [
      ...(u.is_source ? [{ label: 'Leave out · not marketing', arg: `${u.id}:${OUT}`, on: u.excluded }, { heading: 'Count under' }] : []),
      ...channelItems.map(i => ({ ...i, arg: `${u.id}:${i.arg}`, on: !u.excluded && (u.channel_id || '') === i.arg }))];
    const budgets = d.targets.rows.filter(r => r.key.startsWith('budget_'));
    const cell = (row, mi, bold) => {
      const month = d.targets.months[mi].key, id = `${month}:${row.key}`, v = row.values[mi];
      if (ui.edit === id) {
        return html`<input class="cell-input" id="target-input" type="number" min="0" step="any" value="${v == null ? '' : v}" data-change="target" data-month="${month}" data-key="${row.key}" data-blur="stopEdit" data-autofocus>`;
      }
      return html`<span class="right ${bold ? 'medium' : ''}"><span class="editable" data-act="editTarget" data-arg="${id}" title="Click to change">${v == null ? 'Set' : FMT[row.kind](v)}</span></span>`;
    };

    return html`
    ${pageHead(`${d.company} workspace`, 'Settings', html`<div class="row small muted" style="gap:10px">Appearance ${segmented(themes, 'theme')}</div>`)}
    <span class="section">Data sources</span>
    <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
      ${d.sources.map(s => { const [label, tone] = STATE[s.state] || STATE.not_connected; const primary = s.action === 'Reconnect' || s.action === 'Connect'; return html`
        <div class="card stack" style="padding:16px;gap:12px">
          <div class="between" style="align-items:flex-start"><span class="tile" style="width:32px;height:32px;border-radius:8px;font-size:11px">${s.initials}</span>
            <span class="pill sm">${dot(`var(--${tone})`)}${label}</span></div>
          <div class="stack" style="gap:1px"><span class="semi">${s.name}</span><span class="small muted">${s.detail}</span></div>
          <div class="between" style="align-items:center;gap:8px;padding-top:10px;border-top:1px solid var(--line2)"><span class="tiny faint">${s.synced}</span>
            <span class="btn xs ${primary ? 'primary' : ''}" data-act="syncSource" data-arg="${s.key}">${s.action}</span></div>
        </div>`; })}
    </div>
    <div class="grid start" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr);margin-top:12px">
      <div class="card" style="padding:18px 20px 8px;--cols:minmax(0,1.2fr) minmax(0,1fr) 64px 64px">
        <div class="baseline" style="margin-bottom:8px"><span class="title">Lead sources and tags to channels</span>${unmapped ? html`<span class="small" style="color:var(--warn)">${unmapped} unmapped</span>` : ''}</div>
        <div class="thead" style="padding:0 0 6px;border:0;gap:12px"><span>Lead source or tracking tags</span><span>Channel</span><span class="right">Sessions</span><span class="right">Leads</span></div>
        <div data-scroll="utm" style="max-height:520px;overflow-y:auto;margin-right:-8px;padding-right:8px">
        ${d.utm.map(u => { const c = u.channel_id ? ctx.channel(u.channel_id) : null; const tone = u.excluded ? 'var(--ink3)' : c ? 'var(--ink)' : 'var(--warn)'; return html`<div class="trow" style="padding:8px 0;gap:12px">
          <span class="${u.is_source ? '' : 'mono'} clip ${u.excluded ? 'faint' : ''}" title="${u.label}">${u.label}</span>
          <div class="menu-wrap" data-menu-trigger>
            <span class="row editable" style="gap:8px;color:${tone};cursor:pointer" data-act="menu" data-arg="utm-${u.id}" title="Change channel">
              ${c ? sq(c.color) : html`<span class="sq" style="border:1.5px ${u.excluded ? 'solid var(--line)' : 'dashed var(--warn)'}"></span>`}${u.excluded ? 'Left out' : c ? c.name : 'Unmapped'}</span>
            ${app.menu === 'utm-' + u.id ? menu(itemsFor(u), 'mapTag') : ''}</div>
          <span class="right muted">${u.sessions ? f.num(u.sessions) : '—'}</span>
          <span class="right ${u.excluded ? 'faint' : 'muted'}" title="${u.excluded ? 'Leads in Zoho that are left out' : ''}">${u.excluded ? (u.left_out ? f.num(u.left_out) : '—') : u.leads ? f.num(u.leads) : '—'}</span></div>`; })}
        </div>
        <div class="small faint" style="padding:10px 0 12px;border-top:1px solid var(--line2)">${leftOut ? `${f.num(leftOut)} leads are left out as not marketing. ` : ''}Pick “Leave out” for a source to drop its leads and deals from every screen. Zoho itself is not changed.</div>
      </div>
      <div class="card" style="padding:18px 20px 8px;--cols:${TARGET_COLS}">
        <div class="thead" style="padding:0 0 8px;border:0;gap:12px;align-items:baseline"><span class="title ink">Targets and budgets</span>${d.targets.months.map(m => html`<span class="right">${m.label}</span>`)}</div>
        ${d.targets.rows.map(r => html`<div class="trow" style="padding:8px 0;gap:12px;${r.key === 'budget_meta' ? 'border-top-color:var(--line)' : ''}">
          <span class="row" style="gap:8px">${r.channel_id ? sq(ctx.channel(r.channel_id).color) : ''}${r.label}</span>${cell(r, 0, false)}${cell(r, 1, true)}</div>`)}
        <div class="trow semi" style="padding:9px 0;gap:12px;border-top-color:var(--line)"><span>Total budget</span>
          ${d.targets.months.map((m, mi) => html`<span class="right">${f.money(budgets.reduce((a, r) => a + (r.values[mi] || 0), 0))}</span>`)}</div>
      </div>
    </div>
    <div class="card clipped" style="margin-top:12px;--cols:minmax(0,1.4fr) minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)">
      <div class="baseline" style="padding:16px 16px 10px"><span class="title">Users and roles</span></div>
      <div class="thead" style="padding:8px 16px;border-top:1px solid var(--line);gap:12px"><span>Name</span><span>Team</span><span>Role</span><span>Last active</span></div>
      ${d.users.map((u, i) => html`<div class="trow ${i ? '' : 'first'}" style="padding:9px 16px;gap:12px">
        <span class="row" style="gap:10px">${avatar(u.initials, 26)}<span class="medium">${u.name}</span></span><span class="muted">${u.team}</span><span>${u.role}</span><span class="muted">${u.last}</span></div>`)}
      <div class="small faint" style="padding:10px 16px;border-top:1px solid var(--line)">Admin: everything · Editor: targets, rules, reports · Lead owner: leads and reminders · Viewer: read only</div>
    </div>`;
  },

  actions: {
    theme: (ctx, d) => ctx.setTheme(d.arg),
    editTarget(ctx, d) { ctx.ui().edit = d.arg; ctx.render(); },
    stopEdit(ctx) { if (ctx.ui().edit) { ctx.ui().edit = null; ctx.render(); } },
    mapTag(ctx, d) {
      const [id, channel] = d.arg.split(':');
      ctx.app.menu = null;
      const body = channel === '!out' ? { left_out: true } : { channel_id: channel || null };
      return ctx.save(() => ctx.api.put('utm/' + id, body), r => r.message || 'Mapping saved.');
    },
  },

  changes: {
    target(ctx, value, el) {
      ctx.ui().edit = null;
      if (value === '' || Number(value) < 0) return ctx.render();
      return ctx.save(() => ctx.api.put('targets', { month: el.dataset.month, key: el.dataset.key, value: Number(value) }));
    },
  },
};

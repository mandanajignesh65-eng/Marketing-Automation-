// App shell: state, routing, the sidebar and top bar, and event delegation for every screen.
import { html, raw } from './html.js';
import { api } from './api.js';
import { segmented, toggle, avatar, menu } from './ui.js';
import { setCurrency } from './format.js';
import overview from './screens/overview.js';
import funnel from './screens/funnel.js';
import channels from './screens/channels.js';
import paid from './screens/paid.js';
import outbound from './screens/outbound.js';
import web from './screens/web.js';
import leads from './screens/leads.js';
import quality from './screens/quality.js';
import subs from './screens/subs.js';
import reports from './screens/reports.js';
import alerts from './screens/alerts.js';
import targets from './screens/targets.js';
import people from './screens/people.js';
import settings from './screens/settings.js';

const SCREENS = { overview, funnel, channels, paid, outbound, web, leads, quality, targets, people, subs, reports, alerts, settings };
const NAV = [
  { label: null, items: [['overview', 'Overview']] },
  { label: 'Performance', items: [['funnel', 'Funnel'], ['channels', 'Channels'], ['paid', 'Paid ads'], ['outbound', 'Outbound'], ['web', 'Website & organic']] },
  { label: 'Leads', items: [['leads', 'Leads', 'leads'], ['quality', 'Lead quality']] },
  { label: 'Team', items: [['targets', 'Targets'], ['people', 'People']] },
  { label: 'Operations', items: [['subs', 'Subscriptions'], ['reports', 'Reports'], ['alerts', 'Alerts & reminders', 'alerts']] },
];
// Sidebar icons: thin single-colour line drawings on one 24-unit grid, so they sit quietly beside the names and
// follow the text colour in light and dark mode.
const ICON = {
  overview: '<rect x="3.5" y="3.5" width="7" height="9.5" rx="2"/><rect x="13.5" y="3.5" width="7" height="5.5" rx="2"/><rect x="13.5" y="11.5" width="7" height="9" rx="2"/><rect x="3.5" y="15.500" width="7" height="5" rx="2"/>',
  funnel: '<path d="M4 5.500h16l-6.200 7.300v5.200l-3.600 2v-7.200L4 5.500z"/>',
  channels: '<circle cx="6" cy="12" r="2.300"/><circle cx="18" cy="6" r="2.300"/><circle cx="18" cy="18" r="2.300"/><path d="M8.100 11l7.800-3.900M8.100 13l7.800 3.900"/>',
  paid: '<path d="M4 10v4h3l6 4V6l-6 4H4z"/><path d="M16.500 9.500a3.600 3.600 0 010 5M19 7a7 7 0 010 10"/>',
  outbound: '<path d="M20.500 3.500L3.500 10.300l6.700 2.500 2.500 6.700 7.800-16z"/><path d="M10.200 12.800l10.300-9.300"/>',
  web: '<circle cx="12" cy="12" r="8.500"/><ellipse cx="12" cy="12" rx="3.600" ry="8.500"/><path d="M3.500 12h17"/>',
  leads: '<circle cx="9" cy="8.500" r="3.200"/><path d="M3.200 19.500c.6-3.400 2.900-5.300 5.800-5.300s5.200 1.900 5.800 5.300"/><path d="M15.300 5.600a3.200 3.200 0 010 5.800M17.300 14.600c1.800.7 3 2.400 3.500 4.900"/>',
  quality: '<circle cx="12" cy="9" r="5.200"/><path d="M9.200 13.400L7.700 20.500l4.300-2.400 4.300 2.400-1.500-7.100"/>',
  targets: '<circle cx="12" cy="12" r="8.500"/><circle cx="12" cy="12" r="4.700"/><circle cx="12" cy="12" r="1.100"/>',
  subs: '<rect x="3.500" y="5.500" width="17" height="13" rx="2.600"/><path d="M3.500 10.200h17M7 14.600h3.500"/>',
  reports: '<path d="M7.500 3.500h6.300l4.700 4.700v10.800a1.500 1.500 0 01-1.500 1.500H7.500A1.500 1.500 0 016 19V5a1.500 1.500 0 011.500-1.500z"/><path d="M13.500 3.800v4.700h4.700M9 13h6M9 16.500h4"/>',
  alerts: '<path d="M6.500 16.500V11a5.500 5.500 0 0111 0v5.500l1.500 2.200h-14l1.500-2.200z"/><path d="M10.300 20.800a2 2 0 003.400 0"/>',
  settings: '<path d="M4 7h8.800M17.200 7H20M4 12h2.800M11.200 12H20M4 17h10.800M19.200 17H20"/><circle cx="15" cy="7" r="2.200"/><circle cx="9" cy="12" r="2.200"/><circle cx="17" cy="17" r="2.200"/>',
};
ICON.people = '<circle cx="12" cy="8" r="3.400"/><path d="M5.200 19.500c.7-3.700 3.400-5.800 6.800-5.800s6.100 2.100 6.800 5.800"/>';
// Pages only a leader may open. With sign-in off there is no signed-in person, and everything is open.
const LEADER_SCREENS = ['people', 'settings'];
const leader = () => !app.shell || !app.shell.user || app.shell.user.admin !== false;
const icon = id => html`<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${raw(ICON[id] || '')}</svg>`;

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const app = {
  shell: null, screen: 'overview', params: {}, range: 'month', start: null, end: null, compare: true, channel: 'all',
  data: null, loading: false, error: null, ui: {}, menu: null, modal: null, seq: 0,
};

// ---------------------------------------------------------------- routing

function toHash(screen, params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') qs.set(k, v); });
  return '#/' + screen + (qs.toString() ? '?' + qs : '');
}

function parseHash() {
  const [path, query] = location.hash.replace(/^#\/?/, '').split('?');
  const open = SCREENS[path] && (leader() || !LEADER_SCREENS.includes(path));
  return { screen: open ? path : leader() ? 'overview' : 'targets', params: Object.fromEntries(new URLSearchParams(query || '')) };
}

async function load(soft = false) {
  const screen = SCREENS[app.screen];
  const token = ++app.seq;
  app.loading = true;
  if (!soft) app.data = null;
  render();
  try {
    const data = await screen.load(ctx);
    if (token !== app.seq) return;
    app.data = data;
    app.error = null;
  } catch (err) {
    if (token !== app.seq) return;
    app.error = err.message;
  }
  app.loading = false;
  render();
}

function onRoute() {
  const { screen, params } = parseHash();
  const same = screen === app.screen && app.data;
  app.screen = screen;
  app.params = params;
  app.menu = null;
  app.modal = null;
  if (!same) window.scrollTo(0, 0);
  load(same);
}

// ---------------------------------------------------------------- context handed to screens

const ctx = {
  app, api,
  channel: id => app.shell.channels.find(c => c.id === id) || { id, name: 'Unmapped', color: 'var(--ink3)', grp: null },
  rangeParams: () => (app.range === 'custom' ? { range: 'custom', start: app.start, end: app.end } : { range: app.range }),
  go(screen, params = {}) {
    const hash = toHash(screen, params);
    if (location.hash === hash) onRoute(); else location.hash = hash;
  },
  setParams(params) {
    app.params = params;
    history.replaceState(null, '', toHash(app.screen, params));
    render();
  },
  reload: (soft = true) => load(soft),
  render: () => render(),
  ui: () => (app.ui[app.screen] = app.ui[app.screen] || {}),
  // The toast lives outside the app root so showing or hiding it never re-renders a form mid-edit.
  toast(message) {
    const root = document.getElementById('toast-root');
    root.innerHTML = message ? html`<div class="toast" role="status">${message}</div>`.toString() : '';
    clearTimeout(ctx.toastTimer);
    if (message) ctx.toastTimer = setTimeout(() => { root.innerHTML = ''; }, 4500);
  },
  toggleMenu(id) { app.menu = app.menu === id ? null : id; render(); },
  openModal(modal) { app.modal = modal; app.menu = null; render(); },
  closeModal() { app.modal = null; render(); },
  async refreshShell() { app.shell = await api.get('shell'); setCurrency(app.shell.currency); },
  theme: () => document.documentElement.dataset.theme || 'auto',
  setTheme(mode) {
    if (mode === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = mode;
    try { localStorage.setItem('meridian-theme', mode); } catch (e) { /* storage unavailable */ }
    render();
  },
  // Run a write, then refresh the screen. Failures surface as a toast instead of breaking the page.
  async save(fn, done) {
    try {
      const result = await fn();
      await ctx.refreshShell();
      await load(true);
      if (done) ctx.toast(typeof done === 'function' ? done(result) : done);
      return result;
    } catch (err) {
      ctx.toast(err.message);
      return null;
    }
  },
};

// ---------------------------------------------------------------- shell markup

function periodLabel() {
  const day = s => new Date(s + 'T00:00:00');
  const today = day(app.shell.today);
  let s = today, e = today;
  if (app.range === 'week') { s = new Date(today); s.setDate(today.getDate() - ((today.getDay() + 6) % 7)); }
  else if (app.range === 'month') s = new Date(today.getFullYear(), today.getMonth(), 1);
  else if (app.range === 'custom') { e = day(app.end) > today ? today : day(app.end); s = day(app.start) > e ? e : day(app.start); }
  const dm = d => d.getDate() + ' ' + MONTHS[d.getMonth()];
  if (+s === +e) return dm(e) + ' ' + e.getFullYear();
  if (s.getMonth() === e.getMonth() && s.getFullYear() === e.getFullYear()) return `${s.getDate()} – ${dm(e)} ${e.getFullYear()}`;
  return `${dm(s)} – ${dm(e)} ${e.getFullYear()}`;
}

function sidebar() {
  const s = app.shell;
  return html`<aside class="side">
    <div class="brand"><div class="brand-mark"><i></i></div>
      <div class="stack"><span class="semi" style="font-size:14px;letter-spacing:-0.01em">${s.product}</span><span class="tiny muted">${s.company}</span></div></div>
    ${NAV.map(g => html`<nav class="nav-group">
      ${g.label ? html`<div class="nav-label">${g.label}</div>` : ''}
      ${g.items.filter(([id]) => leader() || !LEADER_SCREENS.includes(id)).map(([id, label, badge]) => html`<a class="nav-item ${app.screen === id ? 'on' : ''}" href="#/${id}">
        <span class="row" style="gap:10px;min-width:0">${icon(id)}<span class="clip">${label}</span></span>${badge && s.badges[badge] ? html`<span class="badge">${s.badges[badge].toLocaleString(s.currency.locale)}</span>` : ''}</a>`)}
    </nav>`)}
    <div class="side-foot">
      ${leader() ? html`<a class="nav-item ${app.screen === 'settings' ? 'on' : ''}" href="#/settings"><span class="row" style="gap:10px">${icon('settings')}<span>Settings</span></span></a>` : ''}
      ${s.user ? html`<div class="me">${avatar(s.user.initials, 26)}
        <div class="stack" style="flex:1;min-width:0;${s.user.signed_in ? 'cursor:pointer' : ''}" ${s.user.signed_in ? html`data-act="account" title="Change your password"` : ''}><span class="small medium clip">${s.user.name}</span><span class="tiny muted">${s.user.role}</span></div>
        ${s.user.signed_in ? html`<span class="tiny muted" data-act="signOut" style="cursor:pointer" title="Sign out of Meridian">Sign out</span>` : ''}</div>` : ''}
    </div>
  </aside>`;
}

function channelMenu() {
  const items = [{ label: 'All channels', arg: 'all', on: app.channel === 'all' }];
  app.shell.groups.forEach(g => {
    items.push({ heading: g.label });
    items.push({ label: 'All ' + g.label.toLowerCase(), arg: g.id, on: app.channel === g.id });
    app.shell.channels.filter(c => c.grp === g.id).forEach(c => items.push({ label: c.name, arg: c.id, color: c.color, on: app.channel === c.id }));
  });
  return menu(items, 'setChannel');
}

function channelLabel() {
  if (app.channel === 'all') return 'All channels';
  const g = app.shell.groups.find(x => x.id === app.channel);
  return g ? g.label : ctx.channel(app.channel).name;
}

function topbar(screen) {
  const uses = screen.uses || {};
  const s = app.shell;
  const ranges = [['day', 'Day'], ['week', 'Week'], ['month', 'Month'], ['custom', 'Custom']].map(([arg, label]) => ({ arg, label, on: app.range === arg }));
  return html`<header class="topbar">
    <div class="menu-wrap ${uses.range ? '' : 'off'}" data-menu-trigger>${segmented(ranges, 'setRange')}
      ${app.menu === 'custom' ? html`<form class="menu" data-menu data-submit="customRange" style="padding:12px;gap:10px;min-width:230px">
        <label class="field">From<input class="input" type="date" name="start" value="${app.start || s.today.slice(0, 8) + '01'}" max="${s.today}" required></label>
        <label class="field">To<input class="input" type="date" name="end" value="${app.end || s.today}" max="${s.today}" required></label>
        <button class="btn primary" type="submit">Apply</button></form>` : ''}
    </div>
    <div class="medium ${uses.range ? '' : 'off'}">${periodLabel()}</div>
    <div class="vr"></div>
    <div class="row small muted ${uses.compare ? '' : 'off'}" style="gap:8px" data-act="toggleCompare">${toggle(app.compare, 'toggleCompare')}<span>Compare to previous period</span></div>
    <div class="menu-wrap ${uses.channel ? '' : 'off'}" data-menu-trigger>
      <div class="select" data-act="menu" data-arg="channel">${channelLabel()}<span class="caret"></span></div>
      ${app.menu === 'channel' ? channelMenu() : ''}
    </div>
    <div style="flex:1"></div>
    ${s.demo ? html`<span class="pill sm" title="The figures come from the built-in sample company, pinned to ${s.today}.">Sample data</span>` : ''}
    <div class="row small muted" style="gap:7px"><span class="dot" style="width:7px;height:7px;background:var(--${s.sync.tone})"></span>${app.loading && !app.data ? 'Loading…' : s.sync.text}</div>
  </header>`;
}

function banner() {
  const b = app.shell.sync.banner;
  if (!b) return '';
  return html`<div class="banner" style="background:color-mix(in srgb, var(--${b.tone}) 9%, var(--surface))">
    <span class="dot" style="width:8px;height:8px;background:var(--${b.tone})"></span>
    <div class="stack" style="flex:1;min-width:0;gap:1px"><span class="semi">${b.title}</span><span class="small muted">${b.detail}</span></div>
    <div class="btn outline" data-act="syncSource" data-arg="${b.source}">${b.action}</div>
  </div>`;
}

function skeleton() {
  const bars = [62, 70, 58, 44, 20, 16, 66, 74, 70, 64, 52, 20, 18, 80, 84, 76, 72, 50, 20, 16, 64, 60, 60, 36];
  return html`<div class="page skeleton">
    <div class="stack" style="gap:10px;margin-bottom:6px"><div class="skel" style="width:180px;height:12px"></div><div class="skel" style="width:150px;height:28px"></div><div class="skel" style="width:560px;max-width:100%;height:14px"></div></div>
    <div class="grid" style="grid-template-columns:minmax(0,2.3fr) repeat(4,minmax(0,1fr))">${[1, 2, 3, 4, 5].map(() => html`<div class="card" style="height:118px;padding:18px;display:flex;flex-direction:column;gap:10px;box-shadow:none">
      <div class="skel" style="width:60%;height:28px"></div><div class="skel" style="width:45%;height:10px"></div><div class="skel" style="width:35%;height:10px"></div></div>`)}</div>
    <div class="grid" style="grid-template-columns:minmax(0,1fr) 336px">
      <div class="card" style="height:300px;padding:20px;display:flex;align-items:flex-end;gap:6px;box-shadow:none">${bars.map(h => html`<div class="skel" style="flex:1;height:${h}%;border-radius:3px"></div>`)}</div>
      <div class="card" style="height:300px;padding:20px;display:flex;flex-direction:column;gap:22px;box-shadow:none">${[1, 2, 3, 4, 5].map(() => html`<div class="skel" style="height:6px;border-radius:3px"></div>`)}</div>
    </div>
    <div class="small faint" style="text-align:center">Loading figures…</div>
  </div>`;
}

function emptyOverview() {
  const steps = [['Step 1', 'Zoho CRM', 'Leads, owners, deals'], ['Step 2', 'Meta and LinkedIn Ads', 'Spend and campaigns'], ['Step 3', 'Analytics and Search Console', 'Traffic and queries']];
  return html`<div class="page"><h1 class="h1">Overview</h1>
    <div class="card" style="padding:56px 32px;display:flex;flex-direction:column;align-items:center;gap:22px;text-align:center">
      <div class="stack" style="gap:6px;max-width:440px"><span style="font-size:20px;font-weight:600;letter-spacing:-0.015em">Connect your first source</span>
        <span class="muted pretty" style="font-size:14px">${app.shell.product} fills in as data arrives. Start with Zoho CRM so every lead has an owner and status, then add ad accounts and analytics.</span></div>
      <div class="grid" style="grid-template-columns:repeat(3,minmax(0,200px));text-align:left">${steps.map(([n, t, d]) => html`<div class="stack" style="padding:14px;border-radius:12px;border:1px solid var(--line);gap:4px">
        <span class="tiny faint medium">${n}</span><span class="medium">${t}</span><span class="small muted">${d}</span></div>`)}</div>
      <a class="btn primary" href="#/settings" style="padding:8px 16px;border-radius:9px;font-size:13px;text-decoration:none">Connect Zoho CRM</a>
    </div></div>`;
}

function body(screen) {
  if (app.error) {
    return html`<div class="page"><div class="empty"><span class="title">This screen could not load</span>
      <span class="small muted">${app.error}</span><div class="btn" data-act="retry">Try again</div></div></div>`;
  }
  if (app.screen === 'overview' && app.shell.sync.state === 'empty') return emptyOverview();
  if (!app.data) return skeleton();
  const content = screen.render(app.data, ctx);
  return screen.bare ? content : html`<div class="page ${app.loading ? 'stale' : ''}">${content}</div>`;
}

// Opened by clicking your own name: the one thing every signed-in person can change about themselves.
function accountModal() {
  const u = app.shell.user;
  return html`<form class="modal" data-submit="changePassword" autocomplete="off">
    <span class="section">Change your password</span>
    <span class="small muted">Signed in as ${u.email}</span>
    <label class="field">Current password<input class="input" name="current" type="password" required data-autofocus autocomplete="current-password"></label>
    <label class="field">New password<input class="input" name="new" type="password" minlength="10" required placeholder="At least 10 characters" autocomplete="new-password"></label>
    <label class="field">New password again<input class="input" name="again" type="password" minlength="10" required autocomplete="new-password"></label>
    <div class="row" style="gap:8px;justify-content:flex-end;margin-top:4px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div>
  </form>`;
}

function view() {
  if (!app.shell) {
    return app.error ? html`<div class="page"><div class="empty"><span class="title">Meridian could not start</span><span class="small muted">${app.error}</span></div></div>` : html``;
  }
  const screen = SCREENS[app.screen];
  return html`<div class="app">${sidebar()}<main class="main">${topbar(screen)}${banner()}${body(screen)}</main></div>
    ${app.modal && app.modal.account ? html`<div class="overlay" data-act="closeModal">${accountModal()}</div>`
      : app.modal && screen.modal ? html`<div class="overlay" data-act="closeModal">${screen.modal(app.modal, ctx)}</div>` : ''}`;
}

// A form field's identity across renders: its form plus its name, or its id.
const fieldKey = el => (el.form && el.form.dataset.submit ? `${el.form.dataset.submit}:${el.name}` : el.id ? '#' + el.id : null);
// Fields bound with data-input keep their value in screen state, so they are left alone.
const fieldsIn = root => [...root.querySelectorAll('input, textarea, select')].filter(el => fieldKey(el) && !el.dataset.input);

// Re-rendering replaces the markup, so carry scroll positions, half-typed fields and input focus across.
function render() {
  const root = document.getElementById('app');
  const scrolls = [...root.querySelectorAll('[data-scroll]')].map(el => [el.dataset.scroll, el.scrollTop]);
  const typed = new Map(fieldsIn(root).map(el => [fieldKey(el), el.value]));
  const active = document.activeElement;
  const focus = active && active.id && root.contains(active) ? { id: active.id, start: active.selectionStart, end: active.selectionEnd } : null;
  root.innerHTML = view().toString();
  scrolls.forEach(([key, top]) => { const el = root.querySelector(`[data-scroll="${key}"]`); if (el) el.scrollTop = top; });
  fieldsIn(root).forEach(el => { if (typed.has(fieldKey(el))) el.value = typed.get(fieldKey(el)); });
  if (focus) {
    const el = document.getElementById(focus.id);
    if (el) { el.focus(); try { el.setSelectionRange(focus.start, focus.end); } catch (e) { /* not a text input */ } }
  }
  const auto = root.querySelector('[data-autofocus]');
  if (auto && !focus) { auto.focus(); if (auto.select) auto.select(); }
}

// ---------------------------------------------------------------- global actions

const actions = {
  menu: (c, d) => ctx.toggleMenu(d.arg),
  async signOut() { await api.post('logout'); location.reload(); },
  account: () => ctx.openModal({ account: true }),
  setRange(c, d) {
    if (d.arg === 'custom') return ctx.toggleMenu('custom');
    app.range = d.arg;
    app.menu = null;
    load(true);
  },
  toggleCompare() { app.compare = !app.compare; render(); },
  setChannel(c, d) { app.channel = d.arg; app.menu = null; load(true); },
  retry: () => load(false),
  closeModal(c, d, el, event) { if (event.target === el) ctx.closeModal(); },
  cancelModal: () => ctx.closeModal(),
  async syncSource(c, d) {
    try { const r = await api.post(`sources/${d.arg}/sync`); ctx.toast(r.message); } catch (err) { ctx.toast(err.message); }
  },
};

const submits = {
  async changePassword(c, v) {
    if (v.new !== v.again) return ctx.toast('The two new passwords are different.');
    try { await api.post('account/password', { current: v.current, new: v.new }); } catch (err) { return ctx.toast(err.message); }
    ctx.closeModal();
    ctx.toast('Your password is changed.');
  },
  customRange(c, values) {
    app.range = 'custom';
    app.start = values.start <= values.end ? values.start : values.end;
    app.end = values.end;
    app.menu = null;
    load(true);
  },
};

function handler(kind, name) {
  const screen = SCREENS[app.screen];
  return (screen[kind] && screen[kind][name]) || (kind === 'actions' ? actions[name] : kind === 'submits' ? submits[name] : null);
}

// The "i" notes open on hover; a click (or tap, where there is no hover) pins one open until the next click.
document.addEventListener('click', event => {
  const note = event.target.closest('.info');
  document.querySelectorAll('.info.open').forEach(el => { if (el !== note) el.classList.remove('open'); });
  if (note) note.classList.toggle('open');
}, true);

document.addEventListener('click', event => {
  const el = event.target.closest('[data-act]');
  const inMenu = event.target.closest('[data-menu], [data-menu-trigger]');
  if (app.menu && !inMenu) { app.menu = null; if (!el) return render(); }
  if (!el) return;
  const fn = handler('actions', el.dataset.act);
  if (fn) { if (el.tagName === 'A' && el.getAttribute('href') === '#') event.preventDefault(); fn(ctx, el.dataset, el, event); }
});
document.addEventListener('input', event => {
  const el = event.target.closest('[data-input]');
  const fn = el && handler('inputs', el.dataset.input);
  if (fn) fn(ctx, el.value, el);
});
document.addEventListener('change', event => {
  const el = event.target.closest('[data-change]');
  const fn = el && handler('changes', el.dataset.change);
  if (fn) fn(ctx, el.value, el);
});
document.addEventListener('focusout', event => {
  const el = event.target.closest && event.target.closest('[data-blur]');
  const fn = el && handler('actions', el.dataset.blur);
  if (fn) fn(ctx, el.dataset, el, event);
});
document.addEventListener('submit', event => {
  const form = event.target.closest('[data-submit]');
  if (!form) return;
  event.preventDefault();
  const fn = handler('submits', form.dataset.submit);
  if (fn) fn(ctx, Object.fromEntries(new FormData(form)), form, event);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && (app.menu || app.modal)) { app.menu = null; app.modal = null; render(); }
  if (event.key === 'Enter' && event.target.matches('[data-enter]')) {
    const fn = handler('actions', event.target.dataset.enter);
    if (fn) { event.preventDefault(); fn(ctx, event.target.dataset, event.target, event); }
  }
});
window.addEventListener('hashchange', onRoute);

(async function start() {
  try {
    await ctx.refreshShell();
  } catch (err) {
    app.error = err.message;
    return render();
  }
  if (!leader() && !location.hash) history.replaceState(null, '', '#/targets?view=today');  // a team member starts on their own day
  onRoute();
})();

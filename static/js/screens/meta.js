// The Meta part of the Paid ads screen: what Meta tells us, and what Meridian sends back.
import { html } from '../html.js';
import * as f from '../format.js';
import { info, segmented, switcher, sq, dot } from '../ui.js';

const TABS = [['results', 'Results'], ['creatives', 'Ads and creatives'], ['people', 'Audience'], ['sending', 'Sent to Meta']];
const BLURB = {
  results: 'What we spent and what came back, by campaign, ad set and ad',
  creatives: 'Each ad with its picture or video, how people reacted, and how Meta rates it',
  people: 'Where the ads were shown and who saw them',
  sending: 'What Meridian tells Meta, so Meta can find better leads and leave the wrong people out',
};
const TIPS = {
  spend: 'Money spent on Meta ads in this period.',
  impressions: 'How many times the ads were shown on a screen. One person can see an ad more than once.',
  cpm: 'What it costs to show the ads 1,000 times. It tells you how expensive this audience is.',
  clicks: 'How many times people tapped the ad to go to WhatsApp or the website.',
  ctr: 'Out of every 100 times the ad was shown, how many times people tapped it. Higher means the ad catches attention.',
  chats: 'How many people started a WhatsApp chat with us from an ad. Counted by Meta.',
  perChat: 'Money spent divided by chats started. This is what one new chat costs us.',
  reply: 'Out of every 100 chats started, in how many did the person actually send us a message. Low means people open WhatsApp and leave.',
  daily: 'One bar for each day. Use the buttons to change what is counted.',
  table: 'Use the buttons to look at campaigns, ad sets or single ads. Click a campaign to see its ad sets, and an ad set to see its ads.',
  learning: 'When an ad set is new or was changed, Meta spends a few days testing who to show it to. Results jump around during this time. Meta needs about 50 results in a week to finish.',
  hook: 'Out of every 100 times the video was shown, how many times people watched at least 3 seconds. It tells you if the first seconds stop the scroll.',
  hold: 'Out of the people who watched 3 seconds, how many kept watching to the end (or 15 seconds). It tells you if the video keeps attention.',
  rank: 'Meta compares each ad with other ads shown to the same people. Quality is how people react to it. Engagement is how much they tap. Conversion is how often it reaches the goal. Needs about 500 views first.',
  breakdown: 'The same numbers split by one thing. Use the buttons to change what is counted.',
  mode: 'A safety switch. Off: nothing leaves Meridian. Test: events go only to Meta’s test screen and change nothing. Live: events are used by Meta to improve the ads.',
  events: 'A message Meridian sends to Meta that says “this chat turned into a good lead” or “this lead had a meeting”. Meta uses these to find more people like them.',
  lists: 'Lists of people that Meridian builds from Zoho. Emails are scrambled before they leave, so Meta can only match people it already knows.',
  later: 'This needs the WhatsApp bot to tell Meridian which ad each chat came from. That is the next phase.',
};
const STATUS = { ACTIVE: ['Active', 'pos'], PAUSED: ['Paused', 'ink3'], CAMPAIGN_PAUSED: ['Campaign paused', 'ink3'], ADSET_PAUSED: ['Ad set paused', 'ink3'],
  PENDING_REVIEW: ['In review', 'warn'], DISAPPROVED: ['Rejected', 'neg'], WITH_ISSUES: ['Has issues', 'neg'], IN_PROCESS: ['Processing', 'warn'],
  ARCHIVED: ['Archived', 'ink3'], DELETED: ['Deleted', 'ink3'] };
const LEARNING = { LEARNING: ['Learning', 'warn'], SUCCESS: ['Learning done', 'pos'], FAIL: ['Learning limited', 'neg'] };
const GOAL = { CONVERSATIONS: 'More chats', OFFSITE_CONVERSIONS: 'More conversions', LEAD_GENERATION: 'More leads', QUALITY_LEAD: 'Better leads',
  LINK_CLICKS: 'More clicks', REACH: 'Reach', IMPRESSIONS: 'Views', THRUPLAY: 'Video views', LANDING_PAGE_VIEWS: 'Page views', VALUE: 'Highest value' };
const KEYS = ['spend', 'impressions', 'link_clicks', 'chats', 'first_replies', 'video_3s', 'thruplays'];
const rate = (a, b) => (b ? a / b * 100 : null);
const per = (a, b) => (b ? a / b : null);
const change = (a, b) => (b ? (a - b) / b * 100 : null);
const add = rows => rows.reduce((t, r) => { KEYS.forEach(k => { t[k] += r[k] || 0; }); t.prev_spend += r.prev_spend || 0; t.prev_chats += r.prev_chats || 0; return t; },
  Object.fromEntries([...KEYS, 'prev_spend', 'prev_chats'].map(k => [k, 0])));
const pill = (pair, raw) => { const [label, tone] = pair || [String(raw || '—').toLowerCase().replace(/_/g, ' '), 'ink3']; return html`<span class="row small muted nowrap" style="gap:6px">${dot(`var(--${tone})`)}${label}</span>`; };
const when = unix => new Date(unix * 1000).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

function bars(list, value, color, fmt) {
  const ax = f.axis(Math.max(...list.map(value), 1));
  const dense = list.length > 16;
  return html`<div style="display:grid;grid-template-columns:52px minmax(0,1fr);gap:0 8px">
    <div style="position:relative;height:190px">${ax.ticks.map(t => html`<span class="micro faint" style="position:absolute;right:0;bottom:${t / ax.max * 100}%;transform:translateY(50%)">${fmt(t)}</span>`)}</div>
    <div style="position:relative;height:190px">
      ${ax.ticks.map(t => html`<div style="position:absolute;left:0;right:0;bottom:${t / ax.max * 100}%;height:1px;background:var(--grid)"></div>`)}
      <div style="position:absolute;inset:0;display:flex;align-items:flex-end;gap:${dense ? 3 : 10}px">
        ${list.map(x => html`<div class="stack" style="flex:1;min-width:0;height:100%;justify-content:flex-end;gap:4px">
          ${dense ? '' : html`<span class="small medium" style="text-align:center">${fmt(value(x))}</span>`}
          <div title="${x.date}: ${fmt(value(x))}" style="height:${value(x) / ax.max * 100}%;min-height:${value(x) ? 2 : 0}px;border-radius:${dense ? 3 : 6}px ${dense ? 3 : 6}px 1px 1px;background:${color}"></div></div>`)}
      </div>
    </div>
    <span></span>
    <div style="display:flex;gap:${dense ? 3 : 10}px;margin-top:6px">${list.map((x, i) => html`<span class="micro muted nowrap" style="flex:1;text-align:center;min-width:0">${i === 0 || !dense || Number(x.date.slice(8)) % 5 === 0 ? Number(x.date.slice(8)) : ''}</span>`)}</div>
  </div>`;
}

export function renderMeta(m, ctx) {
  const ui = ctx.ui(), show = ctx.app.compare !== false;
  const view = TABS.some(t => t[0] === ctx.app.params.view) ? ctx.app.params.view : 'results';
  const lead = !ctx.app.shell.user || ctx.app.shell.user.admin !== false;
  const kpi = (value, label, tip, sub = '', end = false) => html`<div class="card kpi" style="padding:16px 18px"><span class="kpi-v md">${value}</span>
    <span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span><span class="kpi-d faint">${sub}</span></div>`;
  const delta = (a, b, mode = 'up') => { const c = change(a, b); return c == null ? '' : html`<span style="color:${f.tone(c, mode)}">${f.arrowShort(c)}</span> vs ${m.period.prev_short}`; };
  const head = html`<div class="row" style="gap:10px;margin:2px 0 -2px;flex-wrap:wrap"><span class="section">${TABS.find(t => t[0] === view)[1]}</span>
    <span style="flex:1"></span>${segmented(TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'view', 14)}</div>`;
  const empty = !m.ads.length;
  const notYet = html`<div class="card pad stack" style="gap:8px"><span class="title">${m.connected ? 'No ads have run yet' : 'Meta Ads is not connected yet'}</span>
    <span class="muted pretty">${m.connected ? 'The account is connected. Campaigns, ad sets and ads will show here after the next sync once they exist in Ads Manager.'
      : 'Once it is connected, Meridian reads every campaign, ad set and ad with its spend, views, taps and WhatsApp chats started, a few times a day.'}</span>
    ${m.note ? html`<span class="small" style="color:var(--warn)">${m.note}</span>` : ''}</div>`;

  // ------------------------------------------------------------ results
  const results = () => {
    const t = add(m.ads);
    const metric = ['spend', 'chats', 'link_clicks', 'impressions'].includes(ui.day) ? ui.day : 'spend';
    const M = { spend: ['Spend', 'var(--ink)', f.money], chats: ['Chats started', 'oklch(0.60 0.11 165)', f.num], link_clicks: ['Taps on the ad', 'var(--accent)', f.num], impressions: ['Times shown', 'var(--ink3)', f.big] };
    const level = ['campaign', 'adset', 'ad'].includes(ui.level) ? ui.level : 'campaign';
    const camp = m.campaigns.find(c => c.id === ui.camp), set = m.adsets.find(s => s.id === ui.adset);
    const adsOf = fn => m.ads.filter(fn);
    let rows;
    if (level === 'campaign') rows = m.campaigns.map(c => ({ id: c.id, name: c.name, status: c.status, budget: c.daily_budget, sub: c.objective ? c.objective.replace('OUTCOME_', '').toLowerCase() : '', act: 'openCamp', ...add(adsOf(a => a.campaign_id === c.id)) }));
    else if (level === 'adset') rows = m.adsets.filter(s => !camp || s.campaign_id === camp.id).map(s => ({ id: s.id, name: s.name, status: s.status, budget: s.daily_budget, learning: s.learning,
      sub: [GOAL[s.optimization_goal] || (s.optimization_goal || '').toLowerCase().replace(/_/g, ' '), (s.targeting.regions || []).concat(s.targeting.cities || []).slice(0, 2).join(', ') || (s.targeting.countries || []).join(', '),
        s.targeting.excluded ? `${s.targeting.excluded} list${s.targeting.excluded === 1 ? '' : 's'} left out` : ''].filter(Boolean).join(' · '), act: 'openSet', ...add(adsOf(a => a.adset_id === s.id)) }));
    else rows = adsOf(a => (!set || a.adset_id === set.id) && (!camp || a.campaign_id === camp.id)).map(a => ({ id: a.id, name: a.name, status: a.status, sub: a.format, ...add([a]) }));
    rows.sort((a, b) => b.spend - a.spend);
    const cols = 'minmax(0,2fr) 110px 84px repeat(7,minmax(0,0.75fr))';
    const cells = r => html`<span class="medium">${f.money(r.spend)}</span><span class="muted">${f.big(r.impressions)}</span><span class="muted">${f.orDash(per(r.spend * 1000, r.impressions), f.money)}</span>
      <span>${f.num(r.link_clicks)}</span><span class="muted">${f.orDash(rate(r.link_clicks, r.impressions), f.pct)}</span><span class="medium">${f.num(r.chats)}</span><span>${f.orDash(per(r.spend, r.chats), f.moneyAuto)}</span>`;
    return html`
    <div class="grid" style="grid-template-columns:repeat(5,minmax(0,1fr))">
      ${kpi(f.money(t.spend), 'Spent', TIPS.spend, show ? delta(t.spend, t.prev_spend, 'neutral') : '')}
      ${kpi(f.big(t.impressions), 'Times shown', TIPS.impressions, t.impressions ? html`${f.money(t.spend * 1000 / t.impressions)} per 1,000` : '')}
      ${kpi(f.num(t.link_clicks), 'Taps on the ad', TIPS.clicks, t.impressions ? html`${f.pct(t.link_clicks / t.impressions * 100)} of views` : '')}
      ${kpi(f.num(t.chats), 'Chats started', TIPS.chats, show ? delta(t.chats, t.prev_chats) : '')}
      ${kpi(f.orDash(per(t.spend, t.chats), f.moneyAuto), 'Cost of one chat', TIPS.perChat, t.chats ? html`${f.orDash(rate(t.first_replies, t.chats), f.pct)} sent a message` : '', true)}
    </div>
    <div class="card" style="padding:18px 24px 16px">
      <div class="baseline" style="gap:16px;flex-wrap:wrap;margin-bottom:12px"><span class="row" style="gap:8px"><span class="title">${M[metric][0]} per day</span>${info(TIPS.daily)}</span>
        ${switcher(Object.entries(M).map(([k, v]) => ({ arg: `day=${k}`, label: v[0], on: metric === k })), 'set')}</div>
      ${bars(m.days, x => x[metric], M[metric][1], M[metric][2])}
    </div>
    <div class="card clipped" style="--cols:${cols}">
      <div class="baseline" style="padding:16px 16px 10px;gap:16px;flex-wrap:wrap"><span class="row" style="gap:8px;min-width:0"><span class="title">${level === 'campaign' ? 'Campaigns' : level === 'adset' ? 'Ad sets' : 'Ads'}</span>${info(TIPS.table)}
          ${camp && level !== 'campaign' ? html`<span class="pill sm" data-act="clear" data-arg="camp" style="cursor:pointer" title="Show all campaigns">${camp.name} ✕</span>` : ''}
          ${set && level === 'ad' ? html`<span class="pill sm" data-act="clear" data-arg="adset" style="cursor:pointer" title="Show all ad sets">${set.name} ✕</span>` : ''}</span>
        ${switcher([['campaign', 'Campaigns'], ['adset', 'Ad sets'], ['ad', 'Ads']].map(([arg, label]) => ({ arg: `level=${arg}`, label, on: level === arg })), 'set')}</div>
      <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Name</span><span style="text-align:left">Status</span><span>Per day</span><span>Spent</span><span>Shown</span>
        <span class="row" style="gap:5px;justify-content:flex-end">Per 1,000${info(TIPS.cpm, { end: true })}</span><span>Taps</span><span class="row" style="gap:5px;justify-content:flex-end">Tap rate${info(TIPS.ctr, { end: true })}</span><span>Chats</span><span>Per chat</span></div>
      ${rows.map(r => html`<div class="trow right" ${r.act ? html`data-act="${r.act}" data-arg="${r.id}" style="cursor:pointer"` : ''}>
        <div class="stack" style="text-align:left;min-width:0"><span class="medium clip" title="${r.name}">${r.name}</span><span class="tiny muted clip">${r.sub || ''}</span></div>
        <div class="stack" style="align-items:flex-start;gap:1px">${pill(STATUS[r.status], r.status)}${r.learning && LEARNING[r.learning] ? html`<span class="tiny" style="color:var(--${LEARNING[r.learning][1]})">${LEARNING[r.learning][0]}</span>` : ''}</div>
        <span class="muted">${r.budget ? f.money(r.budget) : '—'}</span>${cells(r)}</div>`)}
      ${rows.length > 1 ? html`<div class="trow right tfoot"><span style="text-align:left">Total</span><span></span><span></span>${cells(add(rows))}</div>` : ''}
      ${rows.length ? '' : html`<div class="small muted" style="padding:14px 16px">Nothing here in this period.</div>`}
    </div>
    <div class="row small muted" style="gap:7px">Qualified leads and cost per qualified lead for each ad are not shown yet${info(TIPS.later)}</div>`;
  };

  // ------------------------------------------------------------ creatives
  const creatives = () => {
    const list = m.ads.filter(a => a.impressions || a.status === 'ACTIVE').sort((a, b) => b.spend - a.spend);
    const cheapest = Math.min(...list.filter(a => a.chats >= 3).map(a => a.spend / a.chats));
    const stat = (v, l) => html`<div class="stack"><span class="medium">${v}</span><span class="tiny faint">${l}</span></div>`;
    const rank = (label, value) => html`<div class="between small"><span class="muted">${label}</span><span style="color:var(--${!value ? 'ink3' : value.startsWith('Above') ? 'pos' : value === 'Average' ? 'ink' : 'neg'})">${value || 'Not rated yet'}</span></div>`;
    return html`
    <div class="row small muted" style="gap:14px;flex-wrap:wrap"><span class="row" style="gap:7px">Hook: watched 3 seconds${info(TIPS.hook)}</span><span class="row" style="gap:7px">Hold: stayed to the end${info(TIPS.hold)}</span><span class="row" style="gap:7px">Meta’s rating${info(TIPS.rank)}</span></div>
    <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      ${list.map(a => html`<div class="card clipped stack">
        <div style="aspect-ratio:1.4;background:var(--surface2);position:relative;overflow:hidden">
          ${a.image_url ? html`<img src="${a.image_url}" alt="" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:100%;object-fit:cover">` : html`<div style="display:grid;place-items:center;height:100%" class="small faint">No picture from Meta</div>`}
          <span class="tiny semi" style="position:absolute;top:10px;right:10px;padding:3px 8px;border-radius:999px;background:var(--surface)">${a.format}</span>
          ${a.chats >= 3 && a.spend / a.chats === cheapest && list.length > 1 ? html`<span class="tiny semi" style="position:absolute;top:10px;left:10px;padding:3px 8px;border-radius:999px;background:var(--surface);color:var(--pos)">Cheapest chats</span>` : ''}
        </div>
        <div class="stack" style="padding:14px 16px 16px;gap:12px">
          <div class="stack" style="gap:2px;min-width:0"><span class="semi clip" title="${a.name}">${a.name}</span><span class="small muted clip" title="${a.body || ''}">${a.title || a.body || ''}</span>${pill(STATUS[a.status], a.status)}</div>
          <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px">
            ${stat(f.money(a.spend), 'Spent')}${stat(f.orDash(rate(a.link_clicks, a.impressions), f.pct), 'Tap rate')}${stat(f.num(a.chats), 'Chats')}${stat(f.orDash(per(a.spend, a.chats), f.moneyAuto), 'Per chat')}
            ${a.video_id ? html`${stat(f.orDash(rate(a.video_3s, a.impressions), f.pct), 'Hook')}${stat(f.orDash(rate(a.thruplays, a.video_3s), f.pct), 'Hold')}` : ''}
          </div>
          <div class="stack" style="gap:3px;padding-top:10px;border-top:1px solid var(--line2)">${rank('Quality', a.quality)}${rank('Engagement', a.engagement)}${rank('Conversion', a.conversion)}</div>
          ${a.preview ? html`<a class="link" href="${a.preview}" target="_blank" rel="noopener" style="text-decoration:none">See the ad as people see it</a>` : ''}
        </div>
      </div>`)}
    </div>`;
  };

  // ------------------------------------------------------------ who saw the ads
  const people = () => {
    const metric = ['spend', 'chats', 'impressions'].includes(ui.by) ? ui.by : 'spend';
    const fmt = { spend: f.money, chats: f.num, impressions: f.big }[metric];
    const block = (title, rows) => { const list = (rows || []).slice().sort((a, b) => b[metric] - a[metric]).slice(0, 10), top = Math.max(...list.map(r => r[metric]), 1);
      return html`<div class="card" style="padding:18px 22px 12px"><div class="title" style="margin-bottom:8px;text-transform:none">${title}</div>
        ${list.length ? list.map((r, i) => html`<div class="stack" style="gap:5px;padding:8px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
          <div class="baseline" style="gap:10px"><span class="clip" style="text-transform:capitalize">${r.value}</span>
            <span class="nowrap"><span class="tiny faint">${r.chats ? `${f.moneyAuto(r.spend / r.chats)} per chat` : ''}</span> <span class="medium">${fmt(r[metric])}</span></span></div>
          <div class="track" style="height:8px;border-radius:4px"><div class="fill" style="width:${r[metric] ? Math.max(r[metric] / top * 100, 1.2) : 0}%;background:var(--accent)"></div></div></div>`)
          : html`<div class="small muted" style="padding:6px 0 10px">Nothing in this period.</div>`}</div>`; };
    return html`
    <div class="row" style="gap:12px"><span class="row muted" style="gap:7px">Count by${info(TIPS.breakdown)}</span>${switcher([['spend', 'Spend'], ['chats', 'Chats started'], ['impressions', 'Times shown']].map(([arg, label]) => ({ arg: `by=${arg}`, label, on: metric === arg })), 'set')}</div>
    <div class="grid start" style="grid-template-columns:repeat(3,minmax(0,1fr))">
      ${block('Placement', m.breakdowns.placement)}${block('Age and gender', m.breakdowns.age_gender)}${block('State or region', m.breakdowns.region)}
    </div>`;
  };

  // ------------------------------------------------------------ what Meridian sends to Meta
  const sending = () => {
    const s = m.sending, on = s.setup.mode;
    const MODE = { off: ['Off', 'ink3', 'Nothing leaves Meridian.'], test: ['Test', 'warn', 'Events go only to Meta’s test screen. Nothing is used.'], live: ['Live', 'pos', 'Events are sent to Meta and used to improve the ads.'] }[on];
    const check = (ok, text) => html`<div class="row small" style="gap:8px"><span style="color:var(--${ok ? 'pos' : 'ink3'})">${ok ? '✓' : '○'}</span><span class="${ok ? '' : 'muted'}">${text}</span></div>`;
    const count = (name, status) => (s.by_name.find(x => x.event_name === name && x.status === status) || { n: 0 }).n;
    const WHAT = { LeadSubmitted: 'A chat became a qualified lead', Purchase: 'A qualified lead had a meeting' };
    const ecol = 'minmax(0,1.4fr) repeat(4,minmax(0,0.6fr))', lcol = 'minmax(0,1.6fr) 130px 110px 150px 130px', rcol = '150px minmax(0,1fr) 90px minmax(0,1.4fr)';
    return html`
    <div class="grid start" style="grid-template-columns:minmax(0,1fr) minmax(0,1.2fr)">
      <div class="card pad stack" style="gap:10px">
        <div class="row" style="gap:8px"><span class="title">Sending is</span><span class="pill" style="color:var(--${MODE[1]})">${dot(`var(--${MODE[1]})`)}${MODE[0]}</span>${info(TIPS.mode)}</div>
        <span class="small muted">${MODE[2]} The switch is the setting META_SEND_MODE, changed where the other keys are kept.</span>
      </div>
      <div class="card pad stack" style="gap:6px">
        <span class="title" style="margin-bottom:4px">Setup checklist</span>
        ${check(s.setup.reading, 'Meta Ads connected, so campaigns and spend can be read')}
        ${check(s.setup.dataset, 'The dataset id from Meta Events Manager (META_DATASET_ID)')}
        ${check(s.setup.whatsapp, 'The WhatsApp Business account id (META_WABA_ID)')}
        ${check(s.setup.test_code, 'A test code from Events Manager, for test mode (META_TEST_EVENT_CODE)')}
        ${check(false, 'The WhatsApp bot telling Meridian which ad each chat came from (next phase)')}
      </div>
    </div>
    <div class="card clipped" style="--cols:${ecol}">
      <div class="baseline" style="padding:16px 16px 10px;gap:16px"><span class="row" style="gap:8px"><span class="title">Conversion events</span>${info(TIPS.events)}</span>
        ${lead && on !== 'off' ? html`<span class="btn xs" data-act="sendEvents">Send waiting events now</span>` : ''}</div>
      <div class="thead right" style="border-top:1px solid var(--line)"><span style="text-align:left">Event</span><span>Waiting</span><span>Sent</span><span>Tested</span><span>Failed</span></div>
      ${s.events.map(name => html`<div class="trow right"><div class="stack" style="text-align:left"><span class="medium">${name}</span><span class="tiny muted">${WHAT[name] || ''}</span></div>
        <span>${f.num(count(name, 'queued'))}</span><span class="medium">${f.num(count(name, 'sent'))}</span><span class="muted">${f.num(count(name, 'tested'))}</span>
        <span style="color:var(--${count(name, 'failed') ? 'neg' : 'ink3'})">${f.num(count(name, 'failed') + count(name, 'expired'))}</span></div>`)}
    </div>
    ${s.recent.length ? html`<div class="card clipped" style="--cols:${rcol}">
      <div class="title" style="padding:16px 16px 10px">The last ${s.recent.length} events</div>
      <div class="thead" style="border-top:1px solid var(--line)"><span>When it happened</span><span>Event</span><span>Result</span><span>What Meta answered</span></div>
      ${s.recent.map(e => html`<div class="trow"><span class="muted">${when(e.event_time)}</span><span class="medium">${e.event_name}${e.value != null ? html` <span class="muted">· ${f.money(e.value)}</span>` : ''}</span>
        <span style="color:var(--${e.status === 'sent' ? 'pos' : e.status === 'failed' || e.status === 'expired' ? 'neg' : 'ink2'})">${e.status}</span><span class="tiny muted clip" title="${e.response || ''}">${e.response || ''}</span></div>`)}
    </div>` : ''}
    <div class="card clipped" style="--cols:${lcol}">
      <div class="row" style="gap:8px;padding:16px 16px 10px"><span class="title">Custom audiences</span>${info(TIPS.lists)}</div>
      <div class="thead" style="border-top:1px solid var(--line)"><span>List</span><span>Used to</span><span class="right">People now</span><span>In Meta</span><span></span></div>
      ${s.audiences.map(a => html`<div class="trow">
        <div class="stack" style="min-width:0"><span class="medium">${a.name.replace('Meridian · ', '')}</span><span class="tiny muted pretty">${a.why}</span></div>
        <span class="small" style="color:var(--${a.use === 'exclude' ? 'warn' : 'pos'})">${a.use === 'exclude' ? 'Leave out' : 'Find more like them'}</span>
        <span class="right medium">${f.num(a.people)}</span>
        <span class="small muted">${a.in_meta != null ? `${f.num(a.in_meta)} · ${String(a.synced_at).slice(0, 10)}` : 'Not sent yet'}</span>
        <span class="right">${lead ? html`<span class="btn xs ${on === 'live' && a.people >= 100 ? '' : 'off'}" data-act="pushList" data-arg="${a.key}" title="${on !== 'live' ? 'Sending must be live first' : a.people < 100 ? 'Meta needs at least 100 people' : ''}">${a.in_meta != null ? 'Update in Meta' : 'Send to Meta'}</span>` : ''}</span></div>`)}
    </div>`;
  };

  return html`${head}${view === 'sending' ? sending() : empty ? notYet : { results, creatives, people }[view]()}`;
}

export const metaActions = {
  view: (ctx, d) => ctx.setParams({ ...ctx.app.params, view: d.arg }),
  set(ctx, d) { const at = d.arg.indexOf('='); ctx.ui()[d.arg.slice(0, at)] = d.arg.slice(at + 1) || null; ctx.render(); },
  openCamp(ctx, d) { Object.assign(ctx.ui(), { camp: d.arg, adset: null, level: 'adset' }); ctx.render(); },
  openSet(ctx, d) { Object.assign(ctx.ui(), { adset: d.arg, level: 'ad' }); ctx.render(); },
  clear(ctx, d) { const ui = ctx.ui(); ui[d.arg] = null; if (d.arg === 'camp') ui.adset = null; ctx.render(); },
  async sendEvents(ctx) { try { const r = await ctx.api.post('meta/events/send'); ctx.toast(r.message); ctx.reload(); } catch (err) { ctx.toast(err.message); } },
  async pushList(ctx, d) {
    const list = ctx.app.data.meta.sending.audiences.find(a => a.key === d.arg);
    if (!window.confirm(`Send ${list.people.toLocaleString()} people to Meta as the list “${list.name}”? Their emails are scrambled before they leave.`)) return;
    try { const r = await ctx.api.post('meta/audiences/' + d.arg); ctx.toast(r.message); ctx.reload(); } catch (err) { ctx.toast(err.message); }
  },
};

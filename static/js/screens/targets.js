import { html } from '../html.js';
import * as f from '../format.js';
import { pageHead, info, segmented, switcher, avatar } from '../ui.js';

const TABS = [['progress', 'Progress'], ['today', 'Today'], ['report', 'Week report'], ['blockers', 'Blockers']];
const BLURB = {
  progress: 'How far along each target is, for the week and for the month',
  today: 'What each person needs to do today to stay on track, and what they have done',
  report: 'One week, day by day: what was done on each target, what was written, and what got in the way',
  blockers: 'Things that are stopping work. They stay here until someone marks them solved',
};
const STATUS = { done: ['Done', 'pos'], on_track: ['On track', 'pos'], behind: ['A little behind', 'warn'], far_behind: ['Far behind', 'neg'] };
const TIPS = {
  onTrack: 'How many targets are where they should be by today, or already finished.',
  today: 'Each target asks for a share of the work every working day. This is how many of today’s shares are already done.',
  blockers: 'Problems that someone has reported and nobody has marked as solved yet.',
  person: 'One row for each target. The bar fills up as work is done. The small line on the bar is where it should be by today. If the bar is past the line, the target is on track.',
  days: 'One bar for each working day this week. A taller bar means more was done that day.',
  checklist: 'What this person needs to do today to stay on track. The number is today’s share: what is left, split evenly over the working days that remain. Targets counted from connected tools tick themselves.',
  auto: 'Meridian counts this by itself from the connected tool. Nobody needs to type it in.',
  manual: 'Nobody can count this automatically, so the person presses + each time they do one.',
  week: 'How many of each day’s tasks were finished, over the last five working days.',
  note: 'A short note about today: what was done, or anything worth knowing. It saves when you click away.',
  goalNote: 'A few words about this target today: what you did, or why it did not happen. It shows in the week report.',
  reportTable: 'One row for each target and one column for each working day. The number is what was done that day. Total is the week added up. A dash means nothing was done.',
  dayByDay: 'What the person wrote each day, the one-off tasks they had, and any blockers they reported.',
  metric: 'Choose what to count. If Meridian is connected to the tool it can count it for you. Otherwise choose "We will count it by hand".',
};
const initials = name => name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
const amount = n => (Number.isInteger(n) ? f.num(n) : n.toFixed(1));
const ago = days => (days <= 0 ? 'today' : days === 1 ? 'yesterday' : `${days} days ago`);

export default {
  uses: {},
  // the page and the week report load together; the report follows whichever week is picked
  load: async ctx => { const [main, report] = await Promise.all([ctx.api.get('targets'), ctx.api.get('targets/report', { back: ctx.ui().back || 0 })]); return { ...main, report }; },

  render(d, ctx) {
    const { params } = ctx.app, ui = ctx.ui();
    const user = ctx.app.shell.user, lead = !user || user.admin !== false;  // a team member sees only their own targets and cannot change them
    const view = TABS.some(t => t[0] === params.view) ? params.view : lead ? 'progress' : 'today';
    const who = d.members.some(m => String(m.id) === String(ui.who)) ? Number(ui.who) : null;
    const period = ui.period === 'month' ? 'month' : 'week';
    const members = d.members.filter(m => !who || m.id === who);
    const open = d.blockers.filter(b => !b.resolved_at);
    const name = id => (d.members.find(m => m.id === id) || { name: 'Someone' }).name;
    const goalsOf = (m, p) => d.goals.filter(g => g.member_id === m.id && (!p || g.period === p));
    const pill = status => html`<span class="pill sm" style="color:var(--${STATUS[status][1]})"><span class="dot" style="background:var(--${STATUS[status][1]})"></span>${STATUS[status][0]}</span>`;
    const kpi = (value, label, tip, sub, end, tone) => html`<div class="card kpi" style="padding:16px 18px">
      <span class="kpi-v md" style="${tone ? `color:var(--${tone})` : ''}">${value}</span><span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span><span class="kpi-d faint">${sub}</span></div>`;
    const whoSwitch = d.members.length > 1 ? switcher([{ arg: '', label: 'Everyone', on: !who }, ...d.members.map(m => ({ arg: m.id, label: m.name, on: who === m.id }))], 'who') : '';
    const shown = d.goals.filter(g => (!who || g.member_id === who));
    const onTrack = shown.filter(g => g.status === 'done' || g.status === 'on_track').length;
    const dueToday = shown.filter(g => g.today_share > 0), metToday = dueToday.filter(g => g.today_met).length;
    const tasksToday = d.tasks.filter(t => !who || t.member_id === who);
    const itemsDone = metToday + tasksToday.filter(t => t.done).length, itemsAll = dueToday.length + tasksToday.length;

    const nobody = html`<div class="card pad small muted">${lead ? 'Nobody has targets yet. Click “Add person” to start.' : 'No targets have been set for you yet. Ask a leader to add them.'}</div>`;

    // ------------------------------------------------------------ progress on the targets
    const goalRow = g => html`<div style="display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1.3fr) 130px ${g.period === 'week' ? '150px' : ''};gap:20px;align-items:center;padding:13px 0;border-top:1px solid var(--line2)">
      <div class="stack" style="gap:3px;min-width:0">${lead ? html`<span class="medium clip editable" data-act="editGoal" data-arg="${g.id}" title="Click to change this target">${g.title}</span>` : html`<span class="medium clip">${g.title}</span>`}
        <span class="row tiny muted" style="gap:6px">${g.auto ? `Counted from ${g.source}` : 'Counted by hand'}${info(g.auto ? TIPS.auto : TIPS.manual)}</span></div>
      <div class="stack" style="gap:6px">
        <div class="baseline"><span><span class="semi" style="font-size:16px">${amount(g.done)}</span> <span class="muted">of ${amount(g.target)} ${g.unit}</span></span><span class="medium">${f.pct(Math.min(g.pct, 999))}</span></div>
        <div class="track" style="height:10px;border-radius:5px"><div class="fill" style="width:${Math.min(g.pct, 100)}%;background:var(--${STATUS[g.status][1]})"></div>
          <div class="mark" style="left:${Math.min(g.pace_pct, 100)}%" title="Where it should be by today"></div></div>
      </div>
      <div>${pill(g.status)}</div>
      ${g.period === 'week' ? html`<div style="display:flex;gap:5px;align-items:flex-end;height:38px">${g.days.map(x => { const top = Math.max(...g.days.map(y => y.n), 1); return html`
        <div class="stack" style="flex:1;height:100%;justify-content:flex-end;align-items:center;gap:2px" title="${x.label}: ${amount(x.n)}">
          <div style="width:100%;height:${x.n / top * 100}%;min-height:2px;border-radius:3px 3px 0 0;background:${x.future ? 'var(--track)' : x.n ? 'var(--ink)' : 'var(--ink3)'}"></div>
          <span class="micro faint">${x.label[0]}</span></div>`; })}</div>` : ''}
    </div>`;
    const progress = () => html`
      <div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
        ${kpi(shown.length ? `${onTrack} of ${shown.length}` : '—', 'Targets on track', TIPS.onTrack, shown.length ? `${shown.length - onTrack} need attention` : 'No targets set yet', false, shown.length && onTrack < shown.length ? '' : '')}
        ${kpi(itemsAll ? `${itemsDone} of ${itemsAll}` : '—', 'Done today', TIPS.today, d.working_day ? 'tasks for today' : 'Not a working day')}
        ${kpi(f.num(open.length), 'Open blockers', TIPS.blockers, open.length ? `oldest reported ${ago(Math.max(...open.map(b => b.age_days)))}` : 'Nothing is in the way', true, open.length ? 'warn' : '')}
      </div>
      <div class="row" style="gap:12px;flex-wrap:wrap">${segmented([{ arg: 'week', label: `This week · ${d.week_label}`, on: period === 'week' }, { arg: 'month', label: `This month · ${d.month_label}`, on: period === 'month' }], 'period', 14)}
        <span style="flex:1"></span>${whoSwitch}</div>
      ${members.map(m => { const list = goalsOf(m, period); return html`<div class="card" style="padding:16px 22px 8px">
        <div class="between" style="align-items:center;margin-bottom:6px">
          <div class="row" style="gap:12px">${avatar(initials(m.name), 34)}<div class="stack" style="gap:1px"><span class="row" style="gap:8px"><span class="title">${m.name}</span>${info(TIPS.person)}</span>
            <span class="small muted">${m.focus || 'No focus written yet'}</span></div></div>
          ${lead ? html`<div class="row" style="gap:8px"><span class="btn xs" data-act="editMember" data-arg="${m.id}">Edit</span><span class="btn xs primary" data-act="addGoal" data-arg="${m.id}">Add target</span></div>` : ''}
        </div>
        ${list.length ? list.map(goalRow) : html`<div class="small muted" style="padding:14px 0 16px;border-top:1px solid var(--line2)">No ${period === 'week' ? 'weekly' : 'monthly'} targets for ${m.name} yet.${lead ? ' Click “Add target” to set the first one.' : ''}</div>`}
      </div>`; })}
      ${d.members.length ? '' : nobody}`;

    // ------------------------------------------------------------ today's checklist
    const tick = (on, act, arg) => html`<span ${act ? html`data-act="${act}" data-arg="${arg}"` : ''} style="width:20px;height:20px;border-radius:6px;flex:none;display:grid;place-items:center;font-size:12px;font-weight:700;color:#fff;
      border:1.5px solid ${on ? 'var(--pos)' : 'var(--ink3)'};background:${on ? 'var(--pos)' : 'transparent'};${act ? 'cursor:pointer' : ''}">${on ? '✓' : ''}</span>`;
    const today = () => html`
      <div class="row" style="gap:12px;flex-wrap:wrap"><span class="muted">${d.working_day ? 'Today' : 'Today is not a working day, so nothing is due'}</span><span style="flex:1"></span>${whoSwitch}</div>
      <div class="grid start" style="grid-template-columns:repeat(${Math.min(members.length, 2) || 1},minmax(0,1fr))">
      ${members.map(m => { const due = goalsOf(m).filter(g => g.today_share > 0), tasks = d.tasks.filter(t => t.member_id === m.id);
        const done = due.filter(g => g.today_met).length + tasks.filter(t => t.done).length, all = due.length + tasks.length;
        const mine = open.filter(b => b.member_id === m.id), hist = d.history[m.id] || [];
        return html`<div class="card" style="padding:16px 22px 16px">
        <div class="between" style="align-items:center;margin-bottom:10px">
          <div class="row" style="gap:12px">${avatar(initials(m.name), 34)}<div class="stack" style="gap:1px"><span class="row" style="gap:8px"><span class="title">${m.name}</span>${info(TIPS.checklist)}</span>
            <span class="small muted">${m.focus || ''}</span></div></div>
          <span class="small muted"><span class="ink semi" style="font-size:16px">${done}</span> of ${all} done</span>
        </div>
        ${due.map(g => html`<div class="row" style="gap:12px;padding:10px 0;border-top:1px solid var(--line2)">
          ${tick(g.today_met)}
          <div class="stack" style="flex:1;min-width:0;gap:1px"><span class="${g.today_met ? 'muted' : 'medium'}">${g.title}: ${amount(g.today_share)} today</span>
            <span class="tiny muted">${amount(g.today_done)} done today · ${amount(g.done)} of ${amount(g.target)} this ${g.period} · ${g.auto ? `counted from ${g.source}` : 'counted by hand'}</span></div>
          ${g.auto ? '' : html`<div class="stepper"><span data-act="log" data-arg="${g.id}" data-step="-1">−</span><b style="width:34px">${amount(g.today_done)}</b><span data-act="log" data-arg="${g.id}" data-step="1">+</span></div>`}
        </div>
        <div class="row" style="gap:8px;padding:0 0 10px 32px"><input class="input" id="gnote-${g.id}" value="${g.today_note || ''}" placeholder="What did you do on this today? (optional)" data-change="goalNote" data-goal="${g.id}" autocomplete="off" style="font-size:12px;padding:5px 9px">${info(TIPS.goalNote, { end: true })}</div>`)}
        ${tasks.map(t => html`<div class="row" style="gap:12px;padding:10px 0;border-top:1px solid var(--line2)">
          ${tick(!!t.done, 'toggleTask', t.id)}<span class="${t.done ? 'muted' : 'medium'}" style="flex:1;min-width:0;${t.done ? 'text-decoration:line-through' : ''}">${t.title}</span>
          <span class="tiny faint" data-act="removeTask" data-arg="${t.id}" style="cursor:pointer" title="Remove this task">Remove</span></div>`)}
        ${all ? '' : html`<div class="small muted" style="padding:10px 0;border-top:1px solid var(--line2)">Nothing is due today. ${lead ? 'Add a target on the Progress tab, or a one-off task below.' : 'You can add a one-off task below.'}</div>`}
        <form class="row" data-submit="addTask" style="gap:8px;padding:10px 0 0;border-top:1px solid var(--line2)">
          <input type="hidden" name="member_${m.id}" value="${m.id}">
          <input class="input" name="task_${m.id}" placeholder="Add a one-off task for today" autocomplete="off" style="flex:1"><button class="btn" type="submit" name="for" value="${m.id}">Add</button></form>
        <div class="stack" style="gap:6px;margin-top:14px">
          <span class="row small muted" style="gap:7px">Note for today${info(TIPS.note)}</span>
          <textarea class="input" id="note-${m.id}" rows="2" placeholder="What got done, or anything worth knowing" data-change="note" data-member="${m.id}">${d.notes[m.id] || ''}</textarea>
        </div>
        <form class="row" data-submit="addBlocker" style="gap:8px;margin-top:10px">
          <input class="input" name="blocker_${m.id}" placeholder="Is anything stopping the work? Write it here" autocomplete="off" style="flex:1"><button class="btn" type="submit" name="for" value="${m.id}">Report blocker</button></form>
        ${mine.length ? html`<div class="small" style="margin-top:8px;color:var(--warn)">${mine.length} open blocker${mine.length === 1 ? '' : 's'}: ${mine.map(b => b.text).join(' · ')}</div>` : ''}
        <div style="margin-top:16px;padding-top:12px;border-top:1px solid var(--line2)">
          <div class="row small muted" style="gap:7px;margin-bottom:6px">Last five working days${info(TIPS.week)}</div>
          <div style="display:flex;gap:10px;align-items:flex-end;height:70px">${hist.map(x => html`<div class="stack" style="flex:1;height:100%;justify-content:flex-end;align-items:center;gap:3px">
            <span class="tiny medium">${x.total ? `${x.met}/${x.total}` : '—'}</span>
            <div style="width:100%;max-width:56px;height:${x.total ? x.met / x.total * 100 : 0}%;min-height:3px;border-radius:5px 5px 0 0;background:${!x.total ? 'var(--track)' : x.met >= x.total ? 'var(--pos)' : x.met ? 'oklch(0.70 0.14 65)' : 'var(--neg)'}"></div></div>`)}</div>
          <div style="display:flex;gap:10px;margin-top:4px">${hist.map(x => html`<span class="micro muted" style="flex:1;text-align:center">${x.label}</span>`)}</div>
        </div>
      </div>`; })}
      </div>${d.members.length ? '' : nobody}`;

    // ------------------------------------------------------------ the week, day by day
    const report = () => { const r = d.report, people = r.people.filter(p => !who || p.id === who);
      const cols = `minmax(0,1.6fr) repeat(${r.days.length},minmax(54px,0.6fr)) 70px 110px`;
      const dayName = iso => (r.days.find(x => x.day === iso) || { label: iso }).label;
      return html`
      <div class="row" style="gap:12px;flex-wrap:wrap">
        <div class="seg"><div data-act="week" data-arg="1">◀ Earlier week</div><div class="on" style="cursor:default">${r.label}${r.current ? ' · this week' : ''}</div>${r.back ? html`<div data-act="week" data-arg="-1">Later week ▶</div>` : ''}</div>
        <span style="flex:1"></span>${whoSwitch}<span class="btn" data-act="print">Print or save as PDF</span></div>
      ${people.map(p => { const written = r.days.filter(x => p.notes[x.day] || (p.tasks[x.day] || []).length || p.goals.some(g => (g.days.find(y => y.day === x.day) || {}).note));
        return html`<div class="card" style="padding:16px 22px 14px">
        <div class="row" style="gap:12px;margin-bottom:10px">${avatar(initials(p.name), 34)}<div class="stack" style="gap:1px"><span class="title">${p.name}</span><span class="small muted">${p.focus || ''}</span></div></div>
        ${p.goals.length ? html`
          <div class="thead right" style="--cols:${cols};padding:8px 0;border-top:1px solid var(--line)"><span class="row" style="gap:7px;text-align:left">Target${info(TIPS.reportTable)}</span>
            ${r.days.map(x => html`<span>${x.label.split(' ')[0]} <span class="faint">${x.label.split(' ')[1]}</span></span>`)}<span>Total</span><span>Against target</span></div>
          ${p.goals.map(g => html`<div class="trow right" style="--cols:${cols};padding:10px 0">
            <div class="stack" style="text-align:left;min-width:0"><span class="medium clip" title="${g.title}">${g.title}</span><span class="tiny muted">${g.period === 'week' ? 'Weekly' : 'Monthly'} target of ${amount(g.target)} ${g.unit} · ${g.auto ? 'counted for us' : 'counted by hand'}</span></div>
            ${g.days.map(x => html`<span class="${x.n ? 'medium' : 'faint'}" title="${x.note || ''}">${x.future ? '' : x.n ? amount(x.n) : '—'}${x.note ? html`<span style="color:var(--accent)" title="${x.note}"> •</span>` : ''}</span>`)}
            <span class="semi">${amount(g.total)}</span>
            <span class="small" style="color:var(--${g.pct >= 100 ? 'pos' : g.pct >= 60 ? 'warn' : 'neg'})">${f.pct(Math.min(g.pct, 999))}${g.period === 'month' ? ' of month' : ''}</span></div>`)}`
          : html`<div class="small muted" style="padding:10px 0;border-top:1px solid var(--line2)">No targets were set for ${p.name} in this week.</div>`}
        <div class="row small muted" style="gap:7px;margin:14px 0 4px">Day by day${info(TIPS.dayByDay)}</div>
        ${written.length ? written.map(x => html`<div style="display:grid;grid-template-columns:110px minmax(0,1fr);gap:14px;padding:9px 0;border-top:1px solid var(--line2)">
          <span class="medium">${x.label}</span>
          <div class="stack" style="gap:4px;min-width:0">
            ${p.notes[x.day] ? html`<span class="pretty">${p.notes[x.day]}</span>` : ''}
            ${p.goals.map(g => { const e = g.days.find(y => y.day === x.day); return e && e.note ? html`<span class="small"><span class="muted">${g.title}:</span> ${e.note}</span>` : ''; })}
            ${(p.tasks[x.day] || []).map(t => html`<span class="small ${t.done ? '' : 'muted'}">${t.done ? '✓' : '○'} ${t.title}${t.done ? '' : ' (not done)'}</span>`)}
          </div></div>`) : html`<div class="small muted" style="padding:8px 0;border-top:1px solid var(--line2)">Nothing was written this week.</div>`}
        ${p.blockers.length ? html`<div class="small" style="margin-top:8px;padding-top:10px;border-top:1px solid var(--line2)"><span class="medium" style="color:var(--warn)">Blockers reported:</span>
          ${p.blockers.map(b => html`<div class="row" style="gap:8px;padding-top:4px"><span class="muted">${dayName(b.day)}</span><span>${b.text}</span><span class="tiny ${b.solved ? 'faint' : ''}" style="${b.solved ? '' : 'color:var(--warn)'}">${b.solved ? 'solved' : 'still open'}</span></div>`)}</div>` : ''}
      </div>`; })}`; };

    // ------------------------------------------------------------ blockers
    const blockerRow = b => html`<div class="row" style="gap:14px;padding:12px 0;border-top:1px solid var(--line2);align-items:flex-start">
      ${avatar(initials(name(b.member_id)), 28)}
      <div class="stack" style="flex:1;min-width:0;gap:2px"><span class="${b.resolved_at ? 'muted' : 'medium'} pretty">${b.text}</span>
        <span class="tiny muted">${name(b.member_id)} · reported ${ago(b.age_days)}${b.resolved_at ? ' · solved' : ''}</span></div>
      ${b.resolved_at ? html`<span class="btn xs" data-act="reopen" data-arg="${b.id}">Open again</span>` : html`<span class="btn xs primary" data-act="solve" data-arg="${b.id}">Mark solved</span>`}
    </div>`;
    const blockers = () => { const mineOpen = open.filter(b => !who || b.member_id === who), solved = d.blockers.filter(b => b.resolved_at && (!who || b.member_id === who)); return html`
      <div class="row" style="gap:12px;flex-wrap:wrap"><span class="muted">${mineOpen.length} open · ${solved.length} solved</span><span style="flex:1"></span>${whoSwitch}</div>
      <div class="card" style="padding:16px 22px 8px">
        <div class="title" style="margin-bottom:8px">Open now</div>
        ${mineOpen.length ? mineOpen.map(blockerRow) : html`<div class="small muted" style="padding:10px 0 14px;border-top:1px solid var(--line2)">Nothing is blocking anyone. A blocker is added from the Today tab.</div>`}
      </div>
      ${solved.length ? html`<div class="card" style="padding:16px 22px 8px"><div class="title" style="margin-bottom:8px">Solved</div>${solved.slice(0, 20).map(blockerRow)}</div>` : ''}`; };

    return html`
    ${pageHead(`${d.week_label} · ${d.month_label}`, 'Targets', html`<div class="row" style="gap:10px">${segmented(TABS.map(([arg, label]) => ({ arg, label: arg === 'blockers' && open.length ? `${label} · ${open.length}` : label, on: view === arg })), 'view', 16)}
      ${lead ? html`<a class="btn" href="#/people" style="text-decoration:none">Add person</a>` : ''}</div>`)}
    ${d.demo ? html`<div class="row small" style="gap:12px;padding:9px 14px;border-radius:10px;background:color-mix(in oklch, var(--warn) 12%, var(--surface))">
      <span><span class="semi">Example data.</span> The hand-counted numbers, notes, tasks and blockers on this page are made up to show how it works.</span>
      <span style="flex:1"></span><span class="btn xs" data-act="clearDemo">Remove example data</span></div>` : ''}
    <div class="row" style="gap:10px;margin:2px 0 -2px;flex-wrap:wrap"><span class="section">${TABS.find(t => t[0] === view)[1]}</span><span class="muted">${BLURB[view]}</span></div>
    ${{ progress, today, report, blockers }[view]()}`;
  },

  modal(m, ctx) {
    const d = ctx.app.data;
    if (m.kind === 'member') {
      const p = m.member || {};
      return html`<form class="modal" data-submit="saveMember">
        <span class="section">${m.member ? 'Edit ' + p.name : 'Add a person'}</span>
        <label class="field">Name<input class="input" name="name" value="${p.name || ''}" required data-autofocus></label>
        <label class="field">What they look after<input class="input" name="focus" value="${p.focus || ''}" placeholder="e.g. SEO and LinkedIn posts"></label>
        <div class="between" style="margin-top:4px"><span></span>
          <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div></div>
      </form>`;
    }
    const g = m.goal || { member_id: m.member_id, metric: 'manual', period: ctx.ui().period === 'month' ? 'month' : 'week' };
    return html`<form class="modal" data-submit="saveGoal">
      <span class="section">${m.goal ? 'Change this target' : 'Add a target'}</span>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <label class="field">Who is it for<select class="input" name="member_id">${d.members.map(p => html`<option value="${p.id}" ${p.id === g.member_id ? 'selected' : ''}>${p.name}</option>`)}</select></label>
        <label class="field">For how long<select class="input" name="period"><option value="week" ${g.period === 'week' ? 'selected' : ''}>Each week</option><option value="month" ${g.period === 'month' ? 'selected' : ''}>Each month</option></select></label>
      </div>
      <label class="field"><span class="row" style="gap:7px">What to count${info(TIPS.metric)}</span><select class="input" name="metric">
        <option value="manual" ${g.metric === 'manual' ? 'selected' : ''}>We will count it by hand (posts, blogs, calls…)</option>
        ${d.metrics.map(x => html`<option value="${x.key}" ${g.metric === x.key ? 'selected' : ''}>${x.name} · counted from ${x.source}</option>`)}</select></label>
      <label class="field">Name of the target<input class="input" name="title" value="${g.title || ''}" placeholder="e.g. LinkedIn posts published. Leave empty to use the name above"></label>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <label class="field">Target number<input class="input" name="target" type="number" min="1" step="any" value="${g.target == null ? '' : g.target}" required ${m.goal ? '' : 'data-autofocus'}></label>
        <label class="field">Counted in (for hand-counted targets)<input class="input" name="unit" value="${g.auto ? '' : g.unit || ''}" placeholder="e.g. posts"></label>
      </div>
      <div class="between" style="margin-top:4px">${m.goal ? html`<button type="button" class="btn danger" data-act="removeGoal" data-arg="${g.id}">Delete</button>` : html`<span></span>`}
        <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div></div>
    </form>`;
  },

  actions: {
    view: (ctx, d) => ctx.setParams({ view: d.arg }),
    who(ctx, d) { ctx.ui().who = d.arg || null; ctx.render(); },
    period(ctx, d) { ctx.ui().period = d.arg; ctx.render(); },
    week(ctx, d) { const ui = ctx.ui(); ui.back = Math.max((ui.back || 0) + Number(d.arg), 0); ctx.reload(); },
    print: () => window.print(),
    clearDemo: ctx => ctx.save(() => ctx.api.post('targets', { what: 'clear_demo' }), 'Example data removed. The page is ready for real targets.'),
    editMember: (ctx, d) => ctx.openModal({ kind: 'member', member: ctx.app.data.members.find(m => String(m.id) === d.arg) }),
    addGoal: (ctx, d) => ctx.openModal({ kind: 'goal', goal: null, member_id: Number(d.arg) }),
    editGoal: (ctx, d) => ctx.openModal({ kind: 'goal', goal: ctx.app.data.goals.find(g => String(g.id) === d.arg) }),
    async removeGoal(ctx, d) { ctx.app.modal = null; await ctx.save(() => ctx.api.post('targets', { what: 'remove_goal', id: Number(d.arg) }), 'Target removed.'); },
    log: (ctx, d) => ctx.save(() => ctx.api.post('targets', { what: 'log', id: Number(d.arg), amount: Number(d.step) })),
    toggleTask: (ctx, d) => ctx.save(() => ctx.api.post('targets', { what: 'toggle_task', id: Number(d.arg) })),
    removeTask: (ctx, d) => ctx.save(() => ctx.api.post('targets', { what: 'remove_task', id: Number(d.arg) })),
    solve: (ctx, d) => ctx.save(() => ctx.api.post('targets', { what: 'resolve', id: Number(d.arg), solved: true }), 'Marked as solved.'),
    reopen: (ctx, d) => ctx.save(() => ctx.api.post('targets', { what: 'resolve', id: Number(d.arg), solved: false })),
  },

  changes: {
    goalNote: (ctx, value, el) => ctx.save(() => ctx.api.post('targets', { what: 'goal_note', id: Number(el.dataset.goal), text: value }), 'Saved.'),
    note: (ctx, value, el) => ctx.save(() => ctx.api.post('targets', { what: 'note', member_id: Number(el.dataset.member), text: value }), 'Note saved.'),
  },

  submits: {
    async saveMember(ctx, v) {
      const member = ctx.app.modal.member;
      ctx.app.modal = null;
      await ctx.save(() => ctx.api.post('targets', { what: 'member', id: member ? member.id : null, name: v.name, focus: v.focus, email: member ? member.email : null }), member ? 'Saved.' : 'Added to the team.');
    },
    async saveGoal(ctx, v) {
      const goal = ctx.app.modal.goal;
      ctx.app.modal = null;
      await ctx.save(() => ctx.api.post('targets', { what: 'goal', id: goal ? goal.id : null, member_id: Number(v.member_id), title: v.title, metric: v.metric,
        period: v.period, target: Number(v.target), unit: v.unit }), goal ? 'Target saved.' : 'Target added.');
    },
    // the forms repeat once per person, so each field carries the person's id in its name
    addTask(ctx, v, form) {
      const id = Number(Object.keys(v).find(k => k.startsWith('member_')).slice(7)), title = v['task_' + id];
      form.reset();
      return ctx.save(() => ctx.api.post('targets', { what: 'task', member_id: id, title }));
    },
    addBlocker(ctx, v, form) {
      const key = Object.keys(v).find(k => k.startsWith('blocker_')), id = Number(key.slice(8)), text = v[key];
      form.reset();
      return ctx.save(() => ctx.api.post('targets', { what: 'blocker', member_id: id, text }), 'Blocker reported.');
    },
  },
};

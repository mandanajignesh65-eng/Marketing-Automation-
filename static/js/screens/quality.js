import { html } from '../html.js';
import * as f from '../format.js';
import { sq, pageHead, stepper, bar, info, segmented, switcher } from '../ui.js';

let previewTimer;

const TABS = [['picture', 'How good are our leads'], ['rules', 'Scoring rules']];
const BLURB = { picture: 'How many leads we can judge, and what stops us judging the rest', rules: 'How the score is worked out, and where the bar is set' };
// One colour per answer: green fits, grey does not, and three shades of amber for "we cannot tell", each for a different reason.
const VERDICT = {
  fits: ['var(--pos)', '#fff', 'These leads look like the customers we want. Their company is in the right industry and big enough.'],
  no_fit: ['var(--ink3)', '#fff', 'We know the company, and it is not the kind we want: another industry, or too small.'],
  person: ['oklch(0.80 0.10 80)', 'var(--ink)', 'These gave a personal email like Gmail, or no email, and no real company name. There is nothing to check. Many are people asking a question, not businesses.'],
  pending: ['oklch(0.70 0.14 65)', '#fff', 'These gave a company name or a work email, but we have not looked the company up yet. Running the lookup will sort most of them.'],
  not_found: ['oklch(0.60 0.15 45)', '#fff', 'We looked the company up and our free source did not know it. This is the biggest gap. A second source of company details would sort many of these.'],
};
const TIPS = {
  leads: 'New leads from marketing in this period.',
  qualified: 'Leads that look like the customers we want: the right industry and a big enough company.',
  judged: 'Leads where we know enough about the company to say yes or no. Qualified plus "checked, not a fit".',
  blind: 'Leads we cannot judge, because we do not know what company they are from. These all score 0, so they look bad even if some are good.',
  verdicts: 'Every lead falls into one of five groups, one bar each. A taller bar means more leads. Green means it fits. Grey means it does not. The three orange bars mean we cannot tell, each for a different reason. Use the buttons to see one channel.',
  known: 'What we actually know about our leads. The taller the bar, the more leads have that detail. To judge a lead we need its industry, and to find the industry we need a company name or a work email.',
  actions: 'The steps that would let us judge more leads, biggest first. The number is how many of this period\u2019s leads each step could sort.',
  hist: 'How many leads got each score. Leads at or to the right of the line are qualified. A tall bar at 0 means many leads could not be scored at all.',
  best: 'Which channels bring leads with the best scores. Average score is out of 100. Qualified rate is how many of every 100 leads from that channel qualify.',
  rules: 'How points are given. The numbers must add up to 100. Use + and \u2212 to change how much each thing counts, then save. Every lead is scored again.',
  bar: 'A lead needs at least this many points out of 100 to count as qualified.',
};

// The editor works on a draft of the weights and threshold until it is saved or discarded.
function draft(d, ui) {
  const saved = Object.fromEntries(d.criteria.map(c => [c.key, c.weight]));
  const weights = ui.weights || saved;
  const threshold = ui.threshold != null ? ui.threshold : d.threshold;
  const dirty = threshold !== d.threshold || d.criteria.some(c => weights[c.key] !== c.weight);
  return { weights, threshold, dirty, sum: Object.values(weights).reduce((a, b) => a + b, 0) };
}

function schedulePreview(ctx) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(async () => {
    const ui = ctx.ui(), d = ctx.app.data;
    if (!d || ctx.app.screen !== 'quality') return;
    const { weights, threshold, dirty } = draft(d, ui);
    if (!dirty) { ui.estimate = null; return ctx.render(); }
    try {
      ui.estimate = (await ctx.api.post('scoring/preview', { weights, threshold, ...ctx.rangeParams() })).qualified;
    } catch (err) { ui.estimate = null; }
    ctx.render();
  }, 200);
}

export default {
  uses: { range: true },
  load: ctx => ctx.api.get('quality', ctx.rangeParams()),

  render(d, ctx) {
    const ui = ctx.ui();
    const { weights, threshold: t, dirty, sum } = draft(d, ui);
    const cov = d.coverage;
    const est = dirty ? ui.estimate : d.qualified;
    const top = Math.max(...d.hist, 1) * 1.08;
    const hist = d.hist.map((v, i) => ({
      v, h: v / top * 100, label: i === 9 ? '90+' : String(i * 10),
      color: i * 10 >= t ? 'var(--pos)' : i * 10 + 10 > t ? 'color-mix(in srgb, var(--pos) 45%, var(--track))' : 'var(--ink3)',
      opacity: i * 10 + 10 > t ? 1 : 0.55,
    }));
    const chans = d.channels.map(c => ({ ...c, ...ctx.channel(c.id), rate: c.leads ? c.qualified / c.leads * 100 : 0 })).sort((a, b) => b.rate - a.rate);
    const groups = ['Fit', 'Intent'].map(g => ({ g, items: d.criteria.filter(c => c.grp === g) }));
    const diff = est == null ? '' : est === d.qualified ? 'Same as today' : `${est > d.qualified ? '+' : '−'}${Math.abs(est - d.qualified)} vs current rules`;

    const rules = () => html`
    <div class="grid start" style="grid-template-columns:minmax(0,1.25fr) minmax(0,1fr)">
      <div class="card stack" style="padding:18px 20px 16px;gap:14px">
        <div class="baseline"><span class="row" style="gap:8px"><span class="title">How leads scored</span>${info(TIPS.hist)}</span>
          <span class="small muted"><span class="ink medium">${est == null ? '…' : f.num(est)}</span> of ${f.num(d.total)} at ${t} or above</span></div>
        <div style="position:relative;height:200px;margin-top:22px">
          <div style="position:absolute;inset:0;display:flex;align-items:flex-end;gap:6px">
            ${hist.map(b => html`<div class="stack" style="flex:1;height:100%;justify-content:flex-end;align-items:center;gap:4px">
              <span class="tiny muted">${f.num(b.v)}</span><div style="width:100%;height:${b.h}%;border-radius:4px 4px 1px 1px;background:${b.color};opacity:${b.opacity}"></div></div>`)}
          </div>
          <div style="position:absolute;left:${t}%;top:-22px;bottom:0;width:1.5px;background:var(--ink)"></div>
          <span class="tiny medium nowrap" style="position:absolute;top:-24px;${t > 80 ? `right:${100 - t}%;padding-right:6px` : `left:${t}%;padding-left:6px`}">Qualifies at ${t}</span>
        </div>
        <div style="display:flex;gap:6px">${hist.map(b => html`<span class="micro faint" style="flex:1">${b.label}</span>`)}</div>
        ${cov && (cov.researched || cov.with_industry < cov.leads) ? html`<div class="small muted pretty" style="padding-top:12px;border-top:1px solid var(--line2)">
          Company details: <span class="ink medium">${f.num(cov.with_industry)}</span> of ${f.num(cov.leads)} leads have an industry and <span class="ink medium">${f.num(cov.with_size)}</span> a company size${cov.researched ? html` · ${f.num(cov.researched)} filled in by company research` : ''}. A lead with neither scores 0.</div>` : ''}
      </div>
      <div class="card" style="padding:18px 20px 8px">
        <div class="small muted medium" style="display:grid;grid-template-columns:minmax(0,1fr) 62px minmax(0,1fr) 50px;gap:12px;padding-bottom:8px;align-items:baseline">
          <span class="row title ink" style="gap:8px">Best-fit channels${info(TIPS.best)}</span><span class="right nowrap">Avg score</span><span>Qualified rate</span><span></span></div>
        ${chans.map(c => html`<div style="display:grid;grid-template-columns:minmax(0,1fr) 62px minmax(0,1fr) 50px;gap:12px;align-items:center;padding:9px 0;border-top:1px solid var(--line2)">
          <span class="row" style="gap:8px;min-width:0">${sq(c.color)}<span class="clip">${c.name}</span></span>
          <span class="right medium">${Math.round(c.avg)}</span>${bar(c.rate / 50 * 100, c.color)}<span class="right medium">${f.pct(c.rate)}</span></div>`)}
      </div>
    </div>
    <div class="card stack" style="padding:18px 20px 20px;gap:16px">
      <div class="baseline"><span class="row" style="gap:8px"><span class="title">How points are given</span>${info(TIPS.rules)}</span><span class="small faint">${d.changed}</span></div>
      <div class="grid start" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr) 260px;gap:24px">
        ${groups.map(g => html`<div class="stack">
          <div class="between tiny medium faint" style="padding-bottom:6px"><span>${g.g}</span><span>${g.items.reduce((a, c) => a + weights[c.key], 0)} points</span></div>
          ${g.items.map(c => html`<div class="row" style="gap:12px;padding:11px 0;border-top:1px solid var(--line2)">
            <div class="stack" style="flex:1;min-width:0;gap:1px"><span class="medium">${c.label}</span><span class="small muted pretty">${c.rule}</span></div>
            ${stepper(weights[c.key], 'weight', c.key)}</div>`)}
        </div>`)}
        <div class="inset stack" style="gap:14px">
          <div class="between" style="align-items:center"><span class="row medium" style="gap:7px">Qualifies at${info(TIPS.bar, { end: true })}</span>${stepper(t, 'threshold', '', 34)}</div>
          <div class="stack" style="gap:2px"><span style="font-size:30px;font-weight:600;letter-spacing:-0.025em">${est == null ? '…' : f.num(est)}</span>
            <span class="small muted">qualified ${ctx.app.range === 'month' ? 'this month' : 'in this range'} with these rules${diff ? ' · ' + diff : ''}</span></div>
          <span class="small" style="color:var(--${sum === 100 ? 'pos' : 'neg'})">${sum === 100 ? 'Weights total 100' : `Weights total ${sum}, needs 100`}</span>
          <div class="row" style="gap:8px"><div class="btn primary ${dirty && sum === 100 ? '' : 'disabled'}" data-act="save">Save and rescore</div>
            <div class="btn ${dirty ? '' : 'disabled'}" data-act="discard">Discard</div></div>
        </div>
      </div>
    </div>`;

    // ---------------------------------------------------------------- the picture: can we judge our leads?
    const picture = () => {
      const c = d.clarity, k = c.known, n = id => (c.verdicts.find(v => v.id === id) || { n: 0 }).n;
      const judged = n('fits') + n('no_fit'), blind = n('person') + n('pending') + n('not_found');
      const share = (a, b) => (b ? f.pct(a / b * 100) : '—');
      const kpi = (value, label, tip, sub, end) => html`<div class="card kpi" style="padding:16px 18px">
        <span class="kpi-v md">${f.num(value)}</span><span class="row eyebrow" style="gap:7px">${label}${info(tip, { end })}</span><span class="kpi-d faint">${sub}</span></div>`;
      // one upright bar per group; the buttons pick all channels or a single one
      const chan = c.by_channel.some(r => r.id === ui.chan) ? ui.chan : null;
      const row = chan ? c.by_channel.find(r => r.id === chan) : Object.fromEntries(c.verdicts.map(v => [v.id, v.n]));
      const rowTotal = chan ? row.leads : k.leads;
      const upright = (cols, { height = 240, pct = false } = {}) => { const top = pct ? 100 : Math.max(...cols.map(x => x.value), 1) * 1.12; return html`
        <div style="display:flex;gap:18px;align-items:flex-end;height:${height}px;border-bottom:1px solid var(--line)">
          ${cols.map(x => html`<div class="stack" style="flex:1;min-width:0;height:100%;justify-content:flex-end;align-items:center;gap:6px">
            <span style="font-size:17px;font-weight:600;letter-spacing:-0.01em">${x.top}</span>
            <div title="${x.label}: ${x.top}" style="width:min(100%,120px);height:${x.value / top * 100}%;min-height:${x.value ? 3 : 0}px;border-radius:8px 8px 0 0;background:${x.color}"></div></div>`)}
        </div>
        <div style="display:flex;gap:18px;margin-top:8px">${cols.map(x => html`<div class="stack" style="flex:1;min-width:0;align-items:center;gap:2px;text-align:center">
          <span class="row small medium" style="gap:6px;justify-content:center;flex-wrap:wrap">${x.label}${x.tip ? info(x.tip, { end: x.end }) : ''}</span>
          <span class="tiny muted">${x.sub}</span></div>`)}</div>`; };
      const facts = [['Gave an email', k.email], ['Gave a work email', k.work_email], ['Gave a real company name', k.company], ['Industry known', k.industry], ['Company size known', k.size], ['Job title known', k.title]];
      const steps = [
        n('not_found') ? [n('not_found'), 'Add a second place to look companies up', `We looked up ${f.num(n('not_found'))} companies and our one free source did not know them. A second source would sort many of these. This is the biggest gap.`] : null,
        n('person') ? [n('person'), 'Ask for the company on forms and in the chatbot', `${f.num(n('person'))} leads gave a personal email and no company, so there is nothing to check. A "Company name" box, and asking for a work email, fixes this at the start.`] : null,
        n('pending') ? [n('pending'), 'Look up the companies not checked yet', `${f.num(n('pending'))} leads have a company name or work email that has not been looked up. ${c.lookup_ready ? 'Press Sync on the Crustdata card in Settings.' : 'The lookup is not switched on to run by itself yet.'}`] : null,
        k.leads && k.title / k.leads < 0.5 ? [k.leads - k.title, 'Collect the job title', `Only ${f.num(k.title)} of ${f.num(k.leads)} leads have a job title. Without it we cannot tell a decision maker from a junior. A "Job title" box on forms would let the score use it.`] : null,
      ].filter(Boolean);
      // biggest gap first; the job title goes last because it sharpens the score but does not unblock any lead
      const title = steps.find(x => x[1] === 'Collect the job title');
      steps.splice(0, steps.length, ...steps.filter(x => x !== title).sort((x, y) => y[0] - x[0]), ...(title ? [title] : []));
      return html`
      <div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        ${kpi(k.leads, 'Leads', TIPS.leads, d.period.short)}
        ${kpi(n('fits'), 'Qualified', TIPS.qualified, `${share(n('fits'), k.leads)} of leads`)}
        ${kpi(judged, 'Leads we can judge', TIPS.judged, `${share(judged, k.leads)} of leads`)}
        ${kpi(blind, 'Leads we cannot judge', TIPS.blind, `${share(blind, k.leads)} of leads`, true)}
      </div>
      <div class="card" style="padding:18px 24px 18px">
        <div class="baseline" style="gap:16px;flex-wrap:wrap;margin-bottom:14px"><span class="row" style="gap:8px"><span class="title">Can we judge each lead?</span>${info(TIPS.verdicts)}
            <span class="small muted">${chan ? ctx.channel(chan).name : 'all channels'} · ${f.num(rowTotal)} leads</span></span>
          ${switcher([{ arg: '', label: 'All channels', on: !chan }, ...c.by_channel.map(r => ({ arg: r.id, label: ctx.channel(r.id).name, color: ctx.channel(r.id).color, on: chan === r.id }))], 'chan')}</div>
        ${upright(c.verdicts.map((v, i) => ({ label: v.label, value: row[v.id], top: f.num(row[v.id]), sub: `${share(row[v.id], rowTotal)} of leads`, color: VERDICT[v.id][0], tip: VERDICT[v.id][2], end: i > 2 })))}
      </div>
      <div class="grid start" style="grid-template-columns:minmax(0,1fr) minmax(0,1.15fr)">
        <div class="card" style="padding:18px 24px 12px">
          <div class="row" style="gap:8px;margin-bottom:10px"><span class="title">What we know about each lead</span>${info(TIPS.known)}</div>
          ${upright(facts.map(([label, v]) => { const pc = k.leads ? v / k.leads * 100 : 0; return { label, value: pc, top: f.pct(pc), sub: `${f.num(v)} of ${f.num(k.leads)}`,
            color: pc >= 60 ? 'var(--pos)' : pc >= 30 ? 'oklch(0.70 0.14 65)' : 'var(--neg)' }; }), { height: 200, pct: true })}
          <div class="small muted" style="padding:12px 0 6px;margin-top:10px;border-top:1px solid var(--line2)">Of the ${f.num(k.industry)} leads with a known industry, <span class="ink medium">${f.num(k.from_lookup)}</span> came from looking the company up and <span class="ink medium">${f.num(k.from_crm)}</span> were typed into Zoho.</div>
        </div>
        <div class="card" style="padding:18px 24px 14px">
          <div class="row" style="gap:8px;margin-bottom:10px"><span class="title">How to judge more leads</span>${info(TIPS.actions)}</div>
          ${steps.length ? steps.map(([count, title, text], i) => html`<div style="display:grid;grid-template-columns:64px minmax(0,1fr);gap:14px;padding:11px 0;border-top:${i ? '1px solid var(--line2)' : 'none'}">
            <div class="stack" style="align-items:flex-start"><span style="font-size:22px;font-weight:600;letter-spacing:-0.02em">${f.num(count)}</span><span class="tiny faint">leads</span></div>
            <div class="stack" style="gap:2px"><span class="semi">${i + 1}. ${title}</span><span class="small muted pretty">${text}</span></div></div>`)
            : html`<div class="small muted" style="padding:8px 0">Every lead in this period could be judged.</div>`}
        </div>
      </div>`;
    };

    const view = TABS.some(x => x[0] === ctx.app.params.view) ? ctx.app.params.view : 'picture';
    return html`
    ${pageHead(`${f.num(d.total)} leads · ${d.period.short}`, 'Lead quality', segmented(TABS.map(([arg, label]) => ({ arg, label, on: view === arg })), 'view', 16))}
    <div class="row" style="gap:10px;margin:2px 0 -2px;flex-wrap:wrap"><span class="section">${TABS.find(x => x[0] === view)[1]}</span><span class="muted">${BLURB[view]}</span></div>
    ${view === 'rules' ? rules() : picture()}`;
  },

  actions: {
    view: (ctx, d) => ctx.setParams({ view: d.arg }),
    chan(ctx, d) { ctx.ui().chan = d.arg || null; ctx.render(); },
    weight(ctx, d) {
      const ui = ctx.ui(), cur = draft(ctx.app.data, ui).weights;
      ui.weights = { ...cur, [d.arg]: Math.max(0, cur[d.arg] + Number(d.step)) };
      schedulePreview(ctx);
      ctx.render();
    },
    threshold(ctx, d) {
      const ui = ctx.ui();
      ui.threshold = Math.max(1, Math.min(100, draft(ctx.app.data, ui).threshold + Number(d.step)));
      schedulePreview(ctx);
      ctx.render();
    },
    discard(ctx) { ctx.app.ui.quality = {}; ctx.render(); },
    async save(ctx) {
      const { weights, threshold } = draft(ctx.app.data, ctx.ui());
      const ok = await ctx.save(() => ctx.api.put('scoring', { weights, threshold }), 'Scoring saved. Every lead has been rescored.');
      if (ok) { ctx.app.ui.quality = {}; ctx.render(); }
    },
  },
};

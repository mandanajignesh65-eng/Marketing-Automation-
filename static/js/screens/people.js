import { html } from '../html.js';
import { pageHead, info, avatar } from '../ui.js';

const COLS = 'minmax(0,1.3fr) minmax(0,1.4fr) 150px minmax(0,1.2fr) 90px';
const TIPS = {
  role: 'A leader sees everything, sets targets, adds people and changes settings. A team member sees the dashboards and fills in their own targets, and cannot change anything else.',
  targets: 'People with targets show up on the Targets page. A leader who only wants to look does not need them.',
  password: 'You choose the first password and tell the person. After they sign in they can change it by clicking their name at the bottom left.',
};
const initials = name => name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
const ROLE = { admin: 'Leader', member: 'Team member' };

export default {
  uses: {},
  load: ctx => ctx.api.get('people'),

  render(d) {
    const logins = d.people.filter(p => p.account_id).length;
    return html`
    ${pageHead('Who can sign in, and who has targets', 'People', html`<div class="btn primary" data-act="add">Add person</div>`)}
    <div class="card clipped" style="--cols:${COLS}">
      <div class="thead"><span>Name</span><span>Email</span><span class="row" style="gap:7px">Can do${info(TIPS.role)}</span><span class="row" style="gap:7px">Targets${info(TIPS.targets)}</span><span></span></div>
      ${d.people.map((p, i) => html`<div class="trow ${i ? '' : 'first'}" data-act="edit" data-arg="${i}" title="Change ${p.name}">
        <span class="row" style="gap:10px;min-width:0">${avatar(initials(p.name), 28)}<span class="medium clip">${p.name}</span>${p.you ? html`<span class="pill sm">You</span>` : ''}</span>
        <span class="muted clip">${p.email || '—'}</span>
        <span>${p.role ? ROLE[p.role] : html`<span class="small" style="color:var(--warn)">No login yet</span>`}</span>
        <span class="stack" style="min-width:0">${p.member_id ? html`<span>${p.targets} target${p.targets === 1 ? '' : 's'}</span><span class="tiny muted clip">${p.focus || ''}</span>` : html`<span class="faint">None</span>`}</span>
        <span class="right small muted">Change</span>
      </div>`)}
    </div>
    <div class="small muted">${logins} ${logins === 1 ? 'person' : 'people'} can sign in. Each person signs in with their email and their own password.</div>`;
  },

  modal(m) {
    const p = m.person || { role: 'member' };
    const fresh = !m.person;
    return html`<form class="modal" data-submit="savePerson" autocomplete="off">
      <span class="section">${fresh ? 'Add a person' : 'Change ' + p.name}</span>
      <div class="grid" style="grid-template-columns:1fr 1fr">
        <label class="field">Name<input class="input" name="name" value="${p.name || ''}" required ${fresh ? 'data-autofocus' : ''}></label>
        <label class="field">Work email<input class="input" name="email" type="email" value="${p.email || ''}" placeholder="name@company.com" required></label>
      </div>
      <label class="field"><span class="row" style="gap:7px">What can they do${info(TIPS.role)}</span><select class="input" name="role">
        <option value="member" ${p.role !== 'admin' ? 'selected' : ''}>Team member (fills in their own targets)</option>
        <option value="admin" ${p.role === 'admin' ? 'selected' : ''}>Leader (sets targets, adds people, changes settings)</option></select></label>
      <label class="field"><span class="row" style="gap:7px">${p.account_id ? 'New password (leave empty to keep the current one)' : 'Password for signing in'}${info(TIPS.password)}</span>
        <div class="row" style="gap:8px"><input class="input" id="person-pw" name="password" type="text" minlength="10" placeholder="At least 10 characters" autocomplete="off" style="flex:1">
          <button type="button" class="btn" data-act="suggest">Suggest one</button></div>
        <span class="tiny muted">Copy the password before you save. It is not shown again.</span></label>
      ${p.member_id ? html`<label class="field">What they look after<input class="input" name="focus" value="${p.focus || ''}" placeholder="e.g. SEO and LinkedIn posts"></label>`
        : html`<label class="row small" style="gap:9px;cursor:pointer"><input type="checkbox" name="targets" ${fresh ? 'checked' : ''}><span class="row" style="gap:7px">Give this person targets${info(TIPS.targets)}</span></label>`}
      <div class="between" style="margin-top:4px">${fresh || p.you ? html`<span></span>` : html`<button type="button" class="btn danger" data-act="remove">Remove</button>`}
        <div class="row" style="gap:8px"><button type="button" class="btn" data-act="cancelModal">Cancel</button><button class="btn primary" type="submit">Save</button></div></div>
    </form>`;
  },

  actions: {
    add: ctx => ctx.openModal({ person: null }),
    edit: (ctx, d) => ctx.openModal({ person: ctx.app.data.people[Number(d.arg)] }),
    // a random password made in this browser; it is shown so it can be passed on to the person
    suggest() {
      const letters = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
      const pick = crypto.getRandomValues(new Uint32Array(14));
      document.getElementById('person-pw').value = [...pick].map(n => letters[n % letters.length]).join('');
    },
    async remove(ctx) {
      const p = ctx.app.modal.person;
      if (!window.confirm(`Remove ${p.name}? They will not be able to sign in, and their targets will be hidden.`)) return;
      ctx.app.modal = null;
      await ctx.save(() => ctx.api.post('people/remove', { account_id: p.account_id, member_id: p.member_id }), `${p.name} was removed.`);
    },
  },

  submits: {
    async savePerson(ctx, v) {
      const p = ctx.app.modal.person || {};
      const done = await ctx.save(() => ctx.api.post('people', { account_id: p.account_id || null, member_id: p.member_id || null, name: v.name, email: v.email,
        role: v.role, password: v.password, focus: v.focus == null ? p.focus : v.focus, targets: v.targets === 'on' }),
        p.account_id || !v.password ? 'Saved.' : `${v.name} can now sign in. Tell them the password.`);
      if (done) ctx.closeModal();
    },
  },
};

// The assistant: a slim tab on the right edge of the screen that slides out a panel for asking about the data.
// It keeps its own corner of the page, so a conversation stays open while the screens behind it change.
const IDEAS = ['How many leads came in this month?', 'Which channel has the best win rate?', 'What did competitors post on LinkedIn this week?'];
const SPARK = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.500l1.700 4.800 4.800 1.700-4.800 1.700L12 16.500l-1.700-4.800-4.800-1.700 4.800-1.700L12 3.500z"/><path d="M18.500 15.500l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2z"/></svg>';
const state = { open: false, ready: false, busy: false, turns: [] };
const esc = text => String(text).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
let root, panel;

function draw() {
  const empty = !state.turns.length;
  panel.innerHTML = `
    <div class="ask-head"><span class="ask-title">${SPARK}Ask Meridian</span>${empty ? '' : '<span class="ask-x" data-ask="clear">Clear</span>'}<span class="ask-x" data-ask="toggle" aria-label="Close">✕</span></div>
    <div class="ask-list" id="ask-list">
      ${!state.ready ? '<div class="ask-note">The assistant is not set up yet.</div>'
        : empty ? `<div class="ask-note">Ask anything about leads, deals, channels, the website or competitors.</div>${IDEAS.map(q => `<div class="ask-idea" data-ask="idea">${esc(q)}</div>`).join('')}` : ''}
      ${state.turns.map(t => `<div class="ask-msg ${t.role}${t.error ? ' error' : ''}">${esc(t.text)}</div>`).join('')}
      ${state.busy ? '<div class="ask-msg assistant muted">Looking at the data…</div>' : ''}
    </div>
    <form class="ask-form"><input class="input" id="ask-input" placeholder="Type a question" autocomplete="off" maxlength="600" ${state.ready ? '' : 'disabled'}>
      <button class="btn primary" type="submit" ${state.busy || !state.ready ? 'disabled' : ''}>Ask</button></form>`;
  const list = document.getElementById('ask-list');
  list.scrollTop = list.scrollHeight;
  if (state.open && !state.busy) document.getElementById('ask-input').focus();
}

function toggle(open) {
  state.open = open;
  root.classList.toggle('open', open);
  if (open) setTimeout(() => { const input = document.getElementById('ask-input'); if (input) input.focus(); }, 220);
}

async function ask(question) {
  question = question.trim();
  if (!question || state.busy) return;
  const history = state.turns.filter(t => !t.error).slice(-8).map(t => ({ role: t.role, text: t.text }));
  state.turns.push({ role: 'user', text: question });
  state.busy = true;
  draw();
  try {
    const res = await fetch('/api/assistant', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, history }) });
    const data = await res.json().catch(() => ({}));
    state.turns.push(res.ok ? { role: 'assistant', text: data.answer } : { role: 'assistant', text: typeof data.detail === 'string' ? data.detail : 'That did not work. Try again.', error: true });
  } catch (err) {
    state.turns.push({ role: 'assistant', text: 'The assistant could not be reached. Try again.', error: true });
  }
  state.busy = false;
  draw();
}

export async function mountAssistant() {
  try {
    const res = await fetch('/api/assistant');
    const info = res.ok ? await res.json() : {};
    if (!info.show) return;
    state.ready = !!info.ready;
  } catch (err) { return; }
  root = document.getElementById('assistant-root');
  root.innerHTML = `<button class="ask-tab" data-ask="toggle" title="Ask Meridian" aria-label="Ask Meridian">${SPARK}<span>Ask</span></button><aside class="ask-panel" aria-label="Ask Meridian"></aside>`;
  panel = root.querySelector('.ask-panel');
  root.addEventListener('click', event => {
    const el = event.target.closest('[data-ask]');
    if (!el) return;
    if (el.dataset.ask === 'toggle') toggle(!state.open);
    if (el.dataset.ask === 'clear') { state.turns = []; draw(); }
    if (el.dataset.ask === 'idea') ask(el.textContent);
  });
  root.addEventListener('submit', event => { event.preventDefault(); ask(document.getElementById('ask-input').value); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && state.open) toggle(false); });
  draw();
}

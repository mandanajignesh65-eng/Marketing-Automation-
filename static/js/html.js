// Tagged template for building markup. Interpolated values are HTML-escaped unless they are
// themselves the result of html`` (or raw()), so data from the API can never inject markup.

class Safe {
  constructor(s) { this.s = s; }
  toString() { return this.s; }
}

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = v => String(v).replace(/[&<>"']/g, c => ESC[c]);
export const raw = s => new Safe(String(s));

function out(v) {
  if (v == null || v === false || v === true) return '';
  if (v instanceof Safe) return v.s;
  if (Array.isArray(v)) return v.map(out).join('');
  return esc(v);
}

export function html(strings, ...values) {
  let s = strings[0];
  values.forEach((v, i) => { s += out(v) + strings[i + 1]; });
  return new Safe(s);
}

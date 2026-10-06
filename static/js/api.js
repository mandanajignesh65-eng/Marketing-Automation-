async function request(method, path, params, body) {
  const qs = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => { if (v != null && v !== '' && v !== false) qs.set(k, v); });
  const url = '/api/' + path + (qs.toString() ? '?' + qs : '');
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && path !== 'login') { location.reload(); throw new Error('Please sign in.'); }  // the session ended: back to the sign-in page
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) { /* not JSON */ }
    throw new Error(typeof detail === 'string' ? detail : 'Request failed');
  }
  return res.json();
}

export const api = {
  get: (path, params) => request('GET', path, params),
  post: (path, body, params) => request('POST', path, params, body || {}),
  put: (path, body) => request('PUT', path, null, body),
  patch: (path, body) => request('PATCH', path, null, body),
  del: path => request('DELETE', path),
};

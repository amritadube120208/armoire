/* Same-origin API client. Access tokens live only in this closure; the browser
 * manages the HttpOnly refresh cookie. Never persist passwords or JWTs. */
function createArmoireAPI({ transport = globalThis.fetch.bind(globalThis), onExpired = () => {} } = {}) {
  let accessToken = null;
  let refreshFlight = null;
  let epoch = 0;
  const base = '/api/v1';

  async function send(path, options = {}, token = null) {
    const headers = new Headers(options.headers || {});
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);
    try {
      return await transport(base + path, { ...options, headers, credentials: 'same-origin', signal: controller.signal });
    } finally { clearTimeout(timer); }
  }
  async function read(response) {
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = body.error?.message || body.detail;
      const error = new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}). Please try again.`);
      error.status = response.status;
      throw error;
    }
    return body;
  }
  function clear() { accessToken = null; epoch++; }
  async function renew() {
    if (refreshFlight) return refreshFlight;
    const started = epoch;
    refreshFlight = (async () => {
      const data = await read(await send('/auth/refresh', { method: 'POST' }));
      if (started !== epoch) throw new Error('The account session changed. Please try again.');
      if (!data.access_token) throw new Error('The server did not return a session.');
      accessToken = data.access_token;
      return true;
    })();
    try { return await refreshFlight; }
    catch (error) {
      if (started === epoch && [401, 403].includes(error.status)) { clear(); onExpired(); }
      throw error;
    } finally { refreshFlight = null; }
  }
  async function request(path, options = {}) {
    const started = epoch;
    const usedToken = accessToken;
    let response = await send(path, options, usedToken);
    if (response.status === 401 && started === epoch) {
      if (!accessToken || accessToken === usedToken) await renew();
      response = await send(path, options, accessToken);
    }
    if (started !== epoch) throw new Error('The account session changed. Please try again.');
    if (response.status === 401) { clear(); onExpired(); }
    return read(response);
  }
  async function authenticate(mode, credentials) {
    if (!['login', 'signup'].includes(mode)) throw new Error('Unknown sign-in method.');
    // Finish any restoration before replacing its cookie/session.
    if (refreshFlight) await refreshFlight.catch(() => {});
    const data = await read(await send(`/auth/${mode}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(credentials),
    }));
    if (!data.access_token) throw new Error('The server did not return a session.');
    epoch++; accessToken = data.access_token;
  }
  async function logout() {
    if (refreshFlight) await refreshFlight.catch(() => {});
    await request('/auth/logout', { method: 'POST' });
    clear();
  }
  return { request, authenticate, renew, logout, get signedIn() { return Boolean(accessToken); } };
}
if (typeof module !== 'undefined') module.exports = { createArmoireAPI };

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createArmoireAPI } = require('../../app/static/api.js');
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const credentials = { email: 'test@example.com', password: 'test-password' };

test('login sends credentials once and protected requests use the returned bearer', async () => {
  const calls = [];
  const api = createArmoireAPI({ transport: async (path, opts) => {
    calls.push([path, opts]); return path.endsWith('/login') ? json({ access_token: 'access-one' }) : json({ id: 'user' });
  }});
  await api.authenticate('login', credentials); await api.request('/users/me');
  assert.deepEqual(JSON.parse(calls[0][1].body), credentials);
  assert.equal(calls[0][1].headers.has('Authorization'), false);
  assert.equal(calls[1][1].headers.get('Authorization'), 'Bearer access-one');
  assert.equal(calls[1][1].body, undefined);
  assert.ok(calls.every(([,opts]) => opts.credentials === 'same-origin'));
});
test('concurrent expired requests share one cookie refresh and each retry once', async () => {
  let refreshes = 0; let protectedCalls = 0;
  const api = createArmoireAPI({ transport: async (path, opts) => {
    if (path.endsWith('/login')) return json({ access_token: 'old' });
    if (path.endsWith('/refresh')) { refreshes++; assert.equal(opts.headers.has('Authorization'), false); await new Promise(r => setTimeout(r, 10)); return json({ access_token: 'new' }); }
    protectedCalls++; return opts.headers.get('Authorization') === 'Bearer old' ? json({},401) : json({ ok: true });
  }});
  await api.authenticate('login', credentials);
  assert.deepEqual(await Promise.all([api.request('/users/me'), api.request('/wardrobe/items')]), [{ok:true},{ok:true}]);
  assert.equal(refreshes, 1); assert.equal(protectedCalls, 4);
});
test('rejected refresh clears the session and does not retry the protected operation', async () => {
  let expired = 0; let operations = 0;
  const api = createArmoireAPI({ onExpired: () => expired++, transport: async path => {
    if (path.endsWith('/login')) return json({access_token:'old'});
    if (path.endsWith('/refresh')) return json({error:{message:'Session expired'}},401);
    operations++; return json({},401);
  }});
  await api.authenticate('login', credentials);
  await assert.rejects(api.request('/feedback', {method:'POST'}), /Session expired/);
  assert.equal(api.signedIn, false); assert.equal(expired,1); assert.equal(operations,1);
});
test('a second 401 cannot cause an infinite refresh loop', async () => {
  let refreshes = 0;
  const api = createArmoireAPI({ transport: async path => {
    if (path.endsWith('/refresh')) { refreshes++; return json({access_token:'unusable'}); }
    return json({detail:'Rejected'},401);
  }});
  await assert.rejects(api.request('/users/me'), /Rejected/); assert.equal(refreshes,1); assert.equal(api.signedIn,false);
});
test('authorization failures and validation errors do not trigger refresh', async () => {
  let calls = 0;
  const api = createArmoireAPI({ transport: async () => { calls++; return json({error:{message:'Not allowed'}},403); } });
  await assert.rejects(api.request('/wardrobe/items'), /Not allowed/); assert.equal(calls,1);
});
test('logout renews an expired access token, clears cookie server-side, then clears memory', async () => {
  let logouts = 0;
  const api = createArmoireAPI({ transport: async path => {
    if (path.endsWith('/login')) return json({access_token:'old'});
    if (path.endsWith('/refresh')) return json({access_token:'new'});
    logouts++; return logouts === 1 ? json({},401) : json({message:'Logged out'});
  }});
  await api.authenticate('login',credentials); await api.logout(); assert.equal(logouts,2); assert.equal(api.signedIn,false);
});
test('failed sign-in returns the backend error and leaves no authenticated session', async () => {
  const api = createArmoireAPI({ transport: async () => json({error:{message:'Invalid email or password.'}},401) });
  await assert.rejects(api.authenticate('login',credentials), /Invalid email or password/); assert.equal(api.signedIn,false);
});
test('transient refresh network failure preserves the token for an explicit retry', async () => {
  const api = createArmoireAPI({ transport: async path => {
    if (path.endsWith('/login')) return json({access_token:'old'});
    if (path.endsWith('/refresh')) throw new TypeError('Failed to fetch');
    return json({},401);
  }});
  await api.authenticate('login',credentials); await assert.rejects(api.request('/users/me'), /Failed to fetch/); assert.equal(api.signedIn,true);
});

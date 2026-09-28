'use strict';
const $ = id => document.getElementById(id);
const state = { user: null, occasion: 'casual', category: '', items: [], total: 0, coords: null, mode: 'login', wardrobeVersion: 0, looksVersion: 0, session: 0, uploading: false };
const api = createArmoireAPI({ onExpired: () => { if (state.user) { resetAccount(); toast('Please sign in to continue.'); } } });
// Remove the previous frontend's persisted demo token without reading it.
try { localStorage.removeItem('sw_token'); } catch { /* Storage may be disabled. */ }
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let toastTimer;
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').hidden = true; }, 5500); }
function errorMessage(error) { return error.name === 'AbortError' ? 'This is taking longer than expected. Please try again.' : error.message === 'Failed to fetch' ? 'Could not reach Armoire. Check your connection and try again.' : error.message; }
function empty(target, title, copy, action = '', handler = null) {
  const box = document.createElement('div'); box.className = 'empty-state';
  box.innerHTML = `<span class="empty-symbol" aria-hidden="true">✧</span><h3>${escapeHTML(title)}</h3><p>${escapeHTML(copy)}</p>`;
  if (action) { const button = document.createElement('button'); button.className = 'button button-outline'; button.textContent = action; button.onclick = handler; box.append(button); }
  $(target).replaceChildren(box);
}
function resetAccount() {
  state.session++; state.wardrobeVersion++; state.looksVersion++; state.user = null; state.items = []; state.total = 0; state.coords = null;
  $('accountButton').textContent = 'Sign in ↗'; $('logoutButton').hidden = true; $('pieceCount').textContent = 'Your collection awaits'; $('loadMore').hidden = true;
  if ($('detailDialog')?.open) $('detailDialog').close();
  $('detailContent').replaceChildren(); $('uploadReview').replaceChildren(); $('uploadReview').hidden = true; $('photoInput').value = '';
  $('uploadStatus').textContent = 'Your original photo stays yours. Enhancements are your choice.';
  $('weatherTemperature').textContent = 'A little forecast. A better outfit.'; $('weatherDescription').textContent = 'Set your location for weather-aware suggestions.'; $('weatherLayers').textContent = 'Your location is used only when you choose.';
  empty('looksGrid', 'A new perspective on your wardrobe.', 'Explore outfits made from your own clothes or try the demo wardrobe.', 'Explore demo looks ↗', () => loginDemo(true));
  empty('wardrobeGrid', 'Every great wardrobe starts with one piece.', 'Photograph a favourite or explore our curated sample collection.', 'Explore demo pieces ↗', () => loginDemo(true));
  renderTaste({});
}
async function loginDemo(notify = true) {
  if (state.user && state.user.email === 'demo@smartwardrobe.com') {
    if (notify) toast('You are exploring the Armoire demonstration wardrobe.');
    return true;
  }
  try {
    await api.authenticate('login', { email: 'demo@smartwardrobe.com', password: 'Password123!' });
    state.session++;
    $('passwordInput').value = '';
    if ($('authDialog')?.open) $('authDialog').close();
    await loadProfile();
    if (notify) toast('Welcome to the Armoire demonstration wardrobe.');
    await Promise.all([loadWardrobe(), loadLooks()]);
    return true;
  } catch (error) {
    if (notify) toast(`Demo access unavailable: ${errorMessage(error)}`);
    return false;
  }
}
function openAuth() { if (state.user) { $('wardrobe').scrollIntoView({ behavior: 'smooth' }); return; } $('authError').textContent = ''; if (!$('authDialog').open) $('authDialog').showModal(); }
function authMode() {
  const signup = state.mode === 'signup'; $('nameField').hidden = !signup;
  $('authTitle').innerHTML = signup ? 'Make it <em>yours.</em>' : 'Welcome <em>back.</em>';
  $('authDescription').textContent = signup ? 'A fresh chapter for the clothes you love.' : 'Your wardrobe is right where you left it.';
  $('authSubmit').textContent = signup ? 'Create my account ↗' : 'Sign in ↗'; $('authToggle').textContent = signup ? 'Already have an account? Sign in' : 'New here? Create an account';
  $('passwordInput').autocomplete = signup ? 'new-password' : 'current-password'; $('passwordInput').minLength = signup ? 8 : 1; $('authError').textContent = '';
}
async function loadProfile() {
  const session = state.session;
  const user = await api.request('/users/me');
  if (session !== state.session) return;
  state.user = user; $('accountButton').textContent = user.name || 'My wardrobe'; $('logoutButton').hidden = false; renderTaste(user.preference || {});
  if (user.location && Number.isFinite(user.location.lat) && Number.isFinite(user.location.lon)) state.coords = user.location;
}
function renderTaste(pref) {
  const colors = Object.entries(pref.color_affinity || {}).filter(([,v]) => typeof v === 'number' && v > 0).sort((a,b) => b[1]-a[1]).slice(0,5);
  $('tasteSummary').innerHTML = colors.length ? `<p>Your signature palette.</p><div class="taste-chips">${colors.map(([color]) => `<span>${escapeHTML(color)}</span>`).join('')}</div><small>Inspired by the looks you love.</small>` : '<span class="empty-symbol" aria-hidden="true">✧</span><p>Your style story is still unfolding.</p><small>Like a look to begin discovering your signature palette.</small>';
}
function imageNode(url, alt) {
  const box = document.createElement('div'); box.className = 'garment-image';
  const placeholder = () => { box.innerHTML = '<span class="garment-placeholder" aria-label="Photo unavailable">✧</span>'; };
  if (!url) { placeholder(); return box; }
  try {
    const parsed = new URL(url, location.origin); if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('Unsupported image');
    const img = document.createElement('img'); img.src = parsed.href; img.alt = alt; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.onerror = placeholder; box.append(img);
  } catch { placeholder(); }
  return box;
}
async function loadWardrobe(append = false) {
  if (!state.user) return;
  const version = ++state.wardrobeVersion; const offset = append ? state.items.length : 0;
  const query = new URLSearchParams({ limit: '20', offset: String(offset) }); if (state.category) query.set('category', state.category);
  $('loadMore').disabled = true;
  if (!append) empty('wardrobeGrid', 'Opening your wardrobe…', 'Gathering your favourite pieces.');
  try {
    const data = await api.request(`/wardrobe/items?${query}`); if (version !== state.wardrobeVersion) return;
    state.items = append ? [...state.items, ...data.items] : data.items; state.total = data.total;
    $('pieceCount').textContent = `${data.total} ${data.total === 1 ? 'piece' : 'pieces'}`;
    $('loadMore').hidden = state.items.length >= data.total; renderWardrobe();
  } catch (error) { if (version === state.wardrobeVersion) empty('wardrobeGrid', 'Your wardrobe will be right back.', errorMessage(error), 'Try again', () => loadWardrobe()); }
  finally { if (version === state.wardrobeVersion) $('loadMore').disabled = false; }
}
function renderWardrobe() {
  if (!state.items.length) { empty('wardrobeGrid', 'A little room for possibility.', state.category ? 'No pieces in this category yet.' : 'Photograph your first piece to start your collection.', 'Add a piece ↗', () => $('studio').scrollIntoView({ behavior: 'smooth' })); return; }
  $('wardrobeGrid').replaceChildren();
  state.items.forEach(item => {
    const card = document.createElement('article'); card.className = 'garment-card'; const color = item.attributes?.color_primary || ''; const name = item.subtype || item.category || 'New piece';
    const photo = item.image; card.append(imageNode(photo?.enhancement_applied ? photo.enhanced_url || photo.original_url : photo?.thumbnail_url || photo?.original_url, `${color} ${name}`));
    const details = document.createElement('div'); details.innerHTML = `<h3>${escapeHTML(name)}</h3><p>${escapeHTML(color)}${color ? ' · ' : ''}Worn ${Number(item.wear_count) || 0} times</p><div class="garment-status">${escapeHTML(item.status === 'ready' ? 'Ready to style' : item.status === 'needs_review' ? 'Needs your review' : 'Processing your photo')}</div>`;
    card.append(details); $('wardrobeGrid').append(card);
  });
}
async function loadLooks() {
  if (!state.user) return;
  const version = ++state.looksVersion;
  const query = new URLSearchParams({ occasion: state.occasion }); if (state.coords) { query.set('lat', state.coords.lat); query.set('lon', state.coords.lon); }
  empty('looksGrid', 'Finding your next favourite…', 'Considering your pieces, your plans, and the day ahead.');
  try {
    const data = await api.request(`/recommendations?${query}`); if (version !== state.looksVersion) return;
    renderWeather(data.weather, !state.coords); renderLooks(data.recommendations || []);
  } catch (error) { if (version === state.looksVersion) empty('looksGrid', 'A little pause in the inspiration.', errorMessage(error), 'Try again', loadLooks); }
}
function renderWeather(weather, defaultLocation = false) {
  if (!weather) return;
  $('weatherTemperature').textContent = Number.isFinite(weather.temperature) ? `${Math.round(weather.temperature)}°C` : 'Forecast unavailable';
  const source = weather.source === 'live' ? 'Live real-time forecast' : (weather.source === 'mock' ? 'Sample forecast' : 'Cached forecast');
  const locationLabel = defaultLocation ? 'Default location (New Delhi)' : 'Your location';
  $('weatherDescription').textContent = `${source} · ${weather.condition || 'Conditions unavailable'} · ${locationLabel}`;
  const band = weather.requirement_band || {};
  $('weatherLayers').textContent = band.required_layers?.length ? `Bring a little comfort: ${band.required_layers.join(', ')}.` : 'Keep it light. A breathable base is a good place to start.';
}
function renderLooks(looks) {
  if (!looks.length) { empty('looksGrid', 'Your next look starts here.', 'Add a few ready-to-wear pieces to discover combinations for this occasion.', 'Visit the studio ↗', () => $('studio').scrollIntoView({ behavior: 'smooth' })); return; }
  $('looksGrid').replaceChildren();
  looks.forEach((look, index) => {
    const card = document.createElement('article'); card.className = 'look-card';
    card.innerHTML = `<div class="look-card-header"><h3>The edit No. ${String(index+1).padStart(2,'0')}</h3><span class="match">${Math.round((Number(look.final_score)||0)*100)}% match</span></div>`;
    const photos = document.createElement('div'); photos.className = 'look-items';
    for (const item of look.items || []) photos.append(imageNode(item.thumbnail_url, `${item.color || ''} ${item.subtype || item.category || 'Clothing'}`));
    card.append(photos);
    const caption = document.createElement('p'); caption.textContent = (look.items || []).map(item => item.subtype || item.category).join(' + '); card.append(caption);
    const actions = document.createElement('div'); actions.className = 'look-card-actions';
    for (const [label, action] of [['Wear today ↗','wear'],['♡ Like','like'],['Why this look?','explain']]) {
      const button = document.createElement('button'); button.className = action === 'wear' ? 'button button-dark' : 'text-button'; button.textContent = label;
      button.onclick = async () => {
        if (action === 'explain') { explain(look); return; }
        button.disabled = true;
        try { await api.request('/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ outfit_id: look.outfit_id || look.id, action }) }); toast(action === 'wear' ? 'Your outfit is recorded for today.' : 'A little closer to your signature style.'); button.textContent = action === 'wear' ? 'Worn today ✓' : 'Liked ✓'; await Promise.all([loadProfile(), action === 'wear' ? loadWardrobe() : Promise.resolve()]); }
        catch (error) { toast(errorMessage(error)); button.disabled = false; }
      }; actions.append(button);
    }
    card.append(actions); $('looksGrid').append(card);
  });
}
function explain(look) {
  $('detailContent').replaceChildren();
  for (const key of ['weather','occasion','color','style','personalization','diversity']) {
    const pct = Math.max(0, Math.min(100, Math.round(Number(look.score_breakdown?.[key] ?? look.score_breakdown?.[`${key}_score`] ?? 0)*100)));
    const row = document.createElement('div'); row.className = 'score-row'; row.innerHTML = `<div><span>${key}</span><span>${pct}%</span></div><progress max="100" value="${pct}" aria-label="${key} score">${pct}%</progress>`; $('detailContent').append(row);
  }
  $('detailDialog').showModal();
}
async function upload(file) {
  if (!file || state.uploading) return;
  if (!state.user) {
    const ok = await loginDemo(false);
    if (!ok) { $('photoInput').value = ''; openAuth(); toast('Sign in, then choose your photo again.'); return; }
  }
  if (!['image/jpeg','image/png','image/webp'].includes(file.type)) { $('uploadStatus').textContent = 'Please choose a JPG, PNG or WEBP photo.'; return; }
  if (file.size > 15*1024*1024 || !file.size) { $('uploadStatus').textContent = 'Choose a photo between 1 byte and 15 MB.'; return; }
  const session = state.session; state.uploading = true; $('photoInput').disabled = true; $('uploadReview').hidden = true;
  $('uploadStatus').textContent = 'Analyzing and adding piece to wardrobe…';
  try {
    const form = new FormData(); form.append('file', file);
    let item = await api.request('/wardrobe/items', { method: 'POST', body: form }); if (session !== state.session) return;
    
    // Fast polling fallback if item is still in processing state
    for (let attempt=0; item.status === 'processing' && attempt<10; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 300)); if (session !== state.session) return;
      const status = await api.request(`/wardrobe/items/${encodeURIComponent(item.id)}/status`); if (session !== state.session) return;
      if (status.status !== 'processing') {
        item = await api.request(`/wardrobe/items/${encodeURIComponent(item.id)}`);
        break;
      }
    }
    if (session !== state.session) return;
    if (item.status === 'ready') {
      $('uploadStatus').textContent = 'Your piece is ready. Added to your wardrobe.';
      toast('Your piece is ready and in your wardrobe!');
    } else if (item.status === 'needs_review') {
      $('uploadStatus').textContent = 'Your photo needs a closer look. Review the available images below.';
      toast('Piece uploaded. Quality review suggested.');
    } else {
      $('uploadStatus').textContent = 'Your piece is processing in the background.';
    }
    renderUploadReview(item);
    await Promise.all([loadWardrobe(), loadLooks()]);
  } catch (error) { if (session === state.session) $('uploadStatus').textContent = errorMessage(error); }
  finally { state.uploading = false; $('photoInput').disabled = false; $('photoInput').value = ''; }
}
function renderUploadReview(item) {
  const review = $('uploadReview'); review.replaceChildren(); review.hidden = true;
  if (!item.image?.enhanced_url) return;
  review.hidden = false; const text = document.createElement('p'); text.textContent = 'Original and enhanced: choose the image that feels true to your piece.'; review.append(text);
  for (const [label, url, action] of [['Keep original', item.image.original_url, 'use_original'], ['Use enhanced', item.image.enhanced_url, 'use_enhanced']]) {
    const image = imageNode(url, label); review.append(image);
    const button = document.createElement('button'); button.className = 'button button-outline'; button.textContent = label;
    button.onclick = async () => { button.disabled = true; try { await api.request(`/images/${encodeURIComponent(item.id)}/enhance`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }); toast('Your image choice is saved.'); review.hidden = true; await loadWardrobe(); } catch (error) { toast(errorMessage(error)); button.disabled = false; } }; review.append(button);
  }
}
document.addEventListener('click', event => {
  if (event.target.closest('[data-start]')) {
    if (state.user) {
      $('looks').scrollIntoView({ behavior: 'smooth' });
    } else {
      openAuth();
    }
  }
  const close = event.target.closest('[data-close]');
  if (close) {
    const dialog = $(close.dataset.close);
    if (dialog && dialog.open) dialog.close();
  }
});
$('accountButton').onclick = () => {
  if (state.user) {
    $('wardrobe').scrollIntoView({ behavior: 'smooth' });
  } else {
    openAuth();
  }
};
if ($('demoButton')) $('demoButton').onclick = () => loginDemo(true);
if ($('quickDemoBtn')) $('quickDemoBtn').onclick = () => loginDemo(true);
$('authToggle').onclick = () => { state.mode = state.mode === 'login' ? 'signup' : 'login'; authMode(); };
$('authDialog').addEventListener('close', () => { $('passwordInput').value = ''; });
$('authForm').onsubmit = async event => {
  event.preventDefault(); if ($('authSubmit').disabled) return;
  $('authSubmit').disabled = true; $('authToggle').disabled = true; $('authError').textContent = '';
  try {
    const credentials = { email: $('emailInput').value.trim(), password: $('passwordInput').value };
    if (state.mode === 'signup') credentials.name = $('nameInput').value.trim() || null;
    await api.authenticate(state.mode, credentials); state.session++; $('passwordInput').value = ''; await loadProfile(); $('authDialog').close(); toast('Welcome to your wardrobe.'); await Promise.all([loadWardrobe(), loadLooks()]);
  } catch (error) { $('authError').textContent = errorMessage(error); }
  finally { $('authSubmit').disabled = false; $('authToggle').disabled = false; }
};
$('logoutButton').onclick = async () => { $('logoutButton').disabled = true; try { await api.logout(); resetAccount(); toast('You have signed out.'); } catch (error) { toast(`Could not complete sign-out. ${errorMessage(error)}`); } finally { $('logoutButton').disabled = false; } };
for (const [id, attribute, update] of [['occasions','occasion',loadLooks], ['categories','category',() => loadWardrobe()]]) {
  $(id).onclick = async event => {
    const button = event.target.closest(`button[data-${attribute}]`);
    if (!button) return;
    state[attribute] = button.dataset[attribute];
    for (const sibling of $(id).querySelectorAll('button')) {
      sibling.classList.toggle('selected', sibling === button);
      sibling.setAttribute('aria-pressed', String(sibling === button));
    }
    if (!state.user) {
      await loginDemo(false);
    } else {
      update();
    }
  };
}
$('refreshLooks').onclick = async () => {
  if (!state.user) {
    await loginDemo(false);
  } else {
    loadLooks();
  }
};
$('loadMore').onclick = () => loadWardrobe(true);
$('locationButton').onclick = async () => {
  if (!state.user) {
    const ok = await loginDemo(false);
    if (!ok) { openAuth(); return; }
  }
  if (!navigator.geolocation) {
    toast('Location is not available in this browser.');
    return;
  }
  const session = state.session;
  $('locationButton').disabled = true;
  $('weatherDescription').textContent = 'Acquiring real-time location…';
  navigator.geolocation.getCurrentPosition(
    position => {
      $('locationButton').disabled = false;
      if (session !== state.session) return;
      state.coords = {
        lat: Number(position.coords.latitude.toFixed(4)),
        lon: Number(position.coords.longitude.toFixed(4))
      };
      toast('Live location acquired. Refreshing forecast…');
      loadLooks();
    },
    () => {
      $('locationButton').disabled = false;
      toast('Location permission not granted. Using default forecast.');
      loadLooks();
    },
    { timeout: 10000, maximumAge: 60000 }
  );
};
$('photoInput').onchange = event => upload(event.target.files[0]);
for (const type of ['dragover','dragleave','drop']) $('dropZone').addEventListener(type, event => {
  event.preventDefault();
  $('dropZone').classList.toggle('dragging', type === 'dragover');
  if (type === 'drop') upload(event.dataTransfer.files[0]);
});
$('brandFilm').addEventListener('play', () => { $('brandFilm').parentElement.classList.add('playing'); });
$('watchButton').onclick = async () => {
  const film = $('brandFilm');
  film.scrollIntoView({ behavior: 'smooth', block: 'center' });
  try {
    await film.play();
  } catch (error) {
    try {
      film.muted = true;
      await film.play();
      toast('Playing brand film (muted). Unmute anytime via player controls.');
    } catch {
      toast('Use the video controls to play the story.');
    }
  }
};
resetAccount();
(async () => {
  if (navigator.geolocation && !state.coords) {
    navigator.geolocation.getCurrentPosition(
      position => {
        state.coords = {
          lat: Number(position.coords.latitude.toFixed(4)),
          lon: Number(position.coords.longitude.toFixed(4))
        };
        if (state.user) loadLooks();
      },
      () => {},
      { timeout: 6000, maximumAge: 300000 }
    );
  }
  try {
    await api.renew();
    await loadProfile();
    await Promise.all([loadWardrobe(), loadLooks()]);
  } catch (error) {
    await loginDemo(false);
  }
})();

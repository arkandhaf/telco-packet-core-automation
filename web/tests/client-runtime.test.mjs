import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { Window } from 'happy-dom';

// Execute the actual shipped bundle in an isolated DOM, without contacting devices
// or writing the real audit store. This verifies runtime behavior, not visual layout.
const html = await readFile(new URL('../dist/index.html', import.meta.url), 'utf8');
const source = await readFile(new URL('../dist/assets/relpool-app.js', import.meta.url), 'utf8');
const settle = (ms = 50) => new Promise(resolve => setTimeout(resolve, ms));

function hierarchy(payload = {}) {
  const app = (payload.app_name || 'TikTok').toLowerCase().replace(/\s+/g, '_');
  return { hosts: [`h_${app}_1`], filters: [`f_${app}_1`], domains: ['*.example.com'], filter_group: `fg_gaspol_${app}`, category_group: 'catg_11010_11001000', rule_name: `r_${app}_11010_11001000`, apn_profile: `crbn_${payload.apn_name || 'internet_im3'}_sy`, product_type: 'New Product' };
}

async function launch(t, { preference = 'on', storedPreference = null, reduced = false, offline = false, removeForm = false, legacyMedia = false } = {}) {
  const errors = [];
  const window = new Window({ url: 'http://localhost:8000', settings: { disableJavaScriptFileLoading: true, disableJavaScriptEvaluation: true, disableCSSFileLoading: true } });
  t.after(async () => { await window.happyDOM.close(); });
  window.document.write(html);
  if (storedPreference !== null) window.localStorage.setItem('relpool.motion', storedPreference);
  const media = new window.EventTarget();
  Object.assign(media, { matches: reduced, media: '(prefers-reduced-motion: reduce)' });
  window.matchMedia = () => legacyMedia ? { matches: reduced, addListener() {} } : media;
  window.addEventListener('error', event => errors.push(event.error?.stack || event.message));
  const requests = [];
  window.fetch = async (url, options = {}) => {
    requests.push({ url: String(url), options });
    if (offline) return { ok: false, status: 503, json: async () => ({ detail: 'API offline in test' }) };
    const payload = options.body ? JSON.parse(options.body) : {};
    let body;
    if (String(url).includes('system-info')) body = { live_enabled: false, gateway_status: 'SIMULATION', nodes: [{ name: 'TEST_NODE', ip: '127.0.0.1', status: 'ONLINE' }], engine: { version: 'test' }, statistics: { total_wo: 3, wo_today: 2, generated_count: 3, executed_count: 0 } };
    else if (String(url).includes('/api/audit')) body = { entries: [], total: 0, filtered_total: 0, storage: { active_bytes: 2, active_count: 0, archive_count: 0, archives: [] } };
    else if (String(url).includes('/api/ssh/execute')) body = { status: 'SIMULATED', command_count: 1, logs: ['[SIMULATION #01] Would send: sys'] };
    else if (String(url).includes('/api/generate')) body = { payload, mml_script: '// TEST SCRIPT\nsys', rollback_script: '// ROLLBACK DRAFT', hierarchy_preview: hierarchy(payload), audit_entry: { 'WO ID': 'WO-TEST' } };
    else body = { hierarchy_preview: hierarchy(payload) };
    return { ok: true, json: async () => body };
  };
  if (removeForm) window.document.getElementById('provision-form').remove();
  window.eval(source);
  window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
  if (preference !== 'on') {
    const selector = window.document.getElementById('motion-preference');
    selector.value = preference;
    selector.dispatchEvent(new window.Event('change'));
  }
  await settle(100);
  assert.deepEqual(errors, []);
  return { window, document: window.document, requests };
}

test('shipped page loads a deferred classic bundle with no external import dependency', () => {
  assert.match(html, /<script[^>]*defer[^>]*src="\/assets\/relpool-app\.js"/);
  assert.doesNotMatch(source, /^\s*import\s/m);
  assert.match(source, /GSAP/);
});

test('the shipped HTML downloads and starts its script without manual evaluation', async t => {
  const paths = [];
  const server = createServer((request, response) => {
    paths.push(request.url);
    if (request.url === '/assets/relpool-app.js') {
      response.writeHead(200, { 'Content-Type': 'text/javascript; charset=utf-8', 'Cache-Control': 'no-store' });
      response.end(source);
    } else { response.writeHead(404); response.end(); }
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const { port } = server.address();
  const window = new Window({ url: `http://127.0.0.1:${port}/`, settings: { enableJavaScriptEvaluation: true, disableCSSFileLoading: true } });
  t.after(async () => { await window.happyDOM.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); });
  // An unavailable backend must not stop script loading or motion startup.
  window.fetch = async () => ({ ok: false, status: 503, json: async () => ({ detail: 'API unavailable in loader test' }) });
  window.document.write(html);
  const deadline = Date.now() + 3000;
  while (window.document.documentElement.dataset.frontendReady !== 'true' && Date.now() < deadline) await settle(20);
  assert.ok(paths.includes('/assets/relpool-app.js'), 'HTML parser must request the actual application asset');
  assert.equal(window.document.documentElement.dataset.motionReady, 'true');
  assert.equal(window.document.documentElement.dataset.frontendReady, 'true', window.document.getElementById('frontend-error-detail').textContent);
  const packet = window.document.querySelector('.packet-orb');
  const before = Number(packet.getAttribute('cx'));
  await settle(100);
  assert.ok(Number(packet.getAttribute('cx')) > before);
});

test('GSAP initializes and the SVG packets actually advance', async t => {
  const { document } = await launch(t);
  assert.equal(document.documentElement.dataset.motionReady, 'true');
  assert.equal(document.documentElement.dataset.frontendReady, 'true');
  assert.match(document.getElementById('motion-status').textContent, /GSAP .* ON/);
  const packet = document.querySelector('.packet-orb');
  const initial = Number(packet.getAttribute('cx'));
  await settle(130);
  assert.ok(Number(packet.getAttribute('cx')) > initial, 'SVG packet position must change over time');
  assert.ok(Number(document.querySelector('.data-packet').getAttribute('stroke-dashoffset')) < 0);
});

test('a fresh visit animates automatically without a Motion On action', async t => {
  const { document } = await launch(t, { reduced: true });
  assert.equal(document.getElementById('motion-preference').value, 'on');
  assert.equal(document.documentElement.dataset.motion, 'on');
  const before = Number(document.querySelector('.packet-orb').getAttribute('cx'));
  await settle(90);
  assert.ok(Number(document.querySelector('.packet-orb').getAttribute('cx')) > before);
});

test('old saved Auto and Off values cannot disable animation on a new visit', async t => {
  for (const storedPreference of ['auto', 'off']) {
    const { document } = await launch(t, { storedPreference, reduced: true });
    assert.equal(document.getElementById('motion-preference').value, 'on');
    assert.match(document.getElementById('motion-status').textContent, /ON/);
    assert.ok(Number(document.querySelector('.packet-orb').getAttribute('cx')) > 100);
  }
});

test('Motion Off stops movement and On restarts it', async t => {
  const { window, document } = await launch(t);
  const selector = document.getElementById('motion-preference');
  selector.value = 'off'; selector.dispatchEvent(new window.Event('change'));
  const position = document.querySelector('.packet-orb').getAttribute('cx');
  await settle(90);
  assert.equal(document.querySelector('.packet-orb').getAttribute('cx'), position);
  assert.match(document.getElementById('motion-status').textContent, /OFF/);
  assert.equal(document.getElementById('replay-motion').disabled, true);
  selector.value = 'on'; selector.dispatchEvent(new window.Event('change'));
  await settle(100);
  assert.ok(Number(document.querySelector('.packet-orb').getAttribute('cx')) > 100);
  assert.equal(document.documentElement.dataset.motion, 'on');
  assert.equal(window.localStorage.getItem('relpool.motion'), null);
});

test('motion resumes after repeated back/forward cache restores', async t => {
  const { window, document } = await launch(t);
  for (let attempt = 0; attempt < 2; attempt++) {
    window.dispatchEvent(new window.Event('pagehide'));
    const stopped = document.querySelector('.packet-orb').getAttribute('cx');
    await settle(70);
    assert.equal(document.querySelector('.packet-orb').getAttribute('cx'), stopped);
    const restored = new window.Event('pageshow');
    Object.defineProperty(restored, 'persisted', { value: true });
    window.dispatchEvent(restored);
    await settle(100);
    assert.ok(Number(document.querySelector('.packet-orb').getAttribute('cx')) > 100);
    assert.equal(document.querySelector('.bento-card').style.opacity, '');
  }
});

test('a legacy media-query API does not abort GSAP initialization', async t => {
  const { document } = await launch(t, { preference: 'auto', legacyMedia: true });
  assert.equal(document.documentElement.dataset.frontendReady, 'true');
  assert.equal(document.documentElement.dataset.motionReady, 'true');
  assert.ok(Number(document.querySelector('.packet-orb').getAttribute('cx')) > 100);
});

test('Auto honors reduced motion while On is an explicit application override', async t => {
  const { window, document } = await launch(t, { preference: 'auto', reduced: true });
  assert.match(document.getElementById('motion-status').textContent, /SYSTEM REDUCED/);
  assert.equal(document.querySelector('.packet-orb').getAttribute('cx'), '100');
  assert.equal(document.querySelector('.bento-card').style.opacity, '');
  const selector = document.getElementById('motion-preference');
  selector.value = 'on'; selector.dispatchEvent(new window.Event('change'));
  await settle(90);
  assert.ok(Number(document.querySelector('.packet-orb').getAttribute('cx')) > 100);
});

test('an offline API reports an error without stopping GSAP', async t => {
  const { document } = await launch(t, { offline: true });
  assert.equal(document.documentElement.dataset.frontendReady, 'true');
  assert.match(document.getElementById('motion-status').textContent, /ON/);
  assert.equal(document.getElementById('error-banner').hidden, false);
  const before = Number(document.querySelector('.packet-orb').getAttribute('cx'));
  await settle(90);
  assert.ok(Number(document.querySelector('.packet-orb').getAttribute('cx')) > before);
});

test('a provisioning startup failure is visible and does not prevent motion startup', async t => {
  const { document } = await launch(t, { removeForm: true });
  assert.equal(document.documentElement.dataset.motionReady, 'true');
  assert.notEqual(document.documentElement.dataset.frontendReady, 'true');
  assert.equal(document.getElementById('frontend-error').hidden, false);
  assert.match(document.getElementById('frontend-error-detail').textContent, /provision-form/);
});

test('presets, compilation and SSH simulation remain wired after motion refactoring', async t => {
  const { window, document, requests } = await launch(t, { preference: 'off' });
  document.querySelector('[data-preset="gojek"]').click();
  assert.equal(document.getElementById('app_name').value, 'Gojek Driver');
  assert.equal(document.getElementById('rg_val').value, '20000');
  await settle(230);
  assert.match(document.querySelector('[data-hierarchy="hosts"]').textContent, /h_gojek_driver/);
  document.getElementById('provision-form').dispatchEvent(new window.Event('submit', { cancelable: true }));
  await settle(70);
  assert.equal(document.getElementById('output-content').hidden, false);
  assert.match(document.getElementById('mml-code').textContent, /sys/);
  assert.ok(requests.some(request => request.url === '/api/generate'));
  document.querySelector('[data-output="ssh"]').click();
  document.getElementById('execute-button').click();
  await settle(70);
  assert.match(document.getElementById('ssh-logs').textContent, /SIMULATION/);
  assert.ok(requests.some(request => request.url === '/api/ssh/execute'));
  document.getElementById('app_name').value = 'Changed';
  document.getElementById('app_name').dispatchEvent(new window.Event('input', { bubbles: true }));
  assert.equal(document.getElementById('output-content').hidden, true);
});

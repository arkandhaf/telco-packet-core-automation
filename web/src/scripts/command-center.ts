import { gsap } from 'gsap';
import type { MotionController } from './motion';

type Payload = Record<string, string>;
type AuditEntry = Record<string, unknown> & { Payload?: unknown };
interface Hierarchy { hosts: string[]; filters: string[]; domains: string[]; filter_group: string; category_group: string; rule_name: string; apn_profile: string; product_type: string }
interface Generated { mml_script: string; rollback_script: string; payload: Payload; hierarchy_preview: Hierarchy; audit_entry: AuditEntry }
interface BatchRow { index: number; row_id: string; apn_name: string; app_name: string; mml_script: string; rollback_script: string; mml_filename: string; rollback_filename: string; payload: Payload }
interface BatchResult { raw_preview: Record<string, unknown>[]; mapping_report: Record<string, string>; batch_results: BatchRow[]; combined_txt: string; zip_base64: string }
interface SystemInfo { nodes: { name: string; ip: string; status: string; region: string }[]; statistics: Record<string, number>; engine: { version: string }; live_enabled: boolean; gateway_status: string }
interface AuditArchive { filename: string; event_count: number; bytes: number; created_at: string }
interface AuditStorage { active_bytes: number; active_count: number; revision: string; archive_count: number; archived_bytes: number; archives: AuditArchive[] }
interface AuditPage { entries: AuditEntry[]; total: number; filtered_total: number; offset: number; limit: number; storage: AuditStorage }

export function initializeCommandCenter(motion: MotionController) {
const duration = motion.duration;
const motionEnabled = motion.enabled;
const $ = <T extends HTMLElement = HTMLElement>(id: string): T => {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing interface element: ${id}`);
  return element as T;
};
const all = <T extends HTMLElement = HTMLElement>(selector: string) => Array.from(document.querySelectorAll<T>(selector));
const form = $<HTMLFormElement>('provision-form');
let generated: Generated | null = null;
let generatedPayload: Payload | null = null;
let batch: BatchResult | null = null;
let history: AuditEntry[] = [];
let auditOffset = 0;
let auditLimit = 25;
let auditTotal = 0;
let auditFilteredTotal = 0;
let auditStorage: AuditStorage | null = null;
let auditController: AbortController | undefined;
let auditTimer: ReturnType<typeof setTimeout>;
let archiveRevision = '';
let archiving = false;
let filter = 'All';
let batchTab = 'mml';
let liveMode = false;
let liveEnabled = false;
let executing = false;
let compiling = false;
let previewTimer: ReturnType<typeof setTimeout>;
let previewController: AbortController | undefined;
let revision = 0;
let batchRevision = 0;
const counters = new Map<string, { value: number }>();
let toastTimer: ReturnType<typeof setTimeout>;

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...options, headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers } });
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (Array.isArray(body.detail)) message = body.detail.map((error: { loc: string[]; msg: string }) => `${error.loc.slice(1).join('.') || 'Payload'}: ${error.msg}`).join(' · ');
      else if (typeof body.detail === 'string') message = body.detail;
    } catch { /* Preserve the HTTP status for malformed or proxy responses. */ }
    throw new Error(message);
  }
  return response.json();
}

function showError(error: unknown) {
  $('error-message').textContent = error instanceof Error ? error.message : 'The operation could not be completed.';
  $('error-banner').hidden = false;
}
function toast(message: string) {
  clearTimeout(toastTimer);
  const element = $('toast');
  element.textContent = message;
  element.hidden = false;
  gsap.fromTo(element, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: duration(.22) });
  toastTimer = setTimeout(() => { element.hidden = true; }, 3700);
}
$('dismiss-error').addEventListener('click', () => { $('error-banner').hidden = true; });

function getPayload(): Payload {
  const payload = Object.fromEntries(new FormData(form).entries()) as Payload;
  payload.header_enrichment = $<HTMLInputElement>('header_enrichment').checked ? 'Yes' : 'No';
  if (payload.header_enrichment === 'No') { payload.he_key = ''; payload.he_cipher = ''; }
  return payload;
}

function animateCounter(name: string, target: number) {
  all(`[data-counter="${name}"]`).forEach(element => {
    const count = counters.get(name) || { value: Number(element.dataset.value || 0) };
    counters.set(name, count);
    if (count.value === target) return;
    gsap.killTweensOf(count);
    element.dataset.value = String(target);
    gsap.to(count, { value: target, duration: duration(.85), ease: 'power2.out', onUpdate: () => { element.textContent = Math.round(count.value).toLocaleString(); } });
  });
}

function updateHierarchy(value: Hierarchy) {
  all('[data-hierarchy]').forEach(element => {
    const key = element.dataset.hierarchy as keyof Hierarchy;
    const names = value[key];
    element.textContent = Array.isArray(names) ? names.join('\n') : names;
    element.title = element.textContent;
  });
  $('domain-count').textContent = `${value.domains.length} domain${value.domains.length === 1 ? '' : 's'}`;
  $('domain-badges').replaceChildren(...value.domains.map(domain => {
    const badge = document.createElement('span'); badge.textContent = domain; return badge;
  }));
  $('preview-state').textContent = '● PREVIEW SYNCED';
  $('preview-state').className = 'pill cyan small';
  $('pipeline-scope').textContent = value.product_type === 'Revamp' ? 'Revamp cuts over to v2 and retains the v1 rule.' : value.product_type === 'Reguler Update' ? 'Delta patch updates detection objects; rollback needs a snapshot.' : 'Object names validated by the Huawei compiler.';
  motion.pulseNodes();
}

async function preview() {
  previewController?.abort();
  const controller = new AbortController();
  previewController = controller;
  const current = revision;
  $('preview-state').textContent = '● SYNCING PREVIEW';
  try {
    const result = await api<{ hierarchy_preview: Hierarchy }>('/api/preview', { method: 'POST', body: JSON.stringify(getPayload()), signal: controller.signal });
    if (current === revision) updateHierarchy(result.hierarchy_preview);
  } catch (error) {
    if (controller.signal.aborted || current !== revision) return;
    $('preview-state').textContent = 'CHECK INPUTS';
    $('preview-state').className = 'pill yellow small';
    $('domain-badges').replaceChildren();
    $('domain-count').textContent = 'Unvalidated domains';
    $('pipeline-scope').textContent = error instanceof Error ? error.message : 'Preview unavailable.';
    all('[data-hierarchy]').forEach(element => { element.textContent = '—'; });
  }
}

function invalidate() {
  revision++;
  generated = null;
  generatedPayload = null;
  $('output-content').hidden = true;
  $('output-empty').hidden = false;
  $('output-status').textContent = 'AWAITING COMPILATION';
  $('output-status').className = 'pill small neutral';
  $('output-wo').textContent = 'LOCAL ENGINE';
  $('command-count').textContent = '0 COMMANDS';
  all('[data-preset]').forEach(button => button.classList.remove('active'));
  clearTimeout(previewTimer);
  previewController?.abort();
  previewTimer = setTimeout(preview, 180);
}

form.addEventListener('input', invalidate);
$<HTMLInputElement>('header_enrichment').addEventListener('change', () => {
  const enabled = $<HTMLInputElement>('header_enrichment').checked;
  $('he-fields').hidden = !enabled;
  ['he_key', 'he_cipher'].forEach(id => { $<HTMLInputElement>(id).required = enabled; });
});

const common: Payload = { product_type: 'New Product', user_profile: 'New', apn_name: 'internet_im3', charging_type: 'Zero Rating', rg_val: '11010', sid_val: '11001000', capping_option: 'No Capping', header_enrichment: 'No', he_key: '', he_cipher: '', speed_limit: 'Full Speed', qci_val: '9 (Default Internet)', app_category: 'Well Known Apps', app_name: 'TikTok', app_domain: '*.tiktok.com, *.v2.tiktokcdn.com' };
const presets: Record<string, Payload> = {
  tiktok: { ...common, capping_option: '20 MB/day' },
  gojek: { ...common, user_profile: 'Existing', apn_name: 'b2b_corporate', charging_type: 'Special Rate (differentiate RG)', rg_val: '20000', sid_val: '20001000', app_category: 'Local Apps', app_name: 'Gojek Driver', app_domain: '*.gojek.com, *.driver.gojek.co.id' },
  gaming: { ...common, rg_val: '30000', sid_val: '30001000', qci_val: '1 (Voice/Low Latency)', app_category: 'Gaming', app_name: 'Mobile Legends', app_domain: '*.mobilelegends.com, *.moonton.com' },
};
all<HTMLButtonElement>('[data-preset]').forEach(button => button.addEventListener('click', () => {
  const preset = presets[button.dataset.preset!];
  Object.entries(preset).forEach(([name, value]) => {
    const input = $<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(name);
    if (input instanceof HTMLInputElement && input.type === 'checkbox') input.checked = value === 'Yes';
    else input.value = value;
  });
  $('he-fields').hidden = true;
  ['he_key', 'he_cipher'].forEach(id => { $<HTMLInputElement>(id).required = false; });
  invalidate();
  button.classList.add('active');
  toast(`${button.dataset.preset === 'gaming' ? 'Gaming low latency' : button.dataset.preset === 'gojek' ? 'Gojek special rate' : 'TikTok zero rating'} preset loaded`);
}));

function wireTabs(selector: string) {
  all<HTMLButtonElement>(selector).forEach(button => button.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const buttons = all<HTMLButtonElement>(selector);
    const index = buttons.indexOf(button);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].focus(); buttons[next].click();
  }));
}
all<HTMLButtonElement>('[data-view]').forEach(button => button.addEventListener('click', () => {
  const manual = button.dataset.view === 'manual';
  $('manual-view').hidden = !manual; $('batch-view').hidden = manual;
  all('[data-view]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-selected', String(active)); item.tabIndex = active ? 0 : -1; });
  gsap.fromTo(manual ? '#manual-view' : '#batch-view', { opacity: .4, y: 6 }, { opacity: 1, y: 0, duration: duration(.3) });
}));
wireTabs('[data-view]');
wireTabs('[data-output]');
wireTabs('[data-batch-tab]');
all('[role="tab"][aria-selected="false"]').forEach(element => { element.tabIndex = -1; });

function selectOutput(tab: string) {
  all('[data-output]').forEach(button => { const active = button.dataset.output === tab; button.classList.toggle('active', active); button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1; });
  all('[data-panel]').forEach(panel => { panel.hidden = panel.dataset.panel !== tab; });
}
all('[data-output]').forEach(button => button.addEventListener('click', () => selectOutput(button.dataset.output!)));

function renderCode(target: HTMLElement, code: string) {
  target.replaceChildren(...code.split('\n').map((line, index) => {
    const row = document.createElement('span'); row.className = 'code-line';
    const number = document.createElement('span'); number.className = 'line-number'; number.textContent = String(index + 1); number.setAttribute('aria-hidden', 'true');
    const content = document.createElement('span'); content.className = line.trim().startsWith('//') ? 'code-comment' : 'code-command';
    content.textContent = line || ' ';
    row.append(number, content); return row;
  }));
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (compiling || !form.reportValidity()) return;
  compiling = true;
  updateExecutionMode();
  const payload = getPayload();
  const currentRevision = revision;
  const button = $<HTMLButtonElement>('generate-button');
  button.disabled = true;
  $('error-banner').hidden = true;
  $('compiler').hidden = false;
  gsap.set('.step-track i', { scaleX: 0 });
  const sequence = gsap.timeline();
  all('.step-track i').forEach(track => sequence.to(track, { scaleX: 1, duration: duration(.3), ease: 'power1.inOut' }));
  const completedSequence = new Promise<void>(resolve => { sequence.eventCallback('onComplete', () => resolve()); if (!motionEnabled()) resolve(); });
  try {
    const result = await api<Generated>('/api/generate', { method: 'POST', body: JSON.stringify(payload) });
    await completedSequence;
    if (revision !== currentRevision) { toast('Script was saved to audit. Inputs changed; generate again for the current form.'); await refreshData(); return; }
    generated = result; generatedPayload = payload;
    updateHierarchy(result.hierarchy_preview);
    renderCode($('mml-code'), result.mml_script);
    renderCode($('rollback-code'), result.rollback_script);
    $('summary-code').textContent = JSON.stringify(result.payload, null, 2);
    $('output-empty').hidden = true; $('output-content').hidden = false;
    $('output-status').textContent = 'SCRIPT GENERATED'; $('output-status').className = 'pill small lime';
    $('output-wo').textContent = String(result.audit_entry['WO ID']);
    $('command-count').textContent = `${result.mml_script.split('\n').filter(line => line.trim() && !line.trim().startsWith('//')).length} COMMANDS`;
    $('ssh-logs').textContent = 'Ready for simulation. No commands have been sent.';
    selectOutput('mml');
    gsap.fromTo('#output-content', { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: duration(.35), clearProps: 'opacity,transform' });
    toast('Provisioning script and rollback draft generated.');
    await refreshData();
  } catch (error) { showError(error); }
  finally { compiling = false; button.disabled = executing; $('compiler').hidden = true; sequence.kill(); updateExecutionMode(); }
});

function download(content: BlobPart, filename: string, type = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = filename;
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function outputText(kind: string): string {
  if (!generated) throw new Error('Generate a script first.');
  return kind === 'rollback' ? generated.rollback_script : kind === 'summary' ? JSON.stringify(generated.payload, null, 2) : generated.mml_script;
}
all('[data-copy]').forEach(button => button.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(outputText(button.dataset.copy!)); toast('Copied to clipboard.'); }
  catch (error) { showError(error); }
}));
all('[data-download]').forEach(button => button.addEventListener('click', () => {
  try { const kind = button.dataset.download!; download(outputText(kind), `${kind === 'rollback' ? 'ROLLBACK' : 'MML'}_${generated!.payload.apn_name}_${generated!.payload.app_name}.txt`); }
  catch (error) { showError(error); }
}));

function updateExecutionMode() {
  all('[data-mode]').forEach(button => { const active = button.dataset.mode === (liveMode ? 'live' : 'simulation'); button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); });
  const blocked = liveMode && !liveEnabled;
  $<HTMLButtonElement>('execute-button').disabled = blocked || executing || compiling;
  $<HTMLInputElement>('execute-slider').disabled = blocked || executing || compiling;
  $<HTMLSelectElement>('ssh-host').disabled = executing;
  all<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('#provision-form input, #provision-form select, #provision-form textarea').forEach(input => { input.disabled = executing; });
  all<HTMLButtonElement>('[data-preset]').forEach(button => { button.disabled = executing; });
  $<HTMLButtonElement>('generate-button').disabled = executing || compiling;
  $<HTMLButtonElement>('manage-history').disabled = executing || compiling;
  $('execute-button').querySelector('span')!.textContent = executing ? 'Executing…' : liveMode ? 'Push config to testbed' : 'Run simulation';
  $('swipe-caption').textContent = blocked ? 'Live execution is disabled on this server' : liveMode ? 'Swipe right to push config to testbed' : 'Swipe right to simulate configuration';
  $('ssh-mode-note').textContent = blocked ? 'Live execution is disabled. Configure RELPOOL_ENABLE_LIVE=true, explicit SSH credentials and trusted host keys on the server to enable the existing gateway.' : liveMode ? 'This sends the generated configuration to the selected node. Review the script and rollback draft first. Received prompts do not verify configuration or service health.' : 'Simulation lists commands without opening an SSH connection. Device syntax and impact are not validated.';
}
all('[data-mode]').forEach(button => button.addEventListener('click', () => {
  if (executing) return;
  liveMode = button.dataset.mode === 'live';
  $<HTMLInputElement>('execute-slider').value = '0';
  updateExecutionMode();
}));

async function execute() {
  if (executing || compiling || (liveMode && !liveEnabled)) return;
  if (!generated || !generatedPayload) { showError(new Error('Generate the current CIQ before executing.')); return; }
  executing = true; updateExecutionMode();
  const script = generated.mml_script;
  const payload = { ...generatedPayload };
  $('ssh-logs').textContent = liveMode ? 'Connecting through the configured SSH gateway…' : 'Running the core SSH simulator…';
  try {
    const response = await api<{ logs: string[]; command_count: number; status: string }>('/api/ssh/execute', { method: 'POST', body: JSON.stringify({ mml_script: script, is_live: liveMode, apn_name: payload.apn_name, app_name: payload.app_name, payload, host: $<HTMLSelectElement>('ssh-host').value || null }) });
    $('ssh-logs').textContent = response.logs.join('\n');
    if (['FAILED', 'PARTIAL_FAILED', 'UNKNOWN'].includes(response.status)) showError(new Error(`Execution ended with status ${response.status}. Inspect the terminal log before retrying.`));
    else toast(`${response.status} · ${response.command_count} commands`);
    await refreshData();
  } catch (error) {
    $('ssh-logs').textContent += '\nRequest did not complete. Check audit history and device state before retrying live execution.';
    showError(error);
  } finally { executing = false; updateExecutionMode(); $<HTMLInputElement>('execute-slider').value = '0'; }
}
$('execute-button').addEventListener('click', execute);
$<HTMLInputElement>('execute-slider').addEventListener('change', event => {
  const slider = event.target as HTMLInputElement;
  if (Number(slider.value) >= 96) void execute();
  slider.value = '0';
});

async function processFile(file: File) {
  const current = ++batchRevision;
  batch = null; $('batch-results').hidden = true;
  $('error-banner').hidden = true;
  if (!/\.(csv|xlsx|xls)$/i.test(file.name)) { showError(new Error('Choose a CSV, XLSX or XLS file.')); return; }
  if (file.size > 10 * 1024 * 1024) { showError(new Error('Upload limit is 10 MB.')); return; }
  $('upload-state').textContent = `PROCESSING ${file.name}…`;
  const data = new FormData(); data.append('file', file);
  try {
    const result = await api<BatchResult>('/api/batch/process', { method: 'POST', body: data });
    if (current !== batchRevision) return;
    batch = result;
    $('batch-results').hidden = false;
    $('upload-state').textContent = `${file.name} · ${result.batch_results.length} ROWS COMPILED`;
    animateCounter('batch_scripts', result.batch_results.length);
    animateCounter('batch_apns', new Set(result.batch_results.map(row => row.apn_name)).size);
    animateCounter('batch_apps', new Set(result.batch_results.map(row => row.app_name)).size);
    renderPreviewTable(result.raw_preview);
    $('mapping-report').replaceChildren(...Object.entries(result.mapping_report).map(([name, mapping]) => {
      const container = document.createElement('div'); const label = document.createElement('strong'); label.textContent = name;
      container.append(label, document.createTextNode(mapping)); return container;
    }));
    $<HTMLSelectElement>('batch-row').replaceChildren(...result.batch_results.map((row, index) => {
      const option = document.createElement('option'); option.value = String(index); option.textContent = `${String(row.index).padStart(3, '0')} · ${row.apn_name} / ${row.app_name}`; return option;
    }));
    selectBatchTab('mml');
    gsap.fromTo('#batch-results', { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: duration(.4) });
    toast(`${result.batch_results.length} CIQ rows compiled and audited.`);
    await refreshData();
  } catch (error) {
    if (current !== batchRevision) return;
    $('upload-state').textContent = 'UPLOAD FAILED · CORRECT YOUR FILE AND TRY AGAIN';
    showError(error);
  } finally { $<HTMLInputElement>('batch-file').value = ''; }
}
$<HTMLInputElement>('batch-file').addEventListener('change', event => {
  const file = (event.target as HTMLInputElement).files?.[0]; if (file) void processFile(file);
});
const dropZone = $('drop-zone');
['dragenter', 'dragover'].forEach(name => dropZone.addEventListener(name, event => { event.preventDefault(); dropZone.classList.add('dragover'); }));
['dragleave', 'drop'].forEach(name => dropZone.addEventListener(name, event => { event.preventDefault(); dropZone.classList.remove('dragover'); }));
dropZone.addEventListener('drop', event => { const file = event.dataTransfer?.files[0]; if (file) void processFile(file); });

function renderPreviewTable(rows: Record<string, unknown>[]) {
  const table = $('preview-table'); table.replaceChildren();
  if (!rows.length) return;
  const keys = Object.keys(rows[0]);
  const head = document.createElement('thead'); const headRow = document.createElement('tr');
  keys.forEach(key => { const cell = document.createElement('th'); cell.textContent = key; headRow.append(cell); });
  head.append(headRow); const body = document.createElement('tbody');
  rows.forEach(row => { const tr = document.createElement('tr'); keys.forEach(key => { const td = document.createElement('td'); td.textContent = String(row[key] ?? ''); tr.append(td); }); body.append(tr); });
  table.append(head, body);
}
function selectedBatchRow() { return batch?.batch_results[Number($<HTMLSelectElement>('batch-row').value)]; }
function selectBatchTab(tab: string) {
  batchTab = tab;
  all('[data-batch-tab]').forEach(button => { const active = button.dataset.batchTab === tab; button.classList.toggle('active', active); button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1; });
  const row = selectedBatchRow(); if (!row) return;
  if (tab === 'payload') $('batch-code').textContent = JSON.stringify(row.payload, null, 2);
  else renderCode($('batch-code'), tab === 'rollback' ? row.rollback_script : row.mml_script);
  $('download-row').lastChild!.textContent = `Download ${tab === 'payload' ? 'payload .json' : tab === 'rollback' ? 'rollback .txt' : 'MML .txt'}`;
}
all('[data-batch-tab]').forEach(button => button.addEventListener('click', () => selectBatchTab(button.dataset.batchTab!)));
$('batch-row').addEventListener('change', () => selectBatchTab(batchTab));
$('download-combined').addEventListener('click', () => { if (batch) download(batch.combined_txt, 'ALL_MML_SCRIPTS.txt'); });
$('download-archive').addEventListener('click', () => {
  if (batch) { const bytes = Uint8Array.from(atob(batch.zip_base64), character => character.charCodeAt(0)); download(bytes, 'RELPOOL_CIQ_ARCHIVE.zip', 'application/zip'); }
});
$('download-row').addEventListener('click', () => {
  const row = selectedBatchRow(); if (!row) return;
  if (batchTab === 'payload') download(JSON.stringify(row.payload, null, 2), `${row.row_id}.json`, 'application/json');
  else download(batchTab === 'rollback' ? row.rollback_script : row.mml_script, batchTab === 'rollback' ? row.rollback_filename : row.mml_filename);
});

function auditQuery() {
  return new URLSearchParams({ action: filter, search: $<HTMLInputElement>('audit-search').value.trim().slice(0, 500), limit: String(auditLimit), offset: String(auditOffset) });
}
function formatBytes(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(2)} MB` : bytes >= 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} B`;
}
function acceptAuditPage(page: AuditPage) {
  history = page.entries; auditTotal = page.total; auditFilteredTotal = page.filtered_total; auditStorage = page.storage;
  renderAudit();
}
async function refreshAudit() {
  auditController?.abort();
  const controller = new AbortController(); auditController = controller;
  $<HTMLButtonElement>('audit-previous').disabled = true; $<HTMLButtonElement>('audit-next').disabled = true;
  try {
    const page = await api<AuditPage>(`/api/audit/page?${auditQuery()}`, { signal: controller.signal });
    if (controller.signal.aborted) return;
    if (auditOffset > 0 && auditOffset >= page.filtered_total) { auditOffset = Math.max(0, Math.floor((page.filtered_total - 1) / auditLimit) * auditLimit); await refreshAudit(); return; }
    acceptAuditPage(page);
  } catch (error) { if (!controller.signal.aborted) { renderAudit(); showError(error); } }
}
function statusClass(status: string) { return ['SUCCESS', 'SCRIPT_GENERATED', 'BATCH_SUCCESS'].includes(status) ? 'lime' : ['SIMULATED', 'PENDING', 'SENT_UNVERIFIED'].includes(status) ? 'yellow' : 'rose'; }
function formatTime(value: unknown) {
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value || '—') : date.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta' }) + ' WIB';
}
function renderAudit() {
  const rows = history;
  $('audit-total').textContent = `${auditTotal} active event${auditTotal === 1 ? '' : 's'}`;
  $('audit-showing').textContent = `${rows.length ? auditOffset + 1 : 0}–${auditOffset + rows.length} of ${auditFilteredTotal}`;
  $<HTMLButtonElement>('audit-previous').disabled = auditOffset === 0;
  $<HTMLButtonElement>('audit-next').disabled = auditOffset + auditLimit >= auditFilteredTotal;
  if (auditStorage) $('audit-storage').textContent = `Active: ${formatBytes(auditStorage.active_bytes)} · ${auditStorage.archive_count} compressed archive${auditStorage.archive_count === 1 ? '' : 's'}`;
  $('audit-empty').hidden = rows.length > 0;
  $('audit-empty').querySelector('p')!.textContent = auditTotal ? 'No events match your filters. Try another action or search.' : 'No active events. Generate a script to start the trail, or open Manage history to download saved archives.';
  $('audit-body').replaceChildren(...rows.map(row => {
    const tr = document.createElement('tr'); tr.className = 'audit-row';
    const wo = document.createElement('td'); const link = document.createElement('button'); link.className = 'wo-link'; link.textContent = String(row['WO ID'] || 'Unknown work order'); link.title = link.textContent; link.setAttribute('aria-label', `Inspect ${link.textContent}`);
    const time = document.createElement('span'); time.className = 'subline'; time.textContent = formatTime(row.Timestamp); wo.append(link, time);
    const action = document.createElement('td'); const actionLabel = document.createElement('span'); actionLabel.className = 'action-label'; actionLabel.textContent = String(row.Action || '—'); action.append(actionLabel);
    const target = document.createElement('td'); target.append(document.createTextNode(String(row.APN || '—'))); const application = document.createElement('span'); application.className = 'subline'; application.textContent = String(row['App Target'] || '—'); target.append(application);
    const node = document.createElement('td'); node.textContent = String(row['Target Node'] || 'LOCAL_ENGINE');
    const status = document.createElement('td'); const badge = document.createElement('span'); const value = String(row.Status || 'UNKNOWN'); badge.className = `pill small ${statusClass(value)}`; badge.textContent = value; status.append(badge);
    const inspect = document.createElement('td'); inspect.textContent = '↗'; inspect.className = 'inspect-arrow';
    tr.append(wo, action, target, node, status, inspect);
    tr.addEventListener('click', () => openPayload(row)); return tr;
  }));
}
all('[data-audit-filter]').forEach(button => button.addEventListener('click', () => {
  filter = button.dataset.auditFilter!;
  all('[data-audit-filter]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  auditOffset = 0; void refreshAudit();
}));
$('audit-search').addEventListener('input', () => { clearTimeout(auditTimer); auditController?.abort(); auditOffset = 0; auditTimer = setTimeout(refreshAudit, 200); });
$('audit-page-size').addEventListener('change', () => { auditLimit = Number($<HTMLSelectElement>('audit-page-size').value); auditOffset = 0; void refreshAudit(); });
$('audit-previous').addEventListener('click', () => { auditOffset = Math.max(0, auditOffset - auditLimit); void refreshAudit(); });
$('audit-next').addEventListener('click', () => { if (auditOffset + auditLimit < auditFilteredTotal) { auditOffset += auditLimit; void refreshAudit(); } });
$('export-audit').addEventListener('click', () => {
  const link = document.createElement('a'); const query = auditQuery(); query.delete('limit'); query.delete('offset');
  link.href = `/api/audit/export?${query}`; link.download = 'RELPOOL_AUDIT.csv'; document.body.append(link); link.click(); link.remove();
});

function renderHistoryManager() {
  if (!auditStorage) return;
  const storage = auditStorage;
  $('history-active-count').textContent = `${storage.active_count} events`;
  $('history-active-size').textContent = `${formatBytes(storage.active_bytes)} on disk`;
  $('history-archive-count').textContent = `${storage.archive_count} archives`;
  $('history-archive-size').textContent = `${formatBytes(storage.archived_bytes)} on disk`;
  $('archive-list').replaceChildren(...storage.archives.map(archive => {
    const item = document.createElement('div'); item.className = 'archive-item';
    const label = document.createElement('div'); const name = document.createElement('p'); name.textContent = `${archive.event_count} archived events`;
    const description = document.createElement('small'); description.textContent = `${formatTime(archive.created_at)} · ${formatBytes(archive.bytes)}`;
    label.append(name, description);
    const link = document.createElement('a'); link.href = `/api/audit/archives/${encodeURIComponent(archive.filename)}`; link.download = archive.filename; link.textContent = 'Download .json.gz'; link.className = 'btn-secondary';
    item.append(label, link); return item;
  }));
  if (!storage.archives.length) { const empty = document.createElement('p'); empty.textContent = 'No archives yet. Archiving preserves all active records in a compressed file on this server.'; $('archive-list').append(empty); }
  updateArchiveButton();
}
function updateArchiveButton() {
  $<HTMLButtonElement>('archive-history').disabled = archiving || !auditStorage?.active_count || !$<HTMLInputElement>('archive-confirmation').checked || executing || compiling;
}
$('manage-history').addEventListener('click', async () => {
  $('archive-result').textContent = '';
  $<HTMLInputElement>('archive-confirmation').checked = false;
  await refreshAudit();
  if (!auditStorage) return;
  archiveRevision = auditStorage.revision;
  renderHistoryManager();
  $<HTMLDialogElement>('history-dialog').showModal();
});
$('close-history').addEventListener('click', () => { if (!archiving) $<HTMLDialogElement>('history-dialog').close(); });
$('archive-confirmation').addEventListener('change', updateArchiveButton);
$<HTMLDialogElement>('history-dialog').addEventListener('cancel', event => { if (archiving) event.preventDefault(); });
$('archive-history').addEventListener('click', async () => {
  if (archiving || executing || compiling || !$<HTMLInputElement>('archive-confirmation').checked) return;
  archiving = true; updateArchiveButton(); $<HTMLButtonElement>('close-history').disabled = true;
  $('archive-result').textContent = 'Saving the compressed archive before resetting active history…';
  try {
    const result = await api<{ filename: string; archived_count: number }>('/api/audit/archive', { method: 'POST', body: JSON.stringify({ confirmation: 'ARCHIVE_AND_RESET', expected_revision: archiveRevision }) });
    auditOffset = 0;
    await refreshData();
    $('archive-result').textContent = `${result.archived_count} events preserved. Active history and counters have been reset. Download the archive below.`;
    $<HTMLInputElement>('archive-confirmation').checked = false;
    if (auditStorage) archiveRevision = auditStorage.revision;
    renderHistoryManager();
    toast('History archived safely. Active workspace reset.');
  } catch (error) {
    $('archive-result').textContent = error instanceof Error ? error.message : 'Archiving failed. Active history has not been intentionally cleared.';
    await refreshAudit();
    $<HTMLInputElement>('archive-confirmation').checked = false;
    if (auditStorage) archiveRevision = auditStorage.revision;
    renderHistoryManager();
  } finally { archiving = false; $<HTMLButtonElement>('close-history').disabled = false; updateArchiveButton(); }
});
function openPayload(row: AuditEntry) {
  $('payload-title').textContent = String(row.Action || 'Work order detail');
  $('payload-meta').textContent = `${row['WO ID']} · ${formatTime(row.Timestamp)}`;
  $('payload-code').textContent = JSON.stringify({ payload: row.Payload ?? {}, metadata: row.Metadata ?? {}, status: row.Status, target_node: row['Target Node'] }, null, 2);
  $<HTMLDialogElement>('payload-dialog').showModal();
  gsap.fromTo('#payload-dialog', { x: 25, opacity: 0 }, { x: 0, opacity: 1, duration: duration(.25), ease: 'power2.out' });
}
$('close-payload').addEventListener('click', () => $<HTMLDialogElement>('payload-dialog').close());
$<HTMLDialogElement>('payload-dialog').addEventListener('click', event => {
  const dialog = event.currentTarget as HTMLDialogElement;
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
});

async function refreshData() {
  const results = await Promise.allSettled([api<SystemInfo>('/api/system-info'), refreshAudit()]);
  if (results[0].status === 'fulfilled') {
    const system = results[0].value;
    liveEnabled = system.live_enabled;
    $('connection-state').textContent = '● API CONNECTED'; $('connection-state').className = 'pill lime';
    $('engine-ready').textContent = 'READY'; $('engine-version').textContent = system.engine.version;
    $('engine-label').textContent = 'Engine ready';
    $('gateway-status').textContent = system.gateway_status;
    const primary = system.nodes.find(node => node.status === 'ONLINE') || system.nodes[0];
    $('active-node').textContent = primary ? `● ${primary.name} · ${primary.ip}` : 'No nodes configured';
    Object.entries(system.statistics).forEach(([name, value]) => animateCounter(name, value));
    const selector = $<HTMLSelectElement>('ssh-host'); const previous = selector.value;
    selector.replaceChildren(...system.nodes.map(node => { const option = document.createElement('option'); option.value = node.ip; option.textContent = `${node.name} · ${node.ip} (${node.status})`; return option; }));
    if (system.nodes.some(node => node.ip === previous)) selector.value = previous;
    updateExecutionMode();
  } else {
    $('connection-state').textContent = '● API UNAVAILABLE'; $('connection-state').className = 'pill rose'; $('engine-ready').textContent = 'UNAVAILABLE';
    $('engine-label').textContent = 'Engine offline';
    showError(results[0].reason);
  }
  if (results[1].status === 'rejected') { $('audit-empty').querySelector('p')!.textContent = 'Audit storage is unavailable. Restore the connection to inspect deployment history.'; showError(results[1].reason); }
}

all('.bento-card').forEach(card => card.addEventListener('pointermove', event => {
  const bounds = card.getBoundingClientRect(); card.style.setProperty('--mouse-x', `${event.clientX - bounds.left}px`); card.style.setProperty('--mouse-y', `${event.clientY - bounds.top}px`);
}));
all('.bento-card').forEach(card => card.addEventListener('pointerleave', () => { card.style.removeProperty('--mouse-x'); card.style.removeProperty('--mouse-y'); }));
$('local-date').textContent = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Jakarta' }).toUpperCase();
void refreshData();
void preview();
setInterval(() => { if (!document.hidden && !executing && !compiling && !archiving && !$<HTMLDialogElement>('history-dialog').open) void refreshData(); }, 30_000);
}

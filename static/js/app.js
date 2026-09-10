// ---------- Общие утилиты ----------

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

let toastTimer = null;
function showToast(text, isError) {
  const t = document.getElementById('toast');
  t.textContent = text;
  t.classList.toggle('error', !!isError);
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3500);
}

// ---------- Навигация по вкладкам ----------

function closeMobileNav() {
  document.body.classList.remove('nav-open');
  const toggle = document.getElementById('nav-toggle');
  const scrim = document.getElementById('nav-scrim');
  if (toggle) toggle.setAttribute('aria-expanded', 'false');
  if (scrim) scrim.hidden = true;
}

function openMobileNav() {
  document.body.classList.add('nav-open');
  const toggle = document.getElementById('nav-toggle');
  const scrim = document.getElementById('nav-scrim');
  if (toggle) toggle.setAttribute('aria-expanded', 'true');
  if (scrim) scrim.hidden = false;
}

function setupMobileNav() {
  const toggle = document.getElementById('nav-toggle');
  const scrim = document.getElementById('nav-scrim');
  toggle?.addEventListener('click', () => {
    document.body.classList.contains('nav-open') ? closeMobileNav() : openMobileNav();
  });
  scrim?.addEventListener('click', closeMobileNav);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMobileNav();
  });
}

function activateTab(tab) {
  if (!tab) return;
  document.querySelectorAll('.nav-item[data-tab], .mobile-tab[data-tab]').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id === 'tab-' + tab));
  closeMobileNav();
  if (tab === 'hr' && typeof populateHrJobSelect === 'function') populateHrJobSelect();
}

document.querySelectorAll('.nav-item[data-tab], .mobile-tab[data-tab]').forEach(btn => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});
setupMobileNav();

// ---------- Под-вкладки внутри «Резюме»: список файлов / конструктор ----------

document.querySelectorAll('.subtab-item').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.subtab-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.subtab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('subtab-' + btn.dataset.subtab).classList.add('active');
    if (btn.dataset.subtab === 'builder' && typeof applyResumeZoom === 'function') {
      applyResumeZoom();
    }
    if (btn.dataset.subtab === 'templates' && typeof renderTplPreview === 'function') {
      const applyBtn = document.getElementById('btn-tpl-apply-current');
      if (applyBtn) applyBtn.style.display = currentResumeId ? 'inline-flex' : 'none';
      renderTplPreview();
    }
  });
});

function openResumeBuilder() {
  document.querySelector('.nav-item[data-tab="cvs"]').click();
  document.querySelector('.subtab-item[data-subtab="builder"]').click();
}

// ============================================================
// ПОИСК ВАКАНСИЙ
// ============================================================

let allJobs = [];

function updateChipStyle(chipId) {
  const chip = document.getElementById(chipId);
  const checked = chip.querySelector('input').checked;
  chip.classList.toggle('active', checked);
}
document.getElementById('chip-djinni').addEventListener('click', () => setTimeout(syncSearchFormUi));
document.getElementById('chip-workua').addEventListener('click', () => setTimeout(syncSearchFormUi));
document.getElementById('chip-rabotaua').addEventListener('click', () => setTimeout(syncSearchFormUi));
document.getElementById('chip-jooble').addEventListener('click', () => setTimeout(syncSearchFormUi));

const SOURCE_LABELS = { djinni: 'djinni.co', workua: 'work.ua', rabotaua: 'robota.ua', jooble: 'jooble.org' };

let accountPrefs = {
  keyword: '', query: '', region: '',
  sources: ['djinni', 'workua', 'rabotaua'],
  all_pages: true, pages: 1, delay: 3,
  employment_type: '', remote: '', reservation: false, salary_expectation: '',
};

function collectRemote(name) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value || '';
}

function applyRemote(name, value) {
  const v = (value === 'remote' || value === 'include') ? value : '';
  document.querySelectorAll(`input[name="${name}"]`).forEach(el => {
    el.checked = el.value === v;
    el.closest('.chip')?.classList.toggle('active', el.checked);
  });
}

function applyReservation(id, on) {
  const el = document.getElementById(id);
  if (!el) return;
  el.checked = !!on;
  el.closest('.chip')?.classList.toggle('active', !!on);
}

function wireChoiceChips(containerId) {
  const root = document.getElementById(containerId);
  if (!root) return;
  const sync = () => {
    root.querySelectorAll('.chip, [data-choice-chip]').forEach(chip => {
      const input = chip.querySelector('input');
      if (input) chip.classList.toggle('active', !!input.checked);
    });
  };
  root.addEventListener('click', () => setTimeout(sync));
  sync();
}

function payloadFromPrefs(prefs, excludeJooble) {
  const sources = (prefs.sources || []).filter(s => (excludeJooble ? s !== 'jooble' : true));
  return {
    sources,
    keyword: (prefs.keyword || '').trim(),
    query: (prefs.query || '').trim(),
    region: prefs.region || '',
    pages: prefs.pages || 1,
    delay: prefs.delay || 3,
    all_pages: prefs.all_pages !== false,
    remote: prefs.remote || '',
    reservation: !!prefs.reservation,
  };
}

function payloadFromSearchForm() {
  return {
    sources: selectedSources(),
    keyword: collectRegions('keyword-chips', 'f-keyword-extra'),
    query: document.getElementById('f-query').value.trim(),
    region: collectRegions('region-chips', 'f-region-extra'),
    pages: document.getElementById('f-pages').value,
    delay: document.getElementById('f-delay').value,
    all_pages: document.getElementById('f-all-pages').checked,
    remote: collectRemote('f-remote'),
    reservation: document.getElementById('f-reservation')?.checked || false,
  };
}

function payloadFromMarketForm() {
  return {
    sources: selectedMarketSources(),
    keyword: collectRegions('m-keyword-chips', 'm-keyword-extra'),
    query: document.getElementById('m-query').value.trim(),
    region: collectRegions('m-region-chips', 'm-region-extra'),
    pages: document.getElementById('m-pages').value,
    delay: document.getElementById('m-delay').value,
    all_pages: document.getElementById('m-all-pages').checked,
    remote: collectRemote('m-remote'),
  };
}

function renderPrefsSummary(rootId, prefs, excludeJooble) {
  const root = document.getElementById(rootId);
  if (!root) return;
  const p = payloadFromPrefs(prefs, excludeJooble);
  const sources = p.sources.map(s => SOURCE_LABELS[s] || s).join(' · ') || 'не выбраны';
  const q = [p.keyword, p.query].filter(Boolean).join(' · ') || 'не задан';
  const region = p.region || 'вся Украина';
  const volume = p.all_pages ? 'все страницы' : `${p.pages} стр.`;
  const remoteLabel = p.remote === 'remote' ? 'только удалёнка' : (p.remote === 'include' ? 'удалёнка + города' : 'не важно');
  const reservationRow = excludeJooble ? '' : `<div class="prefs-kv"><span>Бронювання</span><b>${escapeHtml(p.reservation ? 'только с бронюванням' : 'не важно')}</b></div>`;
  root.innerHTML = `
    <div class="prefs-kv"><span>Источники</span><b>${escapeHtml(sources)}</b></div>
    <div class="prefs-kv"><span>Запрос</span><b>${escapeHtml(q)}</b></div>
    <div class="prefs-kv"><span>Регионы</span><b>${escapeHtml(region)}</b></div>
    <div class="prefs-kv"><span>Удалёнка</span><b>${escapeHtml(remoteLabel)}</b></div>
    ${reservationRow}
    <div class="prefs-kv"><span>Объём</span><b>${escapeHtml(String(volume))} · пауза ${escapeHtml(String(p.delay))} с</b></div>
  `;
}

function refreshPrefsSummaries() {
  renderPrefsSummary('search-prefs-summary', accountPrefs, false);
  renderPrefsSummary('market-prefs-summary', accountPrefs, true);
}

function openAccount(section) {
  document.querySelector('.nav-item[data-tab="settings"]')?.click();
  const tab = document.querySelector(`.acct-subtab[data-acct="${section}"]`);
  tab?.click();
}

document.querySelectorAll('.acct-subtab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.acct-subtab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.acct-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.querySelector(`[data-acct-panel="${btn.dataset.acct}"]`)?.classList.add('active');
  });
});

function selectedSources() {
  return Array.from(document.querySelectorAll('#tab-search .sources input:checked')).map(i => i.value);
}

function syncAllPagesUi() {
  const allOn = document.getElementById('f-all-pages').checked;
  const pagesInput = document.getElementById('f-pages');
  const pagesField = document.getElementById('pages-field');
  pagesInput.disabled = allOn;
  pagesField.classList.toggle('is-disabled', allOn);
  document.getElementById('chip-all-pages').classList.toggle('active', allOn);
}

let platformStatus = { ai_ready: false, jooble_ready: false, boards_ready: {} };

function syncJoobleHint(hintId, joobleOn) {
  const hint = document.getElementById(hintId);
  if (!hint) return;
  hint.hidden = !joobleOn || !!platformStatus.jooble_ready;
}

function syncMarketBoardsHint() {
  const hint = document.getElementById('market-boards-hint');
  if (!hint) return;
  const ready = platformStatus.boards_ready || {};
  const missing = ['djinni', 'workua', 'rabotaua'].filter(k => !ready[k]);
  if (!missing.length) { hint.hidden = true; return; }
  const labels = { djinni: 'djinni.co', workua: 'work.ua', rabotaua: 'robota.ua' };
  hint.hidden = false;
  hint.textContent = 'Владелец ещё не задал вход в админке для: '
    + missing.map(k => labels[k]).join(', ')
    + '. Без сессии ленты резюме закрыты.';
}

function syncSearchFormUi() {
  ['chip-djinni', 'chip-workua', 'chip-rabotaua', 'chip-jooble'].forEach(updateChipStyle);
  const sources = selectedSources();
  syncJoobleHint('jooble-hint', sources.includes('jooble'));
  const delayInput = document.getElementById('f-delay');
  const delayHint = document.getElementById('delay-hint');
  if (sources.includes('workua')) {
    if (Number(delayInput.value) < 3) delayInput.value = 3;
    if (delayHint) delayHint.textContent = 'Для work.ua не меньше 3 сек — иначе сайт включает проверку.';
  } else if (delayHint) {
    delayHint.textContent = 'Пауза между страницами выдачи.';
  }
  syncAllPagesUi();
}

function collectRegions(chipContainerId, extraInputId) {
  const chips = Array.from(document.querySelectorAll(`#${chipContainerId} input:checked`)).map(i => i.value);
  const extra = (document.getElementById(extraInputId)?.value || '')
    .split(/[,;|/]+/).map(s => s.trim()).filter(Boolean);
  const seen = new Set();
  const out = [];
  for (const name of [...chips, ...extra]) {
    const key = name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(name);
  }
  return out.join(', ');
}

function applyRegions(chipContainerId, extraInputId, regionStr) {
  const parts = (regionStr || '').split(/[,;|/]+/).map(s => s.trim()).filter(Boolean);
  const boxes = document.querySelectorAll(`#${chipContainerId} input[type=checkbox]`);
  const known = new Map();
  boxes.forEach(cb => known.set(cb.value.toLowerCase(), cb));
  const extra = [];
  parts.forEach(name => {
    const cb = known.get(name.toLowerCase());
    if (cb) cb.checked = true;
    else extra.push(name);
  });
  boxes.forEach(cb => {
    if (!parts.some(p => p.toLowerCase() === cb.value.toLowerCase())) cb.checked = false;
  });
  const extraEl = document.getElementById(extraInputId);
  if (extraEl) extraEl.value = extra.join(', ');
  document.querySelectorAll(`#${chipContainerId} [data-region-chip]`).forEach(chip => {
    chip.classList.toggle('active', chip.querySelector('input').checked);
  });
}

function wireRegionChips(containerId) {
  const root = document.getElementById(containerId);
  if (!root) return;
  root.addEventListener('click', () => {
    setTimeout(() => {
      root.querySelectorAll('[data-region-chip]').forEach(chip => {
        chip.classList.toggle('active', chip.querySelector('input').checked);
      });
    });
  });
}

wireRegionChips('region-chips');
wireRegionChips('pref-region-chips');
wireRegionChips('m-region-chips');
wireRegionChips('keyword-chips');
wireRegionChips('pref-keyword-chips');
wireRegionChips('m-keyword-chips');
wireRegionChips('profile-headline-chips');
wireChoiceChips('f-remote-chips');
wireChoiceChips('pref-remote-chips');
wireChoiceChips('m-remote-chips');
document.getElementById('f-reservation-chip')?.addEventListener('click', () => {
  setTimeout(() => applyReservation('f-reservation', document.getElementById('f-reservation').checked));
});
document.getElementById('pref-reservation-chip')?.addEventListener('click', () => {
  setTimeout(() => applyReservation('pref-reservation', document.getElementById('pref-reservation').checked));
});

function renderGrid() {
  const filterText = document.getElementById('filter-text').value.trim().toLowerCase();
  const filterSource = document.getElementById('filter-source').value;
  const sortBy = document.getElementById('sort-by').value;

  let jobs = allJobs.filter(j => {
    if (filterSource && j.source !== filterSource) return false;
    if (filterText) {
      const hay = `${j.title} ${j.company} ${j.description}`.toLowerCase();
      if (!hay.includes(filterText)) return false;
    }
    return true;
  });

  if (sortBy === 'title') jobs = [...jobs].sort((a,b) => (a.title||'').localeCompare(b.title||''));
  if (sortBy === 'company') jobs = [...jobs].sort((a,b) => (a.company||'').localeCompare(b.company||''));

  const grid = document.getElementById('grid');
  const emptyMsg = document.getElementById('empty-msg');
  document.getElementById('count-badge').textContent = `${jobs.length} из ${allJobs.length}`;
  const breakdown = document.getElementById('source-breakdown');
  if (breakdown) {
    const counts = {};
    allJobs.forEach(j => { counts[j.source] = (counts[j.source] || 0) + 1; });
    breakdown.innerHTML = Object.keys(SOURCE_LABELS)
      .filter(src => counts[src] || (accountPrefs.sources || []).includes(src))
      .map(src => `<span class="src-count-chip"><span class="dot ${src}"></span>${escapeHtml(SOURCE_LABELS[src])} ${counts[src] || 0}</span>`)
      .join('');
  }

  if (jobs.length === 0) {
    grid.innerHTML = '';
    emptyMsg.style.display = 'block';
    return;
  }
  emptyMsg.style.display = 'none';

  grid.innerHTML = jobs.map((j, idx) => `
    <div class="card${j._fresh ? ' is-new' : ''}" data-idx="${idx}" style="--card-i:${Math.min(idx, 16)}">
      <div class="card-top">
        <span class="src-badge ${j.source}">${SOURCE_LABELS[j.source] || j.source}</span>
        ${j._fresh ? '<span class="badge-new">новая</span>' : ''}
      </div>
      <h3><button type="button" class="job-title-btn btn-open-detail" data-idx="${idx}">${escapeHtml(j.title)}</button></h3>
      ${j.company ? `<div class="company">${escapeHtml(j.company)}</div>` : ''}
      ${j.salary ? `<div class="salary">${escapeHtml(j.salary)}</div>` : ''}
      ${j.meta ? `<div class="meta">${escapeHtml(j.meta)}</div>` : ''}
      ${j.description ? `<div class="desc">${escapeHtml(j.description)}</div>` : ''}
      <div class="card-footer">
        <a class="jobs-link" href="${j.url}" target="_blank" rel="noopener">Открыть вакансию →</a>
        <div style="display:flex; gap:6px;">
          <button class="small-primary btn-cover-letter" data-idx="${idx}"><svg class="icn" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="4.5" width="15" height="11" rx="2"/><path d="M3 5.5l7 5.5 7-5.5"/></svg>Письмо</button>
          <button class="small-primary btn-match" data-idx="${idx}">Оценить с ИИ</button>
        </div>
      </div>
      <div class="match-box" id="match-${idx}"></div>
      <div class="match-box" id="cover-${idx}"></div>
    </div>
  `).join('');

  grid.querySelectorAll('.btn-match').forEach(btn => {
    btn.addEventListener('click', () => runMatch(jobs[+btn.dataset.idx], document.getElementById(`match-${btn.dataset.idx}`), btn));
  });
  grid.querySelectorAll('.btn-cover-letter').forEach(btn => {
    btn.addEventListener('click', () => runCoverLetter(jobs[+btn.dataset.idx], document.getElementById(`cover-${btn.dataset.idx}`), btn));
  });
  grid.querySelectorAll('.btn-open-detail').forEach(btn => {
    btn.addEventListener('click', () => openJobDetail(jobs[+btn.dataset.idx]));
  });
}

document.getElementById('filter-text').addEventListener('input', renderGrid);
document.getElementById('filter-source').addEventListener('change', renderGrid);
document.getElementById('sort-by').addEventListener('change', renderGrid);

function downloadBlob(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

document.getElementById('btn-export-json').addEventListener('click', () => {
  downloadBlob(JSON.stringify(allJobs, null, 2), 'jobs.json', 'application/json');
});
document.getElementById('btn-export-csv').addEventListener('click', () => {
  const fields = ['source','title','company','salary','meta','url','description'];
  const rows = [fields.join(',')];
  for (const j of allJobs) {
    rows.push(fields.map(f => '"' + String(j[f] || '').replace(/"/g, '""') + '"').join(','));
  }
  downloadBlob(rows.join('\n'), 'jobs.csv', 'text/csv');
});

const btnSearch = document.getElementById('btn-search');
const statusText = document.getElementById('status-text');
const logPanel = document.getElementById('log-panel');
const searchLivePill = document.getElementById('search-live-pill');

let searchWs = null;
let searchLive = false;

function jobIdentity(job) {
  return (job && job.url) ? job.url : `${job?.source || ''}|${job?.title || ''}|${job?.company || ''}`;
}

function setSearchLiveUi(on) {
  searchLive = !!on;
  btnSearch.classList.toggle('is-live', searchLive);
  btnSearch.textContent = searchLive ? 'Стоп' : 'Автопоиск';
  if (searchLivePill) searchLivePill.hidden = !searchLive;
}

function stopAutosearch(status) {
  if (searchWs) {
    try {
      if (searchWs.readyState === WebSocket.OPEN) {
        searchWs.send(JSON.stringify({ action: 'stop' }));
      }
      searchWs.close();
    } catch (_) { /* already closed */ }
    searchWs = null;
  }
  setSearchLiveUi(false);
  if (status) statusText.textContent = status;
}

function mergeIncomingJobs(incoming, { prepend, markNew }) {
  const have = new Set(allJobs.map(jobIdentity));
  const added = [];
  for (const job of incoming || []) {
    const key = jobIdentity(job);
    if (!key || have.has(key)) continue;
    have.add(key);
    const copy = { ...job, _fresh: !!(markNew || job._fresh) };
    added.push(copy);
  }
  if (!added.length) return added;
  allJobs = prepend ? [...added, ...allJobs] : [...allJobs, ...added];
  if (markNew) {
    setTimeout(() => {
      added.forEach(j => { j._fresh = false; });
      renderGrid();
    }, 45000);
  }
  return added;
}

document.getElementById('f-all-pages').addEventListener('change', syncAllPagesUi);

function runAutosearch(payload) {
  if (searchLive) return true;

  const sources = payload.sources;
  const keyword = payload.keyword;
  const query = payload.query;

  if (sources.length === 0) { statusText.textContent = 'Выберите хотя бы один источник в настройках аккаунта'; return false; }
  if (!keyword && !query) { statusText.textContent = 'Задайте категорию или запрос в настройках аккаунта'; return false; }

  statusText.textContent = 'Соединяюсь…';
  logPanel.textContent = '';
  document.getElementById('results-panel').style.display = 'block';

  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${wsProtocol}//${location.host}/ws/search`);
  searchWs = ws;
  setSearchLiveUi(true);

  ws.addEventListener('open', () => {
    statusText.textContent = payload.all_pages ? 'Автопоиск: первый проход по всем страницам…' : 'Автопоиск: первый проход…';
    ws.send(JSON.stringify({
      sources,
      keyword,
      query,
      region: payload.region,
      pages: payload.pages,
      delay: payload.delay,
      all_pages: payload.all_pages,
      remote: payload.remote,
      reservation: payload.reservation,
      watch: true,
      watch_interval: 60,
    }));
  });

  ws.addEventListener('message', (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'log') {
      logPanel.textContent += msg.text + '\n';
      logPanel.scrollTop = logPanel.scrollHeight;
    } else if (msg.type === 'jobs') {
      const markNew = !!msg.fresh;
      const added = mergeIncomingJobs(msg.jobs, { prepend: markNew, markNew });
      document.getElementById('results-panel').style.display = 'block';
      renderGrid();
      const total = msg.total != null ? msg.total : allJobs.length;
      if (markNew && added.length) {
        statusText.textContent = `Новых: ${added.length} · всего ${total}`;
        showToast(added.length === 1 ? 'Новая вакансия' : `${added.length} новых вакансий`);
      } else {
        statusText.textContent = `Найдено ${total} вакансий…`;
      }
    } else if (msg.type === 'watching') {
      const total = msg.total != null ? msg.total : allJobs.length;
      const wait = msg.interval || 60;
      statusText.textContent = `Автопоиск · ${total} вакансий · проверка каждые ${wait} с`;
      document.getElementById('results-panel').style.display = 'block';
      renderGrid();
    } else if (msg.type === 'stopped' || msg.type === 'done') {
      const total = msg.total != null ? msg.total : allJobs.length;
      stopAutosearch(msg.type === 'done' ? `Готово: ${total} вакансий` : `Автопоиск остановлен · ${total} вакансий`);
    } else if (msg.type === 'error') {
      logPanel.innerHTML += `<span class="err">Ошибка: ${escapeHtml(msg.text)}</span>\n`;
      stopAutosearch('Ошибка при поиске');
    }
  });

  ws.addEventListener('error', () => {
    if (!searchLive || searchWs !== ws) return;
    statusText.textContent = 'Ошибка соединения';
  });

  ws.addEventListener('close', (e) => {
    if (searchWs !== ws) return;
    searchWs = null;
    if (!searchLive) return;
    setSearchLiveUi(false);
    if (!e.wasClean) {
      logPanel.innerHTML += `<span class="err">Соединение прервано</span>\n`;
      statusText.textContent = `Соединение прервано · ${allJobs.length} вакансий`;
    } else if (!statusText.textContent.includes('остановлен') && !statusText.textContent.includes('Ошибка')) {
      statusText.textContent = `Автопоиск остановлен · ${allJobs.length} вакансий`;
    }
  });

  return true;
}

btnSearch.addEventListener('click', () => {
  if (searchLive) {
    stopAutosearch(`Автопоиск остановлен · ${allJobs.length} вакансий`);
    return;
  }
  const overrideOn = !document.getElementById('search-override')?.hidden;
  const payload = overrideOn ? payloadFromSearchForm() : payloadFromPrefs(accountPrefs);
  runAutosearch(payload);
});

// Мгновенный показ уже найденных ранее вакансий из постоянного хранилища — до того,
// как автопоиск вообще успеет подключиться и что-то сам найти по сети.
async function loadCachedJobs() {
  const payload = payloadFromPrefs(accountPrefs);
  if (!payload.sources.length || (!payload.keyword && !payload.query)) return;
  try {
    const resp = await fetch('/api/jobs/cached', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sources: payload.sources, keyword: payload.keyword, query: payload.query,
        region: payload.region, remote: payload.remote, reservation: payload.reservation,
      }),
    });
    if (!resp.ok) return;
    const data = await resp.json();
    const added = mergeIncomingJobs(data.jobs, { prepend: false, markNew: false });
    if (added.length) {
      document.getElementById('results-panel').style.display = 'block';
      renderGrid();
    }
  } catch (_) { /* нет кэша — не страшно, фон найдёт на следующей проверке */ }
}

// ============================================================
// РЫНОК КАНДИДАТОВ
// ============================================================

let marketCards = [];
let marketAnalysis = null;

['m-chip-djinni', 'm-chip-workua', 'm-chip-rabotaua'].forEach(id => {
  document.getElementById(id)?.addEventListener('click', () => setTimeout(() => updateChipStyle(id)));
});

function selectedMarketSources() {
  return Array.from(document.querySelectorAll('#m-sources input:checked')).map(i => i.value);
}

function syncMarketAllPages() {
  const allOn = document.getElementById('m-all-pages').checked;
  document.getElementById('m-pages').disabled = allOn;
  document.getElementById('m-pages-field').classList.toggle('is-disabled', allOn);
  document.getElementById('m-chip-all-pages').classList.toggle('active', allOn);
}
document.getElementById('m-all-pages')?.addEventListener('change', syncMarketAllPages);

function renderMarketGrid() {
  const filterText = (document.getElementById('m-filter-text').value || '').trim().toLowerCase();
  const filterSource = document.getElementById('m-filter-source').value;
  let cards = marketCards.filter(c => {
    if (filterSource && c.source !== filterSource) return false;
    if (filterText) {
      const hay = `${c.title} ${(c.skills || []).join(' ')} ${c.city} ${c.snippet}`.toLowerCase();
      if (!hay.includes(filterText)) return false;
    }
    return true;
  });
  document.getElementById('m-count-badge').textContent = `${cards.length} из ${marketCards.length}`;
  const grid = document.getElementById('market-grid');
  const emptyMsg = document.getElementById('market-empty');
  if (cards.length === 0) {
    grid.innerHTML = '';
    emptyMsg.style.display = 'block';
    return;
  }
  emptyMsg.style.display = 'none';
  grid.innerHTML = cards.map((c, idx) => `
    <div class="card" style="--card-i:${Math.min(idx, 16)}">
      <div class="card-top">
        <span class="src-badge ${c.source}">${SOURCE_LABELS[c.source] || c.source}</span>
      </div>
      <h3>${c.url ? `<a href="${c.url}" target="_blank" rel="noopener">${escapeHtml(c.title)}</a>` : escapeHtml(c.title)}</h3>
      ${c.salary ? `<div class="salary">${escapeHtml(c.salary)}</div>` : ''}
      ${c.meta ? `<div class="meta">${escapeHtml(c.meta)}</div>` : ''}
      ${c.snippet ? `<div class="desc">${escapeHtml(c.snippet)}</div>` : ''}
      ${(c.skills || []).length ? `<div class="skill-cloud">${c.skills.map(s => `<span class="skill-pill">${escapeHtml(s)}</span>`).join('')}</div>` : ''}
    </div>
  `).join('');
}

function fmtSalary(n) {
  if (n == null) return '—';
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function skillBar(items, extraClass = '') {
  const max = Math.max(1, ...items.map(s => s.count || 0));
  return items.map(s => {
    const pct = Math.max(8, Math.round((s.count / max) * 100));
    const label = escapeHtml(s.skill || s.title || s.label || '');
    return `<div class="bar-row ${extraClass}">
      <span class="bar-label">${label}</span>
      <div class="bar" aria-hidden="true"><i style="width:${pct}%"></i></div>
      <span class="bar-count">${s.count}</span>
    </div>`;
  }).join('');
}

function renderMarketExamples(examples) {
  const panel = document.getElementById('market-examples-panel');
  const root = document.getElementById('market-examples');
  const items = (examples || []).filter(e => (e.snippet || '').trim());
  if (!panel || !root) return;
  if (!items.length) { panel.style.display = 'none'; root.innerHTML = ''; return; }
  panel.style.display = 'block';
  root.innerHTML = items.map(e => {
    const bits = [e.city, e.experience_years != null ? `${e.experience_years} р.` : '', e.salary]
      .filter(Boolean).map(escapeHtml).join(' · ');
    const skills = (e.skills || []).slice(0, 6).map(s => `<span class="skill-pill">${escapeHtml(s)}</span>`).join('');
    const title = e.url
      ? `<a href="${e.url}" target="_blank" rel="noopener">${escapeHtml(e.title)}</a>`
      : escapeHtml(e.title);
    return `<article class="example-card">
      <div class="card-top">
        <span class="src-badge ${e.source}">${SOURCE_LABELS[e.source] || e.source}</span>
        ${bits ? `<div class="meta">${bits}</div>` : ''}
      </div>
      <h3>${title}</h3>
      <blockquote class="example-quote">${escapeHtml(e.snippet)}</blockquote>
      ${skills ? `<div class="skill-cloud">${skills}</div>` : ''}
    </article>`;
  }).join('');
}

function renderMarketAnalysis(a) {
  const panel = document.getElementById('market-analysis-panel');
  const root = document.getElementById('market-stats');
  if (!a) { panel.style.display = 'none'; renderMarketExamples([]); return; }
  panel.style.display = 'block';
  const srcBits = Object.entries(a.by_source || {}).map(([k, v]) => `${SOURCE_LABELS[k] || k}: ${v}`).join(' · ');
  const missing = (a.cv_missing || []).map(s => `<span class="skill-pill missing">${escapeHtml(s.skill)} ×${s.count}</span>`).join('');
  const present = (a.cv_present || []).map(s => `<span class="skill-pill present">${escapeHtml(s.skill)} ×${s.count}</span>`).join('');
  const salaryRange = a.salary_min != null
    ? `${fmtSalary(a.salary_min)} – ${fmtSalary(a.salary_max)}`
    : '—';
  const buckets = (a.experience_buckets || []).filter(b => b.count > 0);
  const titles = a.top_titles || [];
  const topSkills = (a.top_skills || []).slice(0, 12);
  root.innerHTML = `
    <div class="market-stat"><div class="market-stat-label">Карточек</div><div class="market-stat-value">${a.total}</div></div>
    <div class="market-stat"><div class="market-stat-label">Медиана зарплаты</div><div class="market-stat-value">${fmtSalary(a.salary_median)}</div></div>
    <div class="market-stat"><div class="market-stat-label">Вилка зарплат</div><div class="market-stat-value market-stat-range">${salaryRange}</div></div>
    <div class="market-stat"><div class="market-stat-label">Опыт, лет (среднее)</div><div class="market-stat-value">${a.experience_avg != null ? a.experience_avg : '—'}</div></div>
    <div class="market-stat market-stat-wide"><div class="market-stat-label">По источникам</div><div class="meta" style="margin-top:8px;">${escapeHtml(srcBits) || '—'}</div></div>
    ${buckets.length ? `<div class="market-stat"><div class="market-stat-label">Опыт на рынке</div><div class="bar-list">${skillBar(buckets)}</div></div>` : ''}
    ${titles.length ? `<div class="market-stat"><div class="market-stat-label">Частые должности</div><div class="bar-list">${skillBar(titles)}</div></div>` : ''}
    <div class="market-stat market-stat-wide"><div class="market-stat-label">Частые навыки на рынке</div>${topSkills.length ? `<div class="bar-list">${skillBar(topSkills)}</div>` : '<div class="meta" style="margin-top:8px;">—</div>'}</div>
    ${a.cv_compared ? `<div class="market-stat market-stat-wide"><div class="market-stat-label">Есть в вашем резюме</div><div class="skill-cloud">${present || '—'}</div></div>
    <div class="market-stat market-stat-wide"><div class="market-stat-label">Часто у других, нет у вас</div><div class="skill-cloud">${missing || 'ничего критичного не видно'}</div></div>` : '<div class="market-stat market-stat-wide"><div class="meta">Выберите своё резюме выше, чтобы увидеть пробелы относительно рынка.</div></div>'}
  `;
  renderMarketExamples(a.examples);
}

document.getElementById('m-filter-text')?.addEventListener('input', renderMarketGrid);
document.getElementById('m-filter-source')?.addEventListener('change', renderMarketGrid);

const btnMarket = document.getElementById('btn-market');
const marketStatus = document.getElementById('market-status');
const marketLog = document.getElementById('market-log');

btnMarket?.addEventListener('click', () => {
  const overrideOn = !document.getElementById('market-override')?.hidden;
  const payload = overrideOn ? payloadFromMarketForm() : payloadFromPrefs(accountPrefs, true);
  const sources = payload.sources;
  const keyword = payload.keyword;
  const query = payload.query;
  const region = payload.region;
  const pages = payload.pages;
  const delay = payload.delay;
  const allPages = payload.all_pages;
  const cvId = document.getElementById('market-cv-select').value;

  if (sources.length === 0) { marketStatus.textContent = 'Выберите хотя бы один источник в настройках аккаунта'; return; }
  if (!keyword && !query) { marketStatus.textContent = 'Задайте категорию или запрос в настройках аккаунта'; return; }

  const label = btnMarket.textContent;
  let finished = false;
  btnMarket.disabled = true;
  btnMarket.textContent = 'Собираю…';
  marketStatus.textContent = 'Соединяюсь…';
  marketLog.style.display = 'block';
  marketLog.textContent = '';
  document.getElementById('market-results-panel').style.display = 'none';
  document.getElementById('market-analysis-panel').style.display = 'none';
  const examplesPanel = document.getElementById('market-examples-panel');
  if (examplesPanel) examplesPanel.style.display = 'none';

  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${wsProtocol}//${location.host}/ws/candidates`);
  const restore = () => { btnMarket.disabled = false; btnMarket.textContent = label; };

  ws.addEventListener('open', () => {
    marketStatus.textContent = 'Собираю публичные карточки…';
    ws.send(JSON.stringify({ sources, keyword, query, region, pages, delay, all_pages: allPages, cv_id: cvId }));
  });
  ws.addEventListener('message', (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'log') {
      marketLog.textContent += msg.text + '\n';
      marketLog.scrollTop = marketLog.scrollHeight;
    } else if (msg.type === 'done') {
      finished = true;
      marketCards = msg.results || [];
      marketAnalysis = msg.analysis || null;
      marketStatus.textContent = `Готово: ${marketCards.length} карточек`;
      document.getElementById('m-filter-text').value = '';
      document.getElementById('m-filter-source').value = '';
      document.getElementById('market-results-panel').style.display = 'block';
      renderMarketAnalysis(marketAnalysis);
      renderMarketGrid();
      restore();
      ws.close();
    } else if (msg.type === 'error') {
      finished = true;
      marketLog.innerHTML += `<span class="err">Ошибка: ${escapeHtml(msg.text)}</span>\n`;
      marketStatus.textContent = 'Ошибка';
      restore();
      ws.close();
    }
  });
  ws.addEventListener('error', () => { if (!finished) marketStatus.textContent = 'Ошибка соединения'; });
  ws.addEventListener('close', (e) => {
    if (finished) return;
    if (btnMarket.disabled && !e.wasClean) {
      marketLog.innerHTML += `<span class="err">Соединение прервано</span>\n`;
      marketStatus.textContent = 'Соединение прервано';
      restore();
    }
  });
});

// ---------- Рынок кандидатов: автономно и адаптивно, как поиск вакансий ----------
// Сбор идёт в фоновом потоке (webapp._background_scan_user), сюда — только мгновенный
// показ уже собранного из постоянного хранилища + аналитика по нему, без своего сетевого похода.

async function loadCachedCandidates() {
  const payload = payloadFromPrefs(accountPrefs, true);
  if (!payload.sources.length || (!payload.keyword && !payload.query)) return;
  try {
    const resp = await fetch('/api/candidates/cached', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sources: payload.sources, keyword: payload.keyword, query: payload.query,
        region: payload.region, remote: payload.remote,
      }),
    });
    if (!resp.ok) return;
    const data = await resp.json();
    marketCards = data.candidates || [];
    document.getElementById('market-results-panel').style.display = 'block';
    renderMarketGrid();
  } catch (_) { /* нет кэша — фон найдёт на следующей проверке */ }
}

async function loadMarketAnalysis() {
  const payload = payloadFromPrefs(accountPrefs, true);
  if (!payload.sources.length || (!payload.keyword && !payload.query)) return;
  const cvId = document.getElementById('market-cv-select')?.value || '';
  try {
    const resp = await fetch('/api/candidates/analysis', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sources: payload.sources, keyword: payload.keyword, query: payload.query,
        region: payload.region, remote: payload.remote, cv_id: cvId,
      }),
    });
    if (!resp.ok) return;
    const data = await resp.json();
    marketAnalysis = data.analysis || null;
    renderMarketAnalysis(marketAnalysis);
  } catch (_) { /* аналитика необязательна — тихо пропускаем */ }
}

document.getElementById('market-cv-select')?.addEventListener('change', loadMarketAnalysis);

// ============================================================
// ИИ-ОЦЕНКА СООТВЕТСТВИЯ
// ============================================================

function scoreClass(score) {
  if (score >= 70) return 'good';
  if (score >= 40) return 'mid';
  return 'low';
}

async function runMatch(job, box, btn) {
  const cvId = document.getElementById('match-cv-select').value;
  if (!cvId) { showToast('Сначала выберите резюме в списке справа', true); return; }

  btn.disabled = true;
  btn.textContent = 'Оцениваю…';
  box.style.display = 'block';
  box.innerHTML = '<span class="status">Отправляю запрос ИИ…</span>';

  try {
    const resp = await fetch('/api/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job, cv_id: cvId }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      box.innerHTML = `<span class="status" style="color:var(--danger)">${escapeHtml(data.error || 'Ошибка ИИ-оценки')}</span>`;
    } else {
      const strengths = (data.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');
      const gaps = (data.gaps || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');
      const matchedKw = (data.matched_keywords || []).map(k => `<span class="kw-chip kw-matched">${escapeHtml(k)}</span>`).join('');
      const missingKw = (data.missing_keywords || []).map(k => `<span class="kw-chip kw-missing">${escapeHtml(k)}</span>`).join('');
      const studyList = (data.study_recommendations || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');
      box.innerHTML = `
        <span class="match-score ${scoreClass(data.score)}">${data.score}%</span>
        <div class="match-verdict">${escapeHtml(data.verdict || '')}</div>
        ${strengths ? `<ul class="match-list strengths">${strengths}</ul>` : ''}
        ${gaps ? `<ul class="match-list gaps">${gaps}</ul>` : ''}
        ${matchedKw || missingKw ? `<div class="ai-audit-heading">Ключевые слова вакансии</div><div class="kw-chips">${matchedKw}${missingKw}</div>` : ''}
        ${studyList ? `<div class="ai-audit-heading">Перед откликом почитайте</div><ul class="match-list study">${studyList}</ul>` : ''}
        ${data.recommendation ? `<div class="match-recommendation">💡 ${escapeHtml(data.recommendation)}</div>` : ''}
      `;
    }
  } catch (e) {
    box.innerHTML = `<span class="status" style="color:var(--danger)">Ошибка сети: ${escapeHtml(String(e))}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Оценить с ИИ';
  }
}

async function runCoverLetter(job, box, btn) {
  const cvId = document.getElementById('match-cv-select').value;
  if (!cvId) { showToast('Сначала выберите резюме в списке справа', true); return; }

  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Пишу…';
  box.style.display = 'block';
  box.innerHTML = '<span class="status">Составляю сопроводительное письмо…</span>';

  try {
    const resp = await fetch('/api/ai/cover-letter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job, cv_id: cvId }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      box.innerHTML = `<span class="status" style="color:var(--danger)">${escapeHtml(data.error || 'Ошибка ИИ')}</span>`;
    } else {
      box.innerHTML = `
        <div class="cover-letter-text">${escapeHtml(data.text)}</div>
        <button type="button" class="ghost small-add copy-cover-btn" style="margin-top:8px;">Скопировать</button>
      `;
      box.querySelector('.copy-cover-btn').addEventListener('click', () => {
        navigator.clipboard.writeText(data.text);
        showToast('Письмо скопировано');
      });
    }
  } catch (e) {
    box.innerHTML = `<span class="status" style="color:var(--danger)">Ошибка сети: ${escapeHtml(String(e))}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

// ---------- Просмотр вакансии целиком + отправка резюме ----------

let currentDetailJob = null;
let lastApplyDryRun = null;
let detailLoadSeq = 0;

function openJobDetail(job) {
  currentDetailJob = job;
  lastApplyDryRun = null;
  const seq = ++detailLoadSeq;

  document.getElementById('detail-src-badge').textContent = SOURCE_LABELS[job.source] || job.source;
  document.getElementById('detail-src-badge').className = `src-badge ${job.source}`;
  document.getElementById('detail-title').textContent = job.title || '';
  document.getElementById('detail-company').textContent = job.company || '';
  document.getElementById('detail-salary').textContent = job.salary || '';
  document.getElementById('detail-salary').style.display = job.salary ? 'block' : 'none';
  document.getElementById('detail-meta').textContent = job.meta || '';
  document.getElementById('detail-meta').style.display = job.meta ? 'block' : 'none';
  const descEl = document.getElementById('detail-description');
  descEl.textContent = job.description || '';
  descEl.classList.toggle('is-loading', !job._fullDescription && (job.source === 'rabotaua' || job.source === 'djinni'));
  document.getElementById('detail-link').href = job.url || '#';

  document.getElementById('detail-match-box').innerHTML = '';
  document.getElementById('detail-cover-box').innerHTML = '';
  const applyBox = document.getElementById('detail-apply-box');
  applyBox.innerHTML = '';
  applyBox.style.display = 'none';

  const applySection = document.getElementById('detail-apply-section');
  const applyHint = document.getElementById('detail-apply-hint');
  if (job.source === 'djinni') {
    applySection.style.display = 'block';
    applyHint.style.display = 'none';
  } else {
    applySection.style.display = 'none';
    applyHint.style.display = 'block';
  }

  openModal('modal-job-detail');
  if (!job._fullDescription && (job.source === 'rabotaua' || job.source === 'djinni')) {
    loadFullJobDescription(job, seq, descEl);
  }
}

async function loadFullJobDescription(job, seq, descEl) {
  try {
    const resp = await fetch('/api/jobs/description', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job }),
    });
    const data = await resp.json().catch(() => ({}));
    if (seq !== detailLoadSeq) return;
    const text = (data.description || '').trim();
    if (text) {
      descEl.textContent = text;
      job.description = text;
      job._fullDescription = true;
      if (currentDetailJob === job) currentDetailJob.description = text;
    }
  } catch (_) {
    /* оставляем анонс из выдачи */
  } finally {
    if (seq === detailLoadSeq) descEl.classList.remove('is-loading');
  }
}

document.querySelector('#modal-job-detail .jp-modal-backdrop')?.addEventListener('click', () => closeModal('modal-job-detail'));
document.getElementById('btn-detail-close')?.addEventListener('click', () => closeModal('modal-job-detail'));

document.getElementById('btn-detail-match')?.addEventListener('click', (e) => {
  if (!currentDetailJob) return;
  runMatch(currentDetailJob, document.getElementById('detail-match-box'), e.currentTarget);
});
document.getElementById('btn-detail-cover')?.addEventListener('click', (e) => {
  if (!currentDetailJob) return;
  runCoverLetter(currentDetailJob, document.getElementById('detail-cover-box'), e.currentTarget);
});

async function runApply(confirm) {
  if (!currentDetailJob) return;
  const cvId = document.getElementById('match-cv-select').value;
  if (!cvId) { showToast('Сначала выберите резюме в списке справа', true); return; }

  const btn = document.getElementById(confirm ? 'btn-detail-apply-confirm' : 'btn-detail-apply');
  const box = document.getElementById('detail-apply-box');
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = confirm ? 'Отправляю…' : 'Проверяю…';
  box.style.display = 'block';
  box.innerHTML = '<span class="status">Вхожу в ваш аккаунт djinni.co и ищу форму отклика…</span>';

  try {
    const resp = await fetch('/api/jobs/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job: currentDetailJob, cv_id: cvId, confirm: !!confirm }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      box.innerHTML = `<span class="status" style="color:var(--danger)">${escapeHtml(data.error || 'Ошибка отправки')}</span>`;
      document.getElementById('btn-detail-apply-confirm').style.display = 'none';
      return;
    }
    if (data.status === 'dry_run') {
      lastApplyDryRun = data;
      box.innerHTML = `
        <div class="status" style="color:var(--warning)">⚠ Пока НЕ отправлено — это предпросмотр</div>
        <div class="hint-inline" style="margin-top:6px;">Нашёл форму отклика. Проверьте письмо ниже — если всё верно, нажмите «Точно отправить».</div>
        <div class="cover-letter-text" style="margin-top:8px;">${escapeHtml(data.cover_letter || data.cover_letter_preview || '')}</div>
      `;
      document.getElementById('btn-detail-apply-confirm').style.display = 'inline-flex';
    } else if (data.status === 'sent') {
      box.innerHTML = `<span class="status" style="color:var(--success)">✓ Отклик отправлен на djinni.co</span>`;
      document.getElementById('btn-detail-apply-confirm').style.display = 'none';
    }
  } catch (e) {
    box.innerHTML = `<span class="status" style="color:var(--danger)">Ошибка сети: ${escapeHtml(String(e))}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

document.getElementById('btn-detail-apply')?.addEventListener('click', () => runApply(false));
document.getElementById('btn-detail-apply-confirm')?.addEventListener('click', () => runApply(true));

// ---------- Подбор вакансий по резюме (ранжирование всего найденного списка) ----------

async function runRankJobsByResume() {
  const cvId = document.getElementById('match-cv-select').value;
  if (!cvId) { showToast('Сначала выберите резюме в списке справа', true); return; }
  if (!allJobs.length) { showToast('Сначала найдите вакансии', true); return; }

  const statusEl = document.getElementById('rank-jobs-status');
  const listEl = document.getElementById('rank-jobs-list');
  statusEl.textContent = `Сверяю резюме с ${allJobs.length} вакансиями…`;
  listEl.innerHTML = '';
  openModal('modal-rank-jobs');

  try {
    const resp = await fetch('/api/jobs/rank-by-resume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jobs: allJobs, cv_id: cvId }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      statusEl.textContent = '';
      listEl.innerHTML = `<span class="status" style="color:var(--danger)">${escapeHtml(data.error || 'Ошибка подбора')}</span>`;
      return;
    }
    const results = (data.results || []).filter(r => r.score > 0).slice(0, 30);
    statusEl.textContent = results.length
      ? `Топ ${results.length} по совпадению с резюме — из ${allJobs.length} вакансий`
      : '';
    if (!results.length) {
      listEl.innerHTML = '<div class="empty">Совпадений не нашлось — резюме и вакансии почти не пересекаются по ключевым словам.</div>';
      return;
    }
    listEl.innerHTML = results.map(r => {
      const job = allJobs[r.index];
      if (!job) return '';
      const hasAi = r.verdict !== undefined;
      const strengths = (r.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');
      const gaps = (r.gaps || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');
      const kwChips = (r.matched_keywords || []).map(k => `<span class="kw-chip kw-matched">${escapeHtml(k)}</span>`).join('');
      return `
        <div class="rank-job-card" data-idx="${r.index}">
          <div class="rank-job-head">
            <span class="match-score ${scoreClass(r.score)}">${r.score}%</span>
            <div class="rank-job-title-block">
              <button type="button" class="job-title-btn rank-job-open" data-idx="${r.index}">${escapeHtml(job.title || '')}</button>
              <div class="company">${escapeHtml(job.company || '')}</div>
            </div>
            <span class="src-badge ${job.source}">${escapeHtml(SOURCE_LABELS[job.source] || job.source)}</span>
          </div>
          ${hasAi ? `
            ${r.verdict ? `<div class="match-verdict">${escapeHtml(r.verdict)}</div>` : ''}
            ${strengths ? `<ul class="match-list strengths">${strengths}</ul>` : ''}
            ${gaps ? `<ul class="match-list gaps">${gaps}</ul>` : ''}
          ` : ''}
          ${kwChips ? `<div class="kw-chips">${kwChips}</div>` : ''}
        </div>`;
    }).join('');
    listEl.querySelectorAll('.rank-job-open').forEach(btn => {
      btn.addEventListener('click', () => {
        const job = allJobs[Number(btn.dataset.idx)];
        if (job) { closeModal('modal-rank-jobs'); openJobDetail(job); }
      });
    });
  } catch (e) {
    statusEl.textContent = '';
    listEl.innerHTML = `<span class="status" style="color:var(--danger)">Ошибка сети: ${escapeHtml(String(e))}</span>`;
  }
}

document.getElementById('btn-rank-jobs')?.addEventListener('click', runRankJobsByResume);
document.getElementById('rank-jobs-backdrop')?.addEventListener('click', () => closeModal('modal-rank-jobs'));
document.getElementById('btn-rank-jobs-close')?.addEventListener('click', () => closeModal('modal-rank-jobs'));

// ============================================================
// РЕЗЮМЕ
// ============================================================

const cvListEl = document.getElementById('cv-list');
const cvEmptyEl = document.getElementById('cv-empty');
const matchCvSelect = document.getElementById('match-cv-select');
const dropzone = document.getElementById('dropzone');
const cvFileInput = document.getElementById('cv-file-input');
const cvUploadStatus = document.getElementById('cv-upload-status');

async function loadCvs() {
  const resp = await fetch('/api/cvs');
  const cvs = await resp.json();

  if (cvs.length === 0) {
    cvListEl.innerHTML = '';
    cvEmptyEl.style.display = 'block';
  } else {
    cvEmptyEl.style.display = 'none';
    const iconLabel = { pdf: 'PDF', docx: 'DOC', txt: 'TXT', builder: 'CV' };
    cvListEl.innerHTML = cvs.map(cv => `
      <div class="cv-card" data-cv-card="${cv.id}">
        <div class="cv-row">
          <div class="cv-icon">${iconLabel[cv.format] || cv.format.toUpperCase()}</div>
          <div class="cv-info">
            <div class="cv-name">${escapeHtml(cv.original_name)}</div>
            <div class="cv-meta">${cv.format === 'builder' ? 'Собрано в конструкторе' : cv.size_human} · ${cv.text_len} симв. текста</div>
          </div>
          <div class="cv-row-actions">
            <button type="button" class="small-primary" data-hr-id="${cv.id}">Аналитика HR</button>
            ${cv.format === 'builder' ? `<button class="ghost" data-edit-id="${cv.id}">Редактировать</button>` : ''}
            <button class="danger-ghost" data-id="${cv.id}">Удалить</button>
          </div>
        </div>
        <div class="cv-hr-panel" data-hr-panel="${cv.id}" hidden></div>
      </div>
    `).join('');
    cvListEl.querySelectorAll('.danger-ghost').forEach(b => {
      b.addEventListener('click', async () => {
        await fetch(`/api/cvs/${b.dataset.id}`, { method: 'DELETE' });
        loadCvs();
      });
    });
    cvListEl.querySelectorAll('[data-edit-id]').forEach(b => {
      b.addEventListener('click', () => {
        openResumeBuilder();
        loadResumeIntoForm(b.dataset.editId);
      });
    });
    cvListEl.querySelectorAll('[data-hr-id]').forEach(b => {
      b.addEventListener('click', () => runHrAnalytics(b.dataset.hrId, b));
    });
  }

  matchCvSelect.innerHTML = '<option value="">ИИ-оценка: выберите резюме</option>' +
    cvs.map(cv => `<option value="${cv.id}">${escapeHtml(cv.original_name)}</option>`).join('');
  const marketCv = document.getElementById('market-cv-select');
  if (marketCv) {
    const keep = marketCv.value;
    marketCv.innerHTML = '<option value="">Без сверки — только рынок</option>' +
      cvs.map(cv => `<option value="${cv.id}">${escapeHtml(cv.original_name)}</option>`).join('');
    if (keep) marketCv.value = keep;
  }
  const hrCv = document.getElementById('hr-cv-select');
  if (hrCv) {
    const keep = hrCv.value;
    hrCv.innerHTML = '<option value="">Резюме, открытое в конструкторе</option>' +
      cvs.map(cv => `<option value="${cv.id}">${escapeHtml(cv.original_name)}</option>`).join('');
    if (keep) hrCv.value = keep;
  }
}

function populateHrJobSelect() {
  const sel = document.getElementById('hr-job-select');
  if (!sel) return;
  const keep = sel.value;
  sel.innerHTML = '<option value="">Без вакансии — общие вопросы по резюме</option>' +
    allJobs.map((j, i) => `<option value="${i}">${escapeHtml(j.title || '')}${j.company ? ' — ' + escapeHtml(j.company) : ''}</option>`).join('');
  if (keep && Number(keep) < allJobs.length) sel.value = keep;
}

async function uploadCv(file) {
  cvUploadStatus.textContent = `Загружаю ${file.name}…`;
  const formData = new FormData();
  formData.append('file', file);
  try {
    const resp = await fetch('/api/cvs', { method: 'POST', body: formData });
    const data = await resp.json();
    if (!resp.ok) {
      cvUploadStatus.textContent = data.error || 'Ошибка загрузки';
      showToast(data.error || 'Ошибка загрузки', true);
    } else {
      cvUploadStatus.textContent = `Загружено: ${file.name}`;
      showToast('Резюме загружено');
      loadCvs();
    }
  } catch (e) {
    cvUploadStatus.textContent = 'Ошибка сети: ' + e;
  }
}

dropzone.addEventListener('click', () => cvFileInput.click());
cvFileInput.addEventListener('change', () => {
  if (cvFileInput.files[0]) uploadCv(cvFileInput.files[0]);
  cvFileInput.value = '';
});
['dragover', 'dragenter'].forEach(evt => {
  dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add('drag'); });
});
['dragleave', 'drop'].forEach(evt => {
  dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove('drag'); });
});
dropzone.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files[0];
  if (file) uploadCv(file);
});

const HR_ANALYTICS_STEPS = [
  { id: 'read', label: 'Читаю резюме' },
  { id: 'audit', label: 'Оценка' },
  { id: 'flags', label: 'Красные флаги' },
  { id: 'path', label: 'Траектория' },
  { id: 'market', label: 'Рынок' },
];
let hrAnalyticsSeq = 0;

function hrStepperHtml(activeId, states) {
  return HR_ANALYTICS_STEPS.map((step, i) => {
    const st = states[step.id] || (step.id === activeId ? 'active' : '');
    const line = i < HR_ANALYTICS_STEPS.length - 1
      ? `<div class="ai-step-line${st === 'done' || states[HR_ANALYTICS_STEPS[i + 1].id] ? ' done' : ''}"></div>`
      : '';
    const num = (st === 'done' || st === 'fail') ? '' : String(i + 1);
    return `<div class="ai-step ${st}" data-hr-step="${step.id}"><div class="ai-step-num">${num}</div><div class="ai-step-label">${escapeHtml(step.label)}</div></div>${line}`;
  }).join('');
}

function renderHrProgress(panel, { activeId, states, pct, live }) {
  const fill = panel.querySelector('.hr-progress-fill');
  const pctEl = panel.querySelector('.hr-progress-pct');
  const stepsEl = panel.querySelector('.hr-steps');
  const liveEl = panel.querySelector('.hr-live');
  const liveText = panel.querySelector('.hr-live-text');
  if (fill) fill.style.width = `${pct}%`;
  if (pctEl) pctEl.textContent = `${pct}%`;
  if (stepsEl) stepsEl.innerHTML = hrStepperHtml(activeId, states);
  if (liveEl) liveEl.hidden = !live;
  if (liveText && live) liveText.textContent = live;
  const track = panel.querySelector('.hr-progress-track');
  if (track) track.setAttribute('aria-valuenow', String(pct));
}

function appendHrResult(panel, title, html) {
  const box = panel.querySelector('.hr-results');
  if (!box) return;
  const block = document.createElement('div');
  block.className = 'hr-result-block';
  block.innerHTML = `<h4>${escapeHtml(title)}</h4>${html}`;
  box.appendChild(block);
  block.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function postAiJson(url, body) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: resp.ok, data };
}

async function runHrAnalytics(cvId, btn) {
  const card = document.querySelector(`[data-cv-card="${cvId}"]`);
  const panel = document.querySelector(`[data-hr-panel="${cvId}"]`);
  if (!card || !panel) return;

  document.querySelectorAll('.cv-card.is-analyzing').forEach((el) => {
    if (el !== card) el.classList.remove('is-analyzing');
  });
  document.querySelectorAll('.cv-hr-panel').forEach((el) => {
    if (el !== panel) el.hidden = true;
  });

  const seq = ++hrAnalyticsSeq;
  const states = {};
  const setStep = (id, state) => { states[id] = state; };

  card.classList.add('is-analyzing');
  panel.hidden = false;
  panel.setAttribute('aria-busy', 'true');
  panel.innerHTML = `
    <div class="hr-progress-head">
      <div class="hr-progress-title">Аналитика HR</div>
      <div class="hr-progress-pct">0%</div>
    </div>
    <div class="hr-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" aria-label="Ход аналитики HR">
      <div class="hr-progress-fill"></div>
    </div>
    <div class="hr-steps">${hrStepperHtml('read', { read: 'active' })}</div>
    <div class="hr-live">
      <div class="ai-loading-spinner" aria-hidden="true"><div></div><div></div><div></div></div>
      <div class="hr-live-text">Открываю резюме…</div>
    </div>
    <div class="hr-results"></div>
  `;
  if (btn) { btn.disabled = true; }

  const stillMine = () => seq === hrAnalyticsSeq && panel.isConnected;
  const tick = (id, pct, live) => {
    if (!stillMine()) return false;
    renderHrProgress(panel, { activeId: id, states, pct, live });
    return true;
  };

  try {
    setStep('read', 'active');
    if (!tick('read', 8, 'Читаю резюме…')) return;
    const srcResp = await fetch(`/api/cvs/${cvId}/hr-source`);
    const src = await srcResp.json().catch(() => ({}));
    if (!stillMine()) return;
    if (!srcResp.ok) {
      setStep('read', 'fail');
      tick('read', 8, '');
      appendHrResult(panel, 'Резюме', `<span class="status" style="color:var(--danger)">${escapeHtml(src.error || 'не удалось открыть')}</span>`);
      return;
    }
    const resumeData = src.resume_data || {};
    const template = src.template || 'classic';
    setStep('read', 'done');
    if (!tick('audit', 20, 'Оцениваю структуру и формулировки…')) return;

    setStep('audit', 'active');
    const audit = await postAiJson('/api/ai/audit-resume', {
      resume_data: resumeData, template, compare_market: false,
    });
    if (!stillMine()) return;
    if (!audit.ok) {
      setStep('audit', 'fail');
      tick('audit', 20, '');
      appendHrResult(panel, 'Оценка', `<span class="status" style="color:var(--danger)">${escapeHtml(audit.data.error || 'Ошибка ИИ')}</span>`);
    } else {
      setStep('audit', 'done');
      appendHrResult(panel, 'Оценка резюме', renderAuditHtml(audit.data));
    }
    if (!tick('flags', 40, 'Ищу красные флаги…')) return;

    setStep('flags', 'active');
    const flags = await postAiJson('/api/ai/red-flags', { resume_data: resumeData });
    if (!stillMine()) return;
    if (!flags.ok) {
      setStep('flags', 'fail');
      appendHrResult(panel, 'Красные флаги', `<span class="status" style="color:var(--danger)">${escapeHtml(flags.data.error || 'Ошибка ИИ')}</span>`);
    } else {
      setStep('flags', 'done');
      appendHrResult(panel, 'Красные флаги', renderRedFlagsHtml(flags.data));
    }
    if (!tick('path', 60, 'Смотрю карьерную траекторию…')) return;

    setStep('path', 'active');
    const path = await postAiJson('/api/ai/career-trajectory', { resume_data: resumeData });
    if (!stillMine()) return;
    if (!path.ok) {
      setStep('path', 'fail');
      appendHrResult(panel, 'Траектория', `<span class="status" style="color:var(--danger)">${escapeHtml(path.data.error || 'Ошибка ИИ')}</span>`);
    } else {
      setStep('path', 'done');
      appendHrResult(panel, 'Карьерная траектория', renderTrajectoryHtml(path.data));
    }
    if (!tick('market', 78, 'Сверяю с рынком — вакансии и похожие резюме…')) return;

    setStep('market', 'active');
    const market = await postAiJson('/api/ai/market-fit', { resume_data: resumeData });
    if (!stillMine()) return;
    if (market.data.skipped) {
      setStep('market', 'skipped');
      appendHrResult(panel, 'Рынок', `<span class="status">${escapeHtml(market.data.error || 'Сверку с рынком пропустил')}</span>`);
    } else if (!market.ok) {
      setStep('market', 'fail');
      appendHrResult(panel, 'Рынок', `<span class="status" style="color:var(--danger)">${escapeHtml(market.data.error || 'Ошибка сверки')}</span>`);
    } else {
      setStep('market', 'done');
      appendHrResult(panel, 'Сравнение с рынком', renderMarketFit(market.data.market_fit) || `<span class="status">${escapeHtml(market.data.error || '')}</span>`);
    }
    if (!tick('', 100, '')) return;
    renderHrProgress(panel, { activeId: '', states, pct: 100, live: '' });
  } catch (err) {
    if (!stillMine()) return;
    appendHrResult(panel, 'Ошибка', `<span class="status" style="color:var(--danger)">${escapeHtml(String(err))}</span>`);
    renderHrProgress(panel, { activeId: '', states, pct: Number(panel.querySelector('.hr-progress-track')?.getAttribute('aria-valuenow') || 0), live: '' });
  } finally {
    if (stillMine()) {
      panel.removeAttribute('aria-busy');
      card.classList.add('is-analyzing');
    }
    if (btn) btn.disabled = false;
  }
}

// ============================================================
// НАСТРОЙКИ ИИ
// ============================================================

async function loadSettings() {
  const resp = await fetch('/api/settings');
  if (!resp.ok) return;
  const s = await resp.json();
  platformStatus = {
    ai_ready: !!s.ai_ready,
    jooble_ready: !!s.jooble_ready,
    boards_ready: s.boards_ready || {},
  };
  syncSearchFormUi();
  syncPrefSearchUi();
  syncMarketBoardsHint();
}

async function loadProfile() {
  const resp = await fetch('/api/profile');
  if (!resp.ok) return null;
  const p = await resp.json();
  const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  setVal('profile-first-name', p.first_name);
  setVal('profile-last-name', p.last_name);
  setVal('profile-email', p.email);
  setVal('profile-phone', p.phone);
  setVal('profile-location', p.location);
  applyRegions('profile-headline-chips', 'profile-headline-extra', p.headline || '');
  applyBoardStatus(p);
  return p;
}

document.getElementById('btn-save-profile')?.addEventListener('click', async () => {
  const statusEl = document.getElementById('profile-save-status');
  statusEl.textContent = 'Сохраняю…';
  try {
    const resp = await fetch('/api/profile', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        first_name: document.getElementById('profile-first-name').value,
        last_name: document.getElementById('profile-last-name').value,
        email: document.getElementById('profile-email').value,
        phone: document.getElementById('profile-phone').value,
        location: document.getElementById('profile-location').value,
        headline: collectRegions('profile-headline-chips', 'profile-headline-extra'),
      }),
    });
    const result = await resp.json();
    if (!resp.ok) {
      statusEl.textContent = result.error || 'Ошибка';
      showToast(result.error || 'Не удалось сохранить профиль', true);
      return;
    }
    statusEl.textContent = 'Сохранено';
    showToast('Профиль сохранён');
    syncProfileIntoResume(result);
    const nameEl = document.querySelector('.sidebar-user-name');
    if (nameEl && result.name) nameEl.textContent = result.name;
    const emailEl = document.querySelector('.sidebar-user-email');
    if (emailEl && result.email) emailEl.textContent = result.email;
  } catch (e) {
    statusEl.textContent = 'Ошибка сети: ' + e;
  }
});

document.getElementById('btn-suggest-headline')?.addEventListener('click', async () => {
  const statusEl = document.getElementById('suggest-headline-status');
  let cvId = matchCvSelect?.value;
  if (!cvId) {
    for (const opt of matchCvSelect?.options || []) { if (opt.value) { cvId = opt.value; break; } }
  }
  if (!cvId) { showToast('Сначала добавьте резюме — в разделе «Резюме»', true); return; }

  statusEl.textContent = 'Подбираю по резюме…';
  try {
    const resp = await fetch('/api/ai/suggest-headline', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cv_id: cvId }),
    });
    const data = await resp.json();
    if (!resp.ok) { statusEl.textContent = ''; showToast(data.error || 'Ошибка ИИ', true); return; }
    applyRegions('profile-headline-chips', 'profile-headline-extra', (data.positions || []).join(', '));
    statusEl.textContent = 'Подобрано — проверьте и нажмите «Сохранить профиль».';
  } catch (e) {
    statusEl.textContent = '';
    showToast('Ошибка сети: ' + e, true);
  }
});

const SEARCH_PREF_CHIP_IDS = { djinni: 'pref-src-djinni', workua: 'pref-src-workua', rabotaua: 'pref-src-rabotaua', jooble: 'pref-src-jooble' };

let prefsDirty = false;
let prefsSaveTimer = null;

function syncPrefSearchUi() {
  ['pref-chip-djinni', 'pref-chip-workua', 'pref-chip-rabotaua', 'pref-chip-jooble'].forEach(id => {
    if (document.getElementById(id)) updateChipStyle(id);
  });
  const joobleOn = document.getElementById('pref-src-jooble')?.checked;
  syncJoobleHint('pref-jooble-hint', joobleOn);
  const delayInput = document.getElementById('pref-delay');
  const delayHint = document.getElementById('pref-delay-hint');
  const workuaOn = document.getElementById('pref-src-workua')?.checked;
  if (workuaOn && delayInput && Number(delayInput.value) < 3) delayInput.value = 3;
  if (delayHint) {
    delayHint.textContent = workuaOn
      ? 'Для work.ua не меньше 3 сек — иначе сайт включает проверку.'
      : 'Пауза между страницами выдачи.';
  }
  const allOn = document.getElementById('pref-all-pages')?.checked;
  const pagesInput = document.getElementById('pref-pages');
  const pagesField = document.getElementById('pref-pages-field');
  if (pagesInput) pagesInput.disabled = !!allOn;
  pagesField?.classList.toggle('is-disabled', !!allOn);
  document.getElementById('pref-all-pages-chip')?.classList.toggle('active', !!allOn);
}

function collectSettingsPrefs() {
  const sources = Object.entries(SEARCH_PREF_CHIP_IDS)
    .filter(([, id]) => document.getElementById(id)?.checked)
    .map(([src]) => src);
  return {
    keyword: collectRegions('pref-keyword-chips', 'pref-keyword-extra'),
    query: document.getElementById('pref-query')?.value || '',
    region: collectRegions('pref-region-chips', 'pref-region-extra'),
    sources,
    remote: collectRemote('pref-remote'),
    reservation: document.getElementById('pref-reservation')?.checked || false,
    employment_type: document.getElementById('pref-employment')?.value || '',
    salary_expectation: document.getElementById('pref-salary')?.value || '',
    all_pages: document.getElementById('pref-all-pages')?.checked || false,
    pages: document.getElementById('pref-pages')?.value || 1,
    delay: document.getElementById('pref-delay')?.value || 3,
  };
}

function applyPrefsToSettingsForm(p) {
  if (!p) return;
  const q = document.getElementById('pref-query');
  if (q) q.value = p.query || '';
  applyRegions('pref-keyword-chips', 'pref-keyword-extra', p.keyword || '');
  applyRegions('pref-region-chips', 'pref-region-extra', p.region || '');
  applyRemote('pref-remote', p.remote || '');
  applyReservation('pref-reservation', p.reservation);
  const emp = document.getElementById('pref-employment');
  if (emp) emp.value = p.employment_type || '';
  const sal = document.getElementById('pref-salary');
  if (sal) sal.value = p.salary_expectation || '';
  const pages = document.getElementById('pref-pages');
  if (pages) pages.value = p.pages || 1;
  const delay = document.getElementById('pref-delay');
  if (delay) delay.value = p.delay || 3;
  const prefAll = document.getElementById('pref-all-pages');
  if (prefAll) prefAll.checked = p.all_pages !== false;
  Object.entries(SEARCH_PREF_CHIP_IDS).forEach(([src, id]) => {
    const el = document.getElementById(id);
    if (el) el.checked = (p.sources || []).includes(src);
  });
  syncPrefSearchUi();
}

function applyPrefsToSearchForms(p) {
  if (!p) return;
  applyRegions('keyword-chips', 'f-keyword-extra', p.keyword || '');
  applyRegions('m-keyword-chips', 'm-keyword-extra', p.keyword || '');
  const fq = document.getElementById('f-query');
  if (fq) fq.value = p.query || '';
  const mq = document.getElementById('m-query');
  if (mq) mq.value = p.query || '';
  applyRegions('region-chips', 'f-region-extra', p.region || '');
  applyRegions('m-region-chips', 'm-region-extra', p.region || '');
  applyRemote('f-remote', p.remote || '');
  applyRemote('m-remote', p.remote || '');
  applyReservation('f-reservation', p.reservation);
  if (p.sources && p.sources.length) {
    document.querySelectorAll('#tab-search .sources input[type=checkbox]').forEach(cb => {
      cb.checked = p.sources.includes(cb.value);
    });
    document.querySelectorAll('#m-sources input[type=checkbox]:not(:disabled)').forEach(cb => {
      cb.checked = p.sources.includes(cb.value);
    });
  }
  if (typeof p.all_pages === 'boolean') {
    const fAll = document.getElementById('f-all-pages');
    if (fAll) fAll.checked = p.all_pages;
    const mAll = document.getElementById('m-all-pages');
    if (mAll) mAll.checked = p.all_pages;
  }
  if (p.pages) {
    const fp = document.getElementById('f-pages');
    if (fp) fp.value = p.pages;
    const mp = document.getElementById('m-pages');
    if (mp) mp.value = p.pages;
  }
  if (p.delay) {
    const fd = document.getElementById('f-delay');
    if (fd) fd.value = p.delay;
    const md = document.getElementById('m-delay');
    if (md) md.value = p.delay;
  }
  syncSearchFormUi();
  syncMarketAllPages();
  ['m-chip-djinni', 'm-chip-workua', 'm-chip-rabotaua'].forEach(id => {
    if (document.getElementById(id)) updateChipStyle(id);
  });
}

function adoptPrefs(p) {
  accountPrefs = { ...accountPrefs, ...p };
  refreshPrefsSummaries();
}

async function loadSearchPrefsIntoSettings() {
  const resp = await fetch('/api/search-prefs');
  if (!resp.ok) return null;
  const p = await resp.json();
  if (prefsDirty) return p;
  adoptPrefs(p);
  applyPrefsToSettingsForm(p);
  return p;
}

async function saveSearchPrefs(opts = {}) {
  const silent = !!opts.silent;
  const statusEl = document.getElementById('prefs-save-status');
  const payload = opts.payload || collectSettingsPrefs();
  if (!payload.sources.length) {
    if (statusEl && !silent) statusEl.textContent = 'Выберите хотя бы один источник';
    if (!silent) showToast('Выберите хотя бы один источник', true);
    return null;
  }
  if (statusEl && !silent) statusEl.textContent = 'Сохраняю…';
  try {
    const resp = await fetch('/api/search-prefs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const saved = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const err = saved.error || 'Не удалось сохранить фильтры';
      if (statusEl) statusEl.textContent = err;
      if (!silent) showToast(err, true);
      return null;
    }
    prefsDirty = false;
    adoptPrefs(saved);
    applyPrefsToSettingsForm(saved);
    applyPrefsToSearchForms(saved);
    if (statusEl) statusEl.textContent = 'Сохранено';
    if (!silent) showToast('Фильтры поиска сохранены');
    return saved;
  } catch (e) {
    if (statusEl) statusEl.textContent = 'Ошибка сети: ' + e;
    if (!silent) showToast('Сеть: не удалось сохранить фильтры', true);
    return null;
  }
}

function schedulePrefsAutosave() {
  prefsDirty = true;
  clearTimeout(prefsSaveTimer);
  prefsSaveTimer = setTimeout(() => saveSearchPrefs({ silent: true }), 700);
}

document.getElementById('btn-save-prefs')?.addEventListener('click', () => saveSearchPrefs());

document.querySelector('[data-acct-panel="search"]')?.addEventListener('change', schedulePrefsAutosave);
document.querySelector('[data-acct-panel="search"]')?.addEventListener('input', (e) => {
  if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA')) {
    schedulePrefsAutosave();
  }
});

async function applySearchPrefsToForm() {
  const resp = await fetch('/api/search-prefs');
  if (!resp.ok) return;
  const p = await resp.json();
  adoptPrefs(p);
  applyPrefsToSearchForms(p);
}

document.getElementById('btn-save-search-as-prefs')?.addEventListener('click', () => {
  saveSearchPrefs({
    payload: {
      ...collectSettingsPrefs(),
      ...payloadFromSearchForm(),
      employment_type: document.getElementById('pref-employment')?.value || '',
      salary_expectation: document.getElementById('pref-salary')?.value || '',
    },
  });
});
document.getElementById('btn-save-market-as-prefs')?.addEventListener('click', () => {
  const market = payloadFromMarketForm();
  saveSearchPrefs({
    payload: {
      ...collectSettingsPrefs(),
      keyword: market.keyword,
      query: market.query,
      region: market.region,
      sources: market.sources,
      remote: market.remote,
      all_pages: market.all_pages,
      pages: market.pages,
      delay: market.delay,
    },
  });
});

// Ключи ИИ / Jooble задаются только в админке владельцем сайта.

// ============================================================
// КОНСТРУКТОР РЕЗЮМЕ
// ============================================================

const REPEAT_FIELDS = {
  experience: [
    { key: 'position', label: 'Должность', type: 'text' },
    { key: 'company', label: 'Компания', type: 'text' },
    { key: 'period', label: 'Период', type: 'text', placeholder: '2022 — н.в.' },
    { key: 'description', label: 'Описание', type: 'textarea' },
  ],
  education: [
    { key: 'degree', label: 'Специальность / степень', type: 'text' },
    { key: 'school', label: 'Учебное заведение', type: 'text' },
    { key: 'period', label: 'Период', type: 'text', placeholder: '2018 — 2022' },
  ],
  languages: [
    { key: 'name', label: 'Язык', type: 'text', placeholder: 'Английский' },
    { key: 'level', label: 'Уровень', type: 'text', placeholder: 'B2' },
  ],
  links: [
    { key: 'label', label: 'Название', type: 'text', placeholder: 'LinkedIn' },
    { key: 'url', label: 'URL', type: 'text', placeholder: 'https://…' },
  ],
  achievements: [
    { key: 'value', label: 'Цифра', type: 'text', placeholder: '+40%' },
    { key: 'label', label: 'Что это', type: 'text', placeholder: 'Ускорение деплоя' },
    { key: 'description', label: 'Подробности (необязательно)', type: 'textarea', context: 'описание достижения в резюме' },
  ],
};

const REPEAT_TITLES = {
  experience: v => [v.position, v.company].filter(Boolean).join(' — ') || 'Новое место работы',
  education: v => [v.degree, v.school].filter(Boolean).join(', ') || 'Новое образование',
  languages: v => v.name || 'Новый язык',
  links: v => v.label || v.url || 'Новая ссылка',
  achievements: v => [v.value, v.label].filter(Boolean).join(' — ') || 'Новое достижение',
};

let currentResumeId = null;
let currentCanvasLayout = JSON.parse(JSON.stringify(DEFAULT_CANVAS_LAYOUT));
let currentCanvasImages = [];
let currentAvatarUrl = '';
let frozenFromTemplate = null; // если задано — «Свободный холст» показывает не пустые блоки,
                                // а разморозку этого готового шаблона (см. freezeCurrentTemplateToCanvas)
let frozenSkin = null;         // { rootClass, styleVars } — тема размороженного шаблона

function updateAvatarPreview() {
  const preview = document.getElementById('avatar-preview');
  const placeholder = document.getElementById('avatar-placeholder');
  document.getElementById('btn-remove-avatar').style.display = currentAvatarUrl ? 'inline-flex' : 'none';
  if (currentAvatarUrl) {
    preview.style.backgroundImage = 'url("' + currentAvatarUrl.replace(/"/g, '%22') + '")';
    if (placeholder) placeholder.style.display = 'none';
  } else {
    preview.style.backgroundImage = '';
    if (placeholder) placeholder.style.display = 'block';
  }
}

document.getElementById('btn-add-avatar').addEventListener('click', () => {
  document.getElementById('avatar-file-input').click();
});

document.getElementById('btn-remove-avatar').addEventListener('click', () => {
  currentAvatarUrl = '';
  updateAvatarPreview();
  renderResumePreview();
});

document.getElementById('avatar-file-input').addEventListener('change', async () => {
  const input = document.getElementById('avatar-file-input');
  const file = input.files[0];
  if (!file) return;
  const statusEl = document.getElementById('avatar-upload-status');
  const fd = new FormData();
  fd.append('file', file);
  statusEl.textContent = 'Загружаю…';
  try {
    const resp = await fetch('/api/resumes/images', { method: 'POST', body: fd });
    const data = await resp.json();
    if (!resp.ok) { statusEl.textContent = ''; showToast(data.error || 'Ошибка загрузки фото', true); return; }
    currentAvatarUrl = data.url;
    updateAvatarPreview();
    renderResumePreview();
    statusEl.textContent = '';
  } catch (e) {
    statusEl.textContent = '';
    showToast('Ошибка сети: ' + e, true);
  } finally {
    input.value = '';
  }
});

function addRepeatRow(containerId, kind, values) {
  values = values || {};
  const container = document.getElementById(containerId);
  const row = document.createElement('div');
  row.className = 'repeat-row';
  const rowFieldId = 'f_' + Math.random().toString(36).slice(2, 9);
  const fieldsHtml = REPEAT_FIELDS[kind].map((f, i) => `
    <div class="field">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <label>${f.label}</label>
        ${f.type === 'textarea' ? `
          <span>
            ${kind === 'experience' ? `<button type="button" class="ai-bullets-btn" data-target="${rowFieldId}_${i}"><svg class="icn" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="10" cy="10" r="7"/><circle cx="10" cy="10" r="3.5"/><circle cx="10" cy="10" r=".6" fill="currentColor" stroke="none"/></svg>Развернуть в буллеты</button>` : ''}
            <button type="button" class="ai-improve-btn" data-target="${rowFieldId}_${i}" data-context="${escapeHtml(f.context || 'описание места работы в резюме')}"><svg class="icn" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2.5l1.2 3.6L15 7.5l-3.8 1.4L10 12.5l-1.2-3.6L5 7.5l3.8-1.4L10 2.5z"/><path d="M16 12l.6 1.8 1.9.7-1.9.7L16 17l-.6-1.8-1.9-.7 1.9-.7L16 12z"/></svg>Улучшить с ИИ</button>
          </span>` : ''}
      </div>
      ${f.type === 'textarea'
        ? `<textarea id="${rowFieldId}_${i}" data-key="${f.key}" rows="2" placeholder="${escapeHtml(f.placeholder || '')}">${escapeHtml(values[f.key] || '')}</textarea>`
        : `<input type="text" data-key="${f.key}" placeholder="${escapeHtml(f.placeholder || '')}" value="${escapeHtml(values[f.key] || '')}">`}
    </div>
  `).join('');
  row.innerHTML = `
    <div class="repeat-row-head">
      <span class="repeat-drag" title="Порядок пока фиксированный">⠿</span>
      <span class="repeat-row-title">${escapeHtml(REPEAT_TITLES[kind](values))}</span>
      <button type="button" class="repeat-icon-btn" title="Удалить запись">✕</button>
    </div>
    <div class="repeat-row-grid">${fieldsHtml}</div>
  `;
  row.querySelector('.repeat-icon-btn').addEventListener('click', () => {
    row.remove();
    renderResumePreview();
  });
  row.addEventListener('input', () => {
    const vals = {};
    row.querySelectorAll('[data-key]').forEach(el => { vals[el.dataset.key] = el.value; });
    row.querySelector('.repeat-row-title').textContent = REPEAT_TITLES[kind](vals);
  });
  container.appendChild(row);
}

function collectRepeatRows(containerId) {
  const container = document.getElementById(containerId);
  return Array.from(container.querySelectorAll('.repeat-row')).map(row => {
    const obj = {};
    row.querySelectorAll('[data-key]').forEach(el => { obj[el.dataset.key] = el.value; });
    return obj;
  });
}

function collectResumeData() {
  return {
    full_name: document.getElementById('r-name').value.trim(),
    headline: document.getElementById('r-headline').value.trim(),
    email: document.getElementById('r-email').value.trim(),
    phone: document.getElementById('r-phone').value.trim(),
    location: document.getElementById('r-location').value.trim(),
    summary: document.getElementById('r-summary').value.trim(),
    skills: document.getElementById('r-skills').value.trim(),
    experience: collectRepeatRows('experience-list'),
    education: collectRepeatRows('education-list'),
    languages: collectRepeatRows('language-list'),
    links: collectRepeatRows('link-list'),
    achievements: collectRepeatRows('achievement-list'),
    canvas_layout: currentCanvasLayout,
    images: currentCanvasImages,
    canvas_effect: document.getElementById('canvas-effect').value,
    avatar_url: currentAvatarUrl,
    frozen_from: frozenFromTemplate || '',
    canvas_skin: frozenSkin || null,
  };
}

function fillField(id, value, force) {
  const el = document.getElementById(id);
  if (!el || !value) return;
  if (force || !el.value.trim()) el.value = value;
}

function syncProfileIntoResume(p, force) {
  if (!p) return;
  const name = [p.first_name, p.last_name].filter(Boolean).join(' ').trim();
  fillField('r-name', name, force);
  fillField('r-headline', p.headline, force);
  fillField('r-email', p.email, force);
  fillField('r-phone', p.phone, force);
  fillField('r-location', p.location, force);
  if (typeof renderResumePreview === 'function') renderResumePreview();
}

function applyImportedResume(data) {
  if (!data) return;
  fillField('r-name', data.full_name, true);
  fillField('r-headline', data.headline, true);
  fillField('r-email', data.email, true);
  fillField('r-phone', data.phone, true);
  fillField('r-location', data.location, true);
  fillField('r-summary', data.summary, true);
  fillField('r-skills', data.skills, true);
  if ((data.experience || []).length) {
    document.getElementById('experience-list').innerHTML = '';
    data.experience.forEach(v => addRepeatRow('experience-list', 'experience', v));
  }
  if ((data.education || []).length) {
    document.getElementById('education-list').innerHTML = '';
    data.education.forEach(v => addRepeatRow('education-list', 'education', v));
  }
  if ((data.languages || []).length) {
    document.getElementById('language-list').innerHTML = '';
    data.languages.forEach(v => addRepeatRow('language-list', 'languages', v));
  }
  if ((data.links || []).length) {
    document.getElementById('link-list').innerHTML = '';
    data.links.forEach(v => addRepeatRow('link-list', 'links', v));
  }
  renderResumePreview();
}

async function importResumeFromLogin(source, creds, options) {
  const applyToBuilder = !options || options.applyToBuilder !== false;
  const resp = await fetch('/api/resume/import', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, ...(creds || {}) }),
  });
  const result = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(result.error || 'Не удалось импортировать резюме');
  if (applyToBuilder) applyImportedResume(result.resume);
  if (result.profile) {
    const setVal = (id, val) => { const el = document.getElementById(id); if (el && val) el.value = val; };
    setVal('profile-first-name', result.profile.first_name);
    setVal('profile-last-name', result.profile.last_name);
    setVal('profile-phone', result.profile.phone);
    setVal('profile-location', result.profile.location);
    if (result.profile.headline) applyRegions('profile-headline-chips', 'profile-headline-extra', result.profile.headline);
    applyBoardStatus(result.profile);
    syncProfileIntoResume(result.profile, false);
  }
  return result;
}

const BOARD_LABELS = { djinni: 'djinni.co', workua: 'work.ua', rabota: 'robota.ua' };
const boardResumeCache = { djinni: [], workua: [], rabota: [] };

function splitSkills(raw) {
  return String(raw || '').split(/[,;/|]+/).map(s => s.trim()).filter(Boolean).slice(0, 12);
}

function boardCvHtml(source, cv, idx) {
  const title = escapeHtml(cv.headline || cv.full_name || 'Резюме');
  const meta = [cv.full_name, cv.location].filter(Boolean).map(escapeHtml).join(' · ');
  const skills = splitSkills(cv.skills).map(s => `<span class="skill-pill">${escapeHtml(s)}</span>`).join('');
  const summary = cv.summary ? `<p class="board-cv-summary">${escapeHtml(cv.summary)}</p>` : '';
  const expItems = (cv.experience || []).map(row => {
    const role = escapeHtml(row.position || row.company || 'Опыт');
    const company = [row.company, row.period].filter(Boolean).map(escapeHtml).join(' · ');
    const desc = row.description ? `<p class="board-cv-desc">${escapeHtml(row.description)}</p>` : '';
    return `<li><div class="board-cv-role">${role}</div>${company ? `<div class="board-cv-company">${company}</div>` : ''}${desc}</li>`;
  }).join('');
  const details = (summary || expItems)
    ? `<details><summary>Подробнее</summary>${summary}${expItems ? `<ul class="board-cv-exp">${expItems}</ul>` : ''}</details>`
    : '';
  const url = cv.source_url ? `<a href="${escapeHtml(cv.source_url)}" target="_blank" rel="noopener noreferrer">На ${escapeHtml(BOARD_LABELS[source] || source)}</a>` : '';
  return `<article class="board-cv">
    <div class="board-cv-head"><h3 class="board-cv-title">${title}</h3></div>
    ${meta ? `<p class="board-cv-meta">${meta}</p>` : ''}
    ${skills ? `<div class="skill-cloud">${skills}</div>` : ''}
    ${details}
    <div class="board-cv-actions">
      ${url}
      <button type="button" class="ghost" data-apply-board-cv="${idx}">В конструктор</button>
    </div>
  </article>`;
}

function renderBoardResumes(source, resumes, connected, loaded) {
  const box = document.getElementById('board-resumes-' + source);
  if (!box) return;
  const items = Array.isArray(resumes) ? resumes : [];
  boardResumeCache[source] = items;
  if (!items.length) {
    if (connected && loaded) {
      box.hidden = false;
      box.innerHTML = '<p class="empty">В кабинете нет опубликованного резюме</p>';
    } else if (connected) {
      box.hidden = false;
      box.innerHTML = '<p class="empty">Нажмите «Обновить», чтобы показать резюме из кабинета</p>';
    } else {
      box.hidden = true;
      box.innerHTML = '';
    }
    return;
  }
  box.hidden = false;
  box.innerHTML = items.map((cv, i) => boardCvHtml(source, cv, i)).join('');
}

function applyBoardCvToBuilder(source, idx) {
  const cv = (boardResumeCache[source] || [])[idx];
  if (!cv) return;
  applyImportedResume(cv);
  document.querySelector('.nav-item[data-tab="cvs"]')?.click();
  document.querySelector('.subtab-item[data-subtab="builder"]')?.click();
  showToast('Резюме открыто в конструкторе');
}

function applyBoardStatus(profile) {
  const boards = profile?.boards || {};
  ['djinni', 'workua', 'rabota'].forEach(src => {
    const info = boards[src] || {};
    const status = document.getElementById('board-status-' + src);
    if (status) {
      const count = info.resume_count || (info.resumes || []).length;
      status.textContent = info.connected
        ? ('подключено' + (info.email_masked ? ' · ' + info.email_masked : '') + (count ? ' · ' + count + ' резюме' : ''))
        : 'не подключено';
      status.classList.toggle('set', !!info.connected);
      status.classList.toggle('unset', !info.connected);
    }
    const emailEl = document.getElementById('board-email-' + src);
    if (emailEl && info.email && !emailEl.value) emailEl.value = info.email;
    const passEl = document.getElementById('board-password-' + src);
    if (passEl && info.connected) passEl.placeholder = 'сохранён — введите, чтобы заменить';
    const connectBtn = document.querySelector('[data-connect-board="' + src + '"]');
    if (connectBtn) connectBtn.textContent = info.connected ? 'Обновить' : 'Войти и показать';
    renderBoardResumes(src, info.resumes, !!info.connected, !!info.resumes_loaded);
  });
}

function boardIsConnected(profile, source) {
  return !!(profile?.boards?.[source]?.connected);
}

function openModal(id) {
  document.getElementById(id)?.classList.add('is-open');
}
function closeModal(id) {
  document.getElementById(id)?.classList.remove('is-open');
}

async function dismissGate(which, modalId) {
  await fetch('/api/prompts/later', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ which }),
  }).catch(() => {});
  closeModal(modalId);
  if (which === 'profile') maybeShowImportGate({ prompt_import_later: false });
}

function maybeShowProfileGate(profile) {
  if (!profile || profile.profile_complete || profile.prompt_profile_later) {
    maybeShowImportGate(profile);
    return;
  }
  const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  setVal('gate-first-name', profile.first_name);
  setVal('gate-last-name', profile.last_name);
  setVal('gate-phone', profile.phone);
  setVal('gate-location', profile.location);
  setVal('gate-headline', profile.headline);
  setVal('gate-email', profile.email);
  openModal('modal-profile-gate');
}

function maybeShowImportGate(profile) {
  if (!profile || profile.prompt_import_later) return;
  const boards = profile.boards || {};
  const connected = ['djinni', 'workua', 'rabota'].some(src => boards[src]?.connected);
  const hasUrl = profile.resume_url_djinni || profile.resume_url_workua || profile.resume_url_rabota;
  if (connected || hasUrl) return;
  openModal('modal-import-gate');
}

document.getElementById('btn-gate-profile-save')?.addEventListener('click', async () => {
  const statusEl = document.getElementById('gate-profile-status');
  if (statusEl) statusEl.textContent = 'Сохраняю…';
  try {
    const resp = await fetch('/api/profile', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        first_name: document.getElementById('gate-first-name').value,
        last_name: document.getElementById('gate-last-name').value,
        email: document.getElementById('gate-email').value,
        phone: document.getElementById('gate-phone').value,
        location: document.getElementById('gate-location').value,
        headline: document.getElementById('gate-headline').value,
      }),
    });
    const result = await resp.json();
    if (!resp.ok) {
      if (statusEl) statusEl.textContent = result.error || 'Ошибка';
      return;
    }
    syncProfileIntoResume(result, true);
    await loadProfile();
    closeModal('modal-profile-gate');
    showToast('Данные сохранены и подставлены в резюме');
    maybeShowImportGate(result);
  } catch (e) {
    if (statusEl) statusEl.textContent = 'Сеть: ' + e;
  }
});
document.getElementById('btn-gate-profile-later')?.addEventListener('click', () => dismissGate('profile', 'modal-profile-gate'));
document.getElementById('btn-gate-import-later')?.addEventListener('click', () => dismissGate('import', 'modal-import-gate'));
document.getElementById('btn-gate-import-go')?.addEventListener('click', async () => {
  const source = document.getElementById('gate-import-source')?.value || 'djinni';
  const email = (document.getElementById('gate-import-email')?.value || '').trim();
  const password = document.getElementById('gate-import-password')?.value || '';
  const statusEl = document.getElementById('gate-import-status');
  if (!email || !password) {
    if (statusEl) statusEl.textContent = 'Введите email и пароль вашего аккаунта на площадке';
    return;
  }
  if (statusEl) statusEl.textContent = 'Вхожу и ищу резюме…';
  try {
    await importResumeFromLogin(source, { email, password });
    closeModal('modal-import-gate');
    showToast('Резюме подтянуто с ' + BOARD_LABELS[source]);
    document.querySelector('.nav-item[data-tab="cvs"]')?.click();
    document.querySelector('.subtab-item[data-subtab="builder"]')?.click();
  } catch (e) {
    if (statusEl) statusEl.textContent = e.message || String(e);
  }
});
document.querySelectorAll('[data-connect-board]').forEach(btn => {
  btn.addEventListener('click', () => connectBoard(btn.getAttribute('data-connect-board')));
});
document.querySelectorAll('[data-disconnect-board]').forEach(btn => {
  btn.addEventListener('click', () => disconnectBoard(btn.getAttribute('data-disconnect-board')));
});
document.querySelectorAll('.board-resumes').forEach(box => {
  box.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-apply-board-cv]');
    if (!btn) return;
    const source = box.id.replace('board-resumes-', '');
    applyBoardCvToBuilder(source, Number(btn.getAttribute('data-apply-board-cv')));
  });
});
document.getElementById('btn-import-resume-builder')?.addEventListener('click', runResumeImport);

async function connectBoard(source) {
  const statusEl = document.getElementById('import-resume-status');
  const email = (document.getElementById('board-email-' + source)?.value || '').trim();
  const password = document.getElementById('board-password-' + source)?.value || '';
  if (statusEl) statusEl.textContent = 'Вхожу в кабинет и загружаю резюме…';
  try {
    const result = await importResumeFromLogin(source, { email, password }, { applyToBuilder: false });
    const passEl = document.getElementById('board-password-' + source);
    if (passEl) passEl.value = '';
    const n = (result.resumes || []).length;
    if (statusEl) statusEl.textContent = n ? ('Показано: ' + n) : 'Готово';
    showToast(n
      ? ('На ' + BOARD_LABELS[source] + ': ' + n + ' резюме')
      : ('Кабинет ' + BOARD_LABELS[source] + ' открыт'));
  } catch (e) {
    if (statusEl) statusEl.textContent = e.message || String(e);
    showToast(e.message || 'Не удалось подключить площадку', true);
  }
}

async function disconnectBoard(source) {
  const statusEl = document.getElementById('import-resume-status');
  try {
    const resp = await fetch('/api/resume/boards/' + source, { method: 'DELETE' });
    const result = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(result.error || 'Не удалось отключить');
    applyBoardStatus(result.profile);
    const passEl = document.getElementById('board-password-' + source);
    if (passEl) { passEl.value = ''; passEl.placeholder = 'пароль площадки'; }
    if (statusEl) statusEl.textContent = 'Отключено';
    showToast(BOARD_LABELS[source] + ' отключён');
  } catch (e) {
    if (statusEl) statusEl.textContent = e.message || String(e);
    showToast(e.message || 'Не удалось отключить', true);
  }
}

async function runResumeImport() {
  const source = document.getElementById('import-resume-source')?.value || 'djinni';
  const statusEl = document.getElementById('import-resume-status');
  const email = (document.getElementById('board-email-' + source)?.value || '').trim();
  const password = document.getElementById('board-password-' + source)?.value || '';
  if (statusEl) statusEl.textContent = 'Ищу резюме в кабинете…';
  try {
    await importResumeFromLogin(source, { email, password });
    if (statusEl) statusEl.textContent = 'Готово';
    showToast('Резюме подтянуто с ' + BOARD_LABELS[source]);
  } catch (e) {
    if (statusEl) statusEl.textContent = e.message || String(e);
    showToast(e.message || 'Не удалось импортировать', true);
  }
}

function getSelectedTemplate() {
  if (comboTemplate) return comboTemplate;
  const checked = document.querySelector('input[name=tpl]:checked');
  return checked ? checked.value : 'classic';
}

let comboTemplate = null;

function updateComboBanner() {
  const banner = document.getElementById('combo-tpl-banner');
  if (!banner) return;
  if (!comboTemplate) { banner.style.display = 'none'; return; }
  const [sid, tid] = comboTemplate.split('__');
  const s = TEMPLATE_STRUCTURES.find(x => x.id === sid);
  const t = TEMPLATE_THEMES.find(x => x.id === tid);
  document.getElementById('combo-tpl-banner-text').textContent = `Шаблон из галереи: ${s ? s.name : sid} · ${t ? t.name : tid}`;
  banner.style.display = 'flex';
}

const A4_WIDTH_PX = 210 * 96 / 25.4; // ≈793.7px — реальная ширина A4 в CSS-пикселях
let resumeZoom = 0.72;

function computeFitZoom() {
  const frame = document.getElementById('resume-preview');
  const available = frame.clientWidth - 40; // минус паддинг рамки
  if (available <= 0) return resumeZoom; // панель ещё не отрисована/скрыта — не делить на пусто
  return Math.max(0.3, Math.min(1, available / A4_WIDTH_PX));
}

function applyResumeZoom() {
  resumeZoom = computeFitZoom();
  const page = document.querySelector('#resume-preview .resume-page, #resume-preview .resume-canvas-page');
  if (page) page.style.zoom = resumeZoom;
  document.getElementById('zoom-label').textContent = 'По ширине · ' + Math.round(resumeZoom * 100) + '%';
}

window.addEventListener('resize', () => {
  if (document.getElementById('subtab-builder')?.classList.contains('active')) applyResumeZoom();
});

new ResizeObserver(() => {
  if (document.getElementById('subtab-builder')?.classList.contains('active')) applyResumeZoom();
}).observe(document.getElementById('resume-preview'));

// ---- «Разрешить перетаскивание»: любой готовый шаблон можно превратить в свободный холст,
// сохранив его цвета/шрифт — измеряем, где сейчас на экране стоит каждый [data-piece], и
// превращаем эти координаты в canvas_layout. Дальше — та же самая логика драга/ресайза,
// что и у пустого «Свободного холста» (getBlockRef/otherBlockRects работают по ключу
// в currentCanvasLayout, им всё равно, что это за кусок шаблона). ----

function freezeCurrentTemplateToCanvas() {
  const template = getSelectedTemplate();
  if (template === 'custom') return;
  const pageEl = document.querySelector('#resume-preview .resume-page');
  if (!pageEl) { showToast('Не удалось включить перетаскивание', true); return; }

  const pieces = pageEl.querySelectorAll('[data-piece]');
  if (!pieces.length) { showToast('В этом шаблоне нечего перетаскивать', true); return; }

  const pageRect = pageEl.getBoundingClientRect();
  const layout = {};
  pieces.forEach(el => {
    const r = el.getBoundingClientRect();
    layout[el.dataset.piece] = {
      x: Math.max(0, Math.round((r.left - pageRect.left) / resumeZoom)),
      y: Math.max(0, Math.round((r.top - pageRect.top) / resumeZoom)),
      w: Math.max(20, Math.round(r.width / resumeZoom)),
      h: Math.max(20, Math.round(r.height / resumeZoom)),
    };
  });

  const rootClass = Array.from(pageEl.classList).filter(c => c !== 'resume-page').join(' ');
  const styleVars = (pageEl.getAttribute('style') || '').replace(/zoom\s*:[^;]*;?/gi, '').trim();

  frozenFromTemplate = template;
  frozenSkin = { rootClass, styleVars };
  currentCanvasLayout = layout;

  comboTemplate = null;
  const customRadio = document.querySelector('input[name=tpl][value=custom]');
  if (customRadio) customRadio.checked = true;
  document.querySelectorAll('.tpl-card').forEach(o => o.classList.toggle('active', o.dataset.tpl === 'custom'));
  document.getElementById('canvas-tools').style.display = 'flex';
  updateComboBanner();

  renderResumePreview();
  showToast('Теперь можно перетаскивать блоки — цвета и шрифт шаблона сохранены');
}

document.getElementById('btn-unlock-drag')?.addEventListener('click', freezeCurrentTemplateToCanvas);

function renderResumePreview() {
  const data = collectResumeData();
  const template = getSelectedTemplate();
  const frame = document.getElementById('resume-preview');
  if (template === 'custom') {
    frame.innerHTML = renderResumeCanvasHTML(data, currentCanvasLayout, true, frozenFromTemplate, frozenSkin);
    wireCanvasInteractions();
  } else {
    frame.innerHTML = renderResumeHTML(data, template);
  }
  const unlockBtn = document.getElementById('btn-unlock-drag');
  if (unlockBtn) unlockBtn.style.display = template === 'custom' ? 'none' : 'inline-flex';
  applyResumeZoom();
}

// ---- Свободный холст: перетаскивание и ресайз блоков (текстовых и фото) мышью ----

function getBlockRef(block) {
  if (block.dataset.block === 'image') {
    return currentCanvasImages.find(img => img.id === block.dataset.imageId);
  }
  return currentCanvasLayout[block.dataset.block];
}

// ---- Умное размещение: привязка к краям и центрам соседних блоков при перетаскивании ----

const SNAP_THRESHOLD = 6;
let snapGuideXEl = null, snapGuideYEl = null;

function otherBlockRects(excludeBlock) {
  const isImage = excludeBlock.dataset.block === 'image';
  const rects = [];
  Object.keys(currentCanvasLayout).forEach(key => {
    if (!isImage && key === excludeBlock.dataset.block) return;
    const r = currentCanvasLayout[key];
    if (r) rects.push(r);
  });
  currentCanvasImages.forEach(img => {
    if (isImage && img.id === excludeBlock.dataset.imageId) return;
    rects.push(img);
  });
  return rects;
}

function applySnap(x, y, w, h, others) {
  const targetsX = [0, CANVAS_PAGE_WIDTH, (CANVAS_PAGE_WIDTH - w) / 2];
  const targetsY = [0];
  others.forEach(r => {
    targetsX.push(r.x, r.x + r.w, r.x + r.w / 2 - w / 2);
    targetsY.push(r.y, r.y + r.h);
  });

  let sx = x, sy = y, guideX = null, guideY = null;
  for (const t of targetsX) {
    if (Math.abs(x - t) < SNAP_THRESHOLD) { sx = t; guideX = t; break; }
    if (Math.abs((x + w) - t) < SNAP_THRESHOLD) { sx = t - w; guideX = t; break; }
  }
  for (const t of targetsY) {
    if (Math.abs(y - t) < SNAP_THRESHOLD) { sy = t; guideY = t; break; }
    if (Math.abs((y + h) - t) < SNAP_THRESHOLD) { sy = t - h; guideY = t; break; }
  }
  return { x: Math.max(0, sx), y: Math.max(0, sy), guideX, guideY };
}

function ensureSnapGuides(pageEl) {
  if (!snapGuideXEl) {
    snapGuideXEl = document.createElement('div');
    snapGuideXEl.className = 'canvas-snap-guide vertical';
    pageEl.appendChild(snapGuideXEl);
  }
  if (!snapGuideYEl) {
    snapGuideYEl = document.createElement('div');
    snapGuideYEl.className = 'canvas-snap-guide horizontal';
    pageEl.appendChild(snapGuideYEl);
  }
}
function updateSnapGuides(guideX, guideY) {
  snapGuideXEl.style.display = guideX === null ? 'none' : 'block';
  if (guideX !== null) snapGuideXEl.style.left = guideX + 'px';
  snapGuideYEl.style.display = guideY === null ? 'none' : 'block';
  if (guideY !== null) snapGuideYEl.style.top = guideY + 'px';
}
function clearSnapGuides() {
  if (snapGuideXEl) snapGuideXEl.remove();
  if (snapGuideYEl) snapGuideYEl.remove();
  snapGuideXEl = null; snapGuideYEl = null;
}

function wireCanvasInteractions() {
  const pageEl = document.querySelector('#resume-preview .resume-canvas-page');
  if (!pageEl) return;
  pageEl.querySelectorAll('.canvas-block.editable').forEach(block => {
    block.addEventListener('mousedown', (e) => {
      if (e.target.closest('.canvas-resize-handle') || e.target.closest('.canvas-image-remove') || e.target.closest('.canvas-shape-recolor')) return;
      e.preventDefault();
      startCanvasDrag(block, e);
    });
    const handle = block.querySelector('.canvas-resize-handle');
    if (handle) {
      handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        e.stopPropagation();
        startCanvasResize(block, e);
      });
    }
  });
  pageEl.querySelectorAll('.canvas-image-remove').forEach(btn => {
    btn.addEventListener('mousedown', (e) => e.stopPropagation());
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      currentCanvasImages = currentCanvasImages.filter(img => img.id !== btn.dataset.imgId);
      renderResumePreview();
    });
  });
  pageEl.querySelectorAll('.canvas-shape-recolor').forEach(input => {
    input.addEventListener('mousedown', (e) => e.stopPropagation());
    input.addEventListener('click', (e) => e.stopPropagation());
    input.addEventListener('change', () => {
      const img = currentCanvasImages.find(i => i.id === input.dataset.imgId);
      if (!img) return;
      img.color = input.value;
      img.url = shapeDataUri(img.shapeKey, img.color);
      renderResumePreview();
    });
  });
}

function startCanvasDrag(block, e) {
  const ref = getBlockRef(block);
  if (!ref) return;
  const startX = e.clientX, startY = e.clientY;
  const orig = { ...ref };
  const others = otherBlockRects(block);
  const pageEl = block.closest('.resume-canvas-page');
  ensureSnapGuides(pageEl);
  block.classList.add('dragging');

  function onMove(ev) {
    const dx = (ev.clientX - startX) / resumeZoom;
    const dy = (ev.clientY - startY) / resumeZoom;
    const rawX = Math.max(0, Math.min(CANVAS_PAGE_WIDTH - orig.w, orig.x + dx));
    const rawY = Math.max(0, orig.y + dy);
    const snapped = ev.altKey ? { x: rawX, y: rawY, guideX: null, guideY: null } : applySnap(rawX, rawY, orig.w, orig.h, others);
    ref.x = snapped.x;
    ref.y = snapped.y;
    block.style.left = ref.x + 'px';
    block.style.top = ref.y + 'px';
    updateSnapGuides(snapped.guideX, snapped.guideY);
  }
  function onUp() {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    block.classList.remove('dragging');
    clearSnapGuides();
  }
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

function startCanvasResize(block, e) {
  const ref = getBlockRef(block);
  if (!ref) return;
  const startX = e.clientX, startY = e.clientY;
  const orig = { ...ref };
  block.classList.add('dragging');

  function onMove(ev) {
    const dx = (ev.clientX - startX) / resumeZoom;
    const dy = (ev.clientY - startY) / resumeZoom;
    ref.w = Math.max(40, Math.min(CANVAS_PAGE_WIDTH - orig.x, orig.w + dx));
    ref.h = Math.max(40, orig.h + dy);
    block.style.width = ref.w + 'px';
    block.style.height = ref.h + 'px';
  }
  function onUp() {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    block.classList.remove('dragging');
  }
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
}

document.getElementById('add-experience').addEventListener('click', () => { addRepeatRow('experience-list', 'experience'); renderResumePreview(); });
document.getElementById('add-education').addEventListener('click', () => { addRepeatRow('education-list', 'education'); renderResumePreview(); });
document.getElementById('add-language').addEventListener('click', () => { addRepeatRow('language-list', 'languages'); renderResumePreview(); });
document.getElementById('add-link').addEventListener('click', () => { addRepeatRow('link-list', 'links'); renderResumePreview(); });
document.getElementById('add-achievement').addEventListener('click', () => { addRepeatRow('achievement-list', 'achievements'); renderResumePreview(); });

let _resumePreviewDebounceTimer = null;
document.getElementById('subtab-builder').addEventListener('input', () => {
  clearTimeout(_resumePreviewDebounceTimer);
  _resumePreviewDebounceTimer = setTimeout(renderResumePreview, 150);
});

document.querySelectorAll('#template-picker input[name=tpl]').forEach(r => {
  r.addEventListener('change', () => {
    comboTemplate = null;
    updateComboBanner();
    document.querySelectorAll('.tpl-card').forEach(o => o.classList.toggle('active', o.querySelector('input').checked));
    document.getElementById('canvas-tools').style.display = getSelectedTemplate() === 'custom' ? 'flex' : 'none';
    renderResumePreview();
  });
});

document.getElementById('btn-combo-tpl-reset')?.addEventListener('click', () => {
  comboTemplate = null;
  updateComboBanner();
  document.querySelector('input[name=tpl][value=classic]').checked = true;
  document.querySelectorAll('.tpl-card').forEach(o => o.classList.toggle('active', o.dataset.tpl === 'classic'));
  renderResumePreview();
});

function resetBuilderForm() {
  currentResumeId = null;
  comboTemplate = null;
  updateComboBanner();
  currentCanvasLayout = JSON.parse(JSON.stringify(DEFAULT_CANVAS_LAYOUT));
  currentCanvasImages = [];
  currentAvatarUrl = '';
  frozenFromTemplate = null;
  frozenSkin = null;
  updateAvatarPreview();
  document.getElementById('r-name').value = '';
  document.getElementById('r-headline').value = '';
  document.getElementById('r-email').value = '';
  document.getElementById('r-phone').value = '';
  document.getElementById('r-location').value = '';
  document.getElementById('r-summary').value = '';
  document.getElementById('r-skills').value = '';
  document.getElementById('canvas-effect').value = 'none';
  document.getElementById('ai-job-description').value = '';
  ['experience-list', 'education-list', 'language-list', 'link-list', 'achievement-list'].forEach(id => {
    document.getElementById(id).innerHTML = '';
  });
  document.querySelector('input[name=tpl][value=classic]').checked = true;
  document.querySelectorAll('.tpl-card').forEach(o => o.classList.toggle('active', o.dataset.tpl === 'classic'));
  document.getElementById('canvas-tools').style.display = 'none';
  document.getElementById('resume-save-status').textContent = '';
  addRepeatRow('experience-list', 'experience');
  addRepeatRow('education-list', 'education');
  addRepeatRow('language-list', 'languages');
  addRepeatRow('link-list', 'links');
  renderResumePreview();
}

async function loadResumeIntoForm(id) {
  const resp = await fetch(`/api/resumes/${id}`);
  if (!resp.ok) { showToast('Не удалось загрузить резюме', true); return; }
  const r = await resp.json();
  const data = r.data;
  currentResumeId = r.id;
  currentCanvasLayout = data.canvas_layout
    ? JSON.parse(JSON.stringify(data.canvas_layout))
    : JSON.parse(JSON.stringify(DEFAULT_CANVAS_LAYOUT));
  currentCanvasImages = data.images ? JSON.parse(JSON.stringify(data.images)) : [];
  currentAvatarUrl = data.avatar_url || '';
  frozenFromTemplate = data.frozen_from || null;
  frozenSkin = data.canvas_skin || null;
  updateAvatarPreview();

  document.getElementById('r-name').value = data.full_name || '';
  document.getElementById('r-headline').value = data.headline || '';
  document.getElementById('r-email').value = data.email || '';
  document.getElementById('r-phone').value = data.phone || '';
  document.getElementById('r-location').value = data.location || '';
  document.getElementById('r-summary').value = data.summary || '';
  document.getElementById('r-skills').value = data.skills || '';
  document.getElementById('canvas-effect').value = data.canvas_effect || 'none';
  document.getElementById('canvas-tools').style.display = r.template === 'custom' ? 'flex' : 'none';

  ['experience-list', 'education-list', 'language-list', 'link-list', 'achievement-list'].forEach(id => {
    document.getElementById(id).innerHTML = '';
  });
  (data.experience || []).forEach(v => addRepeatRow('experience-list', 'experience', v));
  (data.education || []).forEach(v => addRepeatRow('education-list', 'education', v));
  (data.languages || []).forEach(v => addRepeatRow('language-list', 'languages', v));
  (data.links || []).forEach(v => addRepeatRow('link-list', 'links', v));
  (data.achievements || []).forEach(v => addRepeatRow('achievement-list', 'achievements', v));

  if (r.template && r.template.includes('__')) {
    comboTemplate = r.template;
    document.querySelectorAll('input[name=tpl]').forEach(el => { el.checked = false; });
    document.querySelectorAll('.tpl-card').forEach(o => o.classList.remove('active'));
  } else {
    comboTemplate = null;
    document.querySelectorAll('input[name=tpl]').forEach(el => { el.checked = el.value === r.template; });
    document.querySelectorAll('.tpl-card').forEach(o => o.classList.toggle('active', o.dataset.tpl === r.template));
  }
  updateComboBanner();

  document.getElementById('resume-save-status').textContent = 'Открыто для редактирования';
  renderResumePreview();
}

async function saveResume() {
  const data = collectResumeData();
  const template = getSelectedTemplate();
  const statusEl = document.getElementById('resume-save-status');
  try {
    const resp = await fetch('/api/resumes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: currentResumeId, template, data }),
    });
    const result = await resp.json();
    if (!resp.ok) {
      statusEl.textContent = result.error || 'Ошибка сохранения';
      showToast(result.error || 'Ошибка сохранения', true);
      return null;
    }
    currentResumeId = result.id;
    statusEl.textContent = `Сохранено: ${result.title}`;
    showToast('Резюме сохранено');
    loadCvs();
    loadResumeList();
    return result.id;
  } catch (e) {
    statusEl.textContent = 'Ошибка сети: ' + e;
    return null;
  }
}

document.getElementById('btn-save-resume').addEventListener('click', saveResume);
document.getElementById('btn-new-resume').addEventListener('click', resetBuilderForm);
document.getElementById('btn-download-resume').addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  btn.disabled = true;
  try {
    const id = await saveResume();
    if (id) window.open(`/resume/${id}/print`, '_blank');
  } finally {
    btn.disabled = false;
  }
});

async function loadResumeList() {
  const resp = await fetch('/api/cvs');
  const cvs = await resp.json();
  const resumes = cvs.filter(c => c.format === 'builder');
  const listEl = document.getElementById('resume-list');
  const emptyEl = document.getElementById('resume-list-empty');

  if (resumes.length === 0) {
    listEl.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';
  listEl.innerHTML = resumes.map(cv => `
    <div class="cv-row">
      <div class="cv-icon">CV</div>
      <div class="cv-info">
        <div class="cv-name">${escapeHtml(cv.original_name)}</div>
        <div class="cv-meta">${cv.text_len} симв. текста</div>
      </div>
      <div class="cv-row-actions">
        <button class="ghost" data-edit-id="${cv.id}">Редактировать</button>
        <button class="ghost" data-pdf-id="${cv.id}">Скачать PDF</button>
        <button class="danger-ghost" data-id="${cv.id}">Удалить</button>
      </div>
    </div>
  `).join('');
  listEl.querySelectorAll('[data-edit-id]').forEach(b => {
    b.addEventListener('click', () => loadResumeIntoForm(b.dataset.editId));
  });
  listEl.querySelectorAll('[data-pdf-id]').forEach(b => {
    b.addEventListener('click', () => window.open(`/resume/${b.dataset.pdfId}/print`, '_blank'));
  });
  listEl.querySelectorAll('.danger-ghost').forEach(b => {
    b.addEventListener('click', async () => {
      await fetch(`/api/resumes/${b.dataset.id}`, { method: 'DELETE' });
      showToast('Резюме удалено');
      loadCvs();
      loadResumeList();
    });
  });
}

// ---------- ИИ: улучшение формулировок в конструкторе резюме ----------

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.ai-improve-btn');
  if (!btn) return;
  const targetEl = document.getElementById(btn.dataset.target);
  if (!targetEl || !targetEl.value.trim()) { showToast('Сначала напишите хоть немного текста', true); return; }

  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Улучшаю…';
  try {
    const resp = await fetch('/api/ai/improve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: targetEl.value, context: btn.dataset.context }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showToast(data.error || 'Ошибка ИИ', true);
    } else {
      targetEl.value = data.text;
      targetEl.dispatchEvent(new Event('input', { bubbles: true }));
      showToast('Текст улучшен');
    }
  } catch (err) {
    showToast('Ошибка сети: ' + err, true);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.ai-bullets-btn');
  if (!btn) return;
  const targetEl = document.getElementById(btn.dataset.target);
  if (!targetEl) return;
  const row = targetEl.closest('.repeat-row');
  const position = row.querySelector('[data-key=position]')?.value || '';
  const company = row.querySelector('[data-key=company]')?.value || '';
  const note = targetEl.value.trim();
  if (!note) { showToast('Сначала кратко опишите, чем занимались (пара слов)', true); return; }

  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Генерирую…';
  try {
    const resp = await fetch('/api/ai/experience-bullets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position, company, note }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showToast(data.error || 'Ошибка ИИ', true);
    } else {
      targetEl.value = data.text;
      targetEl.dispatchEvent(new Event('input', { bubbles: true }));
      showToast('Буллеты сгенерированы');
    }
  } catch (err) {
    showToast('Ошибка сети: ' + err, true);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

// ---------- Свободный холст: фото и визуальные эффекты ----------

document.getElementById('btn-add-photo').addEventListener('click', () => {
  document.getElementById('canvas-image-input').click();
});

document.getElementById('canvas-image-input').addEventListener('change', async () => {
  const input = document.getElementById('canvas-image-input');
  const file = input.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const resp = await fetch('/api/resumes/images', { method: 'POST', body: fd });
    const data = await resp.json();
    if (!resp.ok) { showToast(data.error || 'Ошибка загрузки фото', true); return; }
    currentCanvasImages.push({ id: data.id, url: data.url, x: 600, y: 20, w: 140, h: 140 });
    renderResumePreview();
    showToast('Фото добавлено — перетащите его в нужное место');
  } catch (e) {
    showToast('Ошибка сети: ' + e, true);
  } finally {
    input.value = '';
  }
});

document.getElementById('canvas-effect').addEventListener('change', renderResumePreview);

// ---------- Свободный холст: графические элементы (фигуры, разделители, акценты) ----------
// Каждая фигура — SVG на currentColor/явном fill, перекодируется в data URI при добавлении
// и при смене цвета. Хранится в том же currentCanvasImages, что и фото (kind:'shape'
// отличает её только для превью-панели и object-fit:contain) — драг/ресайз/удаление
// у них уже полностью общие с фото, отдельная логика взаимодействия не нужна.
const CANVAS_SHAPES = {
  'circle-fill': { label: 'Круг', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="${c}"/></svg>` },
  'circle-ring': { label: 'Кольцо', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="38" fill="none" stroke="${c}" stroke-width="9"/></svg>` },
  'half-circle': { label: 'Полукруг', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><path d="M0 50 A50 50 0 0 1 100 50 Z" fill="${c}"/></svg>` },
  triangle: { label: 'Треугольник', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><polygon points="50,6 96,94 4,94" fill="${c}"/></svg>` },
  diamond: { label: 'Ромб', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><polygon points="50,4 96,50 50,96 4,50" fill="${c}"/></svg>` },
  blob: { label: 'Клякса', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-100 -100 200 200"><path fill="${c}" d="M52.8,-58.9C67.5,-49.5,77.4,-31.9,80.1,-13.2C82.8,5.6,78.3,25.5,67.4,40.8C56.5,56.1,39.2,66.8,20.5,72.1C1.8,77.4,-18.3,77.3,-35.5,69.8C-52.7,62.3,-67,47.4,-73.8,29.6C-80.6,11.8,-79.9,-8.9,-71.8,-25.5C-63.7,-42.1,-48.2,-54.6,-32,-63C-15.8,-71.4,1.1,-75.7,17.9,-73.4C34.7,-71.1,52.8,-58.9,52.8,-58.9Z"/></svg>` },
  ribbon: { label: 'Лента', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60"><rect x="0" y="10" width="200" height="40" rx="4" fill="${c}" transform="rotate(-4 100 30)"/></svg>` },
  'divider-solid': { label: 'Линия', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 12"><rect x="0" y="4" width="200" height="4" rx="2" fill="${c}"/></svg>` },
  'divider-dash': { label: 'Пунктир', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 12"><line x1="2" y1="6" x2="198" y2="6" stroke="${c}" stroke-width="4" stroke-linecap="round" stroke-dasharray="14 10"/></svg>` },
  'divider-wave': { label: 'Волна', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 24"><path d="M0 12 Q 12.5 0 25 12 T 50 12 T 75 12 T 100 12 T 125 12 T 150 12 T 175 12 T 200 12" fill="none" stroke="${c}" stroke-width="4" stroke-linecap="round"/></svg>` },
  corner: { label: 'Уголок', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M0 0 H100 V16 H16 V100 H0 Z" fill="${c}"/></svg>` },
  'dot-grid': { label: 'Точки', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">${[0,1,2,3].flatMap(r => [0,1,2,3].map(col => `<circle cx="${12+col*26}" cy="${12+r*26}" r="4" fill="${c}"/>`)).join('')}</svg>` },
  star: { label: 'Звезда', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path fill="${c}" d="M50 4l12.9 32.4L98 40l-26 22.7L79.4 98 50 78.6 20.6 98 28 62.7 2 40l35.1-3.6z"/></svg>` },
  spark: { label: 'Искра', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path fill="${c}" d="M50 2l10 34 34 10-34 10-10 34-10-34-34-10 34-10z"/></svg>` },
  'check-badge': { label: 'Галочка', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46" fill="${c}"/><path d="M30 52l14 14 26-30" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></svg>` },
  arrow: { label: 'Стрелка', svg: c => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60"><path d="M4 30 H80 M60 12 L80 30 L60 48" fill="none" stroke="${c}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></svg>` },
};

function shapeDataUri(shapeKey, color) {
  const shape = CANVAS_SHAPES[shapeKey];
  if (!shape) return '';
  return 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(shape.svg(color))));
}

const shapePickerBtn = document.getElementById('btn-add-shape');
const shapePickerPopover = document.getElementById('shape-picker-popover');

if (shapePickerBtn && shapePickerPopover) {
  shapePickerPopover.innerHTML = Object.keys(CANVAS_SHAPES).map(key => `
    <button type="button" class="shape-swatch" data-shape="${key}" title="${escapeHtml(CANVAS_SHAPES[key].label)}">
      ${CANVAS_SHAPES[key].svg('currentColor')}
    </button>
  `).join('');

  shapePickerBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    shapePickerPopover.hidden = !shapePickerPopover.hidden;
  });
  document.addEventListener('click', (e) => {
    if (!shapePickerPopover.hidden && !e.target.closest('.shape-picker-wrap')) {
      shapePickerPopover.hidden = true;
    }
  });
  shapePickerPopover.addEventListener('click', (e) => {
    const btn = e.target.closest('.shape-swatch');
    if (!btn) return;
    const shapeKey = btn.dataset.shape;
    const color = '#ffb020';
    currentCanvasImages.push({
      id: 'shape_' + Math.random().toString(36).slice(2, 9),
      url: shapeDataUri(shapeKey, color),
      kind: 'shape', shapeKey, color,
      x: 600, y: 20, w: 100, h: 100,
    });
    shapePickerPopover.hidden = true;
    renderResumePreview();
    showToast('Добавлено — перетащите, измените размер или цвет');
  });
}

// ---------- ИИ-ассистент: генерация / подгонка «О себе» под вакансию ----------

document.getElementById('btn-ai-generate-summary').addEventListener('click', async () => {
  const btn = document.getElementById('btn-ai-generate-summary');
  const jobDescription = document.getElementById('ai-job-description').value.trim();
  const resumeData = collectResumeData();

  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Генерирую…';
  try {
    const resp = await fetch('/api/ai/generate-summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_data: resumeData, job_description: jobDescription }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showToast(data.error || 'Ошибка ИИ', true);
      return;
    }
    document.getElementById('r-summary').value = data.summary || '';
    document.getElementById('r-summary').dispatchEvent(new Event('input', { bubbles: true }));
    if (data.skills && data.skills.length) {
      document.getElementById('r-skills').value = data.skills.join(', ');
      document.getElementById('r-skills').dispatchEvent(new Event('input', { bubbles: true }));
    }
    showToast(jobDescription ? 'Резюме подогнано под вакансию' : '«О себе» сгенерировано');
  } catch (e) {
    showToast('Ошибка сети: ' + e, true);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

function auditScoreClass(score) {
  if (score >= 70) return 'good';
  if (score >= 40) return 'mid';
  return 'low';
}

function renderAuditHtml(data) {
  const list = (items, cls) => items && items.length
    ? `<div class="ai-audit-heading">${cls === 'strengths' ? 'Сильные стороны' : cls === 'weaknesses' ? 'Слабые места' : 'Советы'}</div><ul class="ai-audit-list ${cls}">${items.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul>`
    : '';
  return `
    <span class="ai-audit-score ${auditScoreClass(data.score)}">${data.score}/100</span>
    <div class="ai-audit-heading">Чек-лист</div>
    <div class="audit-checklist">${renderChecklistHtml(data.checklist)}</div>
    ${list(data.strengths, 'strengths')}
    ${list(data.weaknesses, 'weaknesses')}
    ${list(data.suggestions, 'suggestions')}
    ${data.market_fit_error ? `<div class="status" style="color:var(--warning);margin-top:8px;">${escapeHtml(data.market_fit_error)}</div>` : ''}
    ${renderMarketFit(data.market_fit)}
  `;
}

function renderRedFlagsHtml(data) {
  const suggestions = (data.suggestions || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');
  return `
    <div class="ai-audit-heading">Чек-лист</div>
    <div class="audit-checklist">${renderChecklistHtml(data.checklist)}</div>
    ${data.overall_note ? `<div class="match-recommendation">${escapeHtml(data.overall_note)}</div>` : ''}
    ${suggestions ? `<div class="ai-audit-heading">Как снять тревогу</div><ul class="match-list study">${suggestions}</ul>` : ''}
  `;
}

function renderTrajectoryHtml(data) {
  const directions = (data.directions || []).map(d => `
    <div class="audit-check-row" style="align-items:flex-start;">
      <span class="audit-check-icon">→</span>
      <div>
        <b>${escapeHtml(d.title || '')}</b>
        <div class="audit-check-note">${escapeHtml(d.rationale || '')}</div>
        ${(d.skills_to_develop || []).length ? `<div class="kw-chips" style="margin-top:6px;">${d.skills_to_develop.map(s => `<span class="kw-chip kw-missing">${escapeHtml(s)}</span>`).join('')}</div>` : ''}
      </div>
    </div>
  `).join('');
  return `
    ${data.summary ? `<div class="match-verdict">${escapeHtml(data.summary)}</div>` : ''}
    <div class="audit-checklist" style="margin-top:8px;">${directions}</div>
  `;
}

document.getElementById('audit-compare-market').addEventListener('change', (e) => {
  document.getElementById('audit-market-hint').style.display = e.target.checked ? 'block' : 'none';
});

function percentileBarHtml(label, pct, insufficient) {
  if (insufficient || pct === null || pct === undefined) {
    return `<div class="market-metric"><div class="market-metric-label">${escapeHtml(label)}</div><div class="market-metric-note">Недостаточно данных для честной оценки</div></div>`;
  }
  return `
    <div class="market-metric">
      <div class="market-metric-label">${escapeHtml(label)}<span class="market-metric-pct">${pct}%</span></div>
      <div class="market-bar"><div class="market-bar-fill" style="width:${pct}%"></div></div>
    </div>`;
}

function renderMarketFit(mf) {
  if (!mf) return '';
  const chips = (skills, cls) => skills && skills.length
    ? `<div class="market-chip-row">${skills.map(s => `<span class="market-chip ${cls}">${escapeHtml(s)}</span>`).join('')}</div>`
    : '<div class="ai-audit-list-empty">—</div>';
  const synthesis = mf.synthesis
    ? `
      <div class="ai-audit-heading">Вывод по рынку</div>
      <div class="audit-check-note">${escapeHtml(mf.synthesis.verdict || '')}</div>
      ${(mf.synthesis.strengths || []).length ? `<ul class="ai-audit-list strengths">${mf.synthesis.strengths.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
      ${(mf.synthesis.gaps || []).length ? `<ul class="ai-audit-list weaknesses">${mf.synthesis.gaps.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
      ${(mf.synthesis.suggestions || []).length ? `<ul class="ai-audit-list suggestions">${mf.synthesis.suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>` : ''}
    `
    : (mf.synthesis_error ? `<div class="status" style="color:var(--danger)">${escapeHtml(mf.synthesis_error)}</div>` : '');
  return `
    <div class="ai-audit-market-block">
      <div class="ai-audit-heading">Сравнение с рынком (${mf.jobs_sample_size} вакансий, ${mf.candidates_sample_size} резюме)</div>
      ${percentileBarHtml('Навыки относительно похожих резюме', mf.skill_percentile, mf.skill_percentile_insufficient_data)}
      ${percentileBarHtml('Опыт относительно похожих резюме', mf.experience_percentile, mf.experience_percentile_insufficient_data)}
      ${mf.demand_coverage_pct !== null && mf.demand_coverage_pct !== undefined ? `
        <div class="market-metric">
          <div class="market-metric-label">Покрытие ключевых требований вакансий<span class="market-metric-pct">${mf.demand_coverage_pct}%</span></div>
          <div class="market-bar"><div class="market-bar-fill" style="width:${mf.demand_coverage_pct}%"></div></div>
        </div>` : ''}
      <div class="ai-audit-heading">Востребовано на рынке, но не в резюме</div>
      ${chips(mf.demand_missing_skills, 'gap')}
      <div class="ai-audit-heading">Есть и востребовано</div>
      ${chips(mf.demand_covered_skills, 'ok')}
      ${synthesis}
    </div>`;
}

document.getElementById('btn-ai-audit').addEventListener('click', async () => {
  const btn = document.getElementById('btn-ai-audit');
  const box = document.getElementById('ai-audit-result');
  const resumeData = collectResumeData();
  const compareMarket = document.getElementById('audit-compare-market').checked;

  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = compareMarket ? 'Оцениваю и сверяю с рынком…' : 'Оцениваю…';
  box.style.display = 'block';
  box.innerHTML = '<span class="status">Отправляю резюме на оценку…</span>';
  try {
    const resp = await fetch('/api/ai/audit-resume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_data: resumeData, template: getSelectedTemplate(), compare_market: compareMarket }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      box.innerHTML = `<span class="status" style="color:var(--danger)">${escapeHtml(data.error || 'Ошибка ИИ')}</span>`;
      return;
    }
    box.innerHTML = renderAuditHtml(data);
  } catch (e) {
    box.innerHTML = `<span class="status" style="color:var(--danger)">Ошибка сети: ${escapeHtml(String(e))}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

// ---------- Виртуальный HR: красные флаги, карьерная траектория, тренажёр собеседования ----------

document.getElementById('btn-hr-open-builder')?.addEventListener('click', openResumeBuilder);

function statusIconFor(status) {
  return { ok: '✓', warning: '⚠', missing: '✕' }[status] || '•';
}

function renderChecklistHtml(items) {
  return (items || []).map(c => `
    <div class="audit-check-row audit-check-${c.status}">
      <span class="audit-check-icon">${statusIconFor(c.status)}</span>
      <div><b>${escapeHtml(c.item)}</b><div class="audit-check-note">${escapeHtml(c.note || '')}</div></div>
    </div>
  `).join('');
}

document.getElementById('btn-hr-redflags')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  const box = document.getElementById('hr-redflags-result');
  const resumeData = collectResumeData();

  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Проверяю…';
  box.style.display = 'block';
  box.innerHTML = '<span class="status">Считаю разрывы и смотрю формулировки…</span>';
  try {
    const resp = await fetch('/api/ai/red-flags', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_data: resumeData }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      box.innerHTML = `<span class="status" style="color:var(--danger)">${escapeHtml(data.error || 'Ошибка ИИ')}</span>`;
      return;
    }
    box.innerHTML = renderRedFlagsHtml(data);
  } catch (err) {
    box.innerHTML = `<span class="status" style="color:var(--danger)">Ошибка сети: ${escapeHtml(String(err))}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

document.getElementById('btn-hr-trajectory')?.addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  const box = document.getElementById('hr-trajectory-result');
  const resumeData = collectResumeData();

  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Думаю…';
  box.style.display = 'block';
  box.innerHTML = '<span class="status">Смотрю историю опыта…</span>';
  try {
    const resp = await fetch('/api/ai/career-trajectory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_data: resumeData }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      box.innerHTML = `<span class="status" style="color:var(--danger)">${escapeHtml(data.error || 'Ошибка ИИ')}</span>`;
      return;
    }
    box.innerHTML = renderTrajectoryHtml(data);
  } catch (err) {
    box.innerHTML = `<span class="status" style="color:var(--danger)">Ошибка сети: ${escapeHtml(String(err))}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
});

// ---------- Тренажёр собеседования: пошаговый чат с ИИ-HR ----------
// В отличие от старого «выдать сразу список вопросов», здесь каждый шаг — отдельный запрос
// к /api/ai/interview-chat с полной историей разговора; сервер не хранит состояние,
// вся история живёт в hrChatState на клиенте.

const hrChatState = { history: [], cvId: '', job: null, jobDescription: '', done: false, busy: false };

function hrChatAppendMessage(role, text) {
  const log = document.getElementById('hr-chat-log');
  const row = document.createElement('div');
  row.className = `hr-msg ${role === 'hr' ? 'hr-msg-hr' : 'hr-msg-candidate'}`;
  row.innerHTML = `<div class="hr-msg-label">${role === 'hr' ? 'HR' : 'Вы'}</div>${escapeHtml(text)}`;
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

function hrChatSetTyping(on) {
  const log = document.getElementById('hr-chat-log');
  let el = log.querySelector('.hr-msg-typing');
  if (on) {
    if (!el) {
      el = document.createElement('div');
      el.className = 'hr-msg hr-msg-typing';
      el.textContent = 'HR печатает…';
      log.appendChild(el);
    }
    log.scrollTop = log.scrollHeight;
  } else if (el) {
    el.remove();
  }
}

function hrChatSetInputEnabled(on) {
  document.getElementById('hr-chat-answer').disabled = !on;
  document.getElementById('btn-hr-chat-send').disabled = !on;
}

async function hrChatRequestTurn() {
  hrChatState.busy = true;
  hrChatSetInputEnabled(false);
  hrChatSetTyping(true);
  try {
    const resp = await fetch('/api/ai/interview-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resume_data: collectResumeData(), cv_id: hrChatState.cvId,
        job: hrChatState.job, job_description: hrChatState.jobDescription,
        history: hrChatState.history,
      }),
    });
    const data = await resp.json();
    hrChatSetTyping(false);
    if (!resp.ok) {
      hrChatAppendMessage('hr', data.error || 'Ошибка ИИ — попробуйте ещё раз.');
      return;
    }
    const text = [data.reaction, data.message].filter(Boolean).join('\n\n');
    hrChatState.history.push({ role: 'hr', text });
    hrChatAppendMessage('hr', text);
    if (data.is_final) {
      hrChatState.done = true;
      const note = document.createElement('div');
      note.className = 'hr-chat-final-note';
      note.textContent = 'Собеседование завершено — можно начать заново с тем же или другим резюме/вакансией.';
      document.getElementById('hr-chat-log').appendChild(note);
      document.getElementById('btn-hr-interview-restart').style.display = 'inline-flex';
    }
  } catch (err) {
    hrChatSetTyping(false);
    hrChatAppendMessage('hr', 'Ошибка сети: ' + String(err));
  } finally {
    hrChatState.busy = false;
    hrChatSetInputEnabled(!hrChatState.done);
    if (!hrChatState.done) document.getElementById('hr-chat-answer').focus();
  }
}

function hrChatReset() {
  hrChatState.history = [];
  hrChatState.done = false;
  hrChatState.busy = false;
  document.getElementById('hr-chat-log').innerHTML = '';
  document.getElementById('hr-chat-answer').value = '';
  document.getElementById('btn-hr-interview-restart').style.display = 'none';
}

document.getElementById('btn-hr-interview-start')?.addEventListener('click', () => {
  hrChatState.cvId = document.getElementById('hr-cv-select')?.value || '';
  const jobIdx = document.getElementById('hr-job-select')?.value || '';
  hrChatState.job = jobIdx !== '' ? allJobs[Number(jobIdx)] : null;
  hrChatState.jobDescription = document.getElementById('hr-interview-job').value.trim();

  hrChatReset();
  document.getElementById('hr-chat').style.display = 'block';
  hrChatRequestTurn();
});

document.getElementById('btn-hr-interview-restart')?.addEventListener('click', () => {
  hrChatReset();
  hrChatRequestTurn();
});

function hrChatSendAnswer() {
  if (hrChatState.busy || hrChatState.done) return;
  const input = document.getElementById('hr-chat-answer');
  const text = input.value.trim();
  if (!text) return;
  hrChatState.history.push({ role: 'candidate', text });
  hrChatAppendMessage('candidate', text);
  input.value = '';
  hrChatRequestTurn();
}

document.getElementById('btn-hr-chat-send')?.addEventListener('click', hrChatSendAnswer);
document.getElementById('hr-chat-answer')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    hrChatSendAnswer();
  }
});

// ---------- Собрать резюме с нуля с ИИ: мастер (текст → вопросы → проверка → готово) ----------

let aiBuildRawText = '';
let aiBuildData = null;

const AI_STEP_ORDER = ['input', 'clarify', 'review', 'done'];
let aiStepStatus = { input: 'active', clarify: 'pending', review: 'pending', done: 'pending' };

function renderAiSteps() {
  document.querySelectorAll('#ai-wizard-steps .ai-step').forEach(el => {
    el.classList.remove('active', 'done', 'skipped');
    const st = aiStepStatus[el.dataset.step];
    if (st && st !== 'pending') el.classList.add(st);
  });
  document.querySelectorAll('#ai-wizard-steps .ai-step-line').forEach(el => {
    const idx = Number(el.dataset.line);
    const beforeKey = AI_STEP_ORDER[idx - 1];
    const st = aiStepStatus[beforeKey];
    el.classList.toggle('done', st === 'done' || st === 'skipped');
  });
}

function setAiStage(stage) {
  document.querySelectorAll('.ai-stage').forEach(s => s.classList.toggle('active', s.dataset.stage === stage));
}

let aiLoadingTimer = null;
function startAiLoading(messages) {
  const el = document.getElementById('ai-loading-text');
  let i = 0;
  el.textContent = messages[0];
  clearInterval(aiLoadingTimer);
  aiLoadingTimer = setInterval(() => {
    i = (i + 1) % messages.length;
    el.textContent = messages[i];
  }, 1100);
}
function stopAiLoading() { clearInterval(aiLoadingTimer); }

document.querySelectorAll('#ai-build-chips .ai-chip').forEach(btn => {
  btn.addEventListener('click', () => {
    const ta = document.getElementById('ai-build-text');
    const sep = ta.value && !ta.value.endsWith('\n') ? '\n' : '';
    ta.value = ta.value + sep + btn.dataset.hint;
    ta.focus();
    ta.selectionStart = ta.selectionEnd = ta.value.length;
  });
});

function applyAiResumeData(data) {
  resetBuilderForm();
  document.getElementById('r-name').value = data.full_name || '';
  document.getElementById('r-headline').value = data.headline || '';
  document.getElementById('r-summary').value = data.summary || '';
  document.getElementById('r-skills').value = data.skills || '';

  ['experience-list', 'education-list', 'language-list', 'link-list', 'achievement-list'].forEach(id => {
    document.getElementById(id).innerHTML = '';
  });
  (data.experience || []).forEach(v => addRepeatRow('experience-list', 'experience', v));
  (data.education || []).forEach(v => addRepeatRow('education-list', 'education', v));
  (data.languages || []).forEach(v => addRepeatRow('language-list', 'languages', v));
  (data.achievements || []).forEach(v => addRepeatRow('achievement-list', 'achievements', v));

  renderResumePreview();
}

function aiSkillList() {
  return aiBuildData.skills ? aiBuildData.skills.split(',').map(s => s.trim()).filter(Boolean) : [];
}

function renderAiReview() {
  const d = aiBuildData;
  const grid = document.getElementById('ai-review-grid');
  let html = `
    <div class="ai-review-card">
      <div class="ai-review-card-head"><span class="ai-review-card-label">Основное</span></div>
      <div class="ai-review-card-grid">
        <input type="text" id="ai-rv-name" placeholder="Имя" value="${escapeHtml(d.full_name)}">
        <input type="text" id="ai-rv-headline" placeholder="Желаемая позиция" value="${escapeHtml(d.headline)}">
      </div>
    </div>
    <div class="ai-review-card">
      <div class="ai-review-card-head"><span class="ai-review-card-label">О себе</span></div>
      <textarea id="ai-rv-summary" rows="3" placeholder="Коротко о профессиональном опыте">${escapeHtml(d.summary)}</textarea>
    </div>
    <div class="ai-review-card">
      <div class="ai-review-card-head"><span class="ai-review-card-label">Опыт работы</span></div>
      ${d.experience.length ? d.experience.map((exp, i) => `
        <div style="margin-bottom:10px; padding-bottom:10px; border-bottom:1px solid var(--border-subtle);">
          <div style="display:flex; justify-content:flex-end;"><button type="button" class="ai-review-remove" data-remove="experience:${i}">×</button></div>
          <div class="ai-review-card-grid">
            <input type="text" data-exp="${i}:position" placeholder="Должность" value="${escapeHtml(exp.position)}">
            <input type="text" data-exp="${i}:company" placeholder="Компания" value="${escapeHtml(exp.company)}">
          </div>
          <input type="text" data-exp="${i}:period" placeholder="Период" value="${escapeHtml(exp.period)}" style="margin-top:8px;">
          <textarea data-exp="${i}:description" rows="2" placeholder="Чем занимались" style="margin-top:8px;">${escapeHtml(exp.description)}</textarea>
        </div>
      `).join('') : '<div class="ai-review-empty">В тексте не найдено — можно добавить вручную в конструкторе.</div>'}
    </div>
    <div class="ai-review-card">
      <div class="ai-review-card-head"><span class="ai-review-card-label">Образование</span></div>
      ${d.education.length ? d.education.map((edu, i) => `
        <div style="margin-bottom:10px; padding-bottom:10px; border-bottom:1px solid var(--border-subtle);">
          <div style="display:flex; justify-content:flex-end;"><button type="button" class="ai-review-remove" data-remove="education:${i}">×</button></div>
          <div class="ai-review-card-grid">
            <input type="text" data-edu="${i}:degree" placeholder="Специальность" value="${escapeHtml(edu.degree)}">
            <input type="text" data-edu="${i}:school" placeholder="Учебное заведение" value="${escapeHtml(edu.school)}">
          </div>
          <input type="text" data-edu="${i}:period" placeholder="Период" value="${escapeHtml(edu.period)}" style="margin-top:8px;">
        </div>
      `).join('') : '<div class="ai-review-empty">В тексте не найдено — можно добавить вручную в конструкторе.</div>'}
    </div>
    <div class="ai-review-card">
      <div class="ai-review-card-head"><span class="ai-review-card-label">Навыки</span></div>
      <div class="ai-review-skills">
        ${aiSkillList().map(s => `<span class="ai-review-skill-tag">${escapeHtml(s)}<button type="button" data-remove-skill="${escapeHtml(s)}">×</button></span>`).join('')}
        <input type="text" class="ai-review-skill-add" id="ai-rv-skill-add" placeholder="+ навык, Enter">
      </div>
    </div>
    <div class="ai-review-card">
      <div class="ai-review-card-head"><span class="ai-review-card-label">Языки</span></div>
      ${d.languages.length ? d.languages.map((lang, i) => `
        <div style="display:flex; gap:8px; align-items:flex-start; margin-bottom:8px;">
          <div class="ai-review-card-grid" style="flex:1;">
            <input type="text" data-lang="${i}:name" placeholder="Язык" value="${escapeHtml(lang.name)}">
            <input type="text" data-lang="${i}:level" placeholder="Уровень" value="${escapeHtml(lang.level)}">
          </div>
          <button type="button" class="ai-review-remove" data-remove="languages:${i}">×</button>
        </div>
      `).join('') : '<div class="ai-review-empty">В тексте не найдено — можно добавить вручную в конструкторе.</div>'}
    </div>
  `;
  grid.innerHTML = html;

  document.getElementById('ai-rv-name').addEventListener('input', e => { d.full_name = e.target.value; });
  document.getElementById('ai-rv-headline').addEventListener('input', e => { d.headline = e.target.value; });
  document.getElementById('ai-rv-summary').addEventListener('input', e => { d.summary = e.target.value; });

  grid.querySelectorAll('[data-exp]').forEach(inp => inp.addEventListener('input', () => {
    const [i, field] = inp.dataset.exp.split(':');
    d.experience[Number(i)][field] = inp.value;
  }));
  grid.querySelectorAll('[data-edu]').forEach(inp => inp.addEventListener('input', () => {
    const [i, field] = inp.dataset.edu.split(':');
    d.education[Number(i)][field] = inp.value;
  }));
  grid.querySelectorAll('[data-lang]').forEach(inp => inp.addEventListener('input', () => {
    const [i, field] = inp.dataset.lang.split(':');
    d.languages[Number(i)][field] = inp.value;
  }));
  grid.querySelectorAll('[data-remove]').forEach(btn => btn.addEventListener('click', () => {
    const [kind, idx] = btn.dataset.remove.split(':');
    d[kind].splice(Number(idx), 1);
    renderAiReview();
  }));
  grid.querySelectorAll('[data-remove-skill]').forEach(btn => btn.addEventListener('click', () => {
    d.skills = aiSkillList().filter(s => s !== btn.dataset.removeSkill).join(', ');
    renderAiReview();
  }));
  const skillAdd = document.getElementById('ai-rv-skill-add');
  skillAdd.addEventListener('keydown', e => {
    if (e.key === 'Enter' && skillAdd.value.trim()) {
      e.preventDefault();
      d.skills = [...aiSkillList(), skillAdd.value.trim()].join(', ');
      renderAiReview();
    }
  });
}

async function submitAiBuild(qaHistory) {
  try {
    const resp = await fetch('/api/ai/build-resume', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw_text: aiBuildRawText, qa_history: qaHistory }),
    });
    const data = await resp.json();
    stopAiLoading();
    if (!resp.ok) {
      showToast(data.error || 'Ошибка ИИ', true);
      if (qaHistory.length) {
        aiStepStatus = { input: 'done', clarify: 'active', review: 'pending', done: 'pending' };
        setAiStage('clarify');
      } else {
        aiStepStatus = { input: 'active', clarify: 'pending', review: 'pending', done: 'pending' };
        setAiStage('input');
      }
      renderAiSteps();
      return;
    }
    if (data.status === 'questions') {
      const list = document.getElementById('ai-build-questions-list');
      list.innerHTML = data.questions.map((q, i) => `
        <div class="ai-build-question-row">
          <label>${escapeHtml(q)}</label>
          <input type="text" data-question="${escapeHtml(q)}" id="ai-build-q-${i}">
        </div>
      `).join('');
      aiStepStatus = { input: 'done', clarify: 'active', review: 'pending', done: 'pending' };
      renderAiSteps();
      setAiStage('clarify');
    } else {
      aiBuildData = data.data;
      aiStepStatus = { input: 'done', clarify: qaHistory.length ? 'done' : 'skipped', review: 'active', done: 'pending' };
      renderAiSteps();
      renderAiReview();
      setAiStage('review');
    }
  } catch (e) {
    stopAiLoading();
    showToast('Ошибка сети: ' + e, true);
    setAiStage(qaHistory.length ? 'clarify' : 'input');
  }
}

document.getElementById('btn-ai-build-analyze').addEventListener('click', () => {
  const text = document.getElementById('ai-build-text').value.trim();
  if (!text) { showToast('Сначала напишите хоть немного о себе', true); return; }
  aiBuildRawText = text;
  setAiStage('loading');
  startAiLoading(['Читаем ваш текст…', 'Извлекаем факты…', 'Проверяем, чего не хватает…']);
  submitAiBuild([]);
});

document.getElementById('btn-ai-build-finish').addEventListener('click', () => {
  const inputs = document.querySelectorAll('#ai-build-questions-list [data-question]');
  const qaHistory = Array.from(inputs).map(inp => ({ question: inp.dataset.question, answer: inp.value.trim() }));
  setAiStage('loading');
  startAiLoading(['Собираем резюме…', 'Сверяем факты…', 'Формируем структуру…']);
  submitAiBuild(qaHistory);
});

document.getElementById('btn-ai-restart').addEventListener('click', () => {
  aiBuildRawText = '';
  aiBuildData = null;
  document.getElementById('ai-build-text').value = '';
  document.getElementById('ai-build-questions-list').innerHTML = '';
  aiStepStatus = { input: 'active', clarify: 'pending', review: 'pending', done: 'pending' };
  renderAiSteps();
  setAiStage('input');
});

document.getElementById('btn-ai-confirm').addEventListener('click', () => {
  applyAiResumeData(aiBuildData);
  aiStepStatus = { input: 'done', clarify: aiStepStatus.clarify === 'active' ? 'done' : aiStepStatus.clarify, review: 'done', done: 'active' };
  renderAiSteps();
  setAiStage('done');
  showToast('Резюме собрано — открываем в конструкторе');
  setTimeout(() => {
    document.querySelector('.subtab-item[data-subtab="builder"]').click();
  }, 900);
});

// ---------- Галерея шаблонов: структуры × темы ----------

const STRUCT_THUMB_PATTERNS = {
  'classic-single': 'abbb',
  'sidebar-left': 'abbb',
  'sidebar-right': 'abbb',
  'header-band': 'abbb',
  'diagonal-split': 'abb',
  'timeline': 'abbb',
  'cards': 'abb',
  'chip-header': 'abbb',
  'two-col-balance': 'bbabb',
  'initial-badge': 'abbb',
  'dense-ats': 'abbbbbb',
};

const TPL_DEMO_DATA = {
  full_name: 'Иван Петров',
  headline: 'Frontend Developer',
  email: 'ivan@example.com', phone: '+380 99 123 4567', location: 'Киев',
  summary: 'Более 4 лет опыта в разработке интерфейсов на React и TypeScript. Люблю доводить детали до идеала и работать в команде.',
  experience: [
    { position: 'Frontend Developer', company: 'ТОВ Технології', period: '2022 — н.в.', description: 'Разработка SPA на React, оптимизация производительности, код-ревью.' },
    { position: 'Junior Frontend Developer', company: 'StartApp', period: '2020 — 2022', description: 'Вёрстка и интеграция API, поддержка дизайн-системы.' },
  ],
  education: [{ degree: 'Компьютерные науки', school: 'КПІ', period: '2016 — 2020' }],
  skills: 'React, TypeScript, CSS, Webpack, Git',
  languages: [{ name: 'Английский', level: 'B2' }, { name: 'Украинский', level: 'Родной' }],
};

let selectedStructure = TEMPLATE_STRUCTURES[0].id;
let selectedTheme = TEMPLATE_THEMES[0].id;

function renderTplStructGrid() {
  const grid = document.getElementById('tpl-struct-grid');
  if (!grid) return;
  grid.innerHTML = TEMPLATE_STRUCTURES.map(s => {
    const pattern = STRUCT_THUMB_PATTERNS[s.id] || 'abbb';
    const children = pattern.split('').map(c => `<div class="${c}"></div>`).join('');
    return `
      <div class="tpl-struct-card${s.id === selectedStructure ? ' active' : ''}" data-struct="${s.id}">
        <div class="tpl-struct-thumb thumb-${s.id}">${children}</div>
        <div class="tpl-struct-label">${escapeHtml(s.name)}</div>
      </div>`;
  }).join('');
  grid.querySelectorAll('.tpl-struct-card').forEach(card => {
    card.addEventListener('click', () => {
      selectedStructure = card.dataset.struct;
      grid.querySelectorAll('.tpl-struct-card').forEach(c => c.classList.toggle('active', c.dataset.struct === selectedStructure));
      renderTplPreview();
    });
  });
}

function renderTplThemeGroups() {
  const container = document.getElementById('tpl-theme-groups');
  if (!container) return;
  const countEl = document.getElementById('tpl-theme-count');
  if (countEl) countEl.textContent = TEMPLATE_THEMES.length + ' тем';
  const cats = [...new Set(TEMPLATE_THEMES.map(t => t.category))];
  container.innerHTML = cats.map(cat => `
    <div class="tpl-theme-cat">${escapeHtml(cat)}</div>
    <div class="tpl-theme-row">
      ${TEMPLATE_THEMES.filter(t => t.category === cat).map(t => `
        <div class="tpl-theme-swatch${t.id === selectedTheme ? ' active' : ''}" data-theme="${t.id}" title="${escapeHtml(t.name)}" style="background:linear-gradient(135deg, ${t.p}, ${t.p2});"></div>
      `).join('')}
    </div>
  `).join('');
  container.querySelectorAll('.tpl-theme-swatch').forEach(sw => {
    sw.addEventListener('click', () => {
      selectedTheme = sw.dataset.theme;
      container.querySelectorAll('.tpl-theme-swatch').forEach(s => s.classList.toggle('active', s.dataset.theme === selectedTheme));
      renderTplPreview();
    });
  });
}

function renderTplPreview() {
  const frame = document.getElementById('tpl-preview-frame');
  if (!frame) return;
  frame.innerHTML = renderComboResumeHTML(TPL_DEMO_DATA, selectedStructure, selectedTheme);
  const page = frame.querySelector('.resume-page');
  const available = frame.clientWidth - 40;
  const zoom = available > 0 ? Math.max(0.3, Math.min(1, available / A4_WIDTH_PX)) : 0.55;
  if (page) page.style.zoom = zoom;
  const theme = TEMPLATE_THEMES.find(t => t.id === selectedTheme);
  const struct = TEMPLATE_STRUCTURES.find(s => s.id === selectedStructure);
  const label = document.getElementById('tpl-preview-label');
  if (label) label.textContent = `${struct ? struct.name : ''} · ${theme ? theme.name : ''}`;
}

document.getElementById('btn-tpl-use-new')?.addEventListener('click', () => {
  resetBuilderForm();
  comboTemplate = `${selectedStructure}__${selectedTheme}`;
  updateComboBanner();
  document.querySelector('.subtab-item[data-subtab="builder"]').click();
  renderResumePreview();
  showToast('Шаблон применён к новому резюме');
});

document.getElementById('btn-tpl-apply-current')?.addEventListener('click', () => {
  comboTemplate = `${selectedStructure}__${selectedTheme}`;
  updateComboBanner();
  document.querySelector('.subtab-item[data-subtab="builder"]').click();
  renderResumePreview();
  showToast('Шаблон применён к текущему резюме — не забудьте сохранить');
});

// ---------- Инициализация ----------

loadCvs();
loadSettings();
resetBuilderForm();
renderTplStructGrid();
renderTplThemeGroups();
loadResumeList();
syncSearchFormUi();
syncPrefSearchUi();
['pref-chip-djinni', 'pref-chip-workua', 'pref-chip-rabotaua', 'pref-chip-jooble'].forEach(id => {
  document.getElementById(id)?.addEventListener('click', () => setTimeout(syncPrefSearchUi));
});
document.getElementById('pref-all-pages')?.addEventListener('change', syncPrefSearchUi);
document.getElementById('btn-goto-search-prefs')?.addEventListener('click', () => openAccount('search'));
document.getElementById('btn-goto-market-prefs')?.addEventListener('click', () => openAccount('search'));
document.getElementById('btn-toggle-search-override')?.addEventListener('click', (e) => {
  const panel = document.getElementById('search-override');
  panel.hidden = !panel.hidden;
  e.currentTarget.textContent = panel.hidden ? 'Разовый запрос' : 'Скрыть разовый запрос';
});
document.getElementById('btn-toggle-market-override')?.addEventListener('click', (e) => {
  const panel = document.getElementById('market-override');
  panel.hidden = !panel.hidden;
  e.currentTarget.textContent = panel.hidden ? 'Разовый запрос' : 'Скрыть разовый запрос';
});
['m-chip-djinni', 'm-chip-workua', 'm-chip-rabotaua'].forEach(id => {
  if (document.getElementById(id)) updateChipStyle(id);
});
syncMarketAllPages();
document.getElementById('pref-all-pages')?.addEventListener('change', (e) => {
  document.getElementById('pref-all-pages-chip')?.classList.toggle('active', e.target.checked);
});

(async function bootAccount() {
  const profile = await loadProfile();
  const prefs = await loadSearchPrefsIntoSettings();
  if (prefs) applyPrefsToSearchForms(prefs);
  else await applySearchPrefsToForm();
  if (profile) {
    syncProfileIntoResume(profile, false);
    maybeShowProfileGate(profile);
  }
  loadCachedJobs();
  setInterval(loadCachedJobs, 60000);
  loadCachedCandidates();
  loadMarketAnalysis();
  setInterval(() => { loadCachedCandidates(); loadMarketAnalysis(); }, 60000);
})();

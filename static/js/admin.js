function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function fmtDate(ts) {
  return new Date(ts * 1000).toLocaleDateString('ru-RU');
}

function fmtDateTime(ts) {
  return new Date(ts * 1000).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

const ACTION_LABELS = {
  'auth.login': 'Вход',
  'auth.register': 'Регистрация',
  'auth.logout': 'Выход',
  'search.jobs': 'Поиск вакансий',
  'search.candidates': 'Рынок кандидатов',
  'resume.import': 'Импорт резюме',
  'ai.match': 'ИИ: оценка вакансии',
  'ai.improve': 'ИИ: улучшить текст',
  'ai.summary': 'ИИ: саммари',
  'ai.audit': 'ИИ: аудит резюме',
  'ai.bullets': 'ИИ: опыт',
  'ai.cover': 'ИИ: сопроводительное',
  'ai.build': 'ИИ: собрать резюме',
  'keys.save': 'Ключи: сохранение',
  'keys.delete': 'Ключи: удаление',
};

let toastTimer = null;
function showToast(text) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = text;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2800);
}

function setKeyStatus(el, isSet, masked) {
  if (!el) return;
  el.textContent = isSet ? `задан (${masked})` : 'не задан';
  el.classList.toggle('set', !!isSet);
  el.classList.toggle('unset', !isSet);
}

function applyKeys(s) {
  if (!s) return;
  setKeyStatus(document.getElementById('status-anthropic'), s.anthropic_api_key_set, s.anthropic_api_key_masked);
  setKeyStatus(document.getElementById('status-openai'), s.openai_api_key_set, s.openai_api_key_masked);
  setKeyStatus(document.getElementById('status-gemini'), s.gemini_api_key_set, s.gemini_api_key_masked);
  setKeyStatus(document.getElementById('status-jooble'), s.jooble_api_key_set, s.jooble_api_key_masked);
  const setModel = (id, val, fallback) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = val || '';
    el.placeholder = val || fallback;
  };
  setModel('model-anthropic', s.anthropic_model, 'claude-haiku-4-5-20251001');
  setModel('model-openai', s.openai_model, 'gpt-4o-mini');
  setModel('model-gemini', s.gemini_model, 'gemini-2.0-flash');
  document.querySelectorAll('input[name=active-provider]').forEach(r => {
    r.checked = r.value === s.active_provider;
  });
}

function detailText(action, detail) {
  if (!detail || typeof detail !== 'object') return '—';
  if (action.startsWith('ai.') || action === 'resume.import') {
    const ok = detail.ok !== false;
    const err = detail.error ? ` · ${detail.error}` : '';
    return `${ok ? 'успех' : 'ошибка'} · ${detail.provider || detail.source || ''}${err}`;
  }
  if (action.startsWith('search.')) {
    const src = Array.isArray(detail.sources) ? detail.sources.join(', ') : '';
    const q = [detail.keyword, detail.query].filter(Boolean).join(' / ');
    return `${src || '—'} · ${q || '—'} · ${detail.n ?? 0}`;
  }
  if (action.startsWith('keys.')) {
    return (detail.fields || [detail.provider]).filter(Boolean).join(', ') || '—';
  }
  if (action.startsWith('auth.')) return detail.email || '—';
  try { return JSON.stringify(detail); } catch (e) { return '—'; }
}

function renderActivity(items, counts) {
  const aiN = (counts?.by_action || []).filter(r => (r.action || '').startsWith('ai.')).reduce((s, r) => s + (r.n || 0), 0);
  const countEl = document.getElementById('admin-log-count');
  if (countEl) {
    countEl.textContent = counts
      ? `за 14 дней: ${counts.total || 0} событий, из них ИИ — ${aiN}`
      : '';
  }
  const body = document.getElementById('admin-activity-body');
  if (!body) return;
  body.innerHTML = (items || []).map(row => {
    const ok = row.detail && typeof row.detail === 'object' ? row.detail.ok : null;
    const dot = ok === true ? '<span class="ok-dot ok"></span>' : (ok === false ? '<span class="ok-dot err"></span>' : '');
    const who = row.email || row.name || (row.user_id === '__platform__' ? 'платформа' : '—');
    return `<tr>
      <td>${fmtDateTime(row.created_at)}</td>
      <td>${escapeHtml(who)}</td>
      <td>${dot}${escapeHtml(ACTION_LABELS[row.action] || row.action)}</td>
      <td class="log-detail">${escapeHtml(detailText(row.action, row.detail))}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="4">Пока нет событий</td></tr>';
}

async function saveProvider(provider) {
  const key = (document.getElementById(`key-${provider}`)?.value || '').trim();
  const modelEl = document.getElementById(`model-${provider}`);
  const model = modelEl ? modelEl.value.trim() : '';
  const body = {};
  if (key) body[`${provider}_api_key`] = key;
  if (model) body[`${provider}_model`] = model;
  if (!key && !model) { showToast('Введите ключ или модель'); return; }
  const resp = await fetch('/api/admin/keys', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const s = await resp.json();
  if (!resp.ok) { showToast(s.error || 'Ошибка'); return; }
  const el = document.getElementById(`key-${provider}`);
  if (el) el.value = '';
  applyKeys(s);
  showToast('Сохранено');
  load();
}

async function clearKey(provider, label) {
  const resp = await fetch('/api/admin/keys/' + provider, { method: 'DELETE' });
  const s = await resp.json();
  if (!resp.ok) { showToast(s.error || 'Ошибка'); return; }
  applyKeys(s);
  showToast('Ключ ' + label + ' удалён');
  load();
}

async function load() {
  const filter = document.getElementById('admin-log-filter')?.value || '';
  const resp = await fetch('/api/admin/overview');
  if (!resp.ok) { showToast('Не удалось загрузить обзор'); return; }
  const data = await resp.json();
  const stats = data.stats || {};
  const analytics = data.analytics || {};
  const aiN = (data.activity_counts?.by_action || []).filter(r => (r.action || '').startsWith('ai.')).reduce((s, r) => s + (r.n || 0), 0);
  const searches = analytics.total_searches || 0;
  const cacheHits = analytics.total_cache_hits || 0;
  document.getElementById('admin-stats').innerHTML = `
    <div class="admin-stat"><b>${stats.users || 0}</b><span>пользователей</span></div>
    <div class="admin-stat"><b>${stats.resumes || 0}</b><span>резюме в конструкторе</span></div>
    <div class="admin-stat"><b>${stats.cvs || 0}</b><span>резюме всего (+файлы)</span></div>
    <div class="admin-stat"><b>${searches}</b><span>поисков за 14 дней</span></div>
    <div class="admin-stat"><b>${aiN}</b><span>ИИ-запросов за 14 дней</span></div>
    <div class="admin-stat"><b>${searches ? Math.round(100 * cacheHits / searches) : 0}%</b><span>из кэша</span></div>
  `;

  if (data.keys) applyKeys(data.keys);

  document.getElementById('admin-users-body').innerHTML = (data.users || []).map(u => `
    <tr>
      <td class="strong">${escapeHtml(u.name)}</td>
      <td>${escapeHtml(u.email)}</td>
      <td><span class="role-badge ${u.role}">${u.role}</span></td>
      <td>${fmtDate(u.created_at)}</td>
    </tr>
  `).join('') || '<tr><td colspan="4">Пока нет пользователей</td></tr>';

  const days = analytics.by_day || [];
  const maxDay = Math.max(1, ...days.map(d => d.n));
  document.getElementById('admin-bars').innerHTML = days.map((d, i) => `
    <div class="admin-bar-wrap">
      <div class="admin-bar" style="height:${Math.max(4, Math.round(80 * d.n / maxDay))}px"></div>
      <div class="admin-bar-day">${escapeHtml((d.day || '').slice(5))}</div>
    </div>
  `).join('') || '<div class="empty">Пока нет данных</div>';

  const kws = analytics.top_keywords || [];
  const maxKw = Math.max(1, ...kws.map(k => k.n));
  document.getElementById('admin-kw').innerHTML = kws.map(k => `
    <div class="admin-kw-row">
      <div class="admin-kw-fill" style="width:${Math.round(100 * k.n / maxKw)}%"></div>
      <div class="admin-kw-content"><span>${escapeHtml(k.term || '—')}</span><span>${k.n}</span></div>
    </div>
  `).join('') || '<div class="empty">Пока нет запросов</div>';

  document.getElementById('admin-sources-body').innerHTML = (analytics.by_source || []).map(s => `
    <tr>
      <td class="strong">${escapeHtml(s.source)}</td>
      <td>${s.n}</td>
      <td>${s.hits || 0}</td>
      <td>${s.total_results || 0}</td>
    </tr>
  `).join('') || '<tr><td colspan="4">Пока нет данных</td></tr>';

  if (filter) {
    const act = await fetch('/api/admin/activity?action=' + encodeURIComponent(filter)).then(r => r.json());
    renderActivity(act.items, data.activity_counts);
  } else {
    renderActivity(data.activity, data.activity_counts);
  }
}

document.querySelectorAll('[data-admin-section]').forEach(btn => {
  btn.addEventListener('click', () => {
    const id = btn.dataset.adminSection;
    document.querySelectorAll('[data-admin-section]').forEach(b => {
      b.classList.toggle('active', b.dataset.adminSection === id);
    });
    document.querySelectorAll('[data-admin-panel]').forEach(p => {
      p.classList.toggle('is-active', p.dataset.adminPanel === id);
    });
    document.body.classList.remove('nav-open');
    const toggle = document.getElementById('nav-toggle');
    const scrim = document.getElementById('nav-scrim');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    if (scrim) scrim.hidden = true;
  });
});

(function setupMobileNav() {
  const toggle = document.getElementById('nav-toggle');
  const scrim = document.getElementById('nav-scrim');
  const closeNav = () => {
    document.body.classList.remove('nav-open');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    if (scrim) scrim.hidden = true;
  };
  toggle?.addEventListener('click', () => {
    if (document.body.classList.contains('nav-open')) closeNav();
    else {
      document.body.classList.add('nav-open');
      if (toggle) toggle.setAttribute('aria-expanded', 'true');
      if (scrim) scrim.hidden = false;
    }
  });
  scrim?.addEventListener('click', closeNav);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeNav();
  });
})();

document.getElementById('save-anthropic')?.addEventListener('click', () => saveProvider('anthropic'));
document.getElementById('save-openai')?.addEventListener('click', () => saveProvider('openai'));
document.getElementById('save-gemini')?.addEventListener('click', () => saveProvider('gemini'));
document.getElementById('save-jooble')?.addEventListener('click', () => saveProvider('jooble'));
document.getElementById('clear-anthropic')?.addEventListener('click', () => clearKey('anthropic', 'Anthropic'));
document.getElementById('clear-openai')?.addEventListener('click', () => clearKey('openai', 'OpenAI'));
document.getElementById('clear-gemini')?.addEventListener('click', () => clearKey('gemini', 'Gemini'));
document.getElementById('clear-jooble')?.addEventListener('click', () => clearKey('jooble', 'Jooble'));
document.querySelectorAll('input[name=active-provider]').forEach(r => {
  r.addEventListener('change', async () => {
    const resp = await fetch('/api/admin/keys', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active_provider: r.value }),
    });
    const s = await resp.json();
    if (resp.ok) { applyKeys(s); showToast('Активный провайдер обновлён'); }
  });
});
document.getElementById('admin-log-filter')?.addEventListener('change', load);

load();

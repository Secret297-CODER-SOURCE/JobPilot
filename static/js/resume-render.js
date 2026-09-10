// Общий рендеринг резюме из структурированных данных в HTML.
// Используется живым превью в конструкторе, отдельной страницей печати и
// свободным холстом — чтобы то, что человек видит в приложении, один в один
// совпадало с PDF.

function resumeEscape(s) {
  return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// Строит HTML-содержимое каждого смыслового блока резюме отдельно —
// это даёт как фиксированные шаблоны (склеивают блоки в готовую раскладку),
// так и свободный холст (позиционирует те же блоки как угодно).
function buildResumeBlocks(data) {
  const name = resumeEscape(data.full_name) || '<span class="resume-empty-hint">Имя не указано</span>';
  const headline = resumeEscape(data.headline);
  const contacts = [data.email, data.phone, data.location].filter(Boolean).map(resumeEscape).join(' · ');
  const links = (data.links || []).filter(l => l.url).map(l =>
    `<a href="${resumeEscape(l.url)}" target="_blank" rel="noopener" style="color:inherit;">${resumeEscape(l.label || l.url)}</a>`
  ).join(' · ');

  const summary = (data.summary || '').trim() ? `
    <div class="resume-section" data-piece="summary">
      <div class="resume-section-title">О себе</div>
      <div class="resume-entry-desc">${resumeEscape(data.summary)}</div>
    </div>` : '';

  const experienceItems = data.experience || [];
  const experience = experienceItems.length ? `
    <div class="resume-section" data-piece="experience">
      <div class="resume-section-title">Опыт работы</div>
      ${experienceItems.map(e => `
        <div class="resume-entry">
          <div class="resume-entry-head">
            <span>${resumeEscape(e.position)}${e.company ? ' — ' + resumeEscape(e.company) : ''}</span>
            <span class="resume-entry-period">${resumeEscape(e.period)}</span>
          </div>
          ${e.description ? `<div class="resume-entry-desc">${resumeEscape(e.description)}</div>` : ''}
        </div>
      `).join('')}
    </div>` : '';

  const educationItems = data.education || [];
  const education = educationItems.length ? `
    <div class="resume-section" data-piece="education">
      <div class="resume-section-title">Образование</div>
      ${educationItems.map(e => `
        <div class="resume-entry">
          <div class="resume-entry-head">
            <span>${resumeEscape(e.degree)}${e.school ? ', ' + resumeEscape(e.school) : ''}</span>
            <span class="resume-entry-period">${resumeEscape(e.period)}</span>
          </div>
        </div>
      `).join('')}
    </div>` : '';

  const skillsItems = (data.skills || '').split(',').map(s => s.trim()).filter(Boolean);
  const skills = skillsItems.length ? `
    <div class="resume-section" data-piece="skills">
      <div class="resume-section-title">Навыки</div>
      <div class="resume-skills">${skillsItems.map(s => `<span class="resume-skill-chip">${resumeEscape(s)}</span>`).join('')}</div>
    </div>` : '';

  const languageItems = (data.languages || []).filter(l => l.name);
  const languages = languageItems.length ? `
    <div class="resume-section" data-piece="languages">
      <div class="resume-section-title">Языки</div>
      ${languageItems.map(l => `<div class="resume-entry-sub">${resumeEscape(l.name)} — ${resumeEscape(l.level)}</div>`).join('')}
    </div>` : '';

  const achievementItems = (data.achievements || []).filter(a => a.value || a.label);
  const achievements = achievementItems.length ? `
    <div class="resume-section resume-achievements-section" data-piece="achievements">
      <div class="resume-section-title">Достижения</div>
      <div class="resume-achievements">
        ${achievementItems.map(a => `
          <div class="resume-achievement-card">
            <div class="resume-achievement-value">${resumeEscape(a.value)}</div>
            <div class="resume-achievement-label">${resumeEscape(a.label)}</div>
            ${a.description ? `<div class="resume-achievement-desc">${resumeEscape(a.description)}</div>` : ''}
          </div>
        `).join('')}
      </div>
    </div>` : '';

  const header = `
    <div class="resume-header" data-piece="header">
      <div class="resume-name">${name}</div>
      ${headline ? `<div class="resume-headline">${headline}</div>` : ''}
      <div class="resume-contacts">${[contacts, links].filter(Boolean).join(' · ')}</div>
    </div>`;

  return {
    header, summary, experience, education, skills, languages, achievements,
    raw: {
      name: data.full_name || '', headline: data.headline || '',
      email: data.email || '', phone: data.phone || '', location: data.location || '',
      summaryText: (data.summary || '').trim(),
      experienceItems, educationItems, skillsItems, languageItems, achievementItems,
      links: (data.links || []).filter(l => l.url),
      avatarUrl: data.avatar_url || '',
    },
  };
}

// ---------------------------------------------------------------------------
// Общие приёмы для «настоящих креативов» (не структура×тема): значок-контакты,
// полосы-навыки по порядку значимости, фото/аватар — используются шаблонами
// editorial / geo-bold / twotone-split ниже.
// ---------------------------------------------------------------------------

const _CONTACT_ICONS = {
  mail: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="4.5" width="15" height="11" rx="1.5"/><path d="M3 5.5l7 5.5 7-5.5"/></svg>',
  phone: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 3.5c-1 0-1.5.6-1.5 1.5 0 6.6 5.4 12 12 12 .9 0 1.5-.5 1.5-1.5v-2l-3.5-1-1.3 1.3a9 9 0 01-5-5l1.3-1.3-1-3.5H5z"/></svg>',
  pin: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 18s6-5.5 6-10a6 6 0 10-12 0c0 4.5 6 10 6 10z"/><circle cx="10" cy="8" r="2"/></svg>',
  link: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 12l4-4M7 14l-2 2a3 3 0 01-4-4l2-2M13 6l2-2a3 3 0 014 4l-2 2"/></svg>',
};

function avatarImgHtml(raw, cls) {
  return raw.avatarUrl ? `<img class="${cls}" src="${resumeEscape(raw.avatarUrl)}" alt="">` : '';
}

function contactIconRowsHtml(raw) {
  const rows = [];
  if (raw.email) rows.push({ icon: 'mail', text: raw.email });
  if (raw.phone) rows.push({ icon: 'phone', text: raw.phone });
  if (raw.location) rows.push({ icon: 'pin', text: raw.location });
  raw.links.forEach(l => rows.push({ icon: 'link', text: l.label || l.url, url: l.url }));
  return rows.map(row => `
    <div class="contact-icon-row">
      <span class="contact-icon">${_CONTACT_ICONS[row.icon]}</span>
      <span>${row.url
        ? `<a href="${resumeEscape(row.url)}" target="_blank" rel="noopener" style="color:inherit;">${resumeEscape(row.text)}</a>`
        : resumeEscape(row.text)}</span>
    </div>`).join('');
}

function skillBarsHtml(raw) {
  const n = raw.skillsItems.length;
  if (!n) return '';
  return raw.skillsItems.map((s, i) => {
    const pct = n === 1 ? 100 : Math.max(35, Math.round(100 - (i * 55) / (n - 1)));
    return `
      <div class="skill-bar-row">
        <div class="skill-bar-label">${resumeEscape(s)}</div>
        <div class="skill-bar-track"><div class="skill-bar-fill" style="width:${pct}%"></div></div>
      </div>`;
  }).join('');
}

// ---------------------------------------------------------------------------
// Настоящие креативы — авторские шаблоны с собственной типографикой, графикой
// и (у части) местом для фото, а не перекрашенная структура из галереи ниже.
// ---------------------------------------------------------------------------

function renderEditorialHTML(data) {
  const r = buildResumeBlocks(data).raw;
  const nameParts = (r.name || '').trim().split(/\s+/).filter(Boolean);
  const nameHtml = nameParts.length > 1
    ? `${resumeEscape(nameParts.slice(0, -1).join(' '))}<br>${resumeEscape(nameParts.slice(-1)[0])}`
    : (resumeEscape(r.name) || '<span class="resume-empty-hint">Имя не указано</span>');
  const contactsLine = [r.email, r.phone, r.location].filter(Boolean).map(resumeEscape).join('   ·   ');

  const expHtml = r.experienceItems.map(e => `
    <div class="ed-entry">
      <div class="ed-entry-head"><span class="ed-entry-role">${resumeEscape(e.position)}</span><span class="ed-entry-period">${resumeEscape(e.period)}</span></div>
      ${e.company ? `<div class="ed-entry-company">${resumeEscape(e.company)}</div>` : ''}
      ${e.description ? `<div class="ed-entry-desc">${resumeEscape(e.description)}</div>` : ''}
    </div>`).join('');

  const eduHtml = r.educationItems.map(e => `
    <div class="ed-entry-sub">
      <div><b>${resumeEscape(e.degree)}</b>${e.school ? ', ' + resumeEscape(e.school) : ''}</div>
      <div class="ed-entry-period">${resumeEscape(e.period)}</div>
    </div>`).join('');
  const skillsHtml = r.skillsItems.map(s => `<div>${resumeEscape(s)}</div>`).join('');
  const langHtml = r.languageItems.map(l => `<div>${resumeEscape(l.name)} — ${resumeEscape(l.level)}</div>`).join('');
  const achHtml = r.achievementItems.map(a => `
    <div class="ed-stat"><div class="ed-stat-value">${resumeEscape(a.value)}</div><div class="ed-stat-label">${resumeEscape(a.label)}</div></div>`).join('');

  return `
    <div class="resume-page tpl-editorial">
      <div class="ed-header-group" data-piece="ed-header">
        <div class="ed-masthead">
          <div class="ed-eyebrow">${r.headline ? resumeEscape(r.headline) : 'РЕЗЮМЕ'}</div>
          ${avatarImgHtml(r, 'ed-avatar')}
        </div>
        <div class="ed-name">${nameHtml}</div>
        <div class="ed-rule"></div>
        ${contactsLine ? `<div class="ed-contacts">${contactsLine}</div>` : ''}
      </div>
      <div class="ed-body" data-piece="ed-body">
        <div class="ed-main">
          ${r.summaryText ? `<div class="ed-intro">${resumeEscape(r.summaryText)}</div>` : ''}
          ${achHtml ? `<div class="ed-stat-row">${achHtml}</div>` : ''}
          ${expHtml ? `<div class="ed-heading">Опыт работы</div>${expHtml}` : ''}
        </div>
        <div class="ed-aside">
          ${eduHtml ? `<div class="ed-heading">Образование</div>${eduHtml}` : ''}
          ${skillsHtml ? `<div class="ed-heading">Навыки</div><div class="ed-skill-list">${skillsHtml}</div>` : ''}
          ${langHtml ? `<div class="ed-heading">Языки</div>${langHtml}` : ''}
        </div>
      </div>
    </div>`;
}

function renderGeoBoldHTML(data) {
  const r = buildResumeBlocks(data).raw;
  const expHtml = r.experienceItems.map(e => `
    <div class="gb-entry">
      <div class="gb-entry-dot"></div>
      <div class="gb-entry-body">
        <div class="gb-entry-head"><span class="gb-entry-role">${resumeEscape(e.position)}</span>${e.company ? `<span class="gb-entry-company"> · ${resumeEscape(e.company)}</span>` : ''}</div>
        <div class="gb-entry-period">${resumeEscape(e.period)}</div>
        ${e.description ? `<div class="gb-entry-desc">${resumeEscape(e.description)}</div>` : ''}
      </div>
    </div>`).join('');
  const eduHtml = r.educationItems.map(e => `
    <div class="gb-entry">
      <div class="gb-entry-dot"></div>
      <div class="gb-entry-body">
        <div class="gb-entry-head"><span class="gb-entry-role">${resumeEscape(e.degree)}</span></div>
        <div class="gb-entry-period">${[e.school, e.period].filter(Boolean).map(resumeEscape).join(' · ')}</div>
      </div>
    </div>`).join('');
  const langHtml = r.languageItems.map(l => `<span class="gb-lang-chip">${resumeEscape(l.name)} · ${resumeEscape(l.level)}</span>`).join('');
  const achHtml = r.achievementItems.map(a => `
    <div class="gb-stat"><div class="gb-stat-value">${resumeEscape(a.value)}</div><div class="gb-stat-label">${resumeEscape(a.label)}</div></div>`).join('');

  return `
    <div class="resume-page tpl-geo-bold">
      <div class="gb-shape-1"></div>
      <div class="gb-shape-2"></div>
      <div class="gb-header-group" data-piece="gb-header">
        <div class="gb-header">
          <div class="gb-header-text">
            <div class="gb-name">${resumeEscape(r.name) || 'Имя не указано'}</div>
            ${r.headline ? `<div class="gb-headline">${resumeEscape(r.headline)}</div>` : ''}
          </div>
          ${avatarImgHtml(r, 'gb-avatar')}
        </div>
        <div class="gb-contacts">${contactIconRowsHtml(r)}</div>
        ${r.summaryText ? `<div class="gb-summary">${resumeEscape(r.summaryText)}</div>` : ''}
        ${achHtml ? `<div class="gb-stat-row">${achHtml}</div>` : ''}
      </div>
      <div class="gb-body" data-piece="gb-body">
        <div class="gb-main">
          ${expHtml ? `<div class="gb-heading">Опыт работы</div>${expHtml}` : ''}
          ${eduHtml ? `<div class="gb-heading">Образование</div>${eduHtml}` : ''}
        </div>
        <div class="gb-aside">
          ${r.skillsItems.length ? `<div class="gb-heading">Навыки</div>${skillBarsHtml(r)}` : ''}
          ${langHtml ? `<div class="gb-heading">Языки</div><div class="gb-lang-list">${langHtml}</div>` : ''}
        </div>
      </div>
    </div>`;
}

function renderTwotoneSplitHTML(data) {
  const r = buildResumeBlocks(data).raw;
  const expHtml = r.experienceItems.map(e => `
    <div class="ts-entry">
      <div class="ts-entry-head"><span>${resumeEscape(e.position)}${e.company ? ' — ' + resumeEscape(e.company) : ''}</span><span class="ts-entry-period">${resumeEscape(e.period)}</span></div>
      ${e.description ? `<div class="ts-entry-desc">${resumeEscape(e.description)}</div>` : ''}
    </div>`).join('');
  const eduHtml = r.educationItems.map(e => `
    <div class="ts-entry"><div class="ts-entry-head"><span>${resumeEscape(e.degree)}${e.school ? ', ' + resumeEscape(e.school) : ''}</span><span class="ts-entry-period">${resumeEscape(e.period)}</span></div></div>`).join('');
  const skillsChips = r.skillsItems.map(s => `<span class="ts-chip">${resumeEscape(s)}</span>`).join('');
  const langHtml = r.languageItems.map(l => `<div class="ts-lang-row"><span>${resumeEscape(l.name)}</span><span>${resumeEscape(l.level)}</span></div>`).join('');
  const achHtml = r.achievementItems.map(a => `
    <div class="ts-stat"><div class="ts-stat-value">${resumeEscape(a.value)}</div><div class="ts-stat-label">${resumeEscape(a.label)}</div></div>`).join('');

  return `
    <div class="resume-page tpl-twotone-split">
      <div class="ts-panel" data-piece="ts-panel">
        <div class="ts-ruler"></div>
        ${r.avatarUrl ? avatarImgHtml(r, 'ts-avatar') : `<div class="ts-badge">${resumeEscape(initials(r.name))}</div>`}
        <div class="ts-name">${resumeEscape(r.name) || 'Имя не указано'}</div>
        ${r.headline ? `<div class="ts-headline">${resumeEscape(r.headline)}</div>` : ''}
        <div class="ts-contacts">${contactIconRowsHtml(r)}</div>
        ${skillsChips ? `<div class="ts-panel-heading">Навыки</div><div class="ts-chip-row">${skillsChips}</div>` : ''}
        ${langHtml ? `<div class="ts-panel-heading">Языки</div>${langHtml}` : ''}
      </div>
      <div class="ts-content" data-piece="ts-content">
        ${r.summaryText ? `<div class="ts-intro">${resumeEscape(r.summaryText)}</div>` : ''}
        ${achHtml ? `<div class="ts-stat-row">${achHtml}</div>` : ''}
        ${expHtml ? `<div class="ts-content-heading">Опыт работы</div>${expHtml}` : ''}
        ${eduHtml ? `<div class="ts-content-heading">Образование</div>${eduHtml}` : ''}
      </div>
    </div>`;
}

function renderMonoGridHTML(data) {
  const r = buildResumeBlocks(data).raw;
  const sections = [];
  if (r.summaryText) {
    sections.push({ label: 'О себе', html: `<div class="mg-text">${resumeEscape(r.summaryText)}</div>` });
  }
  if (r.achievementItems.length) {
    sections.push({ label: 'Достижения', html: `<div class="mg-stat-row">${r.achievementItems.map(a => `
      <div class="mg-stat"><div class="mg-stat-value">${resumeEscape(a.value)}</div><div class="mg-stat-label">${resumeEscape(a.label)}</div></div>`).join('')}</div>` });
  }
  if (r.experienceItems.length) {
    sections.push({ label: 'Опыт работы', html: r.experienceItems.map(e => `
      <div class="mg-row">
        <div class="mg-row-period">${resumeEscape(e.period)}</div>
        <div class="mg-row-body"><b>${resumeEscape(e.position)}</b>${e.company ? ' — ' + resumeEscape(e.company) : ''}${e.description ? `<div class="mg-row-desc">${resumeEscape(e.description)}</div>` : ''}</div>
      </div>`).join('') });
  }
  if (r.educationItems.length) {
    sections.push({ label: 'Образование', html: r.educationItems.map(e => `
      <div class="mg-row">
        <div class="mg-row-period">${resumeEscape(e.period)}</div>
        <div class="mg-row-body"><b>${resumeEscape(e.degree)}</b>${e.school ? ', ' + resumeEscape(e.school) : ''}</div>
      </div>`).join('') });
  }
  if (r.skillsItems.length) {
    sections.push({ label: 'Навыки', html: `<div class="mg-skill-row">${r.skillsItems.map(resumeEscape).join(' / ')}</div>` });
  }
  if (r.languageItems.length) {
    sections.push({ label: 'Языки', html: r.languageItems.map(l => `
      <div class="mg-row"><div class="mg-row-period">${resumeEscape(l.level)}</div><div class="mg-row-body">${resumeEscape(l.name)}</div></div>`).join('') });
  }

  const sectionsHtml = sections.map((s, i) => `
    <div class="mg-section">
      <div class="mg-index">${String(i + 1).padStart(2, '0')}</div>
      <div class="mg-section-body">
        <div class="mg-section-label">${resumeEscape(s.label)}</div>
        ${s.html}
      </div>
    </div>`).join('');

  const contactsLine = [r.email, r.phone, r.location].filter(Boolean).map(resumeEscape).join('   /   ');

  return `
    <div class="resume-page tpl-mono-grid">
      <div class="mg-header-group" data-piece="mg-header">
        <div class="mg-header">
          <div class="mg-name">${resumeEscape(r.name) || 'Имя не указано'}</div>
          ${r.headline ? `<div class="mg-headline">${resumeEscape(r.headline)}</div>` : ''}
        </div>
        <div class="mg-ruler"></div>
        ${contactsLine ? `<div class="mg-contacts">${contactsLine}</div>` : ''}
      </div>
      <div class="mg-sections" data-piece="mg-sections">${sectionsHtml}</div>
    </div>`;
}

// ---------------------------------------------------------------------------
// Галерея шаблонов: структуры (раскладка) × темы (цвет/градиент).
// Каждая структура — реальная отдельная вёрстка. Каждая тема — палитра,
// применяемая через CSS-переменные --tpl-*. Комбинация «структура__тема» даёт
// самостоятельно выглядящий шаблон, не просто перекрашенную копию.
// ---------------------------------------------------------------------------

const TEMPLATE_STRUCTURES = [
  { id: 'classic-single', name: 'Классика' },
  { id: 'sidebar-left', name: 'Сайдбар слева' },
  { id: 'sidebar-right', name: 'Сайдбар справа' },
  { id: 'header-band', name: 'Цветная шапка' },
  { id: 'diagonal-split', name: 'Диагональный сплит' },
  { id: 'timeline', name: 'Таймлайн' },
  { id: 'cards', name: 'Карточки' },
  { id: 'chip-header', name: 'Навыки под шапкой' },
  { id: 'two-col-balance', name: 'Два столбца' },
  { id: 'initial-badge', name: 'Инициалы-медальон' },
  { id: 'dense-ats', name: 'Плотный ATS' },
];

const TEMPLATE_THEMES = [
  // Профессиональные
  { id: 'ocean-blue', name: 'Океан', category: 'Профессиональные', p: '#0369A1', p2: '#0EA5E9', ink: '#ffffff' },
  { id: 'navy-steel', name: 'Флот', category: 'Профессиональные', p: '#1E3A5F', p2: '#3B6EA5', ink: '#ffffff' },
  { id: 'slate-graphite', name: 'Графит', category: 'Профессиональные', p: '#334155', p2: '#64748B', ink: '#ffffff' },
  { id: 'forest-exec', name: 'Хвоя', category: 'Профессиональные', p: '#14532D', p2: '#16A34A', ink: '#ffffff' },
  { id: 'burgundy-classic', name: 'Бордо', category: 'Профессиональные', p: '#7F1D1D', p2: '#B91C1C', ink: '#ffffff' },
  { id: 'midnight-indigo', name: 'Полночь', category: 'Профессиональные', p: '#1E1B4B', p2: '#4338CA', ink: '#ffffff' },
  { id: 'charcoal-mono', name: 'Уголь', category: 'Профессиональные', p: '#18181B', p2: '#3F3F46', ink: '#ffffff' },
  { id: 'teal-corporate', name: 'Корпоративный тил', category: 'Профессиональные', p: '#0F766E', p2: '#14B8A6', ink: '#ffffff' },
  // Яркие
  { id: 'sunset-coral', name: 'Закат', category: 'Яркие', p: '#EA580C', p2: '#F97316', ink: '#ffffff' },
  { id: 'crimson-pop', name: 'Малина', category: 'Яркие', p: '#DC2626', p2: '#F87171', ink: '#ffffff' },
  { id: 'electric-violet', name: 'Электрик', category: 'Яркие', p: '#7C3AED', p2: '#A855F7', ink: '#ffffff' },
  { id: 'hot-pink', name: 'Фуксия', category: 'Яркие', p: '#DB2777', p2: '#F472B6', ink: '#ffffff' },
  { id: 'amber-blaze', name: 'Янтарь', category: 'Яркие', p: '#D97706', p2: '#FBBF24', ink: '#1a1206' },
  { id: 'lime-punch', name: 'Лайм', category: 'Яркие', p: '#4D7C0F', p2: '#84CC16', ink: '#0c1a03' },
  { id: 'cobalt-bright', name: 'Кобальт', category: 'Яркие', p: '#1D4ED8', p2: '#3B82F6', ink: '#ffffff' },
  { id: 'magenta-flash', name: 'Маджента', category: 'Яркие', p: '#A21CAF', p2: '#D946EF', ink: '#ffffff' },
  // Элегантные
  { id: 'dusty-rose', name: 'Пыльная роза', category: 'Элегантные', p: '#9F6B6B', p2: '#C89595', ink: '#2a1414' },
  { id: 'sage-calm', name: 'Шалфей', category: 'Элегантные', p: '#6B8F71', p2: '#9BB89F', ink: '#10190f' },
  { id: 'taupe-soft', name: 'Тауп', category: 'Элегантные', p: '#8B7D6B', p2: '#B5A692', ink: '#211c14' },
  { id: 'lavender-mist', name: 'Лаванда', category: 'Элегантные', p: '#8678B0', p2: '#B3A6D6', ink: '#1c1730' },
  { id: 'mocha-warm', name: 'Мокко', category: 'Элегантные', p: '#7A5C4A', p2: '#A6836B', ink: '#ffffff' },
  { id: 'stone-quiet', name: 'Камень', category: 'Элегантные', p: '#78716C', p2: '#A8A29E', ink: '#ffffff' },
  { id: 'powder-blue', name: 'Пудровый синий', category: 'Элегантные', p: '#6C93B5', p2: '#A6C7DE', ink: '#10202e' },
  { id: 'sand-neutral', name: 'Песок', category: 'Элегантные', p: '#A68A64', p2: '#CBB292', ink: '#241c10' },
  // Тёплые
  { id: 'terracotta', name: 'Терракота', category: 'Тёплые', p: '#C2571A', p2: '#E08A4E', ink: '#ffffff' },
  { id: 'golden-hour', name: 'Золотой час', category: 'Тёплые', p: '#B45309', p2: '#F59E0B', ink: '#1a1002' },
  { id: 'cinnamon', name: 'Корица', category: 'Тёплые', p: '#9A3412', p2: '#C2610D', ink: '#ffffff' },
  { id: 'peach-glow', name: 'Персик', category: 'Тёплые', p: '#E8926B', p2: '#F4B896', ink: '#331c0f' },
  { id: 'coral-reef', name: 'Коралл', category: 'Тёплые', p: '#F0654A', p2: '#F79577', ink: '#33110a' },
  { id: 'mustard-field', name: 'Горчица', category: 'Тёплые', p: '#A16207', p2: '#D4A72C', ink: '#1c1502' },
  { id: 'rust-earth', name: 'Ржавчина', category: 'Тёплые', p: '#92400E', p2: '#B45F1D', ink: '#ffffff' },
  // Холодные
  { id: 'arctic-ice', name: 'Арктика', category: 'Холодные', p: '#0891B2', p2: '#67E8F9', ink: '#04262b' },
  { id: 'deep-sea', name: 'Глубина', category: 'Холодные', p: '#075985', p2: '#38BDF8', ink: '#ffffff' },
  { id: 'mint-fresh', name: 'Мята', category: 'Холодные', p: '#059669', p2: '#6EE7B7', ink: '#042e21' },
  { id: 'glacier-blue', name: 'Ледник', category: 'Холодные', p: '#2563EB', p2: '#93C5FD', ink: '#ffffff' },
  { id: 'periwinkle', name: 'Барвинок', category: 'Холодные', p: '#4F46E5', p2: '#A5B4FC', ink: '#ffffff' },
  { id: 'cyan-tech', name: 'Технотил', category: 'Холодные', p: '#0E7490', p2: '#22D3EE', ink: '#042e2e' },
  { id: 'spruce-cool', name: 'Ель', category: 'Холодные', p: '#115E59', p2: '#2DD4BF', ink: '#ffffff' },
  // Монохром
  { id: 'pure-black', name: 'Чёрный', category: 'Монохром', p: '#0A0A0A', p2: '#404040', ink: '#ffffff' },
  { id: 'ink-gray', name: 'Чернильный', category: 'Монохром', p: '#27272A', p2: '#52525B', ink: '#ffffff' },
  { id: 'paper-white', name: 'Бумага', category: 'Монохром', p: '#E5E7EB', p2: '#F9FAFB', ink: '#18181b' },
  { id: 'graphite-silver', name: 'Серебро', category: 'Монохром', p: '#4B5563', p2: '#9CA3AF', ink: '#ffffff' },
  { id: 'warm-gray', name: 'Тёплый серый', category: 'Монохром', p: '#57534E', p2: '#A8A29E', ink: '#ffffff' },
  { id: 'cool-gray', name: 'Холодный серый', category: 'Монохром', p: '#475569', p2: '#94A3B8', ink: '#ffffff' },
  { id: 'onyx-minimal', name: 'Оникс', category: 'Монохром', p: '#171717', p2: '#262626', ink: '#ffffff' },
  { id: 'porcelain', name: 'Фарфор', category: 'Монохром', p: '#D6D3D1', p2: '#E7E5E4', ink: '#292524' },
];

function themeById(id) {
  return TEMPLATE_THEMES.find(t => t.id === id) || TEMPLATE_THEMES[0];
}

function themeStyleVars(theme) {
  return `--tpl-primary:${theme.p};--tpl-primary-2:${theme.p2};--tpl-ink:${theme.ink};`;
}

function initials(name) {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return parts.slice(0, 2).map(p => p[0].toUpperCase()).join('');
}

function renderComboResumeHTML(data, structureId, themeId) {
  const b = buildResumeBlocks(data);
  const theme = themeById(themeId);
  const style = themeStyleVars(theme);
  const cls = `resume-page struct-${structureId}`;

  if (structureId === 'sidebar-left') {
    return `<div class="${cls}" style="${style}">
      <div class="resume-sidebar">${b.header}${b.skills}${b.languages}</div>
      <div class="resume-main">${b.summary}${b.achievements}${b.experience}${b.education}</div>
    </div>`;
  }
  if (structureId === 'sidebar-right') {
    return `<div class="${cls}" style="${style}">
      <div class="struct-band">${b.header}</div>
      <div class="struct-body">
        <div class="resume-main">${b.summary}${b.achievements}${b.experience}${b.education}</div>
        <div class="resume-sidebar-right">${b.skills}${b.languages}</div>
      </div>
    </div>`;
  }
  if (structureId === 'header-band') {
    return `<div class="${cls}" style="${style}">
      <div class="struct-band struct-band-deco">${b.header}</div>
      <div class="struct-content">${b.summary}${b.achievements}${b.experience}${b.education}${b.skills}${b.languages}</div>
    </div>`;
  }
  if (structureId === 'diagonal-split') {
    return `<div class="${cls}" style="${style}">
      <div class="struct-diagonal-bg"></div>
      <div class="struct-diagonal-head">${b.header}</div>
      <div class="struct-content">${b.summary}${b.achievements}${b.experience}${b.education}${b.skills}${b.languages}</div>
    </div>`;
  }
  if (structureId === 'timeline') {
    return `<div class="${cls}" style="${style}">
      ${b.header}
      <div class="struct-timeline">${b.summary}${b.achievements}${b.experience}</div>
      ${b.education}${b.skills}${b.languages}
    </div>`;
  }
  if (structureId === 'cards') {
    return `<div class="${cls}" style="${style}">
      ${b.header}
      <div class="struct-card-grid">${b.summary}${b.achievements}${b.experience}${b.education}${b.skills}${b.languages}</div>
    </div>`;
  }
  if (structureId === 'chip-header') {
    return `<div class="${cls}" style="${style}">
      ${b.header}
      <div class="struct-chip-strip">${b.skills}</div>
      <div class="struct-body">
        <div class="resume-main">${b.summary}${b.achievements}${b.experience}${b.education}</div>
        <div class="resume-sidebar-right">${b.languages}</div>
      </div>
    </div>`;
  }
  if (structureId === 'two-col-balance') {
    return `<div class="${cls}" style="${style}">
      ${b.header}
      <div class="struct-balance">
        <div class="struct-balance-col">${b.summary}${b.achievements}${b.experience}</div>
        <div class="struct-balance-col">${b.education}${b.skills}${b.languages}</div>
      </div>
    </div>`;
  }
  if (structureId === 'initial-badge') {
    return `<div class="${cls}" style="${style}">
      <div class="struct-badge-head">
        <div class="struct-badge">${resumeEscape(initials(data.full_name))}</div>
        ${b.header}
      </div>
      <div class="struct-content">${b.summary}${b.achievements}${b.experience}${b.education}${b.skills}${b.languages}</div>
    </div>`;
  }
  if (structureId === 'dense-ats') {
    return `<div class="${cls}" style="${style}">${b.header}${b.summary}${b.achievements}${b.experience}${b.education}${b.skills}${b.languages}</div>`;
  }
  // classic-single (по умолчанию)
  return `<div class="${cls}" style="${style}">${b.header}${b.summary}${b.achievements}${b.experience}${b.education}${b.skills}${b.languages}</div>`;
}

function renderResumeHTML(data, template) {
  const b = buildResumeBlocks(data);

  if (template.includes('__')) {
    const [structureId, themeId] = template.split('__');
    return renderComboResumeHTML(data, structureId, themeId);
  }

  if (template === 'editorial') return renderEditorialHTML(data);
  if (template === 'geo-bold') return renderGeoBoldHTML(data);
  if (template === 'twotone-split') return renderTwotoneSplitHTML(data);
  if (template === 'mono-grid') return renderMonoGridHTML(data);

  if (template.startsWith('modern')) {
    return `
      <div class="resume-page tpl-${template}">
        <div class="resume-sidebar">
          ${b.header}
          ${b.skills}
          ${b.languages}
        </div>
        <div class="resume-main">
          ${b.summary}
          ${b.achievements}
          ${b.experience}
          ${b.education}
        </div>
      </div>`;
  }

  if (template.startsWith('executive')) {
    return `
      <div class="resume-page tpl-${template}">
        ${b.header}
        <div class="resume-exec-body">
          <div class="resume-main">
            ${b.summary}
            ${b.achievements}
            ${b.experience}
            ${b.education}
          </div>
          <div class="resume-sidebar-right">
            ${b.skills}
            ${b.languages}
          </div>
        </div>
      </div>`;
  }

  if (template === 'custom') {
    return renderResumeCanvasHTML(
      data, (data.canvas_layout) || DEFAULT_CANVAS_LAYOUT, false,
      data.frozen_from || 'custom', data.canvas_skin || null,
    );
  }

  return `
    <div class="resume-page tpl-${template}">
      ${b.header}
      ${b.summary}
      ${b.achievements}
      ${b.experience}
      ${b.education}
      ${b.skills}
      ${b.languages}
    </div>`;
}

// ---------------------------------------------------------------------------
// Свободный холст — блоки резюме можно перетаскивать и менять им размер.
// Позиции хранятся в px в системе координат страницы A4 при 96dpi (без учёта
// текущего масштаба превью — zoom только визуально уменьшает картинку целиком).
// ---------------------------------------------------------------------------

const CANVAS_PAGE_WIDTH = 794;   // 210mm при 96dpi
const CANVAS_PAGE_HEIGHT = 1123; // 297mm при 96dpi

const DEFAULT_CANVAS_LAYOUT = {
  header:       { x: 32, y: 28,  w: 730, h: 96  },
  summary:      { x: 32, y: 136, w: 730, h: 84  },
  achievements: { x: 32, y: 228, w: 730, h: 72  },
  experience:   { x: 32, y: 308, w: 478, h: 444 },
  education:    { x: 526, y: 232, w: 236, h: 170 },
  skills:       { x: 526, y: 414, w: 236, h: 120 },
  languages:    { x: 526, y: 546, w: 236, h: 120 },
};

const CANVAS_BLOCK_LABELS = {
  header: 'Шапка', summary: 'О себе', achievements: 'Достижения', experience: 'Опыт работы',
  education: 'Образование', skills: 'Навыки', languages: 'Языки',
  'ed-header': 'Шапка', 'ed-body': 'Содержимое',
  'gb-header': 'Шапка', 'gb-body': 'Содержимое',
  'ts-panel': 'Боковая панель', 'ts-content': 'Содержимое',
  'mg-header': 'Шапка', 'mg-sections': 'Разделы',
};

// «Разморозка» готового шаблона в перетаскиваемый холст (см. app.js:freezeCurrentTemplateToCanvas):
// пользователь может включить свободное перетаскивание для ЛЮБОГО шаблона, не только пустого
// «Свободного холста». Вместо того чтобы у каждого шаблона отдельно прописывать, из каких кусков
// он состоит, здесь просто рендерим шаблон как обычно и вынимаем из готового HTML всё, что
// помечено data-piece — это работает одинаково что для блочных шаблонов (galerie/классика,
// где data-piece стоит прямо в buildResumeBlocks), что для авторских (editorial/geo-bold/
// twotone-split/mono-grid, где data-piece расставлен вручную на их 2 крупных зоны).
function extractTemplatePieces(fullHtml) {
  const wrapper = document.createElement('div');
  wrapper.innerHTML = fullHtml;
  const pieces = {};
  wrapper.querySelectorAll('[data-piece]').forEach(el => {
    pieces[el.dataset.piece] = el.outerHTML;
  });
  return pieces;
}

function getTemplatePieces(data, originalTemplate) {
  if (!originalTemplate || originalTemplate === 'custom') {
    const b = buildResumeBlocks(data);
    const pieces = {};
    ['header', 'summary', 'achievements', 'experience', 'education', 'skills', 'languages'].forEach(key => {
      if (b[key]) pieces[key] = b[key];
    });
    return pieces;
  }
  return extractTemplatePieces(renderResumeHTML(data, originalTemplate));
}

function renderResumeCanvasHTML(data, layout, editable, originalTemplate, skin) {
  const pieces = getTemplatePieces(data, originalTemplate);
  const blocksHtml = Object.keys(pieces).map(key => {
    const pos = layout[key] || DEFAULT_CANVAS_LAYOUT[key] || { x: 32, y: 32, w: 400, h: 150 };
    const handle = editable
      ? `<div class="canvas-block-label">${CANVAS_BLOCK_LABELS[key] || key}</div><div class="canvas-resize-handle"></div>`
      : '';
    return `<div class="canvas-block${editable ? ' editable' : ''}" data-block="${key}" style="left:${pos.x}px;top:${pos.y}px;width:${pos.w}px;height:${pos.h}px;">${handle}<div class="canvas-block-content">${pieces[key]}</div></div>`;
  }).join('');

  const images = data.images || [];
  const imagesHtml = images.map(img => {
    const isShape = img.kind === 'shape';
    const controls = editable
      ? `<button type="button" class="canvas-image-remove" data-img-id="${img.id}" title="Удалить">✕</button>` +
        (isShape ? `<input type="color" class="canvas-shape-recolor" data-img-id="${img.id}" value="${resumeEscape(img.color || '#ffb020')}" title="Цвет">` : '') +
        `<div class="canvas-resize-handle"></div>`
      : '';
    return `<div class="canvas-block canvas-image-block${isShape ? ' is-shape' : ''}${editable ? ' editable' : ''}" data-block="image" data-image-id="${img.id}" style="left:${img.x}px;top:${img.y}px;width:${img.w}px;height:${img.h}px;"><img src="${resumeEscape(img.url)}" class="canvas-image-el" draggable="false" alt="">${controls}</div>`;
  }).join('');

  const effect = data.canvas_effect && data.canvas_effect !== 'none' ? ` fx-${data.canvas_effect}` : '';
  // «Скин» — классы и CSS-переменные исходного шаблона (см. captureCurrentSkin в app.js),
  // сохранённые при разморозке, чтобы цвет темы (заголовки, чипы навыков) остался таким же,
  // каким был в готовом шаблоне до включения перетаскивания. Структурные элементы вроде
  // цветных полос/декоративных фигур не переносятся — только сами блоки с содержимым.
  const skinClass = skin && skin.rootClass ? ` resume-page ${skin.rootClass}` : '';
  const skinStyle = skin && skin.styleVars ? skin.styleVars : '';
  // padding:0 обязателен инлайном — у «размороженных» шаблонов подмешивается класс .resume-page,
  // а у него самого есть padding:16mm, из-за которого все координаты блоков (измеренные ещё
  // без этого класса) съехали бы вглубь ровно на этот паддинг.
  return `<div class="resume-canvas-page tpl-canvas${skinClass}${effect}" style="width:${CANVAS_PAGE_WIDTH}px;min-height:${CANVAS_PAGE_HEIGHT}px;padding:0;${skinStyle}">${blocksHtml}${imagesHtml}</div>`;
}

# Graph Report - jobscraper  (2026-08-26)

## Corpus Check
- 19 files · ~56,028 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 778 nodes · 1759 edges · 34 communities (33 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 55 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d4ded15a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- webapp.py
- collectRegions
- app.js
- candidate_scraper.py
- ai_match.py
- FakeWorkuaPage
- fetch
- startCanvasDrag
- resume-render.js
- showToast
- applyPrefsToSearchForms
- escapeHtml
- resume_import.py
- db.py
- CLAUDE.md
- test_candidates.py
- test_account.py
- parse_search_body
- LoginImportTests
- normalize_remote_mode
- board_auth.py
- admin.js
- cv_extract.py
- renderGrid
- log_activity
- job_scraper.py
- compute_resume_market_fit
- set_setting
- payloadFromPrefs
- _do_search
- fetch_full_job_description
- applyBoardStatus
- scrape_workua_candidates
- scrape_rabotaua

## God Nodes (most connected - your core abstractions)
1. `login_required()` - 51 edges
2. `current_user()` - 45 edges
3. `get_conn()` - 34 edges
4. `escapeHtml()` - 31 edges
5. `fetch()` - 23 edges
6. `_dispatch()` - 18 edges
7. `_run_ai()` - 18 edges
8. `showToast()` - 17 edges
9. `_do_search()` - 17 edges
10. `AIMatchError` - 16 edges

## Surprising Connections (you probably didn't know these)
- `scrape_rabotaua_candidates()` --calls--> `fetch()`  [INFERRED]
  candidate_scraper.py → djinni_scraper.py
- `scrape_djinni_candidates()` --calls--> `fetch()`  [INFERRED]
  candidate_scraper.py → djinni_scraper.py
- `fetch_djinni_full_description()` --calls--> `fetch()`  [INFERRED]
  job_scraper.py → djinni_scraper.py
- `fetch_rabota_full_description()` --calls--> `fetch()`  [INFERRED]
  job_scraper.py → djinni_scraper.py
- `load_rabota_cities()` --calls--> `fetch()`  [INFERRED]
  job_scraper.py → djinni_scraper.py

## Import Cycles
- None detected.

## Communities (34 total, 1 thin omitted)

### Community 0 - "webapp.py"
Cohesion: 0.08
Nodes (84): delete_cv(), get_cv(), get_resume_draft(), flatten_text(), route, _admin_keys_payload(), admin_page(), admin_required() (+76 more)

### Community 1 - "collectRegions"
Cohesion: 0.38
Nodes (7): collectRegions(), collectRemote(), collectSettingsPrefs(), payloadFromMarketForm(), payloadFromSearchForm(), selectedMarketSources(), selectedSources()

### Community 2 - "app.js"
Cohesion: 0.05
Nodes (41): accountPrefs, AI_STEP_ORDER, aiSkillList(), aiStepStatus, allJobs, applyResumeZoom(), BOARD_LABELS, boardResumeCache (+33 more)

### Community 3 - "candidate_scraper.py"
Cohesion: 0.21
Nodes (16): analyze_market(), anonymize_candidate(), _experience_bucket(), _experience_years(), parse_djinni_candidates(), parse_rabota_candidate(), _pick_examples(), Оставить только поля для анализа рынка, выкинуть PII. (+8 more)

### Community 4 - "ai_match.py"
Cohesion: 0.15
Nodes (33): AIMatchError, analyze_red_flags(), audit_resume(), _build_prompt(), build_resume_from_text(), _call_anthropic(), _call_gemini(), _call_openai() (+25 more)

### Community 5 - "FakeWorkuaPage"
Cohesion: 0.06
Nodes (8): CityResolveTests, FakeWorkuaPage, ParseJobTests, ParseRegionsTests, SalaryTests, _workua_card(), WorkuaScrapeTests, WorkuaUrlTests

### Community 6 - "fetch"
Cohesion: 0.08
Nodes (13): bearer_json_fetch(), build_query(), clean_text(), fetch(), main(), parse_jobs(), print_table(), scrape() (+5 more)

### Community 7 - "startCanvasDrag"
Cohesion: 0.21
Nodes (14): applySnap(), clearSnapGuides(), ensureSnapGuides(), getBlockRef(), otherBlockRects(), shapeDataUri(), startCanvasDrag(), onMove() (+6 more)

### Community 8 - "resume-render.js"
Cohesion: 0.23
Nodes (22): avatarImgHtml(), buildResumeBlocks(), CANVAS_BLOCK_LABELS, _CONTACT_ICONS, contactIconRowsHtml(), DEFAULT_CANVAS_LAYOUT, extractTemplatePieces(), getTemplatePieces() (+14 more)

### Community 9 - "showToast"
Cohesion: 0.15
Nodes (25): addRepeatRow(), applyAiResumeData(), applyBoardCvToBuilder(), applyImportedResume(), collectRepeatRows(), collectResumeData(), connectBoard(), fillField() (+17 more)

### Community 10 - "applyPrefsToSearchForms"
Cohesion: 0.17
Nodes (18): adoptPrefs(), applyPrefsToSearchForms(), applyPrefsToSettingsForm(), applyRegions(), applyRemote(), applyReservation(), applySearchPrefsToForm(), loadSearchPrefsIntoSettings() (+10 more)

### Community 11 - "escapeHtml"
Cohesion: 0.14
Nodes (23): appendHrResult(), auditScoreClass(), escapeHtml(), fmtSalary(), hrStepperHtml(), percentileBarHtml(), populateHrJobSelect(), postAiJson() (+15 more)

### Community 12 - "resume_import.py"
Cohesion: 0.07
Nodes (60): _apply_djinni_reliable_fields(), _canon_path(), classify_url(), _clip(), default_fetch(), discover_djinni_profile_url(), discover_workua_resume_url(), discover_workua_resume_urls() (+52 more)

### Community 13 - "db.py"
Cohesion: 0.11
Nodes (34): activity_counts(), all_settings(), delete_platform_setting(), delete_resume_draft(), delete_setting(), get_conn(), get_user(), init_db() (+26 more)

### Community 15 - "test_candidates.py"
Cohesion: 0.06
Nodes (8): AnalyzeTests, BoardLoginTests, DjinniParseTests, FakeResumePage, RabotaScrapeTests, StripPiiTests, WorkuaScrapeTests, WorkuaUrlTests

### Community 16 - "test_account.py"
Cohesion: 0.05
Nodes (10): AccountHelpersTests, ActivityLogTests, AutoSearchTests, FilterModeTests, HrSourceTests, JobStoreListTests, PlatformKeysTests, ResumeImportApiTests (+2 more)

### Community 17 - "parse_search_body"
Cohesion: 0.26
Nodes (13): _background_scan_user(), _background_search_loop(), _clamp_float(), _clamp_int(), _get_search_prefs(), _parse_keyword_field(), _parse_remote_mode(), _parse_reservation() (+5 more)

### Community 18 - "LoginImportTests"
Cohesion: 0.10
Nodes (4): DiscoverTests, LoginImportTests, ParseTests, UrlGuardTests

### Community 19 - "normalize_remote_mode"
Cohesion: 0.18
Nodes (18): djinni_search_passes(), _fold_city_name(), normalize_remote_mode(), parse_keywords(), parse_regions(), Наборы query-параметров djinni: категории × регионы + при include отдельный…, Разобрать один или несколько регионов: строка «Київ, Львів», список или одно…, Список категорий: «Python, Java», список или одно имя. Не больше KEYWORD_MAX. (+10 more)

### Community 20 - "board_auth.py"
Cohesion: 0.10
Nodes (24): djinni_candidate_login(), djinni_login(), djinni_page_requires_login(), _djinni_submit_credentials(), extract_csrf(), HttpSession, _page_try_click(), _page_try_fill() (+16 more)

### Community 21 - "admin.js"
Cohesion: 0.35
Nodes (12): ACTION_LABELS, applyKeys(), clearKey(), detailText(), escapeHtml(), fmtDate(), fmtDateTime(), load() (+4 more)

### Community 22 - "cv_extract.py"
Cohesion: 0.43
Nodes (6): _extract_docx(), _extract_pdf(), extract_text(), _extract_txt(), Извлечение текста из резюме разных форматов (pdf/docx/txt)., ValueError

### Community 23 - "renderGrid"
Cohesion: 0.16
Nodes (18): closeModal(), dismissGate(), jobIdentity(), loadCachedJobs(), loadFullJobDescription(), maybeShowImportGate(), maybeShowProfileGate(), mergeIncomingJobs() (+10 more)

### Community 24 - "log_activity"
Cohesion: 0.18
Nodes (12): count_users(), create_user(), get_user_by_email(), log_activity(), _finish_resume_import(), login_page(), Повторные проходы автопоиска — только первая страница, без кэша., Ждать interval секунд. stop — клиент остановил, gone — отключился, timeout —… (+4 more)

### Community 25 - "job_scraper.py"
Cohesion: 0.15
Nodes (18): _append_meta(), _clean_text(), djinni_search_url(), _fetch(), main(), _parse_djinni_jobs(), _parse_jooble_job(), print_table() (+10 more)

### Community 26 - "compute_resume_market_fit"
Cohesion: 0.18
Nodes (10): compute_job_skill_demand(), compute_resume_market_fit(), percentile_rank(), Доля значений <= x — перцентиль без сторонних библиотек., Доля вакансий, где встречается каждый навык из словаря — реальный, посчитанный…, Место резюме относительно реального рынка: покрытие спроса вакансий +…, Преобразование структурированных данных конструктора резюме в текст для ИИ-…, Грубая, но честная оценка стажа: разброс годов, упомянутых в полях "период"… (+2 more)

### Community 27 - "set_setting"
Cohesion: 0.24
Nodes (9): add_cv(), get_platform_setting(), get_setting(), save_resume_draft(), set_platform_setting(), set_setting(), update_user_name(), api_onboarding_complete() (+1 more)

### Community 28 - "payloadFromPrefs"
Cohesion: 0.33
Nodes (6): loadCachedCandidates(), loadMarketAnalysis(), payloadFromPrefs(), refreshPrefsSummaries(), renderMarketGrid(), renderPrefsSummary()

### Community 29 - "_do_search"
Cohesion: 0.31
Nodes (10): get_cached_search(), log_search(), make_cache_key(), set_cached_search(), _do_candidate_search(), _do_search(), _fetch_market_fit(), _job_identity_sig() (+2 more)

### Community 30 - "fetch_full_job_description"
Cohesion: 0.40
Nodes (6): fetch_djinni_full_description(), fetch_full_job_description(), fetch_rabota_full_description(), html_to_text(), HTML описания вакансии → читаемый текст с абзацами и списками., Полный текст вакансии для карточки. Поиск отдаёт только короткий анонс.

### Community 31 - "applyBoardStatus"
Cohesion: 0.33
Nodes (6): applyBoardStatus(), boardCvHtml(), disconnectBoard(), loadProfile(), renderBoardResumes(), splitSkills()

### Community 33 - "scrape_workua_candidates"
Cohesion: 0.18
Nodes (11): _clear_workua_state(), _load_workua_state(), _save_workua_state(), scrape_workua_candidates(), _chromium_full_executable(), _launch_playwright_chromium(), UA должен совпадать с ОС Chromium, иначе Cloudflare Turnstile не проходит., Путь к полному Chromium, если headless_shell не скачан. (+3 more)

### Community 34 - "scrape_rabotaua"
Cohesion: 0.24
Nodes (11): scrape_rabotaua_candidates(), fallback_search_terms(), format_rabota_salary(), load_rabota_cities(), parse_rabota_job(), rabota_has_reservation(), work.ua / robota.ua / jooble: текстовый запрос целиком или каждая категория…, Сопоставить текстовый регион с cityId справочника robota.ua. Возвращает int… (+3 more)

## Knowledge Gaps
- **40 isolated node(s):** `ACTION_LABELS`, `allJobs`, `SOURCE_LABELS`, `accountPrefs`, `platformStatus` (+35 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fetch()` connect `fetch` to `scrape_rabotaua`, `candidate_scraper.py`, `fetch_full_job_description`, `test_candidates.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `FakeWorkuaPage` connect `FakeWorkuaPage` to `board_auth.py`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **What connects `ACTION_LABELS`, `allJobs`, `SOURCE_LABELS` to the rest of the system?**
  _40 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `webapp.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07698476343223737 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.04698581560283688 - nodes in this community are weakly interconnected._
- **Should `ai_match.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14795008912655971 - nodes in this community are weakly interconnected._
- **Should `FakeWorkuaPage` be split into smaller, more focused modules?**
  _Cohesion score 0.05708245243128964 - nodes in this community are weakly interconnected._
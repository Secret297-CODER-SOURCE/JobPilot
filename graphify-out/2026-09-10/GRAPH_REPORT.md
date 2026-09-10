# Graph Report - jobscraper  (2026-09-10)

## Corpus Check
- 19 files · ~57,190 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 830 nodes · 1839 edges · 52 communities (39 shown, 13 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 56 edges (avg confidence: 0.85)
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
- AutoSearchTests
- RemoteReservationFilterTests
- LoginImportTests
- normalize_remote_mode
- board_auth.py
- admin.js
- cv_extract.py
- renderGrid
- test_rabota.py
- job_scraper.py
- _fetch_market_fit
- djinni_scraper.py
- set_setting
- SalaryTests
- fetch_full_job_description
- hrChatRequestTurn
- CityResolveTests
- all_settings
- FullDescriptionTests
- test_account.py
- _do_search
- log_activity
- scrape_rabotaua
- PlatformKeysTests
- _run_autosearch
- api_candidates_cached
- FirstRunAuthTests
- JobStoreListTests
- merge_top_keywords
- HrSourceTests
- mark_missing_candidates_removed
- mark_missing_removed
- upsert_jobs
- upsert_candidates
- AccountHelpersTests
- FilterModeTests

## God Nodes (most connected - your core abstractions)
1. `login_required()` - 52 edges
2. `current_user()` - 46 edges
3. `get_conn()` - 35 edges
4. `escapeHtml()` - 31 edges
5. `fetch()` - 23 edges
6. `_dispatch()` - 19 edges
7. `_run_ai()` - 19 edges
8. `AIMatchError` - 17 edges
9. `showToast()` - 17 edges
10. `_do_search()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `bearer_json_fetch()` --indirect_call--> `fetch()`  [INFERRED]
  board_auth.py → djinni_scraper.py
- `scrape_rabotaua_candidates()` --calls--> `fetch()`  [INFERRED]
  candidate_scraper.py → djinni_scraper.py
- `scrape_djinni_candidates()` --calls--> `fetch()`  [INFERRED]
  candidate_scraper.py → djinni_scraper.py
- `fetch_djinni_full_description()` --calls--> `fetch()`  [INFERRED]
  job_scraper.py → djinni_scraper.py
- `fetch_rabota_full_description()` --calls--> `fetch()`  [INFERRED]
  job_scraper.py → djinni_scraper.py

## Import Cycles
- None detected.

## Communities (52 total, 13 thin omitted)

### Community 0 - "webapp.py"
Cohesion: 0.05
Nodes (111): delete_cv(), get_cv(), get_resume_draft(), flatten_text(), route, _admin_keys_payload(), admin_page(), admin_required() (+103 more)

### Community 1 - "collectRegions"
Cohesion: 0.38
Nodes (7): collectRegions(), collectRemote(), collectSettingsPrefs(), payloadFromMarketForm(), payloadFromSearchForm(), selectedMarketSources(), selectedSources()

### Community 2 - "app.js"
Cohesion: 0.04
Nodes (50): accountPrefs, activateTab(), AI_STEP_ORDER, aiSkillList(), aiStepStatus, allJobs, applyResumeZoom(), BOARD_LABELS (+42 more)

### Community 3 - "candidate_scraper.py"
Cohesion: 0.17
Nodes (21): analyze_market(), anonymize_candidate(), _clear_workua_state(), _experience_bucket(), _experience_years(), _load_workua_state(), parse_djinni_candidates(), parse_rabota_candidate() (+13 more)

### Community 4 - "ai_match.py"
Cohesion: 0.11
Nodes (39): AIMatchError, analyze_red_flags(), audit_resume(), _build_prompt(), build_resume_from_text(), _call_anthropic(), _call_gemini(), _call_openai() (+31 more)

### Community 5 - "FakeWorkuaPage"
Cohesion: 0.17
Nodes (3): FakeWorkuaPage, _workua_card(), WorkuaScrapeTests

### Community 7 - "startCanvasDrag"
Cohesion: 0.21
Nodes (14): applySnap(), clearSnapGuides(), ensureSnapGuides(), getBlockRef(), otherBlockRects(), shapeDataUri(), startCanvasDrag(), onMove() (+6 more)

### Community 8 - "resume-render.js"
Cohesion: 0.23
Nodes (22): avatarImgHtml(), buildResumeBlocks(), CANVAS_BLOCK_LABELS, _CONTACT_ICONS, contactIconRowsHtml(), DEFAULT_CANVAS_LAYOUT, extractTemplatePieces(), getTemplatePieces() (+14 more)

### Community 9 - "showToast"
Cohesion: 0.13
Nodes (28): addRepeatRow(), applyAiResumeData(), applyBoardCvToBuilder(), applyBoardStatus(), applyImportedResume(), collectRepeatRows(), collectResumeData(), connectBoard() (+20 more)

### Community 10 - "applyPrefsToSearchForms"
Cohesion: 0.17
Nodes (18): adoptPrefs(), applyPrefsToSearchForms(), applyPrefsToSettingsForm(), applyRegions(), applyRemote(), applyReservation(), applySearchPrefsToForm(), loadSearchPrefsIntoSettings() (+10 more)

### Community 11 - "escapeHtml"
Cohesion: 0.12
Nodes (27): appendHrResult(), auditScoreClass(), escapeHtml(), fmtSalary(), hrStepperHtml(), loadCachedCandidates(), loadMarketAnalysis(), payloadFromPrefs() (+19 more)

### Community 12 - "resume_import.py"
Cohesion: 0.07
Nodes (60): bearer_json_fetch(), _apply_djinni_reliable_fields(), _canon_path(), classify_url(), _clip(), default_fetch(), discover_djinni_profile_url(), discover_workua_resume_url() (+52 more)

### Community 13 - "db.py"
Cohesion: 0.20
Nodes (18): activity_counts(), delete_platform_setting(), delete_resume_draft(), delete_setting(), get_conn(), list_activity(), list_cvs(), list_jobs_by_query_sigs() (+10 more)

### Community 15 - "test_candidates.py"
Cohesion: 0.06
Nodes (8): AnalyzeTests, BoardLoginTests, DjinniParseTests, FakeResumePage, RabotaScrapeTests, StripPiiTests, WorkuaScrapeTests, WorkuaUrlTests

### Community 18 - "LoginImportTests"
Cohesion: 0.10
Nodes (4): DiscoverTests, LoginImportTests, ParseTests, UrlGuardTests

### Community 19 - "normalize_remote_mode"
Cohesion: 0.16
Nodes (20): _chromium_full_executable(), djinni_search_passes(), fallback_search_terms(), _fold_city_name(), _launch_playwright_chromium(), normalize_remote_mode(), parse_keywords(), parse_regions() (+12 more)

### Community 20 - "board_auth.py"
Cohesion: 0.10
Nodes (26): djinni_candidate_login(), djinni_login(), djinni_page_requires_login(), _djinni_submit_credentials(), extract_csrf(), HttpSession, _page_try_click(), _page_try_fill() (+18 more)

### Community 21 - "admin.js"
Cohesion: 0.35
Nodes (12): ACTION_LABELS, applyKeys(), clearKey(), detailText(), escapeHtml(), fmtDate(), fmtDateTime(), load() (+4 more)

### Community 22 - "cv_extract.py"
Cohesion: 0.43
Nodes (6): _extract_docx(), _extract_pdf(), extract_text(), _extract_txt(), Извлечение текста из резюме разных форматов (pdf/docx/txt)., ValueError

### Community 23 - "renderGrid"
Cohesion: 0.16
Nodes (18): closeModal(), dismissGate(), jobIdentity(), loadCachedJobs(), loadFullJobDescription(), maybeShowImportGate(), maybeShowProfileGate(), mergeIncomingJobs() (+10 more)

### Community 24 - "test_rabota.py"
Cohesion: 0.18
Nodes (3): ParseJobTests, ParseRegionsTests, WorkuaUrlTests

### Community 25 - "job_scraper.py"
Cohesion: 0.14
Nodes (19): _append_meta(), _clean_text(), djinni_search_url(), _fetch(), main(), _parse_djinni_jobs(), _parse_jooble_job(), print_table() (+11 more)

### Community 26 - "_fetch_market_fit"
Cohesion: 0.22
Nodes (9): compute_job_skill_demand(), compute_resume_market_fit(), percentile_rank(), Доля значений <= x — перцентиль без сторонних библиотек., Доля вакансий, где встречается каждый навык из словаря — реальный, посчитанный…, Место резюме относительно реального рынка: покрытие спроса вакансий +…, _fetch_market_fit(), Оперативная сверка резюме с рынком: только djinni.co и robota.ua (быстрые… (+1 more)

### Community 27 - "djinni_scraper.py"
Cohesion: 0.42
Nodes (8): build_query(), clean_text(), main(), parse_jobs(), print_table(), scrape(), write_csv(), write_json()

### Community 28 - "set_setting"
Cohesion: 0.25
Nodes (10): add_cv(), get_platform_setting(), get_setting(), save_resume_draft(), set_setting(), update_user_name(), api_import_resume(), api_onboarding_complete() (+2 more)

### Community 30 - "fetch_full_job_description"
Cohesion: 0.40
Nodes (6): fetch_djinni_full_description(), fetch_full_job_description(), fetch_rabota_full_description(), html_to_text(), HTML описания вакансии → читаемый текст с абзацами и списками., Полный текст вакансии для карточки. Поиск отдаёт только короткий анонс.

### Community 31 - "hrChatRequestTurn"
Cohesion: 0.50
Nodes (5): hrChatAppendMessage(), hrChatRequestTurn(), hrChatSendAnswer(), hrChatSetInputEnabled(), hrChatSetTyping()

### Community 33 - "all_settings"
Cohesion: 0.20
Nodes (11): all_settings(), init_db(), migrate_platform_keys(), platform_settings(), Если владелец раньше хранил ключи в своём профиле — перенести на платформу., Если владелец раньше хранил ключи в своём профиле — перенести на платформу., set_platform_setting(), _admin_user_id() (+3 more)

### Community 35 - "test_account.py"
Cohesion: 0.18
Nodes (5): ActivityLogTests, ResumeImportApiTests, SearchPrefSaveTests, TopKeywordsMergeTests, WipePersonalDataTests

### Community 36 - "_do_search"
Cohesion: 0.33
Nodes (9): get_cached_search(), log_search(), make_cache_key(), set_cached_search(), _do_candidate_search(), _do_search(), _job_identity_sig(), Стабильный идентификатор «этого поиска» для постоянного учёта вакансий… (+1 more)

### Community 37 - "log_activity"
Cohesion: 0.39
Nodes (8): count_users(), create_user(), get_user(), get_user_by_email(), log_activity(), _first_run(), login_page(), register_page()

### Community 38 - "scrape_rabotaua"
Cohesion: 0.29
Nodes (8): format_rabota_salary(), load_rabota_cities(), parse_rabota_job(), rabota_has_reservation(), Сопоставить текстовый регион с cityId справочника robota.ua. Возвращает int…, resolve_rabota_city_id(), scrape_rabotaua(), _uah()

### Community 40 - "_run_autosearch"
Cohesion: 0.29
Nodes (7): Повторные проходы автопоиска — только первая страница, без кэша., Повторные проходы автопоиска — только первая страница, без кэша., Ждать interval секунд. stop — клиент остановил, gone — отключился, timeout —…, Ждать interval секунд. stop — клиент остановил, gone — отключился, timeout —…, _run_autosearch(), watch_poll_form(), _ws_wait()

### Community 41 - "api_candidates_cached"
Cohesion: 0.33
Nodes (6): list_candidates_by_query_sigs(), Карточки кандидатов из постоянного хранилища под указанными query_sig (ещё не…, Карточки кандидатов из постоянного хранилища под указанными query_sig (ещё не…, api_candidates_cached(), Карточки «Рынка кандидатов», уже лежащие в постоянном хранилище под текущими…, Карточки «Рынка кандидатов», уже лежащие в постоянном хранилище под текущими…

### Community 44 - "merge_top_keywords"
Cohesion: 0.50
Nodes (4): merge_top_keywords(), _normalize_search_term(), Склеить одинаковые запросы без учёта регистра и лишних пробелов., Склеить одинаковые запросы без учёта регистра и лишних пробелов.

### Community 46 - "mark_missing_candidates_removed"
Cohesion: 0.67
Nodes (3): mark_missing_candidates_removed(), Только после ПОЛНОГО прохода: карточки под этим query_sig, не встреченные в…, Только после ПОЛНОГО прохода: карточки под этим query_sig, не встреченные в…

### Community 47 - "mark_missing_removed"
Cohesion: 0.67
Nodes (3): mark_missing_removed(), Только после ПОЛНОГО прохода по источнику+запросу: всё, что раньше видели под…, Только после ПОЛНОГО прохода по источнику+запросу: всё, что раньше видели под…

### Community 48 - "upsert_jobs"
Cohesion: 0.67
Nodes (3): jobs_with_keys — список (key, job_dict). Возвращает {key: is_new} — is_new=True…, jobs_with_keys — список (key, job_dict). Возвращает {key: is_new} — is_new=True…, upsert_jobs()

### Community 49 - "upsert_candidates"
Cohesion: 0.67
Nodes (3): candidates_with_keys — список (key, card_dict). Возвращает {key: is_new}., candidates_with_keys — список (key, card_dict). Возвращает {key: is_new}., upsert_candidates()

## Knowledge Gaps
- **41 isolated node(s):** `ACTION_LABELS`, `allJobs`, `SOURCE_LABELS`, `accountPrefs`, `platformStatus` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fetch()` connect `fetch` to `FullDescriptionTests`, `candidate_scraper.py`, `scrape_rabotaua`, `resume_import.py`, `test_candidates.py`, `RemoteReservationFilterTests`, `djinni_scraper.py`, `fetch_full_job_description`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `FakeWorkuaPage` connect `FakeWorkuaPage` to `test_rabota.py`, `board_auth.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `AutoSearchTests` connect `AutoSearchTests` to `test_account.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **What connects `ACTION_LABELS`, `allJobs`, `SOURCE_LABELS` to the rest of the system?**
  _41 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `webapp.py` be split into smaller, more focused modules?**
  _Cohesion score 0.053407855922993325 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.041742286751361164 - nodes in this community are weakly interconnected._
- **Should `ai_match.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11463414634146342 - nodes in this community are weakly interconnected._
# Graph Report - jobscraper  (2026-08-25)

## Corpus Check
- 20 files · ~48,954 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 646 nodes · 1455 edges · 23 communities (22 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- webapp.py
- collectRegions
- app.js
- job_scraper.py
- ai_match.py
- FakeWorkuaPage
- fetch
- startCanvasDrag
- resume-render.js
- renderResumePreview
- applyPrefsToSearchForms
- escapeHtml
- resume_import.py
- CLAUDE.md
- test_candidates.py
- test_account.py
- db.py
- test_resume_import.py
- showToast
- board_auth.py
- admin.js
- cv_extract.py
- maybeShowImportGate

## God Nodes (most connected - your core abstractions)
1. `login_required()` - 43 edges
2. `current_user()` - 40 edges
3. `get_conn()` - 30 edges
4. `escapeHtml()` - 20 edges
5. `fetch()` - 19 edges
6. `_dispatch()` - 17 edges
7. `AIMatchError` - 15 edges
8. `_do_search()` - 15 edges
9. `_run_ai()` - 15 edges
10. `log_activity()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `bearer_json_fetch()` --indirect_call--> `fetch()`  [INFERRED]
  board_auth.py → djinni_scraper.py
- `scrape_rabotaua_candidates()` --calls--> `fetch()`  [INFERRED]
  candidate_scraper.py → djinni_scraper.py
- `scrape_djinni_candidates()` --calls--> `fetch()`  [INFERRED]
  candidate_scraper.py → djinni_scraper.py
- `load_rabota_cities()` --calls--> `fetch()`  [INFERRED]
  job_scraper.py → djinni_scraper.py
- `scrape_rabotaua()` --calls--> `fetch()`  [INFERRED]
  job_scraper.py → djinni_scraper.py

## Import Cycles
- None detected.

## Communities (23 total, 1 thin omitted)

### Community 0 - "webapp.py"
Cohesion: 0.07
Nodes (90): add_cv(), delete_cv(), delete_resume_draft(), get_cv(), get_resume_draft(), platform_settings(), save_resume_draft(), flatten_text() (+82 more)

### Community 1 - "collectRegions"
Cohesion: 0.38
Nodes (7): collectRegions(), collectRemote(), collectSettingsPrefs(), payloadFromMarketForm(), payloadFromSearchForm(), selectedMarketSources(), selectedSources()

### Community 2 - "app.js"
Cohesion: 0.05
Nodes (38): accountPrefs, AI_STEP_ORDER, aiSkillList(), aiStepStatus, allJobs, BOARD_LABELS, btnMarket, btnSearch (+30 more)

### Community 3 - "job_scraper.py"
Cohesion: 0.05
Nodes (78): analyze_market(), anonymize_candidate(), _clear_workua_state(), compute_job_skill_demand(), compute_resume_market_fit(), _experience_bucket(), _experience_years(), _load_workua_state() (+70 more)

### Community 4 - "ai_match.py"
Cohesion: 0.20
Nodes (26): AIMatchError, analyze_red_flags(), audit_resume(), _build_prompt(), build_resume_from_text(), _call_anthropic(), _call_gemini(), _call_openai() (+18 more)

### Community 5 - "FakeWorkuaPage"
Cohesion: 0.06
Nodes (8): CityResolveTests, FakeWorkuaPage, ParseJobTests, ParseRegionsTests, SalaryTests, _workua_card(), WorkuaScrapeTests, WorkuaUrlTests

### Community 6 - "fetch"
Cohesion: 0.09
Nodes (11): build_query(), clean_text(), fetch(), main(), parse_jobs(), print_table(), scrape(), write_csv() (+3 more)

### Community 7 - "startCanvasDrag"
Cohesion: 0.23
Nodes (13): applySnap(), clearSnapGuides(), ensureSnapGuides(), getBlockRef(), otherBlockRects(), startCanvasDrag(), onMove(), onUp() (+5 more)

### Community 8 - "resume-render.js"
Cohesion: 0.25
Nodes (20): avatarImgHtml(), buildResumeBlocks(), CANVAS_BLOCK_LABELS, _CONTACT_ICONS, contactIconRowsHtml(), DEFAULT_CANVAS_LAYOUT, initials(), renderComboResumeHTML() (+12 more)

### Community 9 - "renderResumePreview"
Cohesion: 0.23
Nodes (14): addRepeatRow(), applyAiResumeData(), applyImportedResume(), applyResumeZoom(), collectRepeatRows(), collectResumeData(), computeFitZoom(), fillField() (+6 more)

### Community 10 - "applyPrefsToSearchForms"
Cohesion: 0.17
Nodes (18): adoptPrefs(), applyPrefsToSearchForms(), applyPrefsToSettingsForm(), applyRegions(), applyRemote(), applyReservation(), applySearchPrefsToForm(), loadSearchPrefsIntoSettings() (+10 more)

### Community 11 - "escapeHtml"
Cohesion: 0.12
Nodes (21): escapeHtml(), fmtSalary(), jobIdentity(), mergeIncomingJobs(), openJobDetail(), payloadFromPrefs(), percentileBarHtml(), refreshPrefsSummaries() (+13 more)

### Community 12 - "resume_import.py"
Cohesion: 0.13
Nodes (32): classify_url(), default_fetch(), discover_djinni_profile_url(), empty_resume(), extract_contacts(), extract_skills(), _finalize(), _first_group() (+24 more)

### Community 15 - "test_candidates.py"
Cohesion: 0.06
Nodes (8): AnalyzeTests, BoardLoginTests, DjinniParseTests, FakeResumePage, RabotaScrapeTests, StripPiiTests, WorkuaScrapeTests, WorkuaUrlTests

### Community 16 - "test_account.py"
Cohesion: 0.06
Nodes (7): AccountHelpersTests, ActivityLogTests, AutoSearchTests, FilterModeTests, PlatformKeysTests, ResumeImportApiTests, TopKeywordsMergeTests

### Community 17 - "db.py"
Cohesion: 0.09
Nodes (42): activity_counts(), all_settings(), count_users(), create_user(), delete_platform_setting(), delete_setting(), get_conn(), get_platform_setting() (+34 more)

### Community 18 - "test_resume_import.py"
Cohesion: 0.12
Nodes (4): DiscoverTests, LoginImportTests, ParseTests, UrlGuardTests

### Community 19 - "showToast"
Cohesion: 0.20
Nodes (14): applyBoardStatus(), connectBoard(), disconnectBoard(), getSelectedTemplate(), importResumeFromLogin(), loadCvs(), loadProfile(), loadResumeList() (+6 more)

### Community 20 - "board_auth.py"
Cohesion: 0.10
Nodes (25): bearer_json_fetch(), djinni_candidate_login(), djinni_login(), djinni_page_requires_login(), _djinni_submit_credentials(), extract_csrf(), HttpSession, _page_try_click() (+17 more)

### Community 21 - "admin.js"
Cohesion: 0.34
Nodes (13): ACTION_LABELS, applyKeys(), clearKey(), detailText(), escapeHtml(), fmtDate(), fmtDateTime(), load() (+5 more)

### Community 22 - "cv_extract.py"
Cohesion: 0.53
Nodes (5): _extract_docx(), _extract_pdf(), extract_text(), _extract_txt(), Извлечение текста из резюме разных форматов (pdf/docx/txt).

### Community 23 - "maybeShowImportGate"
Cohesion: 0.50
Nodes (5): closeModal(), dismissGate(), maybeShowImportGate(), maybeShowProfileGate(), openModal()

## Knowledge Gaps
- **35 isolated node(s):** `ACTION_LABELS`, `allJobs`, `SOURCE_LABELS`, `accountPrefs`, `platformStatus` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fetch()` connect `fetch` to `job_scraper.py`, `board_auth.py`, `test_candidates.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `RemoteReservationFilterTests` connect `fetch` to `FakeWorkuaPage`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **What connects `ACTION_LABELS`, `allJobs`, `SOURCE_LABELS` to the rest of the system?**
  _35 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `webapp.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0694249649368864 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.050241545893719805 - nodes in this community are weakly interconnected._
- **Should `job_scraper.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05335628227194492 - nodes in this community are weakly interconnected._
- **Should `FakeWorkuaPage` be split into smaller, more focused modules?**
  _Cohesion score 0.06342780026990553 - nodes in this community are weakly interconnected._
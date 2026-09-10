# Graph Report - jobscraper  (2026-08-24)

## Corpus Check
- 16 files · ~38,979 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 502 nodes · 1088 edges · 19 communities (18 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- webapp.py
- payloadFromMarketForm
- app.js
- job_scraper.py
- ai_match.py
- FakeWorkuaPage
- fetch
- startCanvasDrag
- resume-render.js
- renderResumePreview
- applySearchPrefsToForm
- escapeHtml
- cv_extract.py
- submitAiBuild
- CLAUDE.md
- test_candidates.py
- AutoSearchTests
- db.py
- candidate_scraper.py

## God Nodes (most connected - your core abstractions)
1. `login_required()` - 35 edges
2. `current_user()` - 31 edges
3. `get_conn()` - 28 edges
4. `fetch()` - 19 edges
5. `escapeHtml()` - 18 edges
6. `_do_search()` - 15 edges
7. `_dispatch()` - 13 edges
8. `RemoteReservationFilterTests` - 13 edges
9. `scrape_rabotaua()` - 12 edges
10. `FakeWorkuaPage` - 12 edges

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

## Communities (19 total, 1 thin omitted)

### Community 0 - "webapp.py"
Cohesion: 0.08
Nodes (74): add_cv(), delete_cv(), get_cv(), get_resume_draft(), flatten_text(), Преобразование структурированных данных конструктора резюме в текст для ИИ-…, resume_title(), route (+66 more)

### Community 1 - "payloadFromMarketForm"
Cohesion: 0.40
Nodes (6): collectRegions(), collectRemote(), payloadFromMarketForm(), payloadFromSearchForm(), selectedMarketSources(), selectedSources()

### Community 2 - "app.js"
Cohesion: 0.05
Nodes (31): accountPrefs, AI_STEP_ORDER, aiStepStatus, allJobs, applyResumeZoom(), btnMarket, btnSearch, computeFitZoom() (+23 more)

### Community 3 - "job_scraper.py"
Cohesion: 0.10
Nodes (40): _append_meta(), _chromium_full_executable(), _clean_text(), djinni_search_passes(), djinni_search_url(), _fetch(), _fold_city_name(), format_rabota_salary() (+32 more)

### Community 4 - "ai_match.py"
Cohesion: 0.23
Nodes (20): AIMatchError, audit_resume(), _build_prompt(), build_resume_from_text(), _call_anthropic(), _call_gemini(), _call_openai(), _clean_skills() (+12 more)

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
Cohesion: 0.29
Nodes (12): buildResumeBlocks(), CANVAS_BLOCK_LABELS, DEFAULT_CANVAS_LAYOUT, initials(), renderComboResumeHTML(), renderResumeCanvasHTML(), renderResumeHTML(), resumeEscape() (+4 more)

### Community 9 - "renderResumePreview"
Cohesion: 0.25
Nodes (15): addRepeatRow(), applyAiResumeData(), collectRepeatRows(), collectResumeData(), getSelectedTemplate(), loadCvs(), loadResumeIntoForm(), loadResumeList() (+7 more)

### Community 10 - "applySearchPrefsToForm"
Cohesion: 0.22
Nodes (14): applyRegions(), applyRemote(), applyReservation(), applySearchPrefsToForm(), loadSearchPrefsIntoSettings(), loadSettings(), refreshPrefsSummaries(), syncAllPagesUi() (+6 more)

### Community 11 - "escapeHtml"
Cohesion: 0.14
Nodes (19): escapeHtml(), fmtSalary(), jobIdentity(), mergeIncomingJobs(), payloadFromPrefs(), percentileBarHtml(), renderGrid(), renderMarketAnalysis() (+11 more)

### Community 12 - "cv_extract.py"
Cohesion: 0.53
Nodes (5): _extract_docx(), _extract_pdf(), extract_text(), _extract_txt(), Извлечение текста из резюме разных форматов (pdf/docx/txt).

### Community 13 - "submitAiBuild"
Cohesion: 0.33
Nodes (6): aiSkillList(), renderAiReview(), renderAiSteps(), setAiStage(), stopAiLoading(), submitAiBuild()

### Community 15 - "test_candidates.py"
Cohesion: 0.07
Nodes (8): AnalyzeTests, BoardLoginTests, DjinniParseTests, FakeResumePage, RabotaScrapeTests, StripPiiTests, WorkuaScrapeTests, WorkuaUrlTests

### Community 16 - "AutoSearchTests"
Cohesion: 0.07
Nodes (6): AccountHelpersTests, ActivityLogTests, AutoSearchTests, FilterModeTests, PlatformKeysTests, TopKeywordsMergeTests

### Community 17 - "db.py"
Cohesion: 0.09
Nodes (46): activity_counts(), all_settings(), count_users(), create_user(), delete_platform_setting(), delete_resume_draft(), delete_setting(), get_cached_search() (+38 more)

### Community 18 - "candidate_scraper.py"
Cohesion: 0.07
Nodes (44): bearer_json_fetch(), djinni_login(), djinni_page_requires_login(), extract_csrf(), HttpSession, parse_rabota_token(), rabota_login(), Вход владельца на площадки для ленты кандидатов. Email/пароль задаёт только… (+36 more)

## Knowledge Gaps
- **32 isolated node(s):** `allJobs`, `SOURCE_LABELS`, `accountPrefs`, `platformStatus`, `btnSearch` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fetch()` connect `fetch` to `candidate_scraper.py`, `job_scraper.py`, `test_candidates.py`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `RemoteReservationFilterTests` connect `fetch` to `FakeWorkuaPage`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `fetch()` (e.g. with `bearer_json_fetch()` and `scrape_djinni_candidates()`) actually correct?**
  _`fetch()` has 17 INFERRED edges - model-reasoned connections that need verification._
- **What connects `allJobs`, `SOURCE_LABELS`, `accountPrefs` to the rest of the system?**
  _32 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `webapp.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08270676691729323 - nodes in this community are weakly interconnected._
- **Should `app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.05398110661268556 - nodes in this community are weakly interconnected._
- **Should `job_scraper.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09830866807610994 - nodes in this community are weakly interconnected._
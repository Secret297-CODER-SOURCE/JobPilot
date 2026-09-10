#!/usr/bin/env python3
"""Публичные карточки резюме для анализа рынка (не полный CV и не контакты).

Со всех поддерживаемых площадок берём только то, что видно в выдаче поиска:
должность, навыки, зарплата, город, опыт. Имена, телефоны, email, мессенджеры
и полные тексты резюме отбрасываются. Страницы отдельных анкет не открываем.

Ленты кандидатов на площадках закрыты без входа работодателя — владелец
задаёт свои аккаунты в админке (как ключ Jooble).

  djinni   — HTML /developers/ после входа
  workua   — Playwright, /resumes-{city}/{query}/, сессия работодателя
  rabotaua — JSON API resume/search с JWT с auth-api.rabota.ua
  jooble   — резюме кандидатов не публикует
"""

import collections
import json
import re
import sys
import time
import urllib.error
import urllib.parse

import board_auth
import db
import job_scraper
import resume_builder

WORKUA_STATE_FILE = db.DATA_DIR / "workua_employer_state.json"


def _load_workua_state():
    try:
        if WORKUA_STATE_FILE.is_file():
            return json.loads(WORKUA_STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return None


def _save_workua_state(storage):
    if not storage:
        return
    try:
        WORKUA_STATE_FILE.write_text(json.dumps(storage))
    except OSError:
        pass


def _clear_workua_state():
    try:
        WORKUA_STATE_FILE.unlink(missing_ok=True)
    except OSError:
        pass


CANDIDATE_MAX_PAGES = 10
CANDIDATE_PAGE_SIZE = 40
RABOTA_RESUME_SEARCH_URL = "https://api.rabota.ua/resume/search"
RABOTA_RESUME_URL = "https://robota.ua/candidates/{id}"
DJINNI_DEVELOPERS_URL = "https://djinni.co/developers/"

_CONTACT_RE = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.]+"
    r"|(?:https?://)?t\.me/\S+"
    r"|@[A-Za-z0-9_]{4,}"
    r"|\+?\d[\d\s().-]{8,}\d"
    r"|telegram|whatsapp|viber|skype",
    re.I,
)
_DJINNI_PROFILE_RE = re.compile(
    r'<a[^>]+href="((?:/q/|/developers/)[^"?#]+/)"[^>]*>(.*?)</a>',
    re.S | re.I,
)
_SALARY_RE = re.compile(
    r'(\$|€|грн|UAH)?\s*([\d\s]{2,9})\s*(?:[-–—]\s*([\d\s]{2,9}))?\s*(\$|€|грн|UAH)?',
    re.I,
)
_YEARS_RE = re.compile(r"(\d+)\s*(?:рок|год|year|yrs?)", re.I)
_SKILL_SPLIT_RE = re.compile(r"[,;/|•·\n]+")
_NON_SKILL = {
    "and", "or", "the", "для", "або", "та", "на", "в", "з", "и", "или",
    "remote", "hybrid", "office", "київ", "киев", "львів", "ukraine",
}


def strip_contacts(text):
    text = job_scraper._clean_text(text or "")
    text = _CONTACT_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _skills_from_text(*parts):
    bag = []
    seen = set()
    for raw in parts:
        chunk = strip_contacts(raw or "")
        if not chunk:
            continue
        for token in _SKILL_SPLIT_RE.split(chunk):
            token = token.strip(" .()-[]").strip()
            if not token or len(token) < 2 or len(token) > 40:
                continue
            if " " in token and len(token.split()) > 4:
                continue
            key = token.casefold()
            if key in _NON_SKILL or key.isdigit() or key in seen:
                continue
            seen.add(key)
            bag.append(token)
    return bag[:24]


def _experience_years(*parts):
    for raw in parts:
        if isinstance(raw, (int, float)) and raw >= 0:
            return int(raw)
        text = str(raw or "")
        m = _YEARS_RE.search(text)
        if m:
            return int(m.group(1))
        if str(raw).strip().isdigit():
            return int(raw)
    return None


def anonymize_candidate(item):
    """Оставить только поля для анализа рынка, выкинуть PII."""
    title = strip_contacts(item.get("title") or item.get("position") or "")
    city = strip_contacts(item.get("city") or "")
    salary = strip_contacts(item.get("salary") or "")
    snippet = strip_contacts(item.get("snippet") or "")
    skills = item.get("skills") or _skills_from_text(title, snippet)
    skills = [strip_contacts(s) for s in skills if strip_contacts(s)]
    cid = str(item.get("id") or "")
    source = item.get("source") or ""
    years = _experience_years(item.get("experience_years"), item.get("experience"), snippet)
    return {
        "source": source,
        "id": cid,
        "title": title[:200],
        "salary": salary[:80],
        "city": city[:80],
        "experience_years": years,
        "skills": skills[:16],
        "snippet": snippet[:280],
        "url": (item.get("url") or "")[:300],
        "meta": " · ".join(p for p in [city, f"{years} р." if years is not None else ""] if p),
    }


def parse_rabota_candidate(raw):
    cid = str(raw.get("id") or "")
    title = (
        raw.get("speciality") or raw.get("position")
        or raw.get("vacancyName") or raw.get("title") or ""
    )
    skills_raw = raw.get("skills") or raw.get("skillName") or []
    if isinstance(skills_raw, str):
        skill_list = _skills_from_text(skills_raw)
    else:
        skill_list = [str(s.get("name") if isinstance(s, dict) else s).strip() for s in skills_raw]
        skill_list = [s for s in skill_list if s]
    city = (raw.get("cityName") or "").strip()
    exp = raw.get("experience") if raw.get("experience") is not None else raw.get("experienceYears")
    snippet = raw.get("shortDescription") or raw.get("additionalInformation") or ""
    return anonymize_candidate({
        "source": "rabotaua",
        "id": cid,
        "title": title,
        "salary": job_scraper.format_rabota_salary(raw),
        "city": city,
        "experience_years": exp,
        "skills": skill_list,
        "snippet": snippet,
        "url": RABOTA_RESUME_URL.format(id=cid) if cid else "",
    })


def scrape_rabotaua_candidates(args, log=None, fetch=None):
    log = log or (lambda msg: print(msg, file=sys.stderr))
    if fetch is None:
        email = (getattr(args, "rabota_email", None) or "").strip()
        password = getattr(args, "rabota_password", None) or ""
        if not email or not password:
            log("[rabotaua-cv] нет входа — владелец задаёт email/пароль robota.ua в админке")
            return []
        try:
            token = board_auth.rabota_login(email, password, log=log)
        except Exception as e:
            log(f"[rabotaua-cv] вход не удался: {e}")
            return []
        fetch = board_auth.bearer_json_fetch(token)
    terms = job_scraper.fallback_search_terms(args)
    cities_index = None
    targets = [(None, None)]
    if args.region:
        cities_index = job_scraper.load_rabota_cities(log=log, fetch=fetch)
        targets = []
        seen = set()
        unresolved = []
        for region in job_scraper.parse_regions(args.region):
            city_id = job_scraper.resolve_rabota_city_id(region, cities_index)
            if city_id is None:
                unresolved.append(region)
                continue
            if city_id in seen:
                continue
            seen.add(city_id)
            targets.append((region, city_id))
        for name in unresolved:
            log(f"[rabotaua-cv] город «{name}» не найден — пропускаю")
        if not targets:
            log("[rabotaua-cv] ни один город не распознан — ищу по всей Украине")
            targets = [(None, None)]

    all_pages = bool(getattr(args, "all_pages", False))
    page_limit = CANDIDATE_MAX_PAGES if all_pages else max(1, args.pages)
    found = []
    seen_ids = set()

    for ki, keywords in enumerate(terms):
        if len(terms) > 1 and keywords:
            log(f"[rabotaua-cv] категория «{keywords}»")
        for ti, (region_label, city_id) in enumerate(targets):
            if city_id is not None:
                log(f"[rabotaua-cv] регион «{region_label}» → cityId={city_id}")
            page = 0
            limit = page_limit
            while page < limit:
                params = {"keyWords": keywords, "count": CANDIDATE_PAGE_SIZE, "page": page}
                if city_id is not None:
                    params["cityId"] = city_id
                url = f"{RABOTA_RESUME_SEARCH_URL}?{urllib.parse.urlencode(params)}"
                try:
                    data = fetch(url)
                except urllib.error.HTTPError as e:
                    log(f"[rabotaua-cv] HTTP {e.code} на странице {page + 1}")
                    break
                except Exception as e:
                    log(f"[rabotaua-cv] ошибка на странице {page + 1}: {e}")
                    break
                if not isinstance(data, dict):
                    break
                if data.get("errorMessage"):
                    log(f"[rabotaua-cv] API: {data['errorMessage']}")
                    break
                raw_docs = data.get("documents") or data.get("resumes") or []
                if not raw_docs:
                    break
                batch = [parse_rabota_candidate(r) for r in raw_docs]
                new = [c for c in batch if c["id"] and c["id"] not in seen_ids and c["title"]]
                if not new:
                    break
                seen_ids.update(c["id"] for c in new)
                found.extend(new)
                total = data.get("total")
                log(f"[rabotaua-cv] страница {page + 1}: {len(new)} карточек (всего: {total if total is not None else '?'})")
                if all_pages and total:
                    needed = (int(total) + CANDIDATE_PAGE_SIZE - 1) // CANDIDATE_PAGE_SIZE
                    limit = min(max(needed, 1), CANDIDATE_MAX_PAGES)
                if len(raw_docs) < CANDIDATE_PAGE_SIZE:
                    break
                page += 1
                if page < limit:
                    time.sleep(args.delay)
            if ti + 1 < len(targets):
                time.sleep(args.delay)
        if ki + 1 < len(terms):
            time.sleep(args.delay)
    return found


def parse_djinni_candidates(page_html):
    cards = []
    seen = set()
    for m in _DJINNI_PROFILE_RE.finditer(page_html or ""):
        path, title_html = m.group(1), m.group(2)
        cid = path.strip("/").split("/")[-1]
        if not cid or cid in seen or cid in ("developers", "q"):
            continue
        seen.add(cid)
        start = m.start()
        block = page_html[start:start + 1800]
        salary_m = _SALARY_RE.search(job_scraper._clean_text(block))
        skills_m = re.search(r'class="[^"]*skill[^"]*"[^>]*>(.*?)</', block, re.S | re.I)
        loc_m = re.search(r'class="[^"]*location[^"]*"[^>]*>(.*?)</', block, re.S | re.I)
        exp_m = _YEARS_RE.search(job_scraper._clean_text(block))
        title = job_scraper._clean_text(title_html)
        snippet = job_scraper._clean_text(skills_m.group(1) if skills_m else "")
        if not snippet:
            blob = job_scraper._clean_text(block)
            snippet = blob.replace(title, "", 1).strip()
        cards.append(anonymize_candidate({
            "source": "djinni",
            "id": cid,
            "title": title,
            "salary": job_scraper._clean_text(salary_m.group(0) if salary_m else ""),
            "city": job_scraper._clean_text(loc_m.group(1) if loc_m else ""),
            "experience_years": int(exp_m.group(1)) if exp_m else None,
            "snippet": snippet,
            "skills": _skills_from_text(title, snippet),
            "url": urllib.parse.urljoin(DJINNI_DEVELOPERS_URL, path),
        }))
    return [c for c in cards if c["title"]]


def scrape_djinni_candidates(args, log=None, fetch=None):
    log = log or (lambda msg: print(msg, file=sys.stderr))
    if fetch is None:
        email = (getattr(args, "djinni_email", None) or "").strip()
        password = getattr(args, "djinni_password", None) or ""
        if not email or not password:
            log("[djinni-cv] нет входа — владелец задаёт email/пароль djinni.co в админке")
            return []
        try:
            sess = board_auth.djinni_login(email, password, log=log)
        except Exception as e:
            log(f"[djinni-cv] вход не удался: {e}")
            return []
        fetch = sess.get
    terms = job_scraper.fallback_search_terms(args)
    regions = job_scraper.parse_regions(args.region) or [None]
    all_pages = bool(getattr(args, "all_pages", False))
    page_limit = CANDIDATE_MAX_PAGES if all_pages else max(1, args.pages)
    found = []
    seen = set()
    for ki, keywords in enumerate(terms):
        if len(terms) > 1 and keywords:
            log(f"[djinni-cv] категория «{keywords}»")
        for ri, region in enumerate(regions):
            if region:
                log(f"[djinni-cv] регион «{region}»")
            for page in range(1, page_limit + 1):
                params = {"keywords": keywords}
                if region:
                    params["region"] = region
                if page > 1:
                    params["page"] = page
                url = f"{DJINNI_DEVELOPERS_URL}?{urllib.parse.urlencode(params)}"
                try:
                    html = fetch(url)
                except urllib.error.HTTPError as e:
                    log(f"[djinni-cv] HTTP {e.code} на странице {page} — публичная лента может быть закрыта без входа")
                    break
                except Exception as e:
                    log(f"[djinni-cv] ошибка на странице {page}: {e}")
                    break
                if isinstance(html, str) and board_auth.djinni_page_requires_login(html):
                    log("[djinni-cv] лента всё ещё требует вход — сессия не принята")
                    break
                batch = parse_djinni_candidates(html if isinstance(html, str) else "")
                new = [c for c in batch if c["id"] not in seen]
                if not new:
                    break
                seen.update(c["id"] for c in new)
                found.extend(new)
                log(f"[djinni-cv] страница {page}: {len(new)} карточек")
                if page < page_limit:
                    time.sleep(args.delay)
            if ri + 1 < len(regions):
                time.sleep(args.delay)
        if ki + 1 < len(terms):
            time.sleep(args.delay)
    return found


def workua_resume_url(query, page_num, city_slug=None):
    base = f"https://www.work.ua/resumes-{city_slug}/" if city_slug else "https://www.work.ua/resumes/"
    q = (query or "").strip().strip("/")
    if q:
        slug = urllib.parse.quote(q.replace(" ", "+"), safe="+")
        base = f"{base}{slug}/"
    if page_num > 1:
        return f"{base}?page={int(page_num)}"
    return base


WORKUA_RESUME_EXTRACT_JS = """
cards => cards.map(c => {
    const a = c.querySelector
        ? (c.querySelector('h2 a[href*="/resumes/"], h3 a[href*="/resumes/"], a[href*="/resumes/"]') || (c.tagName === 'A' ? c : null))
        : null;
    const node = a || c;
    const href = (node && (node.href || node.getAttribute && node.getAttribute('href'))) || '';
    const card = (a && a.closest && (a.closest('div.card, article') || a.parentElement)) || c;
    const salaryIcon = card.querySelector && card.querySelector('.glyphicon-hryvnia-fill');
    const salary = salaryIcon
        ? (salaryIcon.parentElement.querySelector('.strong-600')?.innerText.trim() || '')
        : ((card.querySelector && (card.querySelector('.salary, .strong-600')?.innerText.trim() || '')) || '');
    const locEl = card.querySelector && card.querySelector('.glyphicon-location, .glyphicon-map-marker');
    let location = '';
    if (locEl) {
        const wrap = locEl.closest('.text-indent, p, div');
        location = wrap ? wrap.innerText.trim() : '';
    }
    const desc = (card.querySelector && card.querySelector('p.ellipsis, .ellipsis, p')?.innerText.trim()) || '';
    return {
        title: a ? a.innerText.trim() : (node.innerText || '').trim(),
        url: href,
        salary,
        location: location.replace(/^[\\s,]+/, ''),
        snippet: desc,
    };
})
"""


def scrape_workua_candidates(args, log=None, info=None, page=None):
    log = log or (lambda msg: print(msg, file=sys.stderr))
    terms = job_scraper.fallback_search_terms(args)
    all_pages = bool(getattr(args, "all_pages", False))
    found = []
    seen_urls = set()

    remote_mode = job_scraper.normalize_remote_mode(getattr(args, "remote", None))
    targets, unresolved = job_scraper.workua_search_targets(args.region, remote_mode, reservation=False)
    for name in unresolved:
        log(f"[workua-cv] город «{name}» не знаю — пропускаю")
    if unresolved and targets == [(None, None)]:
        log("[workua-cv] ни один город не распознан — ищу по всей Украине")

    def parse_listing(listing_page, url, page_num):
        try:
            listing_page.goto(url, timeout=45000)
            if job_scraper.workua_wait_challenge_clear(listing_page):
                raise RuntimeError("challenge")
            listing_page.wait_for_selector(
                'a[href*="/resumes/"], div.card.resume-link, div.card.card-hover, div.card',
                timeout=20000,
            )
        except Exception:
            if job_scraper.workua_wait_challenge_clear(listing_page, timeout=8000) or job_scraper.workua_page_blocked(listing_page):
                log(f"[workua-cv] страница {page_num}: Cloudflare, останавливаюсь")
                if info is not None:
                    info["challenge_stopped"] = True
                return None, True
            here = getattr(listing_page, "url", "") or ""
            log(f"[workua-cv] страница {page_num}: не удалось загрузить ({title or here or 'нет карточек'})")
            return None, False
        selector = 'a[href*="/resumes/"], div.card.resume-link, div.card.card-hover, div.card'
        raw = listing_page.eval_on_selector_all(selector, WORKUA_RESUME_EXTRACT_JS)
        last = job_scraper._workua_last_page(listing_page) if all_pages else None
        return (raw, last), False

    def consume(raw, last, page_limit):
        added = 0
        if last:
            needed = min(int(last), CANDIDATE_MAX_PAGES)
            if needed != page_limit:
                log(f"[workua-cv] по пагинации страниц: {needed}")
            page_limit = needed
        for row in raw or []:
            url = (row.get("url") or "").split("?")[0]
            if not url or url in seen_urls or not re.search(r"/resumes/\d+", url):
                continue
            cand = anonymize_candidate({
                "source": "workua",
                "id": url.rstrip("/").split("/")[-1],
                "title": row.get("title"),
                "salary": row.get("salary"),
                "city": row.get("location"),
                "snippet": row.get("snippet"),
                "url": url,
            })
            if not cand["title"]:
                continue
            seen_urls.add(url)
            found.append(cand)
            added += 1
        return page_limit, added

    def run_cities(open_page, close_page=lambda: None):
        try:
            stopped_all = False
            for ki, query in enumerate(terms):
                if len(terms) > 1 and query:
                    log(f"[workua-cv] категория «{query}»")
                for ti, (region_label, slug) in enumerate(targets):
                    if slug:
                        log(f"[workua-cv] регион «{region_label}» → {slug}")
                    page_limit = CANDIDATE_MAX_PAGES if all_pages else max(1, args.pages)
                    page_num = 1
                    stopped = False
                    while page_num <= page_limit:
                        url = workua_resume_url(query, page_num, slug)
                        listing = open_page()
                        parsed, stopped = parse_listing(listing, url, page_num)
                        if parsed is None:
                            break
                        raw, last = parsed
                        page_limit, n_new = consume(raw, last, page_limit)
                        if not n_new:
                            break
                        log(f"[workua-cv] страница {page_num}: {n_new} карточек")
                        page_num += 1
                        if page_num <= page_limit:
                            time.sleep(args.delay)
                    if stopped:
                        stopped_all = True
                        break
                    if ti + 1 < len(targets):
                        time.sleep(args.delay)
                if stopped_all:
                    break
                if ki + 1 < len(terms):
                    time.sleep(args.delay)
        finally:
            close_page()

    if page is not None:
        run_cities(lambda: page)
        return found

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("Playwright не установлен — work.ua резюме недоступны")
        raise RuntimeError("playwright not installed")

    email = (getattr(args, "workua_email", None) or "").strip()
    password = getattr(args, "workua_password", None) or ""

    with sync_playwright() as p:
        browser = job_scraper._launch_playwright_chromium(p)
        state = {"page": None, "ctx": None, "storage": None}
        storage = _load_workua_state()
        if storage:
            log("[workua-cv] повторно использую сохранённую сессию work.ua")
        elif email and password:
            login_ctx = job_scraper._workua_browser_context(browser)
            login_page = login_ctx.new_page()
            try:
                board_auth.workua_login(login_page, email, password, log=log)
                storage = login_ctx.storage_state()
                _save_workua_state(storage)
            except Exception as e:
                log(f"[workua-cv] вход не удался: {e}")
                log("[workua-cv] пробую публичную ленту резюме без кабинета")
                _clear_workua_state()
                storage = None
            finally:
                try:
                    login_ctx.close()
                except Exception:
                    pass
        else:
            log("[workua-cv] нет входа — публичная лента, кабинет работодателя в админке не задан")
        state["storage"] = storage

        def open_page():
            if state["page"] is not None:
                try:
                    state["page"].close()
                except Exception:
                    pass
                state["page"] = None
            if state["ctx"] is not None:
                try:
                    state["ctx"].close()
                except Exception:
                    pass
                state["ctx"] = None
            kwargs = {}
            if state["storage"]:
                kwargs["storage_state"] = state["storage"]
            state["ctx"] = job_scraper._workua_browser_context(browser, **kwargs)
            state["page"] = state["ctx"].new_page()
            return state["page"]

        def close_page():
            if state["page"] is not None:
                try:
                    state["page"].close()
                except Exception:
                    pass
                state["page"] = None
            if state["ctx"] is not None:
                try:
                    state["ctx"].close()
                except Exception:
                    pass
                state["ctx"] = None

        try:
            run_cities(open_page, close_page)
            if not found and state["storage"] and email and password:
                log("[workua-cv] сохранённая сессия не дала карточек — вхожу заново")
                _clear_workua_state()
                state["storage"] = None
                login_ctx = job_scraper._workua_browser_context(browser)
                login_page = login_ctx.new_page()
                try:
                    board_auth.workua_login(login_page, email, password, log=log)
                    state["storage"] = login_ctx.storage_state()
                    _save_workua_state(state["storage"])
                except Exception as e:
                    log(f"[workua-cv] повторный вход не удался: {e}")
                    log("[workua-cv] пробую публичную ленту резюме без кабинета")
                finally:
                    try:
                        login_ctx.close()
                    except Exception:
                        pass
                run_cities(open_page, close_page)
        finally:
            browser.close()
    return found


def scrape_all_candidates(args, log=None, info=None, fetch=None, page=None):
    """Собрать карточки с выбранных источников. jooble пропускается."""
    log = log or (lambda msg: print(msg, file=sys.stderr))
    info = info if info is not None else {}
    sources = list(getattr(args, "sources", None) or [getattr(args, "source", None)])
    sources = [s for s in sources if s]
    results = []
    if "jooble" in sources:
        log("[jooble-cv] jooble.org не публикует резюме кандидатов — пропускаю")
    if "djinni" in sources:
        try:
            results.extend(scrape_djinni_candidates(args, log=log, fetch=fetch))
        except Exception as e:
            log(f"djinni.co (кандидаты) недоступен: {e}")
    if "rabotaua" in sources:
        try:
            results.extend(scrape_rabotaua_candidates(args, log=log, fetch=fetch))
        except Exception as e:
            log(f"robota.ua (кандидаты) недоступен: {e}")
    if "workua" in sources:
        try:
            results.extend(scrape_workua_candidates(args, log=log, info=info, page=page))
        except RuntimeError as e:
            log(f"work.ua (кандидаты) недоступен: {e}")
        except Exception as e:
            log(f"work.ua (кандидаты) недоступен: {e}")
    return results


def _salary_values(text):
    nums = []
    for m in re.finditer(r"(\d[\d\s]{2,8})", text or ""):
        n = int(re.sub(r"\s+", "", m.group(1)))
        if 200 <= n <= 500000:
            nums.append(n)
    return nums


def _experience_bucket(years):
    if years is None:
        return None
    n = int(years)
    if n <= 1:
        return "0–1"
    if n <= 3:
        return "2–3"
    if n <= 5:
        return "4–5"
    return "6+"


def _pick_examples(candidates, limit=8):
    """Разношёрстные публичные карточки как примеры формулировок, без PII."""
    ranked = []
    for c in candidates:
        title = (c.get("title") or "").strip()
        if not title:
            continue
        snippet = (c.get("snippet") or "").strip()
        score = 0
        if snippet:
            score += 4
        if c.get("skills"):
            score += 1
        if c.get("salary"):
            score += 1
        if c.get("experience_years") is not None:
            score += 1
        ranked.append((score, c))
    ranked.sort(key=lambda row: -row[0])
    out = []
    seen_title = set()
    seen_snip = set()
    for _, c in ranked:
        title_key = (c.get("title") or "").casefold()
        snip_key = (c.get("snippet") or "").casefold()[:90]
        if title_key in seen_title and (not snip_key or snip_key in seen_snip):
            continue
        seen_title.add(title_key)
        if snip_key:
            seen_snip.add(snip_key)
        out.append({
            "source": c.get("source") or "",
            "title": (c.get("title") or "")[:200],
            "salary": (c.get("salary") or "")[:80],
            "city": (c.get("city") or "")[:80],
            "experience_years": c.get("experience_years"),
            "skills": (c.get("skills") or [])[:8],
            "snippet": (c.get("snippet") or "")[:280],
            "url": (c.get("url") or "")[:300],
        })
        if len(out) >= limit:
            break
    return out


def analyze_market(candidates, cv_text=""):
    """Агрегаты по рынку + примеры формулировок + пробелы относительно резюме."""
    skill_counts = collections.Counter()
    title_counts = collections.Counter()
    salaries = []
    years = []
    by_source = collections.Counter()
    buckets = collections.Counter()
    for c in candidates:
        by_source[c.get("source") or ""] += 1
        title = strip_contacts(c.get("title") or "")
        if title:
            title_counts[title] += 1
        for s in c.get("skills") or []:
            skill_counts[s.casefold()] += 1
        salaries.extend(_salary_values(c.get("salary") or ""))
        if c.get("experience_years") is not None:
            years.append(int(c["experience_years"]))
            bucket = _experience_bucket(c["experience_years"])
            if bucket:
                buckets[bucket] += 1
        for extra in _skills_from_text(c.get("title") or ""):
            skill_counts[extra.casefold()] += 1

    top_skills = skill_counts.most_common(20)
    salaries.sort()
    median = salaries[len(salaries) // 2] if salaries else None
    cv_l = (cv_text or "").casefold()
    missing = []
    present = []
    for skill, count in top_skills:
        if count < 2:
            continue
        if skill in cv_l:
            present.append({"skill": skill, "count": count})
        else:
            missing.append({"skill": skill, "count": count})

    bucket_order = ["0–1", "2–3", "4–5", "6+"]
    return {
        "total": len(candidates),
        "by_source": dict(by_source),
        "top_skills": [{"skill": s, "count": n} for s, n in top_skills],
        "top_titles": [{"title": t, "count": n} for t, n in title_counts.most_common(8)],
        "salary_count": len(salaries),
        "salary_min": salaries[0] if salaries else None,
        "salary_max": salaries[-1] if salaries else None,
        "salary_median": median,
        "experience_avg": round(sum(years) / len(years), 1) if years else None,
        "experience_buckets": [{"label": label, "count": buckets[label]} for label in bucket_order],
        "examples": _pick_examples(candidates),
        "cv_present": present[:12],
        "cv_missing": missing[:12],
        "cv_compared": bool(cv_text and cv_text.strip()),
    }


# ---------------------------------------------------------------------------
# Сверка резюме с рынком: спрос по реальным вакансиям + место среди похожих
# резюме. Только честная статистика по данным, реально собранным в этом
# запросе — маленькую выборку явно помечаем, а не выдаём как уверенный факт.
# ---------------------------------------------------------------------------

MIN_MARKET_SAMPLE = 8
_CORE_SKILL_MIN_FRACTION = 0.2


def percentile_rank(values, x):
    """Доля значений <= x — перцентиль без сторонних библиотек."""
    if not values:
        return None
    return round(100 * sum(1 for v in values if v <= x) / len(values))


def compute_job_skill_demand(jobs, vocabulary, min_fraction=_CORE_SKILL_MIN_FRACTION):
    """Доля вакансий, где встречается каждый навык из словаря — реальный, посчитанный сейчас
    спрос рынка. Вакансии — это связная проза, а не список через запятую, поэтому вместо повторной
    токенизации текста (что даёт мусорные обрывки фраз) ищем по границе слова каждый уже известный
    атомарный навык из словаря (собранного из структурированных данных резюме кандидатов).
    "Ядровым" считаем навык, встретившийся в min_fraction и выше вакансий."""
    total = len(jobs or [])
    if not total or not vocabulary:
        return {"skills": [], "sample_size": total}
    texts = [
        " ".join(filter(None, [job.get("title"), job.get("description")])).casefold()
        for job in jobs
    ]
    counts = collections.Counter()
    for skill in vocabulary:
        pattern = re.compile(r"(?<![a-zа-яё0-9])" + re.escape(skill) + r"(?![a-zа-яё0-9])", re.I)
        count = sum(1 for text in texts if pattern.search(text))
        if count:
            counts[skill] = count
    core = [
        {"skill": skill, "fraction": round(count / total, 2), "count": count}
        for skill, count in counts.most_common(40)
        if count / total >= min_fraction
    ]
    return {"skills": core, "sample_size": total}


def compute_resume_market_fit(candidates, jobs, resume_data, cv_text=""):
    """Место резюме относительно реального рынка: покрытие спроса вакансий + перцентиль по
    навыкам/опыту среди похожих публичных резюме. Все проценты — из данных, собранных в этом же
    запросе; при маленькой выборке соответствующий показатель помечается как недостаточный,
    а не выдаётся приблизительной цифрой."""
    cv_l = (cv_text or "").casefold()
    resume_skills = {
        s.strip().casefold() for s in (resume_data.get("skills") or "").split(",") if s.strip()
    }

    skill_counts = collections.Counter()
    candidate_years = []
    for c in candidates or []:
        skills = {s.casefold() for s in (c.get("skills") or [])}
        skills.update(s.casefold() for s in _skills_from_text(c.get("title") or ""))
        for s in skills:
            skill_counts[s] += 1
        if c.get("experience_years") is not None:
            candidate_years.append(int(c["experience_years"]))

    top_market_skills = {s for s, _ in skill_counts.most_common(20)}
    vocabulary = top_market_skills | resume_skills

    demand = compute_job_skill_demand(jobs, vocabulary)
    demand_covered = [
        s for s in demand["skills"] if s["skill"] in resume_skills or s["skill"] in cv_l
    ]
    demand_missing = [s for s in demand["skills"] if s not in demand_covered]
    demand_coverage_pct = (
        round(100 * len(demand_covered) / len(demand["skills"])) if demand["skills"] else None
    )

    candidate_overlaps = []
    if top_market_skills:
        for c in candidates or []:
            skills = {s.casefold() for s in (c.get("skills") or [])}
            candidate_overlaps.append(len(skills & top_market_skills))
    my_skills = resume_skills or {s.casefold() for s in _skills_from_text(cv_text)}
    my_overlap = len(my_skills & top_market_skills)

    skill_percentile = None
    skill_percentile_insufficient = True
    if len(candidate_overlaps) >= MIN_MARKET_SAMPLE:
        skill_percentile = percentile_rank(candidate_overlaps, my_overlap)
        skill_percentile_insufficient = False

    my_years = resume_builder.total_experience_years(resume_data.get("experience"))
    experience_percentile = None
    experience_percentile_insufficient = True
    if len(candidate_years) >= MIN_MARKET_SAMPLE and my_years is not None:
        experience_percentile = percentile_rank(candidate_years, my_years)
        experience_percentile_insufficient = False

    return {
        "jobs_sample_size": demand["sample_size"],
        "candidates_sample_size": len(candidates or []),
        "demand_coverage_pct": demand_coverage_pct,
        "demand_covered_skills": [s["skill"] for s in demand_covered[:12]],
        "demand_missing_skills": [s["skill"] for s in demand_missing[:12]],
        "skill_percentile": skill_percentile,
        "skill_percentile_insufficient_data": skill_percentile_insufficient,
        "experience_percentile": experience_percentile,
        "experience_percentile_insufficient_data": experience_percentile_insufficient,
        "my_experience_years": my_years,
    }

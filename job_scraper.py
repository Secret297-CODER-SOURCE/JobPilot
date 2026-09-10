#!/usr/bin/env python3
"""
Парсер вакансий с djinni.co, work.ua, robota.ua (rabota.ua) и jooble.org.

Источники:
  djinni    - работает через обычные HTTP-запросы (urllib из stdlib),
              зависимостей не требует.
  workua    - work.ua закрыт Cloudflare managed challenge (JS-челлендж на
              каждый запрос), обычным HTTP это не пройти. Используется
              headless Chromium через Playwright: он честно исполняет JS
              и проходит челлендж как обычный браузер, без спуфинга.
  rabotaua  - публичный JSON API api.rabota.ua (ключ не нужен). HTML-сайт
              robota.ua закрыт Cloudflare + проверкой navigator.webdriver,
              поэтому берём выдачу с открытого search-эндпоинта, а не
              рендерим страницу.
  jooble    - официальный REST API jooble.org (не скрапинг). Нужен свой
              бесплатный ключ: https://jooble.org/api/about

Установка (нужно только для source=workua):
    python3 -m venv job_scraper_venv
    ./job_scraper_venv/bin/pip install playwright
    ./job_scraper_venv/bin/playwright install chromium

Примеры:
    python3 job_scraper.py --source djinni -k Python --pages 3
    python3 job_scraper.py --source rabotaua -q "python" --region "Київ, Львів" --all-pages
    ./job_scraper_venv/bin/python3 job_scraper.py --source workua -q "python" --region Київ --all-pages --output jobs.csv
    python3 job_scraper.py --source jooble -q "python" --jooble-key YOUR_KEY --output jobs.csv
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# djinni.co (plain HTTP, stdlib only)
# ---------------------------------------------------------------------------

DJINNI_BASE_URL = "https://djinni.co/jobs/"
DJINNI_RESERVATION_URL = "https://djinni.co/jobs/l-reservation/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Удалёнка на площадках устроена по-разному: djinni — employment=remote,
# work.ua — отдельный «регион» /jobs-remote/, robota.ua — scheduleId=3,
# jooble — только location="Remote". «include» = выбранные города ∪ удалёнка.
REMOTE_ONLY = "remote"
REMOTE_INCLUDE = "include"
RABOTA_REMOTE_SCHEDULE_ID = 3  # проверено по api.rabota.ua: python 236 → 64


def normalize_remote_mode(value):
    v = (value or "").strip().lower()
    if v in (REMOTE_ONLY, "only", "only_remote"):
        return REMOTE_ONLY
    if v in (REMOTE_INCLUDE, "also", "with_cities", "remote_or_city"):
        return REMOTE_INCLUDE
    return ""


def want_reservation(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _append_meta(job, *parts):
    extra = [p for p in parts if p]
    if not extra:
        return job
    existing = [p.strip() for p in (job.get("meta") or "").split("·") if p.strip()]
    for part in extra:
        if part not in existing:
            existing.append(part)
    job["meta"] = " · ".join(existing)
    return job

_ITEM_START_RE = re.compile(r'<div id="job-item-(\d+)"')
_LINK_RE = re.compile(r'href="(/jobs/[^"?#]+/)"')
_TITLE_RE = re.compile(r'<h2 class="job-item__position[^"]*"[^>]*>(.*?)</h2>', re.S)
_COMPANY_RE = re.compile(
    r'<span class="small text-gray-800 opacity-75 font-weight-500">(.*?)</span>', re.S
)
_SALARY_RE = re.compile(
    r'<strong class="text-success text-nowrap small">(.*?)</strong>', re.S
)
_HEADER_END_RE = re.compile(r'</header>')
_TAGS_DIV_RE = re.compile(r'<div class="job-item__tags">')
_META_SPAN_RE = re.compile(
    r'<span class="(?:text-nowrap|location-text)"[^>]*>(.*?)</span>', re.S
)
_DESCRIPTION_RE = re.compile(r'<span class="js-truncated-text">(.*?)</span>', re.S)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")


def _clean_text(raw):
    text = _TAG_STRIP_RE.sub("", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


_BLOCK_BREAK_RE = re.compile(r"(?i)<(br|/p|/div|/h[1-6]|/tr|/li)[^>]*>")
_LI_OPEN_RE = re.compile(r"(?i)<li[^>]*>")
_HEAD_RE = re.compile(r"(?is)<head[^>]*>.*?</head>")
_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")


def html_to_text(raw):
    """HTML описания вакансии → читаемый текст с абзацами и списками."""
    text = raw or ""
    text = _HEAD_RE.sub(" ", text)
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = _LI_OPEN_RE.sub("\n• ", text)
    text = _BLOCK_BREAK_RE.sub("\n", text)
    text = _TAG_STRIP_RE.sub("", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _parse_djinni_jobs(page_html):
    starts = [m.start() for m in _ITEM_START_RE.finditer(page_html)]
    ids = [m.group(1) for m in _ITEM_START_RE.finditer(page_html)]
    blocks = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(page_html)
        blocks.append((ids[i], page_html[start:end]))

    jobs = []
    for job_id, block in blocks:
        link_m = _LINK_RE.search(block)
        title_m = _TITLE_RE.search(block)
        company_m = _COMPANY_RE.search(block)
        salary_m = _SALARY_RE.search(block)
        desc_m = _DESCRIPTION_RE.search(block)

        header_end = _HEADER_END_RE.search(block)
        tags_start = _TAGS_DIV_RE.search(block)
        meta_text = ""
        if header_end and tags_start:
            meta_block = block[header_end.end():tags_start.start()]
            meta_parts = [_clean_text(s) for s in _META_SPAN_RE.findall(meta_block)]
            meta_parts = [p for p in meta_parts if p]
            meta_text = " · ".join(meta_parts)

        jobs.append({
            "source": "djinni",
            "id": job_id,
            "title": _clean_text(title_m.group(1)) if title_m else "",
            "company": _clean_text(company_m.group(1)) if company_m else "",
            "salary": _clean_text(salary_m.group(1)) if salary_m else "",
            "meta": meta_text,
            "url": urllib.parse.urljoin(DJINNI_BASE_URL, link_m.group(1)) if link_m else "",
            "description": _clean_text(desc_m.group(1)) if desc_m else "",
        })
    return jobs


def djinni_search_url(params, page=1, reservation=False):
    base = DJINNI_RESERVATION_URL if reservation else DJINNI_BASE_URL
    page_params = dict(params or {})
    if page > 1:
        page_params["page"] = page
    qs = urllib.parse.urlencode(page_params)
    return f"{base}?{qs}" if qs else base


def djinni_search_passes(args):
    """Наборы query-параметров djinni: категории × регионы + при include отдельный employment=remote."""
    keywords = parse_keywords(getattr(args, "keyword", None)) or [None]
    query = (getattr(args, "query", None) or "").strip() or None
    remote_mode = normalize_remote_mode(getattr(args, "remote", None))
    regions = parse_regions(getattr(args, "region", None)) or [None]
    reservation = want_reservation(getattr(args, "reservation", False))
    many_kw = len([k for k in keywords if k]) > 1
    passes = []
    for kw in keywords:
        params = {}
        if kw:
            params["primary_keyword"] = kw
        if query:
            params["all_keywords"] = query
        for key, value in args.param or []:
            params[key] = value
        if remote_mode == REMOTE_ONLY:
            params["employment"] = "remote"
        for region in regions:
            page_params = dict(params)
            if region:
                page_params["region"] = region
            if many_kw and kw and region:
                label = f"{kw} · {region}"
            elif many_kw and kw:
                label = kw
            else:
                label = region
            passes.append((label, page_params))
        if remote_mode == REMOTE_INCLUDE and any(regions):
            extra = dict(params)
            extra["employment"] = "remote"
            extra.pop("region", None)
            extra_label = f"{kw} · віддалено" if many_kw and kw else "віддалено"
            passes.append((extra_label, extra))
    return reservation, passes


def scrape_djinni(args, log=None):
    log = log or (lambda msg: print(msg, file=sys.stderr))
    reservation, passes = djinni_search_passes(args)
    if reservation:
        log("[djinni] бронювання → /jobs/l-reservation/")
    all_jobs = []
    seen_ids = set()
    for ri, (region, region_params) in enumerate(passes):
        if region:
            log(f"[djinni] регион «{region}»")
        if region_params.get("employment") == "remote":
            log("[djinni] тільки віддалені (employment=remote)")
        for page in range(1, args.pages + 1):
            url = djinni_search_url(region_params, page=page, reservation=reservation)

            try:
                page_html = _fetch(url)
            except urllib.error.HTTPError as e:
                log(f"HTTP {e.code} на странице {page}, останавливаюсь.")
                break
            except urllib.error.URLError as e:
                log(f"Ошибка сети на странице {page}: {e.reason}")
                break

            jobs = _parse_djinni_jobs(page_html)
            if reservation:
                for job in jobs:
                    _append_meta(job, "бронювання")
            new_jobs = [j for j in jobs if j["id"] not in seen_ids]
            if not new_jobs:
                break
            seen_ids.update(j["id"] for j in new_jobs)
            all_jobs.extend(new_jobs)
            log(f"[djinni] страница {page}: найдено {len(new_jobs)} вакансий")

            if page < args.pages:
                time.sleep(args.delay)
        if ri + 1 < len(passes):
            time.sleep(args.delay)

    return all_jobs


# ---------------------------------------------------------------------------
# jooble.org — официальный REST API (не скрапинг сайта).
# Ключ бесплатный, выдаётся самим Jooble: https://jooble.org/api/about
# ---------------------------------------------------------------------------

JOOBLE_API_URL = "https://jooble.org/api/{key}"


def _parse_jooble_job(raw):
    return {
        "source": "jooble",
        "id": str(raw.get("id") or raw.get("link") or ""),
        "title": (raw.get("title") or "").strip(),
        "company": (raw.get("company") or "").strip(),
        "salary": (raw.get("salary") or "").strip(),
        "meta": " · ".join(p for p in [
            (raw.get("location") or "").strip(),
            (raw.get("type") or "").strip(),
            (raw.get("updated") or "").strip(),
        ] if p),
        "url": (raw.get("link") or "").strip(),
        "description": _clean_text(raw.get("snippet") or ""),
    }


def scrape_jooble(args, api_key, log=None):
    log = log or (lambda msg: print(msg, file=sys.stderr))
    if not api_key:
        raise RuntimeError(
            "Нет ключа Jooble API. Получи бесплатный ключ на https://jooble.org/api/about "
            "и сохрани его в разделе «Настройки ИИ» → Jooble."
        )

    terms = fallback_search_terms(args)
    locations = parse_regions(args.region) or [""]
    remote_mode = normalize_remote_mode(getattr(args, "remote", None))
    if remote_mode == REMOTE_ONLY:
        locations = ["Remote"]
    elif remote_mode == REMOTE_INCLUDE and any(locations):
        if not any(_fold_city_name(loc) == "remote" for loc in locations):
            locations.append("Remote")
    if want_reservation(getattr(args, "reservation", False)):
        log("[jooble] у API нет фильтра бронювання — ищу без него")
    all_jobs = []
    seen_ids = set()
    url = JOOBLE_API_URL.format(key=api_key)

    for ki, keywords in enumerate(terms):
        if len(terms) > 1 and keywords:
            log(f"[jooble] категория «{keywords}»")
        for li, location in enumerate(locations):
            if location:
                log(f"[jooble] регион «{location}»")
            for page in range(1, args.pages + 1):
                body = json.dumps({
                    "keywords": keywords,
                    "location": location,
                    "page": str(page),
                }).encode("utf-8")
                req = urllib.request.Request(
                    url, data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                except urllib.error.HTTPError as e:
                    detail = e.read().decode("utf-8", errors="replace")
                    log(f"[jooble] HTTP {e.code} на странице {page}: {detail[:200]}")
                    break
                except urllib.error.URLError as e:
                    log(f"[jooble] ошибка сети на странице {page}: {e.reason}")
                    break

                raw_jobs = data.get("jobs", [])
                if not raw_jobs:
                    break

                jobs = [_parse_jooble_job(r) for r in raw_jobs]
                new_jobs = [j for j in jobs if j["id"] not in seen_ids]
                if not new_jobs:
                    break
                seen_ids.update(j["id"] for j in new_jobs)
                all_jobs.extend(new_jobs)
                log(f"[jooble] страница {page}: найдено {len(new_jobs)} вакансий "
                    f"(всего по запросу: {data.get('totalCount', '?')})")

                if page < args.pages:
                    time.sleep(args.delay)
            if li + 1 < len(locations):
                time.sleep(args.delay)
        if ki + 1 < len(terms):
            time.sleep(args.delay)

    return all_jobs


# ---------------------------------------------------------------------------
# robota.ua / rabota.ua — публичный JSON API (ключ не нужен).
# HTML-фронт закрыт Cloudflare + webdriver-check; search API отдаёт JSON
# обычным GET. Документация де-факто: GET /vacancy/search + /dictionary/city.
# ---------------------------------------------------------------------------

RABOTA_SEARCH_URL = "https://api.rabota.ua/vacancy/search"
RABOTA_CITIES_URL = "https://api.rabota.ua/dictionary/city"
RABOTA_VACANCY_DETAIL_URL = "https://api.rabota.ua/vacancy?id={vacancy_id}"
RABOTA_VACANCY_URL = "https://robota.ua/company{company_id}/vacancy{vacancy_id}"
DJINNI_FULL_DESC_RE = re.compile(
    r'(?is)<div[^>]*class="[^"]*job-post__description[^"]*"[^>]*>(.*?)</div>'
)
RABOTA_PAGE_SIZE = 40
RABOTA_MAX_PAGES = 80  # защитный потолок (~3200 вакансий) в режиме «все страницы»

_rabota_cities_cache = None


def _fetch_json(url, timeout=20, headers=None):
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged.update(headers)
    req = urllib.request.Request(
        url,
        headers=merged,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset, errors="replace"))


def _uah(n):
    return f"{int(n):,}".replace(",", " ")


def format_rabota_salary(raw):
    comment = (raw.get("salaryComment") or "").strip()
    lo = int(raw.get("salaryFrom") or 0)
    hi = int(raw.get("salaryTo") or 0)
    sal = int(raw.get("salary") or 0)
    if lo and hi:
        text = f"{_uah(lo)}–{_uah(hi)} грн" if lo != hi else f"{_uah(lo)} грн"
    elif lo:
        text = f"от {_uah(lo)} грн"
    elif hi:
        text = f"до {_uah(hi)} грн"
    elif sal:
        text = f"{_uah(sal)} грн"
    else:
        text = ""
    if comment and comment not in text:
        text = f"{text} ({comment})".strip() if text else comment
    return text


def rabota_has_reservation(raw):
    for badge in raw.get("badges") or []:
        name = (badge.get("name") or "").casefold()
        if "брон" in name:
            return True
    return False


def parse_rabota_job(raw):
    job_id = str(raw.get("id") or "")
    company_id = raw.get("notebookId") or ""
    date = (raw.get("date") or "").split("T")[0]
    city = (raw.get("cityName") or "").strip()
    meta_parts = [p for p in [city, date] if p]
    if raw.get("hot"):
        meta_parts.append("гаряча")
    if rabota_has_reservation(raw):
        meta_parts.append("бронювання")
    return {
        "source": "rabotaua",
        "id": job_id,
        "title": (raw.get("name") or "").strip(),
        "company": (raw.get("companyName") or "").strip(),
        "salary": format_rabota_salary(raw),
        "meta": " · ".join(meta_parts),
        "url": RABOTA_VACANCY_URL.format(company_id=company_id, vacancy_id=job_id) if job_id else "",
        "description": html_to_text(raw.get("description") or raw.get("shortDescription") or ""),
    }


def fetch_rabota_full_description(job_id, fetch=_fetch_json):
    job_id = str(job_id or "").strip()
    if not job_id:
        return ""
    try:
        data = fetch(RABOTA_VACANCY_DETAIL_URL.format(vacancy_id=urllib.parse.quote(job_id, safe="")))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return html_to_text(data.get("description") or data.get("shortDescription") or "")


def fetch_djinni_full_description(url, fetch=_fetch):
    url = (url or "").strip()
    if not url:
        return ""
    try:
        page = fetch(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return ""
    match = DJINNI_FULL_DESC_RE.search(page or "")
    if not match:
        return ""
    return html_to_text(match.group(1))


def fetch_full_job_description(job, fetch_json=_fetch_json, fetch_html=_fetch):
    """Полный текст вакансии для карточки. Поиск отдаёт только короткий анонс."""
    job = job or {}
    current = (job.get("description") or "").strip()
    source = (job.get("source") or "").strip()
    full = ""
    if source == "rabotaua":
        full = fetch_rabota_full_description(job.get("id"), fetch=fetch_json)
    elif source == "djinni":
        full = fetch_djinni_full_description(job.get("url"), fetch=fetch_html)
    if full and len(full) > len(current):
        return full
    return current


def _fold_city_name(name):
    return (name or "").strip().casefold().replace("ё", "е").replace("’", "'")


def parse_regions(region):
    """Разобрать один или несколько регионов: строка «Київ, Львів», список или одно имя."""
    if region is None:
        return []
    if isinstance(region, (list, tuple)):
        out = []
        seen = set()
        for item in region:
            for part in parse_regions(item):
                key = _fold_city_name(part)
                if key in seen:
                    continue
                seen.add(key)
                out.append(part)
        return out
    parts = re.split(r"[,;|/]+", str(region))
    seen = set()
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        key = _fold_city_name(part)
        if key in seen:
            continue
        seen.add(key)
        out.append(part)
    return out


KEYWORD_MAX = 16

# Единый список категорий-подсказок — используется и как чипы в фильтрах поиска/аккаунта,
# и как ориентир для ИИ при подборе «Желаемой должности» (ai_match.suggest_desired_positions),
# чтобы предложения были в тех же категориях, что реально ищутся на площадках.
KEYWORD_CATEGORIES = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Node.js", "PHP",
    ".NET", "Go", "Kotlin", "QA", "DevOps", "Data Science", "Android", "iOS",
]


def parse_keywords(value):
    """Список категорий: «Python, Java», список или одно имя. Не больше KEYWORD_MAX."""
    return parse_regions(value)[:KEYWORD_MAX]


def fallback_search_terms(args):
    """work.ua / robota.ua / jooble: текстовый запрос целиком или каждая категория отдельно."""
    query = (getattr(args, "query", None) or "").strip()
    if query:
        return [query]
    terms = parse_keywords(getattr(args, "keyword", None))
    return terms or [""]


def resolve_rabota_city_id(region, cities):
    """Сопоставить текстовый регион с cityId справочника robota.ua.

    Возвращает int cityId или None, если ничего однозначного не нашлось.
    Цифровая строка считается готовым cityId.
    """
    region = (region or "").strip()
    if not region:
        return None
    if region.isdigit():
        return int(region)

    needle = _fold_city_name(region)
    exact = []
    prefix = []
    for city in cities:
        names = [
            city.get("ua"), city.get("ru"), city.get("en"),
            (city.get("locativeName") or {}).get("ua"),
            (city.get("locativeName") or {}).get("ru"),
        ]
        folded = [_fold_city_name(n) for n in names if n]
        if needle in folded:
            exact.append(city)
            continue
        if len(needle) >= 4 and any(n.startswith(needle) or needle.startswith(n) for n in folded if n):
            prefix.append(city)

    pool = exact or prefix
    if not pool:
        return None
    pool.sort(key=lambda c: c.get("vacancyCount") or 0, reverse=True)
    return int(pool[0]["id"])


def load_rabota_cities(log=None, fetch=_fetch_json):
    global _rabota_cities_cache
    if _rabota_cities_cache is not None:
        return _rabota_cities_cache
    try:
        data = fetch(RABOTA_CITIES_URL)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        if log:
            log(f"[rabotaua] не удалось загрузить справочник городов: {e}")
        return []
    if not isinstance(data, list):
        return []
    _rabota_cities_cache = data
    return data


def scrape_rabotaua(args, log=None, fetch=_fetch_json):
    log = log or (lambda msg: print(msg, file=sys.stderr))
    terms = fallback_search_terms(args)
    remote_mode = normalize_remote_mode(getattr(args, "remote", None))
    reservation = want_reservation(getattr(args, "reservation", False))
    cities_index = None
    targets = [(None, None)]
    if args.region:
        cities_index = load_rabota_cities(log=log, fetch=fetch)
        targets = []
        seen_city_ids = set()
        unresolved = []
        for region in parse_regions(args.region):
            city_id = resolve_rabota_city_id(region, cities_index)
            if city_id is None:
                unresolved.append(region)
                continue
            if city_id in seen_city_ids:
                continue
            seen_city_ids.add(city_id)
            targets.append((region, city_id))
        for name in unresolved:
            log(f"[rabotaua] город «{name}» не найден в справочнике — пропускаю")
        if not targets:
            log("[rabotaua] ни один город не распознан — ищу по всей Украине")
            targets = [(None, None)]

    schedule_id = RABOTA_REMOTE_SCHEDULE_ID if remote_mode == REMOTE_ONLY else None
    runs = [(label, city_id, schedule_id) for label, city_id in targets]
    if remote_mode == REMOTE_INCLUDE and any(city_id is not None for _, city_id in targets):
        runs.append(("віддалено", None, RABOTA_REMOTE_SCHEDULE_ID))
    if reservation:
        log("[rabotaua] бронювання — по бейджу «Бронирование сотрудников» (в API нет query-параметра)")
    if schedule_id:
        log(f"[rabotaua] тільки віддалені (scheduleId={schedule_id})")

    all_jobs = []
    seen_ids = set()

    for ki, keywords in enumerate(terms):
        if len(terms) > 1 and keywords:
            log(f"[rabotaua] категория «{keywords}»")
        for ti, (region_label, city_id, run_schedule) in enumerate(runs):
            if city_id is not None:
                log(f"[rabotaua] регион «{region_label}» → cityId={city_id}")
            elif region_label:
                log(f"[rabotaua] {region_label}")
            all_pages = bool(getattr(args, "all_pages", False))
            page_limit = RABOTA_MAX_PAGES if all_pages else max(1, args.pages)
            page = 0
            while page < page_limit:
                params = {
                    "keyWords": keywords,
                    "count": RABOTA_PAGE_SIZE,
                    "page": page,
                }
                if city_id is not None:
                    params["cityId"] = city_id
                if run_schedule is not None:
                    params["scheduleId"] = run_schedule
                url = f"{RABOTA_SEARCH_URL}?{urllib.parse.urlencode(params)}"

                try:
                    data = fetch(url)
                except urllib.error.HTTPError as e:
                    log(f"[rabotaua] HTTP {e.code} на странице {page + 1}")
                    break
                except urllib.error.URLError as e:
                    log(f"[rabotaua] ошибка сети на странице {page + 1}: {e.reason}")
                    break
                except (TimeoutError, json.JSONDecodeError) as e:
                    log(f"[rabotaua] не разобрал ответ на странице {page + 1}: {e}")
                    break

                if not isinstance(data, dict):
                    log(f"[rabotaua] неожиданный ответ на странице {page + 1}")
                    break
                if data.get("errorMessage"):
                    log(f"[rabotaua] API: {data['errorMessage']}")
                    break

                raw_jobs = data.get("documents") or []
                if not raw_jobs:
                    break
                page_len = len(raw_jobs)
                if reservation:
                    raw_jobs = [r for r in raw_jobs if rabota_has_reservation(r)]

                jobs = [parse_rabota_job(r) for r in raw_jobs]
                new_jobs = [j for j in jobs if j["id"] and j["id"] not in seen_ids]
                if not new_jobs:
                    if reservation and page_len >= RABOTA_PAGE_SIZE:
                        page += 1
                        if page < page_limit:
                            time.sleep(args.delay)
                        continue
                    break
                seen_ids.update(j["id"] for j in new_jobs)
                all_jobs.extend(new_jobs)
                total = data.get("total")
                log(
                    f"[rabotaua] страница {page + 1}: найдено {len(new_jobs)} вакансий "
                    f"(всего по запросу: {total if total is not None else '?'})"
                )

                if all_pages and total:
                    needed = (int(total) + RABOTA_PAGE_SIZE - 1) // RABOTA_PAGE_SIZE
                    page_limit = min(max(needed, 1), RABOTA_MAX_PAGES)

                if page_len < RABOTA_PAGE_SIZE:
                    break
                page += 1
                if page < page_limit:
                    time.sleep(args.delay)
            if ti + 1 < len(runs):
                time.sleep(args.delay)
        if ki + 1 < len(terms):
            time.sleep(args.delay)

    return all_jobs


# ---------------------------------------------------------------------------
# work.ua (Playwright / headless Chromium — see module docstring for why)
# ---------------------------------------------------------------------------

WORKUA_JOB_EXTRACT_JS = """
cards => cards.map(c => {
    const a = c.querySelector('h2 a');
    const salaryIcon = c.querySelector('.glyphicon-hryvnia-fill');
    const salary = salaryIcon ? (salaryIcon.parentElement.querySelector('.strong-600')?.innerText.trim() || '') : '';
    const companyIcon = c.querySelector('.glyphicon-company');
    let company = '';
    let location = '';
    if (companyIcon) {
        const wrap = companyIcon.closest('.text-indent');
        company = wrap.querySelector('.strong-600')?.innerText.trim() || '';
        const spans = Array.from(wrap.querySelectorAll(':scope > span'));
        location = spans.length ? spans[spans.length - 1].innerText.trim() : '';
    }
    const desc = c.querySelector('p.ellipsis')?.innerText.trim() || '';
    return {
        title: a ? a.innerText.trim() : '',
        url: a ? a.href : '',
        salary,
        company,
        location: location.replace(/^[,\\s]+/, ''),
        description: desc,
    };
})
"""

# Публичные city-slug'и work.ua (jobs-kyiv, jobs-lviv, …)
WORKUA_CITY_SLUGS = {
    "київ": "kyiv", "киев": "kyiv", "kyiv": "kyiv", "киеве": "kyiv", "києві": "kyiv",
    "львів": "lviv", "львов": "lviv", "lviv": "lviv", "львове": "lviv", "львові": "lviv",
    "дніпро": "dnipro", "днепр": "dnipro", "dnipro": "dnipro", "дніпрі": "dnipro", "днепре": "dnipro",
    "харків": "kharkiv", "харьков": "kharkiv", "kharkiv": "kharkiv", "харкові": "kharkiv", "харькове": "kharkiv",
    "одеса": "odesa", "одесса": "odesa", "odesa": "odesa", "odessa": "odesa",
    "вінниця": "vinnytsya", "винница": "vinnytsya", "vinnytsia": "vinnytsya", "vinnytsya": "vinnytsya",
    "запоріжжя": "zaporizhzhia", "запорожье": "zaporizhzhia", "zaporizhia": "zaporizhzhia",
    "zaporizhzhia": "zaporizhzhia",
    "миколаїв": "mykolaiv", "николаев": "mykolaiv", "mykolaiv": "mykolaiv",
    "чернівці": "chernivtsi", "черновцы": "chernivtsi", "chernivtsi": "chernivtsi",
    "remote": "remote", "віддалено": "remote", "удаленно": "remote",
    "дистанційно": "remote", "дистанционно": "remote", "удалёнка": "remote", "удаленка": "remote",
}


def resolve_workua_city_slug(region):
    region = (region or "").strip()
    if not region:
        return None
    return WORKUA_CITY_SLUGS.get(_fold_city_name(region))


def workua_search_url(query, page_num, city_slug=None, reservation=False):
    # ?search= на city-URL work.ua игнорирует — запрос в path: /jobs-kyiv/python/
    # Удалёнка — регион /jobs-remote/. Бронювання — раздел /jobs/deferment/.
    if reservation:
        base = "https://www.work.ua/jobs/deferment/"
    elif city_slug:
        base = f"https://www.work.ua/jobs-{city_slug}/"
    else:
        base = "https://www.work.ua/jobs/"
    q = (query or "").strip().strip("/")
    if q:
        slug = urllib.parse.quote(q.replace(" ", "+"), safe="+")
        base = f"{base}{slug}/"
    if page_num > 1:
        return f"{base}?page={int(page_num)}"
    return base


def workua_search_targets(region, remote=None, reservation=False):
    """Список (label, city_slug) и нераспознанные города для выдачи work.ua."""
    unresolved = []
    if want_reservation(reservation):
        return [("бронювання", None)], unresolved
    remote_mode = normalize_remote_mode(remote)
    if remote_mode == REMOTE_ONLY:
        return [("віддалено", "remote")], unresolved
    region_names = parse_regions(region)
    if not region_names:
        return [(None, None)], unresolved
    targets = []
    seen_slugs = set()
    for name in region_names:
        slug = resolve_workua_city_slug(name)
        if not slug:
            unresolved.append(name)
            continue
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        targets.append((name, slug))
    if not targets:
        targets = [(None, None)]
    elif remote_mode == REMOTE_INCLUDE and "remote" not in seen_slugs:
        targets.append(("віддалено", "remote"))
    return targets, unresolved


WORKUA_MAX_PAGES = 80  # защитный потолок в режиме «все страницы»
_WORKUA_REMOTE_LOC_RE = re.compile(r"дистанц|віддален|удален|remote", re.I)

# Номера из блока пагинации work.ua (последняя страница выдачи).
WORKUA_LAST_PAGE_JS = """
() => {
  const root = document.querySelector('ul.pagination, nav.pagination, .pagination');
  if (!root) return null;
  const nums = [];
  for (const el of root.querySelectorAll('a, span')) {
    const t = parseInt((el.innerText || '').trim(), 10);
    if (Number.isFinite(t) && t > 0 && t < 10000) nums.push(t);
    const href = el.getAttribute && el.getAttribute('href');
    if (href) {
      const m = href.match(/[?&]page=(\\d+)/);
      if (m) {
        const n = parseInt(m[1], 10);
        if (Number.isFinite(n) && n > 0 && n < 10000) nums.push(n);
      }
    }
  }
  return nums.length ? Math.max(...nums) : null;
}
"""


def workua_browser_user_agent():
    """UA должен совпадать с ОС Chromium, иначе Cloudflare Turnstile не проходит."""
    if sys.platform == "darwin":
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
    if sys.platform.startswith("linux"):
        return (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
    return USER_AGENT


def _workua_page_title(page):
    try:
        title = page.title()
    except Exception:
        return ""
    return title or ""


def _workua_page_url(page):
    try:
        return page.url or ""
    except Exception:
        return ""


def _workua_is_challenge(title, url=""):
    t = (title or "").lower()
    if "just a moment" in t or "трохи зачекайте" in t or "please wait" in t:
        return True
    u = (url or "").lower()
    return "__cf_chl" in u or "cf-challenge" in u


def workua_page_blocked(page):
    """Cloudflare interstitial: заголовок, редирект cf_chl или текст Turnstile."""
    if _workua_is_challenge(_workua_page_title(page), _workua_page_url(page)):
        return True
    try:
        html = (page.content() or "")[:6000].lower()
    except Exception:
        return False
    return (
        "трохи зачекайте" in html
        or "just a moment" in html
        or "cf-turnstile" in html
        or "cf-chl" in html
        or "перевірка надійності підключення" in html
    )


def workua_wait_challenge_clear(page, timeout=35000):
    """Подождать managed challenge. Не обходим защиту — Chromium сам исполняет JS.

    True — челлендж так и не прошёл.
    """
    if not workua_page_blocked(page):
        return False
    try:
        page.wait_for_function(
            """() => {
                const t = (document.title || '').toLowerCase();
                const u = (location.href || '').toLowerCase();
                if (/just a moment|трохи зачекайте|please wait/.test(t)) return false;
                if (u.indexOf('__cf_chl') >= 0 || u.indexOf('cf-challenge') >= 0) return false;
                return true;
            }""",
            timeout=timeout,
        )
    except Exception:
        pass
    return workua_page_blocked(page)


def _workua_last_page(page):
    try:
        last = page.evaluate(WORKUA_LAST_PAGE_JS)
    except Exception:
        return None
    try:
        last = int(last)
    except (TypeError, ValueError):
        return None
    return last if last >= 1 else None


def _chromium_full_executable(playwright):
    """Путь к полному Chromium, если headless_shell не скачан."""
    from pathlib import Path

    roots = []
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env:
        roots.append(Path(env))
    home = Path.home()
    roots.extend([
        home / "Library/Caches/ms-playwright",
        home / ".cache/ms-playwright",
    ])
    rels = (
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-linux/chrome",
        "chrome-linux64/chrome",
        "chrome-win64/chrome.exe",
    )
    seen = set()
    for root in roots:
        if root in seen or not root.exists():
            continue
        seen.add(root)
        for child in sorted(root.glob("chromium-*"), reverse=True):
            if "headless" in child.name:
                continue
            for rel in rels:
                cand = child / rel
                if cand.is_file():
                    return str(cand)
    exe = getattr(playwright.chromium, "executable_path", None)
    return exe or None


def _launch_playwright_chromium(playwright):
    """Полный Chromium, не chrome-headless-shell: shell чаще отваливается на Turnstile."""
    args = ["--disable-blink-features=AutomationControlled"]
    exe = _chromium_full_executable(playwright)
    kwargs = {"headless": True, "args": args}
    if exe:
        kwargs["executable_path"] = exe
    try:
        return playwright.chromium.launch(**kwargs)
    except Exception as err:
        if "Executable doesn't exist" not in str(err):
            raise
        return playwright.chromium.launch(headless=True, args=args)


def _workua_browser_context(browser, storage_state=None):
    kwargs = {
        "user_agent": workua_browser_user_agent(),
        "locale": "uk-UA",
        "viewport": {"width": 1366, "height": 768},
    }
    if storage_state:
        kwargs["storage_state"] = storage_state
    return browser.new_context(**kwargs)


def scrape_workua(args, log=None, info=None, page=None):
    log = log or (lambda msg: print(msg, file=sys.stderr))
    terms = fallback_search_terms(args)
    all_jobs = []
    seen_urls = set()
    all_pages = bool(getattr(args, "all_pages", False))
    remote_mode = normalize_remote_mode(getattr(args, "remote", None))
    reservation = want_reservation(getattr(args, "reservation", False))
    targets, unresolved = workua_search_targets(args.region, remote_mode, reservation)
    for name in unresolved:
        log(f"[workua] город «{name}» не знаю как подставить в URL — пропускаю")
    if unresolved and targets == [(None, None)]:
        log("[workua] ни один город не распознан — ищу по всей Украине")
    if reservation:
        log("[workua] бронювання → /jobs/deferment/")
        if remote_mode == REMOTE_ONLY:
            log("[workua] удалёнку при бронюванні відсікаю по тексту локації картки")
        elif parse_regions(args.region):
            log("[workua] міста в URL з розділом бронювання не комбінуються — шукаю по всій Україні")

    def parse_listing(page, url, page_num):
        """None — не загрузилось; True — Cloudflare, стоп по всем городам."""
        try:
            page.goto(url, timeout=30000)
            if workua_wait_challenge_clear(page):
                raise RuntimeError("challenge")
            page.wait_for_selector("div.card.job-link", timeout=20000)
        except Exception:
            if workua_wait_challenge_clear(page, timeout=8000) or workua_page_blocked(page):
                log(
                    f"[workua] страница {page_num}: сайт усилил проверку "
                    f"(Cloudflare challenge), останавливаюсь на уже собранных "
                    f"вакансиях. Попробуйте позже или с меньшим числом страниц."
                )
                if info is not None:
                    info["challenge_stopped"] = True
                return None, True
            log(f"[workua] страница {page_num}: не удалось загрузить")
            if info is not None:
                info["load_failed"] = True
            return None, False

        raw_jobs = page.eval_on_selector_all("div.card.job-link", WORKUA_JOB_EXTRACT_JS)
        last = _workua_last_page(page) if all_pages else None
        return (raw_jobs, last), False

    def consume(raw_jobs, last, page_limit, city_slug=None):
        new_jobs = [j for j in raw_jobs if j["url"] and j["url"] not in seen_urls]
        if last:
            needed = min(last, WORKUA_MAX_PAGES)
            if needed != page_limit:
                log(f"[workua] по пагинации страниц: {needed}")
            page_limit = needed
        kept = []
        for j in new_jobs:
            location = j.pop("location")
            j["source"] = "workua"
            j["meta"] = location
            if reservation:
                _append_meta(j, "бронювання")
            if city_slug == "remote" or (reservation and remote_mode == REMOTE_ONLY):
                if reservation and remote_mode == REMOTE_ONLY and not _WORKUA_REMOTE_LOC_RE.search(location or ""):
                    continue
                _append_meta(j, "віддалено")
            seen_urls.add(j["url"])
            kept.append(j)
        all_jobs.extend(kept)
        return page_limit, len(kept)

    def run_cities(open_page, close_page=lambda: None):
        try:
            stopped_all = False
            for ki, query in enumerate(terms):
                if len(terms) > 1 and query:
                    log(f"[workua] категория «{query}»")
                for ti, (region_label, slug) in enumerate(targets):
                    if slug:
                        log(f"[workua] регион «{region_label}» → {slug}")
                    elif region_label:
                        log(f"[workua] {region_label}")
                    page_limit = WORKUA_MAX_PAGES if all_pages else max(1, args.pages)
                    page_num = 1
                    stopped = False
                    while page_num <= page_limit:
                        url = workua_search_url(query, page_num, slug, reservation=reservation)
                        listing_page = open_page()
                        parsed, stopped = parse_listing(listing_page, url, page_num)
                        if parsed is None:
                            break
                        if info is not None:
                            info["listing_ok"] = True
                        raw_jobs, last = parsed
                        page_limit, n_new = consume(raw_jobs, last, page_limit, slug)
                        if n_new:
                            log(f"[workua] страница {page_num}: найдено {n_new} вакансий")
                        elif not raw_jobs:
                            break
                        elif not (reservation and remote_mode == REMOTE_ONLY):
                            break
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
        return all_jobs

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log(
            "Playwright не установлен. Для source=workua нужно:\n"
            "  python3 -m venv job_scraper_venv\n"
            "  ./job_scraper_venv/bin/pip install playwright\n"
            "  ./job_scraper_venv/bin/playwright install chromium\n"
            "и запускать скрипт через ./job_scraper_venv/bin/python3"
        )
        raise RuntimeError("playwright not installed")

    # Повторный goto в той же сессии ловит Cloudflare; каждая страница
    # выдачи — первый заход в новом browser context.
    with sync_playwright() as p:
        browser = _launch_playwright_chromium(p)
        state = {"page": None, "ctx": None}

        def open_page():
            close_page()
            state["ctx"] = _workua_browser_context(browser)
            state["page"] = state["ctx"].new_page()
            return state["page"]

        def close_page():
            for key in ("page", "ctx"):
                obj = state.get(key)
                if obj is None:
                    continue
                try:
                    obj.close()
                except Exception:
                    pass
                state[key] = None

        try:
            run_cities(open_page, close_page)
        finally:
            browser.close()

    return all_jobs


# ---------------------------------------------------------------------------
# Общий вывод
# ---------------------------------------------------------------------------

def print_table(jobs):
    for j in jobs:
        print(f"[{j['source']}] {j['title']} — {j['company']}")
        if j["salary"]:
            print(f"  Зарплата: {j['salary']}")
        if j["meta"]:
            print(f"  {j['meta']}")
        print(f"  {j['url']}")
        print()


def write_csv(jobs, path):
    fieldnames = ["source", "id", "title", "company", "salary", "meta", "url", "description"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for j in jobs:
            writer.writerow({k: j.get(k, "") for k in fieldnames})


def write_json(jobs, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Парсер вакансий с djinni.co, work.ua, robota.ua и jooble.org")
    parser.add_argument("--source", choices=["djinni", "workua", "rabotaua", "jooble"], required=True)
    parser.add_argument("-k", "--keyword", help="djinni: категория/специализация (можно несколько через запятую); workua/rabotaua/jooble: поисковый запрос, если -q не задан")
    parser.add_argument("-q", "--query", help="Текстовый поиск (djinni: all_keywords; workua/rabotaua/jooble: search)")
    parser.add_argument("--region", help="Один или несколько городов через запятую, напр. «Київ, Львів» (djinni / workua / rabotaua / jooble)")
    parser.add_argument(
        "--remote", choices=["any", "remote", "include"], default="any",
        help="Удалёнка: any — не фильтровать; remote — только удалёнка; include — города ∪ удалёнка",
    )
    parser.add_argument(
        "--reservation", action="store_true",
        help="Только вакансии с бронюванням (djinni / work.ua / robota.ua)",
    )
    parser.add_argument(
        "--param", action="append", nargs=2, metavar=("KEY", "VALUE"),
        help="djinni: произвольный доп. параметр запроса (можно несколько раз)"
    )
    parser.add_argument("--jooble-key", help="API-ключ Jooble (https://jooble.org/api/about), нужен для --source jooble")
    parser.add_argument("--pages", type=int, default=1, help="Сколько страниц выдачи забрать (по умолчанию 1; для --all-pages игнорируется)")
    parser.add_argument("--all-pages", action="store_true", dest="all_pages", help="Забрать все страницы выдачи (как «Выгрузить все страницы» в UI)")
    parser.add_argument("--delay", type=float, default=3.0, help="Пауза между запросами страниц, сек (для workua рекомендуется не уменьшать)")
    parser.add_argument("--output", help="Путь к .csv или .json для сохранения результата")

    args = parser.parse_args()
    if not args.keyword and not args.query:
        parser.error("нужно указать -k/--keyword или -q/--query")
    if args.all_pages:
        args.pages = max(args.pages, 30)
    args.remote = "" if args.remote == "any" else args.remote

    try:
        if args.source == "djinni":
            jobs = scrape_djinni(args)
        elif args.source == "jooble":
            jobs = scrape_jooble(args, args.jooble_key)
        elif args.source == "rabotaua":
            jobs = scrape_rabotaua(args)
        else:
            jobs = scrape_workua(args)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    print(f"\nВсего вакансий: {len(jobs)}\n", file=sys.stderr)

    if args.output:
        if args.output.endswith(".json"):
            write_json(jobs, args.output)
        else:
            write_csv(jobs, args.output)
        print(f"Сохранено в {args.output}", file=sys.stderr)
    else:
        print_table(jobs)


if __name__ == "__main__":
    main()

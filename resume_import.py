"""Импорт собственного резюме пользователя с площадки.

Основной путь — вход в ваш аккаунт соискателя (email/пароль). Платформа
сама находит резюме в кабинете. URL оставляем как внутренний разбор
найденной страницы. Чужие ленты и контакты третьих лиц отсюда не собираем.
"""

from __future__ import annotations

import html as html_lib
import json
import re
import urllib.error
import urllib.parse
import urllib.request

import board_auth
import job_scraper

ALLOWED_HOSTS = {
    "djinni.co": "djinni",
    "www.djinni.co": "djinni",
    "djinni.com": "djinni",
    "www.djinni.com": "djinni",
    "work.ua": "workua",
    "www.work.ua": "workua",
    "robota.ua": "rabota",
    "www.robota.ua": "rabota",
    "rabota.ua": "rabota",
    "www.rabota.ua": "rabota",
}

_TAG_RE = re.compile(r"<[^>]+>", re.S)
_SCRIPT_RE = re.compile(r"(?is)<script[^>]*>.*?</script>")
_STYLE_RE = re.compile(r"(?is)<style[^>]*>.*?</style>")
_WS_RE = re.compile(r"\s+")
_H1_RE = re.compile(r"(?is)<h1[^>]*>(.*?)</h1>")
_OG_TITLE_RE = re.compile(
    r'(?is)<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']'
)
_OG_DESC_RE = re.compile(
    r'(?is)<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']'
)
_JSONLD_RE = re.compile(
    r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
)
_SKILL_RE = re.compile(
    r'(?is)<(?:span|a|li|div)[^>]*class=["\'][^"\']*(?:skill|tag|badge)[^"\']*["\'][^>]*>(.*?)</'
)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{8,}\d")
_CHALLENGE_MARKERS = (
    "just a moment",
    "checking your browser",
    "cf-challenge",
    "cf-browser-verification",
    "attention required",
)


class ResumeImportError(ValueError):
    """Понятная ошибка импорта для API."""


def classify_url(url):
    parsed = urllib.parse.urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise ResumeImportError("нужна ссылка http(s) на ваше резюме")
    host = (parsed.hostname or "").lower()
    source = ALLOWED_HOSTS.get(host)
    if not source:
        raise ResumeImportError("поддерживаются только djinni.co, work.ua и robota.ua")
    if not parsed.path or parsed.path == "/":
        raise ResumeImportError("укажите ссылку на страницу резюме, не на главную сайта")
    return parsed, source


def strip_html(raw):
    text = _SCRIPT_RE.sub(" ", raw or "")
    text = _STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = html_lib.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def looks_like_challenge(html):
    low = (html or "").lower()
    return any(marker in low for marker in _CHALLENGE_MARKERS)


def _first_group(match):
    if not match:
        return ""
    return strip_html(next((g for g in match.groups() if g), "") or "")


def json_ld_blocks(html):
    blocks = []
    for match in _JSONLD_RE.finditer(html or ""):
        raw = html_lib.unescape(match.group(1) or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks


def _is_person(node):
    kind = node.get("@type") if isinstance(node, dict) else None
    if isinstance(kind, list):
        return "Person" in kind
    return kind == "Person"


def from_json_ld(blocks):
    person = next((item for item in blocks if _is_person(item)), None)
    if not person:
        return {}
    job = person.get("jobTitle") or ""
    if isinstance(job, list):
        job = ", ".join(str(part) for part in job if part)
    address = person.get("address") or {}
    if isinstance(address, list) and address:
        address = address[0]
    location = ""
    if isinstance(address, dict):
        location = address.get("addressLocality") or address.get("addressRegion") or ""
    elif isinstance(address, str):
        location = address
    skills = person.get("knowsAbout") or person.get("skills") or []
    if isinstance(skills, str):
        skills = [part.strip() for part in re.split(r"[,;/]+", skills) if part.strip()]
    elif isinstance(skills, list):
        skills = [str(item).strip() for item in skills if str(item).strip()]
    else:
        skills = []
    works = person.get("worksFor") or []
    if isinstance(works, dict):
        works = [works]
    experience = []
    if isinstance(works, list):
        for item in works:
            if not isinstance(item, dict):
                continue
            experience.append({
                "position": str(item.get("jobTitle") or "").strip(),
                "company": str(item.get("name") or item.get("legalName") or "").strip(),
                "period": "",
                "description": str(item.get("description") or "").strip(),
            })
    return {
        "full_name": str(person.get("name") or "").strip(),
        "headline": str(job).strip(),
        "email": str(person.get("email") or "").strip(),
        "phone": str(person.get("telephone") or "").strip(),
        "location": str(location).strip(),
        "summary": str(person.get("description") or "").strip(),
        "skills": ", ".join(skills),
        "experience": [row for row in experience if row["position"] or row["company"]],
    }


def extract_skills(html, extra_text=""):
    found = []
    seen = set()
    for match in _SKILL_RE.finditer(html or ""):
        name = strip_html(match.group(1))
        key = name.lower()
        if not name or len(name) > 40 or key in seen:
            continue
        seen.add(key)
        found.append(name)
    if not found and extra_text:
        for part in re.split(r"[,;/|]+", extra_text):
            name = part.strip()
            key = name.lower()
            if 1 < len(name) <= 32 and key not in seen:
                seen.add(key)
                found.append(name)
    return found[:24]


def extract_contacts(text):
    email_match = _EMAIL_RE.search(text or "")
    phone_match = _PHONE_RE.search(text or "")
    email = email_match.group(0) if email_match else ""
    phone = phone_match.group(0).strip() if phone_match else ""
    return email, phone


def split_name(full_name):
    parts = [part for part in re.split(r"\s+", (full_name or "").strip()) if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def empty_resume():
    return {
        "full_name": "",
        "headline": "",
        "email": "",
        "phone": "",
        "location": "",
        "summary": "",
        "skills": "",
        "experience": [],
        "education": [],
        "languages": [],
        "links": [],
    }


def merge_resume(*parts):
    out = empty_resume()
    for part in parts:
        if not part:
            continue
        for key in ("full_name", "headline", "email", "phone", "location", "summary", "skills"):
            if part.get(key) and not out.get(key):
                out[key] = part[key]
        for key in ("experience", "education", "languages", "links"):
            if part.get(key) and not out.get(key):
                out[key] = part[key]
    return out


def headline_from_title(title, name):
    title = (title or "").strip()
    name = (name or "").strip()
    if name and title.lower().startswith(name.lower()):
        rest = title[len(name):].lstrip("—–-|: ").strip()
        return rest or title
    if " — " in title:
        left, right = title.split(" — ", 1)
        if name and left.strip().lower() == name.lower():
            return right.strip()
        return right.strip() or title
    return title


def parse_generic(html, url):
    og_title = _first_group(_OG_TITLE_RE.search(html or ""))
    h1 = _first_group(_H1_RE.search(html or ""))
    name = h1 or (og_title.split("—")[0].split("|")[0].strip() if og_title else "")
    desc = _first_group(_OG_DESC_RE.search(html or ""))
    text = strip_html(html)
    email, phone = extract_contacts(text)
    skills = extract_skills(html, desc)
    linked = from_json_ld(json_ld_blocks(html))
    base = {
        "full_name": name,
        "headline": headline_from_title(og_title or h1, name),
        "email": email,
        "phone": phone,
        "summary": desc[:800],
        "skills": ", ".join(skills),
        "links": [{"label": "Профиль", "url": url}] if url else [],
    }
    return merge_resume(linked, base)


def parse_djinni_resume(html, url=""):
    data = parse_generic(html, url)
    loc_match = re.search(
        r'(?is)(?:location|city|проживан)[^<]{0,80}</[^>]+>\s*([^<]{2,40})',
        html or "",
    )
    if loc_match and not data["location"]:
        data["location"] = strip_html(loc_match.group(1))
    blocks = re.findall(
        r'(?is)<(?:article|div)[^>]*class=["\'][^"\']*(?:timeline|experience|job)[^"\']*["\'][^>]*>(.{40,2500})</(?:article|div)>',
        html or "",
    )
    experience = []
    for block in blocks[:8]:
        title_match = re.search(r"(?is)<h[23][^>]*>(.*?)</h[23]>", block)
        company_match = re.search(
            r'(?is)class=["\'][^"\']*(?:company|org)[^"\']*["\'][^>]*>(.*?)<',
            block,
        )
        period_match = re.search(r"(?is)(20\d{2}\s*[—\-–]\s*(?:20\d{2}|н\.в\.|now|тепер))", block)
        if not title_match:
            continue
        experience.append({
            "position": strip_html(title_match.group(1)),
            "company": strip_html(company_match.group(1)) if company_match else "",
            "period": strip_html(period_match.group(1)) if period_match else "",
            "description": strip_html(block)[:400],
        })
    if experience and not data["experience"]:
        data["experience"] = experience
    return data


_DJINNI_ACCOUNT_LINK_FIELDS = {
    "github": "GitHub",
    "linkedin": "LinkedIn",
    "portfolio": "Portfolio",
    "telegram": "Telegram",
}


def extract_djinni_account_links(html):
    """GitHub/LinkedIn/Portfolio/Telegram на djinni.co живут не на странице профиля, а на
    отдельной странице «Контакти» (/my/account/) — djinni нарочно не пускает такие ссылки в
    сам профиль ради анонимности поиска ("не вставляйте посилання... можна буде додати
    пізніше, на сторінці Контакти"). Без похода на эту страницу отдельно эти поля не найти
    ни в каком варианте профиля."""
    links = []
    for field, label in _DJINNI_ACCOUNT_LINK_FIELDS.items():
        m = re.search(rf'name="{field}"[^>]*\svalue="([^"]*)"', html or "", re.I)
        if not m:
            continue
        value = html_lib.unescape(m.group(1)).strip()
        if not value:
            continue
        url = value
        if field == "telegram" and not url.startswith("http"):
            url = "https://t.me/" + url.lstrip("@")
        elif not url.startswith("http"):
            url = "https://" + url
        links.append({"label": label, "url": url})
    return links


def _input_value(html, name):
    m = re.search(rf'name="{name}"[^>]*\svalue="([^"]*)"', html or "", re.I)
    return html_lib.unescape(m.group(1)).strip() if m else ""


def parse_djinni_account_page(html):
    """Реальные ФИО/email/телефон + личные ссылки со страницы «Контакти» (/my/account/).
    Публичный вид профиля (тот, что виден работодателям) анонимный: вместо email там
    показывается служебный magic@djinni.co, вместо имени — ничего, поэтому эти поля нужно
    брать именно отсюда, а не с публичной страницы."""
    return {
        "full_name": _input_value(html, "name"),
        "email": _input_value(html, "email"),
        "phone": _input_value(html, "phone"),
        "links": extract_djinni_account_links(html),
    }


def extract_djinni_profile_skills(html):
    """Навыки — со страницы редактирования профиля (/my/profile/, поле skills_experience),
    а не с публичного вида: там вместо реальных навыков попадаются обрывки соседней вёрстки
    (чекбоксы вида «Вимкнений» и т.п.), потому что нет чёткого маркера блока навыков."""
    skills, seen = [], set()
    for m in re.finditer(r'name="skills_experience\[\d+\]\[skill\]"[^>]*\svalue="([^"]*)"', html or "", re.I):
        value = html_lib.unescape(m.group(1)).strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            skills.append(value)
    return skills


def _selected_option_text(select_html):
    m = re.search(r'<option value="[^"]+"\s+selected>\s*([^<]+?)\s*</option>', select_html or "")
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def extract_djinni_profile_languages(html):
    """Языки — со страницы редактирования профиля (language_knowledge[N][code]/[level]):
    два выпадающих списка на каждый язык, значение — выбранный <option>."""
    languages = []
    for idx_m in re.finditer(r'name="language_knowledge\[(\d+)\]\[code\]"', html or ""):
        idx = idx_m.group(1)
        code_block = re.search(rf'name="language_knowledge\[{idx}\]\[code\]".*?</select>', html, re.S)
        level_block = re.search(rf'name="language_knowledge\[{idx}\]\[level\]".*?</select>', html, re.S)
        name = _selected_option_text(code_block.group(0)) if code_block else ""
        level = _selected_option_text(level_block.group(0)) if level_block else ""
        if name:
            languages.append({"name": name, "level": level})
    return languages


def parse_djinni_profile_form(html):
    """headline/локация/навыки/языки — со страницы редактирования профиля (/my/profile/),
    где поля реально доступны как value="..."/selected, а не угадываются регуляркой по
    случайным классам публичной анонимной страницы."""
    return {
        "headline": _input_value(html, "position"),
        "location": _input_value(html, "location"),
        "skills": extract_djinni_profile_skills(html),
        "languages": extract_djinni_profile_languages(html),
    }


def parse_workua_resume(html, url=""):
    return parse_generic(html, url)


def parse_rabota_resume(html, url=""):
    return parse_generic(html, url)


PARSERS = {
    "djinni": parse_djinni_resume,
    "workua": parse_workua_resume,
    "rabota": parse_rabota_resume,
}


def default_fetch(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": job_scraper.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en;q=0.7",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise ResumeImportError(f"площадка ответила HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ResumeImportError("не удалось открыть ссылку") from exc


def import_from_url(url, html=None, fetch=None, session_get=None):
    parsed, source = classify_url(url)
    canon = parsed.geturl()
    if html is None:
        getter = session_get or fetch or default_fetch
        html = getter(canon)
    if looks_like_challenge(html):
        raise ResumeImportError(
            "площадка показала проверку браузера. Откройте резюме в браузере "
            "и вставьте публичную ссылку, либо заполните данные вручную"
        )
    data = PARSERS[source](html, canon)
    return _finalize(data, source, canon)


MAX_BOARD_RESUMES = 8


def _finalize(data, source, url):
    data["source"] = source
    data["source_url"] = url or ""
    if not data.get("full_name") and not data.get("headline") and not data.get("skills"):
        raise ResumeImportError(
            "в кабинете не нашлось данных резюме — опубликуйте его на площадке"
        )
    return data


def _clip(value, limit):
    return str(value or "").strip()[:limit]


def _row_list(rows, fields, limit=8):
    out = []
    if not isinstance(rows, list):
        return out
    for item in rows[:limit]:
        if not isinstance(item, dict):
            continue
        row = {key: _clip(item.get(key), size) for key, size in fields}
        if any(row.values()):
            out.append(row)
    return out


def resume_snapshot(data):
    """Компактная копия резюме для профиля: просмотр без повторного входа."""
    data = data or {}
    skills = data.get("skills") or ""
    if isinstance(skills, list):
        skills = ", ".join(str(part).strip() for part in skills if str(part).strip())
    return {
        "source": _clip(data.get("source"), 20),
        "source_url": _clip(data.get("source_url"), 400),
        "full_name": _clip(data.get("full_name"), 160),
        "headline": _clip(data.get("headline"), 200),
        "email": _clip(data.get("email"), 160),
        "phone": _clip(data.get("phone"), 40),
        "location": _clip(data.get("location"), 120),
        "summary": _clip(data.get("summary"), 800),
        "skills": _clip(skills, 400),
        "experience": _row_list(
            data.get("experience"),
            (("position", 120), ("company", 120), ("period", 60), ("description", 400)),
        ),
        "education": _row_list(
            data.get("education"),
            (("degree", 120), ("school", 160), ("period", 60)),
        ),
        "languages": _row_list(
            data.get("languages"),
            (("name", 80), ("level", 40)),
        ),
        "links": _row_list(
            data.get("links"),
            (("label", 80), ("url", 400)),
        ),
    }


DJINNI_PROFILE_HREF_RE = re.compile(
    r"""href=["'](?:https?://(?:www\.)?djinni\.co)?(/q/[A-Za-z0-9_-]+/?)["']""",
    re.I,
)
DJINNI_PROFILE_ABS_RE = re.compile(
    r"https?://(?:www\.)?djinni\.co(/q/[A-Za-z0-9_-]+/?)",
    re.I,
)
WORKUA_RESUME_HREF_RE = re.compile(
    r"""href=["'](?:https?://(?:www\.)?work\.ua)?(/resumes/\d+/?)["']""",
    re.I,
)
WORKUA_RESUME_ABS_RE = re.compile(
    r"https?://(?:www\.)?work\.ua(/resumes/\d+/?)",
    re.I,
)
WORKUA_MY_RESUME_ID_RE = re.compile(r"/jobseeker/my/resumes/(\d+)", re.I)

DJINNI_DISCOVER_URLS = (
    "https://djinni.co/my/dashboard/",
    "https://djinni.co/home/",
    "https://djinni.co/my/profile/",
    "https://djinni.co/my/",
    "https://djinni.co/",
)
WORKUA_DISCOVER_URLS = (
    "https://www.work.ua/jobseeker/my/resumes/",
    "https://www.work.ua/jobseeker/my/",
)
RABOTA_MY_RESUME_URLS = (
    "https://api.rabota.ua/resume/my",
    "https://api.rabota.ua/cv/my",
    "https://api.rabota.ua/notebook/resumes",
    "https://api.rabota.ua/resume",
)


def _canon_path(path):
    path = path or ""
    if path and not path.endswith("/"):
        path += "/"
    return path


def discover_djinni_profile_url(html):
    match = DJINNI_PROFILE_HREF_RE.search(html or "") or DJINNI_PROFILE_ABS_RE.search(html or "")
    if not match:
        return ""
    return "https://djinni.co" + _canon_path(match.group(1))


def _workua_resume_id(path):
    match = re.search(r"(\d+)", path or "")
    return match.group(1) if match else ""


def discover_workua_resume_urls(html):
    """Все ссылки на свои резюме в кабинете work.ua, без дублей."""
    ids = []
    seen = set()

    def add_id(rid):
        rid = str(rid or "").strip()
        if rid.isdigit() and rid not in seen:
            seen.add(rid)
            ids.append(rid)

    for match in WORKUA_RESUME_HREF_RE.finditer(html or ""):
        add_id(_workua_resume_id(match.group(1)))
    for match in WORKUA_RESUME_ABS_RE.finditer(html or ""):
        add_id(_workua_resume_id(match.group(1)))
    for match in WORKUA_MY_RESUME_ID_RE.finditer(html or ""):
        add_id(match.group(1))
    return [f"https://www.work.ua/resumes/{rid}/" for rid in ids[:MAX_BOARD_RESUMES]]


def discover_workua_resume_url(html):
    urls = discover_workua_resume_urls(html)
    return urls[0] if urls else ""


def _safe_get(getter, url):
    try:
        return getter(url) or ""
    except Exception:
        return ""


def json_collection(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("documents", "resumes", "items", "data", "result", "notebooks"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = json_collection(value)
            if nested:
                return nested
    markers = (
        "speciality", "position", "fullName", "firstName", "name",
        "skills", "id", "headline",
    )
    if any(payload.get(key) for key in markers):
        return [payload]
    return []


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip()


def parse_rabota_own_resume(raw, url=""):
    if not isinstance(raw, dict):
        raw = {}
    first = _text(raw.get("firstName") or raw.get("first_name"))
    last = _text(raw.get("lastName") or raw.get("last_name"))
    name = " ".join(part for part in (first, last) if part) or _text(
        raw.get("fullName") or raw.get("name")
    )
    headline = _text(
        raw.get("speciality") or raw.get("position")
        or raw.get("title") or raw.get("vacancyName")
    )
    skills_raw = raw.get("skills") or raw.get("skillName") or raw.get("skillNames") or []
    if isinstance(skills_raw, str):
        skills = [part.strip() for part in re.split(r"[,;/|]+", skills_raw) if part.strip()]
    elif isinstance(skills_raw, list):
        skills = []
        for item in skills_raw:
            if isinstance(item, dict):
                label = _text(item.get("name") or item.get("title") or item.get("skill"))
            else:
                label = _text(item)
            if label:
                skills.append(label)
    else:
        skills = []
    email = _text(raw.get("email") or raw.get("eMail"))
    phone = _text(raw.get("phone") or raw.get("telephone") or raw.get("phoneNumber"))
    location = _text(raw.get("cityName") or raw.get("city") or raw.get("city_name"))
    summary = _text(
        raw.get("additionalInformation") or raw.get("shortDescription")
        or raw.get("description")
    )
    exp_raw = (
        raw.get("experiences") or raw.get("experience")
        or raw.get("jobs") or raw.get("workExperience") or []
    )
    if isinstance(exp_raw, dict):
        exp_raw = [exp_raw]
    experience = []
    if isinstance(exp_raw, list):
        for item in exp_raw[:12]:
            if not isinstance(item, dict):
                continue
            row = {
                "position": _text(item.get("position") or item.get("title") or item.get("speciality")),
                "company": _text(item.get("company") or item.get("companyName") or item.get("name")),
                "period": _text(item.get("period") or item.get("date") or item.get("years")),
                "description": _text(item.get("description") or item.get("duties"))[:400],
            }
            if row["position"] or row["company"]:
                experience.append(row)
    data = empty_resume()
    data.update({
        "full_name": name,
        "headline": headline,
        "email": email,
        "phone": phone,
        "location": location,
        "summary": summary[:800],
        "skills": ", ".join(skills[:24]),
        "experience": experience,
        "links": [{"label": "Профиль", "url": url}] if url else [],
    })
    return data


def _fetch_djinni_reliable_sources(getter, log):
    """Публичный вид профиля (тот, что попадает в html_pages ниже) специально анонимный —
    это то, что видят работодатели: без настоящего имени, телефона, реальных навыков и
    личных ссылок. Все они реально живут на двух других страницах, доступных только самому
    владельцу — «Контакти» (/my/account/) и редактирование профиля (/my/profile/) — поэтому
    заходим туда отдельно и потом подмешиваем в результат парсинга публичной страницы."""
    account, profile_form = {}, {}
    try:
        html = _safe_get(getter, "https://djinni.co/my/account/")
        if html and not looks_like_challenge(html):
            account = parse_djinni_account_page(html)
    except Exception:
        pass
    try:
        html = _safe_get(getter, "https://djinni.co/my/profile/")
        if html and not looks_like_challenge(html):
            profile_form = parse_djinni_profile_form(html)
    except Exception:
        pass
    if account.get("links"):
        log(f"[djinni] со страницы «Контакти» подтянуто ссылок: {len(account['links'])}")
    if profile_form.get("skills"):
        log(f"[djinni] со страницы профиля подтянуто навыков: {len(profile_form['skills'])}")
    if profile_form.get("languages"):
        log(f"[djinni] языков: {len(profile_form['languages'])}")
    return account, profile_form


def _apply_djinni_reliable_fields(data, account, profile_form):
    if account.get("full_name"):
        data["full_name"] = account["full_name"]
    if account.get("email"):
        data["email"] = account["email"]
    if account.get("phone"):
        data["phone"] = account["phone"]
    data["links"] = (data.get("links") or []) + account.get("links", [])
    if profile_form.get("headline"):
        data["headline"] = profile_form["headline"]
    if profile_form.get("location"):
        data["location"] = profile_form["location"]
    if profile_form.get("skills"):
        data["skills"] = ", ".join(profile_form["skills"])
    if profile_form.get("languages"):
        data["languages"] = profile_form["languages"]
    return data


def import_djinni_from_login(email, password, *, session=None, login=None, log=None):
    log = log or (lambda msg: None)
    login = login or board_auth.djinni_candidate_login
    try:
        sess = login(email, password, log=log, session=session)
    except TypeError:
        sess = login(email, password, log=log)
    except RuntimeError as exc:
        raise ResumeImportError(str(exc)) from exc
    getter = sess.get
    account, profile_form = _fetch_djinni_reliable_sources(getter, log)
    html_pages = []
    profile_url = ""
    for url in DJINNI_DISCOVER_URLS:
        html = _safe_get(getter, url)
        if not html:
            continue
        if looks_like_challenge(html):
            raise ResumeImportError("djinni.co показал проверку браузера — попробуйте ещё раз")
        html_pages.append((url, html))
        profile_url = discover_djinni_profile_url(html)
        if profile_url:
            break
    if profile_url:
        html = _safe_get(getter, profile_url)
        if looks_like_challenge(html):
            raise ResumeImportError("djinni.co показал проверку на странице резюме")
        data = _apply_djinni_reliable_fields(parse_djinni_resume(html, profile_url), account, profile_form)
        return [_finalize(data, "djinni", profile_url)]
    for url, html in html_pages:
        if board_auth.djinni_page_requires_login(html):
            continue
        try:
            data = _apply_djinni_reliable_fields(parse_djinni_resume(html, url), account, profile_form)
            return [_finalize(data, "djinni", url)]
        except ResumeImportError:
            continue
    raise ResumeImportError("не нашли резюме в кабинете djinni.co — опубликуйте профиль")


def _workua_with_browser(callback):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ResumeImportError(
            "для work.ua нужен Playwright. Установите его в том же venv, "
            "которым запускаете приложение"
        ) from exc
    with sync_playwright() as playwright:
        browser = job_scraper._launch_playwright_chromium(playwright)
        try:
            page = browser.new_page(user_agent=job_scraper.USER_AGENT)
            return callback(page)
        finally:
            browser.close()


def import_workua_from_login(email, password, *, page=None, login=None, log=None):
    log = log or (lambda msg: None)
    login = login or board_auth.workua_jobseeker_login

    def run(active_page):
        try:
            login(active_page, email, password, log=log)
        except RuntimeError as exc:
            raise ResumeImportError(str(exc)) from exc
        list_html = ""
        resume_urls = []
        for url in WORKUA_DISCOVER_URLS:
            active_page.goto(url, timeout=45000)
            if job_scraper.workua_wait_challenge_clear(active_page):
                raise ResumeImportError("work.ua показал проверку браузера в кабинете")
            list_html = active_page.content()
            resume_urls = discover_workua_resume_urls(list_html)
            if resume_urls:
                break
        found = []
        for resume_url in resume_urls:
            active_page.goto(resume_url, timeout=45000)
            if job_scraper.workua_wait_challenge_clear(active_page):
                raise ResumeImportError("work.ua показал проверку на странице резюме")
            html = active_page.content()
            try:
                found.append(_finalize(parse_workua_resume(html, resume_url), "workua", resume_url))
            except ResumeImportError:
                continue
        if found:
            return found
        if list_html and not looks_like_challenge(list_html):
            try:
                used = getattr(active_page, "url", "") or ""
                return [_finalize(parse_workua_resume(list_html, used), "workua", used)]
            except ResumeImportError:
                pass
        raise ResumeImportError(
            "в кабинете work.ua не нашли резюме — создайте его в разделе «Мои резюме»"
        )

    if page is not None:
        return run(page)
    return _workua_with_browser(run)


def import_rabota_from_login(email, password, *, login=None, fetch=None, log=None):
    log = log or (lambda msg: None)
    login = login or (lambda e, p, log=None: board_auth.rabota_login(e, p, log=log))
    try:
        token = login(email, password, log=log)
    except RuntimeError as exc:
        raise ResumeImportError(str(exc)) from exc
    getter = fetch or board_auth.bearer_json_fetch(token)
    last_err = None
    items = []
    for url in RABOTA_MY_RESUME_URLS:
        try:
            payload = getter(url)
        except Exception as exc:
            last_err = exc
            continue
        items = json_collection(payload)
        if items:
            break
    if not items:
        raise ResumeImportError(
            "не нашли резюме в кабинете robota.ua — создайте его на площадке"
            + (f" ({last_err})" if last_err else "")
        )
    found = []
    for raw in items[:MAX_BOARD_RESUMES]:
        rid = raw.get("id") or raw.get("resumeId") or ""
        source_url = f"https://robota.ua/candidates/{rid}" if rid else "https://robota.ua/"
        try:
            found.append(_finalize(parse_rabota_own_resume(raw, source_url), "rabota", source_url))
        except ResumeImportError:
            continue
    if not found:
        raise ResumeImportError("не нашли резюме в кабинете robota.ua — создайте его на площадке")
    return found


def list_from_login(source, email, password, **hooks):
    """Все резюме из кабинета площадки (вход соискателя)."""
    source = (source or "").strip().lower()
    email = (email or "").strip()
    password = password or ""
    if source not in ("djinni", "workua", "rabota"):
        raise ResumeImportError("площадка: djinni.co, work.ua или robota.ua")
    if not email or not password:
        raise ResumeImportError("нужны email и пароль вашего аккаунта на площадке")
    if source == "djinni":
        return import_djinni_from_login(
            email, password,
            session=hooks.get("session"),
            login=hooks.get("djinni_login"),
            log=hooks.get("log"),
        )
    if source == "workua":
        return import_workua_from_login(
            email, password,
            page=hooks.get("workua_page"),
            login=hooks.get("workua_login"),
            log=hooks.get("log"),
        )
    return import_rabota_from_login(
        email, password,
        login=hooks.get("rabota_login"),
        fetch=hooks.get("rabota_fetch"),
        log=hooks.get("log"),
    )


def import_from_login(source, email, password, **hooks):
    return list_from_login(source, email, password, **hooks)[0]

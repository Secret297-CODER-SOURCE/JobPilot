"""Вход владельца на площадки для ленты кандидатов.

Email/пароль задаёт только владелец в админке (как ключ Jooble). Сессия
нужна, чтобы увидеть публичные карточки выдачи. Имена, телефоны и полные
чужие CV по-прежнему не сохраняем — это делает candidate_scraper.
"""

import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request

import job_scraper

DJINNI_LOGIN_URL = "https://djinni.co/login"
DJINNI_DEVELOPERS_URL = "https://djinni.co/developers/"
DJINNI_CANDIDATE_HOME_URLS = (
    "https://djinni.co/my/dashboard/",
    "https://djinni.co/home/",
    "https://djinni.co/my/profile/",
)
RABOTA_LOGIN_URL = "https://auth-api.rabota.ua/Login"
WORKUA_EMPLOYER_LOGIN_URL = "https://www.work.ua/employer/login/"
WORKUA_JOBSEEKER_LOGIN_URL = "https://www.work.ua/jobseeker/login/"
WORKUA_JOBSEEKER_EMAIL_SELECTORS = (
    "#email",
    "input[name='email']",
    "input[type='email']",
    "#user-login",
)
WORKUA_JOBSEEKER_PASSWORD_SELECTORS = (
    "#password",
    "input[name='password']",
    "input[type='password']",
)
WORKUA_JOBSEEKER_SUBMIT_SELECTORS = (
    "form button[type=submit]",
    "button[type=submit]",
    "input[type=submit]",
)

_CSRF_RE = re.compile(
    r'name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)'
    r'|value=["\']([^"\']+)["\'][^>]*name=["\']csrfmiddlewaretoken["\']',
    re.I,
)


def extract_csrf(html):
    m = _CSRF_RE.search(html or "")
    if not m:
        return ""
    return m.group(1) or m.group(2) or ""


def djinni_page_requires_login(html):
    text = html or ""
    low = text.lower()
    if "/q/" in text or re.search(r"/developers/\d+", text):
        return False
    if "увійти на джин" in low or "войти на джин" in low:
        return True
    return 'id="password"' in low and ('id="email"' in low or 'name="email"' in low)


def _read_response(resp):
    charset = resp.headers.get_content_charset() or "utf-8"
    return resp.read().decode(charset, errors="replace")


class HttpSession:
    def __init__(self, opener=None):
        jar = http.cookiejar.CookieJar()
        self.opener = opener or urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )

    def get(self, url, headers=None, timeout=20):
        merged = {"User-Agent": job_scraper.USER_AGENT}
        if headers:
            merged.update(headers)
        req = urllib.request.Request(url, headers=merged)
        with self.opener.open(req, timeout=timeout) as resp:
            return _read_response(resp)

    def post(self, url, data=None, headers=None, timeout=20):
        merged = {"User-Agent": job_scraper.USER_AGENT}
        if headers:
            merged.update(headers)
        body = data
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            merged.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif isinstance(data, str):
            body = data.encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=merged, method="POST")
        with self.opener.open(req, timeout=timeout) as resp:
            return _read_response(resp)


def _djinni_submit_credentials(email, password, session=None):
    email = (email or "").strip()
    password = password or ""
    if not email or not password:
        raise RuntimeError("не задан вход djinni.co")
    sess = session or HttpSession()
    html = sess.get(DJINNI_LOGIN_URL)
    csrf = extract_csrf(html)
    if not csrf:
        raise RuntimeError("не нашёл CSRF на странице входа djinni.co")
    try:
        sess.post(
            DJINNI_LOGIN_URL,
            data={
                "email": email,
                "password": password,
                "csrfmiddlewaretoken": csrf,
            },
            headers={
                "Referer": DJINNI_LOGIN_URL,
                "Origin": "https://djinni.co",
            },
        )
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"djinni.co вход отклонён (HTTP {e.code})") from e
    return sess


def djinni_login(email, password, log=None, session=None):
    """Сессия djinni.co по email/паролю владельца. Возвращает HttpSession."""
    log = log or (lambda msg: None)
    sess = _djinni_submit_credentials(email, password, session=session)
    check = sess.get(DJINNI_DEVELOPERS_URL)
    if djinni_page_requires_login(check):
        raise RuntimeError("djinni.co отклонил вход — проверьте email и пароль в админке")
    log("[djinni-cv] вход выполнен")
    return sess


def djinni_candidate_login(email, password, log=None, session=None):
    """Вход соискателя: проверяем кабинет, не ленту /developers/."""
    log = log or (lambda msg: None)
    sess = _djinni_submit_credentials(email, password, session=session)
    for url in DJINNI_CANDIDATE_HOME_URLS:
        try:
            check = sess.get(url)
        except urllib.error.URLError:
            continue
        if not djinni_page_requires_login(check):
            log("[djinni] вход соискателя выполнен")
            return sess
    raise RuntimeError("djinni.co отклонил вход — проверьте email и пароль")


def parse_rabota_token(raw):
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("{") or text.startswith('"'):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text.strip('"')
        if isinstance(data, str):
            return data.strip()
        if isinstance(data, dict):
            return (
                data.get("token")
                or data.get("access_token")
                or data.get("jwt")
                or ""
            ).strip()
    return text.strip().strip('"')


def rabota_login(email, password, log=None, post=None):
    """JWT работодателя через официальный auth-api.rabota.ua/Login."""
    log = log or (lambda msg: None)
    email = (email or "").strip()
    password = password or ""
    if not email or not password:
        raise RuntimeError("не задан вход robota.ua")

    def _post(url, payload):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "User-Agent": job_scraper.USER_AGENT,
                "Accept": "application/json, text/plain",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    poster = post or _post
    try:
        raw = poster(RABOTA_LOGIN_URL, {"username": email, "password": password})
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"robota.ua вход отклонён (HTTP {e.code})") from e
    token = parse_rabota_token(raw)
    if not token:
        raise RuntimeError("robota.ua не вернул токен")
    log("[rabotaua-cv] вход выполнен")
    return token


def bearer_json_fetch(token):
    def fetch(url):
        return job_scraper._fetch_json(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
    return fetch


def workua_login(page, email, password, log=None):
    """Вход работодателя на work.ua в уже открытом Playwright page."""
    log = log or (lambda msg: None)
    email = (email or "").strip()
    password = password or ""
    if not email or not password:
        raise RuntimeError("не задан вход work.ua")
    page.goto(WORKUA_EMPLOYER_LOGIN_URL, timeout=45000)
    if job_scraper.workua_wait_challenge_clear(page):
        raise RuntimeError("work.ua: Cloudflare на странице входа не прошёл")
    url = (getattr(page, "url", "") or "").lower()
    if "login" not in url:
        log("[workua-cv] сессия work.ua уже активна")
        return True
    page.wait_for_selector("#user-login", timeout=20000)
    page.fill("#user-login", email)
    page.fill("#password", password)
    try:
        page.wait_for_function(
            """() => {
                const el = document.querySelector('#g-recaptcha-response-lForm, textarea[name="g-recaptcha-response"]');
                return !el || (el.value && el.value.length > 10);
            }""",
            timeout=8000,
        )
    except Exception:
        pass
    page.click("form#lForm button[type=submit]")
    try:
        page.wait_for_load_state("domcontentloaded", timeout=20000)
    except Exception:
        pass
    if job_scraper.workua_wait_challenge_clear(page):
        raise RuntimeError("work.ua: Cloudflare после отправки формы входа")
    url = (getattr(page, "url", "") or "").lower()
    if "login" in url:
        raise RuntimeError("work.ua отклонил вход — проверьте email и пароль в админке")
    log("[workua-cv] вход выполнен")
    return True


def _page_try_fill(page, selectors, value, timeout=8000):
    last_err = None
    for sel in selectors:
        try:
            waiter = getattr(page, "wait_for_selector", None)
            if waiter:
                waiter(sel, timeout=timeout)
            page.fill(sel, value)
            return sel
        except Exception as err:
            last_err = err
    raise RuntimeError("не нашёл поле входа work.ua") from last_err


def _page_try_click(page, selectors, timeout=8000):
    last_err = None
    for sel in selectors:
        try:
            waiter = getattr(page, "wait_for_selector", None)
            if waiter:
                waiter(sel, timeout=timeout)
            page.click(sel)
            return sel
        except Exception as err:
            last_err = err
    raise RuntimeError("не нашёл кнопку входа work.ua") from last_err


def workua_jobseeker_login(page, email, password, log=None):
    """Вход соискателя на work.ua (не кабинет работодателя)."""
    log = log or (lambda msg: None)
    email = (email or "").strip()
    password = password or ""
    if not email or not password:
        raise RuntimeError("не задан вход work.ua")
    page.goto(WORKUA_JOBSEEKER_LOGIN_URL, timeout=45000)
    if job_scraper.workua_wait_challenge_clear(page):
        raise RuntimeError("work.ua: Cloudflare на странице входа соискателя не прошёл")
    url = (getattr(page, "url", "") or "").lower()
    if "login" not in url:
        log("[workua] сессия соискателя уже активна")
        return True
    _page_try_fill(page, WORKUA_JOBSEEKER_EMAIL_SELECTORS, email)
    _page_try_fill(page, WORKUA_JOBSEEKER_PASSWORD_SELECTORS, password)
    try:
        page.wait_for_function(
            """() => {
                const el = document.querySelector(
                    '#g-recaptcha-response, textarea[name="g-recaptcha-response"]'
                );
                return !el || (el.value && el.value.length > 10);
            }""",
            timeout=8000,
        )
    except Exception:
        pass
    _page_try_click(page, WORKUA_JOBSEEKER_SUBMIT_SELECTORS)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=20000)
    except Exception:
        pass
    if job_scraper.workua_wait_challenge_clear(page):
        raise RuntimeError("work.ua: Cloudflare после входа соискателя")
    url = (getattr(page, "url", "") or "").lower()
    if "login" in url:
        raise RuntimeError("work.ua отклонил вход соискателя — проверьте email и пароль")
    log("[workua] вход соискателя выполнен")
    return True

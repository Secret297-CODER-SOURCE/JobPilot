#!/usr/bin/env python3
"""
JobPilot — платформа поиска работы для нескольких пользователей.

Поиск вакансий (djinni.co + work.ua + robota.ua + jooble.org) + рынок кандидатов
(публичные карточки резюме без имён и контактов) + резюме + ИИ + аккаунты.

Запуск:
    ./jobscraper/job_scraper_venv/bin/pip install flask flask-sock pypdf python-docx
    ./jobscraper/job_scraper_venv/bin/python3 webapp.py
Открыть http://127.0.0.1:5057
"""

import json
import os
import re
import secrets
import sys
import threading
import time
import types
import uuid
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask_sock import Sock
from simple_websocket import ConnectionClosed
from werkzeug.security import check_password_hash, generate_password_hash

sys.path.insert(0, str(Path(__file__).parent / "jobscraper"))

import ai_match
import board_auth
import job_apply
import candidate_scraper
import cv_extract
import db
import job_scraper
import resume_builder
import resume_import

SECRET_KEY_PATH = db.DATA_DIR / "secret_key.txt"


def _load_or_create_secret_key():
    if SECRET_KEY_PATH.exists():
        return SECRET_KEY_PATH.read_text().strip()
    key = secrets.token_hex(32)
    SECRET_KEY_PATH.write_text(key)
    return key


app = Flask(__name__)
app.secret_key = _load_or_create_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB на загрузку резюме
sock = Sock(app)

ALLOWED_CV_FORMATS = {"pdf", "docx", "txt"}
ALLOWED_IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp"}
IMAGES_DIR = db.UPLOADS_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

db.init_db()


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.svg", mimetype="image/svg+xml")


# ---------------------------------------------------------------------------
# Аккаунты
# ---------------------------------------------------------------------------

def current_user():
    uid = session.get("user_id")
    return db.get_user(uid) if uid else None


def _first_run():
    return db.count_users() == 0


def _guest_auth_redirect():
    """Пока нет ни одного аккаунта — сразу форма регистрации, иначе вход."""
    if _first_run():
        return redirect(url_for("register_page"))
    return redirect(url_for("login_page"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        uid = session.get("user_id")
        if not uid or not db.get_user(uid):
            session.clear()
            if request.path.startswith("/api/"):
                return {"error": "требуется авторизация"}, 401
            return _guest_auth_redirect()
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or user["role"] != "admin":
            if request.path.startswith("/api/"):
                return {"error": "требуются права администратора"}, 403
            return "Доступ запрещён", 403
        return view(*args, **kwargs)
    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "GET":
        if "user_id" in session and db.get_user(session["user_id"]):
            return redirect(url_for("index"))
        return render_template("register.html", first_run=_first_run())

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    first_run = _first_run()

    if not name or not email or not password:
        return render_template("register.html", error="Заполните все поля", name=name, email=email, first_run=first_run), 400
    if len(password) < 8:
        return render_template("register.html", error="Пароль должен быть не короче 8 символов", name=name, email=email, first_run=first_run), 400
    if db.get_user_by_email(email):
        return render_template("register.html", error="Этот email уже зарегистрирован", name=name, email=email, first_run=first_run), 400

    role = "admin" if db.count_users() == 0 else "user"
    user_id = uuid.uuid4().hex
    db.create_user(user_id, email, generate_password_hash(password), name, role)
    db.set_setting(user_id, "onboarding_done", "0")
    session["user_id"] = user_id
    db.log_activity(user_id, "auth.register", {"email": email, "role": role})
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        if "user_id" in session and db.get_user(session["user_id"]):
            return redirect(url_for("index"))
        if _first_run():
            return redirect(url_for("register_page"))
        return render_template("login.html")

    if _first_run():
        return redirect(url_for("register_page"))

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    user = db.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Неверный email или пароль", email=email), 401

    session["user_id"] = user["id"]
    db.log_activity(user["id"], "auth.login", {"email": user["email"]})
    return redirect(url_for("index"))


@app.route("/logout", methods=["POST"])
def logout():
    uid = session.get("user_id")
    if uid:
        db.log_activity(uid, "auth.logout")
    session.clear()
    return _guest_auth_redirect()


# ---------------------------------------------------------------------------
# Поиск вакансий (кэш 15 минут на первый проход; автопоиск шлёт новые по WS)
# ---------------------------------------------------------------------------

ALL_PAGES_CAP = 30  # защитный потолок для режима "выгрузить все страницы"
WATCH_INTERVAL_DEFAULT = 60
WATCH_INTERVAL_MIN = 30
WATCH_INTERVAL_MAX = 180


def job_key(job):
    if not isinstance(job, dict):
        return ""
    url = (job.get("url") or "").strip()
    if url:
        return url
    title = (job.get("title") or "").strip()
    if not title:
        return ""
    source = (job.get("source") or "").strip()
    company = (job.get("company") or "").strip()
    return f"{source}|{title}|{company}"


def candidate_key(card):
    if not isinstance(card, dict):
        return ""
    url = (card.get("url") or "").strip()
    if url:
        return url
    title = (card.get("title") or "").strip()
    if not title:
        return ""
    source = (card.get("source") or "").strip()
    city = (card.get("city") or "").strip()
    snippet = (card.get("snippet") or "").strip()[:40]
    return f"{source}|{title}|{city}|{snippet}"


def take_new_jobs(jobs, seen):
    """Вернуть вакансии, которых ещё не было в seen, и запомнить их ключи."""
    fresh = []
    for job in jobs or []:
        key = job_key(job)
        if not key or key in seen:
            continue
        seen.add(key)
        fresh.append(job)
    return fresh


def _job_identity_sig(source, keyword, query, region, remote, reservation):
    """Стабильный идентификатор «этого поиска» для постоянного учёта вакансий (jobs.query_sig) —
    в отличие от cache_key поиска, НЕ включает pages/all_pages/delay. Полный проход по всем
    страницам и лёгкий поллинг первой страницы — один и тот же логический поиск и должны
    делить один query_sig, иначе mark_missing_removed после полного прохода не находит вакансии,
    которым poll успел переписать query_sig, и реально пропавшие вакансии никогда не помечаются."""
    return db.make_cache_key(source, {
        "keyword": keyword, "query": query, "region": region,
        "remote": remote, "reservation": reservation,
    })


def watch_poll_form(form):
    """Повторные проходы автопоиска — только первая страница, без кэша."""
    poll = dict(form)
    poll["pages"] = 1
    poll["all_pages"] = False
    return poll


def _truthy(value, default=False):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def parse_search_body(body):
    """Разобрать JSON автопоиска. Возвращает (form, error_text)."""
    if not isinstance(body, dict):
        return None, "некорректный запрос"
    if (body.get("action") or "").strip().lower() in ("stop", "close", "cancel"):
        return {"action": "stop"}, None
    sources = body.get("sources") or []
    if not sources:
        return None, "нужно выбрать хотя бы один источник"
    keyword = _parse_keyword_field(body.get("keyword"))
    query = (body.get("query") or "").strip()
    if not keyword and not query:
        return None, "нужно указать ключевое слово или поисковый запрос"
    all_pages = bool(body.get("all_pages"))
    pages = ALL_PAGES_CAP if all_pages else _clamp_int(body.get("pages", 1), 1, 10, 1)
    delay = _clamp_float(body.get("delay", 2.0), 1.0, 10.0, 2.0)
    form = {
        "sources": sources,
        "keyword": keyword or None,
        "query": query or None,
        "region": (body.get("region") or "").strip() or None,
        "pages": pages,
        "delay": delay,
        "all_pages": all_pages,
        "remote": _parse_remote_mode(body.get("remote")),
        "reservation": _parse_reservation(body.get("reservation")),
        "watch": _truthy(body.get("watch"), default=True),
        "watch_interval": _clamp_int(
            body.get("watch_interval", WATCH_INTERVAL_DEFAULT),
            WATCH_INTERVAL_MIN, WATCH_INTERVAL_MAX, WATCH_INTERVAL_DEFAULT,
        ),
    }
    return form, None


def _ws_wait(ws, seconds):
    """Ждать interval секунд. stop — клиент остановил, gone — отключился, timeout — пора снова искать."""
    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "timeout"
        try:
            raw = ws.receive(timeout=min(remaining, 5.0))
        except ConnectionClosed:
            return "gone"
        if not getattr(ws, "connected", True):
            return "gone"
        if raw is None:
            continue
        try:
            msg = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if (msg.get("action") or "").strip().lower() in ("stop", "close", "cancel"):
            return "stop"


def _do_search(user_id, form, log, *, use_cache=True, write_cache=True, on_chunk=None, log_activity=True):
    sources = form["sources"]
    keyword = form.get("keyword")
    query = form.get("query")
    region = form.get("region")
    pages = form["pages"]
    delay = form["delay"]
    all_pages = bool(form.get("all_pages"))
    remote = job_scraper.normalize_remote_mode(form.get("remote"))
    reservation = job_scraper.want_reservation(form.get("reservation"))
    cache_params = {
        "keyword": keyword, "query": query, "region": region,
        "pages": pages, "all_pages": all_pages,
        "remote": remote, "reservation": reservation,
    }

    results = []

    def _take(chunk):
        if not chunk:
            return
        results.extend(chunk)
        if on_chunk:
            on_chunk(chunk)

    def _record(cache_key, chunk, *, complete):
        """Постоянный учёт вакансий: обновляет last_seen_at всегда; помечает пропавшие
        removed_at только на полном прогоне без обрывов защитой — иначе недокачанная страница
        ошибочно похоронит ещё живые вакансии глубже по пагинации. Проставляет job['_fresh']
        по-настоящему — увидели этот ключ впервые за всё время, а не просто "после первого
        раунда автопоиска в этом сеансе"."""
        if not chunk:
            return {}
        keyed = [(job_key(j), j) for j in chunk if job_key(j)]
        is_new = db.upsert_jobs(keyed, cache_key)
        for key, job in keyed:
            job["_fresh"] = is_new.get(key, False)
        if complete and all_pages:
            db.mark_missing_removed(cache_key, {k for k, _ in keyed})
        return is_new

    if "djinni" in sources:
        cache_key = db.make_cache_key("djinni", cache_params)
        identity_key = _job_identity_sig("djinni", keyword, query, region, remote, reservation)
        cached = db.get_cached_search(cache_key) if use_cache else None
        if cached is not None:
            log(f"djinni.co: {len(cached)} вакансий из кэша (запрос за последние 15 минут)")
            _record(identity_key, cached, complete=False)
            _take(cached)
            db.log_search(user_id, "djinni", keyword, query, region, len(cached), True)
        else:
            log("Запускаю поиск на djinni.co…")
            args = types.SimpleNamespace(
                keyword=keyword, query=query, region=region, param=None,
                pages=pages, delay=delay, remote=remote, reservation=reservation,
            )
            djinni_jobs = job_scraper.scrape_djinni(args, log=log)
            _record(identity_key, djinni_jobs, complete=True)
            _take(djinni_jobs)
            log(f"djinni.co: получено {len(djinni_jobs)} вакансий")
            if write_cache:
                db.set_cached_search(cache_key, "djinni", djinni_jobs)
            db.log_search(user_id, "djinni", keyword, query, region, len(djinni_jobs), False)

    if "workua" in sources:
        cache_key = db.make_cache_key("workua", cache_params)
        identity_key = _job_identity_sig("workua", keyword, query, region, remote, reservation)
        cached = db.get_cached_search(cache_key) if use_cache else None
        if cached is not None:
            log(f"work.ua: {len(cached)} вакансий из кэша (запрос за последние 15 минут)")
            _record(identity_key, cached, complete=False)
            _take(cached)
            db.log_search(user_id, "workua", keyword, query, region, len(cached), True)
        else:
            log("Запускаю поиск на work.ua (headless-браузер, может занять время)…")
            args = types.SimpleNamespace(
                keyword=keyword, query=query, region=region, param=None,
                pages=pages, delay=max(delay, 3.0), all_pages=all_pages,
                remote=remote, reservation=reservation,
            )
            try:
                workua_info = {}
                workua_jobs = job_scraper.scrape_workua(args, log=log, info=workua_info)
                incomplete = bool(
                    workua_info.get("challenge_stopped")
                    or (not workua_jobs and not workua_info.get("listing_ok"))
                )
                _record(identity_key, workua_jobs, complete=not incomplete)
                _take(workua_jobs)
                log(f"work.ua: получено {len(workua_jobs)} вакансий")
                if incomplete:
                    log("work.ua: результат неполный из-за защиты сайта — не сохраняю в кэш, чтобы повторный поиск мог попробовать снова, а не залипал на неполном результате.")
                elif write_cache:
                    db.set_cached_search(cache_key, "workua", workua_jobs)
                db.log_search(user_id, "workua", keyword, query, region, len(workua_jobs), False)
            except RuntimeError as e:
                log(f"work.ua недоступен: {e}")

    if "rabotaua" in sources:
        cache_key = db.make_cache_key("rabotaua", cache_params)
        identity_key = _job_identity_sig("rabotaua", keyword, query, region, remote, reservation)
        cached = db.get_cached_search(cache_key) if use_cache else None
        if cached is not None:
            log(f"robota.ua: {len(cached)} вакансий из кэша (запрос за последние 15 минут)")
            _record(identity_key, cached, complete=False)
            _take(cached)
            db.log_search(user_id, "rabotaua", keyword, query, region, len(cached), True)
        else:
            log("Запускаю поиск на robota.ua (публичный API)…")
            args = types.SimpleNamespace(
                keyword=keyword, query=query, region=region, param=None,
                pages=pages, delay=delay, all_pages=all_pages,
                remote=remote, reservation=reservation,
            )
            try:
                rabota_jobs = job_scraper.scrape_rabotaua(args, log=log)
                _record(identity_key, rabota_jobs, complete=True)
                _take(rabota_jobs)
                log(f"robota.ua: получено {len(rabota_jobs)} вакансий")
                if write_cache:
                    db.set_cached_search(cache_key, "rabotaua", rabota_jobs)
                db.log_search(user_id, "rabotaua", keyword, query, region, len(rabota_jobs), False)
            except Exception as e:
                log(f"robota.ua недоступен: {e}")

    if "jooble" in sources:
        cache_key = db.make_cache_key("jooble", cache_params)
        identity_key = _job_identity_sig("jooble", keyword, query, region, remote, reservation)
        cached = db.get_cached_search(cache_key) if use_cache else None
        if cached is not None:
            log(f"jooble.org: {len(cached)} вакансий из кэша (запрос за последние 15 минут)")
            _record(identity_key, cached, complete=False)
            _take(cached)
            db.log_search(user_id, "jooble", keyword, query, region, len(cached), True)
        else:
            log("Запускаю поиск через Jooble API…")
            jooble_key = db.get_platform_setting("jooble_api_key")
            args = types.SimpleNamespace(
                keyword=keyword, query=query, region=region, param=None,
                pages=pages, delay=delay, remote=remote, reservation=reservation,
            )
            try:
                jooble_jobs = job_scraper.scrape_jooble(args, jooble_key, log=log)
                _record(identity_key, jooble_jobs, complete=True)
                _take(jooble_jobs)
                log(f"jooble.org: получено {len(jooble_jobs)} вакансий")
                if write_cache:
                    db.set_cached_search(cache_key, "jooble", jooble_jobs)
                db.log_search(user_id, "jooble", keyword, query, region, len(jooble_jobs), False)
            except RuntimeError as e:
                log(f"jooble.org недоступен: {e}")

    if log_activity:
        db.log_activity(user_id, "search.jobs", {
            "sources": sources, "keyword": keyword, "query": query,
            "region": region, "n": len(results),
            "remote": remote, "reservation": reservation,
        })
    return results


def _do_candidate_search(user_id, form, cv_text, log):
    sources = form["sources"]
    keyword = form.get("keyword")
    query = form.get("query")
    region = form.get("region")
    pages = form["pages"]
    delay = form["delay"]
    all_pages = bool(form.get("all_pages"))
    remote = job_scraper.normalize_remote_mode(form.get("remote"))
    cache_params = {
        "kind": "candidates", "keyword": keyword, "query": query,
        "region": region, "pages": pages, "all_pages": all_pages, "remote": remote,
    }
    results = []
    djinni_email, djinni_password = _board_admin_credentials("djinni")
    workua_email, workua_password = _board_admin_credentials("workua")
    rabota_email, rabota_password = _board_admin_credentials("rabota")

    def _record(identity_key, chunk, *, complete):
        """Постоянный учёт карточек рынка — та же честная логика, что и у вакансий
        (_do_search._record): removed_at выставляется только после полного прохода."""
        if not chunk:
            return
        keyed = [(candidate_key(c), c) for c in chunk if candidate_key(c)]
        db.upsert_candidates(keyed, identity_key)
        if complete and all_pages:
            db.mark_missing_candidates_removed(identity_key, {k for k, _ in keyed})

    for src in sources:
        cache_key = db.make_cache_key(f"cand-{src}", cache_params)
        identity_key = _job_identity_sig(f"cand-{src}", keyword, query, region, remote, False)
        cached = db.get_cached_search(cache_key)
        if cached:
            log(f"{src}: {len(cached)} карточек из кэша (15 минут)")
            _record(identity_key, cached, complete=False)
            results.extend(cached)
            continue
        args = types.SimpleNamespace(
            keyword=keyword, query=query, region=region, param=None,
            pages=pages, delay=max(delay, 3.0) if src == "workua" else delay,
            all_pages=all_pages, sources=[src], remote=remote,
            djinni_email=djinni_email,
            djinni_password=djinni_password,
            workua_email=workua_email,
            workua_password=workua_password,
            rabota_email=rabota_email,
            rabota_password=rabota_password,
        )
        info = {}
        try:
            chunk = candidate_scraper.scrape_all_candidates(args, log=log, info=info)
        except Exception as e:
            log(f"{src}: {e}")
            chunk = []
        results.extend(chunk)
        incomplete = bool(info.get("challenge_stopped"))
        _record(identity_key, chunk, complete=not incomplete)
        if incomplete:
            log("work.ua: результат неполный из-за защиты сайта — не сохраняю в кэш, чтобы повторный поиск мог попробовать снова.")
        elif not chunk:
            log(f"{src}: пусто — не кэширую, чтобы повтор с входом мог сработать")
        else:
            db.set_cached_search(cache_key, f"cand-{src}", chunk)
    analysis = candidate_scraper.analyze_market(results, cv_text or "")
    log(f"Итого публичных карточек: {len(results)}")
    db.log_activity(user_id, "search.candidates", {
        "sources": sources, "keyword": keyword, "query": query,
        "region": region, "n": len(results),
    })
    return results, analysis


@app.route("/")
@login_required
def index():
    uid = current_user()["id"]
    if db.get_setting(uid, "onboarding_done") == "0":
        return redirect(url_for("onboarding_page"))
    return render_template("index.html", user=current_user(), keyword_categories=job_scraper.KEYWORD_CATEGORIES)


@app.route("/onboarding")
@login_required
def onboarding_page():
    return render_template("onboarding.html", user=current_user(), keyword_categories=job_scraper.KEYWORD_CATEGORIES)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(email):
    return bool(email) and bool(_EMAIL_RE.match(email))


def _clamp_int(value, lo, hi, default):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _clamp_float(value, lo, hi, default):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _save_profile_fields(uid, body, current_name):
    first_name = (body.get("first_name") or "").strip()[:80]
    last_name = (body.get("last_name") or "").strip()[:80]
    phone = (body.get("phone") or "").strip()[:40]
    location = (body.get("location") or "").strip()[:120]
    headline = _parse_keyword_field(body.get("headline"))
    db.set_setting(uid, "profile_first_name", first_name)
    db.set_setting(uid, "profile_last_name", last_name)
    db.set_setting(uid, "profile_phone", phone)
    db.set_setting(uid, "profile_location", location)
    db.set_setting(uid, "profile_headline", headline)
    if headline and not (db.get_setting(uid, "pref_keyword") or "").strip():
        # Желаемая должность и «Категория» в фильтрах поиска — одно и то же по сути;
        # подставляем как стартовое значение поиска, только если там ещё ничего не выбрано,
        # чтобы не затирать то, что пользователь уже сам настроил.
        db.set_setting(uid, "pref_keyword", headline)
    for key in ("resume_url_djinni", "resume_url_workua", "resume_url_rabota"):
        if key in body:
            db.set_setting(uid, key, (body.get(key) or "").strip()[:400])
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        db.update_user_name(uid, full_name)
    return {
        "first_name": first_name, "last_name": last_name, "phone": phone,
        "location": location, "headline": headline,
        "name": full_name or current_name,
    }


def _parse_keyword_field(value):
    return ", ".join(job_scraper.parse_keywords(value))[:800]


def _parse_remote_mode(value):
    return job_scraper.normalize_remote_mode(value)


def _parse_reservation(value):
    return job_scraper.want_reservation(value)


SEARCH_PREF_SOURCES = ("djinni", "workua", "rabotaua", "jooble")


def _save_search_pref_fields(uid, body):
    keyword = _parse_keyword_field(body.get("keyword"))
    query = (body.get("query") or "").strip()[:200]
    region = ", ".join(job_scraper.parse_regions(body.get("region")))[:400]
    sources = [s for s in (body.get("sources") or []) if s in SEARCH_PREF_SOURCES]
    employment_type = (body.get("employment_type") or "").strip()[:40]
    remote = _parse_remote_mode(body.get("remote"))
    reservation = _parse_reservation(body.get("reservation"))
    salary_expectation = (body.get("salary_expectation") or "").strip()[:60]
    db.set_setting(uid, "pref_keyword", keyword)
    db.set_setting(uid, "pref_query", query)
    db.set_setting(uid, "pref_region", region)
    db.set_setting(uid, "pref_sources", json.dumps(sources))
    db.set_setting(uid, "pref_employment_type", employment_type)
    db.set_setting(uid, "pref_remote", remote)
    db.set_setting(uid, "pref_reservation", "1" if reservation else "0")
    db.set_setting(uid, "pref_salary_expectation", salary_expectation)
    pages = _clamp_int(body.get("pages"), 1, 10, 1)
    delay = _clamp_float(body.get("delay"), 1.0, 10.0, 3.0)
    db.set_setting(uid, "pref_pages", str(pages))
    db.set_setting(uid, "pref_delay", str(delay))
    if "all_pages" in body:
        db.set_setting(uid, "pref_all_pages", "1" if body.get("all_pages") else "0")
    return {
        "keyword": keyword, "query": query, "region": region, "sources": sources,
        "employment_type": employment_type, "remote": remote, "reservation": reservation,
        "salary_expectation": salary_expectation,
        "all_pages": (db.get_setting(uid, "pref_all_pages") or "1") != "0",
        "pages": pages,
        "delay": delay,
    }


def _profile_payload(uid=None):
    user = current_user()
    uid = uid or user["id"]
    s = db.all_settings(uid)
    first = s.get("profile_first_name", "")
    last = s.get("profile_last_name", "")
    phone = s.get("profile_phone", "")
    headline = s.get("profile_headline", "")
    return {
        "first_name": first,
        "last_name": last,
        "phone": phone,
        "location": s.get("profile_location", ""),
        "headline": headline,
        "email": user["email"],
        "name": user["name"],
        "profile_complete": bool(first.strip() and (phone.strip() or headline.strip())),
        "prompt_profile_later": s.get("prompt_profile_later") == "1",
        "prompt_import_later": s.get("prompt_import_later") == "1",
        "resume_url_djinni": s.get("resume_url_djinni", ""),
        "resume_url_workua": s.get("resume_url_workua", ""),
        "resume_url_rabota": s.get("resume_url_rabota", ""),
        "boards": _boards_payload(s),
    }


@app.route("/api/profile", methods=["GET"])
@login_required
def api_get_profile():
    return _profile_payload()


@app.route("/api/profile", methods=["POST"])
@login_required
def api_save_profile():
    user = current_user()
    body = request.get_json(force=True)
    email = (body.get("email") or "").strip().lower()
    if email:
        if not _valid_email(email):
            return {"error": "некорректный email"}, 400
        if email != user["email"]:
            other = db.get_user_by_email(email)
            if other and other["id"] != user["id"]:
                return {"error": "этот email уже занят"}, 409
            try:
                db.update_user_email(user["id"], email)
            except ValueError:
                return {"error": "этот email уже занят"}, 409
    result = _save_profile_fields(user["id"], body, user["name"])
    payload = _profile_payload()
    payload["name"] = result.get("name") or payload["name"]
    return payload


def _get_search_prefs(uid):
    s = db.all_settings(uid)
    try:
        sources = json.loads(s.get("pref_sources") or "[]")
    except (TypeError, ValueError):
        sources = []
    if not sources:
        sources = ["djinni", "workua", "rabotaua"]
    return {
        "keyword": s.get("pref_keyword", ""),
        "query": s.get("pref_query", ""),
        "region": s.get("pref_region", ""),
        "sources": sources,
        "employment_type": s.get("pref_employment_type", ""),
        "remote": _parse_remote_mode(s.get("pref_remote", "")),
        "reservation": _parse_reservation(s.get("pref_reservation", "")),
        "salary_expectation": s.get("pref_salary_expectation", ""),
        "all_pages": (s.get("pref_all_pages") or "1") != "0",
        "pages": _clamp_int(s.get("pref_pages"), 1, 10, 1),
        "delay": _clamp_float(s.get("pref_delay"), 1.0, 10.0, 3.0),
    }


@app.route("/api/search-prefs", methods=["GET"])
@login_required
def api_get_search_prefs():
    return _get_search_prefs(current_user()["id"])


@app.route("/api/search-prefs", methods=["POST"])
@login_required
def api_save_search_prefs():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    return _save_search_pref_fields(uid, body)


@app.route("/api/onboarding/complete", methods=["POST"])
@login_required
def api_onboarding_complete():
    user = current_user()
    uid = user["id"]
    body = request.get_json(force=True)

    profile = _save_profile_fields(uid, body.get("profile") or {}, user["name"])
    _save_search_pref_fields(uid, body.get("search_prefs") or {})

    exp = body.get("experience") or {}
    edu = body.get("education") or {}
    if (exp.get("position") or "").strip() or (edu.get("degree") or "").strip():
        data = {
            "full_name": profile["name"],
            "headline": profile["headline"],
            "email": user["email"],
            "phone": profile["phone"],
            "location": profile["location"],
            "summary": "",
            "experience": [exp] if (exp.get("position") or "").strip() else [],
            "education": [edu] if (edu.get("degree") or "").strip() else [],
            "skills": "",
            "languages": [],
        }
        resume_id = uuid.uuid4().hex
        data_json = json.dumps(data, ensure_ascii=False)
        db.save_resume_draft(resume_id, uid, "classic", data_json)
        text_content = resume_builder.flatten_text(data)
        db.add_cv(
            resume_id, uid, resume_builder.resume_title(data), "builder", f"builder:{resume_id}",
            text_content, len(text_content.encode("utf-8")),
        )

    db.set_setting(uid, "onboarding_done", "1")
    return {"ok": True}


@app.route("/api/onboarding/skip", methods=["POST"])
@login_required
def api_onboarding_skip():
    db.set_setting(current_user()["id"], "onboarding_done", "1")
    return {"ok": True}


@app.route("/api/prompts/later", methods=["POST"])
@login_required
def api_prompt_later():
    which = ((request.get_json(force=True) or {}).get("which") or "").strip()
    keys = {"profile": "prompt_profile_later", "import": "prompt_import_later"}
    if which not in keys:
        return {"error": "неизвестный шаг"}, 400
    db.set_setting(current_user()["id"], keys[which], "1")
    return {"ok": True, "profile": _profile_payload()}


_RESUME_URL_KEYS = {
    "djinni": "resume_url_djinni",
    "workua": "resume_url_workua",
    "rabota": "resume_url_rabota",
}
_BOARD_RESUMES_KEYS = {
    "djinni": "board_resumes_djinni",
    "workua": "board_resumes_workua",
    "rabota": "board_resumes_rabota",
}

CV_BOARD_KEYS = {
    "djinni": ("cv_djinni_email", "cv_djinni_password"),
    "workua": ("cv_workua_email", "cv_workua_password"),
    "rabota": ("cv_rabota_email", "cv_rabota_password"),
}


def _admin_user_id():
    for user in db.list_users():
        if user.get("role") == "admin":
            return user["id"]
    return None


def _board_admin_credentials(board):
    """Вход на djinni.co/work.ua/robota.ua для «Рынка кандидатов» не хранится отдельно на
    платформе — берётся из личного cv_<board>_email/password владельца (см. «Моё резюме с
    площадок»), чтобы не заставлять вводить один и тот же логин и пароль дважды."""
    uid = _admin_user_id()
    if not uid or board not in CV_BOARD_KEYS:
        return "", ""
    email_key, password_key = CV_BOARD_KEYS[board]
    s = db.all_settings(uid)
    return s.get(email_key, ""), s.get(password_key, "")


def _load_board_resumes(raw):
    try:
        items = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)][:resume_import.MAX_BOARD_RESUMES]


def _boards_payload(settings):
    out = {}
    for source, (email_key, password_key) in CV_BOARD_KEYS.items():
        email = (settings.get(email_key) or "").strip()
        password = settings.get(password_key) or ""
        raw = settings.get(_BOARD_RESUMES_KEYS[source])
        resumes = _load_board_resumes(raw) if raw is not None else []
        out[source] = {
            "connected": bool(email and password),
            "email": email,
            "email_masked": _mask_email(email) if email else None,
            "resume_url": settings.get(_RESUME_URL_KEYS[source], ""),
            "resumes": resumes,
            "resume_count": len(resumes),
            "resumes_loaded": raw is not None,
        }
    return out


def _finish_resume_import(uid, source, data, resumes=None):
    items = list(resumes or ([data] if data else []))
    snaps = [resume_import.resume_snapshot(item) for item in items]
    db.set_setting(uid, _BOARD_RESUMES_KEYS[source], json.dumps(snaps, ensure_ascii=False))
    if data.get("source_url"):
        db.set_setting(uid, _RESUME_URL_KEYS[source], (data.get("source_url") or "")[:400])
    s = db.all_settings(uid)
    first, last = resume_import.split_name(data.get("full_name"))
    _save_profile_fields(uid, {
        "first_name": s.get("profile_first_name") or first,
        "last_name": s.get("profile_last_name") or last,
        "phone": s.get("profile_phone") or data.get("phone") or "",
        "location": s.get("profile_location") or data.get("location") or "",
        "headline": s.get("profile_headline") or data.get("headline") or "",
    }, current_user()["name"])
    db.log_activity(uid, "resume.import", {"source": source, "ok": True, "count": len(snaps)})
    return {"ok": True, "resume": data, "resumes": snaps, "profile": _profile_payload()}


@app.route("/api/resume/import", methods=["POST"])
@login_required
def api_import_resume():
    body = request.get_json(force=True) or {}
    uid = current_user()["id"]
    source = (body.get("source") or "").strip().lower()
    url = (body.get("url") or "").strip()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    settings = db.all_settings(uid)

    if source in CV_BOARD_KEYS:
        email_key, password_key = CV_BOARD_KEYS[source]
        email = email or (settings.get(email_key) or "").strip()
        password = password or (settings.get(password_key) or "")
        try:
            items = resume_import.list_from_login(source, email, password)
        except resume_import.ResumeImportError as exc:
            return {"error": str(exc)}, 400
        except Exception as exc:
            return {"error": f"не удалось подключить площадку: {exc}"}, 400
        db.set_setting(uid, email_key, email)
        db.set_setting(uid, password_key, password)
        if not items:
            return {"error": "не нашли резюме в кабинете — опубликуйте его на площадке"}, 400
        return _finish_resume_import(uid, source, items[0], resumes=items)

    if url:
        try:
            _parsed, source = resume_import.classify_url(url)
        except resume_import.ResumeImportError as exc:
            return {"error": str(exc)}, 400
        session_get = None
        if email and password and source == "djinni":
            try:
                sess = board_auth.djinni_login(email, password)
                session_get = sess.get
            except Exception as exc:
                return {"error": f"вход на djinni.co не удался: {exc}"}, 400
        try:
            data = resume_import.import_from_url(url, session_get=session_get)
        except resume_import.ResumeImportError as exc:
            return {"error": str(exc)}, 400
        except Exception:
            return {"error": "не удалось прочитать страницу резюме"}, 400
        return _finish_resume_import(uid, source, data, resumes=[data])

    return {"error": "выберите площадку и введите email и пароль вашего аккаунта"}, 400


@app.route("/api/resume/boards/<source>", methods=["DELETE"])
@login_required
def api_disconnect_board(source):
    source = (source or "").strip().lower()
    if source not in CV_BOARD_KEYS:
        return {"error": "неизвестная площадка"}, 400
    uid = current_user()["id"]
    email_key, password_key = CV_BOARD_KEYS[source]
    db.delete_setting(uid, email_key)
    db.delete_setting(uid, password_key)
    db.delete_setting(uid, _BOARD_RESUMES_KEYS[source])
    db.delete_setting(uid, _RESUME_URL_KEYS[source])
    return {"ok": True, "profile": _profile_payload()}


def _ws_send(ws, msg_type, **payload):
    try:
        ws.send(json.dumps({"type": msg_type, **payload}, ensure_ascii=False))
        return True
    except (ConnectionClosed, OSError, TypeError):
        return False


def _run_autosearch(ws, user, form):
    seen = set()
    round_no = 0
    interval = form["watch_interval"]
    watch = form["watch"]

    def send(msg_type, **payload):
        return _ws_send(ws, msg_type, **payload)

    def log(msg):
        send("log", text=msg)

    def on_chunk(chunk):
        fresh = take_new_jobs(chunk, seen)
        if fresh:
            send("jobs", jobs=fresh, round=round_no, fresh=(round_no > 0), total=len(seen))

    if form.get("all_pages"):
        log("Режим «все страницы» включён — work.ua и robota.ua забираю до конца выдачи.")
    log("Автопоиск: первый проход по фильтрам аккаунта.")

    try:
        _do_search(user["id"], form, log, on_chunk=on_chunk)
    except Exception as e:
        send("error", text=str(e))
        return

    if not send("watching", total=len(seen), interval=interval if watch else 0, round=round_no):
        return
    if watch:
        log(f"Первый проход готов: {len(seen)} вакансий. Дальше проверяю площадки каждые {interval} с — новые появятся в списке сами.")
    else:
        log(f"Готово: {len(seen)} вакансий.")
        send("done", total=len(seen))
        return

    while True:
        wait = _ws_wait(ws, interval)
        if wait in ("stop", "gone"):
            send("stopped", total=len(seen))
            return
        round_no += 1
        log(f"Проверяю новые вакансии (проход {round_no + 1})…")
        poll = watch_poll_form(form)
        before = len(seen)
        try:
            _do_search(
                user["id"], poll, log,
                use_cache=False, write_cache=False,
                on_chunk=on_chunk, log_activity=False,
            )
        except Exception as e:
            log(f"Проход не удался: {e} — повторю позже.")
            continue
        added = len(seen) - before
        if added:
            db.log_activity(user["id"], "search.jobs", {
                "sources": form["sources"], "keyword": form.get("keyword"),
                "query": form.get("query"), "region": form.get("region"),
                "n": added, "watch": True, "round": round_no,
            })
            log(f"Новых вакансий: {added}. Всего {len(seen)}.")
        else:
            log(f"Новых нет. Всего {len(seen)}. Следующая проверка через {interval} с.")
        if not send("watching", total=len(seen), interval=interval, round=round_no):
            return


@app.route("/api/jobs/cached", methods=["POST"])
@login_required
def api_jobs_cached():
    """Вакансии, уже лежащие в постоянном хранилище под текущими фильтрами — для мгновенного
    показа при открытии страницы, без ожидания нового сетевого прохода автопоиска."""
    body = request.get_json(force=True)
    form, err = parse_search_body(body)
    if err or not form or form.get("action") == "stop":
        return {"jobs": []}
    keyword = form.get("keyword")
    query = form.get("query")
    region = form.get("region")
    remote = job_scraper.normalize_remote_mode(form.get("remote"))
    reservation = job_scraper.want_reservation(form.get("reservation"))
    identity_keys = [
        _job_identity_sig(source, keyword, query, region, remote, reservation)
        for source in form["sources"]
    ]
    return {"jobs": db.list_jobs_by_query_sigs(identity_keys)}


@app.route("/api/candidates/cached", methods=["POST"])
@login_required
def api_candidates_cached():
    """Карточки «Рынка кандидатов», уже лежащие в постоянном хранилище под текущими
    фильтрами — для мгновенного показа без нового сетевого прохода."""
    body = request.get_json(force=True)
    sources = [s for s in (body.get("sources") or []) if s in ("djinni", "workua", "rabotaua")]
    keyword = (body.get("keyword") or "").strip()
    query = (body.get("query") or "").strip()
    if not sources or (not keyword and not query):
        return {"candidates": []}
    region = (body.get("region") or "").strip() or None
    remote = job_scraper.normalize_remote_mode(body.get("remote"))
    identity_keys = [
        _job_identity_sig(f"cand-{source}", keyword or None, query or None, region, remote, False)
        for source in sources
    ]
    return {"candidates": db.list_candidates_by_query_sigs(identity_keys)}


@app.route("/api/candidates/analysis", methods=["POST"])
@login_required
def api_candidates_analysis():
    """Аналитика рынка (зарплаты/навыки/пробелы) по уже собранным карточкам — без сетевого
    похода на площадки. cv_id опционален — без него просто рыночные агрегаты без сверки."""
    uid = current_user()["id"]
    body = request.get_json(force=True)
    sources = [s for s in (body.get("sources") or []) if s in ("djinni", "workua", "rabotaua")]
    keyword = (body.get("keyword") or "").strip()
    query = (body.get("query") or "").strip()
    if not sources or (not keyword and not query):
        return {"error": "нужны source и категория/запрос"}, 400
    region = (body.get("region") or "").strip() or None
    remote = job_scraper.normalize_remote_mode(body.get("remote"))
    identity_keys = [
        _job_identity_sig(f"cand-{source}", keyword or None, query or None, region, remote, False)
        for source in sources
    ]
    candidates = db.list_candidates_by_query_sigs(identity_keys)

    cv_text = ""
    cv_id = (body.get("cv_id") or "").strip()
    if cv_id:
        cv = db.get_cv(cv_id, uid)
        if cv:
            cv_text = cv.get("text_content") or ""

    analysis = candidate_scraper.analyze_market(candidates, cv_text)
    return {"candidates": candidates, "analysis": analysis}


@app.route("/api/jobs/description", methods=["POST"])
@login_required
def api_job_description():
    """Полный текст вакансии: в выдаче поиска только короткий анонс."""
    job = (request.get_json(force=True) or {}).get("job") or {}
    snippet = (job.get("description") or "").strip()
    source = (job.get("source") or "").strip()
    if source not in ("rabotaua", "djinni"):
        return {"description": snippet, "full": False}
    try:
        text = job_scraper.fetch_full_job_description(job)
    except Exception:
        return {"description": snippet, "full": False}
    full = bool(text and len(text) > len(snippet))
    return {"description": text or snippet, "full": full}


BACKGROUND_SCAN_INTERVAL = 15 * 60  # честная проверка «есть ли новое / что пропало», раз в 15 минут,
                                     # независимо от того, открыт ли у кого-то браузер


def _background_scan_user(uid):
    prefs = _get_search_prefs(uid)
    if not prefs["sources"] or not (prefs["keyword"] or prefs["query"]):
        return

    form, err = parse_search_body({
        "sources": prefs["sources"], "keyword": prefs["keyword"], "query": prefs["query"],
        "region": prefs["region"], "all_pages": prefs["all_pages"], "pages": prefs["pages"],
        "delay": prefs["delay"], "remote": prefs["remote"], "reservation": prefs["reservation"],
    })
    if not err:
        try:
            _do_search(uid, form, lambda msg: None, use_cache=True, write_cache=True, log_activity=False)
        except Exception as e:
            print(f"[background scan] jobs user={uid}: {e}", file=sys.stderr)

    candidate_sources = [s for s in prefs["sources"] if s in ("djinni", "workua", "rabotaua")]
    if candidate_sources:
        cand_form = {
            "sources": candidate_sources,
            "keyword": prefs["keyword"] or None, "query": prefs["query"] or None,
            "region": prefs["region"] or None, "pages": prefs["pages"], "delay": prefs["delay"],
            "all_pages": prefs["all_pages"], "remote": prefs["remote"],
        }
        try:
            _do_candidate_search(uid, cand_form, "", lambda msg: None)
        except Exception as e:
            print(f"[background scan] candidates user={uid}: {e}", file=sys.stderr)


def _background_search_loop():
    """Держит таблицы вакансий и карточек «Рынка кандидатов» (upsert_jobs/upsert_candidates +
    mark_missing_*) свежими сама, без браузера — иначе честная логика новое/уже видели/пропало
    работает только пока у кого-то открыта вкладка с автопоиском."""
    while True:
        for user in db.list_users():
            try:
                _background_scan_user(user["id"])
            except Exception as e:
                print(f"[background scan] user={user['id']}: {e}", file=sys.stderr)
        time.sleep(BACKGROUND_SCAN_INTERVAL)


@sock.route("/ws/search")
def ws_search(ws):
    user = current_user()
    if not user:
        ws.close(reason="требуется авторизация")
        return

    while True:
        try:
            raw = ws.receive()
        except ConnectionClosed:
            return
        if raw is None:
            return

        try:
            body = json.loads(raw)
        except (TypeError, ValueError):
            _ws_send(ws, "error", text="некорректный запрос")
            continue

        form, err = parse_search_body(body)
        if err:
            _ws_send(ws, "error", text=err)
            continue
        if form.get("action") == "stop":
            _ws_send(ws, "stopped", total=0)
            continue

        try:
            _run_autosearch(ws, user, form)
        except ConnectionClosed:
            return
        except Exception as e:
            _ws_send(ws, "error", text=str(e))


@sock.route("/ws/candidates")
def ws_candidates(ws):
    user = current_user()
    if not user:
        ws.close(reason="требуется авторизация")
        return

    while True:
        raw = ws.receive()
        if raw is None:
            return

        def send(msg_type, **payload):
            ws.send(json.dumps({"type": msg_type, **payload}, ensure_ascii=False))

        try:
            body = json.loads(raw)
        except (TypeError, ValueError):
            send("error", text="некорректный запрос")
            continue

        sources = [s for s in (body.get("sources") or []) if s in ("djinni", "workua", "rabotaua")]
        if not sources:
            send("error", text="выберите djinni.co, work.ua или robota.ua")
            continue
        keyword = (body.get("keyword") or "").strip()
        query = (body.get("query") or "").strip()
        if not keyword and not query:
            send("error", text="нужно указать категорию или запрос")
            continue

        all_pages = bool(body.get("all_pages"))
        if all_pages:
            pages = candidate_scraper.CANDIDATE_MAX_PAGES
        else:
            try:
                pages = max(1, min(10, int(body.get("pages", 1))))
            except (TypeError, ValueError):
                pages = 1
        try:
            delay = max(1.0, min(10.0, float(body.get("delay", 3.0))))
        except (TypeError, ValueError):
            delay = 3.0

        send("log", text="Собираю публичные резюме для примеров и аналитики. Имена и контакты не сохраняю.")

        cv_text = ""
        cv_id = (body.get("cv_id") or "").strip()
        if cv_id:
            cv = db.get_cv(cv_id, user["id"])
            if cv:
                cv_text = cv.get("text_content") or ""
                send("log", text=f"Сверяю рынок с резюме «{cv.get('original_name') or cv_id}».")

        form = {
            "sources": sources,
            "keyword": keyword or None,
            "query": query or None,
            "region": (body.get("region") or "").strip() or None,
            "pages": pages,
            "delay": delay,
            "all_pages": all_pages,
            "remote": _parse_remote_mode(body.get("remote")),
        }
        try:
            results, analysis = _do_candidate_search(user["id"], form, cv_text, lambda msg: send("log", text=msg))
            send("done", results=results, analysis=analysis)
        except Exception as e:
            send("error", text=str(e))


# ---------------------------------------------------------------------------
# Резюме (CV)
# ---------------------------------------------------------------------------

def _mask_size(n):
    if n < 1024:
        return f"{n} Б"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} КБ"
    return f"{n / 1024 / 1024:.1f} МБ"


@app.route("/api/cvs", methods=["GET"])
@login_required
def api_list_cvs():
    cvs = db.list_cvs(current_user()["id"])
    for c in cvs:
        c["size_human"] = _mask_size(c["size_bytes"])
    return jsonify(cvs)


@app.route("/api/cvs", methods=["POST"])
@login_required
def api_upload_cv():
    uid = current_user()["id"]
    file = request.files.get("file")
    if not file or not file.filename:
        return {"error": "файл не передан"}, 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_CV_FORMATS:
        return {"error": f"формат .{ext} не поддерживается (нужен pdf, docx или txt)"}, 400

    cv_id = uuid.uuid4().hex
    stored_path = db.UPLOADS_DIR / f"{cv_id}.{ext}"
    file.save(stored_path)
    size_bytes = stored_path.stat().st_size

    try:
        text_content = cv_extract.extract_text(stored_path, ext)
    except Exception as e:
        stored_path.unlink(missing_ok=True)
        return {"error": f"не удалось прочитать файл: {e}"}, 400

    if not text_content.strip():
        stored_path.unlink(missing_ok=True)
        return {"error": "не удалось извлечь текст из файла (возможно, это скан без текстового слоя)"}, 400

    db.add_cv(cv_id, uid, file.filename, ext, stored_path, text_content, size_bytes)
    return {"id": cv_id, "original_name": file.filename, "format": ext, "size_bytes": size_bytes}


@app.route("/api/cvs/<cv_id>", methods=["DELETE"])
@login_required
def api_delete_cv(cv_id):
    uid = current_user()["id"]
    ok = db.delete_cv(cv_id, uid)
    if not ok:
        return {"error": "не найдено"}, 404
    db.delete_resume_draft(cv_id, uid)
    return {"ok": True}


@app.route("/api/cvs/<cv_id>/text", methods=["GET"])
@login_required
def api_cv_text(cv_id):
    cv = db.get_cv(cv_id, current_user()["id"])
    if not cv:
        return {"error": "не найдено"}, 404
    return {"text": cv["text_content"]}


def _resume_data_for_cv(uid, cv_id):
    """Данные резюме для HR-аналитики: черновик конструктора или текст загруженного файла."""
    cv = db.get_cv(cv_id, uid)
    if not cv:
        return None
    settings = db.all_settings(uid)
    fallback_headline = (settings.get("profile_headline") or "").strip()
    fallback_location = (settings.get("profile_location") or "").strip()
    draft = db.get_resume_draft(cv_id, uid)
    if draft:
        try:
            data = json.loads(draft.get("data_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        if not (data.get("headline") or "").strip() and fallback_headline:
            data["headline"] = fallback_headline
        if not (data.get("location") or "").strip() and fallback_location:
            data["location"] = fallback_location
        return {
            "name": cv.get("original_name") or "",
            "template": draft.get("template") or "classic",
            "resume_data": data,
        }
    return {
        "name": cv.get("original_name") or "",
        "template": "classic",
        "resume_data": {
            "headline": fallback_headline,
            "location": fallback_location,
            "summary": (cv.get("text_content") or "").strip(),
        },
    }


@app.route("/api/cvs/<cv_id>/hr-source", methods=["GET"])
@login_required
def api_cv_hr_source(cv_id):
    payload = _resume_data_for_cv(current_user()["id"], cv_id)
    if not payload:
        return {"error": "не найдено"}, 404
    return payload


# ---------------------------------------------------------------------------
# Ключи ИИ и Jooble — только владелец, работают на все профили
# ---------------------------------------------------------------------------

def _mask_key(key):
    if not key:
        return None
    if len(key) <= 8:
        return "•" * len(key)
    return key[:4] + "…" + key[-4:]


def _mask_email(email):
    text = (email or "").strip()
    if not text:
        return None
    if "@" not in text:
        return _mask_key(text)
    name, _, host = text.partition("@")
    shown = name[:1] + "…" if len(name) <= 2 else name[:2] + "…"
    return shown + "@" + host


def _public_platform_status():
    s = db.platform_settings()
    boards_ready = {}
    for board, key in (("djinni", "djinni"), ("workua", "workua"), ("rabota", "rabotaua")):
        email, password = _board_admin_credentials(board)
        boards_ready[key] = bool(email.strip() and password)
    return {
        "ai_ready": any(s.get(f"{p}_api_key") for p in ("anthropic", "openai", "gemini")),
        "jooble_ready": bool(s.get("jooble_api_key")),
        "active_provider": s.get("active_provider") or "anthropic",
        "boards_ready": boards_ready,
    }


def _admin_keys_payload():
    s = db.platform_settings()
    status = _public_platform_status()
    payload = {
        **status,
        "anthropic_api_key_set": bool(s.get("anthropic_api_key")),
        "anthropic_api_key_masked": _mask_key(s.get("anthropic_api_key")),
        "anthropic_model": s.get("anthropic_model", ai_match.DEFAULT_ANTHROPIC_MODEL),
        "openai_api_key_set": bool(s.get("openai_api_key")),
        "openai_api_key_masked": _mask_key(s.get("openai_api_key")),
        "openai_model": s.get("openai_model", ai_match.DEFAULT_OPENAI_MODEL),
        "gemini_api_key_set": bool(s.get("gemini_api_key")),
        "gemini_api_key_masked": _mask_key(s.get("gemini_api_key")),
        "gemini_model": s.get("gemini_model", ai_match.DEFAULT_GEMINI_MODEL),
        "jooble_api_key_set": bool(s.get("jooble_api_key")),
        "jooble_api_key_masked": _mask_key(s.get("jooble_api_key")),
    }
    for board, key in (("djinni", "djinni"), ("workua", "workua"), ("rabota", "rabota")):
        ready_key = "rabotaua" if board == "rabota" else board
        email, _password = _board_admin_credentials(board)
        payload[f"{key}_email_set"] = status["boards_ready"][ready_key]
        payload[f"{key}_email_masked"] = _mask_email(email)
        payload[f"{key}_password_set"] = status["boards_ready"][ready_key]
    return payload


def _save_platform_keys(body, actor_id):
    changed = []
    for provider in ("anthropic", "openai", "gemini", "jooble"):
        key_name = f"{provider}_api_key"
        if body.get(key_name):
            db.set_platform_setting(key_name, body[key_name].strip())
            changed.append(key_name)
        if provider != "jooble":
            model_name = f"{provider}_model"
            if body.get(model_name):
                db.set_platform_setting(model_name, body[model_name].strip())
                changed.append(model_name)
    if body.get("active_provider") in ("anthropic", "openai", "gemini"):
        db.set_platform_setting("active_provider", body["active_provider"])
        changed.append("active_provider")
    if changed:
        db.log_activity(actor_id, "keys.save", {"fields": changed})
    return _admin_keys_payload()


@app.route("/api/settings", methods=["GET"])
@login_required
def api_get_settings():
    return _public_platform_status()


@app.route("/api/settings", methods=["POST"])
@login_required
@admin_required
def api_save_settings():
    body = request.get_json(force=True)
    return _save_platform_keys(body, current_user()["id"])


@app.route("/api/settings/<provider>", methods=["DELETE"])
@login_required
@admin_required
def api_delete_key(provider):
    if provider not in ("anthropic", "openai", "gemini", "jooble"):
        return {"error": "неизвестный провайдер"}, 400
    db.delete_platform_setting(f"{provider}_api_key")
    db.log_activity(current_user()["id"], "keys.delete", {"provider": provider})
    return _admin_keys_payload()


@app.route("/api/admin/keys", methods=["GET"])
@login_required
@admin_required
def api_admin_get_keys():
    return _admin_keys_payload()


@app.route("/api/admin/keys", methods=["POST"])
@login_required
@admin_required
def api_admin_save_keys():
    body = request.get_json(force=True)
    return _save_platform_keys(body, current_user()["id"])


@app.route("/api/admin/keys/<provider>", methods=["DELETE"])
@login_required
@admin_required
def api_admin_delete_key(provider):
    return api_delete_key(provider)


# ---------------------------------------------------------------------------
# ИИ: оценка соответствия резюме вакансии + улучшение формулировок
# ---------------------------------------------------------------------------

@app.route("/api/match", methods=["POST"])
@login_required
def api_match():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    job = body.get("job")
    cv_id = body.get("cv_id")
    if not job or not cv_id:
        return {"error": "нужны job и cv_id"}, 400

    cv = db.get_cv(cv_id, uid)
    if not cv:
        return {"error": "резюме не найдено"}, 404

    result, err = _run_ai(
        uid, "ai.match",
        lambda provider, api_key, model: ai_match.match_cv_to_job(
            job, cv["text_content"], provider, api_key, model,
        ),
    )
    if err:
        return err
    return result


@app.route("/api/ai/suggest-headline", methods=["POST"])
@login_required
def api_suggest_headline():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    cv_id = body.get("cv_id")
    if not cv_id:
        return {"error": "нужен cv_id"}, 400

    cv = db.get_cv(cv_id, uid)
    if not cv:
        return {"error": "резюме не найдено"}, 404

    result, err = _run_ai(
        uid, "ai.suggest_headline",
        lambda provider, api_key, model: ai_match.suggest_desired_positions(
            cv["text_content"], job_scraper.KEYWORD_CATEGORIES, provider, api_key, model,
        ),
    )
    if err:
        return err
    return result


@app.route("/api/jobs/rank-by-resume", methods=["POST"])
@login_required
def api_rank_jobs_by_resume():
    """Подбор вакансий под резюме: сначала быстрый детерминированный препросев
    по ключевым словам всего присланного списка (без ИИ — список может быть
    большим), затем настоящая ИИ-оценка (match_cv_to_job) только для топ-5 —
    чтобы не гонять весь список через ИИ по цене и времени."""
    uid = current_user()["id"]
    body = request.get_json(force=True)
    jobs = body.get("jobs") or []
    cv_id = body.get("cv_id")
    if not jobs or not cv_id:
        return {"error": "нужны jobs и cv_id"}, 400
    if len(jobs) > 500:
        return {"error": "слишком много вакансий за один раз"}, 400

    cv = db.get_cv(cv_id, uid)
    if not cv:
        return {"error": "резюме не найдено"}, 404

    pre_ranked = ai_match.rank_jobs_by_resume(cv["text_content"], jobs)

    AI_TOP_N = 5
    results = []
    for r in pre_ranked[:AI_TOP_N]:
        job = jobs[r["index"]]
        ai_result, err = _run_ai(
            uid, "ai.match",
            lambda provider, api_key, model: ai_match.match_cv_to_job(
                job, cv["text_content"], provider, api_key, model,
            ),
        )
        if err:
            results.append(r)
            continue
        results.append({
            "index": r["index"],
            "score": ai_result.get("score", r["score"]),
            "verdict": ai_result.get("verdict"),
            "strengths": ai_result.get("strengths", []),
            "gaps": ai_result.get("gaps", []),
            "matched_keywords": ai_result.get("matched_keywords") or r["matched_keywords"],
        })
    results.extend(pre_ranked[AI_TOP_N:])
    return {"results": results}


@app.route("/api/ai/improve", methods=["POST"])
@login_required
def api_ai_improve():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    text = (body.get("text") or "").strip()
    context = (body.get("context") or "").strip()
    if not text:
        return {"error": "нет текста для улучшения"}, 400

    result, err = _run_ai(
        uid, "ai.improve",
        lambda provider, api_key, model: ai_match.improve_text(text, context, provider, api_key, model),
    )
    if err:
        return err
    return {"text": result}


def _ai_creds():
    s = db.platform_settings()
    preferred = s.get("active_provider") or "anthropic"
    order = [preferred, "anthropic", "openai", "gemini"]
    seen = set()
    for provider in order:
        if provider in seen or provider not in ("anthropic", "openai", "gemini"):
            continue
        seen.add(provider)
        key = s.get(f"{provider}_api_key")
        if key:
            return provider, key, s.get(f"{provider}_model")
    return preferred if preferred in ("anthropic", "openai", "gemini") else "anthropic", None, None


def _run_ai(uid, action, fn):
    provider, api_key, model = _ai_creds()
    try:
        result = fn(provider, api_key, model)
        db.log_activity(uid, action, {"provider": provider, "ok": True})
        return result, None
    except ai_match.AIMatchError as e:
        db.log_activity(uid, action, {"provider": provider, "ok": False, "error": str(e)[:240]})
        return None, ({"error": str(e)}, 400)
    except Exception as e:
        db.log_activity(uid, action, {"provider": provider, "ok": False, "error": str(e)[:240]})
        return None, ({"error": f"неожиданная ошибка: {e}"}, 500)


@app.route("/api/ai/generate-summary", methods=["POST"])
@login_required
def api_ai_generate_summary():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    resume_data = body.get("resume_data") or {}
    job_description = (body.get("job_description") or "").strip()
    result, err = _run_ai(
        uid, "ai.summary",
        lambda provider, api_key, model: ai_match.generate_resume_summary(
            resume_data, job_description, provider, api_key, model,
        ),
    )
    if err:
        return err
    return result


def _fetch_market_fit(uid, resume_data, cv_text):
    """Оперативная сверка резюме с рынком: только djinni.co и robota.ua (быстрые HTTP/API-источники) —
    work.ua здесь намеренно не трогаем, его сбор идёт через headless-браузер и слишком медленный для
    синхронного запроса внутри ИИ-аудита. Возвращает None, если сверка невозможна (нет желаемой
    позиции — не по чему искать похожие вакансии и резюме)."""
    headline = (resume_data.get("headline") or "").strip()
    if not headline:
        return None
    noop_log = lambda msg: None
    form = {
        "sources": ["djinni", "rabotaua"],
        "keyword": headline, "query": None,
        "region": (resume_data.get("location") or "").strip() or None,
        "pages": 1, "delay": 1.5, "all_pages": False,
        "remote": None, "reservation": None,
    }
    jobs = _do_search(uid, form, noop_log, log_activity=False)
    candidates, _ = _do_candidate_search(uid, form, cv_text, noop_log)
    return candidate_scraper.compute_resume_market_fit(candidates, jobs, resume_data, cv_text)


@app.route("/api/ai/audit-resume", methods=["POST"])
@login_required
def api_ai_audit_resume():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    resume_data = body.get("resume_data") or {}
    template = body.get("template") or "classic"
    result, err = _run_ai(
        uid, "ai.audit",
        lambda provider, api_key, model: ai_match.audit_resume(resume_data, template, provider, api_key, model),
    )
    if err:
        return err

    if body.get("compare_market"):
        try:
            market_fit = _fetch_market_fit(uid, resume_data, resume_builder.flatten_text(resume_data))
        except Exception as e:
            market_fit = None
            result["market_fit_error"] = f"Не удалось собрать рыночные данные: {e}"
        if market_fit is None:
            result.setdefault(
                "market_fit_error",
                "Для сверки с рынком укажите желаемую позицию (поле «Желаемая позиция»).",
            )
        else:
            synthesis, synth_err = _run_ai(
                uid, "ai.market_fit",
                lambda provider, api_key, model: ai_match.synthesize_market_fit(
                    resume_data, market_fit, provider, api_key, model,
                ),
            )
            if synth_err:
                market_fit["synthesis_error"] = synth_err[0].get("error")
            else:
                market_fit["synthesis"] = synthesis
            result["market_fit"] = market_fit

    return result


@app.route("/api/ai/market-fit", methods=["POST"])
@login_required
def api_ai_market_fit():
    """Отдельный шаг сверки с рынком — чтобы UI мог показать ход аналитики, а не ждать всё сразу."""
    uid = current_user()["id"]
    body = request.get_json(force=True) or {}
    resume_data = body.get("resume_data") or {}
    try:
        market_fit = _fetch_market_fit(uid, resume_data, resume_builder.flatten_text(resume_data))
    except Exception as e:
        return {"error": f"Не удалось собрать рыночные данные: {e}"}, 400
    if market_fit is None:
        return {
            "skipped": True,
            "error": "Для сверки с рынком укажите желаемую позицию (поле «Желаемая позиция»).",
        }
    synthesis, synth_err = _run_ai(
        uid, "ai.market_fit",
        lambda provider, api_key, model: ai_match.synthesize_market_fit(
            resume_data, market_fit, provider, api_key, model,
        ),
    )
    if synth_err:
        market_fit["synthesis_error"] = synth_err[0].get("error")
    else:
        market_fit["synthesis"] = synthesis
    return {"market_fit": market_fit}


@app.route("/api/ai/red-flags", methods=["POST"])
@login_required
def api_ai_red_flags():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    resume_data = body.get("resume_data") or {}
    result, err = _run_ai(
        uid, "ai.red_flags",
        lambda provider, api_key, model: ai_match.analyze_red_flags(resume_data, provider, api_key, model),
    )
    if err:
        return err
    return result


@app.route("/api/ai/career-trajectory", methods=["POST"])
@login_required
def api_ai_career_trajectory():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    resume_data = body.get("resume_data") or {}
    result, err = _run_ai(
        uid, "ai.trajectory",
        lambda provider, api_key, model: ai_match.suggest_career_trajectory(resume_data, provider, api_key, model),
    )
    if err:
        return err
    return result


@app.route("/api/ai/interview-questions", methods=["POST"])
@login_required
def api_ai_interview_questions():
    uid = current_user()["id"]
    body = request.get_json(force=True)

    cv_id = (body.get("cv_id") or "").strip()
    if cv_id:
        cv = db.get_cv(cv_id, uid)
        if not cv:
            return {"error": "резюме не найдено"}, 404
        cv_text = cv.get("text_content") or ""
    else:
        resume_data = body.get("resume_data") or {}
        cv_text = resume_builder.flatten_text(resume_data)

    job = body.get("job") or {}
    if job:
        job_description = " — ".join(p for p in [job.get("title"), job.get("company")] if p)
        if job.get("description"):
            job_description = f"{job_description}\n\n{job['description']}" if job_description else job["description"]
    else:
        job_description = (body.get("job_description") or "").strip()

    result, err = _run_ai(
        uid, "ai.interview_questions",
        lambda provider, api_key, model: ai_match.generate_interview_questions(
            cv_text, job_description, provider, api_key, model,
        ),
    )
    if err:
        return err
    return result


@app.route("/api/ai/interview-feedback", methods=["POST"])
@login_required
def api_ai_interview_feedback():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    question = body.get("question") or ""
    answer = body.get("answer") or ""

    cv_id = (body.get("cv_id") or "").strip()
    if cv_id:
        cv = db.get_cv(cv_id, uid)
        if not cv:
            return {"error": "резюме не найдено"}, 404
        cv_text = cv.get("text_content") or ""
    else:
        resume_data = body.get("resume_data") or {}
        cv_text = resume_builder.flatten_text(resume_data)

    result, err = _run_ai(
        uid, "ai.interview_feedback",
        lambda provider, api_key, model: ai_match.evaluate_interview_answer(
            question, answer, cv_text, provider, api_key, model,
        ),
    )
    if err:
        return err
    return result


@app.route("/api/ai/interview-chat", methods=["POST"])
@login_required
def api_ai_interview_chat():
    """Один шаг живого пошагового тренажёра собеседования (см. ai_match.hr_interview_turn):
    клиент присылает всю историю разговора, получает следующую реплику HR."""
    uid = current_user()["id"]
    body = request.get_json(force=True)

    cv_id = (body.get("cv_id") or "").strip()
    if cv_id:
        cv = db.get_cv(cv_id, uid)
        if not cv:
            return {"error": "резюме не найдено"}, 404
        cv_text = cv.get("text_content") or ""
    else:
        resume_data = body.get("resume_data") or {}
        cv_text = resume_builder.flatten_text(resume_data)

    job = body.get("job") or {}
    if job:
        job_description = " — ".join(p for p in [job.get("title"), job.get("company")] if p)
        if job.get("description"):
            job_description = f"{job_description}\n\n{job['description']}" if job_description else job["description"]
    else:
        job_description = (body.get("job_description") or "").strip()

    history = body.get("history") or []
    if not isinstance(history, list):
        return {"error": "некорректная история разговора"}, 400

    result, err = _run_ai(
        uid, "ai.interview_chat",
        lambda provider, api_key, model: ai_match.hr_interview_turn(
            cv_text, job_description, history, provider, api_key, model,
        ),
    )
    if err:
        return err
    return result


@app.route("/api/ai/experience-bullets", methods=["POST"])
@login_required
def api_ai_experience_bullets():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    result, err = _run_ai(
        uid, "ai.bullets",
        lambda provider, api_key, model: ai_match.generate_experience_bullets(
            body.get("position"), body.get("company"), body.get("note"), provider, api_key, model,
        ),
    )
    if err:
        return err
    return {"text": result}


@app.route("/api/ai/cover-letter", methods=["POST"])
@login_required
def api_ai_cover_letter():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    job = body.get("job")
    cv_id = body.get("cv_id")
    if not job or not cv_id:
        return {"error": "нужны job и cv_id"}, 400

    cv = db.get_cv(cv_id, uid)
    if not cv:
        return {"error": "резюме не найдено"}, 404

    result, err = _run_ai(
        uid, "ai.cover",
        lambda provider, api_key, model: ai_match.generate_cover_letter(
            job, cv["text_content"], provider, api_key, model,
        ),
    )
    if err:
        return err
    return {"text": result}


@app.route("/api/jobs/apply", methods=["POST"])
@login_required
def api_apply_job():
    """Автоматический отклик — пока только djinni.co, по умолчанию dry-run (см. job_apply.py)."""
    uid = current_user()["id"]
    body = request.get_json(force=True) or {}
    job = body.get("job") or {}
    cv_id = body.get("cv_id")
    confirm = bool(body.get("confirm"))

    if (job.get("source") or "") != "djinni":
        return {"error": "Автоматическая отправка пока доступна только для вакансий djinni.co"}, 400
    if not cv_id:
        return {"error": "нужно выбрать резюме"}, 400
    cv = db.get_cv(cv_id, uid)
    if not cv:
        return {"error": "резюме не найдено"}, 404

    settings = db.all_settings(uid)
    email = (settings.get("cv_djinni_email") or "").strip()
    password = settings.get("cv_djinni_password") or ""
    if not email or not password:
        return {
            "error": "сначала подключите свой аккаунт djinni.co: «Резюме» → «Подтянуть с площадки»",
        }, 400

    cover_letter, err = _run_ai(
        uid, "ai.cover",
        lambda provider, api_key, model: ai_match.generate_cover_letter(
            job, cv["text_content"], provider, api_key, model,
        ),
    )
    if err:
        return err

    try:
        result = job_apply.djinni_apply(email, password, job.get("url"), cover_letter, confirm=confirm)
    except job_apply.ApplyError as e:
        db.log_activity(uid, "job.apply", {"source": "djinni", "confirm": confirm, "ok": False, "error": str(e)[:240]})
        return {"error": str(e)}, 400
    except Exception as e:
        db.log_activity(uid, "job.apply", {"source": "djinni", "confirm": confirm, "ok": False, "error": str(e)[:240]})
        return {"error": f"неожиданная ошибка: {e}"}, 500

    db.log_activity(uid, "job.apply", {"source": "djinni", "confirm": confirm, "ok": True, "status": result.get("status")})
    result["cover_letter"] = cover_letter
    return result


@app.route("/api/ai/build-resume", methods=["POST"])
@login_required
def api_ai_build_resume():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    raw_text = body.get("raw_text") or ""
    qa_history = body.get("qa_history") or []
    result, err = _run_ai(
        uid, "ai.build",
        lambda provider, api_key, model: ai_match.build_resume_from_text(
            raw_text, qa_history, provider, api_key, model,
        ),
    )
    if err:
        return err
    return result


# ---------------------------------------------------------------------------
# Конструктор резюме
# ---------------------------------------------------------------------------

ALLOWED_TEMPLATES = (
    "classic", "modern", "modern-light", "minimal", "executive",
    "compact-ats", "creative", "creative-purple", "custom",
    "editorial", "geo-bold", "twotone-split", "mono-grid",
)

TEMPLATE_STRUCTURE_IDS = (
    "classic-single", "sidebar-left", "sidebar-right", "header-band",
    "diagonal-split", "timeline", "cards", "chip-header",
    "two-col-balance", "initial-badge", "dense-ats",
)

TEMPLATE_THEME_IDS = (
    "ocean-blue", "navy-steel", "slate-graphite", "forest-exec", "burgundy-classic",
    "midnight-indigo", "charcoal-mono", "teal-corporate",
    "sunset-coral", "crimson-pop", "electric-violet", "hot-pink", "amber-blaze",
    "lime-punch", "cobalt-bright", "magenta-flash",
    "dusty-rose", "sage-calm", "taupe-soft", "lavender-mist", "mocha-warm",
    "stone-quiet", "powder-blue", "sand-neutral",
    "terracotta", "golden-hour", "cinnamon", "peach-glow", "coral-reef",
    "mustard-field", "rust-earth",
    "arctic-ice", "deep-sea", "mint-fresh", "glacier-blue", "periwinkle",
    "cyan-tech", "spruce-cool",
    "pure-black", "ink-gray", "paper-white", "graphite-silver", "warm-gray",
    "cool-gray", "onyx-minimal", "porcelain",
)


def _is_allowed_template(template):
    if template in ALLOWED_TEMPLATES:
        return True
    if "__" in template:
        structure_id, _, theme_id = template.partition("__")
        return structure_id in TEMPLATE_STRUCTURE_IDS and theme_id in TEMPLATE_THEME_IDS
    return False


@app.route("/api/resumes/images", methods=["POST"])
@login_required
def api_upload_resume_image():
    file = request.files.get("file")
    if not file or not file.filename:
        return {"error": "файл не передан"}, 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_FORMATS:
        return {"error": "нужен PNG, JPG или WEBP"}, 400

    image_id = uuid.uuid4().hex
    filename = f"{image_id}.{ext}"
    file.save(IMAGES_DIR / filename)
    return {"id": image_id, "url": f"/uploads/images/{filename}"}


@app.route("/uploads/images/<filename>")
@login_required
def uploaded_resume_image(filename):
    return send_from_directory(IMAGES_DIR, filename)


@app.route("/api/resumes/<resume_id>", methods=["GET"])
@login_required
def api_get_resume(resume_id):
    draft = db.get_resume_draft(resume_id, current_user()["id"])
    if not draft:
        return {"error": "не найдено"}, 404
    return {
        "id": draft["id"],
        "template": draft["template"],
        "data": json.loads(draft["data_json"]),
    }


@app.route("/api/resumes", methods=["POST"])
@login_required
def api_save_resume():
    uid = current_user()["id"]
    body = request.get_json(force=True)
    data = body.get("data") or {}
    template = body.get("template") or "classic"
    if not _is_allowed_template(template):
        return {"error": "неизвестный шаблон"}, 400

    resume_id = body.get("id") or uuid.uuid4().hex
    if body.get("id") and not db.get_resume_draft(resume_id, uid):
        return {"error": "резюме не найдено"}, 404

    data_json = json.dumps(data, ensure_ascii=False)
    text_content = resume_builder.flatten_text(data)
    if not text_content.strip():
        return {"error": "резюме пустое — заполните хотя бы имя или раздел"}, 400

    db.save_resume_draft(resume_id, uid, template, data_json)
    title = resume_builder.resume_title(data)
    db.add_cv(
        resume_id, uid, title, "builder", f"builder:{resume_id}",
        text_content, len(text_content.encode("utf-8")),
    )
    return {"id": resume_id, "title": title}


@app.route("/api/resumes/<resume_id>", methods=["DELETE"])
@login_required
def api_delete_resume(resume_id):
    uid = current_user()["id"]
    db.delete_resume_draft(resume_id, uid)
    db.delete_cv(resume_id, uid)
    return {"ok": True}


@app.route("/resume/<resume_id>/print")
@login_required
def resume_print_page(resume_id):
    draft = db.get_resume_draft(resume_id, current_user()["id"])
    if not draft:
        return "Резюме не найдено", 404
    return render_template(
        "resume_print.html",
        resume_id=resume_id,
        template=draft["template"],
        data_json=draft["data_json"],
    )


# ---------------------------------------------------------------------------
# Админка: пользователи + аналитика поиска
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required
@admin_required
def admin_page():
    return render_template("admin.html", user=current_user())


@app.route("/api/admin/overview")
@login_required
@admin_required
def api_admin_overview():
    return {
        "stats": db.platform_stats(),
        "users": db.list_users(),
        "analytics": db.search_analytics(days=14),
        "keys": _admin_keys_payload(),
        "activity": db.list_activity(limit=80),
        "activity_counts": db.activity_counts(days=14),
    }


@app.route("/api/admin/activity")
@login_required
@admin_required
def api_admin_activity():
    action = (request.args.get("action") or "").strip() or None
    try:
        limit = max(1, min(200, int(request.args.get("limit", 80))))
    except (TypeError, ValueError):
        limit = 80
    return {"items": db.list_activity(limit=limit, action=action)}


if __name__ == "__main__":
    threading.Thread(target=_background_search_loop, daemon=True).start()
    print("Открой http://127.0.0.1:5057", file=sys.stderr)
    app.run(host=os.environ.get("JOBPILOT_HOST", "127.0.0.1"), port=5057, debug=False, threaded=True)

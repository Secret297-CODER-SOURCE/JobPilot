"""
Хранилище платформы JobPilot: SQLite, многопользовательское.

Ключи ИИ, Jooble и входы на площадки — общие на всю платформу (задаёт только владелец в админке).
Резюме и фильтры поиска — у каждого пользователя свои. Кэш выдачи вакансий
общий: одинаковый запрос возвращает одно и то же независимо от того, кто ищет.
Файлы резюме лежат на диске в uploads/, в базе — метаданные и извлечённый текст.
"""

import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("JOBPILOT_DATA_DIR") or Path(__file__).parent)
DB_PATH = DATA_DIR / "app.db"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True, parents=True)

SEARCH_CACHE_TTL = 15 * 60  # 15 минут — вакансии не протухают мгновенно, но и не зависают навечно


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        );
        CREATE TABLE IF NOT EXISTS cvs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            original_name TEXT NOT NULL,
            format TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            text_content TEXT,
            size_bytes INTEGER NOT NULL,
            uploaded_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS resume_drafts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            template TEXT NOT NULL,
            data_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS search_cache (
            cache_key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            results_json TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            query_sig TEXT NOT NULL,
            title TEXT,
            company TEXT,
            salary TEXT,
            meta TEXT,
            url TEXT,
            description TEXT,
            first_seen_at REAL NOT NULL,
            last_seen_at REAL NOT NULL,
            removed_at REAL
        );
        CREATE TABLE IF NOT EXISTS candidates (
            key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            query_sig TEXT NOT NULL,
            title TEXT,
            salary TEXT,
            city TEXT,
            experience_years REAL,
            skills TEXT,
            snippet TEXT,
            url TEXT,
            first_seen_at REAL NOT NULL,
            last_seen_at REAL NOT NULL,
            removed_at REAL
        );
        CREATE INDEX IF NOT EXISTS idx_candidates_query ON candidates(query_sig, removed_at);
        CREATE TABLE IF NOT EXISTS search_log (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            source TEXT NOT NULL,
            keyword TEXT,
            query TEXT,
            region TEXT,
            result_count INTEGER NOT NULL,
            cache_hit INTEGER NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT NOT NULL,
            detail TEXT,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cvs_user ON cvs(user_id);
        CREATE INDEX IF NOT EXISTS idx_resume_drafts_user ON resume_drafts(user_id);
        CREATE INDEX IF NOT EXISTS idx_search_log_created ON search_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_log(action);
        CREATE INDEX IF NOT EXISTS idx_jobs_query ON jobs(query_sig, removed_at);
    """)
    conn.commit()
    conn.close()
    migrate_platform_keys()


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------

def create_user(user_id, email, password_hash, name, role="user"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (id, email, password_hash, name, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, email.lower().strip(), password_hash, name, role, time.time()),
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_name(user_id, name):
    conn = get_conn()
    conn.execute("UPDATE users SET name=? WHERE id=?", (name, user_id))
    conn.commit()
    conn.close()


def update_user_email(user_id, email):
    conn = get_conn()
    try:
        conn.execute("UPDATE users SET email=? WHERE id=?", (email.lower().strip(), user_id))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("email taken")
    conn.close()


def count_users():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    conn.close()
    return n


def list_users():
    conn = get_conn()
    rows = conn.execute("SELECT id, email, name, role, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Входы на площадки, которые когда-то жили в platform settings (не ключи ИИ/Jooble).
_BOARD_PLATFORM_SECRETS = (
    "djinni_email", "djinni_password",
    "workua_email", "workua_password",
    "rabota_email", "rabota_password",
)


def wipe_personal_data():
    """Удалить аккаунты, резюме, логи и входы на площадки.

    Ключи ИИ и Jooble платформы не трогает — это конфигурация сервиса, не профиль.
    """
    conn = get_conn()
    cv_paths = [row["stored_path"] for row in conn.execute("SELECT stored_path FROM cvs")]
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM settings WHERE user_id != ?", (PLATFORM_UID,))
    conn.execute("DELETE FROM cvs")
    conn.execute("DELETE FROM resume_drafts")
    conn.execute("DELETE FROM activity_log")
    conn.execute("DELETE FROM search_log")
    for key in _BOARD_PLATFORM_SECRETS:
        conn.execute("DELETE FROM settings WHERE user_id=? AND key=?", (PLATFORM_UID, key))
    conn.commit()
    conn.close()

    for raw in cv_paths:
        try:
            Path(raw).unlink(missing_ok=True)
        except OSError:
            pass
    if UPLOADS_DIR.exists():
        for path in UPLOADS_DIR.rglob("*"):
            if path.is_file() and path.name != ".DS_Store":
                try:
                    path.unlink()
                except OSError:
                    pass

    conn = get_conn()
    conn.execute("VACUUM")
    conn.close()


# ---------------------------------------------------------------------------
# Настройки (на пользователя)
# ---------------------------------------------------------------------------

def set_setting(user_id, key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
        (user_id, key, value),
    )
    conn.commit()
    conn.close()


def get_setting(user_id, key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE user_id=? AND key=?", (user_id, key)).fetchone()
    conn.close()
    return row["value"] if row else default


def delete_setting(user_id, key):
    conn = get_conn()
    conn.execute("DELETE FROM settings WHERE user_id=? AND key=?", (user_id, key))
    conn.commit()
    conn.close()


def all_settings(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# Ключи ИИ и Jooble принадлежат платформе, не профилю пользователя. Входы на площадки для
# «Рынка кандидатов» отдельно на платформе не хранятся — берутся из личного cv_<board>_email/
# password владельца (см. webapp._board_admin_credentials и «Моё резюме с площадок»).
PLATFORM_UID = "__platform__"
PLATFORM_KEY_FIELDS = (
    "anthropic_api_key", "openai_api_key", "gemini_api_key", "jooble_api_key",
    "anthropic_model", "openai_model", "gemini_model", "active_provider",
)


def set_platform_setting(key, value):
    set_setting(PLATFORM_UID, key, value)


def get_platform_setting(key, default=None):
    return get_setting(PLATFORM_UID, key, default)


def delete_platform_setting(key):
    delete_setting(PLATFORM_UID, key)


def platform_settings():
    return all_settings(PLATFORM_UID)


def migrate_platform_keys():
    """Если владелец раньше хранил ключи в своём профиле — перенести на платформу."""
    current = platform_settings()
    if any(current.get(k) for k in PLATFORM_KEY_FIELDS if k.endswith("_api_key")):
        return
    try:
        users = list_users()
    except sqlite3.OperationalError:
        return
    for user in users:
        if user.get("role") != "admin":
            continue
        s = all_settings(user["id"])
        if not any(s.get(k) for k in PLATFORM_KEY_FIELDS if k.endswith("_api_key")):
            continue
        for key in PLATFORM_KEY_FIELDS:
            val = s.get(key)
            if val and not current.get(key):
                set_platform_setting(key, val)
        return


# ---------------------------------------------------------------------------
# Журнал действий (админка)
# ---------------------------------------------------------------------------

def log_activity(user_id, action, detail=None):
    import uuid
    payload = json.dumps(detail, ensure_ascii=False) if detail is not None else None
    conn = get_conn()
    conn.execute(
        "INSERT INTO activity_log (id, user_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, user_id, action, payload, time.time()),
    )
    conn.commit()
    conn.close()


def list_activity(limit=80, offset=0, action=None):
    conn = get_conn()
    params = []
    where = ""
    if action:
        where = "WHERE a.action = ?"
        params.append(action)
    params.extend([limit, offset])
    rows = conn.execute(
        f"""SELECT a.id, a.user_id, a.action, a.detail, a.created_at,
                   u.email, u.name, u.role
            FROM activity_log a
            LEFT JOIN users u ON u.id = a.user_id
            {where}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?""",
        params,
    ).fetchall()
    conn.close()
    out = []
    for row in rows:
        item = dict(row)
        raw = item.get("detail")
        if raw:
            try:
                item["detail"] = json.loads(raw)
            except (TypeError, ValueError):
                item["detail"] = {"raw": raw}
        else:
            item["detail"] = None
        out.append(item)
    return out


def activity_counts(days=14):
    since = time.time() - days * 86400
    conn = get_conn()
    rows = conn.execute(
        "SELECT action, COUNT(*) AS n FROM activity_log WHERE created_at >= ? GROUP BY action ORDER BY n DESC",
        (since,),
    ).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM activity_log WHERE created_at >= ?",
        (since,),
    ).fetchone()["n"]
    conn.close()
    return {"total": total or 0, "by_action": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Резюме (файлы и конструктор)
# ---------------------------------------------------------------------------

def add_cv(cv_id, user_id, original_name, fmt, stored_path, text_content, size_bytes):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO cvs (id, user_id, original_name, format, stored_path, text_content, size_bytes, uploaded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (cv_id, user_id, original_name, fmt, str(stored_path), text_content, size_bytes, time.time()),
    )
    conn.commit()
    conn.close()


def list_cvs(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, original_name, format, size_bytes, uploaded_at, "
        "length(text_content) as text_len FROM cvs WHERE user_id=? ORDER BY uploaded_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cv(cv_id, user_id=None):
    conn = get_conn()
    if user_id is None:
        row = conn.execute("SELECT * FROM cvs WHERE id=?", (cv_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM cvs WHERE id=? AND user_id=?", (cv_id, user_id)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_cv(cv_id, user_id):
    cv = get_cv(cv_id, user_id)
    if not cv:
        return False
    conn = get_conn()
    conn.execute("DELETE FROM cvs WHERE id=? AND user_id=?", (cv_id, user_id))
    conn.commit()
    conn.close()
    try:
        Path(cv["stored_path"]).unlink(missing_ok=True)
    except OSError:
        pass
    return True


def save_resume_draft(resume_id, user_id, template, data_json):
    conn = get_conn()
    conn.execute(
        "INSERT INTO resume_drafts (id, user_id, template, data_json, updated_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET template=excluded.template, data_json=excluded.data_json, updated_at=excluded.updated_at",
        (resume_id, user_id, template, data_json, time.time()),
    )
    conn.commit()
    conn.close()


def get_resume_draft(resume_id, user_id=None):
    conn = get_conn()
    if user_id is None:
        row = conn.execute("SELECT * FROM resume_drafts WHERE id=?", (resume_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM resume_drafts WHERE id=? AND user_id=?", (resume_id, user_id)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_resume_draft(resume_id, user_id):
    conn = get_conn()
    conn.execute("DELETE FROM resume_drafts WHERE id=? AND user_id=?", (resume_id, user_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Кэш поиска вакансий (общий для всех пользователей)
# ---------------------------------------------------------------------------

def make_cache_key(source, params):
    raw = json.dumps({"source": source, **params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_search(cache_key):
    conn = get_conn()
    row = conn.execute(
        "SELECT results_json, created_at FROM search_cache WHERE cache_key=?", (cache_key,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    if time.time() - row["created_at"] > SEARCH_CACHE_TTL:
        return None
    return json.loads(row["results_json"])


def set_cached_search(cache_key, source, results):
    conn = get_conn()
    conn.execute(
        "INSERT INTO search_cache (cache_key, source, results_json, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(cache_key) DO UPDATE SET results_json=excluded.results_json, created_at=excluded.created_at",
        (cache_key, source, json.dumps(results, ensure_ascii=False), time.time()),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Постоянный учёт вакансий (общий для всех пользователей) — честные "новая" /
# "уже видели" / "реально пропала", в отличие от 15-минутного search_cache.
# ---------------------------------------------------------------------------

def upsert_jobs(jobs_with_keys, query_sig):
    """jobs_with_keys — список (key, job_dict). Возвращает {key: is_new} — is_new=True только
    для вакансий, которых раньше не было в базе вообще (не для этого query_sig, а вообще)."""
    if not jobs_with_keys:
        return {}
    now = time.time()
    conn = get_conn()
    is_new = {}
    for key, job in jobs_with_keys:
        row = conn.execute("SELECT 1 FROM jobs WHERE key=?", (key,)).fetchone()
        is_new[key] = row is None
        if row is None:
            conn.execute(
                "INSERT INTO jobs (key, source, query_sig, title, company, salary, meta, url, "
                "description, first_seen_at, last_seen_at, removed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (key, job.get("source", ""), query_sig, job.get("title"), job.get("company"),
                 job.get("salary"), job.get("meta"), job.get("url"), job.get("description"), now, now),
            )
        else:
            conn.execute(
                "UPDATE jobs SET query_sig=?, title=?, company=?, salary=?, meta=?, url=?, "
                "description=?, last_seen_at=?, removed_at=NULL WHERE key=?",
                (query_sig, job.get("title"), job.get("company"), job.get("salary"), job.get("meta"),
                 job.get("url"), job.get("description"), now, key),
            )
    conn.commit()
    conn.close()
    return is_new


def mark_missing_removed(query_sig, seen_keys):
    """Только после ПОЛНОГО прохода по источнику+запросу: всё, что раньше видели под этим
    query_sig и не встретили в этот раз, считается реально пропавшим с сайта."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT key FROM jobs WHERE query_sig=? AND removed_at IS NULL", (query_sig,)
    ).fetchall()
    stale = [r["key"] for r in rows if r["key"] not in seen_keys]
    if stale:
        now = time.time()
        conn.executemany(
            "UPDATE jobs SET removed_at=? WHERE key=?", [(now, key) for key in stale]
        )
        conn.commit()
    conn.close()
    return len(stale)


def list_jobs_by_query_sigs(query_sigs, limit_per_sig=400):
    """Вакансии из постоянного хранилища под указанными query_sig (ещё не пропавшие).

    Берём лимит с КАЖДОГО источника отдельно: один общий LIMIT по first_seen_at
    отдаёт почти только Jooble (сотни свежих карточек) и прячет robota.ua / work.ua.
    """
    query_sigs = [s for s in (query_sigs or []) if s]
    if not query_sigs:
        return []
    per = max(1, int(limit_per_sig or 400))
    conn = get_conn()
    jobs = []
    try:
        for sig in query_sigs:
            rows = conn.execute(
                "SELECT source, title, company, salary, meta, url, description, first_seen_at "
                "FROM jobs WHERE query_sig=? AND removed_at IS NULL "
                "ORDER BY last_seen_at DESC LIMIT ?",
                (sig, per),
            ).fetchall()
            jobs.extend(dict(r) for r in rows)
    finally:
        conn.close()
    jobs.sort(key=lambda j: j.get("first_seen_at") or 0, reverse=True)
    return jobs


# ---------------------------------------------------------------------------
# Постоянный учёт карточек «Рынка кандидатов» — та же честная логика
# новое/уже видели/пропало, что и у вакансий (upsert_jobs/mark_missing_removed).
# ---------------------------------------------------------------------------

def upsert_candidates(candidates_with_keys, query_sig):
    """candidates_with_keys — список (key, card_dict). Возвращает {key: is_new}."""
    if not candidates_with_keys:
        return {}
    now = time.time()
    conn = get_conn()
    is_new = {}
    for key, card in candidates_with_keys:
        row = conn.execute("SELECT 1 FROM candidates WHERE key=?", (key,)).fetchone()
        is_new[key] = row is None
        skills_json = json.dumps(card.get("skills") or [], ensure_ascii=False)
        if row is None:
            conn.execute(
                "INSERT INTO candidates (key, source, query_sig, title, salary, city, "
                "experience_years, skills, snippet, url, first_seen_at, last_seen_at, removed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (key, card.get("source", ""), query_sig, card.get("title"), card.get("salary"),
                 card.get("city"), card.get("experience_years"), skills_json, card.get("snippet"),
                 card.get("url"), now, now),
            )
        else:
            conn.execute(
                "UPDATE candidates SET query_sig=?, title=?, salary=?, city=?, experience_years=?, "
                "skills=?, snippet=?, url=?, last_seen_at=?, removed_at=NULL WHERE key=?",
                (query_sig, card.get("title"), card.get("salary"), card.get("city"),
                 card.get("experience_years"), skills_json, card.get("snippet"), card.get("url"), now, key),
            )
    conn.commit()
    conn.close()
    return is_new


def mark_missing_candidates_removed(query_sig, seen_keys):
    """Только после ПОЛНОГО прохода: карточки под этим query_sig, не встреченные в этот раз,
    считаются реально снятыми с публикации."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT key FROM candidates WHERE query_sig=? AND removed_at IS NULL", (query_sig,)
    ).fetchall()
    stale = [r["key"] for r in rows if r["key"] not in seen_keys]
    if stale:
        now = time.time()
        conn.executemany(
            "UPDATE candidates SET removed_at=? WHERE key=?", [(now, key) for key in stale]
        )
        conn.commit()
    conn.close()
    return len(stale)


def list_candidates_by_query_sigs(query_sigs, limit_per_sig=400):
    """Карточки кандидатов из постоянного хранилища под указанными query_sig (ещё не пропавшие)."""
    query_sigs = [s for s in (query_sigs or []) if s]
    if not query_sigs:
        return []
    per = max(1, int(limit_per_sig or 400))
    conn = get_conn()
    cards = []
    try:
        for sig in query_sigs:
            rows = conn.execute(
                "SELECT source, title, salary, city, experience_years, skills, snippet, url, first_seen_at "
                "FROM candidates WHERE query_sig=? AND removed_at IS NULL "
                "ORDER BY last_seen_at DESC LIMIT ?",
                (sig, per),
            ).fetchall()
            for r in rows:
                card = dict(r)
                try:
                    card["skills"] = json.loads(card.get("skills") or "[]")
                except (TypeError, ValueError):
                    card["skills"] = []
                cards.append(card)
    finally:
        conn.close()
    cards.sort(key=lambda c: c.get("first_seen_at") or 0, reverse=True)
    return cards


def log_search(user_id, source, keyword, query, region, result_count, cache_hit):
    import uuid
    conn = get_conn()
    conn.execute(
        "INSERT INTO search_log (id, user_id, source, keyword, query, region, result_count, cache_hit, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, user_id, source, keyword, query, region, result_count, int(cache_hit), time.time()),
    )
    conn.commit()
    conn.close()


def _normalize_search_term(term):
    return re.sub(r"\s+", " ", (term or "").strip()).casefold()


def merge_top_keywords(rows, limit=10):
    """Склеить одинаковые запросы без учёта регистра и лишних пробелов."""
    buckets = {}
    for row in rows:
        raw = (row.get("term") or "").strip()
        if not raw:
            continue
        key = _normalize_search_term(raw)
        rec = buckets.setdefault(key, {"n": 0, "spellings": {}})
        rec["n"] += int(row.get("n") or 0)
        rec["spellings"][raw] = rec["spellings"].get(raw, 0) + int(row.get("n") or 0)
    merged = []
    for rec in buckets.values():
        display = max(rec["spellings"].items(), key=lambda kv: (kv[1], -len(kv[0])))[0]
        merged.append({"term": display, "n": rec["n"]})
    merged.sort(key=lambda item: (-item["n"], item["term"].casefold()))
    return merged[:limit]


def search_analytics(days=14):
    since = time.time() - days * 86400
    conn = get_conn()
    by_source = conn.execute(
        "SELECT source, COUNT(*) AS n, SUM(cache_hit) AS hits, SUM(result_count) AS total_results "
        "FROM search_log WHERE created_at >= ? GROUP BY source ORDER BY n DESC",
        (since,),
    ).fetchall()
    by_day = conn.execute(
        "SELECT date(created_at, 'unixepoch') AS day, COUNT(*) AS n "
        "FROM search_log WHERE created_at >= ? GROUP BY day ORDER BY day ASC",
        (since,),
    ).fetchall()
    top_keywords = conn.execute(
        "SELECT TRIM(COALESCE(NULLIF(keyword, ''), query)) AS term, COUNT(*) AS n "
        "FROM search_log WHERE created_at >= ? "
        "AND TRIM(COALESCE(NULLIF(keyword, ''), query)) != '' "
        "GROUP BY term ORDER BY n DESC",
        (since,),
    ).fetchall()
    totals = conn.execute(
        "SELECT COUNT(*) AS n, SUM(cache_hit) AS hits FROM search_log WHERE created_at >= ?",
        (since,),
    ).fetchone()
    conn.close()
    return {
        "by_source": [dict(r) for r in by_source],
        "by_day": [dict(r) for r in by_day],
        "top_keywords": merge_top_keywords([dict(r) for r in top_keywords], limit=10),
        "total_searches": totals["n"] or 0,
        "total_cache_hits": totals["hits"] or 0,
    }


def platform_stats():
    conn = get_conn()
    n_users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    n_cvs = conn.execute("SELECT COUNT(*) AS n FROM cvs").fetchone()["n"]
    n_resumes = conn.execute("SELECT COUNT(*) AS n FROM resume_drafts").fetchone()["n"]
    n_cache_entries = conn.execute("SELECT COUNT(*) AS n FROM search_cache").fetchone()["n"]
    conn.close()
    return {
        "users": n_users,
        "cvs": n_cvs,
        "resumes": n_resumes,
        "cache_entries": n_cache_entries,
    }

"""Автоматический отклик на вакансию djinni.co от имени соискателя.

Только djinni.co: отклик там достижим через обычную HTTP-сессию (как вход соискателя в
board_auth.djinni_candidate_login), без Cloudflare/Playwright. work.ua и robota.ua требуют
браузерной автоматизации с обходом защиты — это отдельная, более рискованная задача.

ВАЖНО, честно: форма отклика на странице вакансии находится динамически (по регулярке на
живой HTML), а не по жёстко зашитому URL/полям — так надёжнее, но это всё равно не проверено
на реальном сайте, потому что проверить можно только отправив настоящий отклик настоящему
работодателю. Поэтому по умолчанию — dry-run (confirm=False): доходим до формы, показываем,
что нашли и что собираемся отправить, но не жмём финальную кнопку. Реальная отправка — только
через confirm=True, и только после того как пользователь увидел dry-run своими глазами.
"""

import re

import board_auth

_APPLY_FORM_RE = re.compile(
    r'<form[^>]+action=["\']([^"\']*(?:apply|respond|vidguk)[^"\']*)["\'][^>]*>(.*?)</form>',
    re.I | re.S,
)
_TEXTAREA_NAME_RE = re.compile(
    r'<textarea[^>]+name=["\'](\w*(?:cover|message|text|letter|note)\w*)["\']', re.I,
)


class ApplyError(Exception):
    pass


def _absolute_djinni_url(url):
    if url.startswith("http"):
        return url
    return "https://djinni.co" + (url if url.startswith("/") else f"/{url}")


def djinni_apply(email, password, job_url, cover_letter, *, confirm=False, session=None, login=None, log=None):
    log = log or (lambda msg: None)
    login = login or board_auth.djinni_candidate_login
    if not job_url:
        raise ApplyError("нет ссылки на вакансию")

    sess = login(email, password, log=log, session=session)

    try:
        html = sess.get(job_url)
    except Exception as e:
        raise ApplyError(f"не удалось открыть страницу вакансии: {e}") from e
    if board_auth.djinni_page_requires_login(html):
        raise ApplyError("djinni.co не признал вход соискателя — проверьте email и пароль в настройках")

    m = _APPLY_FORM_RE.search(html)
    if not m:
        raise ApplyError(
            "не нашёл форму отклика на странице вакансии — возможно, вы уже откликались, "
            "вакансия закрыта, или djinni.co поменял разметку"
        )
    action_url, form_html = m.group(1), m.group(2)
    action_url = _absolute_djinni_url(action_url)
    csrf = board_auth.extract_csrf(form_html) or board_auth.extract_csrf(html)
    if not csrf:
        raise ApplyError("не нашёл CSRF-токен формы отклика")

    text_field = None
    tm = _TEXTAREA_NAME_RE.search(form_html)
    if tm:
        text_field = tm.group(1)

    payload = {"csrfmiddlewaretoken": csrf}
    if text_field:
        payload[text_field] = cover_letter[:4000]

    preview = {
        "action_url": action_url,
        "fields": sorted(payload.keys()),
        "cover_letter_preview": cover_letter[:400],
        "has_text_field": bool(text_field),
    }

    if not confirm:
        log("[djinni-apply] dry-run: форма отклика найдена, ничего не отправлено")
        return {"status": "dry_run", **preview}

    try:
        sess.post(action_url, data=payload, headers={"Referer": job_url, "Origin": "https://djinni.co"})
    except Exception as e:
        raise ApplyError(f"форма найдена, но отправка не удалась: {e}") from e
    log("[djinni-apply] отклик отправлен")
    return {"status": "sent", **preview}

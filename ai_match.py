"""
Оценка соответствия резюме вакансии через ИИ (Anthropic, OpenAI или Gemini).
Ключи и модель задаёт владелец в админке (общие на всю платформу) —
никуда, кроме выбранного провайдера, не отправляются.
"""

import datetime
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

import resume_builder

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

_PROMPT_TEMPLATE = """Ты — ассистент по подбору персонала. Оцени, насколько резюме кандидата подходит под вакансию.

ВАКАНСИЯ:
Название: {title}
Компания: {company}
Описание: {description}

РЕЗЮМЕ КАНДИДАТА:
{cv_text}

Дополнительно выдели ключевые слова/навыки из описания вакансии (технологии, инструменты, требования) и \
проверь по тексту резюме, какие из них там явно присутствуют, а каких не хватает — это важно, потому что \
многие компании фильтруют резюме по ключевым словам автоматически.

Отдельно: по пробелам между резюме и вакансией сформулируй, что кандидату стоит почитать или подтянуть \
ПЕРЕД откликом — конкретные темы/навыки/технологии, не общие слова, и только то, что реально следует из \
описания вакансии (не выдумывай требований, которых там нет).

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"score": <число от 0 до 100>, "verdict": "<краткий вывод одним предложением>", "strengths": ["<сильная сторона>", ...], "gaps": ["<чего не хватает>", ...], "matched_keywords": ["<ключевое слово из вакансии, которое есть в резюме>", ...], "missing_keywords": ["<ключевое слово из вакансии, которого нет в резюме>", ...], "study_recommendations": ["<конкретная тема/навык почитать или подтянуть перед откликом>", ...], "recommendation": "<1-2 конкретных предложения, что стоит добавить или подчеркнуть в резюме перед откликом>"}}
"""


class AIMatchError(Exception):
    pass


def _build_prompt(job, cv_text):
    return _PROMPT_TEMPLATE.format(
        title=job.get("title", "")[:300],
        company=job.get("company", "")[:200],
        description=(job.get("description", "") or "")[:4000],
        cv_text=cv_text[:6000],
    )


def _extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        return json.loads(m.group(0))
    raise AIMatchError("Модель вернула ответ не в формате JSON")


def _call_anthropic(prompt, api_key, model):
    body = json.dumps({
        "model": model or DEFAULT_ANTHROPIC_MODEL,
        "max_tokens": 600,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise AIMatchError(f"Anthropic API вернул ошибку {e.code}: {detail[:300]}")
    text = "".join(block.get("text", "") for block in data.get("content", []))
    return text


def _call_openai(prompt, api_key, model):
    body = json.dumps({
        "model": model or DEFAULT_OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise AIMatchError(f"OpenAI API вернул ошибку {e.code}: {detail[:300]}")
    return data["choices"][0]["message"]["content"]


def _call_gemini(prompt, api_key, model):
    model = model or DEFAULT_GEMINI_MODEL
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={urllib.parse.quote(api_key)}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise AIMatchError(f"Gemini API вернул ошибку {e.code}: {detail[:300]}")
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise AIMatchError(f"Gemini вернул неожиданный ответ: {json.dumps(data)[:300]}")


def _dispatch(prompt, provider, api_key, model):
    if not api_key:
        raise AIMatchError(f"Нет сохранённого ключа для провайдера {provider}")
    if provider == "anthropic":
        return _call_anthropic(prompt, api_key, model)
    if provider == "openai":
        return _call_openai(prompt, api_key, model)
    if provider == "gemini":
        return _call_gemini(prompt, api_key, model)
    raise AIMatchError(f"Неизвестный провайдер: {provider}")


def match_cv_to_job(job, cv_text, provider, api_key, model=None):
    prompt = _build_prompt(job, cv_text)
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result["score"] = max(0, min(100, int(result.get("score", 0))))
    result.setdefault("verdict", "")
    result.setdefault("strengths", [])
    result.setdefault("gaps", [])
    result.setdefault("matched_keywords", [])
    result.setdefault("missing_keywords", [])
    result.setdefault("study_recommendations", [])
    result.setdefault("recommendation", "")
    return result


_IMPROVE_PROMPT = """Ты — редактор резюме. Перепиши текст ниже так, чтобы он звучал профессиональнее, \
конкретнее и по делу (сильные глаголы действия, при возможности — измеримый результат), сохранив язык \
оригинала и фактическое содержание. В ответе — только переписанный текст, без кавычек и пояснений.

Контекст: {context}

Текст:
{text}
"""


def improve_text(text, context, provider, api_key, model=None):
    prompt = _IMPROVE_PROMPT.format(context=context or "текст резюме", text=text[:4000])
    raw_text = _dispatch(prompt, provider, api_key, model)
    return raw_text.strip().strip('"')


_GENERATE_SUMMARY_PROMPT = """Ты — карьерный консультант. Ниже — РЕАЛЬНЫЕ данные резюме кандидата в формате JSON. \
Сформулируй по ним короткий раздел "О себе" (2–4 предложения, на языке резюме).

Строго важно: используй ТОЛЬКО факты, которые есть в данных ниже. Не придумывай опыт, компании, годы, \
навыки или достижения, которых там нет. Если данных мало — просто честно обобщи то, что есть, коротко.

{job_block}

Данные резюме (JSON):
{resume_json}

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"summary": "<текст о себе>", "skills": ["<навык из тех, что уже перечислены в данных>", ...]}}

В "skills" верни только навыки, которые уже есть в поле skills данных резюме, просто переупорядоченные \
по релевантности{job_note}. Не добавляй ни одного навыка, которого там не было.
"""


def generate_resume_summary(resume_data, job_description, provider, api_key, model=None):
    original_skills = [s.strip() for s in (resume_data.get("skills") or "").split(",") if s.strip()]
    has_content = any([
        resume_data.get("experience"), resume_data.get("education"),
        original_skills, resume_data.get("summary"),
    ])
    if not has_content:
        raise AIMatchError("Сначала заполните хотя бы опыт работы, образование или навыки")

    if job_description:
        job_block = f"Целевая вакансия, под которую нужно сделать акценты:\n{job_description[:3000]}"
        job_note = " к этой вакансии"
    else:
        job_block = "Конкретная вакансия не указана — просто честно обобщи опыт кандидата."
        job_note = ""

    resume_json = json.dumps({
        "headline": resume_data.get("headline"),
        "summary": resume_data.get("summary"),
        "experience": resume_data.get("experience"),
        "education": resume_data.get("education"),
        "skills": original_skills,
        "languages": resume_data.get("languages"),
    }, ensure_ascii=False)[:6000]

    prompt = _GENERATE_SUMMARY_PROMPT.format(job_block=job_block, resume_json=resume_json, job_note=job_note)
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result.setdefault("summary", "")
    returned_skills = result.get("skills") or []
    # Защита от галлюцинаций: оставляем только те навыки, что реально были введены пользователем.
    allowed = {s.lower() for s in original_skills}
    safe_skills = [s for s in returned_skills if s.lower() in allowed]
    result["skills"] = safe_skills or original_skills
    return result


_ATS_TEMPLATE_NOTES = {
    "classic": ("ok", "Один столбец, простая структура — стандартные ATS-парсеры читают такое резюме без проблем."),
    "minimal": ("ok", "Один столбец, минимум украшений — хорошо читается автоматическими системами."),
    "compact-ats": ("ok", "Этот шаблон специально сделан для автоматического парсинга — самый безопасный вариант для откликов через корпоративные формы."),
    "creative": ("ok", "Цветной баннер — просто фон, сам текст идёт одной колонкой, большинство ATS справляется."),
    "creative-purple": ("ok", "Цветной баннер — просто фон, сам текст идёт одной колонкой, большинство ATS справляется."),
    "modern": ("warning", "Двухколоночная раскладка — часть старых ATS-парсеров путает порядок текста между колонками. Если откликаетесь через корпоративную форму крупной компании, держите про запас вариант в шаблоне «ATS-простой»."),
    "modern-light": ("warning", "Двухколоночная раскладка — см. предупреждение для «Современного» шаблона."),
    "executive": ("warning", "Есть боковая колонка с навыками — некоторые ATS-системы читают её текст не в том порядке."),
    "custom": ("warning", "Свободное размещение блоков сложнее всего для автоматического парсинга. Используйте этот вариант, когда резюме читает человек, а не форма с ATS."),
    "editorial": ("warning", "Асимметричная раскладка в две колонки с крупной типографикой — читается человеком отлично, но часть ATS может путать порядок текста. Для откликов через корпоративные формы держите про запас «ATS-простой»."),
    "geo-bold": ("warning", "Графические элементы и две колонки — сделан, чтобы произвести впечатление на человека, а не на автоматический парсер."),
    "twotone-split": ("warning", "Боковая панель с фото и контактами отдельно от основного текста — некоторые ATS-системы читают её не в том порядке или пропускают."),
    "mono-grid": ("ok", "Один столбец, строгая сетка без графики поверх текста — читается автоматическими системами почти как «ATS-простой»."),
}


def _deterministic_checks(resume_data, template):
    checks = []

    contacts = [resume_data.get("email"), resume_data.get("phone"), resume_data.get("location")]
    n_present = sum(1 for c in contacts if (c or "").strip())
    if n_present == 3:
        checks.append({"item": "Контактные данные", "status": "ok", "note": "Email, телефон и город указаны."})
    elif n_present > 0:
        checks.append({"item": "Контактные данные", "status": "warning", "note": "Указаны не все контакты — заполните оставшиеся."})
    else:
        checks.append({"item": "Контактные данные", "status": "missing", "note": "Не указаны ни email, ни телефон, ни город."})

    has_summary = bool((resume_data.get("summary") or "").strip())
    has_experience = bool(resume_data.get("experience"))
    if not has_experience:
        checks.append({"item": "Структура разделов", "status": "missing", "note": "Нет раздела «Опыт работы» — он ключевой почти для любой вакансии."})
    elif not has_summary:
        checks.append({"item": "Структура разделов", "status": "warning", "note": "Нет раздела «О себе» — короткое вступление помогает рекрутеру быстрее понять, кто вы."})
    else:
        checks.append({"item": "Структура разделов", "status": "ok", "note": "Есть и «О себе», и «Опыт работы»."})

    word_count = len(" ".join([
        resume_data.get("summary") or "",
        *[e.get("description", "") for e in (resume_data.get("experience") or [])],
    ]).split())
    if word_count < 15:
        checks.append({"item": "Длина резюме", "status": "warning", "note": "Описаний очень мало — резюме может выглядеть пустым."})
    elif word_count > 600:
        checks.append({"item": "Длина резюме", "status": "warning", "note": "Много текста — резюме обычно читается лучше в пределах 1 страницы."})
    else:
        checks.append({"item": "Длина резюме", "status": "ok", "note": f"Разумный объём текста (~{word_count} слов в описаниях)."})

    ats_status, ats_note = _ATS_TEMPLATE_NOTES.get(template, ("warning", "Незнакомый шаблон — не могу оценить ATS-совместимость."))
    checks.append({"item": "ATS-совместимость шаблона", "status": ats_status, "note": ats_note})

    return checks


_AUDIT_PROMPT = """Ты — независимый ревьюер резюме. Ниже — данные резюме и уже посчитанные объективные \
проверки (не меняй их и не противоречь им в итоговой оценке).

Данные резюме (JSON):
{resume_json}

Уже посчитанные проверки:
{deterministic_json}

Оцени ЕЩЁ два пункта по тексту резюме:
1. "Измеримые результаты" — есть ли в описании опыта конкретные цифры или измеримые результаты, а не только общие фразы.
2. "Глаголы действия" — используются ли сильные глаголы действия ("разработал", "увеличил", "внедрил") вместо пассивных формулировок ("отвечал за", "занимался").

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"score": <число от 0 до 100, учитывая ВСЕ проверки — и посчитанные выше, и твои два>, "checklist_extra": [{{"item": "Измеримые результаты", "status": "ok"|"warning"|"missing", "note": "<коротко>"}}, {{"item": "Глаголы действия", "status": "ok"|"warning"|"missing", "note": "<коротко>"}}], "strengths": ["<сильная сторона>", ...], "weaknesses": ["<слабое место>", ...], "suggestions": ["<конкретный совет по улучшению>", ...]}}
"""


def audit_resume(resume_data, template, provider, api_key, model=None):
    has_content = any([
        resume_data.get("experience"), resume_data.get("education"),
        resume_data.get("skills"), resume_data.get("summary"),
    ])
    if not has_content:
        raise AIMatchError("Сначала заполните резюме — нечего оценивать")

    deterministic = _deterministic_checks(resume_data, template)

    resume_json = json.dumps({
        k: resume_data.get(k)
        for k in ("headline", "summary", "experience", "education", "skills", "languages")
    }, ensure_ascii=False)[:6000]
    deterministic_json = json.dumps(deterministic, ensure_ascii=False)

    prompt = _AUDIT_PROMPT.format(resume_json=resume_json, deterministic_json=deterministic_json)
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result["score"] = max(0, min(100, int(result.get("score", 0))))
    result["checklist"] = deterministic + (result.pop("checklist_extra", None) or [])
    result.setdefault("strengths", [])
    result.setdefault("weaknesses", [])
    result.setdefault("suggestions", [])
    return result


_MARKET_FIT_PROMPT = """Ты — независимый ревьюер резюме, специализирующийся на сравнении кандидата \
с реальным рынком труда. Ниже — уже посчитанные объективные показатели по реальным вакансиям и \
резюме конкурентов, собранным только что. Не меняй и не оспаривай эти цифры и не выдумывай новые — \
только объясни их простыми словами и дай конкретные советы, что делать дальше.

Данные резюме (JSON):
{resume_json}

Рыночные показатели, посчитанные по реальным собранным данным (JSON):
{market_json}

Если у показателя стоит "_insufficient_data": true — выборка слишком мала, честно скажи об этом \
и не делай вид, что знаешь процент.

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"verdict": "<1-2 предложения — как кандидат смотрится на фоне рынка, по цифрам выше>", \
"strengths": ["<в чём кандидат сильнее рынка, опираясь на цифры>", ...], \
"gaps": ["<конкретный пробел относительно спроса вакансий или похожих резюме>", ...], \
"suggestions": ["<конкретный совет, что добавить или подчеркнуть в резюме, опираясь на пробелы выше>", ...]}}
"""


def synthesize_market_fit(resume_data, market_fit, provider, api_key, model=None):
    resume_json = json.dumps({
        k: resume_data.get(k) for k in ("headline", "summary", "experience", "skills")
    }, ensure_ascii=False)[:4000]
    market_json = json.dumps(market_fit, ensure_ascii=False)[:4000]
    prompt = _MARKET_FIT_PROMPT.format(resume_json=resume_json, market_json=market_json)
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result.setdefault("verdict", "")
    result.setdefault("strengths", [])
    result.setdefault("gaps", [])
    result.setdefault("suggestions", [])
    return result


_BULLETS_PROMPT = """Ты — редактор резюме. Кандидат кратко описал, чем занимался на месте работы ниже. \
Разверни это в 2–3 профессиональных буллета для резюме: конкретные формулировки, сильные глаголы действия, \
измеримый результат — ТОЛЬКО если он логично следует из описания, не выдумывай цифр и фактов, которых там нет.

Должность: {position}
Компания: {company}
Краткое описание от кандидата: {note}

Ответь только текстом буллетов, по одному на строку, каждый начинается с "- ". Без заголовков и пояснений.
"""


def generate_experience_bullets(position, company, note, provider, api_key, model=None):
    note = (note or "").strip()
    if not note:
        raise AIMatchError("Сначала кратко опишите, чем занимались на этом месте")
    prompt = _BULLETS_PROMPT.format(position=position or "не указана", company=company or "не указана", note=note[:1500])
    raw_text = _dispatch(prompt, provider, api_key, model)
    return raw_text.strip()


_COVER_LETTER_PROMPT = """Ты — карьерный консультант. Напиши короткое сопроводительное письмо (3–4 абзаца) \
от лица кандидата для отклика на вакансию ниже, используя ТОЛЬКО факты из его реального резюме — не \
придумывай опыт или навыки, которых там нет. Тон — уверенный, но не хвастливый. Язык — тот же, что в вакансии.

ВАКАНСИЯ:
Название: {title}
Компания: {company}
Описание: {description}

РЕЗЮМЕ КАНДИДАТА:
{cv_text}

Ответь только текстом письма, без заголовка "Сопроводительное письмо" и без пояснений.
"""


def generate_cover_letter(job, cv_text, provider, api_key, model=None):
    prompt = _COVER_LETTER_PROMPT.format(
        title=job.get("title", "")[:300],
        company=job.get("company", "")[:200],
        description=(job.get("description", "") or "")[:4000],
        cv_text=cv_text[:6000],
    )
    raw_text = _dispatch(prompt, provider, api_key, model)
    return raw_text.strip()


_BUILD_RULES = """ПРАВИЛА (обязательны):
1. Используй ТОЛЬКО факты из текста кандидата — ни одной компании, даты, навыка, достижения или должности, \
которых там нет. Если данных для поля нет — оставь его пустым ("" или []), НЕ придумывай и не обобщай.
2. Никакой рекламной воды и самовосхваления: запрещены фразы вида «лучший специалист», «всегда на высоте», \
«эксперт во всём», «универсальный профессионал» и подобные пустые superlatives — если кандидат сам не написал \
именно это как факт. Пиши сухо, конкретно, по делу, в деловом стиле резюме.
3. Каждый навык в "skills" — это ОДНО конкретное название технологии/инструмента/языка/метода (например \
"Python", "Docker", "английский B2", "переговоры"). ЗАПРЕЩЕНО добавлять как навык слова вроде "все", "всё", \
"и т.д.", "др.", "разное" или любые обобщения — если список навыков неясен, оставь skills пустым или включи \
только то, что названо явно.
4. "description" в опыте работы — 1-3 конкретных пункта о том, что реально делал кандидат (по его словам), \
без вымышленных метрик и без хвалебных прилагательных, которых кандидат не давал.
5. Пустое или неизвестное поле — это нормально, лучше пусто, чем выдумано."""

_BUILD_ANALYZE_PROMPT = """Ты помогаешь человеку собрать резюме с нуля по свободному тексту о себе — он мог \
писать как угодно, без структуры. Ниже — этот текст.

{rules}

ТЕКСТ КАНДИДАТА:
{{raw_text}}

Если текста достаточно, чтобы собрать резюме (есть хотя бы что-то про опыт или образование), ответь СТРОГО \
в формате JSON:
{{{{"status": "done", "data": {{{{"full_name": "<если есть в тексте>", "headline": "<желаемая позиция, если понятна из текста>", "summary": "<2-4 сухих деловых предложения по фактам из текста>", "experience": [{{{{"position": "...", "company": "...", "period": "...", "description": "..."}}}}], "education": [{{{{"degree": "...", "school": "...", "period": "..."}}}}], "skills": "навык1, навык2", "languages": [{{{{"name": "...", "level": "..."}}}}]}}}}}}}}

Если текста слишком мало (например, пара слов, или совсем нет ни опыта, ни образования) — не выдумывай, а \
задай до 4 коротких конкретных уточняющих вопросов, которые помогут собрать резюме. Ответь СТРОГО в формате JSON:
{{{{"status": "questions", "questions": ["<вопрос>", ...]}}}}
""".format(rules=_BUILD_RULES)

_BUILD_FINALIZE_PROMPT = """Ты собираешь резюме кандидата по его свободному тексту о себе и ответам на \
уточняющие вопросы.

{rules}

ТЕКСТ КАНДИДАТА:
{{raw_text}}

УТОЧНЯЮЩИЕ ВОПРОСЫ И ОТВЕТЫ:
{{qa_text}}

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{{{"full_name": "...", "headline": "...", "summary": "...", "experience": [{{{{"position": "...", "company": "...", "period": "...", "description": "..."}}}}], "education": [{{{{"degree": "...", "school": "...", "period": "..."}}}}], "skills": "навык1, навык2", "languages": [{{{{"name": "...", "level": "..."}}}}]}}}}
""".format(rules=_BUILD_RULES)

_SKILL_STOPWORDS = {
    "все", "всё", "разное", "другое", "др", "др.", "и т.д", "и т.д.", "и тд",
    "и др", "и др.", "прочее", "прочие", "универсальный", "универсал", "-",
}


def _clean_skills(skills_str):
    parts = [s.strip() for s in skills_str.split(",")]
    cleaned = [s for s in parts if s and s.lower().strip(". ") not in _SKILL_STOPWORDS]
    return ", ".join(cleaned)


def _normalize_resume_data(data):
    data.setdefault("full_name", "")
    data.setdefault("headline", "")
    data.setdefault("summary", "")
    data.setdefault("experience", [])
    data.setdefault("education", [])
    data.setdefault("skills", "")
    data.setdefault("languages", [])
    if isinstance(data.get("skills"), list):
        data["skills"] = ", ".join(str(s) for s in data["skills"])
    data["skills"] = _clean_skills(data["skills"])
    return data


def build_resume_from_text(raw_text, qa_history, provider, api_key, model=None):
    raw_text = (raw_text or "").strip()
    if not raw_text:
        raise AIMatchError("Сначала напишите хоть что-то о себе")

    if not qa_history:
        prompt = _BUILD_ANALYZE_PROMPT.format(raw_text=raw_text[:6000])
        raw = _dispatch(prompt, provider, api_key, model)
        result = _extract_json(raw)
        if result.get("status") == "questions":
            questions = [q for q in (result.get("questions") or []) if str(q).strip()][:4]
            if questions:
                return {"status": "questions", "questions": questions}
        # либо статус "done", либо ИИ не дал вопросов — заканчиваем тем, что есть
        return {"status": "done", "data": _normalize_resume_data(result.get("data") or {})}

    qa_text = "\n".join(f"- {qa.get('question', '')}\n  Ответ: {qa.get('answer', '') or '(без ответа)'}" for qa in qa_history)
    prompt = _BUILD_FINALIZE_PROMPT.format(raw_text=raw_text[:6000], qa_text=qa_text[:3000])
    raw = _dispatch(prompt, provider, api_key, model)
    data = _extract_json(raw)
    return {"status": "done", "data": _normalize_resume_data(data)}


# ---------------------------------------------------------------------------
# Виртуальный HR: красные флаги, карьерная траектория, тренажёр собеседования.
# Красные флаги — как и audit_resume — сперва честно считаем по датам в Python,
# ИИ только комментирует уже посчитанное и не имеет права его оспорить.
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"(19|20)\d{2}")
_CURRENT_RE = re.compile(r"н\.?\s*в\.?|наст\.?\s*вр|present|current|по\s+сей|now", re.I)


def _experience_year_spans(experience):
    spans = []
    for e in experience or []:
        period = str((e or {}).get("period") or "")
        years = [int(m.group(0)) for m in _YEAR_RE.finditer(period)]
        is_current = bool(_CURRENT_RE.search(period))
        if not years and not is_current:
            continue
        spans.append({
            "position": (e or {}).get("position") or "",
            "start": min(years) if years else None,
            "end": max(years) if years else None,
            "current": is_current,
        })
    return spans


def _deterministic_red_flags(resume_data):
    spans = _experience_year_spans(resume_data.get("experience") or [])
    dated = [s for s in spans if s["start"] is not None]
    checks = []

    if len(dated) < 2:
        checks.append({
            "item": "Разрывы между местами работы", "status": "ok",
            "note": "Недостаточно дат в опыте, чтобы честно проверить разрывы — это не значит, что их нет.",
        })
    else:
        dated_sorted = sorted(dated, key=lambda s: s["start"])
        gaps = []
        for prev, nxt in zip(dated_sorted, dated_sorted[1:]):
            prev_end = datetime.date.today().year if prev["current"] else (prev["end"] or prev["start"])
            gap = nxt["start"] - prev_end
            if gap >= 1:
                gaps.append(f"{prev_end}–{nxt['start']}")
        if gaps:
            checks.append({
                "item": "Разрывы между местами работы", "status": "warning",
                "note": f"По годам похоже на разрыв (без учёта месяцев, грубая оценка): {', '.join(gaps)}.",
            })
        else:
            checks.append({"item": "Разрывы между местами работы", "status": "ok", "note": "По годам разрывов не видно."})

    short_stints = sum(
        1 for s in dated
        if not s["current"] and (s["end"] or s["start"]) - s["start"] <= 1
    )
    if short_stints >= 3:
        checks.append({
            "item": "Частая смена мест", "status": "warning",
            "note": f"{short_stints} мест сроком около года или меньше (грубая оценка по годам) — рекрутер может об этом спросить.",
        })
    else:
        checks.append({
            "item": "Частая смена мест", "status": "ok",
            "note": "Похоже на стабильную историю занятости." if not short_stints else f"{short_stints} короткое место — по отдельности не тревожно.",
        })

    return checks


_RED_FLAGS_PROMPT = """Ты — опытный рекрутер, честно и без прикрас оцениваешь резюме на предмет того, что \
реально настораживает нанимающих менеджеров. Ниже уже посчитанные объективные факты по датам в резюме — \
не меняй и не оспаривай их, только прокомментируй по существу и не выдумывай новых.

Данные резюме (JSON):
{resume_json}

Уже посчитанные факты по датам (JSON):
{deterministic_json}

Дополнительно оцени по тексту резюме (не по датам — там уже посчитано):
1. Расплывчатые формулировки обязанностей без результата ("отвечал за", "участвовал в")
2. Явный разрыв в датах без единого слова объяснения в резюме (декрет, учёба, фриланс, переезд)

Если тревожных фактов не нашлось — так и скажи, не выдумывай риски, которых нет.

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"extra_flags": [{{"item": "<название>", "status": "ok"|"warning"|"missing", "note": "<коротко и честно>"}}], \
"overall_note": "<1-2 предложения — как это в целом смотрится глазами рекрутера>", \
"suggestions": ["<конкретный совет снять тревогу — например, что стоит упомянуть в сопроводительном письме>", ...]}}
"""


def analyze_red_flags(resume_data, provider, api_key, model=None):
    if not resume_data.get("experience"):
        raise AIMatchError("Сначала заполните опыт работы — нечего проверять")

    deterministic = _deterministic_red_flags(resume_data)
    resume_json = json.dumps({
        k: resume_data.get(k) for k in ("headline", "summary", "experience", "skills")
    }, ensure_ascii=False)[:6000]
    deterministic_json = json.dumps(deterministic, ensure_ascii=False)

    prompt = _RED_FLAGS_PROMPT.format(resume_json=resume_json, deterministic_json=deterministic_json)
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result["checklist"] = deterministic + (result.pop("extra_flags", None) or [])
    result.setdefault("overall_note", "")
    result.setdefault("suggestions", [])
    return result


_TRAJECTORY_PROMPT = """Ты — карьерный консультант с опытом в найме. На основе РЕАЛЬНОЙ истории опыта \
кандидата предложи 2-3 логичных следующих шага в карьере. Не выдумывай опыт, которого нет — опирайся \
только на то, что реально написано в резюме.

Данные резюме (JSON):
{resume_json}

Общий стаж (лет, грубая оценка по годам в датах): {total_years}

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"directions": [{{"title": "<название следующей роли/направления>", "rationale": "<почему это логичный шаг именно для этого кандидата, опираясь на его реальный опыт>", "skills_to_develop": ["<конкретный навык подтянуть>", ...]}}], "summary": "<1-2 предложения общего вывода>"}}
"""


def suggest_career_trajectory(resume_data, provider, api_key, model=None):
    if not resume_data.get("experience"):
        raise AIMatchError("Сначала заполните опыт работы — не от чего строить траекторию")

    resume_json = json.dumps({
        k: resume_data.get(k) for k in ("headline", "summary", "experience", "skills", "education")
    }, ensure_ascii=False)[:6000]
    total_years = resume_builder.total_experience_years(resume_data.get("experience"))

    prompt = _TRAJECTORY_PROMPT.format(
        resume_json=resume_json,
        total_years=total_years if total_years is not None else "неизвестно",
    )
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result.setdefault("directions", [])
    result.setdefault("summary", "")
    return result


_INTERVIEW_QUESTIONS_PROMPT = """Ты — интервьюер, готовишь кандидата к реальному собеседованию на основе его резюме.{job_block}

Сначала честно найди нюансы — конкретные места, за которые HR или технический интервьюер зацепится: \
{nuance_focus}
Не выдумывай риски, которых не видно из текста — только то, что реально следует из резюме{nuance_vs_job}.

Затем составь вопросы, смешав поведенческие и технические. Каждый вопрос должен быть привязан к конкретному \
пункту резюме (компании, проекту, навыку) или к найденному нюансу — не общий шаблонный вопрос, который \
подошёл бы кому угодно.

РЕЗЮМЕ (текст):
{cv_text}

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"nuances": [{{"point": "<конкретный нюанс/несоответствие>", "why": "<почему это могут спросить именно у этого кандидата>", "advice": "<как лучше подготовиться и что ответить>"}}], "questions": [{{"question": "<текст вопроса>", "type": "поведенческий"|"технический", "based_on": "<на какой пункт резюме или вакансии опирается вопрос>"}}]}}
"""


def generate_interview_questions(cv_text, job_description, provider, api_key, model=None):
    cv_text = (cv_text or "").strip()
    if not cv_text:
        raise AIMatchError("Нет текста резюме для подготовки вопросов")
    job_description = (job_description or "").strip()
    if job_description:
        job_block = f"\n\nВАКАНСИЯ, под которую готовимся:\n{job_description[:3000]}"
        nuance_focus = (
            "разрывы в датах и стаже, несоответствие требуемого опыта/стека вакансии тому, что реально "
            "есть в резюме, смена сферы, слишком частая смена мест, расплывчатые формулировки без результата."
        )
        nuance_vs_job = " и из сравнения с требованиями вакансии"
    else:
        job_block = ""
        nuance_focus = (
            "разрывы в датах и стаже, слишком частая смена мест, расплывчатые формулировки без измеримого "
            "результата, несостыковки между разделами резюме."
        )
        nuance_vs_job = ""

    prompt = _INTERVIEW_QUESTIONS_PROMPT.format(
        cv_text=cv_text[:6000], job_block=job_block, nuance_focus=nuance_focus, nuance_vs_job=nuance_vs_job,
    )
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result.setdefault("questions", [])
    result.setdefault("nuances", [])
    return result


_INTERVIEW_FEEDBACK_PROMPT = """Ты — интервьюер, даёшь честную обратную связь на ответ кандидата на вопрос \
собеседования. Оцени по существу — не хвали просто так, но и не придирайся на пустом месте.

ВОПРОС: {question}

ОТВЕТ КАНДИДАТА: {answer}

РЕЗЮМЕ КАНДИДАТА (только для контекста, не выдумывай на основе него того, чего нет в ответе): {cv_text}

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"score": <целое число от 1 до 10>, "strengths": ["<что в ответе хорошо>", ...], "weaknesses": ["<чего не хватает — конкретика, структура STAR, измеримый результат>", ...], "suggestions": ["<как улучшить именно этот ответ>", ...]}}
"""


def evaluate_interview_answer(question, answer, cv_text, provider, api_key, model=None):
    answer = (answer or "").strip()
    if not answer:
        raise AIMatchError("Сначала напишите ответ на вопрос")

    prompt = _INTERVIEW_FEEDBACK_PROMPT.format(
        question=(question or "")[:500], answer=answer[:3000], cv_text=(cv_text or "")[:4000],
    )
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result["score"] = max(1, min(10, int(result.get("score", 5))))
    result.setdefault("strengths", [])
    result.setdefault("weaknesses", [])
    result.setdefault("suggestions", [])
    return result


# ---------------------------------------------------------------------------
# Подбор вакансий под резюме: быстрый детерминированный препросев по ключевым
# словам (без ИИ — резюме сверяется с десятками/сотнями вакансий из поиска,
# гонять каждую через ИИ было бы и медленно, и дорого). ИИ подключается уже
# отдельно, только к отобранному топу (см. webapp.py /api/jobs/rank-by-resume).
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-zа-яёіїєʼ0-9][a-zа-яёіїєʼ0-9+#./-]{1,30}", re.I)

_RANK_STOPWORDS = {
    "и", "в", "во", "не", "на", "я", "с", "со", "что", "а", "как", "к", "у", "же", "но", "за",
    "по", "из", "от", "для", "до", "или", "то", "это", "этот", "эта", "эти", "тот", "та", "те",
    "он", "она", "они", "мы", "вы", "ты", "его", "её", "их", "мой", "наш", "ваш", "свой",
    "быть", "был", "была", "были", "есть", "будет", "может", "можно", "нужно", "надо",
    "также", "очень", "более", "менее", "уже", "ещё", "еще", "чтобы", "если", "когда", "где",
    "который", "которая", "которые", "которых", "лет", "год", "года", "годы", "месяц", "месяцев",
    "работа", "работы", "работать", "работал", "работала", "компания", "компании", "компанию",
    "й", "із", "як", "цей", "ця", "ці",
    "він", "вона", "вони", "ми", "ви", "ти", "його", "її", "їх", "мій", "наш", "ваш", "свій",
    "бути", "був", "була", "були", "буде", "може", "можна", "потрібно", "треба",
    "також", "дуже", "більш", "менш", "вже", "ще", "щоб", "якщо", "коли", "де",
    "який", "яка", "які", "яких", "років", "рік", "місяць", "місяців",
    "робота", "роботи", "працювати", "працював", "працювала", "компанія", "компанії", "компанію",
    "the", "and", "for", "with", "you", "your", "our", "are", "was", "were", "will", "have",
    "has", "had", "this", "that", "these", "those", "from", "into", "about", "job", "work",
    "years", "year", "month", "months", "company",
}


def _rank_tokenize(text):
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _extract_cv_keywords(cv_text, limit=20):
    cv_text = cv_text or ""
    boost = set()
    m = re.search(r"навыки:\s*(.+)", cv_text, re.I) or re.search(r"навички:\s*(.+)", cv_text, re.I)
    if m:
        for part in re.split(r"[,;]", m.group(1)):
            part = part.strip().lower()
            if len(part) >= 2:
                boost.add(part)
                boost.update(t for t in _rank_tokenize(part) if len(t) >= 2)

    counts = Counter(
        t for t in _rank_tokenize(cv_text)
        if len(t) >= 3 and t not in _RANK_STOPWORDS
    )
    ranked = sorted(counts, key=lambda t: -(counts[t] + (5 if t in boost else 0)))
    keywords = list(dict.fromkeys(list(boost) + ranked))
    return keywords[:limit]


def _job_haystack(job):
    return " ".join(
        str(job.get(k) or "") for k in ("title", "company", "meta", "description")
    ).lower()


def _dedupe_matches(matched):
    matched = sorted(set(matched), key=len, reverse=True)
    kept = []
    for m in matched:
        if not any(m != k and m in k for k in kept):
            kept.append(m)
    return kept


def rank_jobs_by_resume(cv_text, jobs, keyword_limit=20):
    """Ранжирует список вакансий (dict с title/company/meta/description) по
    совпадению с резюме — без ИИ, чисто по частотным ключевым словам резюме
    (с усилением явного списка «Навыки:», если он есть в тексте). Возвращает
    список вида [{"index": i, "score": 0..100, "matched_keywords": [...]}],
    отсортированный по убыванию score. score — не «вероятность подходит», а
    просто нормализованная доля пересечения ключевых слов."""
    keywords = _extract_cv_keywords(cv_text, limit=keyword_limit)
    if not keywords:
        return [{"index": i, "score": 0, "matched_keywords": []} for i in range(len(jobs))]

    denom = max(1, min(len(keywords), 12))
    results = []
    for i, job in enumerate(jobs):
        hay = _job_haystack(job)
        matched = _dedupe_matches([kw for kw in keywords if kw and kw in hay])
        title = (job.get("title") or "").lower()
        title_bonus = 15 if any(kw in title for kw in matched) else 0
        score = min(100, round(100 * len(matched) / denom) + title_bonus)
        results.append({"index": i, "score": score, "matched_keywords": matched[:6]})

    results.sort(key=lambda r: -r["score"])
    return results


_HEADLINE_SUGGEST_PROMPT = """Ты помогаешь кандидату сформулировать «желаемую должность» для резюме \
и поиска вакансий. Вот текст его резюме:

{cv_text}

Вот категории, которые реально используются как фильтры при поиске вакансий на джобсайтах \
(djinni.co, work.ua, robota.ua): {categories}

Задача: подобрать 2-4 короткие формулировки желаемой должности, которые реально соответствуют \
опыту в резюме (не выдумывай навыки, которых там нет). Предпочитай точные совпадения из списка \
категорий выше — это то, что реально можно выбрать фильтром на площадках. Если ни одна категория \
не отражает специализацию точно, добавь одну свою короткую формулировку (например, «Senior Python \
Backend Developer»), но не больше одной — остальное бери из списка категорий.

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"positions": ["<должность 1>", "<должность 2>", ...]}}
"""


def suggest_desired_positions(cv_text, categories, provider, api_key, model=None):
    cv_text = (cv_text or "").strip()
    if not cv_text:
        raise AIMatchError("Сначала добавьте резюме — по пустому тексту нечего предлагать")

    prompt = _HEADLINE_SUGGEST_PROMPT.format(
        cv_text=cv_text[:6000], categories=", ".join(categories),
    )
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    positions = [p.strip() for p in (result.get("positions") or []) if (p or "").strip()]
    if not positions:
        raise AIMatchError("ИИ не смог подобрать должность по этому резюме")
    return {"positions": positions[:4]}


# ---------------------------------------------------------------------------
# Живой тренажёр собеседования — пошаговый чат с ИИ-HR (в отличие от
# generate_interview_questions, который сразу выдаёт весь список вопросов списком).
# Один вызов = одна реплика HR: короткая реакция на последний ответ кандидата (кроме
# самого первого шага) + следующий вопрос, либо вежливое завершение после нескольких
# вопросов. Состояние разговора не хранится на сервере — клиент присылает всю историю
# заново на каждом шаге.
# ---------------------------------------------------------------------------

_HR_CHAT_MAX_QUESTIONS = 6

_HR_CHAT_PROMPT = """Ты — живой HR-интервьюер, ведёшь собеседование с кандидатом в чате. Общайся как настоящий \
человек-рекрутер, естественно и по-деловому — не как анкета из списка вопросов.{job_block}

РЕЗЮМЕ КАНДИДАТА:
{cv_text}

ИСТОРИЯ РАЗГОВОРА ДО СИХ ПОР:
{history}

{turn_instruction}

Ответь СТРОГО в формате JSON без пояснений вне JSON:
{{"reaction": "<короткая реакция на последний ответ кандидата (1-2 предложения) — пусто, если это самое начало>", "message": "<следующая реплика: вопрос или, если пора закончить, вежливое завершение с кратким личным впечатлением>", "is_final": true|false}}
"""


def hr_interview_turn(cv_text, job_description, history, provider, api_key, model=None):
    """history — список {"role": "hr"|"candidate", "text": str}, весь разговор до сих пор
    (включая последний ответ кандидата). Возвращает следующую реплику HR."""
    cv_text = (cv_text or "").strip()
    if not cv_text:
        raise AIMatchError("Нет текста резюме для собеседования")

    job_description = (job_description or "").strip()
    job_block = f"\n\nВАКАНСИЯ, на которую собеседуем:\n{job_description[:3000]}" if job_description else ""

    history = history or []
    hr_turns = sum(1 for h in history if (h or {}).get("role") == "hr")
    history_text = "\n".join(
        f"{'HR' if (h or {}).get('role') == 'hr' else 'Кандидат'}: {(h or {}).get('text', '')}"
        for h in history
    ).strip() or "(разговор ещё не начинался)"

    if not history:
        turn_instruction = (
            "Это самое начало интервью. Коротко поздоровайся, представься и задай ПЕРВЫЙ вопрос — "
            "обычно с чего-то открывающего («расскажите о себе» или похожее по духу), опираясь на резюме."
        )
    elif hr_turns >= _HR_CHAT_MAX_QUESTIONS:
        turn_instruction = (
            "Вопросов уже достаточно. Вежливо заверши интервью: поблагодари кандидата и оставь короткое, "
            "честное личное впечатление — не выдумывай формальный вердикт о найме, просто как живой HR в конце звонка."
        )
    else:
        turn_instruction = (
            f"Это вопрос №{hr_turns + 1} из примерно {_HR_CHAT_MAX_QUESTIONS}. Сначала коротко (1-2 предложения) "
            "отреагируй на последний ответ кандидата по существу — не расплывчатой похвалой, а конкретно: если "
            "ответ дельный, что именно понравилось; если расплывчатый или есть нестыковка с резюме/вакансией, "
            "мягко это отметь. Затем задай следующий вопрос — по резюме, вакансии или по нюансам (пробелы в "
            "стеке, разрывы в датах, смена сферы, недостаток опыта под требования)."
        )

    prompt = _HR_CHAT_PROMPT.format(
        cv_text=cv_text[:6000], job_block=job_block, history=history_text[:6000], turn_instruction=turn_instruction,
    )
    raw_text = _dispatch(prompt, provider, api_key, model)
    result = _extract_json(raw_text)
    result.setdefault("reaction", "")
    result.setdefault("message", "")
    result["is_final"] = bool(result.get("is_final")) or hr_turns >= _HR_CHAT_MAX_QUESTIONS
    if not result.get("message"):
        raise AIMatchError("ИИ не ответил — попробуйте ещё раз")
    return result

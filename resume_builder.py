"""Преобразование структурированных данных конструктора резюме в текст для ИИ-оценки и списков."""

import datetime
import re

_YEAR_RE = re.compile(r"(19|20)\d{2}")
_CURRENT_RE = re.compile(r"н\.?\s*в\.?|наст\.?\s*вр|present|current|по\s+сей|now", re.I)


def total_experience_years(experience):
    """Грубая, но честная оценка стажа: разброс годов, упомянутых в полях "период" опыта работы.
    Не суммирует периоды по отдельности (нет структурированных дат), поэтому overlap в
    параллельных местах работы не задваивается — только диапазон от самого раннего года до
    самого позднего (или до текущего, если период помечен как "по настоящее время")."""
    years_found = []
    has_current = False
    for entry in experience or []:
        period = str((entry or {}).get("period") or "")
        years_found.extend(int(m.group(0)) for m in _YEAR_RE.finditer(period))
        if _CURRENT_RE.search(period):
            has_current = True
    if not years_found and not has_current:
        return None
    end = datetime.date.today().year if has_current else max(years_found)
    start = min(years_found) if years_found else end
    return max(0, end - start)


def flatten_text(data):
    parts = []

    name = (data.get("full_name") or "").strip()
    headline = (data.get("headline") or "").strip()
    if name or headline:
        parts.append(" — ".join(p for p in [name, headline] if p))

    contacts = [p for p in [data.get("email"), data.get("phone"), data.get("location")] if (p or "").strip()]
    if contacts:
        parts.append(", ".join(c.strip() for c in contacts))

    summary = (data.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    achievements = data.get("achievements") or []
    if achievements:
        lines = ["Достижения:"]
        for a in achievements:
            head = " — ".join(p for p in [(a.get("value") or "").strip(), (a.get("label") or "").strip()] if p)
            if head:
                lines.append(f"- {head}")
            desc = (a.get("description") or "").strip()
            if desc:
                lines.append(f"  {desc}")
        if len(lines) > 1:
            parts.append("\n".join(lines))

    experience = data.get("experience") or []
    if experience:
        lines = ["Опыт работы:"]
        for e in experience:
            head = " — ".join(p for p in [(e.get("position") or "").strip(), (e.get("company") or "").strip()] if p)
            period = (e.get("period") or "").strip()
            if period:
                head = f"{head} ({period})" if head else period
            if head:
                lines.append(f"- {head}")
            desc = (e.get("description") or "").strip()
            if desc:
                lines.append(f"  {desc}")
        parts.append("\n".join(lines))

    education = data.get("education") or []
    if education:
        lines = ["Образование:"]
        for e in education:
            head = ", ".join(p for p in [(e.get("degree") or "").strip(), (e.get("school") or "").strip()] if p)
            period = (e.get("period") or "").strip()
            if period:
                head = f"{head} ({period})" if head else period
            if head:
                lines.append(f"- {head}")
        parts.append("\n".join(lines))

    skills = (data.get("skills") or "").strip()
    if skills:
        parts.append(f"Навыки: {skills}")

    languages = data.get("languages") or []
    if languages:
        lang_str = "; ".join(
            f"{(l.get('name') or '').strip()} — {(l.get('level') or '').strip()}"
            for l in languages if (l.get("name") or "").strip()
        )
        if lang_str:
            parts.append(f"Языки: {lang_str}")

    links = data.get("links") or []
    if links:
        link_str = ", ".join(
            f"{(l.get('label') or l.get('url') or '').strip()} ({l.get('url', '').strip()})"
            for l in links if (l.get("url") or "").strip()
        )
        if link_str:
            parts.append(f"Ссылки: {link_str}")

    return "\n\n".join(parts).strip()


def resume_title(data):
    name = (data.get("full_name") or "").strip()
    headline = (data.get("headline") or "").strip()
    if name and headline:
        return f"{name} — {headline}"
    return name or headline or "Резюме без названия"

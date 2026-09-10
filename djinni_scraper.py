#!/usr/bin/env python3
"""
Парсер вакансий с djinni.co (украинская IT-биржа труда).
Работает через обычные HTTP-запросы (urllib), без браузера и внешних зависимостей.

work.ua закрыт Cloudflare managed challenge (требует исполнения JS на каждый
запрос, включая /robots.txt), поэтому получить его список вакансий обычным
HTTP-скриптом невозможно. djinni.co отдаёт HTML напрямую, поэтому вместо
work.ua используется он.

Примеры:
    python3 djinni_scraper.py -k Python --pages 3
    python3 djinni_scraper.py -q "data engineer" --region "Київ" --output jobs.csv
    python3 djinni_scraper.py -k Python --english-level B2 --exp-level 1y --output jobs.json
"""

import argparse
import csv
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://djinni.co/jobs/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

ITEM_START_RE = re.compile(r'<div id="job-item-(\d+)"')
LINK_RE = re.compile(r'href="(/jobs/[^"?#]+/)"')
TITLE_RE = re.compile(r'<h2 class="job-item__position[^"]*"[^>]*>(.*?)</h2>', re.S)
COMPANY_RE = re.compile(
    r'<span class="small text-gray-800 opacity-75 font-weight-500">(.*?)</span>', re.S
)
SALARY_RE = re.compile(
    r'<strong class="text-success text-nowrap small">(.*?)</strong>', re.S
)
HEADER_END_RE = re.compile(r'</header>')
TAGS_DIV_RE = re.compile(r'<div class="job-item__tags">')
META_SPAN_RE = re.compile(
    r'<span class="(?:text-nowrap|location-text)"[^>]*>(.*?)</span>', re.S
)
DESCRIPTION_RE = re.compile(
    r'<span class="js-truncated-text">(.*?)</span>', re.S
)
TAG_STRIP_RE = re.compile(r"<[^>]+>")


def clean_text(raw):
    text = TAG_STRIP_RE.sub("", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def parse_jobs(page_html):
    starts = [m.start() for m in ITEM_START_RE.finditer(page_html)]
    ids = [m.group(1) for m in ITEM_START_RE.finditer(page_html)]
    blocks = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(page_html)
        blocks.append((ids[i], page_html[start:end]))

    jobs = []
    for job_id, block in blocks:
        link_m = LINK_RE.search(block)
        title_m = TITLE_RE.search(block)
        company_m = COMPANY_RE.search(block)
        salary_m = SALARY_RE.search(block)
        desc_m = DESCRIPTION_RE.search(block)

        header_end = HEADER_END_RE.search(block)
        tags_start = TAGS_DIV_RE.search(block)
        meta_text = ""
        if header_end and tags_start:
            meta_block = block[header_end.end():tags_start.start()]
            meta_parts = [clean_text(s) for s in META_SPAN_RE.findall(meta_block)]
            meta_parts = [p for p in meta_parts if p]
            meta_text = " · ".join(meta_parts)

        jobs.append({
            "id": job_id,
            "title": clean_text(title_m.group(1)) if title_m else "",
            "company": clean_text(company_m.group(1)) if company_m else "",
            "salary": clean_text(salary_m.group(1)) if salary_m else "",
            "meta": meta_text,
            "url": urllib.parse.urljoin(BASE_URL, link_m.group(1)) if link_m else "",
            "description": clean_text(desc_m.group(1)) if desc_m else "",
        })
    return jobs


def build_query(args):
    params = {}
    if args.keyword:
        params["primary_keyword"] = args.keyword
    if args.query:
        params["all_keywords"] = args.query
    if args.region:
        params["region"] = args.region
    if args.exp_level:
        params["exp_level"] = args.exp_level
    if args.english_level:
        params["english_level"] = args.english_level
    for key, value in args.param or []:
        params[key] = value
    return params


def scrape(args):
    params = build_query(args)
    all_jobs = []
    seen_ids = set()

    for page in range(1, args.pages + 1):
        page_params = dict(params)
        if page > 1:
            page_params["page"] = page
        url = f"{BASE_URL}?{urllib.parse.urlencode(page_params)}"

        try:
            page_html = fetch(url)
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code} на странице {page}, останавливаюсь.", file=sys.stderr)
            break
        except urllib.error.URLError as e:
            print(f"Ошибка сети на странице {page}: {e.reason}", file=sys.stderr)
            break

        jobs = parse_jobs(page_html)
        new_jobs = [j for j in jobs if j["id"] not in seen_ids]
        if not new_jobs:
            break
        for j in new_jobs:
            seen_ids.add(j["id"])
        all_jobs.extend(new_jobs)

        print(f"Страница {page}: найдено {len(new_jobs)} вакансий", file=sys.stderr)

        if page < args.pages:
            time.sleep(args.delay)

    return all_jobs


def print_table(jobs):
    for j in jobs:
        print(f"{j['title']} — {j['company']}")
        if j["salary"]:
            print(f"  Зарплата: {j['salary']}")
        if j["meta"]:
            print(f"  {j['meta']}")
        print(f"  {j['url']}")
        print()


def write_csv(jobs, path):
    fieldnames = ["id", "title", "company", "salary", "meta", "url", "description"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(jobs)


def write_json(jobs, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Парсер вакансий с djinni.co")
    parser.add_argument("-k", "--keyword", help="Категория/специализация (primary_keyword), напр. Python")
    parser.add_argument("-q", "--query", help="Свободный текстовый поиск (all_keywords)")
    parser.add_argument("--region", help="Регион, напр. 'Київ'")
    parser.add_argument("--exp-level", dest="exp_level", help="Опыт, напр. no_exp, 1y, 2y, 5y")
    parser.add_argument("--english-level", dest="english_level", help="Уровень английского, напр. B2")
    parser.add_argument(
        "--param", action="append", nargs=2, metavar=("KEY", "VALUE"),
        help="Произвольный доп. параметр запроса (можно несколько раз)"
    )
    parser.add_argument("--pages", type=int, default=1, help="Сколько страниц выдачи забрать (по умолчанию 1)")
    parser.add_argument("--delay", type=float, default=1.5, help="Пауза между запросами страниц, сек")
    parser.add_argument("--output", help="Путь к .csv или .json для сохранения результата")

    args = parser.parse_args()
    if not args.keyword and not args.query:
        parser.error("нужно указать -k/--keyword или -q/--query")

    jobs = scrape(args)
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

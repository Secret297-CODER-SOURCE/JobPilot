#!/usr/bin/env python3
"""Юнит-тесты парсера robota.ua (публичный API api.rabota.ua)."""

import io
import sys
import types
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import job_scraper


SAMPLE_VACANCY = {
    "id": 11314814,
    "name": "Data Annotator (AI)",
    "date": "2026-08-24T11:37:43.973",
    "hot": True,
    "salary": 0,
    "salaryFrom": 0,
    "salaryTo": 0,
    "salaryComment": "",
    "cityName": "Киев",
    "notebookId": 6627493,
    "companyName": "SKELAR",
    "shortDescription": "Що&nbsp;варто знати про&nbsp;SKELAR? Це венчур-білдер.",
}

CITIES = [
    {"id": 1, "ua": "Київ", "ru": "Киев", "en": "Kyiv", "vacancyCount": 35000,
     "locativeName": {"ua": "Києві", "ru": "Киеве"}},
    {"id": 2, "ua": "Львів", "ru": "Львов", "en": "Lviv", "vacancyCount": 5000,
     "locativeName": {"ua": "Львові", "ru": "Львове"}},
    {"id": 21, "ua": "Харків", "ru": "Харьков", "en": "Kharkiv", "vacancyCount": 4000,
     "locativeName": {"ua": "Харкові", "ru": "Харькове"}},
]


class SalaryTests(unittest.TestCase):
    def test_range(self):
        self.assertEqual(
            job_scraper.format_rabota_salary({"salaryFrom": 40000, "salaryTo": 120000}),
            "40 000–120 000 грн",
        )

    def test_same_from_to(self):
        self.assertEqual(
            job_scraper.format_rabota_salary({"salaryFrom": 25000, "salaryTo": 25000}),
            "25 000 грн",
        )

    def test_from_only(self):
        self.assertEqual(
            job_scraper.format_rabota_salary({"salaryFrom": 15000}),
            "от 15 000 грн",
        )

    def test_to_only(self):
        self.assertEqual(
            job_scraper.format_rabota_salary({"salaryTo": 80000}),
            "до 80 000 грн",
        )

    def test_flat_salary(self):
        self.assertEqual(
            job_scraper.format_rabota_salary({"salary": 30000}),
            "30 000 грн",
        )

    def test_comment_only(self):
        self.assertEqual(
            job_scraper.format_rabota_salary({"salaryComment": "за результатами співбесіди"}),
            "за результатами співбесіди",
        )

    def test_zeros_are_empty(self):
        self.assertEqual(
            job_scraper.format_rabota_salary({"salary": 0, "salaryFrom": 0, "salaryTo": 0}),
            "",
        )


class ParseJobTests(unittest.TestCase):
    def test_maps_public_api_document(self):
        job = job_scraper.parse_rabota_job(SAMPLE_VACANCY)
        self.assertEqual(job["source"], "rabotaua")
        self.assertEqual(job["id"], "11314814")
        self.assertEqual(job["title"], "Data Annotator (AI)")
        self.assertEqual(job["company"], "SKELAR")
        self.assertEqual(job["url"], "https://robota.ua/company6627493/vacancy11314814")
        self.assertIn("Киев", job["meta"])
        self.assertIn("2026-08-24", job["meta"])
        self.assertIn("гаряча", job["meta"])
        self.assertIn("SKELAR", job["description"])
        self.assertNotIn("&nbsp;", job["description"])

    def test_prefers_full_html_description(self):
        job = job_scraper.parse_rabota_job({
            **SAMPLE_VACANCY,
            "description": "<p>Повний текст</p><ul><li>Python</li><li>Django</li></ul>",
        })
        self.assertIn("Повний текст", job["description"])
        self.assertIn("• Python", job["description"])
        self.assertIn("• Django", job["description"])

    def test_skips_empty_id(self):
        job = job_scraper.parse_rabota_job({"name": "x"})
        self.assertEqual(job["id"], "")
        self.assertEqual(job["url"], "")


class FullDescriptionTests(unittest.TestCase):
    def test_html_to_text_keeps_paragraphs(self):
        text = job_scraper.html_to_text(
            "<head></head><p>Перший абзац</p><p>Другий</p><ul><li>A</li><li>B</li></ul>"
        )
        self.assertIn("Перший абзац", text)
        self.assertIn("Другий", text)
        self.assertIn("• A", text)
        self.assertGreater(text.count("\n"), 1)

    def test_rabota_detail_endpoint_used(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return {
                "id": 11314814,
                "description": "<p>Наш партнер military-tech компанія.</p><p>Основні функції: тестування обладнання.</p>",
            }

        text = job_scraper.fetch_full_job_description(
            {"source": "rabotaua", "id": "11314814", "description": "Наш партнер..."},
            fetch_json=fetch,
        )
        self.assertTrue(any("vacancy?id=11314814" in u for u in calls))
        self.assertIn("тестування обладнання", text)
        self.assertIn("\n", text)

    def test_keeps_snippet_if_detail_fails(self):
        def fetch(_url):
            raise urllib.error.URLError("nope")

        text = job_scraper.fetch_full_job_description(
            {"source": "rabotaua", "id": "1", "description": "короткий анонс"},
            fetch_json=fetch,
        )
        self.assertEqual(text, "короткий анонс")

    def test_djinni_job_post_description(self):
        html = """
        <div class="mb-4 job-post__description">
          <p>We need a <strong>Python</strong> engineer.</p>
          <ul><li>Django</li></ul>
        </div>
        """
        text = job_scraper.fetch_full_job_description(
            {"source": "djinni", "url": "https://djinni.co/jobs/1/", "description": "We need..."},
            fetch_html=lambda _url: html,
        )
        self.assertIn("Python", text)
        self.assertIn("• Django", text)


class CityResolveTests(unittest.TestCase):
    def test_numeric_id(self):
        self.assertEqual(job_scraper.resolve_rabota_city_id("1", CITIES), 1)

    def test_ukrainian_russian_english(self):
        self.assertEqual(job_scraper.resolve_rabota_city_id("Київ", CITIES), 1)
        self.assertEqual(job_scraper.resolve_rabota_city_id("Киев", CITIES), 1)
        self.assertEqual(job_scraper.resolve_rabota_city_id("kyiv", CITIES), 1)

    def test_locative(self):
        self.assertEqual(job_scraper.resolve_rabota_city_id("Києві", CITIES), 1)

    def test_prefix_unique(self):
        self.assertEqual(job_scraper.resolve_rabota_city_id("Харк", CITIES), 21)

    def test_unknown(self):
        self.assertIsNone(job_scraper.resolve_rabota_city_id("Мадрид", CITIES))

    def test_empty(self):
        self.assertIsNone(job_scraper.resolve_rabota_city_id("", CITIES))
        self.assertIsNone(job_scraper.resolve_rabota_city_id(None, CITIES))


class ScrapeTests(unittest.TestCase):
    def setUp(self):
        job_scraper._rabota_cities_cache = None

    def tearDown(self):
        job_scraper._rabota_cities_cache = None

    def test_paginates_and_dedups(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "dictionary/city" in url:
                return CITIES
            if "page=0" in url:
                docs = [dict(SAMPLE_VACANCY, id=i, name=f"Job {i}") for i in range(1, job_scraper.RABOTA_PAGE_SIZE + 1)]
                docs[0] = SAMPLE_VACANCY
                return {"total": 22, "documents": docs}
            if "page=1" in url:
                return {
                    "total": 22,
                    "documents": [
                        dict(SAMPLE_VACANCY, id=11314814, name="dup"),
                        dict(SAMPLE_VACANCY, id=99001, name="C"),
                    ],
                }
            return {"total": 22, "documents": []}

        args = types.SimpleNamespace(query="python", keyword=None, region="Київ", pages=3, delay=0)
        logs = []
        jobs = job_scraper.scrape_rabotaua(args, log=logs.append, fetch=fetch)

        self.assertEqual(jobs[0]["id"], "11314814")
        self.assertEqual(len(jobs), job_scraper.RABOTA_PAGE_SIZE + 1)
        self.assertEqual(jobs[-1]["id"], "99001")
        self.assertTrue(any("cityId=1" in u for u in calls))
        self.assertTrue(any("page=0" in u for u in calls))
        self.assertTrue(any("page=1" in u for u in calls))
        self.assertTrue(any("cityId=1" in msg for msg in logs))

    def test_stops_on_short_page(self):
        def fetch(url):
            if "page=0" in url:
                return {"total": 1, "documents": [SAMPLE_VACANCY]}
            raise AssertionError("не должен запрашивать следующую страницу")

        args = types.SimpleNamespace(query="python", keyword=None, region=None, pages=5, delay=0)
        jobs = job_scraper.scrape_rabotaua(args, log=lambda _: None, fetch=fetch)
        self.assertEqual(len(jobs), 1)

    def test_stops_on_http_error(self):
        def fetch(url):
            raise urllib.error.HTTPError(url, 500, "boom", hdrs=None, fp=io.BytesIO(b""))

        args = types.SimpleNamespace(query="python", keyword=None, region=None, pages=2, delay=0)
        logs = []
        jobs = job_scraper.scrape_rabotaua(args, log=logs.append, fetch=fetch)
        self.assertEqual(jobs, [])
        self.assertTrue(any("HTTP 500" in m for m in logs))

    def test_unknown_city_searches_nationwide(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "dictionary/city" in url:
                return CITIES
            return {"total": 1, "documents": [SAMPLE_VACANCY]}

        args = types.SimpleNamespace(query="python", keyword=None, region="Мадрид", pages=1, delay=0)
        logs = []
        jobs = job_scraper.scrape_rabotaua(args, log=logs.append, fetch=fetch)
        self.assertEqual(len(jobs), 1)
        self.assertTrue(any("cityId=" not in u for u in calls if "vacancy/search" in u))
        self.assertTrue(any("не найден" in m for m in logs))

    def test_two_cities_query_each(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "dictionary/city" in url:
                return CITIES
            if "cityId=1" in url:
                return {"total": 1, "documents": [SAMPLE_VACANCY]}
            if "cityId=2" in url:
                return {"total": 1, "documents": [dict(SAMPLE_VACANCY, id=99, name="Lviv job", cityName="Львов")]}
            raise AssertionError(f"unexpected url {url}")

        args = types.SimpleNamespace(query="python", keyword=None, region="Київ, Львів", pages=1, delay=0)
        logs = []
        jobs = job_scraper.scrape_rabotaua(args, log=logs.append, fetch=fetch)
        self.assertEqual([j["id"] for j in jobs], ["11314814", "99"])
        self.assertTrue(any("cityId=1" in u for u in calls))
        self.assertTrue(any("cityId=2" in u for u in calls))
        self.assertTrue(any("Київ" in m for m in logs))
        self.assertTrue(any("Львів" in m for m in logs))

    def test_mixed_known_and_unknown_skips_unknown(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "dictionary/city" in url:
                return CITIES
            return {"total": 1, "documents": [SAMPLE_VACANCY]}

        args = types.SimpleNamespace(query="python", keyword=None, region="Київ, Мадрид", pages=1, delay=0)
        logs = []
        jobs = job_scraper.scrape_rabotaua(args, log=logs.append, fetch=fetch)
        self.assertEqual(len(jobs), 1)
        search_urls = [u for u in calls if "vacancy/search" in u]
        self.assertTrue(all("cityId=1" in u for u in search_urls))
        self.assertTrue(any("Мадрид" in m and "пропускаю" in m for m in logs))

    def test_all_pages_follows_total(self):
        size = job_scraper.RABOTA_PAGE_SIZE
        calls = []

        def fetch(url):
            calls.append(url)
            if "page=0" in url:
                docs = [dict(SAMPLE_VACANCY, id=i) for i in range(1, size + 1)]
                return {"total": size + 2, "documents": docs}
            if "page=1" in url:
                return {
                    "total": size + 2,
                    "documents": [
                        dict(SAMPLE_VACANCY, id=9001),
                        dict(SAMPLE_VACANCY, id=9002),
                    ],
                }
            raise AssertionError(url)

        args = types.SimpleNamespace(
            query="python", keyword=None, region=None, pages=1, delay=0, all_pages=True,
        )
        jobs = job_scraper.scrape_rabotaua(args, log=lambda _: None, fetch=fetch)
        self.assertEqual(len(jobs), size + 2)
        self.assertTrue(any("page=1" in u for u in calls))

    def test_one_page_does_not_follow_total(self):
        size = job_scraper.RABOTA_PAGE_SIZE

        def fetch(url):
            if "page=1" in url:
                raise AssertionError("не должен листать дальше одной страницы")
            docs = [dict(SAMPLE_VACANCY, id=i) for i in range(1, size + 1)]
            return {"total": 200, "documents": docs}

        args = types.SimpleNamespace(query="python", keyword=None, region=None, pages=1, delay=0)
        jobs = job_scraper.scrape_rabotaua(args, log=lambda _: None, fetch=fetch)
        self.assertEqual(len(jobs), size)


class WorkuaUrlTests(unittest.TestCase):
    def test_city_slug(self):
        self.assertEqual(job_scraper.resolve_workua_city_slug("Київ"), "kyiv")
        self.assertEqual(job_scraper.resolve_workua_city_slug("Львов"), "lviv")
        self.assertEqual(job_scraper.resolve_workua_city_slug("Odesa"), "odesa")
        self.assertIsNone(job_scraper.resolve_workua_city_slug("Мадрид"))

    def test_search_url(self):
        self.assertEqual(
            job_scraper.workua_search_url("python", 1),
            "https://www.work.ua/jobs/python/",
        )
        self.assertEqual(
            job_scraper.workua_search_url("python", 2, "kyiv"),
            "https://www.work.ua/jobs-kyiv/python/?page=2",
        )
        self.assertEqual(
            job_scraper.workua_search_url("", 1, "kyiv"),
            "https://www.work.ua/jobs-kyiv/",
        )
        self.assertEqual(
            job_scraper.workua_search_url("python developer", 1, "lviv"),
            "https://www.work.ua/jobs-lviv/python+developer/",
        )


class FakeWorkuaPage:
    def __init__(self, by_url):
        self.by_url = by_url
        self.current = {"jobs": [], "title": "", "last_page": None}
        self.got = []

    def goto(self, url, timeout=None):
        self.got.append(url)
        if url not in self.by_url:
            self.current = {"jobs": [], "title": "", "last_page": None, "fail": True}
            return
        self.current = self.by_url[url]

    def title(self):
        return self.current.get("title") or ""

    @property
    def url(self):
        return self.current.get("url") or (self.got[-1] if self.got else "")

    def content(self):
        return self.current.get("html") or ""

    def wait_for_selector(self, selector, timeout=None):
        if self.current.get("fail") or self.current.get("title") == "Just a moment...":
            raise TimeoutError("no cards")

    def eval_on_selector_all(self, selector, script):
        return [dict(j) for j in (self.current.get("jobs") or [])]

    def evaluate(self, script):
        return self.current.get("last_page")


def _workua_card(i, city="Київ"):
    return {
        "title": f"Job {i}",
        "url": f"https://www.work.ua/jobs/{i}/",
        "salary": "",
        "company": "Co",
        "location": city,
        "description": "",
    }


class WorkuaScrapeTests(unittest.TestCase):
    def test_all_pages_follows_pagination(self):
        pages = {
            job_scraper.workua_search_url("python", 1): {
                "jobs": [_workua_card(1), _workua_card(2)],
                "last_page": 3,
            },
            job_scraper.workua_search_url("python", 2): {
                "jobs": [_workua_card(3)],
                "last_page": 3,
            },
            job_scraper.workua_search_url("python", 3): {
                "jobs": [_workua_card(4)],
                "last_page": 3,
            },
        }
        fake = FakeWorkuaPage(pages)
        args = types.SimpleNamespace(
            query="python", keyword=None, region=None, pages=1, delay=0, all_pages=True,
        )
        jobs = job_scraper.scrape_workua(args, log=lambda _: None, page=fake)
        self.assertEqual([j["url"] for j in jobs], [
            "https://www.work.ua/jobs/1/",
            "https://www.work.ua/jobs/2/",
            "https://www.work.ua/jobs/3/",
            "https://www.work.ua/jobs/4/",
        ])
        self.assertEqual(len(fake.got), 3)
        self.assertFalse(any("page=4" in u for u in fake.got))

    def test_one_page_does_not_follow_pagination(self):
        pages = {
            job_scraper.workua_search_url("python", 1): {
                "jobs": [_workua_card(1)],
                "last_page": 5,
            },
        }
        fake = FakeWorkuaPage(pages)
        args = types.SimpleNamespace(query="python", keyword=None, region=None, pages=1, delay=0)
        jobs = job_scraper.scrape_workua(args, log=lambda _: None, page=fake)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(fake.got, [job_scraper.workua_search_url("python", 1)])

    def test_challenge_title_and_cf_url(self):
        self.assertTrue(job_scraper._workua_is_challenge("Трохи зачекайте…"))
        self.assertTrue(job_scraper._workua_is_challenge("Just a moment..."))
        self.assertTrue(job_scraper._workua_is_challenge("", "https://www.work.ua/jobs/python/?__cf_chl_rt_tk=x"))
        self.assertFalse(job_scraper._workua_is_challenge("Вакансії Python", "https://www.work.ua/jobs/python/"))

    def test_all_pages_stops_when_no_new_jobs(self):
        pages = {
            job_scraper.workua_search_url("python", 1): {
                "jobs": [_workua_card(1)],
                "last_page": None,
            },
            job_scraper.workua_search_url("python", 2): {
                "jobs": [_workua_card(1)],  # тот же url — дубль
                "last_page": None,
            },
        }
        fake = FakeWorkuaPage(pages)
        args = types.SimpleNamespace(
            query="python", keyword=None, region=None, pages=1, delay=0, all_pages=True,
        )
        jobs = job_scraper.scrape_workua(args, log=lambda _: None, page=fake)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(fake.got), 2)

    def test_challenge_stops_and_keeps_jobs(self):
        pages = {
            job_scraper.workua_search_url("python", 1): {
                "jobs": [_workua_card(1)],
                "last_page": 4,
            },
            job_scraper.workua_search_url("python", 2): {
                "title": "Just a moment...",
                "jobs": [],
                "last_page": None,
            },
        }
        fake = FakeWorkuaPage(pages)
        info = {}
        args = types.SimpleNamespace(
            query="python", keyword=None, region=None, pages=1, delay=0, all_pages=True,
        )
        jobs = job_scraper.scrape_workua(args, log=lambda _: None, info=info, page=fake)
        self.assertEqual(len(jobs), 1)
        self.assertTrue(info.get("challenge_stopped"))
        self.assertEqual(len(fake.got), 2)

    def test_failed_load_without_challenge_sets_load_failed(self):
        fake = FakeWorkuaPage({})
        info = {}
        args = types.SimpleNamespace(
            query="python", keyword=None, region=None, pages=1, delay=0, all_pages=False,
        )
        jobs = job_scraper.scrape_workua(args, log=lambda _: None, info=info, page=fake)
        self.assertEqual(jobs, [])
        self.assertTrue(info.get("load_failed"))
        self.assertFalse(info.get("listing_ok"))

    def test_cf_redirect_url_counts_as_challenge(self):
        pages = {
            job_scraper.workua_search_url("python", 1): {
                "title": "",
                "url": "https://www.work.ua/jobs/python/?__cf_chl_rt_tk=abc",
                "fail": True,
                "jobs": [],
            },
        }
        fake = FakeWorkuaPage(pages)
        info = {}
        args = types.SimpleNamespace(
            query="python", keyword=None, region=None, pages=1, delay=0, all_pages=False,
        )
        jobs = job_scraper.scrape_workua(args, log=lambda _: None, info=info, page=fake)
        self.assertEqual(jobs, [])
        self.assertTrue(info.get("challenge_stopped"))


class ParseRegionsTests(unittest.TestCase):
    def test_splits_and_dedups(self):
        self.assertEqual(job_scraper.parse_regions("Київ, Львів"), ["Київ", "Львів"])
        self.assertEqual(job_scraper.parse_regions("Київ; Київ"), ["Київ"])
        self.assertEqual(job_scraper.parse_regions(["Київ", "Львів / Одеса"]), ["Київ", "Львів", "Одеса"])
        self.assertEqual(job_scraper.parse_regions(""), [])
        self.assertEqual(job_scraper.parse_regions(None), [])

    def test_parse_keywords_and_fallback_terms(self):
        self.assertEqual(job_scraper.parse_keywords("Python, Java"), ["Python", "Java"])
        self.assertEqual(job_scraper.parse_keywords("Python; python"), ["Python"])
        self.assertEqual(len(job_scraper.parse_keywords("a,b,c,d,e,f,g,h,i")), 9)
        fifteen = "Python, Java, JavaScript, TypeScript, React, Node.js, PHP, .NET, Go, Kotlin, QA, DevOps, Data Science, Android, iOS"
        self.assertEqual(len(job_scraper.parse_keywords(fifteen)), 15)
        args = types.SimpleNamespace(keyword="Python, Java", query=None)
        self.assertEqual(job_scraper.fallback_search_terms(args), ["Python", "Java"])
        args.query = "data engineer"
        self.assertEqual(job_scraper.fallback_search_terms(args), ["data engineer"])
        empty = types.SimpleNamespace(keyword=None, query="")
        self.assertEqual(job_scraper.fallback_search_terms(empty), [""])


class RemoteReservationFilterTests(unittest.TestCase):
    def setUp(self):
        job_scraper._rabota_cities_cache = None

    def tearDown(self):
        job_scraper._rabota_cities_cache = None

    def test_normalize_remote_mode(self):
        self.assertEqual(job_scraper.normalize_remote_mode("remote"), "remote")
        self.assertEqual(job_scraper.normalize_remote_mode("include"), "include")
        self.assertEqual(job_scraper.normalize_remote_mode("office"), "")
        self.assertEqual(job_scraper.normalize_remote_mode(None), "")

    def test_djinni_urls(self):
        args = types.SimpleNamespace(keyword="Python", query=None, region="Київ", param=None, remote="remote", reservation=True)
        reservation, passes = job_scraper.djinni_search_passes(args)
        self.assertTrue(reservation)
        self.assertEqual(len(passes), 1)
        self.assertEqual(passes[0][1]["employment"], "remote")
        self.assertEqual(passes[0][1]["region"], "Київ")
        url = job_scraper.djinni_search_url(passes[0][1], page=2, reservation=True)
        self.assertTrue(url.startswith("https://djinni.co/jobs/l-reservation/?"))
        self.assertIn("employment=remote", url)
        self.assertIn("page=2", url)

    def test_djinni_include_adds_remote_pass(self):
        args = types.SimpleNamespace(keyword="Python", query=None, region="Київ, Львів", param=None, remote="include", reservation=False)
        reservation, passes = job_scraper.djinni_search_passes(args)
        self.assertFalse(reservation)
        labels = [label for label, _ in passes]
        self.assertEqual(labels, ["Київ", "Львів", "віддалено"])
        self.assertEqual(passes[-1][1]["employment"], "remote")
        self.assertNotIn("region", passes[-1][1])

    def test_djinni_multiple_keywords(self):
        args = types.SimpleNamespace(
            keyword="Python, Java", query=None, region="Київ", param=None,
            remote="", reservation=False,
        )
        _, passes = job_scraper.djinni_search_passes(args)
        self.assertEqual([label for label, _ in passes], ["Python · Київ", "Java · Київ"])
        self.assertEqual(passes[0][1]["primary_keyword"], "Python")
        self.assertEqual(passes[1][1]["primary_keyword"], "Java")

    def test_workua_targets_union_and_only_remote(self):
        only, _ = job_scraper.workua_search_targets("Київ", remote="remote")
        self.assertEqual(only, [("віддалено", "remote")])
        both, _ = job_scraper.workua_search_targets("Київ, Львів", remote="include")
        self.assertEqual([slug for _, slug in both], ["kyiv", "lviv", "remote"])
        nationwide, _ = job_scraper.workua_search_targets("", remote="include")
        self.assertEqual(nationwide, [(None, None)])

    def test_workua_search_url_remote_and_deferment(self):
        self.assertEqual(
            job_scraper.workua_search_url("python", 1, "remote"),
            "https://www.work.ua/jobs-remote/python/",
        )
        self.assertEqual(
            job_scraper.workua_search_url("python", 1, reservation=True),
            "https://www.work.ua/jobs/deferment/python/",
        )

    def test_rabota_schedule_and_badge_filter(self):
        calls = []
        reserved = dict(SAMPLE_VACANCY, id=1, badges=[{"id": 5052569, "name": "Бронирование сотрудников"}])
        office = dict(SAMPLE_VACANCY, id=2, name="Office", badges=[])

        def fetch(url):
            calls.append(url)
            if "dictionary/city" in url:
                return CITIES
            return {"total": 2, "documents": [reserved, office]}

        args = types.SimpleNamespace(
            query="python", keyword=None, region="Київ", pages=1, delay=0,
            remote="remote", reservation=True,
        )
        jobs = job_scraper.scrape_rabotaua(args, log=lambda _: None, fetch=fetch)
        self.assertTrue(any("scheduleId=3" in u for u in calls if "vacancy/search" in u))
        self.assertEqual([j["id"] for j in jobs], ["1"])
        self.assertIn("бронювання", jobs[0]["meta"])

    def test_rabota_include_adds_nationwide_remote(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "dictionary/city" in url:
                return CITIES
            if "scheduleId=3" in url and "cityId=" not in url:
                return {"total": 1, "documents": [dict(SAMPLE_VACANCY, id=77, name="Remote")]}
            if "cityId=1" in url:
                return {"total": 1, "documents": [SAMPLE_VACANCY]}
            raise AssertionError(url)

        args = types.SimpleNamespace(
            query="python", keyword=None, region="Київ", pages=1, delay=0, remote="include",
        )
        jobs = job_scraper.scrape_rabotaua(args, log=lambda _: None, fetch=fetch)
        self.assertEqual([j["id"] for j in jobs], ["11314814", "77"])
        search = [u for u in calls if "vacancy/search" in u]
        self.assertTrue(any("cityId=1" in u and "scheduleId=" not in u for u in search))
        self.assertTrue(any("scheduleId=3" in u and "cityId=" not in u for u in search))

    def test_rabota_searches_each_keyword(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return {"total": 1, "documents": [dict(SAMPLE_VACANCY, id=len(calls))]}

        args = types.SimpleNamespace(
            query=None, keyword="Python, Java", region=None, pages=1, delay=0,
            remote="", reservation=False, all_pages=False,
        )
        job_scraper.scrape_rabotaua(args, log=lambda _: None, fetch=fetch)
        search = [u for u in calls if "vacancy/search" in u]
        self.assertEqual(len(search), 2)
        self.assertTrue(any("keyWords=Python" in u for u in search))
        self.assertTrue(any("keyWords=Java" in u for u in search))

    def test_workua_scrape_remote_url(self):
        url = job_scraper.workua_search_url("python", 1, "remote")
        fake = FakeWorkuaPage({
            url: {"jobs": [_workua_card(8, "Дистанційно")], "last_page": None},
        })
        args = types.SimpleNamespace(
            query="python", keyword=None, region="Київ", pages=1, delay=0, remote="remote",
        )
        jobs = job_scraper.scrape_workua(args, log=lambda _: None, page=fake)
        self.assertEqual(fake.got, [url])
        self.assertEqual(len(jobs), 1)
        self.assertIn("віддалено", jobs[0]["meta"])


if __name__ == "__main__":
    unittest.main()

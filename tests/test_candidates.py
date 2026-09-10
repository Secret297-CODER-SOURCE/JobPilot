#!/usr/bin/env python3
"""Юнит-тесты анализа рынка кандидатов (без контактов и полных CV)."""

import types
import unittest
from pathlib import Path

sys_path_insert = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(sys_path_insert))

import candidate_scraper
import job_scraper


SAMPLE_RESUME = {
    "id": 555,
    "speciality": "Python Developer",
    "name": "Іван Петренко",
    "firstName": "Іван",
    "lastName": "Петренко",
    "email": "ivan@example.com",
    "phone": "+380501112233",
    "cityName": "Киев",
    "salary": 80000,
    "experience": 5,
    "skills": [{"name": "Django"}, {"name": "PostgreSQL"}],
    "shortDescription": "Пишу бекенд. Telegram @ivan_dev +380501112233",
}


DJINNI_HTML = """
<div class="profile">
  <a href="/q/abc99/">Backend Engineer (Python)</a>
  <span class="profile__salary">$3000</span>
  <span class="location-text">Kyiv</span>
  <div class="profile__skills">FastAPI, Redis, 4 роки досвіду</div>
</div>
"""


class StripPiiTests(unittest.TestCase):
    def test_strips_email_phone_telegram(self):
        text = candidate_scraper.strip_contacts("Пишу бекенд. me@x.com +380501112233 t.me/ivan @ivan_dev")
        self.assertNotIn("@", text)
        self.assertNotIn("380", text)
        self.assertNotIn("t.me", text)
        self.assertIn("Пишу бекенд", text)

    def test_rabota_drops_name_and_contacts(self):
        card = candidate_scraper.parse_rabota_candidate(SAMPLE_RESUME)
        blob = " ".join(str(v) for v in card.values())
        self.assertNotIn("Іван", blob)
        self.assertNotIn("Петренко", blob)
        self.assertNotIn("ivan@example.com", blob)
        self.assertNotIn("380501112233", blob)
        self.assertEqual(card["title"], "Python Developer")
        self.assertEqual(card["source"], "rabotaua")
        self.assertIn("Django", card["skills"])
        self.assertEqual(card["experience_years"], 5)


class DjinniParseTests(unittest.TestCase):
    def test_profile_card(self):
        cards = candidate_scraper.parse_djinni_candidates(DJINNI_HTML)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], "abc99")
        self.assertIn("Backend", cards[0]["title"])
        self.assertTrue(any("FastAPI" in s for s in cards[0]["skills"]) or "fastapi" in " ".join(cards[0]["skills"]).lower())


class RabotaScrapeTests(unittest.TestCase):
    def test_paginates(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "dictionary/city" in url:
                return [{"id": 1, "ua": "Київ", "ru": "Киев", "en": "Kyiv"}]
            if "page=0" in url:
                return {"total": 2, "documents": [dict(SAMPLE_RESUME, id=1), dict(SAMPLE_RESUME, id=2)]}
            raise AssertionError(url)

        args = types.SimpleNamespace(query="python", keyword=None, region="Київ", pages=1, delay=0)
        cards = candidate_scraper.scrape_rabotaua_candidates(args, log=lambda _: None, fetch=fetch)
        self.assertEqual(len(cards), 2)
        self.assertTrue(any("resume/search" in u for u in calls))
        self.assertTrue(any("cityId=1" in u for u in calls))


class WorkuaUrlTests(unittest.TestCase):
    def test_resume_url(self):
        self.assertEqual(
            candidate_scraper.workua_resume_url("python", 1, "kyiv"),
            "https://www.work.ua/resumes-kyiv/python/",
        )
        self.assertIn("page=2", candidate_scraper.workua_resume_url("python", 2, "kyiv"))


class FakeResumePage:
    def __init__(self, by_url):
        self.by_url = by_url
        self.current = {"jobs": [], "title": "", "last_page": None}
        self.got = []

    def goto(self, url, timeout=None):
        self.got.append(url)
        self.current = self.by_url.get(url, {"jobs": [], "fail": True})

    def title(self):
        return self.current.get("title") or ""

    def wait_for_selector(self, selector, timeout=None):
        if self.current.get("fail"):
            raise TimeoutError("no cards")

    def eval_on_selector_all(self, selector, script):
        return [dict(j) for j in (self.current.get("jobs") or [])]

    def evaluate(self, script):
        return self.current.get("last_page")


class WorkuaScrapeTests(unittest.TestCase):
    def test_two_pages(self):
        pages = {
            candidate_scraper.workua_resume_url("python", 1): {
                "jobs": [{
                    "title": "Python dev",
                    "url": "https://www.work.ua/resumes/1/",
                    "salary": "50 000 грн",
                    "location": "Київ",
                    "snippet": "Django, API",
                }],
                "last_page": 2,
            },
            candidate_scraper.workua_resume_url("python", 2): {
                "jobs": [{
                    "title": "Data engineer",
                    "url": "https://www.work.ua/resumes/2/",
                    "salary": "70 000 грн",
                    "location": "Київ",
                    "snippet": "Spark",
                }],
                "last_page": 2,
            },
        }
        fake = FakeResumePage(pages)
        args = types.SimpleNamespace(
            query="python", keyword=None, region=None, pages=1, delay=0, all_pages=True,
        )
        cards = candidate_scraper.scrape_workua_candidates(args, log=lambda _: None, page=fake)
        self.assertEqual(len(cards), 2)
        self.assertEqual(len(fake.got), 2)


class AnalyzeTests(unittest.TestCase):
    def test_gaps_against_cv(self):
        cards = [
            {"source": "rabotaua", "skills": ["Django", "PostgreSQL"], "title": "Python", "salary": "80 000 грн", "experience_years": 5},
            {"source": "workua", "skills": ["Django", "PostgreSQL", "Redis"], "title": "Python", "salary": "60 000 грн", "experience_years": 3},
            {"source": "djinni", "skills": ["Django"], "title": "Backend", "salary": "$3000", "experience_years": 4},
        ]
        stats = candidate_scraper.analyze_market(cards, cv_text="Python, PostgreSQL, Linux")
        self.assertEqual(stats["total"], 3)
        self.assertTrue(stats["cv_compared"])
        missing = {m["skill"] for m in stats["cv_missing"]}
        self.assertIn("django", missing)
        present = {p["skill"] for p in stats["cv_present"]}
        self.assertIn("postgresql", present)
        self.assertGreaterEqual(stats["salary_count"], 2)

    def test_examples_and_experience_buckets(self):
        cards = [
            {
                "source": "rabotaua", "skills": ["Django"], "title": "Python Developer",
                "salary": "80 000 грн", "experience_years": 5, "city": "Київ",
                "snippet": "Пишу backend на Django и Postgres.", "url": "https://x/1",
            },
            {
                "source": "workua", "skills": ["Redis"], "title": "Python Developer",
                "salary": "60 000 грн", "experience_years": 1, "city": "Львів",
                "snippet": "Пишу backend на Django и Postgres.", "url": "https://x/2",
            },
            {
                "source": "djinni", "skills": ["FastAPI"], "title": "Backend Engineer",
                "salary": "$3000", "experience_years": 8, "city": "Kyiv",
                "snippet": "FastAPI, Redis, Postgres в проде.", "url": "https://x/3",
            },
        ]
        stats = candidate_scraper.analyze_market(cards)
        buckets = {b["label"]: b["count"] for b in stats["experience_buckets"]}
        self.assertEqual(buckets.get("0–1"), 1)
        self.assertEqual(buckets.get("4–5"), 1)
        self.assertEqual(buckets.get("6+"), 1)
        self.assertGreaterEqual(len(stats["examples"]), 2)
        self.assertTrue(any((e.get("snippet") or "").strip() for e in stats["examples"]))
        titles = {t["title"] for t in stats["top_titles"]}
        self.assertIn("Python Developer", titles)

    def test_jooble_skipped(self):
        logs = []
        args = types.SimpleNamespace(
            sources=["jooble"], query="python", keyword=None, region=None, pages=1, delay=0,
        )
        cards = candidate_scraper.scrape_all_candidates(args, log=logs.append)
        self.assertEqual(cards, [])
        self.assertTrue(any("не публикует" in m for m in logs))


class BoardLoginTests(unittest.TestCase):
    def test_extract_csrf_and_login_gate(self):
        import board_auth
        html = '<input type="hidden" name="csrfmiddlewaretoken" value="tok123" />'
        self.assertEqual(board_auth.extract_csrf(html), "tok123")
        self.assertTrue(board_auth.djinni_page_requires_login('<title>Увійти на Джин</title>'))
        self.assertFalse(board_auth.djinni_page_requires_login('<a href="/q/abc99/">Python</a>'))

    def test_djinni_login_posts_csrf(self):
        import board_auth
        class FakeSess:
            def __init__(self):
                self.posted = None
            def get(self, url, headers=None):
                if "login" in url:
                    return '<input name="csrfmiddlewaretoken" value="abc" />'
                return '<a href="/q/zz/">Backend</a>'
            def post(self, url, data=None, headers=None):
                self.posted = (url, data, headers)
                return "ok"
        sess = FakeSess()
        out = board_auth.djinni_login("a@b.c", "secret", session=sess, log=lambda _: None)
        self.assertIs(out, sess)
        self.assertEqual(sess.posted[1]["csrfmiddlewaretoken"], "abc")
        self.assertEqual(sess.posted[1]["email"], "a@b.c")

    def test_djinni_candidate_login_skips_developers(self):
        import board_auth
        class FakeSess:
            def __init__(self):
                self.urls = []
                self.posted = None
            def get(self, url, headers=None):
                self.urls.append(url)
                if "login" in url:
                    return '<input name="csrfmiddlewaretoken" value="abc" />'
                if "developers" in url:
                    return '<title>Увійти на Джин</title><input id="email"><input id="password">'
                return '<a href="/q/myprofile/">Me</a>'
            def post(self, url, data=None, headers=None):
                self.posted = (url, data, headers)
                return "ok"
        sess = FakeSess()
        out = board_auth.djinni_candidate_login("a@b.c", "secret", session=sess, log=lambda _: None)
        self.assertIs(out, sess)
        self.assertTrue(any("/my/" in u or "/home" in u for u in sess.urls))
        self.assertFalse(any("developers" in u for u in sess.urls))

    def test_workua_jobseeker_login_fills_form(self):
        import board_auth
        class FakePage:
            def __init__(self):
                self.url = "https://www.work.ua/jobseeker/login/"
                self.filled = {}
                self.clicked = None
            def goto(self, url, timeout=None):
                self.url = url
            def title(self):
                return "Вхід"
            def wait_for_selector(self, sel, timeout=None):
                return True
            def fill(self, sel, value):
                self.filled[sel] = value
            def wait_for_function(self, script, timeout=None):
                return True
            def click(self, sel):
                self.clicked = sel
                self.url = "https://www.work.ua/jobseeker/my/"
            def wait_for_load_state(self, state, timeout=None):
                return True
        page = FakePage()
        self.assertTrue(board_auth.workua_jobseeker_login(page, "me@x.com", "pw", log=lambda _: None))
        self.assertEqual(page.filled["#email"], "me@x.com")
        self.assertEqual(page.filled["#password"], "pw")
        self.assertTrue(page.clicked)

    def test_rabota_token_and_login(self):
        import board_auth
        self.assertEqual(board_auth.parse_rabota_token('"jwt-token"'), "jwt-token")
        self.assertEqual(board_auth.parse_rabota_token('{"token":"abc"}'), "abc")
        token = board_auth.rabota_login(
            "a@b.c", "secret", log=lambda _: None,
            post=lambda url, payload: (self.assertIn("username", payload), '"jwt-xyz"')[1],
        )
        self.assertEqual(token, "jwt-xyz")

    def test_skips_without_board_login(self):
        logs = []
        args = types.SimpleNamespace(
            query="python", keyword=None, region=None, pages=1, delay=0,
        )
        self.assertEqual(candidate_scraper.scrape_djinni_candidates(args, log=logs.append), [])
        self.assertEqual(candidate_scraper.scrape_rabotaua_candidates(args, log=logs.append), [])
        self.assertTrue(any("нет входа" in m and "djinni" in m for m in logs))
        self.assertTrue(any("нет входа" in m and "robota" in m for m in logs))

    def test_workua_login_fills_form(self):
        import board_auth
        class FakePage:
            def __init__(self):
                self.url = "https://www.work.ua/employer/login/"
                self.filled = {}
                self.clicked = None
            def goto(self, url, timeout=None):
                self.url = url
            def title(self):
                return "Вхід"
            def wait_for_selector(self, sel, timeout=None):
                return True
            def fill(self, sel, value):
                self.filled[sel] = value
            def wait_for_function(self, script, timeout=None):
                return True
            def click(self, sel):
                self.clicked = sel
                self.url = "https://www.work.ua/employer/"
            def wait_for_load_state(self, state, timeout=None):
                return True
        page = FakePage()
        self.assertTrue(board_auth.workua_login(page, "boss@co.com", "pw", log=lambda _: None))
        self.assertEqual(page.filled["#user-login"], "boss@co.com")
        self.assertEqual(page.filled["#password"], "pw")
        self.assertEqual(page.clicked, "form#lForm button[type=submit]")

    def test_workua_login_waits_out_challenge(self):
        import board_auth
        class FakePage:
            def __init__(self):
                self.url = "https://www.work.ua/employer/login/"
                self._title = "Just a moment..."
                self.filled = {}
                self.clicked = None
            def goto(self, url, timeout=None):
                self.url = url
            def title(self):
                return self._title
            def wait_for_selector(self, sel, timeout=None):
                return True
            def fill(self, sel, value):
                self.filled[sel] = value
            def wait_for_function(self, script, timeout=None):
                self._title = "Вхід для роботодавців"
                return True
            def click(self, sel):
                self.clicked = sel
                self.url = "https://www.work.ua/employer/"
            def wait_for_load_state(self, state, timeout=None):
                return True
        page = FakePage()
        self.assertTrue(board_auth.workua_login(page, "boss@co.com", "pw", log=lambda _: None))
        self.assertEqual(page.filled["#user-login"], "boss@co.com")

    def test_workua_challenge_helper(self):
        class Stuck:
            def title(self):
                return "Just a moment..."
            def wait_for_function(self, script, timeout=None):
                raise TimeoutError("still challenged")
        self.assertTrue(job_scraper.workua_wait_challenge_clear(Stuck(), timeout=10))
        class Ok:
            def title(self):
                return "Резюме Python"
            def wait_for_function(self, script, timeout=None):
                raise AssertionError("should not wait")
        self.assertFalse(job_scraper.workua_wait_challenge_clear(Ok()))


if __name__ == "__main__":
    unittest.main()

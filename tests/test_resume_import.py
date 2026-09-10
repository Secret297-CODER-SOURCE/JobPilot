#!/usr/bin/env python3
"""Импорт собственного резюме по URL площадки."""

import unittest

import resume_import


DJINNI_HTML = """
<html>
<head>
  <meta property="og:title" content="Іван Петренко — Python Developer">
  <meta property="og:description" content="Backend з Django і PostgreSQL">
  <script type="application/ld+json">
  {"@type":"Person","name":"Іван Петренко","jobTitle":"Python Developer",
   "email":"ivan@example.com","telephone":"+380501112233",
   "address":{"addressLocality":"Київ"},
   "knowsAbout":["Python","Django","PostgreSQL"],
   "description":"5 років бекенду"}
  </script>
</head>
<body>
  <h1>Іван Петренко</h1>
  <span class="skill">FastAPI</span>
  <article class="experience-item">
    <h2>Backend Engineer</h2>
    <div class="company">Acme</div>
    2022 — н.в.
    <p>API і черги.</p>
  </article>
</body>
</html>
"""

WORKUA_HTML = """
<html>
<head>
  <meta property="og:title" content="Марія Коваль — QA Engineer">
  <meta property="og:description" content="Тестування веб-продуктів, Cypress, SQL">
</head>
<body>
  <h1>Марія Коваль</h1>
  <div class="badge">Cypress</div>
  <div class="badge">SQL</div>
</body>
</html>
"""

CHALLENGE_HTML = "<html><title>Just a moment...</title><div id='cf-challenge'></div></html>"


class UrlGuardTests(unittest.TestCase):
    def test_accepts_known_hosts(self):
        _, source = resume_import.classify_url("https://djinni.co/q/abc123/")
        self.assertEqual(source, "djinni")
        _, source = resume_import.classify_url("https://www.work.ua/resumes/555/")
        self.assertEqual(source, "workua")
        _, source = resume_import.classify_url("https://robota.ua/candidates/1")
        self.assertEqual(source, "rabota")

    def test_rejects_unknown_and_homepage(self):
        with self.assertRaises(resume_import.ResumeImportError):
            resume_import.classify_url("https://evil.example/resume")
        with self.assertRaises(resume_import.ResumeImportError):
            resume_import.classify_url("https://djinni.co/")
        with self.assertRaises(resume_import.ResumeImportError):
            resume_import.classify_url("ftp://djinni.co/q/1")


class ParseTests(unittest.TestCase):
    def test_djinni_json_ld_and_skills(self):
        data = resume_import.import_from_url(
            "https://djinni.co/q/abc123/", html=DJINNI_HTML,
        )
        self.assertEqual(data["source"], "djinni")
        self.assertEqual(data["full_name"], "Іван Петренко")
        self.assertEqual(data["headline"], "Python Developer")
        self.assertEqual(data["email"], "ivan@example.com")
        self.assertEqual(data["phone"], "+380501112233")
        self.assertIn("Python", data["skills"])
        self.assertTrue(data["experience"])
        first, last = resume_import.split_name(data["full_name"])
        self.assertEqual(first, "Іван")
        self.assertEqual(last, "Петренко")

    def test_workua_og_tags(self):
        data = resume_import.import_from_url(
            "https://www.work.ua/resumes/555/", html=WORKUA_HTML,
        )
        self.assertEqual(data["full_name"], "Марія Коваль")
        self.assertIn("QA", data["headline"])
        self.assertIn("Cypress", data["skills"])

    def test_challenge_page(self):
        with self.assertRaises(resume_import.ResumeImportError):
            resume_import.import_from_url(
                "https://www.work.ua/resumes/1/", html=CHALLENGE_HTML,
            )

    def test_fetch_is_not_called_when_html_given(self):
        def boom(_url):
            raise AssertionError("fetch should not run")
        resume_import.import_from_url(
            "https://djinni.co/q/abc123/", html=DJINNI_HTML, fetch=boom,
        )


class DiscoverTests(unittest.TestCase):
    def test_djinni_profile_href(self):
        html = '<a href="/q/abc123/">Публічний профіль</a>'
        self.assertEqual(
            resume_import.discover_djinni_profile_url(html),
            "https://djinni.co/q/abc123/",
        )

    def test_workua_resume_href_and_cabinet_id(self):
        html = '<a href="/resumes/555/">Моё резюме</a>'
        self.assertEqual(
            resume_import.discover_workua_resume_url(html),
            "https://www.work.ua/resumes/555/",
        )
        html = '<a href="/jobseeker/my/resumes/777">edit</a>'
        self.assertEqual(
            resume_import.discover_workua_resume_url(html),
            "https://www.work.ua/resumes/777/",
        )

    def test_workua_lists_all_resume_urls(self):
        html = (
            '<a href="/resumes/555/">A</a>'
            '<a href="/resumes/555/">dup</a>'
            '<a href="/jobseeker/my/resumes/777">edit</a>'
        )
        self.assertEqual(
            resume_import.discover_workua_resume_urls(html),
            [
                "https://www.work.ua/resumes/555/",
                "https://www.work.ua/resumes/777/",
            ],
        )


class LoginImportTests(unittest.TestCase):
    def test_djinni_login_finds_public_profile(self):
        class FakeSess:
            def get(self, url, headers=None, timeout=None):
                if "/q/abc123" in url:
                    return DJINNI_HTML
                return '<html><a href="/q/abc123/">Профиль</a></html>'

        def fake_login(email, password, log=None, session=None):
            self.assertEqual(email, "me@djinni.co")
            return session

        data = resume_import.import_from_login(
            "djinni", "me@djinni.co", "secret",
            session=FakeSess(), djinni_login=fake_login,
        )
        self.assertEqual(data["source"], "djinni")
        self.assertEqual(data["full_name"], "Іван Петренко")
        self.assertEqual(data["source_url"], "https://djinni.co/q/abc123/")

    def test_rabota_login_reads_own_json(self):
        payload = {
            "documents": [{
                "id": 99,
                "firstName": "Олег",
                "lastName": "Коваль",
                "speciality": "Python Developer",
                "skills": [{"name": "Python"}, {"name": "Flask"}],
                "cityName": "Львів",
                "email": "oleg@example.com",
                "experiences": [{
                    "position": "Dev",
                    "companyName": "Acme",
                    "period": "2020—2024",
                }],
            }]
        }

        data = resume_import.import_from_login(
            "rabota", "a@b.c", "pw",
            rabota_login=lambda e, p, log=None: "jwt",
            rabota_fetch=lambda url: payload,
        )
        self.assertEqual(data["source"], "rabota")
        self.assertEqual(data["full_name"], "Олег Коваль")
        self.assertIn("Python", data["skills"])
        self.assertEqual(data["experience"][0]["company"], "Acme")

    def test_rabota_login_lists_all_resumes(self):
        payload = {
            "documents": [
                {
                    "id": 99,
                    "firstName": "Олег",
                    "lastName": "Коваль",
                    "speciality": "Python Developer",
                    "skills": [{"name": "Python"}],
                },
                {
                    "id": 100,
                    "firstName": "Олег",
                    "lastName": "Коваль",
                    "speciality": "Team Lead",
                    "skills": [{"name": "Django"}],
                },
            ]
        }
        items = resume_import.list_from_login(
            "rabota", "a@b.c", "pw",
            rabota_login=lambda e, p, log=None: "jwt",
            rabota_fetch=lambda url: payload,
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["headline"], "Python Developer")
        self.assertEqual(items[1]["headline"], "Team Lead")
        self.assertEqual(items[1]["source_url"], "https://robota.ua/candidates/100")

    def test_resume_snapshot_keeps_view_fields(self):
        snap = resume_import.resume_snapshot({
            "source": "djinni",
            "source_url": "https://djinni.co/q/abc/",
            "full_name": "Іван Петренко",
            "headline": "Python Developer",
            "skills": ["Python", "Django"],
            "experience": [{"position": "Dev", "company": "Acme", "period": "2022", "description": "API"}],
        })
        self.assertEqual(snap["skills"], "Python, Django")
        self.assertEqual(snap["experience"][0]["company"], "Acme")
        self.assertNotIn("secret", snap)

    def test_workua_login_opens_found_resume(self):
        class FakePage:
            def __init__(self):
                self.url = ""
            def goto(self, url, timeout=None):
                self.url = url
            def content(self):
                if "/resumes/555" in self.url:
                    return WORKUA_HTML
                return '<a href="/resumes/555/">Моё резюме</a>'
            def title(self):
                return "Мои резюме"

        data = resume_import.import_from_login(
            "workua", "a@b.c", "pw",
            workua_page=FakePage(),
            workua_login=lambda *a, **k: True,
        )
        self.assertEqual(data["full_name"], "Марія Коваль")
        self.assertEqual(data["source_url"], "https://www.work.ua/resumes/555/")

    def test_workua_login_opens_all_found_resumes(self):
        class FakePage:
            def __init__(self):
                self.url = ""
            def goto(self, url, timeout=None):
                self.url = url
            def content(self):
                if "/resumes/555" in self.url:
                    return WORKUA_HTML
                if "/resumes/777" in self.url:
                    return WORKUA_HTML.replace("Марія Коваль", "Олена Коваль").replace(
                        "QA Engineer", "Product Manager"
                    )
                return '<a href="/resumes/555/">A</a><a href="/resumes/777/">B</a>'
            def title(self):
                return "Мои резюме"

        items = resume_import.list_from_login(
            "workua", "a@b.c", "pw",
            workua_page=FakePage(),
            workua_login=lambda *a, **k: True,
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["full_name"], "Марія Коваль")
        self.assertEqual(items[1]["full_name"], "Олена Коваль")
        self.assertEqual(items[1]["source_url"], "https://www.work.ua/resumes/777/")

    def test_login_requires_source_and_password(self):
        with self.assertRaises(resume_import.ResumeImportError):
            resume_import.import_from_login("linkedin", "a@b.c", "pw")
        with self.assertRaises(resume_import.ResumeImportError):
            resume_import.import_from_login("djinni", "", "pw")


if __name__ == "__main__":
    unittest.main()

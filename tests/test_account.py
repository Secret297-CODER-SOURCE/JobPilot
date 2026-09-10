#!/usr/bin/env python3
"""Профиль аккаунта и фильтры поиска."""

import json
import unittest

import job_scraper
import webapp


class FilterModeTests(unittest.TestCase):
    def test_remote_modes(self):
        self.assertEqual(webapp._parse_remote_mode("remote"), "remote")
        self.assertEqual(webapp._parse_remote_mode("include"), "include")
        self.assertEqual(webapp._parse_remote_mode("office"), "")
        self.assertEqual(webapp._parse_remote_mode("hybrid"), "")
        self.assertEqual(webapp._parse_remote_mode(""), "")

    def test_reservation(self):
        self.assertTrue(webapp._parse_reservation(True))
        self.assertTrue(webapp._parse_reservation("1"))
        self.assertTrue(webapp._parse_reservation("on"))
        self.assertFalse(webapp._parse_reservation(""))
        self.assertFalse(webapp._parse_reservation(False))


class AccountHelpersTests(unittest.TestCase):
    def test_email(self):
        self.assertTrue(webapp._valid_email("admin@jobpilot.local"))
        self.assertFalse(webapp._valid_email("not-an-email"))
        self.assertFalse(webapp._valid_email(""))

    def test_clamp_pages_delay(self):
        self.assertEqual(webapp._clamp_int("3", 1, 10, 1), 3)
        self.assertEqual(webapp._clamp_int("99", 1, 10, 1), 10)
        self.assertEqual(webapp._clamp_int("x", 1, 10, 1), 1)
        self.assertEqual(webapp._clamp_float("3.5", 1, 10, 3), 3.5)
        self.assertEqual(webapp._clamp_float("0", 1, 10, 3), 1.0)


class TopKeywordsMergeTests(unittest.TestCase):
    def test_merges_case_and_spaces(self):
        import db as dbmod
        rows = [
            {"term": "python", "n": 24},
            {"term": "Python", "n": 4},
            {"term": " python  ", "n": 2},
            {"term": "django", "n": 3},
        ]
        merged = dbmod.merge_top_keywords(rows, limit=10)
        by_term = {r["term"]: r["n"] for r in merged}
        self.assertEqual(len(merged), 2)
        self.assertEqual(by_term["python"], 30)
        self.assertEqual(by_term["django"], 3)
        self.assertEqual(merged[0]["term"], "python")


class PlatformKeysTests(unittest.TestCase):
    def test_ai_creds_use_platform_not_user(self):
        from unittest.mock import patch
        fake = {
            "active_provider": "openai",
            "openai_api_key": "sk-platform",
            "openai_model": "gpt-4o-mini",
            "anthropic_api_key": "",
        }
        with patch("db.platform_settings", return_value=fake):
            provider, key, model = webapp._ai_creds()
        self.assertEqual(provider, "openai")
        self.assertEqual(key, "sk-platform")
        self.assertEqual(model, "gpt-4o-mini")

    def test_ai_creds_falls_back_to_available_key(self):
        from unittest.mock import patch
        fake = {
            "active_provider": "anthropic",
            "gemini_api_key": "AIza-test",
            "gemini_model": "gemini-2.0-flash",
        }
        with patch("db.platform_settings", return_value=fake):
            provider, key, model = webapp._ai_creds()
        self.assertEqual(provider, "gemini")
        self.assertEqual(key, "AIza-test")

    def test_public_status_hides_secrets(self):
        from unittest.mock import patch
        fake = {
            "anthropic_api_key": "sk-ant-secret-value",
            "jooble_api_key": "jooble-secret",
            "djinni_password": "djinni-secret-pass",
            "djinni_email": "owner@company.com",
        }
        with patch("db.platform_settings", return_value=fake):
            status = webapp._public_platform_status()
        self.assertTrue(status["ai_ready"])
        self.assertTrue(status["jooble_ready"])
        self.assertTrue(status["boards_ready"]["djinni"])
        self.assertFalse(status["boards_ready"]["workua"])
        blob = str(status)
        self.assertNotIn("sk-ant-secret-value", blob)
        self.assertNotIn("jooble-secret", blob)
        self.assertNotIn("djinni-secret-pass", blob)
        self.assertNotIn("owner@company.com", blob)

    def test_mask_key(self):
        self.assertIsNone(webapp._mask_key(""))
        masked = webapp._mask_key("sk-ant-abcdefghij")
        self.assertTrue(masked.startswith("sk-a"))
        self.assertIn("…", masked)
        self.assertNotIn("abcdefghij", masked)

    def test_mask_email(self):
        self.assertIsNone(webapp._mask_email(""))
        masked = webapp._mask_email("owner@company.com")
        self.assertIn("@company.com", masked)
        self.assertNotIn("owner@", masked)

    def test_boards_payload_hides_password(self):
        settings = {
            "cv_djinni_email": "ivan@djinni.co",
            "cv_djinni_password": "super-secret",
            "resume_url_djinni": "https://djinni.co/q/abc/",
        }
        boards = webapp._boards_payload(settings)
        blob = str(boards)
        self.assertNotIn("super-secret", blob)
        self.assertTrue(boards["djinni"]["connected"])
        self.assertEqual(boards["djinni"]["email"], "ivan@djinni.co")
        self.assertIn("@djinni.co", boards["djinni"]["email_masked"])
        self.assertFalse(boards["workua"]["connected"])
        self.assertEqual(boards["djinni"]["resumes"], [])
        self.assertEqual(boards["djinni"]["resume_count"], 0)
        self.assertFalse(boards["djinni"]["resumes_loaded"])

    def test_boards_payload_includes_saved_resumes(self):
        settings = {
            "cv_workua_email": "maria@work.ua",
            "cv_workua_password": "secret",
            "board_resumes_workua": json.dumps([
                {"headline": "QA Engineer", "full_name": "Марія", "source_url": "https://www.work.ua/resumes/555/"},
                {"headline": "PM", "full_name": "Марія", "source_url": "https://www.work.ua/resumes/777/"},
            ], ensure_ascii=False),
        }
        boards = webapp._boards_payload(settings)
        self.assertEqual(boards["workua"]["resume_count"], 2)
        self.assertEqual(boards["workua"]["resumes"][1]["headline"], "PM")
        self.assertTrue(boards["workua"]["resumes_loaded"])
        self.assertEqual(webapp._load_board_resumes("{not-json"), [])


class ActivityLogTests(unittest.TestCase):
    def test_counts_shape(self):
        import db as dbmod
        counts = dbmod.activity_counts(days=14)
        self.assertIn("total", counts)
        self.assertIn("by_action", counts)
        self.assertIsInstance(counts["by_action"], list)


class AutoSearchTests(unittest.TestCase):
    def test_job_key_prefers_url(self):
        self.assertEqual(webapp.job_key({"url": "https://x/1", "title": "A"}), "https://x/1")

    def test_job_key_fallback_and_empty(self):
        self.assertEqual(
            webapp.job_key({"source": "djinni", "title": "Python", "company": "Acme"}),
            "djinni|Python|Acme",
        )
        self.assertEqual(webapp.job_key({}), "")
        self.assertEqual(webapp.job_key(None), "")

    def test_take_new_jobs_dedupes(self):
        seen = set()
        first = webapp.take_new_jobs(
            [{"url": "https://a"}, {"url": "https://b"}, {"url": "https://a"}],
            seen,
        )
        self.assertEqual([j["url"] for j in first], ["https://a", "https://b"])
        second = webapp.take_new_jobs(
            [{"url": "https://b"}, {"url": "https://c"}],
            seen,
        )
        self.assertEqual([j["url"] for j in second], ["https://c"])

    def test_watch_poll_form_first_page_only(self):
        poll = webapp.watch_poll_form({"pages": 30, "all_pages": True, "keyword": "Python"})
        self.assertEqual(poll["pages"], 1)
        self.assertFalse(poll["all_pages"])
        self.assertEqual(poll["keyword"], "Python")

    def test_parse_search_body_watch_default(self):
        form, err = webapp.parse_search_body({"sources": ["djinni"], "keyword": "Python", "remote": "remote"})
        self.assertIsNone(err)
        self.assertTrue(form["watch"])
        self.assertEqual(form["watch_interval"], 60)
        self.assertEqual(form["remote"], "remote")
        self.assertEqual(form["keyword"], "Python")

    def test_parse_search_body_multiple_keywords(self):
        form, err = webapp.parse_search_body({
            "sources": ["djinni"], "keyword": ["Python", "Java", "python"],
        })
        self.assertIsNone(err)
        self.assertEqual(form["keyword"], "Python, Java")
        form, err = webapp.parse_search_body({
            "sources": ["workua"], "keyword": "Python, Java",
        })
        self.assertIsNone(err)
        self.assertEqual(form["keyword"], "Python, Java")

    def test_parse_search_body_stop_and_errors(self):
        form, err = webapp.parse_search_body({"action": "stop"})
        self.assertIsNone(err)
        self.assertEqual(form["action"], "stop")
        form, err = webapp.parse_search_body({"sources": ["djinni"]})
        self.assertIsNone(form)
        self.assertIn("запрос", err)
        form, err = webapp.parse_search_body({"keyword": "Python"})
        self.assertIsNone(form)
        self.assertIn("источник", err)

    def test_ws_wait_stop_timeout_gone(self):
        class StopWs:
            connected = True
            def receive(self, timeout=None):
                return '{"action":"stop"}'
        self.assertEqual(webapp._ws_wait(StopWs(), 5), "stop")
        self.assertEqual(webapp._ws_wait(StopWs(), 0), "timeout")

        class DeadWs:
            connected = True
            def receive(self, timeout=None):
                raise webapp.ConnectionClosed(1000, "bye")
        self.assertEqual(webapp._ws_wait(DeadWs(), 5), "gone")

    def test_do_search_skips_cache_on_watch_poll(self):
        from unittest.mock import patch
        form = {
            "sources": ["djinni"], "keyword": "Python", "query": None, "region": None,
            "pages": 1, "delay": 1, "all_pages": False, "remote": "", "reservation": False,
        }
        chunks = []
        with patch("db.get_cached_search") as get_c, \
             patch("db.set_cached_search") as set_c, \
             patch("db.log_search"), \
             patch("db.log_activity") as log_act, \
             patch("job_scraper.scrape_djinni", return_value=[{"url": "https://x", "title": "T"}]):
            jobs = webapp._do_search(
                "u1", form, lambda m: None,
                use_cache=False, write_cache=False,
                on_chunk=chunks.extend, log_activity=False,
            )
        get_c.assert_not_called()
        set_c.assert_not_called()
        log_act.assert_not_called()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(chunks[0]["url"], "https://x")


class SearchPrefSaveTests(unittest.TestCase):
    def test_keeps_all_category_chips(self):
        from unittest.mock import patch
        stored = {}

        def set_setting(uid, key, value):
            stored[key] = value

        def get_setting(uid, key, default=None):
            return stored.get(key, default)

        kws = (
            "Python, Java, JavaScript, TypeScript, React, Node.js, PHP, "
            ".NET, Go, Kotlin, QA, DevOps, Data Science, Android, iOS"
        )
        with patch("webapp.db.set_setting", side_effect=set_setting), patch("webapp.db.get_setting", side_effect=get_setting):
            saved = webapp._save_search_pref_fields("u1", {
                "keyword": kws,
                "query": "backend",
                "region": "Київ, Львів",
                "sources": ["djinni", "workua"],
                "remote": "remote",
                "reservation": True,
                "all_pages": False,
                "pages": 2,
                "delay": 4,
            })
        self.assertEqual(len(job_scraper.parse_keywords(saved["keyword"])), 15)
        self.assertEqual(saved["remote"], "remote")
        self.assertTrue(saved["reservation"])
        self.assertEqual(saved["query"], "backend")
        self.assertIn("Київ", saved["region"])
        self.assertEqual(stored["pref_query"], "backend")


class ResumeImportApiTests(unittest.TestCase):
    def test_classify_rejects_foreign_host(self):
        import resume_import
        with self.assertRaises(resume_import.ResumeImportError):
            resume_import.classify_url("https://example.com/cv")

    def test_split_name(self):
        import resume_import
        self.assertEqual(resume_import.split_name("Іван Петренко"), ("Іван", "Петренко"))
        self.assertEqual(resume_import.split_name(""), ("", ""))


class JobStoreListTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import time
        from pathlib import Path

        import db as dbmod

        self.dbmod = dbmod
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = dbmod.DB_PATH
        dbmod.DB_PATH = Path(self.tmp.name) / "app.db"
        dbmod.init_db()
        self.time = time

    def tearDown(self):
        self.dbmod.DB_PATH = self.old_path
        self.tmp.cleanup()

    def _job(self, source, i):
        return {
            "source": source,
            "title": f"{source}-{i}",
            "company": "Co",
            "salary": "",
            "meta": "",
            "url": f"https://example.test/{source}/{i}",
            "description": "",
        }

    def test_cached_list_keeps_each_source_instead_of_global_newest(self):
        dbmod = self.dbmod
        rabota = [(self._job("rabotaua", i)["url"], self._job("rabotaua", i)) for i in range(20)]
        dbmod.upsert_jobs(rabota, "sig-rabota")
        self.time.sleep(0.02)
        jooble = [(self._job("jooble", i)["url"], self._job("jooble", i)) for i in range(40)]
        dbmod.upsert_jobs(jooble, "sig-jooble")

        jobs = dbmod.list_jobs_by_query_sigs(["sig-jooble", "sig-rabota"], limit_per_sig=10)
        from collections import Counter
        counts = Counter(j["source"] for j in jobs)
        self.assertEqual(counts["jooble"], 10)
        self.assertEqual(counts["rabotaua"], 10)


class HrSourceTests(unittest.TestCase):
    def test_builder_draft_fills_missing_headline(self):
        from unittest.mock import patch
        cv = {"id": "r1", "original_name": "Ivan", "text_content": "hello"}
        draft = {"template": "classic", "data_json": json.dumps({"full_name": "Ivan", "headline": ""})}
        with patch("webapp.db.get_cv", return_value=cv), patch("webapp.db.get_resume_draft", return_value=draft), patch("webapp.db.all_settings", return_value={"profile_headline": "Python", "profile_location": "Київ"}):
            payload = webapp._resume_data_for_cv("u1", "r1")
        self.assertEqual(payload["resume_data"]["headline"], "Python")
        self.assertEqual(payload["resume_data"]["location"], "Київ")
        self.assertEqual(payload["template"], "classic")
        self.assertEqual(payload["name"], "Ivan")

    def test_uploaded_file_uses_text_as_summary(self):
        from unittest.mock import patch
        cv = {"id": "c1", "original_name": "cv.pdf", "text_content": "Python developer"}
        with patch("webapp.db.get_cv", return_value=cv), patch("webapp.db.get_resume_draft", return_value=None), patch("webapp.db.all_settings", return_value={"profile_headline": "QA"}):
            payload = webapp._resume_data_for_cv("u1", "c1")
        self.assertEqual(payload["resume_data"]["summary"], "Python developer")
        self.assertEqual(payload["resume_data"]["headline"], "QA")

    def test_missing_cv(self):
        from unittest.mock import patch
        with patch("webapp.db.get_cv", return_value=None):
            self.assertIsNone(webapp._resume_data_for_cv("u1", "nope"))


class FirstRunAuthTests(unittest.TestCase):
    def setUp(self):
        webapp.app.config["TESTING"] = True
        self.client = webapp.app.test_client()

    def test_root_goes_to_register_when_empty(self):
        from unittest.mock import patch
        with patch("webapp.db.count_users", return_value=0), patch("webapp.db.get_user", return_value=None):
            resp = self.client.get("/", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/register"))

    def test_login_goes_to_register_when_empty(self):
        from unittest.mock import patch
        with patch("webapp.db.count_users", return_value=0), patch("webapp.db.get_user", return_value=None):
            resp = self.client.get("/login", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/register"))

    def test_root_goes_to_login_when_users_exist(self):
        from unittest.mock import patch
        with patch("webapp.db.count_users", return_value=2), patch("webapp.db.get_user", return_value=None):
            resp = self.client.get("/", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/login"))

    def test_register_page_first_run_copy(self):
        from unittest.mock import patch
        with patch("webapp.db.count_users", return_value=0), patch("webapp.db.get_user", return_value=None):
            resp = self.client.get("/register")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Создайте аккаунт", html)
        self.assertNotIn("Уже есть аккаунт", html)


class WipePersonalDataTests(unittest.TestCase):
    def test_removes_users_keeps_platform_ai_keys(self):
        import tempfile
        from pathlib import Path
        import db as dbmod
        old_path = dbmod.DB_PATH
        old_uploads = dbmod.UPLOADS_DIR
        tmp = tempfile.TemporaryDirectory()
        try:
            dbmod.DB_PATH = Path(tmp.name) / "t.db"
            dbmod.UPLOADS_DIR = Path(tmp.name) / "uploads"
            dbmod.UPLOADS_DIR.mkdir()
            (dbmod.UPLOADS_DIR / "cv.pdf").write_bytes(b"%PDF")
            dbmod.init_db()
            dbmod.create_user("u1", "a@b.c", "hash", "Ann")
            dbmod.set_setting("u1", "profile_phone", "123")
            dbmod.set_platform_setting("gemini_api_key", "keep-me")
            dbmod.set_platform_setting("djinni_email", "wipe@me")
            dbmod.wipe_personal_data()
            self.assertEqual(dbmod.count_users(), 0)
            plat = dbmod.platform_settings()
            self.assertEqual(plat.get("gemini_api_key"), "keep-me")
            self.assertNotIn("djinni_email", plat)
            self.assertFalse((dbmod.UPLOADS_DIR / "cv.pdf").exists())
        finally:
            dbmod.DB_PATH = old_path
            dbmod.UPLOADS_DIR = old_uploads
            tmp.cleanup()

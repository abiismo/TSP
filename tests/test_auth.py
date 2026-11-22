"""Real WSGI login, cookie, persistence and rejection checks with isolated SQLite."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults

from app.auth import AuthStore, SESSION_SECONDS
from app.main import application

EMAIL = "estudiante@example.test"
PASSWORD = "Fragancia de prueba 2026!"


class LoginIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.baseline = Path(cls.temp.name) / "baseline.sqlite3"
        AuthStore(cls.baseline).create_user(EMAIL, PASSWORD, "Estudiante")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.path.write_bytes(self.baseline.read_bytes())
        self.now = 1_000_000
        self.store = AuthStore(self.path, clock=lambda: self.now)
        self.mock_store = patch("app.main.auth_store", self.store)
        self.mock_store.start()
        self.addCleanup(self.mock_store.stop)

    def request(self, path, method="GET", data=None, cookie="", csrf="", origin="http://127.0.0.1:8000", secure=False, raw=None, **overrides):
        environ = {}
        setup_testing_defaults(environ)
        body = raw if raw is not None else json.dumps(data if data is not None else {}).encode()
        environ.update({"PATH_INFO": path, "REQUEST_METHOD": method,
            "HTTP_HOST": "127.0.0.1:8000", "HTTP_ORIGIN": origin,
            "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(body)),
            "HTTP_COOKIE": cookie, "HTTP_X_CSRF_TOKEN": csrf,
            "REMOTE_ADDR": "127.0.0.1", "wsgi.input": io.BytesIO(body),
            "wsgi.url_scheme": "https" if secure else "http"})
        environ.update(overrides)
        response = {}

        def start_response(status, headers):
            response.update(status=int(status.split()[0]), headers=dict(headers))

        payload = b"".join(application(environ, start_response))
        response["body"] = json.loads(payload)
        return response

    def login(self, **kwargs):
        return self.request("/api/auth/login", "POST", {"email": EMAIL, "password": PASSWORD}, **kwargs)

    @staticmethod
    def cookie(response):
        return response["headers"]["Set-Cookie"].split(";", 1)[0]

    def test_anonymous_session_does_not_grant_access(self):
        response = self.request("/api/auth/session")
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], {"authenticated": False})
        self.assertEqual(response["headers"]["Cache-Control"], "no-store")

    def test_login_persists_across_requests_and_store_restart(self):
        response = self.login()
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"]["user"]["email"], EMAIL)
        self.assertNotIn("password", response["body"]["user"])
        cookie = self.cookie(response)
        self.assertGreater(len(cookie), 40)
        self.assertIn("HttpOnly", response["headers"]["Set-Cookie"])
        self.assertIn("SameSite=Lax", response["headers"]["Set-Cookie"])
        self.store = AuthStore(self.path, clock=lambda: self.now)
        with patch("app.main.auth_store", self.store):
            self.assertTrue(self.request("/api/auth/session", cookie=cookie)["body"]["authenticated"])

    def test_email_normalization_and_password_spaces_are_preserved(self):
        response = self.request("/api/auth/login", "POST", {"email": "  ESTUDIANTE@EXAMPLE.TEST ", "password": PASSWORD})
        self.assertEqual(response["status"], 200)
        response = self.request("/api/auth/login", "POST", {"email": EMAIL, "password": " " + PASSWORD})
        self.assertEqual(response["status"], 401)

    def test_wrong_password_and_unknown_account_have_same_error(self):
        errors = []
        for email in [EMAIL, "desconocido@example.test"]:
            response = self.request("/api/auth/login", "POST", {"email": email, "password": "incorrecta"})
            self.assertEqual(response["status"], 401)
            self.assertNotIn("Set-Cookie", response["headers"])
            errors.append(response["body"])
        self.assertEqual(errors[0], errors[1])

    def test_password_storage_uses_unique_salts_and_no_plaintext(self):
        self.store.create_user("otra@example.test", PASSWORD, "Otra cuenta")
        with self.store.connection() as db:
            users = db.execute("SELECT salt,password_hash FROM users").fetchall()
            tokens = db.execute("SELECT token_hash FROM sessions").fetchall()
        self.assertNotEqual(users[0]["salt"], users[1]["salt"])
        self.assertNotEqual(users[0]["password_hash"], users[1]["password_hash"])
        self.assertNotIn(PASSWORD.encode(), self.path.read_bytes())
        self.assertEqual(tokens, [])
        login = self.login()
        self.assertNotIn(self.cookie(login).split("=", 1)[1].encode(), self.path.read_bytes())

    def test_expired_and_forged_sessions_are_rejected_and_cookie_cleared(self):
        login = self.login()
        self.now += SESSION_SECONDS + 1
        for cookie in [self.cookie(login), "tsp_session=falso"]:
            response = self.request("/api/auth/session", cookie=cookie)
            self.assertFalse(response["body"]["authenticated"])
            self.assertIn("Max-Age=0", response["headers"]["Set-Cookie"])

    def test_logout_revokes_token_server_side(self):
        login = self.login()
        cookie = self.cookie(login)
        response = self.request("/api/auth/logout", "POST", cookie=cookie, csrf=login["body"]["csrf_token"])
        self.assertEqual(response["status"], 200)
        self.assertIn("Max-Age=0", response["headers"]["Set-Cookie"])
        self.assertFalse(self.request("/api/auth/session", cookie=cookie)["body"]["authenticated"])

    def test_logout_requires_valid_csrf_and_keeps_session_on_failure(self):
        login = self.login()
        cookie = self.cookie(login)
        for csrf in ["", "incorrecto", "ñ"]:
            self.assertEqual(self.request("/api/auth/logout", "POST", cookie=cookie, csrf=csrf)["status"], 403)
        self.assertTrue(self.request("/api/auth/session", cookie=cookie)["body"]["authenticated"])

    def test_relogin_rotates_and_invalidates_previous_cookie(self):
        first = self.login()
        second = self.login(cookie=self.cookie(first))
        self.assertNotEqual(self.cookie(first), self.cookie(second))
        self.assertFalse(self.request("/api/auth/session", cookie=self.cookie(first))["body"]["authenticated"])
        self.assertTrue(self.request("/api/auth/session", cookie=self.cookie(second))["body"]["authenticated"])

    def test_cross_origin_missing_origin_and_form_posts_are_rejected(self):
        for origin in ["https://otro.example", "", "null", "http://["]:
            self.assertEqual(self.login(origin=origin)["status"], 403)
        self.assertEqual(self.login(CONTENT_TYPE="application/x-www-form-urlencoded")["status"], 415)

    def test_wrong_methods_and_unknown_routes(self):
        self.assertEqual(self.request("/api/auth/login")["status"], 405)
        self.assertEqual(self.request("/api/auth/logout")["status"], 405)
        self.assertEqual(self.request("/api/auth/session", "POST")["status"], 405)
        self.assertEqual(self.request("/api/auth/register", "POST")["status"], 404)

    def test_malformed_oversized_and_invalid_inputs(self):
        for raw in [b"not json", b"null", b"[]", b"\xff", b"x" * 4097]:
            self.assertIn(self.request("/api/auth/login", "POST", raw=raw)["status"], [400, 413])
        for data in [{}, {"email": 7, "password": "x"}, {"email": EMAIL, "password": []},
                     {"email": "bad", "password": "x"}, {"email": EMAIL, "password": "x" * 129},
                     {"email": "\ud800@example.test", "password": "x"}, {"email": EMAIL, "password": "\ud800"}]:
            self.assertEqual(self.request("/api/auth/login", "POST", data)["status"], 400)
        self.assertEqual(self.login(CONTENT_LENGTH="bad")["status"], 400)

    def test_rate_limit_persists_and_expires(self):
        for _ in range(5):
            response = self.request("/api/auth/login", "POST", {"email": EMAIL, "password": "incorrecta"})
            self.assertEqual(response["status"], 401)
        response = self.login()
        self.assertEqual(response["status"], 429)
        self.assertEqual(response["headers"]["Retry-After"], "900")
        self.now += 901
        self.assertEqual(self.login()["status"], 200)

    def test_https_cookie_has_secure_attribute(self):
        response = self.login(secure=True, origin="https://127.0.0.1:8000")
        self.assertEqual(response["status"], 200)
        self.assertIn("; Secure", response["headers"]["Set-Cookie"])

    def test_registration_contract_rejects_duplicates_and_weak_passwords(self):
        with self.assertRaises(ValueError):
            self.store.create_user(EMAIL.upper(), PASSWORD, "Duplicado")
        with self.assertRaises(ValueError):
            self.store.create_user("otra@example.test", "corta", "Otra")
        with self.assertRaises(ValueError):
            self.store.create_user("otra@example.test", PASSWORD, " ")

    def test_storage_failure_is_recoverable_and_does_not_expose_internal_details(self):
        with patch.object(self.store, "login", side_effect=OSError("private-path")):
            response = self.login()
        self.assertEqual(response["status"], 503)
        self.assertNotIn("private-path", response["body"]["error"])


if __name__ == "__main__":
    unittest.main()
